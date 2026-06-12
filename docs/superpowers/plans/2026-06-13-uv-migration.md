# uv-Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend-Dependency-Management vollständig auf uv umstellen — committetes Lockfile, CI mit `uv sync --locked`, Docker-Image installiert exakt die gelockten Stände.

**Architecture:** `pyproject.toml` bekommt PEP-735-`[dependency-groups]` statt dev-Extras; `uv.lock` wird regeneriert und committet. CI ersetzt setup-python/pip durch `astral-sh/setup-uv` + `uv sync --locked` + `uv run`. Das Dockerfile wird zweistufig mit uv-Builder (`uv sync --locked --no-dev`) und schlankem Runtime-Image, das nur das venv kopiert. Hatchling bleibt Build-Backend.

**Tech Stack:** uv (lokal installiert: 0.11.x), Python 3.12, GitHub Actions, Docker.

**Spec:** `docs/superpowers/specs/2026-06-13-uv-migration-design.md`

**Hinweise für alle Tasks:**
- Arbeitsverzeichnis für uv-Kommandos: `backend/`.
- Keine Dependency-Upgrades: die `==X.Y.*`-Pins in `pyproject.toml` bleiben unverändert; der Lock friert nur deren aktuelle Auflösung ein.
- Das System-Python ist 3.14 — deshalb legt Task 1 eine `.python-version` mit `3.12` an, sonst würde `uv sync` lokal 3.14 wählen (README und CI sagen 3.12).

---

### Task 1: pyproject auf dependency-groups, Lockfile erzeugen, lokales Setup

**Files:**
- Modify: `backend/pyproject.toml` (Abschnitt `[project.optional-dependencies]`)
- Create: `backend/.python-version`
- Create (regeneriert): `backend/uv.lock` — der vorhandene untracked `uv.lock` ist veraltet (ohne ytmusicapi) und wird überschrieben

- [ ] **Step 1: dev-Extras zu dependency-groups machen**

In `backend/pyproject.toml` den Block

```toml
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
```

ersetzen durch (identische Pins, nur PEP-735-Sektion):

```toml
[dependency-groups]
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
```

- [ ] **Step 2: Python-Version pinnen**

`backend/.python-version` anlegen mit Inhalt:

```
3.12
```

- [ ] **Step 3: Lockfile regenerieren**

```bash
cd backend && rm -f uv.lock && uv lock
```

