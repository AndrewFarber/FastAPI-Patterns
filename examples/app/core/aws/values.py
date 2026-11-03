from datetime import timedelta

import boto3
from botocore.config import Config

from app.core.cache.ttl_cache import TtlCache

CLIENT_CONFIG = Config(
    connect_timeout=1,
    read_timeout=2,
    retries={"mode": "standard", "max_attempts": 2},
)


def create_secrets_manager_cache(region: str, ttl: timedelta) -> TtlCache:
    client = boto3.client(
        "secretsmanager", region_name=region, config=CLIENT_CONFIG
    )
    return TtlCache(
        lambda secret_id: client.get_secret_value(SecretId=secret_id)[
            "SecretString"
        ],
        ttl,
    )


def create_parameter_store_cache(region: str, ttl: timedelta) -> TtlCache:
    client = boto3.client("ssm", region_name=region, config=CLIENT_CONFIG)
    return TtlCache(
        lambda name: client.get_parameter(Name=name, WithDecryption=True)[
            "Parameter"
        ]["Value"],
        ttl,
    )
