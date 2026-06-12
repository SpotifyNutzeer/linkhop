# Umstellung auf uv — Design-Spezifikation

**Datum:** 2026-06-13
**Status:** Design, genehmigt für Implementierungsplanung
**Autor:** Paul Weber (brainstorming mit Claude)

## Überblick

Das Backend nutzt bisher venv + pip ohne Lockfile: lokal `pip install -e
".[dev]"`, in CI dasselbe, im Docker-Image löst pip transitive Dependencies
beim Build neu auf. Ein `backend/uv.lock` lag bereits untracked im Repo,
war aber veraltet (ohne `ytmusicapi`) — genau die Drift, die ein
durchgezogener Lockfile-Workflow verhindert.

Dieses Spec stellt das Backend vollständig auf uv um: Lockfile committet,
lokales Setup, CI und Docker-Image installieren exakt die gelockten
Stände. Das Frontend (pnpm) ist nicht betroffen.

## Ziele und Nicht-Ziele

### Ziele

- **Ein committetes `uv.lock`** als einzige Quelle der aufgelösten
  Dependency-Versionen
- **CI erzwingt Lock-Konsistenz**: `uv sync --locked` schlägt fehl, wenn
  `pyproject.toml` geändert wurde, ohne den Lock zu aktualisieren
- **Reproduzierbares Docker-Image**: Installation aus dem Lock, nicht aus
  erneuter pip-Resolution
- **uv-idiomatische Dev-Dependencies** via `[dependency-groups]` (PEP 735)

### Nicht-Ziele

- **Kein Wechsel des Build-Backends**: Hatchling bleibt; am Wheel-Bau und
  an den `[project]`-Metadaten ändert sich nichts
- **Keine Frontend-Änderungen** (pnpm bleibt)
- **Keine Dependency-Updates** im Zuge der Migration: der neue Lock pinnt
  die aktuellen `==X.Y.*`-Auflösungen, Upgrades sind separate Arbeit

## Entscheidungsgrundlage

| Ansatz | Bewertung |
|---|---|
| **Voll uv-idiomatisch (gewählt)** | dependency-groups, Lock committet, CI `uv sync --locked`, Docker `uv sync --locked --no-dev`. Reproduzierbarkeit end-to-end. |
| uv nur als pip-Ersatz (`uv pip install`) | Schneller, aber kein Lockfile-Workflow — verwirft den Hauptgewinn. |
| Hybrid (Lock + CI uv, Dev-Deps als optional-dependencies) | pip-Kompatibilität als Begründung ist dünn: pip ≥ 25.1 kann Dependency-Groups installieren, und das Projekt hat einen Entwickler. |

## Änderungen im Einzelnen

### `backend/pyproject.toml`

`[project.optional-dependencies] dev = […]` wird zu `[dependency-groups]
dev = […]` mit identischen Pins. `uv sync` installiert die dev-Gruppe per
Default; das Runtime-Paket trägt keine Dev-Extras mehr.

### Lockfile

`uv lock` regeneriert `backend/uv.lock` (der liegende ist veraltet);
das Lockfile wird committet. Lokaler Workflow danach:

```bash
cd backend
uv sync                 # erstellt/aktualisiert .venv aus dem Lock
uv run uvicorn linkhop.main:app --reload --port 8080
uv run pytest
```

### CI (`.github/workflows/backend.yml`, check-Job)

- `actions/setup-python` → `astral-sh/setup-uv@v7` mit
  `python-version: "3.12"` und aktiviertem Cache
- `pip install -e '.[dev]'` → `uv sync --locked`
- `ruff`/`mypy`/`alembic`/`pytest`-Schritte laufen als `uv run …`

`--locked` macht Lock-Drift zum CI-Fehler statt zu stiller Abweichung.

### `backend/Dockerfile`

- **Build-Stage**: `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`;
  `uv sync --locked --no-dev --no-editable` installiert Projekt +
  Dependencies in `/app/.venv`. Layer-Reihenfolge so, dass
  `pyproject.toml` + `uv.lock` vor `src/` kopiert werden
  (Dependency-Layer cached über Code-Änderungen hinweg, via
  `--no-install-project` im ersten Sync-Schritt).
- **Runtime-Stage**: bleibt `python:3.12-slim`, kopiert nur `/app/.venv`
  (uv selbst landet nicht im finalen Image). ENV-Flags, non-root-User,
  EXPOSE, HEALTHCHECK und CMD bleiben unverändert; `uvicorn` wird über
  `PATH`-Eintrag des venv (oder absoluten venv-Pfad) gestartet.
- Die historischen Kommentare zur pip-Pin-Problematik werden durch einen
  Hinweis ersetzt, dass die Versionsgarantie jetzt aus `uv.lock` kommt.

### Dokumentation

- `backend/README.md`: Development-Abschnitt auf `uv sync`/`uv run`;
  Hinweis, dass `uv run alembic upgrade head` vom Host läuft
- Root-`README.md`: Quick-start-Backend-Block auf uv; Stack-Tabelle
  erwähnt uv beim Backend bzw. Packaging

## Fehlerbehandlung / Risiken

| Risiko | Einschätzung |
|---|---|
| Neuer Lock zieht andere Patch-Versionen als die bisherigen venvs | Pins sind `==X.Y.*` — nur Patch-Drift möglich; volle Testsuite nach `uv sync` verifiziert. |
| CI-Cache-Verhalten von setup-uv | `enable-cache: true` cached gegen `uv.lock`-Hash; Worst Case ist ein langsamer, aber korrekter Build. |
| Docker-Build bricht (uv-Image-Tag, venv-Pfad) | Lokaler `docker build` + Container-Smoke-Test ist Teil der Verifikation, vor dem Push. |

## Verifikation

1. `uv sync` in `backend/`, dann `uv run pytest` (volle Suite),
   `uv run ruff check src tests`, `uv run mypy src` — alles grün
2. `uv lock --check` bestätigt, dass Lock und `pyproject.toml` konsistent sind
3. `docker build backend/` erfolgreich; Container startet mit
   docker-compose-Postgres/Redis und `/api/v1/health` antwortet
4. CI-Lauf grün (nach Push sichtbar)
