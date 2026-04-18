import httpx
import pytest

from linkhop.config import Settings
from linkhop.deps import build_adapter_map


async def test_disabled_adapter_not_in_map(monkeypatch):
    monkeypatch.setenv("LINKHOP_ENABLE_SPOTIFY", "false")
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert "spotify" not in m
        assert "deezer" in m


async def test_all_enabled_by_default():
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert "spotify" in m
        assert "deezer" in m
