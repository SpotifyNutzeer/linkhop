# linkhop Backend-Kern Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Funktionierendes FastAPI-Backend mit Spotify- und Deezer-Adaptern, Postgres + Redis, Short-ID-Sharing, Rate-Limiting, API-Key-CLI. Liefert den kompletten Convert-Flow End-to-End für die zwei einfachsten Dienste.

**Architecture:** Python 3.12 FastAPI. Async SQLAlchemy 2 + asyncpg für Postgres, redis-py async für Cache, httpx für externe HTTP-Calls. Adapter-Pattern: Protocol-basiertes Interface, zwei Implementierungen (Spotify, Deezer). Scoring-Pipeline führt Adapter parallel via `asyncio.gather` aus. Tests: pytest-asyncio mit Fixtures, `respx` für HTTP-Mocking, `fakeredis` und in-memory SQLite für schnelle Unit-Tests, Postgres-Container optional für Integrationstests.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, `redis` (async), httpx, Pydantic v2, pytest-asyncio, respx, fakeredis, Click (CLI), argon2-cffi (Key-Hashing), `slowapi`-Stil Rate-Limiter (selbst gebaut auf Redis).

---

## File Structure

```
backend/
├── pyproject.toml
├── Dockerfile
├── README.md
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial.py
├── src/linkhop/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory + lifecycle
│   ├── config.py            # Settings (env-loaded)
│   ├── logging.py           # JSON-Logging-Setup
│   ├── models/
│   │   ├── __init__.py
│   │   ├── api.py           # Pydantic: Request/Response
│   │   ├── domain.py        # Dataclasses: ResolvedContent, SearchHit
│   │   └── db.py            # SQLAlchemy: Conversion, ApiKey
│   ├── db.py                # AsyncSession factory, engine
│   ├── cache.py             # Redis async wrapper
│   ├── url_parser.py        # URL → (service, type, id)
│   ├── matching.py          # Scoring pipeline
│   ├── short_id.py          # Base62 + DB collision handling
│   ├── ratelimit.py         # Redis-backed sliding window
│   ├── api_keys.py          # Key create/hash/lookup/revoke
│   ├── errors.py            # Exception-Klassen + Handlers
│   ├── adapters/
│   │   ├── __init__.py      # Registry: all adapters
│   │   ├── base.py          # Protocol + Helpers
│   │   ├── spotify.py
│   │   └── deezer.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── convert.py       # GET /api/v1/convert
│   │   ├── share.py         # GET /api/v1/c/{id}
│   │   ├── services.py      # GET /api/v1/services
│   │   └── health.py        # GET /api/v1/health
│   └── cli.py               # linkhop-admin (Click)
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── spotify_track.json
    │   ├── spotify_search.json
    │   ├── deezer_track.json
    │   └── deezer_search.json
    ├── test_url_parser.py
    ├── test_matching.py
    ├── test_short_id.py
    ├── test_api_keys.py
    ├── test_ratelimit.py
    ├── adapters/
    │   ├── test_spotify.py
    │   └── test_deezer.py
    └── routes/
        ├── test_convert.py
        ├── test_share.py
        ├── test_services.py
        └── test_health.py
```

**Decomposition-Logik:** `models/` ist gesplittet nach Zweck (API-Wire, Domain, DB), weil jede Ebene eigene Evolutionsraten hat. `adapters/` pro Service eigene Datei — isoliert pro Dienst. `routes/` pro Endpoint eigene Datei — isoliert Endpoint-Lifecycle.

---

## Task 1: Projekt-Skeleton und Tooling

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/linkhop/__init__.py`
- Create: `backend/src/linkhop/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_smoke.py`

- [ ] **Step 1.1: Projektstruktur anlegen**

```bash
cd /home/paul/git/linkconverter
mkdir -p backend/src/linkhop backend/tests
touch backend/src/linkhop/__init__.py backend/tests/__init__.py
```

- [ ] **Step 1.2: `backend/pyproject.toml` schreiben**

```toml
[project]
name = "linkhop"
version = "0.1.0"
description = "Music-link converter across streaming services"
requires-python = ">=3.12"
dependencies = [
    "fastapi==0.136.*",
    "uvicorn[standard]==0.44.*",
    "pydantic==2.13.*",
    "pydantic-settings==2.13.*",
    "sqlalchemy[asyncio]==2.0.*",
    "asyncpg==0.31.*",
    "alembic==1.18.*",
    "redis==7.4.*",
    "httpx==0.28.*",
    "argon2-cffi==25.1.*",
    "click==8.3.*",
    "python-rapidjson==1.23",
]

[project.optional-dependencies]
dev = [
    "pytest==9.0.*",
    "pytest-asyncio==1.3.*",
    "pytest-cov==7.1.*",
    "respx==0.23.*",
    "fakeredis==2.35.*",
    "aiosqlite==0.22.*",
    "ruff==0.15.*",
    "mypy==1.20.*",
]

[project.scripts]
linkhop-admin = "linkhop.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/linkhop"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "SIM", "RUF"]
```

- [ ] **Step 1.3: Minimale FastAPI-App schreiben — `src/linkhop/main.py`**

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="linkhop", version="0.1.0", docs_url="/api/docs", openapi_url="/api/v1/openapi.json")
    return app


app = create_app()
```

- [ ] **Step 1.4: Smoke-Test schreiben — `tests/test_smoke.py`**

```python
from fastapi.testclient import TestClient

from linkhop.main import create_app


def test_app_instantiates():
    app = create_app()
    assert app.title == "linkhop"


def test_openapi_schema_available():
    client = TestClient(create_app())
    resp = client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "linkhop"
```

- [ ] **Step 1.5: `conftest.py` schreiben**

```python
# Shared pytest fixtures. Add fixtures here as they're needed across test files.
```

Notiz: Mit `asyncio_mode = "auto"` und `asyncio_default_fixture_loop_scope = "function"` in `pyproject.toml` übernimmt pytest-asyncio 1.x die Loop-Erzeugung. Ein expliziter `event_loop`- oder `anyio_backend`-Fixture-Override ist weder nötig noch erwünscht (pytest-asyncio 1.0 hat die `event_loop`-Fixture entfernt).

- [ ] **Step 1.6: Dev-Deps installieren und Test ausführen**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

Expected: `2 passed`.

- [ ] **Step 1.7: Commit**

```bash
cd /home/paul/git/linkconverter
git add backend/
git commit -m "feat(backend): project skeleton with FastAPI app"
```

---

## Task 2: Config-Modul

**Files:**
- Create: `backend/src/linkhop/config.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 2.1: Test schreiben — `tests/test_config.py`**

```python
from linkhop.config import Settings


def test_defaults_when_env_empty(monkeypatch):
    for var in (
        "LINKHOP_DATABASE_URL",
        "LINKHOP_REDIS_URL",
        "LINKHOP_RATE_ANONYMOUS",
        "LINKHOP_RATE_WITH_KEY",
        "LINKHOP_CACHE_TTL",
    ):
        monkeypatch.delenv(var, raising=False)
    settings = Settings()
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.rate_anonymous_per_minute == 20
    assert settings.rate_with_key_per_minute == 300
    assert settings.cache_ttl_seconds == 604800
    assert settings.cors_allow_origins == ["*"]


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
    assert settings.enable_tidal is True
    assert settings.enable_youtube_music is True


def test_cors_allow_origins_parses_comma_separated(monkeypatch):
    monkeypatch.setenv("LINKHOP_CORS_ALLOW_ORIGINS", "https://a.example,https://b.example")
    settings = Settings()
    assert settings.cors_allow_origins == ["https://a.example", "https://b.example"]
