import pytest


@pytest.fixture(autouse=True)
def _isolate_env_file(tmp_path, monkeypatch):
    # Settings liest `.env` aus dem CWD (pydantic-settings). Tests dürfen
    # weder den Inhalt von backend/.env sehen noch dort Credentials erwarten
    # — sonst sickern lokale Dev-Secrets in Assertions, die genau `Settings()`
    # ohne explizite Credentials prüfen (z. B. *_skipped_when_credentials_missing).
    monkeypatch.chdir(tmp_path)
