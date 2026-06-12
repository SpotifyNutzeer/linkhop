# Beide Stages teilen exakt dieselbe Python-Basis (Tag inkl. Debian-Release
# gepinnt) — der Interpreter-Symlink im kopierten venv zeigt damit garantiert
# auf denselben Stand. uv kommt als Binary aus dem distroless uv-Image
# (Minor gepinnt, passend zum lokal genutzten uv 0.11).
FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/
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

FROM python:3.12-slim-bookworm
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
