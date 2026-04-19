# linkhop-backend

FastAPI service that converts music-streaming URLs between providers
(Spotify, Deezer in V1) via ISRC/UPC/metadata matching.

## Development

Set up a virtualenv and install the package with dev extras:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Start Postgres and Redis via docker-compose. Note that `docker-compose.yml`
**only runs the databases**; the API itself runs on the host under
`uvicorn --reload`, so you get live code reload without container rebuild:

```bash
docker-compose up -d
```

Apply the database schema (run from the host venv, not inside a container —
the compose services do not ship alembic):

```bash
alembic upgrade head
```

Run the API with auto-reload:

```bash
uvicorn linkhop.main:app --reload --port 8080
```

The OpenAPI docs are served at `http://localhost:8080/api/docs`.

## Configuration

All settings are loaded from env vars prefixed `LINKHOP_` (see
`src/linkhop/config.py`). The defaults match the docker-compose setup,
so a plain `docker-compose up -d` + `uvicorn …` works without overrides.

| Env var | Default | Notes |
| --- | --- | --- |
| `LINKHOP_DATABASE_URL` | `postgresql+asyncpg://linkhop:linkhop@localhost:5432/linkhop` | Matches compose. |
| `LINKHOP_REDIS_URL` | `redis://localhost:6379/0` | Matches compose. |
| `LINKHOP_LOG_LEVEL` | `INFO` | `DEBUG` for verbose dev logs. |
| `LINKHOP_ENABLE_SPOTIFY` / `_DEEZER` / `_TIDAL` | all `true` | Toggle individual adapters. |
| `LINKHOP_SPOTIFY_CLIENT_ID` / `_SECRET` | empty | Required when Spotify is enabled. |
| `LINKHOP_TIDAL_CLIENT_ID` / `_SECRET` | empty | Required when Tidal is enabled. |
| `LINKHOP_RATE_ANONYMOUS` / `_RATE_WITH_KEY` | 20 / 300 per minute | |
| `LINKHOP_CACHE_TTL` | 604800 (7 days) | Redis cache TTL. |
| `LINKHOP_CORS_ALLOW_ORIGINS` | `*` | CSV of origins or `*`. |
| `LINKHOP_FORWARDED_ALLOW_IPS` | `127.0.0.1` | Container-only; trusted CIDR for `X-Forwarded-For`. |

## Admin CLI

The `linkhop-admin` console script (installed by `pip install -e .`)
manages API keys:

```bash
linkhop-admin key create --note "local dev"
linkhop-admin key list
linkhop-admin key revoke <key-id>
```

Run `linkhop-admin --help` for the full command reference.

## Tests

```bash
pytest -v
```

Run with coverage:

```bash
pytest --cov=linkhop --cov-report=term-missing -v
```

Live integration tests against real Spotify/Deezer APIs are skipped by
default; enable them with `LINKHOP_LIVE_TESTS=1` and the matching
`LINKHOP_SPOTIFY_CLIENT_ID` / `LINKHOP_SPOTIFY_CLIENT_SECRET` env vars.
