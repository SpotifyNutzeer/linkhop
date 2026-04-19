import httpx

from linkhop.adapters import DeezerAdapter, SpotifyAdapter, TidalAdapter
from linkhop.config import Settings
from linkhop.deps import build_adapter_map


async def test_disabled_adapter_not_in_map(monkeypatch):
    monkeypatch.setenv("LINKHOP_ENABLE_SPOTIFY", "false")
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert "spotify" not in m
        assert "deezer" in m


async def test_all_enabled_with_credentials(monkeypatch):
    # Type-assertions guard against a key/value swap in deps.py. Creds required
    # because build_adapter_map skips spotify when they're missing (fail-fast).
    monkeypatch.setenv("LINKHOP_SPOTIFY_CLIENT_ID", "cid")
    monkeypatch.setenv("LINKHOP_SPOTIFY_CLIENT_SECRET", "csec")
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert isinstance(m["spotify"], SpotifyAdapter)
        assert isinstance(m["deezer"], DeezerAdapter)


async def test_spotify_skipped_when_credentials_missing():
    # Default Settings() has empty spotify_client_id/_secret; enable_spotify=True
    # alone must not be enough — otherwise a misconfigured deploy produces an
    # adapter that 400s on every call.
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert "spotify" not in m
        assert "deezer" in m


async def test_all_flags_off_returns_empty(monkeypatch):
    monkeypatch.setenv("LINKHOP_ENABLE_SPOTIFY", "false")
    monkeypatch.setenv("LINKHOP_ENABLE_DEEZER", "false")
    monkeypatch.setenv("LINKHOP_ENABLE_TIDAL", "false")
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert m == {}


async def test_tidal_registered_when_credentials_present(monkeypatch):
    monkeypatch.setenv("LINKHOP_TIDAL_CLIENT_ID", "tid")
    monkeypatch.setenv("LINKHOP_TIDAL_CLIENT_SECRET", "tsec")
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert isinstance(m["tidal"], TidalAdapter)


async def test_tidal_skipped_when_credentials_missing():
    # Analog zum Spotify-Pattern: enable_tidal=True (default) reicht nicht,
    # ohne Credentials würde der Adapter bei jedem Token-Fetch 401/400 werfen.
    s = Settings()
    async with httpx.AsyncClient() as c:
        m = build_adapter_map(s, c)
        assert "tidal" not in m
