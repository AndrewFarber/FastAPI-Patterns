from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.config.app import AppSettings
from app.config.cors import CorsSettings
from app.config.email import EmailSettings


def test_build_time_needs_a_zone():
    assert AppSettings(build_time="2026-11-02T10:00:00Z").build_time == datetime(2026, 11, 2, 10, tzinfo=UTC)
    with pytest.raises(ValidationError, match="timezone"):
        AppSettings(build_time="2026-11-02T10:00:00")


@pytest.mark.parametrize("origin", ["https://app.example.com", "http://localhost:3000", "*"])
def test_cors_accepts_origins(origin):
    assert CorsSettings(allow_origins=[origin]).allow_origins == [origin]


@pytest.mark.parametrize(
    "origin", ["https://app.example.com/", "https://app.example.com/app", "app.example.com", "ftp://x.example.com"]
)
def test_cors_rejects_non_origins(origin):
    with pytest.raises(ValidationError, match="not an origin"):
        CorsSettings(allow_origins=[origin])


BASE = {"smtp_host": "h", "from_address": "orders@example.com"}


def test_email_valid_combinations():
    EmailSettings(**BASE, username="u", password="p")
    EmailSettings(**BASE, smtp_port=465, security="tls")
    EmailSettings(**BASE, smtp_port=1025, security="none")   # local mail catcher, no credentials


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"username": "u"}, "both username and password"),
        ({"password": "p"}, "both username and password"),
        ({"username": "u", "password": "p", "smtp_port": 1025, "security": "none"}, "credentials need"),
        ({"smtp_port": 465}, "port 465"),
        ({"security": "tls"}, "port 587"),
    ],
)
def test_email_rejects_inconsistent_settings(fields, message):
    with pytest.raises(ValidationError, match=message):
        EmailSettings(**BASE, **fields)
