import os

import pytest

from linkhop.config import Settings


def test_defaults_when_env_empty(monkeypatch):
    for var in ("DATABASE_URL", "REDIS_URL", "LINKHOP_RATE_ANONYMOUS"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings()
    assert settings.rate_anonymous_per_minute == 20
    assert settings.rate_with_key_per_minute == 300
    assert settings.cache_ttl_seconds == 604800


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LINKHOP_RATE_ANONYMOUS", "5")
    monkeypatch.setenv("LINKHOP_RATE_WITH_KEY", "50")
    monkeypatch.setenv("LINKHOP_CACHE_TTL", "3600")
    settings = Settings()
    assert settings.rate_anonymous_per_minute == 5
    assert settings.rate_with_key_per_minute == 50
    assert settings.cache_ttl_seconds == 3600


def test_service_enable_flags_default_true():
    settings = Settings()
    assert settings.enable_spotify is True
    assert settings.enable_deezer is True