Expected: `uv lock` läuft durch („Resolved N packages…"). Verifizieren, dass der neue Lock vollständig ist:

```bash
grep -c 'name = "ytmusicapi"' uv.lock
```

Expected: mindestens `1` (der alte, veraltete Lock kannte ytmusicapi nicht).

- [ ] **Step 4: venv neu aufbauen und synchen**

Das bestehende `backend/.venv` ist pip-verwaltet — sauber ersetzen:

```bash
cd backend && rm -rf .venv && uv sync
```

Expected: uv erstellt `.venv` mit Python 3.12 und installiert Projekt + dev-Gruppe aus dem Lock.

- [ ] **Step 5: Volle Verifikation über uv**

```bash
cd backend && uv run pytest -q && uv run ruff check src tests && uv run mypy src && uv lock --check
```

Expected: `208 passed, 7 skipped` (Integration-Tests ohne `LINKHOP_LIVE_TESTS` geskippt), ruff „All checks passed!", mypy „no issues found", `uv lock --check` bestätigt Konsistenz.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/.python-version
git commit -m "build(backend): manage dependencies with uv, commit lockfile"
```

---

### Task 2: CI auf uv umstellen

**Files:**
- Modify: `.github/workflows/backend.yml:46-63` (check-Job, Steps ab setup-python)

- [ ] **Step 1: Steps ersetzen**

Im `check`-Job den Block

```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -e '.[dev]'

      - name: Lint
        run: ruff check src tests

      - name: Type check
        run: mypy src

      - name: Run migrations
        run: alembic upgrade head

      - name: Run tests
        run: pytest --tb=short -q
```

ersetzen durch:

```yaml
      - uses: astral-sh/setup-uv@v7
        with:
          python-version: "3.12"
          enable-cache: true
          cache-dependency-glob: "backend/uv.lock"

      # --locked macht Lock-Drift (pyproject geändert, Lock nicht) zum CI-Fehler.
      - name: Install dependencies
        run: uv sync --locked

      - name: Lint
        run: uv run ruff check src tests

      - name: Type check
        run: uv run mypy src

      - name: Run migrations
        run: uv run alembic upgrade head

      - name: Run tests
        run: uv run pytest --tb=short -q
```

(Der `image`-Job bleibt unverändert — er baut nur das Docker-Image, das Task 3 umstellt. `defaults.run.working-directory: backend` bleibt; `cache-dependency-glob` ist dagegen repo-relativ, daher das `backend/`-Präfix.)

- [ ] **Step 2: YAML-Syntax prüfen**

```bash
cd backend && uv run python -c "import yaml; yaml.safe_load(open('../.github/workflows/backend.yml')); print('yaml ok')"
```

Expected: `yaml ok`. (PyYAML ist transitive Dependency; falls der Import fehlschlägt, stattdessen `python3 -c …` mit System-Python verwenden.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/backend.yml
git commit -m "ci(backend): install via uv sync --locked"
```

---

### Task 3: Dockerfile auf uv-Builder umstellen

**Files:**
- Modify: `backend/Dockerfile` (komplett ersetzen)

- [ ] **Step 1: Dockerfile ersetzen**

`backend/Dockerfile` vollständig ersetzen durch:

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
WORKDIR /app
# Bytecode beim Build vorkompilieren beschleunigt den Container-Start.
# copy statt hardlink, weil uv-Cache und /app in unterschiedlichen Layern liegen.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
# Erst Manifest + Lock, Code später: der Dependency-Layer überlebt
# Code-Änderungen im Docker-Cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-editable
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim
# Python-Runtime-Flags: ohne PYTHONUNBUFFERED sitzen stdout-Lines in Buffern,
# wenn stdout eine Pipe ist (immer unter Docker) — bei Crash verliert man die
# letzten JSON-Log-Records. PYTHONDONTWRITEBYTECODE spart Schreibzugriffe im
# Nur-Lese-Container-Layout (die .pyc aus dem Build-Stage existieren schon).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LINKHOP_FORWARDED_ALLOW_IPS=127.0.0.1 \
    PATH="/app/.venv/bin:$PATH"
RUN useradd -u 10001 -m linkhop
WORKDIR /app
# Versionsgarantie kommt aus uv.lock (Build-Stage installiert --locked).
# Das Runtime-Image enthält nur das fertige venv — kein uv, kein pip-Resolve.
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
USER linkhop
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=2).read()" || exit 1
# sh -c statt exec-form, weil exec-form kein Env-Expansion macht. Der Wechsel
# gibt Operatoren einen Override-Knopf ohne den CMD komplett neu zu setzen:
# `-e LINKHOP_FORWARDED_ALLOW_IPS=10.0.0.0/8` reicht. Default 127.0.0.1 bleibt
# sicher-by-default (kein Spoofing von X-Forwarded-For aus dem Open Internet).
CMD ["sh", "-c", "exec uvicorn linkhop.main:app --host 0.0.0.0 --port 8080 --proxy-headers --forwarded-allow-ips=\"$LINKHOP_FORWARDED_ALLOW_IPS\""]
```

Hinweise:
- Das alte `COPY … README.md` entfällt: `pyproject.toml` deklariert kein
  `readme`-Feld, Hatchling braucht die Datei nicht.
- `.venv/bin/python` ist ein Symlink auf `/usr/local/bin/python3.12` —
  identischer Pfad in Build- (uv-bookworm-slim) und Runtime-Image
  (python:3.12-slim), das ist das dokumentierte uv-Multistage-Pattern.

- [ ] **Step 2: Image bauen**

```bash
cd backend && docker build -t linkhop-backend:uv-smoke .
```

Expected: Build läuft durch; im Log sichtbar, dass `uv sync --locked` die Pakete installiert (kein pip).

- [ ] **Step 3: Smoke-Test gegen compose-Datenbanken**

```bash
cd backend && docker compose up -d
uv run alembic upgrade head
docker run -d --rm --name linkhop-uv-smoke --network host linkhop-backend:uv-smoke
sleep 3
curl -fsS http://127.0.0.1:8080/api/v1/health
docker logs linkhop-uv-smoke 2>&1 | tail -5
docker stop linkhop-uv-smoke
```

Expected: `curl` liefert die Health-Antwort (HTTP 200, JSON mit Status); die Logs zeigen einen sauberen uvicorn-Start. (`--network host`, weil die Default-Settings auf `localhost:5432`/`localhost:6379` zeigen — genau das compose-Setup. Falls Port 8080 belegt ist: belegenden Prozess prüfen, nicht den Test überspringen.)

- [ ] **Step 4: Commit**

```bash
git add backend/Dockerfile
git commit -m "build(backend): install locked dependencies via uv in Docker image"
```

---

### Task 4: Dokumentation

**Files:**
- Modify: `backend/README.md` (Development- und Test-Abschnitt)
- Modify: `README.md` (Quick start Backend-Block, Stack-Tabelle)

- [ ] **Step 1: backend/README.md Development-Abschnitt**

Den Block

````markdown
Set up a virtualenv and install the package with dev extras:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```
````

