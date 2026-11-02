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
        appconfig_environment: str,
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
