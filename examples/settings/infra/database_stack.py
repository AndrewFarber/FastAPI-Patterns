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