ersetzen durch:

````markdown
Install [uv](https://docs.astral.sh/uv/), then sync the environment
(creates `.venv` from `uv.lock`, including the dev dependency group):

```bash
uv sync
```
````

- [ ] **Step 2: backend/README.md Kommandos auf `uv run` prefixen**

Alle Kommando-Blöcke im README, die bisher das aktivierte venv voraussetzen, bekommen das `uv run`-Präfix. Konkret:

- `alembic upgrade head` → `uv run alembic upgrade head`
- `uvicorn linkhop.main:app --reload --port 8080` → `uv run uvicorn linkhop.main:app --reload --port 8080`
- `pytest --cov=linkhop --cov-report=term-missing -v` → `uv run pytest --cov=linkhop --cov-report=term-missing -v`
- die `linkhop-admin key …`-Beispiele und der Satz „installed by `pip install -e .`" → `uv run linkhop-admin key …`, Klammertext zu „(available via `uv run`)"
- Kontrolle, dass nichts übersehen wurde: `grep -nE '^(pytest|alembic|uvicorn|linkhop-admin|pip |python -m)' backend/README.md` darf keine Treffer mehr ohne `uv run` liefern (Zeilen in Prosa, die pip historisch erwähnen, sind okay, solange sie keine Anleitung mehr sind).

- [ ] **Step 3: Root-README Quick start**

Den Block

````markdown
Backend (needs Python 3.12):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker-compose up -d               # Postgres + Redis only
alembic upgrade head
uvicorn linkhop.main:app --reload --port 8080
```
````

ersetzen durch:

````markdown
Backend (needs [uv](https://docs.astral.sh/uv/); Python 3.12 is resolved
via `backend/.python-version`):

```bash
cd backend
uv sync
docker-compose up -d               # Postgres + Redis only
uv run alembic upgrade head
uv run uvicorn linkhop.main:app --reload --port 8080
```
````

- [ ] **Step 4: Root-README Stack-Tabelle**

Die Zeile

```markdown
| Backend     | Python 3.12, FastAPI, SQLAlchemy 2 (async), asyncpg, Alembic  |
```

ersetzen durch:

```markdown
| Backend     | Python 3.12 (uv-managed), FastAPI, SQLAlchemy 2 (async), asyncpg, Alembic |
```

- [ ] **Step 5: Commit**

```bash
git add backend/README.md README.md
git commit -m "docs: switch backend setup instructions to uv"
```

---

### Task 5: Abschluss-Verifikation

**Files:** keine Änderungen — reiner Verifikationslauf.

- [ ] **Step 1: Lock-Konsistenz und Suite**

```bash
cd backend && uv lock --check && uv run pytest -q && uv run ruff check src tests && uv run mypy src
```

Expected: Lock konsistent, `208 passed, 7 skipped`, ruff/mypy clean.

- [ ] **Step 2: Sauberkeitscheck**

```bash
git status --short
```

Expected: keine unbeabsichtigten Änderungen; `backend/uv.lock` ist getrackt (taucht nicht mehr unter `??` auf).

- [ ] **Step 3: CI beobachten**

Nach dem Push (separater Schritt außerhalb dieses Plans) den `backend`-Workflow-Lauf prüfen — `uv sync --locked` muss grün sein.
