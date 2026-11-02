import pytest

cdk = pytest.importorskip("aws_cdk")

from aws_cdk import App, Environment, Stack  # noqa: E402
from aws_cdk import aws_ec2 as ec2  # noqa: E402
from aws_cdk.assertions import Match, Template  # noqa: E402

from infra.database_stack import DatabaseStack  # noqa: E402
from infra.service_stack import ServiceStack  # noqa: E402


def test_stacks_synthesize():
    app = App()
    env = Environment(account="123456789012", region="us-east-1")
    network = Stack(app, "Network", env=env)
    vpc = ec2.Vpc(network, "Vpc")
    database = DatabaseStack(app, "Database", vpc=vpc, env=env)
    service = ServiceStack(
        app, "Service", vpc=vpc, database=database, image_tag="1.4.2",
        auth_issuer="https://issuer.test", auth_audiences=["client"], appconfig_environment="prd", env=env,
    )
    app.synth()                                               # fails on dependency cycles

    db = Template.from_stack(database)
    assert len(db.find_resources("AWS::SecretsManager::RotationSchedule")) == 2
    db.has_resource_properties("AWS::RDS::DBInstance", {"StorageEncrypted": True, "DeletionProtection": True})

    template = Template.from_stack(service)
    functions = template.find_resources("AWS::Lambda::Function")
    (function,) = functions.values()
    assert function["Properties"]["PackageType"] == "Image"
    env_vars = function["Properties"]["Environment"]["Variables"]
    assert {"DB__AUTH__METHOD", "DB__AUTH__SECRET_ID", "DB__POOL_SIZE", "AUTH__ISSUER"} <= env_vars.keys()
    assert not any("PASSWORD" in name for name in env_vars)  # secrets are read at runtime, not set here
    assert env_vars["FEATURES__RUNTIME_FLAGS__ENVIRONMENT"] == "prd"
    assert env_vars["AWS_APPCONFIG_EXTENSION_PREFETCH_LIST"] == (
        "/applications/orders-api/environments/prd/configurations/runtime-flags"
    )
    template.has_resource_properties("AWS::IAM::Policy", {
        "PolicyDocument": {"Statement": Match.array_with([Match.object_like({
            "Action": ["appconfig:StartConfigurationSession", "appconfig:GetLatestConfiguration"],
        })])},
    })

    template.has_resource_properties("AWS::Lambda::Alias", {"Name": "live"})
    template.has_resource_properties("AWS::Lambda::Url", {
        "AuthType": "NONE",
        "Qualifier": "live",
        "Cors": Match.absent(),                               # CORS lives in the app only
    })

    # CodeDeploy shifts the live alias; the Errors alarm rolls it back
    template.has_resource_properties("AWS::CodeDeploy::DeploymentGroup", {
        "AlarmConfiguration": Match.object_like({"Enabled": True}),
        "AutoRollbackConfiguration": Match.object_like({"Enabled": True}),
    })
    template.has_resource("AWS::Lambda::Alias", {
        "UpdatePolicy": Match.object_like({"CodeDeployLambdaAliasUpdate": Match.any_value()}),
    })
