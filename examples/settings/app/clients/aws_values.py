import boto3
from botocore.config import Config

from app.clients.ttl_cache import TtlCache

# Fetched on the request path (per DB connection): fail fast and let TtlCache serve the
# last good value, instead of botocore's 60 s timeouts and legacy retries
CLIENT_CONFIG = Config(connect_timeout=1, read_timeout=2, retries={"mode": "standard", "max_attempts": 2})


def secrets_manager_cache(region: str, ttl_seconds: float) -> TtlCache:
    client = boto3.client("secretsmanager", region_name=region, config=CLIENT_CONFIG)
    return TtlCache(lambda secret_id: client.get_secret_value(SecretId=secret_id)["SecretString"], ttl_seconds)


def parameter_store_cache(region: str, ttl_seconds: float) -> TtlCache:
    client = boto3.client("ssm", region_name=region, config=CLIENT_CONFIG)
    return TtlCache(lambda name: client.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"], ttl_seconds)
