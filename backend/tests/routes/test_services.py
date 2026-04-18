from fastapi.testclient import TestClient

from linkhop.config import Settings
from linkhop.main import create_app


def test_services_lists_enabled_adapters(monkeypatch):
    # Spotify-Creds erzwingen — seit Task 17 filtert build_adapter_map Spotify
    # aus, wenn client_id/_secret leer sind (Default). Ohne setenv schlüge der
    # Test an `"spotify" in ids` fehl.
    monkeypatch.setenv("LINKHOP_SPOTIFY_CLIENT_ID", "cid")
    monkeypatch.setenv("LINKHOP_SPOTIFY_CLIENT_SECRET", "csec")
    app = create_app(Settings())
    with TestClient(app) as client:
        resp = client.get("/api/v1/services")
    assert resp.status_code == 200
    body = resp.json()
    ids = {s["id"] for s in body["services"]}
    assert "spotify" in ids
    assert "deezer" in ids


def test_services_excludes_disabled(monkeypatch):
    # Creds gesetzt, damit das Ausschließen von Spotify eindeutig vom
    # ENABLE_SPOTIFY=false-Flag kommt und nicht bloß von fehlenden Creds.
    monkeypatch.setenv("LINKHOP_SPOTIFY_CLIENT_ID", "cid")
    monkeypatch.setenv("LINKHOP_SPOTIFY_CLIENT_SECRET", "csec")
    monkeypatch.setenv("LINKHOP_ENABLE_SPOTIFY", "false")
    app = create_app(Settings())
    with TestClient(app) as client:
        resp = client.get("/api/v1/services")
    body = resp.json()
    ids = {s["id"] for s in body["services"]}
    assert "spotify" not in ids
