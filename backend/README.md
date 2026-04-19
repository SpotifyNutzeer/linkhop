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

Start Postgres and Redis via docker-compose:

```bash
docker-compose up -d
```

Apply the database schema:

```bash
alembic upgrade head
```

Run the API with auto-reload:

```bash
uvicorn linkhop.main:app --reload --port 8080
```

The OpenAPI docs are served at `http://localhost:8080/docs`.

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
