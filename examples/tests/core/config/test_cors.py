import pytest
from pydantic import ValidationError

from app.core.config.cors import CorsSettings


@pytest.mark.parametrize("origin", ["https://app.example.com", "http://localhost:3000", "*"])
def test_cors_accepts_origins(origin):
    assert CorsSettings(allow_origins=[origin]).allow_origins == [origin]


@pytest.mark.parametrize(
    "origin", ["https://app.example.com/", "https://app.example.com/app", "app.example.com", "ftp://x.example.com"]
)
def test_cors_rejects_non_origins(origin):
    with pytest.raises(ValidationError, match="not an origin"):
        CorsSettings(allow_origins=[origin])
