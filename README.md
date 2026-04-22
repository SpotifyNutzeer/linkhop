# linkhop

**Music-link converter across streaming services.** Paste a track, album or
artist link from one service, get the equivalent on every other one.

> Live at **<https://linkhop.paul.wtf>**

Similar in spirit to Odesli / song.link, but self-hosted, Kubernetes-native
and without trackers — match quality is boosted by preferring industry
identifiers (ISRC for tracks, UPC for albums) over fuzzy metadata search.

## Supported services

| Service       | Tracks | Albums | Artists | Notes                     |
| ------------- | ------ | ------ | ------- | ------------------------- |
| Spotify       | ✓      | ✓      | ✓       | OAuth client credentials  |
| Deezer        | ✓      | ✓      | ✓       | No credentials needed     |
| Tidal         | ✓      | ✓      | ✓       | OAuth client credentials  |
| YouTube Music | ✓      | ✓      | ✓       | `ytmusicapi`, unofficial  |

Playlists are out of scope for V1.

## Features

- Bidirectional conversion between all supported services
- **ISRC / UPC matching** for high-quality results; metadata fallback with a
  confidence score exposed via the API
- **Shareable short links** (`/c/<id>`), persisted in Postgres — the link
  lands on a rendered result page, not a JSON endpoint
- **Redis cache** for resolved links (default 7 d TTL)
- **Rate-limiting** per IP or per API key, each independently configurable
- **OpenAPI** docs served at `/api/v1/docs`, Swagger UI
- **Catppuccin Mocha / Latte** theme with `prefers-color-scheme` auto-detect
  and a manual toggle
- Progressive enhancement: `?url=` query parameter triggers an immediate
  conversion, so the site can be used as a browser-search-engine target

## Stack

| Layer       | Tech                                                          |
| ----------- | ------------------------------------------------------------- |
| Backend     | Python 3.12, FastAPI, SQLAlchemy 2 (async), asyncpg, Alembic  |
| Frontend    | SvelteKit (`adapter-static`), TypeScript, Vite                |
| Cache       | Redis 7                                                       |
| Database    | Postgres 16 (CNPG in production)                              |
| Tests       | pytest, Playwright (E2E), Vitest (components)                 |
| Packaging   | Docker images, Helm chart (with Redis sub-chart)              |
| Deployment  | FluxCD → RKE2 + Traefik + cert-manager + external-dns         |

## Quick start (local dev)

Backend (needs Python 3.12):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker-compose up -d               # Postgres + Redis only
alembic upgrade head
uvicorn linkhop.main:app --reload --port 8080
```

Frontend (needs Node 22 + pnpm):

```bash
cd frontend
pnpm install
pnpm gen:api                       # generate typed client from backend OpenAPI
pnpm dev                           # http://localhost:5173, proxied /api → :8080
```

Then open <http://localhost:5173> and paste a Deezer track URL
(Deezer works without credentials; Spotify/Tidal need client credentials
via env vars — see `backend/README.md`).

See [`backend/README.md`](backend/README.md) for the full env-var reference,
admin CLI (`linkhop-admin key create|list|revoke`) and live-integration
test setup.

## API (quick reference)

All endpoints under `/api/v1`. Full schema at `/api/v1/docs`.

| Method | Path                | Purpose                                         |
| ------ | ------------------- | ----------------------------------------------- |
| `GET`  | `/convert?url=...`  | Resolve a link; optional `?share=true` returns a short-id |
| `GET`  | `/c/{short_id}`     | JSON lookup for a short-id (frontend renders `/c/{id}`) |
| `GET`  | `/services`         | Enabled services with display metadata          |
| `GET`  | `/health`           | Liveness + readiness (Redis, Postgres)          |
| `GET`  | `/docs`             | Swagger UI                                      |
| `GET`  | `/openapi.json`     | OpenAPI schema                                  |

## Deployment

A Helm chart is released on every `linkhop-<version>` git tag via
[`helm/chart-releaser-action`][chart-releaser] and served from GitHub Pages:

```bash
helm repo add linkhop https://spotifynutzeer.github.io/linkhop
helm install linkhop linkhop/linkhop --namespace linkhop --create-namespace
```

Container images are published to GHCR on every `v<version>` release:

- `ghcr.io/spotifynutzeer/linkhop-backend:<version>`
- `ghcr.io/spotifynutzeer/linkhop-frontend:<version>`

The chart expects credentials via an `existingSecret` so secrets can be
managed by your tool of choice (External Secrets Operator, sealed-secrets,
sops, plain kubectl). Required keys:
`LINKHOP_DATABASE_URL`, `LINKHOP_REDIS_URL`, `LINKHOP_SPOTIFY_CLIENT_ID`/`_SECRET`,
`LINKHOP_TIDAL_CLIENT_ID`/`_SECRET`.

See [`helm/linkhop/`](helm/linkhop/) for chart values and templates, and
[`docs/superpowers/specs/2026-04-21-helm-chart-design.md`](docs/superpowers/specs/2026-04-21-helm-chart-design.md)
for the design rationale.

## Design docs

- [Backend & API design](docs/superpowers/specs/2026-04-18-linkhop-design.md)
- [Frontend design](docs/superpowers/specs/2026-04-19-linkhop-frontend-design.md)
- [Helm chart design](docs/superpowers/specs/2026-04-21-helm-chart-design.md)

## License

No license file yet — treat the code as "all rights reserved" until one
lands. Open an issue if you need a permissive grant.

[chart-releaser]: https://github.com/helm/chart-releaser-action
