---
title: "RDS password rotation with CDK"
category: persistence
tags: [settings, database, aws-rds, aws-cdk, secrets-rotation]
status: draft
related: ["[[2b-settings-db]]", "[[2b-settings-db-rotated-password]]", "[[2b-settings-db-iam-auth]]", "[[2b-settings-db-rds-tls]]", "[[1e-settings-lambda]]"]
---

# RDS password rotation with CDK

## Problem
Rotation needs several AWS pieces wired together: the DB credentials in Secrets Manager, a rotation Lambda that can reach both the database and Secrets Manager, a schedule, and read access for the app. Set up by hand they drift between environments.

## Use when
- The infrastructure is defined with AWS CDK and the app authenticates with a rotated password ([[2b-settings-db-rotated-password]]).

## Avoid when
- The app uses IAM authentication ([[2b-settings-db-iam-auth]]). With CDK, that's `iam_authentication=True` and `instance.grant_connect(function, "orders_app")` instead, or an RDS Proxy (below).

## Solution
Two secrets, each rotated on a schedule: the master user's (single-user rotation, used only for administration and to rotate the app user) and the app user's (multi-user rotation, read by the app).

```python
# infra/database_stack.py
from aws_cdk import Duration, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from constructs import Construct


class DatabaseStack(Stack):
    def __init__(self, scope: Construct, id: str, *, vpc: ec2.IVpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.instance = rds.DatabaseInstance(
            self, "OrdersDb",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_17),
            vpc=vpc,
            credentials=rds.Credentials.from_generated_secret("postgres"),   # master user, in Secrets Manager
            storage_encrypted=True,
            deletion_protection=True,
        )

        # Master password: single-user rotation
        self.instance.add_rotation_single_user(automatically_after=Duration.days(30))

        # App user: its own secret, rotated by alternating between two users
        self.app_secret = rds.DatabaseSecret(
            self, "OrdersAppSecret",
            username="orders_app",
            master_secret=self.instance.secret,   # adds "masterarn": rotation uses the master to change passwords
        ).attach(self.instance)                   # adds host, port, engine
        self.instance.add_rotation_multi_user(
            "OrdersAppRotation",
            secret=self.app_secret,
            automatically_after=Duration.days(30),
        )
```

```python
# infra/service_stack.py
import json

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_codedeploy as codedeploy
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from infra.database_stack import DatabaseStack


class ServiceStack(Stack):
    def __init__(
        self, scope: Construct, id: str, *,
        vpc: ec2.IVpc, database: DatabaseStack, image_tag: str, auth_issuer: str, auth_audiences: list[str],
        appconfig_environment: str, is_prd: bool,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        # The container image from Dockerfile: FastAPI behind the Lambda Web Adapter
        repository = ecr.Repository.from_repository_name(self, "OrdersApiRepo", "orders-api")
        self.function = lambda_.DockerImageFunction(
            self, "OrdersApi",
            code=lambda_.DockerImageCode.from_ecr(repository, tag_or_digest=image_tag),
            memory_size=1024,
            timeout=Duration.seconds(30),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            environment={
                # No secrets here: env vars are readable via GetFunctionConfiguration (4 KB total)
                # Turns on the production checks in Settings (no debug, no wildcard CORS)
                "APP__IS_PRD": "true" if is_prd else "false",
                "DB__HOST": database.instance.db_instance_endpoint_address,
                "DB__NAME": "orders",
                "DB__USER": "orders_app",
                "DB__SSLROOTCERT": "/etc/ssl/certs/rds-global-bundle.pem",   # baked into the image
                # One request at a time per execution environment: one connection is enough
                "DB__POOL_SIZE": "1",
                "DB__MAX_OVERFLOW": "0",
                "DB__AUTH__METHOD": "rotated_secret",
                "DB__AUTH__SECRET_ID": database.app_secret.secret_arn,
                "DB__AUTH__REGION": self.region,
                "AUTH__ISSUER": auth_issuer,
                "AUTH__AUDIENCES": json.dumps(auth_audiences),
                # Where the app reads the runtime flags: the AppConfig environment is named per stage
                "FEATURES__RUNTIME_FLAGS__APPLICATION": "orders-api",
                "FEATURES__RUNTIME_FLAGS__ENVIRONMENT": appconfig_environment,
                # The agent fetches these during its own init, before the app's, so the first read is a cache hit
                "AWS_APPCONFIG_EXTENSION_PREFETCH_LIST": (
                    f"/applications/orders-api/environments/{appconfig_environment}/configurations/runtime-flags"
                ),
            },
        )
        # The app reads the current password at runtime (2b-settings-db-rotated-password),
        # not as an env var, which would freeze it into the published version
        database.app_secret.grant_read(self.function)
        # The AppConfig agent extension calls AppConfig with the function's role
        self.function.add_to_role_policy(iam.PolicyStatement(
            actions=["appconfig:StartConfigurationSession", "appconfig:GetLatestConfiguration"],
            resources=[f"arn:{self.partition}:appconfig:{self.region}:{self.account}:application/*"],
        ))
        self.function.connections.allow_to_default_port(database.instance)   # rule lives here: no stack cycle

        # Traffic goes to the "live" alias, never to $LATEST; CodeDeploy shifts it between versions
        self.alias = lambda_.Alias(self, "Live", alias_name="live", version=self.function.current_version)
        # CodeDeploy shifts the alias from the old version to the new one; an alarm rolls it back.
        # Errors counts failed invocations (init errors from bad config, crashes, timeouts), not 500s.
        errors = cloudwatch.Alarm(
            self, "OrdersApiErrors",
            metric=self.alias.metric_errors(period=Duration.minutes(1)),
            threshold=1, evaluation_periods=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        codedeploy.LambdaDeploymentGroup(
            self, "OrdersApiDeployment",
            alias=self.alias,
            deployment_config=codedeploy.LambdaDeploymentConfig.CANARY_10_PERCENT_5_MINUTES,
            alarms=[errors],                  # an alarm rolls the alias back
        )
        # Auth NONE: the app verifies JWTs itself. No cors=: CORS is set in the app only
        self.url = self.alias.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)
        CfnOutput(self, "OrdersApiUrl", value=self.url.url)
```

