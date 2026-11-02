import boto3
from moto import mock_aws

from app.core.aws import values as aws_values


def test_aws_value_caches():
    with mock_aws():
        boto3.client("secretsmanager").create_secret(
            Name="s", SecretString="secret-value"
        )
        boto3.client("ssm").put_parameter(
            Name="/p", Value="parameter-value", Type="SecureString"
        )
        assert (
            aws_values.secrets_manager_cache("us-east-1", 60).get("s")
            == "secret-value"
        )
        assert (
            aws_values.parameter_store_cache("us-east-1", 60).get("/p")
            == "parameter-value"
        )


def test_value_cache_clients_have_short_timeouts(monkeypatch):
    created = []
    monkeypatch.setattr(
        aws_values.boto3,
        "client",
        lambda *args, **kwargs: created.append(kwargs["config"]),
    )
    aws_values.secrets_manager_cache("us-east-1", 60)
    aws_values.parameter_store_cache("us-east-1", 60)
    for config in created:
        assert (config.connect_timeout, config.read_timeout) == (1, 2)
        assert config.retries["mode"] == "standard"
        assert (
            config.retries.get(
                "total_max_attempts", config.retries.get("max_attempts", 0) + 1
            )
            == 3
        )