```

- [ ] **Step 2.2: Test laufen lassen — erwartet FAIL**

```bash
cd backend && pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: linkhop.config`.

- [ ] **Step 2.3: `src/linkhop/config.py` schreiben**

```python
from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from env vars prefixed with `LINKHOP_`.

    Fields that would otherwise produce awkwardly long env var names use an
    explicit `validation_alias` to pick a shorter operator-friendly name,
    while still allowing the Python attribute name as a fallback.
    """

    model_config = SettingsConfigDict(
        env_prefix="LINKHOP_",
        case_sensitive=False,
        populate_by_name=True,
    )

    database_url: str = "postgresql+asyncpg://linkhop:linkhop@localhost:5432/linkhop"
    redis_url: str = "redis://localhost:6379/0"

    rate_anonymous_per_minute: int = Field(
        default=20,
        validation_alias=AliasChoices(
            "LINKHOP_RATE_ANONYMOUS", "LINKHOP_RATE_ANONYMOUS_PER_MINUTE"
        ),
    )
    rate_with_key_per_minute: int = Field(
        default=300,
        validation_alias=AliasChoices(
            "LINKHOP_RATE_WITH_KEY", "LINKHOP_RATE_WITH_KEY_PER_MINUTE"
        ),
    )
    cache_ttl_seconds: int = Field(
        default=604800,
        validation_alias=AliasChoices("LINKHOP_CACHE_TTL", "LINKHOP_CACHE_TTL_SECONDS"),
    )

    enable_spotify: bool = True
    enable_deezer: bool = True
    enable_tidal: bool = True
    enable_youtube_music: bool = True

    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    tidal_client_id: str = ""
    tidal_client_secret: str = ""

    ytm_cookie_file: str = ""

    cors_allow_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["*"]
    )

    log_level: str = "INFO"

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v
```

Notiz: `validation_alias=AliasChoices(...)` listet mögliche Env-Var-Namen explizit — beide akzeptiert. `populate_by_name=True` erlaubt, den Python-Feldnamen als Fallback zu nutzen. `cors_allow_origins` ist `list[str]` mit `NoDecode` (verhindert JSON-Parsing durch pydantic-settings) und einem `field_validator` der Komma-separierte Strings aufsplittet — damit akzeptieren wir operator-freundliche Werte wie `LINKHOP_CORS_ALLOW_ORIGINS="https://a,https://b"`.

- [ ] **Step 2.4: Tests ausführen**

```bash
cd backend && pytest tests/test_config.py -v
```

Expected: `3 passed`.

- [ ] **Step 2.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): config module with env overrides"
```

---

## Task 3: URL-Parser

**Files:**
- Create: `backend/src/linkhop/url_parser.py`
- Create: `backend/tests/test_url_parser.py`

- [ ] **Step 3.1: Test schreiben — `tests/test_url_parser.py`**

```python
import pytest

from linkhop.url_parser import ParsedUrl, UnsupportedUrlError, parse


@pytest.mark.parametrize("url,service,type_,id_", [
    ("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb", "spotify", "track", "6habFhsOp2NvshLv26DqMb"),
    ("https://open.spotify.com/album/2dIGnmEIy1WZIcZCFSj6i8", "spotify", "album", "2dIGnmEIy1WZIcZCFSj6i8"),
    ("https://open.spotify.com/artist/0du5cEVh5yTK9QJze8zA0C", "spotify", "artist", "0du5cEVh5yTK9QJze8zA0C"),
    ("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb?si=abc", "spotify", "track", "6habFhsOp2NvshLv26DqMb"),
    ("spotify:track:6habFhsOp2NvshLv26DqMb", "spotify", "track", "6habFhsOp2NvshLv26DqMb"),
    ("https://www.deezer.com/track/3135556", "deezer", "track", "3135556"),
    ("https://www.deezer.com/album/302127", "deezer", "album", "302127"),
    ("https://www.deezer.com/artist/27", "deezer", "artist", "27"),
    ("https://deezer.com/en/track/3135556", "deezer", "track", "3135556"),
    ("https://tidal.com/browse/track/77640617", "tidal", "track", "77640617"),
    ("https://tidal.com/track/77640617", "tidal", "track", "77640617"),
    ("https://tidal.com/album/77640616", "tidal", "album", "77640616"),
    ("https://tidal.com/artist/3527", "tidal", "artist", "3527"),
    ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", "youtube_music", "track", "dQw4w9WgXcQ"),
    ("https://music.youtube.com/playlist?list=OLAK5uy_1234", "youtube_music", "album", "OLAK5uy_1234"),
    ("https://music.youtube.com/channel/UC1234", "youtube_music", "artist", "UC1234"),
])
def test_parse_valid(url, service, type_, id_):
    result = parse(url)
    assert result == ParsedUrl(service=service, type=type_, id=id_)


@pytest.mark.parametrize("url", [
    "",
    "not-a-url",
    "https://example.com/foo",
    "https://open.spotify.com/show/abc",      # Podcast, nicht unterstützt
    "https://www.deezer.com/podcast/123",
    "ftp://tidal.com/track/1",
    "spotify:track:",                          # empty ID
    "spotify:track:abc def",                   # whitespace in ID
    "spotify:track:has/slash",                 # invalid char
    "https://music.youtube.com/channel/../watch",  # path traversal
    "https://music.youtube.com/watch?v=bad id",    # whitespace in v
    "https://music.youtube.com/playlist?list=has/slash",  # invalid list char
    "http://[invalid",                          # malformed URL (urlparse raises)
])
def test_parse_invalid_raises(url):
    with pytest.raises(UnsupportedUrlError):
        parse(url)
```

- [ ] **Step 3.2: Test laufen lassen — erwartet FAIL**

```bash
cd backend && pytest tests/test_url_parser.py -v
```

Expected: `ModuleNotFoundError: linkhop.url_parser`.

- [ ] **Step 3.3: `src/linkhop/url_parser.py` schreiben**

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


class UnsupportedUrlError(ValueError):
    """Raised when a URL is not recognized as a supported music-service URL."""


@dataclass(frozen=True)
class ParsedUrl:
    service: str
    type: str
    id: str


_SPOTIFY_ID = re.compile(r"^[A-Za-z0-9]+$")
_SPOTIFY_PATH = re.compile(r"^/(track|album|artist)/([A-Za-z0-9]+)/?$")
_DEEZER_PATH = re.compile(r"^(?:/[a-z]{2})?/(track|album|artist)/(\d+)/?$")
_TIDAL_PATH = re.compile(r"^(?:/browse)?/(track|album|artist)/(\d+)/?$")
_YTM_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def parse(url: str) -> ParsedUrl:
    if not url:
        raise UnsupportedUrlError("empty URL")

    if url.startswith("spotify:"):
        parts = url.split(":")
        if (
            len(parts) == 3
            and parts[1] in {"track", "album", "artist"}
            and _SPOTIFY_ID.match(parts[2])
        ):
            return ParsedUrl("spotify", parts[1], parts[2])
        raise UnsupportedUrlError("invalid spotify URI")

    try:
        parsed = urlparse(url)
    except ValueError as e:
        raise UnsupportedUrlError("invalid URL") from e

    if parsed.scheme not in {"http", "https"}:
        raise UnsupportedUrlError(f"unsupported scheme: {parsed.scheme}")

    host = parsed.hostname or ""
    path = parsed.path or "/"

    if host in {"open.spotify.com", "spotify.com"}:
        m = _SPOTIFY_PATH.match(path)
        if m:
            return ParsedUrl("spotify", m.group(1), m.group(2))

    elif host in {"www.deezer.com", "deezer.com"}:
        m = _DEEZER_PATH.match(path)
        if m:
            return ParsedUrl("deezer", m.group(1), m.group(2))

    elif host in {"tidal.com", "www.tidal.com", "listen.tidal.com"}:
        m = _TIDAL_PATH.match(path)
        if m:
            return ParsedUrl("tidal", m.group(1), m.group(2))

    elif host == "music.youtube.com":
        if path == "/watch":
            v = parse_qs(parsed.query).get("v", [None])[0]
            if v and _YTM_ID.match(v):
                return ParsedUrl("youtube_music", "track", v)
        elif path == "/playlist":
            lst = parse_qs(parsed.query).get("list", [None])[0]
            if lst and _YTM_ID.match(lst):
                return ParsedUrl("youtube_music", "album", lst)
        elif path.startswith("/channel/"):
            chan = path[len("/channel/") :].rstrip("/")
            if chan and _YTM_ID.match(chan):
                return ParsedUrl("youtube_music", "artist", chan)

    raise UnsupportedUrlError(f"no matching service for host: {host}")
```

- [ ] **Step 3.4: Tests ausführen**

```bash
cd backend && pytest tests/test_url_parser.py -v
```

Expected: Alle Tests grün (29 parametrisierte Fälle: 16 valid + 13 invalid).

- [ ] **Step 3.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): URL parser for spotify/deezer/tidal/yt-music"
```

---

## Task 4: Domain-Modelle

**Files:**
- Create: `backend/src/linkhop/models/__init__.py`
- Create: `backend/src/linkhop/models/domain.py`
- Create: `backend/src/linkhop/models/api.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 4.1: `src/linkhop/models/__init__.py` anlegen (leer)**

```bash
mkdir -p backend/src/linkhop/models
touch backend/src/linkhop/models/__init__.py
```

- [ ] **Step 4.2: Test schreiben — `tests/test_models.py`**

```python
from linkhop.models.api import ConvertResponse, SourceContent, TargetResult
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit


def test_resolved_content_equality():
    a = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="https://...", title="T", artists=("A",), album="Al",
        duration_ms=200_000, isrc="ABC", upc=None, artwork="",
    )
    b = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="https://...", title="T", artists=("A",), album="Al",
        duration_ms=200_000, isrc="ABC", upc=None, artwork="",
    )
    assert a == b


def test_search_hit_carries_confidence():
    hit = SearchHit(service="deezer", id="1", url="https://...", confidence=0.82, match="metadata")
    assert hit.confidence == 0.82
    assert hit.match == "metadata"


def test_convert_response_serializes():
    resp = ConvertResponse(
        source=SourceContent(
            service="tidal", type="track", id="1",
            url="https://tidal.com/track/1",
            title="N", artists=["K"], album="O",
            duration_ms=225_000, isrc="FR", artwork="https://x",
        ),
        targets={
            "spotify": TargetResult(status="ok", url="https://u", confidence=1.0, match="isrc"),
        },
        cache={"hit": False, "ttl_seconds": 604_800},
        share=None,
    )
    data = resp.model_dump(mode="json")
    assert data["source"]["title"] == "N"
    assert data["targets"]["spotify"]["confidence"] == 1.0
```

- [ ] **Step 4.3: Test laufen lassen — FAIL**

```bash
cd backend && pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 4.4: `src/linkhop/models/domain.py` schreiben**

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class ContentType(StrEnum):
    TRACK = "track"
    ALBUM = "album"
    ARTIST = "artist"


MatchType = Literal["isrc", "upc", "metadata"]


@dataclass(frozen=True, slots=True)
class ResolvedContent:
    service: str
    type: ContentType
    id: str
    url: str
    title: str
    artists: tuple[str, ...]
    album: str | None
    duration_ms: int | None
    isrc: str | None
    upc: str | None
    artwork: str


@dataclass(frozen=True, slots=True)
class SearchHit:
    service: str
    id: str
    url: str
    confidence: float
    match: MatchType
```

- [ ] **Step 4.5: `src/linkhop/models/api.py` schreiben**

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from linkhop.models.domain import MatchType


class SourceContent(BaseModel):
    service: str
    type: Literal["track", "album", "artist"]
    id: str
    url: str
    title: str
    artists: list[str]
    album: str | None = None
    duration_ms: int | None = None
    isrc: str | None = None
    upc: str | None = None
    artwork: str = ""


class TargetResult(BaseModel):
    status: Literal["ok", "not_found", "error"]
    url: str | None = None
    confidence: float | None = None
    match: MatchType | None = None
    message: str | None = None


class ShareInfo(BaseModel):
    id: str
    url: str


class CacheInfo(BaseModel):
    hit: bool
    ttl_seconds: int


class ConvertResponse(BaseModel):
    source: SourceContent
    targets: dict[str, TargetResult]
    cache: CacheInfo
    share: ShareInfo | None = None


class ServiceInfo(BaseModel):
    id: str
    name: str
    capabilities: list[Literal["track", "album", "artist"]]


class ServicesResponse(BaseModel):
    services: list[ServiceInfo]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    redis: bool
    postgres: bool


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
```

- [ ] **Step 4.6: Tests ausführen**

```bash
cd backend && pytest tests/test_models.py -v
```

Expected: `3 passed`.

- [ ] **Step 4.7: Commit**

```bash
git add backend/
git commit -m "feat(backend): domain and api models"
```

---

## Task 5: Datenbank-Setup und Initial-Migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_initial.py`
- Create: `backend/src/linkhop/models/db.py`
- Create: `backend/src/linkhop/db.py`
- Create: `backend/tests/test_db.py`

- [ ] **Step 5.1: `src/linkhop/models/db.py` schreiben**

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Conversion(Base):
    __tablename__ = "conversions"
    __table_args__ = (
        UniqueConstraint("source_service", "source_type", "source_id", name="uq_conversion_source"),
    )

    short_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_service: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_access_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rate_limit_override: Mapped[int | None] = mapped_column(Integer)
```

- [ ] **Step 5.2: `src/linkhop/db.py` schreiben**

```python
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from linkhop.config import Settings


def make_engine(settings: Settings):
    return create_async_engine(settings.database_url, pool_pre_ping=True, future=True)


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session
```

- [ ] **Step 5.3: Alembic initialisieren**

```bash
cd backend && .venv/bin/alembic init -t async alembic
```

- [ ] **Step 5.4: `alembic.ini` anpassen (sqlalchemy.url auf Platzhalter)**

Öffne `backend/alembic.ini` und ändere `sqlalchemy.url = driver://user:pass@localhost/dbname` zu:

```ini
sqlalchemy.url =
```

(leer — wird programmatisch gesetzt)

- [ ] **Step 5.5: `alembic/env.py` komplett ersetzen durch:**

```python
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from linkhop.config import Settings
from linkhop.models.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = Settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 5.6: Initial-Migration generieren**

```bash
cd backend && .venv/bin/alembic revision --autogenerate -m "initial schema" -r 0001
```

Überprüfe `alembic/versions/0001_*.py` — sollte `conversions` und `api_keys` Tables enthalten.

- [ ] **Step 5.7: Test für DB-Modelle — `tests/test_db.py`**

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from linkhop.models.db import Base, Conversion, ApiKey
from datetime import datetime, timezone


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as s:
        yield s
    await engine.dispose()


async def test_conversion_insert_and_fetch(session: AsyncSession):
    c = Conversion(
        short_id="ab3x9k",
        source_url="https://open.spotify.com/track/x",
        source_service="spotify",
        source_type="track",
        source_id="x",
        created_at=datetime.now(tz=timezone.utc),
    )
    session.add(c)
    await session.commit()

    result = await session.scalar(select(Conversion).where(Conversion.short_id == "ab3x9k"))
    assert result is not None
    assert result.source_service == "spotify"
    assert result.access_count == 0


async def test_api_key_insert(session: AsyncSession):
    k = ApiKey(
        id="00000000-0000-0000-0000-000000000001",
        key_prefix="lhk_aaaa",
        key_hash="$argon2id$...",
        note="test",
        created_at=datetime.now(tz=timezone.utc),
    )
    session.add(k)
    await session.commit()

    result = await session.scalar(select(ApiKey).where(ApiKey.key_prefix == "lhk_aaaa"))
    assert result is not None
    assert result.revoked_at is None
```

- [ ] **Step 5.8: Tests ausführen**

```bash
cd backend && pytest tests/test_db.py -v
```

Expected: `2 passed`.

- [ ] **Step 5.9: Commit**

```bash
git add backend/
git commit -m "feat(backend): db models, engine, alembic initial migration"
```

---

## Task 6: Redis-Cache-Wrapper

**Files:**
- Create: `backend/src/linkhop/cache.py`
- Create: `backend/tests/test_cache.py`

- [ ] **Step 6.1: Test schreiben — `tests/test_cache.py`**

```python
import fakeredis.aioredis
import pytest

from linkhop.cache import Cache


@pytest.fixture
async def cache():
    client = fakeredis.aioredis.FakeRedis()
    yield Cache(client, default_ttl=3600)
    await client.aclose()


async def test_get_returns_none_for_missing(cache: Cache):
    assert await cache.get("missing") is None


async def test_set_and_get_roundtrip(cache: Cache):
    await cache.set("k", {"hello": "world"})
    assert await cache.get("k") == {"hello": "world"}


async def test_set_with_ttl_honored(cache: Cache):
    await cache.set("k", {"a": 1}, ttl=60)
    client = cache._redis
    assert await client.ttl("k") <= 60


async def test_hash_key_stable():
    k1 = Cache.convert_key("spotify", "track", "abc")
    k2 = Cache.convert_key("spotify", "track", "abc")
    assert k1 == k2
    assert k1.startswith("cache:")
```

- [ ] **Step 6.2: Test laufen — FAIL**

```bash
cd backend && pytest tests/test_cache.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 6.3: `src/linkhop/cache.py` schreiben**

```python
from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis


class Cache:
    def __init__(self, client: redis.Redis, default_ttl: int) -> None:
        self._redis = client
        self._default_ttl = default_ttl

    async def get(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self._redis.set(key, json.dumps(value), ex=ttl or self._default_ttl)

    async def ttl(self, key: str) -> int:
        return await self._redis.ttl(key)

    async def ping(self) -> bool:
        try:
            return await self._redis.ping()
        except Exception:
            return False

    @staticmethod
    def convert_key(service: str, type_: str, id_: str) -> str:
        return f"cache:{service}:{type_}:{id_}"
```

- [ ] **Step 6.4: Tests ausführen**

```bash
cd backend && pytest tests/test_cache.py -v
```

Expected: `4 passed`.

- [ ] **Step 6.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): Redis cache wrapper"
```

---

## Task 7: Adapter-Protocol und Basis-Typen

**Files:**
- Create: `backend/src/linkhop/adapters/__init__.py`
- Create: `backend/src/linkhop/adapters/base.py`
- Create: `backend/tests/adapters/__init__.py`
- Create: `backend/tests/adapters/test_base.py`

- [ ] **Step 7.1: Verzeichnisse anlegen**

```bash
mkdir -p backend/src/linkhop/adapters backend/tests/adapters
touch backend/tests/adapters/__init__.py
```

- [ ] **Step 7.2: Test schreiben — `tests/adapters/test_base.py`**

```python
from linkhop.adapters.base import AdapterCapabilities, ServiceAdapter


def test_adapter_protocol_is_runtime_checkable():
    class Dummy:
        service_id = "dummy"
        capabilities = AdapterCapabilities(track=True, album=False, artist=False)

        async def resolve(self, parsed):
            return None

        async def search(self, meta, target_type):
            return []

    d = Dummy()
    assert isinstance(d, ServiceAdapter)
```

- [ ] **Step 7.3: Test laufen — FAIL**

```bash
cd backend && pytest tests/adapters/test_base.py -v
```

- [ ] **Step 7.4: `src/linkhop/adapters/__init__.py` schreiben**

```python
from __future__ import annotations

from linkhop.adapters.base import AdapterCapabilities, ServiceAdapter

__all__ = ["AdapterCapabilities", "ServiceAdapter"]
```

- [ ] **Step 7.5: `src/linkhop/adapters/base.py` schreiben**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    track: bool
    album: bool
    artist: bool

    def supports(self, type_: ContentType) -> bool:
        return {"track": self.track, "album": self.album, "artist": self.artist}[type_.value]


@runtime_checkable
class ServiceAdapter(Protocol):
    service_id: str
    capabilities: AdapterCapabilities

    async def resolve(self, parsed: ParsedUrl) -> ResolvedContent | None:
        """URL in Form von ParsedUrl → Metadaten. None wenn nicht auffindbar."""
        ...

    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        """Suche mit Metadaten vom Source-Dienst. Liefert bis zu 3 Kandidaten."""
        ...


@dataclass(frozen=True, slots=True)
class AdapterError(Exception):
    service: str
    message: str

    def __str__(self) -> str:
        return f"{self.service}: {self.message}"
```

- [ ] **Step 7.6: Tests ausführen**

```bash
cd backend && pytest tests/adapters/test_base.py -v
```

Expected: `1 passed`.

- [ ] **Step 7.7: Commit**

```bash
git add backend/
git commit -m "feat(backend): adapter protocol and capabilities"
```

---

## Task 8: Spotify-Adapter (Resolve)

**Files:**
- Create: `backend/src/linkhop/adapters/spotify.py`
- Create: `backend/tests/fixtures/spotify_track.json`
- Create: `backend/tests/fixtures/spotify_album.json`
- Create: `backend/tests/fixtures/spotify_artist.json`
- Create: `backend/tests/fixtures/spotify_token.json`
- Create: `backend/tests/adapters/test_spotify.py`

- [ ] **Step 8.1: Fixtures anlegen**

`tests/fixtures/spotify_token.json`:
```json
{ "access_token": "BQ-fixture-token", "token_type": "Bearer", "expires_in": 3600 }
```

`tests/fixtures/spotify_track.json`:
```json
{
  "id": "6habFhsOp2NvshLv26DqMb",
  "name": "Nightcall",
  "duration_ms": 257000,
  "external_ids": { "isrc": "FR6V81200001" },
  "external_urls": { "spotify": "https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb" },
  "album": {
    "name": "OutRun",
    "images": [ { "url": "https://i.scdn.co/image/cover", "width": 640 } ]
  },
  "artists": [ { "name": "Kavinsky" } ]
}
```

`tests/fixtures/spotify_album.json`:
```json
{
  "id": "2dIGnmEIy1WZIcZCFSj6i8",
  "name": "OutRun",
  "external_ids": { "upc": "602537360697" },
  "external_urls": { "spotify": "https://open.spotify.com/album/2dIGnmEIy1WZIcZCFSj6i8" },
  "images": [ { "url": "https://i.scdn.co/image/cover", "width": 640 } ],
  "artists": [ { "name": "Kavinsky" } ]
}
```

`tests/fixtures/spotify_artist.json`:
```json
{
  "id": "0du5cEVh5yTK9QJze8zA0C",
  "name": "Kavinsky",
  "genres": ["french electro", "synthwave"],
  "external_urls": { "spotify": "https://open.spotify.com/artist/0du5cEVh5yTK9QJze8zA0C" },
  "images": [ { "url": "https://i.scdn.co/image/artist", "width": 640 } ]
}
```

- [ ] **Step 8.2: Test schreiben — `tests/adapters/test_spotify.py`**

```python
import json
from pathlib import Path

import httpx
import pytest
import respx

from linkhop.adapters.spotify import SpotifyAdapter
from linkhop.models.domain import ContentType
from linkhop.url_parser import ParsedUrl

FIX = Path(__file__).parent.parent / "fixtures"


def fix(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.fixture
async def adapter():
    async with httpx.AsyncClient() as client:
        yield SpotifyAdapter(client=client, client_id="cid", client_secret="csec")


@respx.mock
async def test_resolve_track(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/tracks/6habFhsOp2NvshLv26DqMb").respond(
        json=fix("spotify_track.json")
    )
    result = await adapter.resolve(ParsedUrl("spotify", "track", "6habFhsOp2NvshLv26DqMb"))
    assert result is not None
    assert result.title == "Nightcall"
    assert result.artists == ("Kavinsky",)
    assert result.isrc == "FR6V81200001"
    assert result.duration_ms == 257000
    assert result.type == ContentType.TRACK
    assert result.artwork.startswith("https://i.scdn.co/image")


@respx.mock
async def test_resolve_album(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/albums/2dIGnmEIy1WZIcZCFSj6i8").respond(
        json=fix("spotify_album.json")
    )
    result = await adapter.resolve(ParsedUrl("spotify", "album", "2dIGnmEIy1WZIcZCFSj6i8"))
    assert result is not None
    assert result.title == "OutRun"
    assert result.upc == "602537360697"


@respx.mock
async def test_resolve_artist(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/artists/0du5cEVh5yTK9QJze8zA0C").respond(
        json=fix("spotify_artist.json")
    )
    result = await adapter.resolve(ParsedUrl("spotify", "artist", "0du5cEVh5yTK9QJze8zA0C"))
    assert result is not None
    assert result.title == "Kavinsky"
    assert result.type == ContentType.ARTIST


@respx.mock
async def test_resolve_returns_none_on_404(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/tracks/missing").respond(status_code=404)
    assert await adapter.resolve(ParsedUrl("spotify", "track", "missing")) is None
```

- [ ] **Step 8.3: Test laufen — FAIL**

```bash
cd backend && pytest tests/adapters/test_spotify.py -v
```

- [ ] **Step 8.4: `src/linkhop/adapters/spotify.py` schreiben**

```python
from __future__ import annotations

import base64
import time

import httpx

from linkhop.adapters.base import AdapterCapabilities, AdapterError
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl


class SpotifyAdapter:
    service_id = "spotify"
    capabilities = AdapterCapabilities(track=True, album=True, artist=True)

    _API = "https://api.spotify.com/v1"
    _TOKEN = "https://accounts.spotify.com/api/token"

    def __init__(self, client: httpx.AsyncClient, client_id: str, client_secret: str) -> None:
        self._http = client
        self._cid = client_id
        self._csec = client_secret
        self._token: str | None = None
        self._token_exp: float = 0.0

    async def _ensure_token(self) -> str:
        if self._token and time.monotonic() < self._token_exp - 30:
            return self._token
        basic = base64.b64encode(f"{self._cid}:{self._csec}".encode()).decode()
        resp = await self._http.post(
            self._TOKEN,
            headers={"Authorization": f"Basic {basic}"},
            data={"grant_type": "client_credentials"},
        )
        if resp.status_code != 200:
            raise AdapterError("spotify", f"token fetch failed: {resp.status_code}")
        body = resp.json()
        self._token = body["access_token"]
        self._token_exp = time.monotonic() + int(body.get("expires_in", 3600))
        return self._token

    async def _get(self, path: str) -> dict | None:
        token = await self._ensure_token()
        resp = await self._http.get(
            f"{self._API}{path}", headers={"Authorization": f"Bearer {token}"}
        )
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise AdapterError("spotify", f"GET {path}: {resp.status_code}")
        return resp.json()

    async def resolve(self, parsed: ParsedUrl) -> ResolvedContent | None:
        if parsed.type == "track":
            data = await self._get(f"/tracks/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id,
                type=ContentType.TRACK,
                id=data["id"],
                url=data["external_urls"]["spotify"],
                title=data["name"],
                artists=tuple(a["name"] for a in data["artists"]),
                album=data["album"]["name"],
                duration_ms=data["duration_ms"],
                isrc=data.get("external_ids", {}).get("isrc"),
                upc=None,
                artwork=(data["album"].get("images") or [{"url": ""}])[0]["url"],
            )
        if parsed.type == "album":
            data = await self._get(f"/albums/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id,
                type=ContentType.ALBUM,
                id=data["id"],
                url=data["external_urls"]["spotify"],
                title=data["name"],
                artists=tuple(a["name"] for a in data["artists"]),
                album=None,
                duration_ms=None,
                isrc=None,
                upc=data.get("external_ids", {}).get("upc"),
                artwork=(data.get("images") or [{"url": ""}])[0]["url"],
            )
        if parsed.type == "artist":
            data = await self._get(f"/artists/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id,
                type=ContentType.ARTIST,
                id=data["id"],
                url=data["external_urls"]["spotify"],
                title=data["name"],
                artists=(data["name"],),
                album=None,
                duration_ms=None,
                isrc=None,
                upc=None,
                artwork=(data.get("images") or [{"url": ""}])[0]["url"],
            )
        return None

    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        raise NotImplementedError  # in Task 9
```

- [ ] **Step 8.5: Tests ausführen**

```bash
cd backend && pytest tests/adapters/test_spotify.py -v
```

Expected: `4 passed`.

- [ ] **Step 8.6: Commit**

```bash
git add backend/
git commit -m "feat(backend): Spotify adapter — resolve"
```

---

## Task 9: Spotify-Adapter (Search)

**Files:**
- Modify: `backend/src/linkhop/adapters/spotify.py`
- Create: `backend/tests/fixtures/spotify_search_track.json`
- Modify: `backend/tests/adapters/test_spotify.py`

- [ ] **Step 9.1: Fixture schreiben — `tests/fixtures/spotify_search_track.json`**

```json
{
  "tracks": {
    "items": [
      {
        "id": "6habFhsOp2NvshLv26DqMb",
        "name": "Nightcall",
        "duration_ms": 257000,
        "external_ids": { "isrc": "FR6V81200001" },
        "external_urls": { "spotify": "https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb" },
        "artists": [ { "name": "Kavinsky" } ]
      }
    ]
  }
}
```

- [ ] **Step 9.2: Tests ergänzen (unten an `tests/adapters/test_spotify.py` anfügen)**

```python
from linkhop.models.domain import ContentType, ResolvedContent


@respx.mock
async def test_search_by_isrc_returns_hit(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/search").respond(json=fix("spotify_search_track.json"))

    source = ResolvedContent(
        service="tidal", type=ContentType.TRACK, id="1",
        url="https://tidal.com/track/1", title="Nightcall",
        artists=("Kavinsky",), album="Outrun",
        duration_ms=257000, isrc="FR6V81200001", upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.TRACK)
    assert len(hits) == 1
    assert hits[0].match == "isrc"
    assert hits[0].confidence == 1.0
    assert hits[0].service == "spotify"


@respx.mock
async def test_search_falls_back_to_metadata(adapter: SpotifyAdapter):
    respx.post("https://accounts.spotify.com/api/token").respond(json=fix("spotify_token.json"))
    respx.get("https://api.spotify.com/v1/search").respond(json=fix("spotify_search_track.json"))

    source = ResolvedContent(
        service="tidal", type=ContentType.TRACK, id="1",
        url="https://tidal.com/track/1", title="Nightcall",
        artists=("Kavinsky",), album="Outrun",
        duration_ms=257000, isrc=None, upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.TRACK)
    assert len(hits) >= 1
    assert hits[0].match == "metadata"
```

- [ ] **Step 9.3: Test laufen — FAIL (`NotImplementedError`)**

```bash
cd backend && pytest tests/adapters/test_spotify.py -v
```

- [ ] **Step 9.4: `search()` in `spotify.py` implementieren — ersetze `raise NotImplementedError`:**

```python
    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        if target_type == ContentType.TRACK and meta.isrc:
            return await self._search_tracks(f"isrc:{meta.isrc}", match="isrc")
        if target_type == ContentType.ALBUM and meta.upc:
            return await self._search_albums(f"upc:{meta.upc}", match="upc")
        if target_type == ContentType.TRACK:
            q = f'track:"{meta.title}" artist:"{meta.artists[0] if meta.artists else ""}"'
            return await self._search_tracks(q, match="metadata")
        if target_type == ContentType.ALBUM:
            q = f'album:"{meta.title}" artist:"{meta.artists[0] if meta.artists else ""}"'
            return await self._search_albums(q, match="metadata")
        if target_type == ContentType.ARTIST:
            q = f'artist:"{meta.title}"'
            return await self._search_artists(q)
        return []

    async def _search_tracks(self, q: str, match: str) -> list[SearchHit]:
        token = await self._ensure_token()
        resp = await self._http.get(
            f"{self._API}/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": q, "type": "track", "limit": 3},
        )
        if resp.status_code >= 400:
            raise AdapterError("spotify", f"search tracks: {resp.status_code}")
        items = resp.json().get("tracks", {}).get("items", [])
        return [
            SearchHit(
                service=self.service_id,
                id=it["id"],
                url=it["external_urls"]["spotify"],
                confidence=1.0 if match == "isrc" else 0.0,  # Scoring erfolgt im Matcher
                match=match,
            )
            for it in items
        ]

    async def _search_albums(self, q: str, match: str) -> list[SearchHit]:
        token = await self._ensure_token()
        resp = await self._http.get(
            f"{self._API}/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": q, "type": "album", "limit": 3},
        )
        if resp.status_code >= 400:
            raise AdapterError("spotify", f"search albums: {resp.status_code}")
        items = resp.json().get("albums", {}).get("items", [])
        return [
            SearchHit(
                service=self.service_id, id=it["id"],
                url=it["external_urls"]["spotify"],
                confidence=1.0 if match == "upc" else 0.0,
                match=match,
            )
            for it in items
        ]

    async def _search_artists(self, q: str) -> list[SearchHit]:
        token = await self._ensure_token()
        resp = await self._http.get(
            f"{self._API}/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": q, "type": "artist", "limit": 3},
        )
        if resp.status_code >= 400:
            raise AdapterError("spotify", f"search artists: {resp.status_code}")
        items = resp.json().get("artists", {}).get("items", [])
        return [
            SearchHit(
                service=self.service_id, id=it["id"],
                url=it["external_urls"]["spotify"],
                confidence=0.0,
                match="metadata",
            )
            for it in items
        ]
```

**Hinweis:** Die `confidence` wird hier roh gesetzt (1.0 bei ID-Match, 0.0 bei Metadata — der Matcher rechnet final). Das entspricht der Spec: ID-Match ist "sicher", Metadata muss gescored werden.

- [ ] **Step 9.5: Tests ausführen**

```bash
cd backend && pytest tests/adapters/test_spotify.py -v
```

Expected: `6 passed`.

- [ ] **Step 9.6: Commit**

```bash
git add backend/
git commit -m "feat(backend): Spotify adapter — search (isrc/upc/metadata)"
```

---

## Task 10: Deezer-Adapter

**Files:**
- Create: `backend/src/linkhop/adapters/deezer.py`
- Create: `backend/tests/fixtures/deezer_track.json`
- Create: `backend/tests/fixtures/deezer_album.json`
- Create: `backend/tests/fixtures/deezer_artist.json`
- Create: `backend/tests/fixtures/deezer_search_track.json`
- Create: `backend/tests/adapters/test_deezer.py`

- [ ] **Step 10.1: Fixtures schreiben**

`tests/fixtures/deezer_track.json`:
```json
{
  "id": 3135556,
  "title": "Nightcall",
  "duration": 257,
  "isrc": "FR6V81200001",
  "link": "https://www.deezer.com/track/3135556",
  "artist": { "name": "Kavinsky", "picture_xl": "https://e-cdns-images.dzcdn.net/a.jpg" },
  "album": { "title": "OutRun", "cover_xl": "https://e-cdns-images.dzcdn.net/c.jpg" }
}
```

`tests/fixtures/deezer_album.json`:
```json
{
  "id": 302127,
  "title": "OutRun",
  "upc": "602537360697",
  "link": "https://www.deezer.com/album/302127",
  "cover_xl": "https://e-cdns-images.dzcdn.net/c.jpg",
  "artist": { "name": "Kavinsky" }
}
```

`tests/fixtures/deezer_artist.json`:
```json
{
  "id": 27,
  "name": "Kavinsky",
  "link": "https://www.deezer.com/artist/27",
  "picture_xl": "https://e-cdns-images.dzcdn.net/a.jpg"
}
```

`tests/fixtures/deezer_search_track.json`:
```json
{
  "data": [
    {
      "id": 3135556,
      "title": "Nightcall",
      "duration": 257,
      "link": "https://www.deezer.com/track/3135556",
      "artist": { "name": "Kavinsky" },
      "album": { "title": "OutRun" }
    }
  ]
}
```

- [ ] **Step 10.2: Test — `tests/adapters/test_deezer.py`**

```python
import json
from pathlib import Path

import httpx
import pytest
import respx

from linkhop.adapters.deezer import DeezerAdapter
from linkhop.models.domain import ContentType, ResolvedContent
from linkhop.url_parser import ParsedUrl

FIX = Path(__file__).parent.parent / "fixtures"


def fix(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.fixture
async def adapter():
    async with httpx.AsyncClient() as client:
        yield DeezerAdapter(client=client)


@respx.mock
async def test_resolve_track(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/track/3135556").respond(json=fix("deezer_track.json"))
    result = await adapter.resolve(ParsedUrl("deezer", "track", "3135556"))
    assert result is not None
    assert result.title == "Nightcall"
    assert result.duration_ms == 257000
    assert result.isrc == "FR6V81200001"


@respx.mock
async def test_resolve_album(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/album/302127").respond(json=fix("deezer_album.json"))
    result = await adapter.resolve(ParsedUrl("deezer", "album", "302127"))
    assert result is not None
    assert result.upc == "602537360697"


@respx.mock
async def test_resolve_artist(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/artist/27").respond(json=fix("deezer_artist.json"))
    result = await adapter.resolve(ParsedUrl("deezer", "artist", "27"))
    assert result is not None
    assert result.title == "Kavinsky"


@respx.mock
async def test_resolve_404_returns_none(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/track/missing").respond(
        json={"error": {"code": 800, "message": "no data"}}
    )
    assert await adapter.resolve(ParsedUrl("deezer", "track", "missing")) is None


@respx.mock
async def test_search_by_isrc(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/track/isrc:FR6V81200001").respond(
        json=fix("deezer_track.json")
    )
    source = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="", title="Nightcall", artists=("Kavinsky",), album="Outrun",
        duration_ms=257000, isrc="FR6V81200001", upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.TRACK)
    assert len(hits) == 1
    assert hits[0].match == "isrc"


@respx.mock
async def test_search_fallback_metadata(adapter: DeezerAdapter):
    respx.get("https://api.deezer.com/search/track").respond(json=fix("deezer_search_track.json"))
    source = ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x",
        url="", title="Nightcall", artists=("Kavinsky",), album="Outrun",
        duration_ms=257000, isrc=None, upc=None, artwork="",
    )
    hits = await adapter.search(source, ContentType.TRACK)
    assert len(hits) >= 1
    assert hits[0].match == "metadata"
```

- [ ] **Step 10.3: Test laufen — FAIL**

```bash
cd backend && pytest tests/adapters/test_deezer.py -v
```

- [ ] **Step 10.4: `src/linkhop/adapters/deezer.py` schreiben**

```python
from __future__ import annotations

import httpx

from linkhop.adapters.base import AdapterCapabilities, AdapterError
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl


class DeezerAdapter:
    service_id = "deezer"
    capabilities = AdapterCapabilities(track=True, album=True, artist=True)

    _API = "https://api.deezer.com"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._http = client

    async def _get(self, path: str, params: dict | None = None) -> dict | None:
        resp = await self._http.get(f"{self._API}{path}", params=params)
        if resp.status_code >= 400:
            raise AdapterError("deezer", f"GET {path}: {resp.status_code}")
        data = resp.json()
        if isinstance(data, dict) and data.get("error"):
            return None
        return data

    async def resolve(self, parsed: ParsedUrl) -> ResolvedContent | None:
        if parsed.type == "track":
            data = await self._get(f"/track/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id, type=ContentType.TRACK, id=str(data["id"]),
                url=data["link"], title=data["title"],
                artists=(data["artist"]["name"],),
                album=data.get("album", {}).get("title"),
                duration_ms=int(data["duration"]) * 1000,
                isrc=data.get("isrc"), upc=None,
                artwork=data.get("album", {}).get("cover_xl", ""),
            )
        if parsed.type == "album":
            data = await self._get(f"/album/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id, type=ContentType.ALBUM, id=str(data["id"]),
                url=data["link"], title=data["title"],
                artists=(data["artist"]["name"],),
                album=None, duration_ms=None,
                isrc=None, upc=data.get("upc"),
                artwork=data.get("cover_xl", ""),
            )
        if parsed.type == "artist":
            data = await self._get(f"/artist/{parsed.id}")
            if not data:
                return None
            return ResolvedContent(
                service=self.service_id, type=ContentType.ARTIST, id=str(data["id"]),
                url=data["link"], title=data["name"],
                artists=(data["name"],), album=None, duration_ms=None,
                isrc=None, upc=None, artwork=data.get("picture_xl", ""),
            )
        return None

    async def search(self, meta: ResolvedContent, target_type: ContentType) -> list[SearchHit]:
        if target_type == ContentType.TRACK and meta.isrc:
            data = await self._get(f"/track/isrc:{meta.isrc}")
            if data:
                return [SearchHit(
                    service=self.service_id, id=str(data["id"]),
                    url=data["link"], confidence=1.0, match="isrc",
                )]
        if target_type == ContentType.ALBUM and meta.upc:
            data = await self._get(f"/album/upc:{meta.upc}")
            if data:
                return [SearchHit(
                    service=self.service_id, id=str(data["id"]),
                    url=data["link"], confidence=1.0, match="upc",
                )]
        artist = meta.artists[0] if meta.artists else ""
        if target_type == ContentType.TRACK:
            data = await self._get("/search/track", {"q": f'track:"{meta.title}" artist:"{artist}"'})
            items = (data or {}).get("data", [])[:3]
            return [SearchHit(
                service=self.service_id, id=str(it["id"]), url=it["link"],
                confidence=0.0, match="metadata",
            ) for it in items]
        if target_type == ContentType.ALBUM:
            data = await self._get("/search/album", {"q": f'album:"{meta.title}" artist:"{artist}"'})
            items = (data or {}).get("data", [])[:3]
            return [SearchHit(
                service=self.service_id, id=str(it["id"]), url=it["link"],
                confidence=0.0, match="metadata",
            ) for it in items]
        if target_type == ContentType.ARTIST:
            data = await self._get("/search/artist", {"q": meta.title})
            items = (data or {}).get("data", [])[:3]
            return [SearchHit(
                service=self.service_id, id=str(it["id"]), url=it["link"],
                confidence=0.0, match="metadata",
            ) for it in items]
        return []
```

- [ ] **Step 10.5: Tests ausführen**

```bash
cd backend && pytest tests/adapters/test_deezer.py -v
```

Expected: `6 passed`.

- [ ] **Step 10.6: Commit**

```bash
git add backend/
git commit -m "feat(backend): Deezer adapter (resolve + search)"
```

---

## Task 11: Matching-/Scoring-Engine

**Files:**
- Create: `backend/src/linkhop/matching.py`
- Create: `backend/tests/test_matching.py`

- [ ] **Step 11.1: Test schreiben — `tests/test_matching.py`**

```python
from linkhop.matching import (
    artist_overlap, duration_score, score_candidate, threshold_status, title_similarity,
)
from linkhop.models.domain import ContentType, ResolvedContent


def make_meta(title="Nightcall", artists=("Kavinsky",), duration_ms=257000, isrc=None):
    return ResolvedContent(
        service="spotify", type=ContentType.TRACK, id="x", url="",
        title=title, artists=artists, album=None,
        duration_ms=duration_ms, isrc=isrc, upc=None, artwork="",
    )


def test_title_similarity_perfect():
    assert title_similarity("Nightcall", "Nightcall") == 1.0


def test_title_similarity_case_and_punct():
    assert title_similarity("Nightcall", "night-call!") > 0.85


def test_title_similarity_different():
    assert title_similarity("Nightcall", "Daybreak") < 0.3


def test_artist_overlap_exact():
    assert artist_overlap(("Kavinsky",), ("Kavinsky",)) == 1.0


def test_artist_overlap_partial():
    assert 0 < artist_overlap(("Kavinsky", "Daft Punk"), ("Kavinsky",)) < 1.0


def test_artist_overlap_none():
    assert artist_overlap(("Kavinsky",), ("Other",)) == 0.0


def test_duration_score_exact():
    assert duration_score(257000, 257000) == 1.0


def test_duration_score_off_by_5s():
    assert 0.4 < duration_score(257000, 252000) < 0.6


def test_duration_score_off_by_30s():
    assert duration_score(257000, 227000) == 0.0


def test_score_candidate_perfect_metadata():
    meta = make_meta()
    cand_meta = make_meta()
    score = score_candidate(meta, cand_meta, match="metadata")
    assert score >= 0.95


def test_score_candidate_isrc_always_one():
    meta = make_meta(title="wrong", artists=("also wrong",), duration_ms=1)
    cand_meta = make_meta()
    assert score_candidate(meta, cand_meta, match="isrc") == 1.0


def test_threshold_status():
    assert threshold_status(1.0) == "ok"
    assert threshold_status(0.8) == "ok"
    assert threshold_status(0.5) == "ok_low"
    assert threshold_status(0.3) == "not_found"
```

- [ ] **Step 11.2: Test laufen — FAIL**

```bash
cd backend && pytest tests/test_matching.py -v
```

- [ ] **Step 11.3: `src/linkhop/matching.py` schreiben**

```python
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from linkhop.models.domain import ResolvedContent


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def artist_overlap(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    sa = {_normalize(x) for x in a}
    sb = {_normalize(x) for x in b}
    if not sa or not sb:
        return 0.0
    inter = sa & sb
    union = sa | sb
    return len(inter) / len(union)


def duration_score(a_ms: int | None, b_ms: int | None) -> float:
    if a_ms is None or b_ms is None:
        return 0.5  # neutral
    diff_s = abs(a_ms - b_ms) / 1000
    return max(0.0, 1.0 - diff_s / 10.0)


def score_candidate(source: ResolvedContent, candidate: ResolvedContent, match: str) -> float:
    if match in {"isrc", "upc"}:
        return 1.0
    title = title_similarity(source.title, candidate.title)
    artists = artist_overlap(source.artists, candidate.artists)
    dur = duration_score(source.duration_ms, candidate.duration_ms) if candidate.duration_ms else 0.5
    return round(title * 0.4 + artists * 0.4 + dur * 0.2, 3)


def threshold_status(confidence: float) -> str:
    """Return canonical status label:
    - 'ok' for confidence >= 0.7
    - 'ok_low' for 0.4 <= confidence < 0.7 (UI shows ~match badge)
    - 'not_found' for < 0.4
    """
    if confidence >= 0.7:
        return "ok"
    if confidence >= 0.4:
        return "ok_low"
    return "not_found"
```

- [ ] **Step 11.4: Tests ausführen**

```bash
cd backend && pytest tests/test_matching.py -v
```

Expected: `11 passed`.

- [ ] **Step 11.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): matching and scoring primitives"
```

---

## Task 12: Matching-Pipeline (Orchestrator)

**Files:**
- Create: `backend/src/linkhop/pipeline.py`
- Create: `backend/tests/test_pipeline.py`

- [ ] **Step 12.1: Test schreiben — `tests/test_pipeline.py`**

```python
from types import SimpleNamespace

import pytest

from linkhop.adapters.base import AdapterError
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.pipeline import Pipeline
from linkhop.url_parser import ParsedUrl


def source_meta() -> ResolvedContent:
    return ResolvedContent(
        service="tidal", type=ContentType.TRACK, id="1",
        url="https://tidal.com/track/1", title="Nightcall",
        artists=("Kavinsky",), album="Outrun",
        duration_ms=257000, isrc="FR6V81200001", upc=None, artwork="",
    )


class FakeAdapter:
    service_id = "fake"
    capabilities = SimpleNamespace(supports=lambda t: True, track=True, album=True, artist=True)

    def __init__(self, service_id, resolve_value=None, search_value=None, raise_on_search=False):
        self.service_id = service_id
        self._resolve_value = resolve_value
        self._search_value = search_value or []
        self._raise = raise_on_search

    async def resolve(self, parsed):
        return self._resolve_value

    async def search(self, meta, target_type):
        if self._raise:
            raise AdapterError(self.service_id, "boom")
        return self._search_value


async def test_pipeline_resolves_and_searches():
    tidal = FakeAdapter("tidal", resolve_value=source_meta())
    spotify = FakeAdapter("spotify", search_value=[
        SearchHit(service="spotify", id="sp1", url="https://open.spotify.com/track/sp1",
                  confidence=1.0, match="isrc"),
    ])
    deezer = FakeAdapter("deezer", search_value=[
        SearchHit(service="deezer", id="dz1", url="https://www.deezer.com/track/dz1",
                  confidence=1.0, match="isrc"),
    ])
    pipeline = Pipeline({"tidal": tidal, "spotify": spotify, "deezer": deezer}, resolver_factory=None)

    result = await pipeline.convert(ParsedUrl("tidal", "track", "1"))
    assert result.source.title == "Nightcall"
    assert result.targets["spotify"].status == "ok"
    assert result.targets["spotify"].match == "isrc"
    assert result.targets["deezer"].status == "ok"


async def test_pipeline_source_adapter_not_found_raises():
    tidal = FakeAdapter("tidal", resolve_value=None)
    pipeline = Pipeline({"tidal": tidal}, resolver_factory=None)

    with pytest.raises(LookupError):
        await pipeline.convert(ParsedUrl("tidal", "track", "missing"))


async def test_pipeline_partial_results_on_adapter_error():
    tidal = FakeAdapter("tidal", resolve_value=source_meta())
    good = FakeAdapter("spotify", search_value=[
        SearchHit(service="spotify", id="sp1", url="...", confidence=1.0, match="isrc"),
    ])
    bad = FakeAdapter("deezer", raise_on_search=True)
    pipeline = Pipeline({"tidal": tidal, "spotify": good, "deezer": bad}, resolver_factory=None)

    result = await pipeline.convert(ParsedUrl("tidal", "track", "1"))
    assert result.targets["spotify"].status == "ok"
    assert result.targets["deezer"].status == "error"
    assert "boom" in (result.targets["deezer"].message or "")


async def test_pipeline_skips_source_service_in_targets():
    tidal = FakeAdapter("tidal", resolve_value=source_meta())
    pipeline = Pipeline({"tidal": tidal}, resolver_factory=None)

    result = await pipeline.convert(ParsedUrl("tidal", "track", "1"))
    assert "tidal" not in result.targets
```

- [ ] **Step 12.2: Test laufen — FAIL**

```bash
cd backend && pytest tests/test_pipeline.py -v
```

- [ ] **Step 12.3: `src/linkhop/pipeline.py` schreiben**

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from linkhop.adapters.base import AdapterError, ServiceAdapter
from linkhop.matching import score_candidate, threshold_status
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.url_parser import ParsedUrl


@dataclass(slots=True)
class TargetOutcome:
    status: str          # "ok" | "not_found" | "error"
    url: str | None = None
    confidence: float | None = None
    match: str | None = None
    message: str | None = None


@dataclass(slots=True)
class ConvertOutcome:
    source: ResolvedContent
    targets: dict[str, TargetOutcome]


class Pipeline:
    def __init__(self, adapters: dict[str, ServiceAdapter], resolver_factory) -> None:
        self._adapters = adapters
        self._resolver_factory = resolver_factory

    async def convert(self, parsed: ParsedUrl) -> ConvertOutcome:
        source_adapter = self._adapters.get(parsed.service)
        if source_adapter is None:
            raise LookupError(f"no adapter for source service: {parsed.service}")

        source = await source_adapter.resolve(parsed)
        if source is None:
            raise LookupError(f"source not found: {parsed.service}/{parsed.type}/{parsed.id}")

        target_ids = [sid for sid in self._adapters if sid != parsed.service]
        type_ = ContentType(parsed.type)

        tasks = [self._search_one(sid, source, type_) for sid in target_ids]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        targets = dict(zip(target_ids, results, strict=True))
        return ConvertOutcome(source=source, targets=targets)

    async def _search_one(self, service_id: str, source: ResolvedContent, type_: ContentType) -> TargetOutcome:
        adapter = self._adapters[service_id]
        try:
            hits: list[SearchHit] = await adapter.search(source, type_)
        except AdapterError as e:
            return TargetOutcome(status="error", message=e.message)
        except Exception as e:  # defensive, unknown adapter bug
            return TargetOutcome(status="error", message=f"unexpected: {e}")

        if not hits:
            return TargetOutcome(status="not_found")

        id_hits = [h for h in hits if h.match in {"isrc", "upc"}]
        if id_hits:
            best = id_hits[0]
            return TargetOutcome(status="ok", url=best.url, confidence=1.0, match=best.match)

        best, best_score = None, 0.0
        for h in hits:
            score = await self._score_hit(service_id, source, h, type_)
            if score > best_score:
                best, best_score = h, score

        status = threshold_status(best_score)
        if status == "not_found" or best is None:
            return TargetOutcome(status="not_found")
        return TargetOutcome(
            status="ok", url=best.url,
            confidence=round(best_score, 3), match="metadata",
        )

    async def _score_hit(self, service_id: str, source: ResolvedContent,
                         hit: SearchHit, type_: ContentType) -> float:
        adapter = self._adapters[service_id]
        full = await adapter.resolve(ParsedUrl(service=service_id, type=type_.value, id=hit.id))
        if full is None:
            return 0.0
        return score_candidate(source, full, match="metadata")
```

- [ ] **Step 12.4: Tests ausführen**

```bash
cd backend && pytest tests/test_pipeline.py -v
```

Expected: `4 passed`.

- [ ] **Step 12.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): convert pipeline with parallel adapter search"
```

---

## Task 13: Short-ID-Generator

**Files:**
- Create: `backend/src/linkhop/short_id.py`
- Create: `backend/tests/test_short_id.py`

- [ ] **Step 13.1: Test — `tests/test_short_id.py`**

```python
import re

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from linkhop.models.db import Base, Conversion
from linkhop.short_id import ShortIdService, generate_short_id


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as s:
        yield s
    await engine.dispose()


def test_generate_short_id_format():
    sid = generate_short_id()
    assert re.match(r"^[A-Za-z0-9]{6}$", sid)


def test_generate_short_id_unique():
    ids = {generate_short_id() for _ in range(1000)}
    assert len(ids) == 1000


async def test_service_returns_existing_for_same_source(session: AsyncSession):
    svc = ShortIdService(session)
    sid1 = await svc.get_or_create(
        source_service="spotify", source_type="track", source_id="x",
        source_url="https://open.spotify.com/track/x",
    )
    sid2 = await svc.get_or_create(
        source_service="spotify", source_type="track", source_id="x",
        source_url="https://open.spotify.com/track/x",
    )
    assert sid1 == sid2


async def test_service_creates_different_for_different_source(session: AsyncSession):
    svc = ShortIdService(session)
    a = await svc.get_or_create(
        source_service="spotify", source_type="track", source_id="x",
        source_url="https://open.spotify.com/track/x",
    )
    b = await svc.get_or_create(
        source_service="deezer", source_type="track", source_id="x",
        source_url="https://www.deezer.com/track/x",
    )
    assert a != b


async def test_service_lookup_by_short_id(session: AsyncSession):
    svc = ShortIdService(session)
    sid = await svc.get_or_create(
        source_service="spotify", source_type="track", source_id="x",
        source_url="https://open.spotify.com/track/x",
    )
    row = await svc.lookup(sid)
    assert row is not None
    assert row.source_service == "spotify"
    assert row.source_id == "x"
    assert row.access_count == 1  # lookup bumped counter
```

- [ ] **Step 13.2: Test laufen — FAIL**

```bash
cd backend && pytest tests/test_short_id.py -v
```

- [ ] **Step 13.3: `src/linkhop/short_id.py` schreiben**

```python
from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from linkhop.models.db import Conversion

_ALPHA = string.ascii_letters + string.digits  # 62 chars


def generate_short_id(length: int = 6) -> str:
    return "".join(secrets.choice(_ALPHA) for _ in range(length))


class ShortIdService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_or_create(
        self, *, source_service: str, source_type: str, source_id: str, source_url: str,
    ) -> str:
        existing = await self._s.scalar(
            select(Conversion).where(
                Conversion.source_service == source_service,
                Conversion.source_type == source_type,
                Conversion.source_id == source_id,
            )
        )
        if existing:
            return existing.short_id

        for _ in range(10):
            sid = generate_short_id()
            row = Conversion(
                short_id=sid,
                source_url=source_url,
                source_service=source_service,
                source_type=source_type,
                source_id=source_id,
                created_at=datetime.now(tz=timezone.utc),
            )
            self._s.add(row)
            try:
                await self._s.commit()
                return sid
            except IntegrityError:
                await self._s.rollback()
                # collision on short_id or unique source; retry
                continue

        raise RuntimeError("failed to allocate short id after 10 retries")

    async def lookup(self, short_id: str) -> Conversion | None:
        row = await self._s.scalar(select(Conversion).where(Conversion.short_id == short_id))
        if row is None:
            return None
        await self._s.execute(
            update(Conversion)
            .where(Conversion.short_id == short_id)
            .values(access_count=Conversion.access_count + 1,
                    last_access_at=datetime.now(tz=timezone.utc))
        )
        await self._s.commit()
        await self._s.refresh(row)
        return row
```

- [ ] **Step 13.4: Tests ausführen**

```bash
cd backend && pytest tests/test_short_id.py -v
```

Expected: `5 passed`.

- [ ] **Step 13.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): short-id generator with DB-backed uniqueness"
```

---

## Task 14: API-Key-Management

**Files:**
- Create: `backend/src/linkhop/api_keys.py`
- Create: `backend/tests/test_api_keys.py`

- [ ] **Step 14.1: Test — `tests/test_api_keys.py`**

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from linkhop.api_keys import ApiKeyService, KEY_PREFIX_LEN
from linkhop.models.db import Base


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as s:
        yield s
    await engine.dispose()


async def test_create_returns_key_with_prefix(session: AsyncSession):
    svc = ApiKeyService(session)
    plain, record = await svc.create(note="paul")
    assert plain.startswith("lhk_")
    assert len(record.key_prefix) == KEY_PREFIX_LEN
    assert plain.startswith(record.key_prefix)


async def test_verify_correct_key(session: AsyncSession):
    svc = ApiKeyService(session)
    plain, _ = await svc.create(note="x")
    verified = await svc.verify(plain)
    assert verified is not None


async def test_verify_wrong_key(session: AsyncSession):
    svc = ApiKeyService(session)
    await svc.create(note="x")
    assert await svc.verify("lhk_wrong0000notvalid") is None


async def test_revoked_key_does_not_verify(session: AsyncSession):
    svc = ApiKeyService(session)
    plain, record = await svc.create(note="x")
    await svc.revoke(record.id)
    assert await svc.verify(plain) is None


async def test_list_and_revoke(session: AsyncSession):
    svc = ApiKeyService(session)
    _, a = await svc.create(note="a")
    _, b = await svc.create(note="b")
    await svc.revoke(a.id)
    keys = await svc.list_all()
    active = [k for k in keys if k.revoked_at is None]
    assert len(active) == 1
    assert active[0].id == b.id
```

- [ ] **Step 14.2: Test laufen — FAIL**

```bash
cd backend && pytest tests/test_api_keys.py -v
```

- [ ] **Step 14.3: `src/linkhop/api_keys.py` schreiben**

```python
from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from linkhop.models.db import ApiKey

KEY_PREFIX_LEN = 8
_KEY_SUFFIX_LEN = 32
_ALPHA = string.ascii_letters + string.digits
_hasher = PasswordHasher()


def _generate_plain_key() -> tuple[str, str]:
    """Returns (full_key, prefix)."""
    body = "".join(secrets.choice(_ALPHA) for _ in range(_KEY_SUFFIX_LEN))
    full = f"lhk_{body}"
    prefix = full[:KEY_PREFIX_LEN]
    return full, prefix


class ApiKeyService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, *, note: str | None = None,
                     rate_limit_override: int | None = None) -> tuple[str, ApiKey]:
        full, prefix = _generate_plain_key()
        row = ApiKey(
            id=str(uuid.uuid4()),
            key_prefix=prefix,
            key_hash=_hasher.hash(full),
            note=note,
            created_at=datetime.now(tz=timezone.utc),
            rate_limit_override=rate_limit_override,
        )
        self._s.add(row)
        await self._s.commit()
        await self._s.refresh(row)
        return full, row

    async def verify(self, presented: str) -> ApiKey | None:
        if len(presented) < KEY_PREFIX_LEN:
            return None
        prefix = presented[:KEY_PREFIX_LEN]
        row = await self._s.scalar(
            select(ApiKey).where(ApiKey.key_prefix == prefix, ApiKey.revoked_at.is_(None))
        )
        if row is None:
            return None
        try:
            _hasher.verify(row.key_hash, presented)
        except VerifyMismatchError:
            return None
        return row

    async def revoke(self, key_id: str) -> None:
        await self._s.execute(
            update(ApiKey).where(ApiKey.id == key_id).values(revoked_at=datetime.now(tz=timezone.utc))
        )
        await self._s.commit()

    async def list_all(self) -> list[ApiKey]:
        result = await self._s.scalars(select(ApiKey).order_by(ApiKey.created_at))
        return list(result.all())
```

- [ ] **Step 14.4: Tests ausführen**

```bash
cd backend && pytest tests/test_api_keys.py -v
```

Expected: `5 passed`.

- [ ] **Step 14.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): api-key service with argon2 hashing"
```

---

## Task 15: Rate-Limiter

**Files:**
- Create: `backend/src/linkhop/ratelimit.py`
- Create: `backend/tests/test_ratelimit.py`

- [ ] **Step 15.1: Test — `tests/test_ratelimit.py`**

```python
import fakeredis.aioredis
import pytest

from linkhop.ratelimit import RateLimiter


@pytest.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.aclose()


async def test_allows_under_limit(redis_client):
    rl = RateLimiter(redis_client, anonymous_per_minute=3, with_key_per_minute=100)
    for _ in range(3):
        assert await rl.check(identifier="1.2.3.4", is_authenticated=False) is True


async def test_blocks_over_limit(redis_client):
    rl = RateLimiter(redis_client, anonymous_per_minute=3, with_key_per_minute=100)
    for _ in range(3):
        await rl.check(identifier="1.2.3.4", is_authenticated=False)
    assert await rl.check(identifier="1.2.3.4", is_authenticated=False) is False


async def test_separate_counters_per_identifier(redis_client):
    rl = RateLimiter(redis_client, anonymous_per_minute=2, with_key_per_minute=100)
    for _ in range(2):
        await rl.check(identifier="a", is_authenticated=False)
    assert await rl.check(identifier="b", is_authenticated=False) is True


async def test_authenticated_uses_higher_limit(redis_client):
    rl = RateLimiter(redis_client, anonymous_per_minute=2, with_key_per_minute=5)
    for _ in range(5):
        assert await rl.check(identifier="key:xyz", is_authenticated=True) is True
    assert await rl.check(identifier="key:xyz", is_authenticated=True) is False


async def test_custom_override_used_when_provided(redis_client):
    rl = RateLimiter(redis_client, anonymous_per_minute=2, with_key_per_minute=5)
    for _ in range(9):
        assert await rl.check(identifier="key:k", is_authenticated=True, override=9) is True
    assert await rl.check(identifier="key:k", is_authenticated=True, override=9) is False
```

- [ ] **Step 15.2: Test laufen — FAIL**

```bash
cd backend && pytest tests/test_ratelimit.py -v
```

- [ ] **Step 15.3: `src/linkhop/ratelimit.py` schreiben**

```python
from __future__ import annotations

import time

import redis.asyncio as redis


class RateLimiter:
    """Fixed-window per-minute limiter backed by Redis INCR + EXPIRE."""

    def __init__(self, client: redis.Redis, *, anonymous_per_minute: int, with_key_per_minute: int) -> None:
        self._r = client
        self._anon = anonymous_per_minute
        self._auth = with_key_per_minute

    async def check(
        self, *, identifier: str, is_authenticated: bool, override: int | None = None,
    ) -> bool:
        limit = override if override is not None else (self._auth if is_authenticated else self._anon)
        bucket = int(time.time() // 60)
        key = f"rl:{identifier}:{bucket}"
        pipe = self._r.pipeline()
        pipe.incr(key)
        pipe.expire(key, 90)  # 60s window + 30s grace
        count, _ = await pipe.execute()
        return count <= limit
```

- [ ] **Step 15.4: Tests ausführen**

```bash
cd backend && pytest tests/test_ratelimit.py -v
```

Expected: `5 passed`.

- [ ] **Step 15.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): Redis-backed rate limiter"
```

---

## Task 16: Errors + Error-Handler-Registrierung

**Files:**
- Create: `backend/src/linkhop/errors.py`
- Create: `backend/tests/test_errors.py`

- [ ] **Step 16.1: Test — `tests/test_errors.py`**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from linkhop.errors import AppError, install_error_handlers
from linkhop.url_parser import UnsupportedUrlError


def make_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/raise-app")
    def _raise_app():
        raise AppError(code="test_error", status=418, message="I am a teapot")

    @app.get("/raise-unsupported")
    def _raise_unsupported():
        raise UnsupportedUrlError("bad url")

    return app


def test_app_error_mapped_to_response():
    client = TestClient(make_app())
    resp = client.get("/raise-app")
    assert resp.status_code == 418
    assert resp.json() == {"error": {"code": "test_error", "message": "I am a teapot"}}


def test_unsupported_url_mapped_to_400():
    client = TestClient(make_app())
    resp = client.get("/raise-unsupported")
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "unsupported_service"
    assert "bad url" in body["error"]["message"]
```

- [ ] **Step 16.2: Test laufen — FAIL**

```bash
cd backend && pytest tests/test_errors.py -v
```

- [ ] **Step 16.3: `src/linkhop/errors.py` schreiben**

```python
from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from linkhop.url_parser import UnsupportedUrlError


@dataclass
class AppError(Exception):
    code: str
    status: int
    message: str


def _body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(status_code=exc.status, content=_body(exc.code, exc.message))

    @app.exception_handler(UnsupportedUrlError)
    async def _unsupported(_: Request, exc: UnsupportedUrlError):
        return JSONResponse(status_code=400, content=_body("unsupported_service", str(exc)))

    @app.exception_handler(LookupError)
    async def _lookup(_: Request, exc: LookupError):
        return JSONResponse(status_code=404, content=_body("source_unavailable", str(exc)))
```

- [ ] **Step 16.4: Tests ausführen**

```bash
cd backend && pytest tests/test_errors.py -v
```

Expected: `2 passed`.

- [ ] **Step 16.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): error types and FastAPI handlers"
```

---

## Task 17: Adapter-Registry + Composition-Root

**Files:**
- Modify: `backend/src/linkhop/adapters/__init__.py`
- Create: `backend/src/linkhop/deps.py`
- Modify: `backend/src/linkhop/main.py`
- Create: `backend/tests/test_deps.py`

- [ ] **Step 17.1: `src/linkhop/adapters/__init__.py` ergänzen**

```python
from __future__ import annotations

from linkhop.adapters.base import AdapterCapabilities, ServiceAdapter
from linkhop.adapters.deezer import DeezerAdapter
from linkhop.adapters.spotify import SpotifyAdapter

__all__ = ["AdapterCapabilities", "ServiceAdapter", "SpotifyAdapter", "DeezerAdapter"]
```

- [ ] **Step 17.2: Test — `tests/test_deps.py`**

```python
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
```

- [ ] **Step 17.3: `src/linkhop/deps.py` schreiben**

```python
from __future__ import annotations

import httpx

from linkhop.adapters import DeezerAdapter, ServiceAdapter, SpotifyAdapter
from linkhop.config import Settings


def build_adapter_map(settings: Settings, http: httpx.AsyncClient) -> dict[str, ServiceAdapter]:
    adapters: dict[str, ServiceAdapter] = {}
    if settings.enable_spotify:
        adapters["spotify"] = SpotifyAdapter(
            client=http,
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
        )
    if settings.enable_deezer:
        adapters["deezer"] = DeezerAdapter(client=http)
    # Tidal / YouTube Music kommen in Plan B
    return adapters
```

- [ ] **Step 17.4: `src/linkhop/main.py` erweitern**

```python
from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker

from linkhop.cache import Cache
from linkhop.config import Settings
from linkhop.db import make_engine, make_session_factory
from linkhop.deps import build_adapter_map
from linkhop.errors import install_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    http = httpx.AsyncClient(timeout=15)
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    engine = make_engine(settings)
    session_factory = make_session_factory(engine)

    app.state.http = http
    app.state.redis = redis_client
    app.state.cache = Cache(redis_client, default_ttl=settings.cache_ttl_seconds)
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.adapters = build_adapter_map(settings, http)

    try:
        yield
    finally:
        await http.aclose()
        await redis_client.aclose()
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="linkhop", version="0.1.0",
        docs_url="/api/docs", openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    install_error_handlers(app)
    return app


app = create_app()
```

- [ ] **Step 17.5: Tests ausführen**

```bash
cd backend && pytest tests/test_deps.py tests/test_smoke.py -v
```

Expected: beide grün.

- [ ] **Step 17.6: Commit**

```bash
git add backend/
git commit -m "feat(backend): adapter registry, app lifespan wiring"
```

---

## Task 18: `/api/v1/health`-Endpoint

**Files:**
- Create: `backend/src/linkhop/routes/__init__.py`
- Create: `backend/src/linkhop/routes/health.py`
- Modify: `backend/src/linkhop/main.py`
- Create: `backend/tests/routes/__init__.py`
- Create: `backend/tests/routes/test_health.py`

- [ ] **Step 18.1: Test — `tests/routes/test_health.py`**

```python
from fastapi.testclient import TestClient

from linkhop.config import Settings
from linkhop.main import create_app


def test_health_returns_200_when_dependencies_ok(monkeypatch):
    monkeypatch.setenv("LINKHOP_REDIS_URL", "redis://localhost:6379/0")
    app = create_app(Settings())
    with TestClient(app) as client:
        resp = client.get("/api/v1/health")
    # Tolerant — echte Redis/Postgres laufen im Test nicht
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "redis" in body
    assert "postgres" in body
```

- [ ] **Step 18.2: `tests/routes/__init__.py` + Verzeichnis anlegen**

```bash
mkdir -p backend/tests/routes
touch backend/tests/routes/__init__.py
```

- [ ] **Step 18.3: `src/linkhop/routes/__init__.py` anlegen (leer)**

```bash
mkdir -p backend/src/linkhop/routes
touch backend/src/linkhop/routes/__init__.py
```

- [ ] **Step 18.4: `src/linkhop/routes/health.py` schreiben**

```python
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from linkhop.models.api import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    redis_ok = await request.app.state.cache.ping()
    pg_ok = False
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        pg_ok = True
    except Exception:
        pg_ok = False

    status = "ok" if (redis_ok and pg_ok) else "degraded"
    code = 200 if status == "ok" else 503
    body = HealthResponse(status=status, redis=redis_ok, postgres=pg_ok).model_dump()
    return JSONResponse(status_code=code, content=body)
```

- [ ] **Step 18.5: `main.py` — Router registrieren, innerhalb `create_app` vor Return**

```python
from linkhop.routes import health as health_route
...
    app.include_router(health_route.router)
```

- [ ] **Step 18.6: Tests ausführen**

```bash
cd backend && pytest tests/routes/test_health.py -v
```

Expected: `1 passed`.

- [ ] **Step 18.7: Commit**

```bash
git add backend/
git commit -m "feat(backend): /api/v1/health endpoint"
```

---

## Task 19: `/api/v1/services`-Endpoint

**Files:**
- Create: `backend/src/linkhop/routes/services.py`
- Modify: `backend/src/linkhop/main.py`
- Create: `backend/tests/routes/test_services.py`

- [ ] **Step 19.1: Test — `tests/routes/test_services.py`**

```python
from fastapi.testclient import TestClient

from linkhop.config import Settings
from linkhop.main import create_app


def test_services_lists_enabled_adapters():
    app = create_app(Settings())
    with TestClient(app) as client:
        resp = client.get("/api/v1/services")
    assert resp.status_code == 200
    body = resp.json()
    ids = {s["id"] for s in body["services"]}
    assert "spotify" in ids
    assert "deezer" in ids


def test_services_excludes_disabled(monkeypatch):
    monkeypatch.setenv("LINKHOP_ENABLE_SPOTIFY", "false")
    app = create_app(Settings())
    with TestClient(app) as client:
        resp = client.get("/api/v1/services")
    body = resp.json()
    ids = {s["id"] for s in body["services"]}
    assert "spotify" not in ids
```

- [ ] **Step 19.2: `src/linkhop/routes/services.py` schreiben**

```python
from __future__ import annotations

from fastapi import APIRouter, Request

from linkhop.models.api import ServiceInfo, ServicesResponse

router = APIRouter(prefix="/api/v1", tags=["services"])

_NAMES = {
    "spotify": "Spotify",
    "deezer": "Deezer",
    "tidal": "Tidal",
    "youtube_music": "YouTube Music",
}


@router.get("/services", response_model=ServicesResponse)
async def list_services(request: Request) -> ServicesResponse:
    adapters = request.app.state.adapters
    entries = []
    for sid, adapter in adapters.items():
        caps = []
        if adapter.capabilities.track:
            caps.append("track")
        if adapter.capabilities.album:
            caps.append("album")
        if adapter.capabilities.artist:
            caps.append("artist")
        entries.append(ServiceInfo(id=sid, name=_NAMES.get(sid, sid), capabilities=caps))
    return ServicesResponse(services=entries)
```

- [ ] **Step 19.3: Router registrieren in `main.py` (mit health zusammen)**

```python
from linkhop.routes import health as health_route
from linkhop.routes import services as services_route
...
    app.include_router(health_route.router)
    app.include_router(services_route.router)
```

- [ ] **Step 19.4: Tests ausführen**

```bash
cd backend && pytest tests/routes/test_services.py -v
```

Expected: `2 passed`.

- [ ] **Step 19.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): /api/v1/services endpoint"
```

---

## Task 20: `/api/v1/convert`-Endpoint

**Files:**
- Create: `backend/src/linkhop/routes/convert.py`
- Modify: `backend/src/linkhop/main.py`
- Create: `backend/tests/routes/test_convert.py`

- [ ] **Step 20.1: Test — `tests/routes/test_convert.py`**

```python
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
import fakeredis.aioredis

from linkhop.cache import Cache
from linkhop.config import Settings
from linkhop.main import create_app
from linkhop.models.db import Base
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit


class StubAdapter:
    def __init__(self, sid: str, resolve_value=None, search_value=None):
        self.service_id = sid
        self.capabilities = SimpleNamespace(track=True, album=True, artist=True, supports=lambda t: True)
        self._resolve_value = resolve_value
        self._search_value = search_value or []

    async def resolve(self, parsed):
        return self._resolve_value

    async def search(self, meta, target_type):
        return self._search_value


@pytest.fixture
def patched_app(monkeypatch):
    app = create_app(Settings())

    async def _fake_startup():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.engine = engine

        rc = fakeredis.aioredis.FakeRedis()
        app.state.redis = rc
        app.state.cache = Cache(rc, default_ttl=60)

        source_meta = ResolvedContent(
            service="tidal", type=ContentType.TRACK, id="1",
            url="https://tidal.com/track/1", title="Nightcall",
            artists=("Kavinsky",), album="Outrun",
            duration_ms=257000, isrc="FR6V81200001", upc=None, artwork="",
        )
        app.state.adapters = {
            "tidal": StubAdapter("tidal", resolve_value=source_meta),
            "spotify": StubAdapter("spotify", search_value=[
                SearchHit(service="spotify", id="sp1",
                          url="https://open.spotify.com/track/sp1",
                          confidence=1.0, match="isrc"),
            ]),
            "deezer": StubAdapter("deezer", search_value=[]),
        }

    asyncio.run(_fake_startup())
    return app


def test_convert_happy_path(patched_app):
    with TestClient(patched_app) as client:
        resp = client.get("/api/v1/convert", params={"url": "https://tidal.com/track/1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"]["title"] == "Nightcall"
    assert body["targets"]["spotify"]["status"] == "ok"
    assert body["targets"]["spotify"]["match"] == "isrc"
    assert body["targets"]["deezer"]["status"] == "not_found"
    assert body["cache"]["hit"] is False


def test_convert_returns_cached(patched_app):
    with TestClient(patched_app) as client:
        client.get("/api/v1/convert", params={"url": "https://tidal.com/track/1"})
        resp = client.get("/api/v1/convert", params={"url": "https://tidal.com/track/1"})
    body = resp.json()
    assert body["cache"]["hit"] is True


def test_convert_unsupported_url_400(patched_app):
    with TestClient(patched_app) as client:
        resp = client.get("/api/v1/convert", params={"url": "https://example.com/foo"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_service"


def test_convert_with_share_returns_short_id(patched_app):
    with TestClient(patched_app) as client:
        resp = client.get(
            "/api/v1/convert",
            params={"url": "https://tidal.com/track/1", "share": "true"},
        )
    body = resp.json()
    assert body["share"] is not None
    assert len(body["share"]["id"]) == 6
```

- [ ] **Step 20.2: `src/linkhop/routes/convert.py` schreiben**

```python
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from linkhop.cache import Cache
from linkhop.models.api import (
    CacheInfo, ConvertResponse, ShareInfo, SourceContent, TargetResult,
)
from linkhop.pipeline import Pipeline
from linkhop.short_id import ShortIdService
from linkhop.url_parser import parse

router = APIRouter(prefix="/api/v1", tags=["convert"])


@router.get("/convert", response_model=ConvertResponse)
async def convert(
    request: Request,
    url: str = Query(..., description="Music-service URL"),
    targets: str | None = Query(None, description="Comma-separated list of target service ids"),
    share: bool = Query(False, description="If true, produce a share short-id"),
) -> ConvertResponse:
    parsed = parse(url)

    cache: Cache = request.app.state.cache
    cache_key = Cache.convert_key(parsed.service, parsed.type, parsed.id)
    cached = await cache.get(cache_key)

    adapters = request.app.state.adapters

    if cached:
        source_dict = cached["source"]
        targets_dict = {k: TargetResult(**v) for k, v in cached["targets"].items()}
        source_model = SourceContent(**source_dict)
        cache_info = CacheInfo(hit=True, ttl_seconds=await cache.ttl(cache_key))
    else:
        pipeline = Pipeline(adapters, resolver_factory=None)
        outcome = await pipeline.convert(parsed)

        source_model = SourceContent(
            service=outcome.source.service,
            type=outcome.source.type.value,
            id=outcome.source.id,
            url=outcome.source.url,
            title=outcome.source.title,
            artists=list(outcome.source.artists),
            album=outcome.source.album,
            duration_ms=outcome.source.duration_ms,
            isrc=outcome.source.isrc,
            upc=outcome.source.upc,
            artwork=outcome.source.artwork,
        )
        targets_dict = {
            sid: TargetResult(
                status=t.status, url=t.url, confidence=t.confidence,
                match=t.match, message=t.message,
            )
            for sid, t in outcome.targets.items()
        }
        payload = {
            "source": source_model.model_dump(mode="json"),
            "targets": {k: v.model_dump(mode="json") for k, v in targets_dict.items()},
        }
        await cache.set(cache_key, payload)
        cache_info = CacheInfo(hit=False, ttl_seconds=request.app.state.settings.cache_ttl_seconds)

    if targets:
        wanted = {t.strip() for t in targets.split(",") if t.strip()}
        targets_dict = {k: v for k, v in targets_dict.items() if k in wanted}

    share_info: ShareInfo | None = None
    if share:
        session_factory = request.app.state.session_factory
        async with session_factory() as session:
            svc = ShortIdService(session)
            sid = await svc.get_or_create(
                source_service=parsed.service,
                source_type=parsed.type,
                source_id=parsed.id,
                source_url=url,
            )
        host = request.headers.get("host", "")
        scheme = request.url.scheme
        share_info = ShareInfo(id=sid, url=f"{scheme}://{host}/c/{sid}")

    return ConvertResponse(
        source=source_model,
        targets=targets_dict,
        cache=cache_info,
        share=share_info,
    )
```

- [ ] **Step 20.3: Router in `main.py` registrieren**

```python
from linkhop.routes import convert as convert_route
...
    app.include_router(convert_route.router)
```

- [ ] **Step 20.4: Tests ausführen**

```bash
cd backend && pytest tests/routes/test_convert.py -v
```

Expected: `4 passed`.

- [ ] **Step 20.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): /api/v1/convert endpoint with cache and share"
```

---

## Task 21: `/api/v1/c/{short_id}`-Redirect-Endpoint

**Files:**
- Create: `backend/src/linkhop/routes/share.py`
- Modify: `backend/src/linkhop/main.py`
- Create: `backend/tests/routes/test_share.py`

- [ ] **Step 21.1: Test — `tests/routes/test_share.py`**

```python
# Verwendet den gleichen `patched_app`-Fixture-Pattern wie test_convert.py.
# Für Kürze: Test prüft dass lookup 404 liefert wenn short_id fehlt, und 200 wenn vorhanden.

import asyncio
from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from linkhop.cache import Cache
from linkhop.config import Settings
from linkhop.main import create_app
from linkhop.models.db import Base
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit


class StubAdapter:
    def __init__(self, sid: str, resolve_value=None, search_value=None):
        self.service_id = sid
        self.capabilities = SimpleNamespace(track=True, album=True, artist=True, supports=lambda t: True)
        self._r = resolve_value
        self._s = search_value or []

    async def resolve(self, parsed): return self._r
    async def search(self, meta, t): return self._s


@pytest.fixture
def app_with_share():
    app = create_app(Settings())

    async def _startup():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        app.state.engine = engine
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)

        rc = fakeredis.aioredis.FakeRedis()
        app.state.redis = rc
        app.state.cache = Cache(rc, default_ttl=60)
        app.state.adapters = {
            "tidal": StubAdapter("tidal", resolve_value=ResolvedContent(
                service="tidal", type=ContentType.TRACK, id="1",
                url="https://tidal.com/track/1", title="N", artists=("K",),
                album="Outrun", duration_ms=200000, isrc=None, upc=None, artwork="",
            )),
            "spotify": StubAdapter("spotify", search_value=[
                SearchHit(service="spotify", id="sp1",
                          url="https://open.spotify.com/track/sp1",
                          confidence=1.0, match="isrc"),
            ]),
        }

    asyncio.run(_startup())
    return app


def test_share_404_for_unknown(app_with_share):
    with TestClient(app_with_share) as client:
        resp = client.get("/api/v1/c/notthere")
    assert resp.status_code == 404


def test_share_200_after_create(app_with_share):
    with TestClient(app_with_share) as client:
        create_resp = client.get(
            "/api/v1/convert",
            params={"url": "https://tidal.com/track/1", "share": "true"},
        )
        sid = create_resp.json()["share"]["id"]
        get_resp = client.get(f"/api/v1/c/{sid}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["source"]["title"] == "N"
```

- [ ] **Step 21.2: `src/linkhop/routes/share.py` schreiben**

```python
from __future__ import annotations

from fastapi import APIRouter, Request

from linkhop.errors import AppError
from linkhop.routes.convert import convert as convert_view
from linkhop.short_id import ShortIdService

router = APIRouter(prefix="/api/v1", tags=["share"])


@router.get("/c/{short_id}")
async def open_share(short_id: str, request: Request):
    async with request.app.state.session_factory() as session:
        svc = ShortIdService(session)
        row = await svc.lookup(short_id)
    if row is None:
        raise AppError(code="share_not_found", status=404, message=f"short id not found: {short_id}")
    return await convert_view(request, url=row.source_url, targets=None, share=False)
```

- [ ] **Step 21.3: Router registrieren in `main.py`**

```python
from linkhop.routes import share as share_route
...
    app.include_router(share_route.router)
```

- [ ] **Step 21.4: Tests ausführen**

```bash
cd backend && pytest tests/routes/test_share.py -v
```

Expected: `2 passed`.

- [ ] **Step 21.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): /api/v1/c/{short_id} share lookup"
```

---

## Task 22: Rate-Limit-Middleware + API-Key-Auth-Dependency

**Files:**
- Create: `backend/src/linkhop/middleware.py`
- Modify: `backend/src/linkhop/main.py`
- Modify: `backend/src/linkhop/routes/convert.py`
- Create: `backend/tests/test_middleware.py`

- [ ] **Step 22.1: Test — `tests/test_middleware.py`**

```python
import asyncio
from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from linkhop.api_keys import ApiKeyService
from linkhop.cache import Cache
from linkhop.config import Settings
from linkhop.main import create_app
from linkhop.models.db import Base
from linkhop.models.domain import ContentType, ResolvedContent, SearchHit
from linkhop.ratelimit import RateLimiter


class StubAdapter:
    service_id = "tidal"
    capabilities = SimpleNamespace(track=True, album=True, artist=True)
    async def resolve(self, parsed):
        return ResolvedContent(
            service="tidal", type=ContentType.TRACK, id="1",
            url="https://tidal.com/track/1", title="N", artists=("K",),
            album="A", duration_ms=100000, isrc=None, upc=None, artwork="",
        )
    async def search(self, meta, t):
        return []


@pytest.fixture
def app_with_limits():
    settings = Settings()
    settings.rate_anonymous_per_minute = 2
    settings.rate_with_key_per_minute = 10
    app = create_app(settings)

    async def _startup():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        app.state.engine = engine
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        rc = fakeredis.aioredis.FakeRedis()
        app.state.redis = rc
        app.state.cache = Cache(rc, default_ttl=60)
        app.state.ratelimiter = RateLimiter(
            rc, anonymous_per_minute=2, with_key_per_minute=10,
        )
        app.state.adapters = {"tidal": StubAdapter()}

    asyncio.run(_startup())
    return app


def test_anonymous_rate_limited(app_with_limits):
    with TestClient(app_with_limits) as client:
        for _ in range(2):
            assert client.get("/api/v1/convert", params={"url": "https://tidal.com/track/1"}).status_code == 200
        resp = client.get("/api/v1/convert", params={"url": "https://tidal.com/track/1"})
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "rate_limited"


def test_valid_key_uses_higher_limit(app_with_limits):
    async def _create_key():
        async with app_with_limits.state.session_factory() as s:
            plain, _ = await ApiKeyService(s).create(note="test")
            return plain
    plain = asyncio.run(_create_key())

    with TestClient(app_with_limits) as client:
        for _ in range(5):
            r = client.get(
                "/api/v1/convert",
                params={"url": "https://tidal.com/track/1"},
                headers={"X-API-Key": plain},
            )
            assert r.status_code == 200
```

- [ ] **Step 22.2: `src/linkhop/middleware.py` schreiben**

```python
from __future__ import annotations

from fastapi import Header, HTTPException, Request

from linkhop.api_keys import ApiKeyService
from linkhop.errors import AppError


async def enforce_rate_limit(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict | None:
    limiter = request.app.state.ratelimiter

    key_record = None
    if x_api_key:
        async with request.app.state.session_factory() as session:
            key_record = await ApiKeyService(session).verify(x_api_key)

    if x_api_key and key_record is None:
        raise AppError(code="invalid_api_key", status=401, message="API key not valid")

    if key_record:
        identifier = f"key:{key_record.id}"
        ok = await limiter.check(
            identifier=identifier, is_authenticated=True,
            override=key_record.rate_limit_override,
        )
    else:
        client_host = request.client.host if request.client else "unknown"
        identifier = f"ip:{client_host}"
        ok = await limiter.check(identifier=identifier, is_authenticated=False)

    if not ok:
        raise AppError(code="rate_limited", status=429, message="rate limit exceeded")

    return {"api_key_id": key_record.id if key_record else None}
```

- [ ] **Step 22.3: `main.py` — Ratelimiter im Lifespan aufsetzen**

Füge zu `lifespan` hinzu, nach `app.state.cache = ...`:

```python
    from linkhop.ratelimit import RateLimiter
    app.state.ratelimiter = RateLimiter(
        redis_client,
        anonymous_per_minute=settings.rate_anonymous_per_minute,
        with_key_per_minute=settings.rate_with_key_per_minute,
    )
```

- [ ] **Step 22.4: `routes/convert.py` — Dependency an `GET /convert` + `GET /c/...` hängen**

In `routes/convert.py`, Signatur von `convert()` erweitern:

```python
from fastapi import Depends
from linkhop.middleware import enforce_rate_limit

@router.get("/convert", response_model=ConvertResponse)
async def convert(
    request: Request,
    url: str = Query(...),
    targets: str | None = Query(None),
    share: bool = Query(False),
    _rl=Depends(enforce_rate_limit),
) -> ConvertResponse:
    ...
```

Analog in `routes/share.py` an `open_share`.

- [ ] **Step 22.5: Tests ausführen**

```bash
cd backend && pytest tests/test_middleware.py tests/routes/ -v
```

Expected: alle grün.

- [ ] **Step 22.6: Commit**

```bash
git add backend/
git commit -m "feat(backend): rate-limit middleware + API-key auth"
```

---

## Task 23: `linkhop-admin` CLI

**Files:**
- Create: `backend/src/linkhop/cli.py`
- Create: `backend/tests/test_cli.py`

- [ ] **Step 23.1: Test — `tests/test_cli.py`**

```python
import re

from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from linkhop.cli import cli


def test_key_create_prints_plain(tmp_path, monkeypatch):
    db_path = tmp_path / "db.sqlite"
    monkeypatch.setenv("LINKHOP_DATABASE_URL", f"sqlite:///{db_path}")

    runner = CliRunner()
    # First: init (creates tables)
    r = runner.invoke(cli, ["init-db"])
    assert r.exit_code == 0, r.output

    # Then: key create
    r = runner.invoke(cli, ["key", "create", "--note", "paul"])
    assert r.exit_code == 0
    assert re.search(r"lhk_[A-Za-z0-9]+", r.output)


def test_key_list_and_revoke(tmp_path, monkeypatch):
    db_path = tmp_path / "db.sqlite"
    monkeypatch.setenv("LINKHOP_DATABASE_URL", f"sqlite:///{db_path}")
    runner = CliRunner()
    runner.invoke(cli, ["init-db"])
    created = runner.invoke(cli, ["key", "create", "--note", "a"])
    # extract id from output (format: "id=<uuid> ...")
    m = re.search(r"id=([a-f0-9-]+)", created.output)
    assert m
    key_id = m.group(1)

    listed = runner.invoke(cli, ["key", "list"])
    assert key_id in listed.output

    revoked = runner.invoke(cli, ["key", "revoke", key_id])
    assert revoked.exit_code == 0

    listed2 = runner.invoke(cli, ["key", "list"])
    assert "revoked" in listed2.output.lower()
```

- [ ] **Step 23.2: `src/linkhop/cli.py` schreiben**

```python
from __future__ import annotations

import asyncio

import click
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from linkhop.api_keys import ApiKeyService
from linkhop.config import Settings
from linkhop.models.db import Base


def _sync_url(url: str) -> str:
    # CLI init uses sync driver for CREATE TABLE (simpler)
    return url.replace("+asyncpg", "").replace("+aiosqlite", "")


@click.group()
def cli() -> None:
    """linkhop-admin — verwalte linkhop-Instanz."""


@cli.command("init-db")
def init_db() -> None:
    settings = Settings()
    engine = create_engine(_sync_url(settings.database_url))
    Base.metadata.create_all(engine)
    click.echo("schema created")


@cli.group()
def key() -> None:
    """API-Key management."""


def _make_async_session_factory():
    settings = Settings()
    engine = create_async_engine(settings.database_url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@key.command("create")
@click.option("--note", default=None, help="Freitext, was der Key ist")
@click.option("--override", type=int, default=None, help="Per-Minute-Override")
def key_create(note: str | None, override: int | None) -> None:
    async def _run():
        engine, factory = _make_async_session_factory()
        try:
            async with factory() as session:
                svc = ApiKeyService(session)
                plain, row = await svc.create(note=note, rate_limit_override=override)
                click.echo(f"key id={row.id} prefix={row.key_prefix}")
                click.echo(f"plaintext (one-time): {plain}")
        finally:
            await engine.dispose()
    asyncio.run(_run())


@key.command("list")
def key_list() -> None:
    async def _run():
        engine, factory = _make_async_session_factory()
        try:
            async with factory() as session:
                rows = await ApiKeyService(session).list_all()
                for r in rows:
                    status = f"revoked at {r.revoked_at}" if r.revoked_at else "active"
                    click.echo(f"id={r.id} prefix={r.key_prefix} note={r.note!r} [{status}]")
        finally:
            await engine.dispose()
    asyncio.run(_run())


@key.command("revoke")
@click.argument("key_id")
def key_revoke(key_id: str) -> None:
    async def _run():
        engine, factory = _make_async_session_factory()
        try:
            async with factory() as session:
                await ApiKeyService(session).revoke(key_id)
                click.echo(f"revoked: {key_id}")
        finally:
            await engine.dispose()
    asyncio.run(_run())


def main() -> None:
    cli()
```

- [ ] **Step 23.3: Tests ausführen**

```bash
cd backend && pytest tests/test_cli.py -v
```

Expected: `2 passed`.

- [ ] **Step 23.4: Commit**

```bash
git add backend/
git commit -m "feat(backend): linkhop-admin CLI for init-db and api-keys"
```

---

## Task 24: JSON-Logging und Request-Logs

**Files:**
- Create: `backend/src/linkhop/logging.py`
- Modify: `backend/src/linkhop/main.py`
- Create: `backend/tests/test_logging.py`

- [ ] **Step 24.1: Test — `tests/test_logging.py`**

```python
import json
import logging

from linkhop.logging import configure_logging, JsonFormatter


def test_formatter_produces_valid_json():
    fmt = JsonFormatter()
    rec = logging.LogRecord(
        name="linkhop.test", level=logging.INFO, pathname=__file__, lineno=10,
        msg="hello %s", args=("world",), exc_info=None,
    )
    out = fmt.format(rec)
    body = json.loads(out)
    assert body["level"] == "INFO"
    assert body["message"] == "hello world"
    assert body["logger"] == "linkhop.test"


def test_configure_logging_runs():
    configure_logging(level="DEBUG")
    logging.getLogger("linkhop.test").info("check")
```

- [ ] **Step 24.2: `src/linkhop/logging.py` schreiben**

```python
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for attr in ("request_id", "path", "method", "status_code", "duration_ms", "service"):
            v = getattr(record, attr, None)
            if v is not None:
                payload[attr] = v
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
```

- [ ] **Step 24.3: `main.py` — Logging initialisieren, Access-Middleware hinzufügen**

In `create_app`:

```python
from linkhop.logging import configure_logging
...
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(level=settings.log_level)
    ...
```

Optional: eine HTTP-Middleware, die Requests mit Status + Dauer loggt. Für V1 überlassen wir das Uvicorn's Access-Log (reicht).

- [ ] **Step 24.4: Tests ausführen**

```bash
cd backend && pytest tests/test_logging.py -v
```

Expected: `2 passed`.

- [ ] **Step 24.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): json-structured logging"
```

---

## Task 25: Dockerfile und lokale Dev-Integration

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/docker-compose.yml` (für lokale Entwicklung)
- Create: `backend/scripts/dev.sh`

- [ ] **Step 25.1: `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim AS build
WORKDIR /app
RUN pip install --no-cache-dir hatchling
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.12-slim
RUN useradd -u 10001 -m linkhop
WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl \
        "uvicorn[standard]==0.32.*" \
        asyncpg==0.29.*
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
USER linkhop
EXPOSE 8080
CMD ["uvicorn", "linkhop.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 25.2: `backend/README.md` schreiben**

```markdown
# linkhop-backend

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Postgres + Redis per docker-compose
docker-compose up -d

# Schema anlegen
alembic upgrade head

# Server starten
uvicorn linkhop.main:app --reload --port 8080

# Admin-CLI
linkhop-admin key create --note "local dev"
```

## Tests

```bash
pytest -v
```
```

- [ ] **Step 25.3: `backend/docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: linkhop
      POSTGRES_PASSWORD: linkhop
      POSTGRES_DB: linkhop
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

- [ ] **Step 25.4: Build smoke-testen**

```bash
cd backend && docker build -t linkhop-backend:local .
```

Expected: Build erfolgreich, Image ~120 MB.

- [ ] **Step 25.5: Commit**

```bash
git add backend/
git commit -m "feat(backend): Dockerfile + docker-compose for local dev"
```

---

## Task 26: End-to-End-Test mit realen Spotify + Deezer (optional, manuell getriggert)

**Files:**
- Create: `backend/tests/integration/test_real_spotify_deezer.py`
- Modify: `backend/pyproject.toml`

- [ ] **Step 26.1: Integration-Test schreiben — `tests/integration/test_real_spotify_deezer.py`**

```python
import os

import httpx
import pytest

from linkhop.adapters.deezer import DeezerAdapter
from linkhop.adapters.spotify import SpotifyAdapter
from linkhop.url_parser import parse

pytestmark = pytest.mark.skipif(
    not os.environ.get("LINKHOP_LIVE_TESTS"),
    reason="Live tests deaktiviert. Setze LINKHOP_LIVE_TESTS=1 und Credentials.",
)


@pytest.fixture
async def clients():
    async with httpx.AsyncClient(timeout=15) as http:
        yield {
            "spotify": SpotifyAdapter(
                client=http,
                client_id=os.environ["LINKHOP_SPOTIFY_CLIENT_ID"],
                client_secret=os.environ["LINKHOP_SPOTIFY_CLIENT_SECRET"],
            ),
            "deezer": DeezerAdapter(client=http),
        }


async def test_spotify_to_deezer_via_isrc(clients):
    parsed = parse("https://open.spotify.com/track/6habFhsOp2NvshLv26DqMb")
    source = await clients["spotify"].resolve(parsed)
    assert source is not None
    hits = await clients["deezer"].search(source, parsed.type and __import__("linkhop.models.domain", fromlist=["ContentType"]).ContentType(parsed.type))
    assert any(h.match == "isrc" for h in hits)


async def test_deezer_to_spotify_via_isrc(clients):
    parsed = parse("https://www.deezer.com/track/3135556")
    source = await clients["deezer"].resolve(parsed)
    assert source is not None
    from linkhop.models.domain import ContentType
    hits = await clients["spotify"].search(source, ContentType(parsed.type))
    assert any(h.match == "isrc" for h in hits)
```

- [ ] **Step 26.2: pytest-Marker in `pyproject.toml` ergänzen**

In `[tool.pytest.ini_options]` einfügen:

```toml
markers = ["integration: real API calls; enable with LINKHOP_LIVE_TESTS=1"]
```

- [ ] **Step 26.3: Tests sollten per Default SKIP sein**

```bash
cd backend && pytest tests/integration/ -v
```

Expected: 2 `skipped`.

- [ ] **Step 26.4: Commit**

```bash
git add backend/
git commit -m "test(backend): optional live integration tests for Spotify/Deezer"
```

---

## Task 27: Full-Suite + Coverage-Check

- [ ] **Step 27.1: Kompletter Test-Lauf mit Coverage**

```bash
cd backend && pytest --cov=linkhop --cov-report=term-missing -v
```

Expected:
- Alle Tests grün (~50-60 Tests)
- Coverage ≥ 85 % für `linkhop/` gesamt
- Fehlende Zeilen: hauptsächlich Fehlerpfade im Adapter, Lifespan-Code

- [ ] **Step 27.2: Ruff-Lint**

```bash
cd backend && ruff check .
```

Expected: keine Issues.

- [ ] **Step 27.3: Mypy (best effort)**

```bash
cd backend && mypy src/linkhop --ignore-missing-imports
```

Issues aufschreiben, aber nicht blockierend.

- [ ] **Step 27.4: Final-Commit**

```bash
git add backend/
git commit --allow-empty -m "chore(backend): plan A complete — backend core with spotify/deezer"
```

---

## Zusammenfassung

Nach Abschluss dieses Plans ist das Backend funktionsfähig:

- FastAPI-App mit `/api/v1/convert`, `/c/{sid}`, `/services`, `/health`, `/docs`
- Spotify- und Deezer-Adapter (Resolve + Search)
- Matching-Pipeline mit ISRC/UPC/Metadata-Scoring
- Postgres + Redis + Short-IDs
- API-Key-CLI (`linkhop-admin`)
- Rate-Limiting (anonym + API-Key)
- JSON-Logging
- Dockerfile + docker-compose für lokale Entwicklung
- ~50 Unit-Tests, optional Live-Integrationstests

**Nächster Plan (Plan B):** Tidal- und YouTube-Music-Adapter ergänzen.

## Spec Coverage Check

- Architektur (3 Tiers) ✓ (Tasks 1-17 legen Backend-Layer; Frontend + Chart in separaten Plänen)
- V1-Dienste Spotify, Deezer ✓ (Tasks 8-10) — Tidal, YT Music in Plan B
- Tracks/Alben/Artists ✓ (`ContentType`-Enum, alle Adapter)
- `/api/v1/convert` ✓ (Task 20)
- `/api/v1/services` ✓ (Task 19)
- `/api/v1/health` ✓ (Task 18)
- `/api/v1/c/{id}` ✓ (Task 21)
- OpenAPI-Docs ✓ (FastAPI auto, Task 1)
- Rate-Limiting ✓ (Task 15, 22)
- API-Key-CLI ✓ (Task 23)
- Short-IDs ✓ (Task 13)
- Scoring-Schwellen 0.7/0.4 ✓ (Task 11)
- Partielle Ergebnisse ✓ (Task 12)
- Postgres-Schema ✓ (Task 5)
- Redis-Cache mit TTL ✓ (Task 6, 20)
- Error-Format `{error: {code, message}}` ✓ (Task 16)
- `existingSecret`-Pattern, Helm — **nicht in Plan A**, kommt in Plan D
- Frontend — **nicht in Plan A**, kommt in Plan C
- NetworkPolicy, PDB — **nicht in Plan A**, kommt in Plan D