- **Wiring lives in the service stack.** The database stack only creates resources; the service stack reads `database.instance` and `database.app_secret`, grants the function read access, and opens the DB security group to it. Doing either from the database stack creates references in both directions, which CDK rejects as a dependency cycle.
- **Encrypted, protected storage.** `storage_encrypted=True` (CDK warns without it) and `deletion_protection=True`, so `cdk destroy` or a replaced construct can't drop the database.
- **Single-user rotation for the master.** Only administrators and the rotation function use it; a brief gap during rotation doesn't affect the app.
- **Multi-user rotation for the app.** It alternates between `orders_app` and a clone user, so the previous password stays valid while running execution environments pick up the new one.
- **Read access, not env vars.** `grant_read` lets the app fetch the secret at runtime. Lambda has no secret injection; a `{{resolve:secretsmanager:...}}` env var would freeze the password into the published version and show it in the function configuration.
- **The rest of the service stack** is covered elsewhere: the AppConfig env vars and IAM actions in [[2f-settings-feature-flags-appconfig]], the alarm and CodeDeploy group in [[1d-settings-deployments]].
- **`automatically_after`** defaults to 30 days for both; shorter is possible, but each rotation briefly invalidates cached passwords.

### With RDS Proxy
Recommended on Lambda ([[1e-settings-lambda]]). RDS Proxy doesn't support the alternating-users strategy, so the secret it reads gets single-user rotation, and the app authenticates to the proxy with IAM ([[2b-settings-db-rds-tls]]):

```python
# infra/database_stack.py (fragment): replaces the multi-user rotation above
from aws_cdk import aws_secretsmanager as secretsmanager

secretsmanager.SecretRotation(
    self, "OrdersAppRotation",
    application=secretsmanager.SecretRotationApplication.POSTGRES_ROTATION_SINGLE_USER,
    secret=self.app_secret,
    target=self.instance,
    vpc=vpc,
    automatically_after=Duration.days(30),
)
# Also opens the DB security group to the proxy
self.proxy = self.instance.add_proxy("OrdersProxy", secrets=[self.app_secret], vpc=vpc, iam_auth=True)
```

```python
# infra/service_stack.py (fragment): instead of the secret and instance wiring
environment={
    "DB__HOST": database.proxy.endpoint,
    "DB__SSLROOTCERT": "/etc/ssl/certs/amazon-root-cas.pem",
    "DB__AUTH__METHOD": "iam",
    "DB__AUTH__REGION": self.region,
    ...
}
database.proxy.grant_connect(self.function, "orders_app")
self.function.connections.allow_to(database.proxy, ec2.Port.tcp(5432))   # a proxy has no default port
```

- The function no longer reads the secret; only the proxy does. `orders_app` keeps its password and must not have `rds_iam` ([[2b-settings-db-iam-auth]]).

## Pitfalls
- **Rotation Lambda without network access.** It runs in the database's VPC and must reach Secrets Manager: through a NAT gateway or a Secrets Manager VPC interface endpoint (`endpoint=` on the rotation options).
- **App user missing from the database.** Create `orders_app` with its grants first (e.g. in a migration); multi-user rotation clones an existing user.
- **The app using the master secret.** A compromised app then has full control of the database. Give the app its own least-privilege user.
- **Cross-stack wiring in both directions.** Granting access or adding security group rules for the function from the database stack fails with a dependency cycle; do it in the service stack.
- **Rotated secrets in Lambda env vars.** Works until the first rotation; see [[2b-settings-db-rotated-password]].
- **Multi-user rotation behind RDS Proxy.** The proxy doesn't support it; use single-user rotation for secrets the proxy reads.

## Related
- [[2b-settings-db]]
- [[2b-settings-db-rotated-password]]
- [[2b-settings-db-iam-auth]]
- [[2b-settings-db-rds-tls]]
- [[1e-settings-lambda]]
