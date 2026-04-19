FROM python:3.12-slim AS build
WORKDIR /app
RUN pip install --no-cache-dir hatchling
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --no-deps --wheel-dir /wheels .

FROM python:3.12-slim
# Python-Runtime-Flags: ohne PYTHONUNBUFFERED sitzen stdout-Lines in Buffern,
# wenn stdout eine Pipe ist (immer unter Docker) — bei Crash verliert man die
# letzten JSON-Log-Records. PYTHONDONTWRITEBYTECODE spart Schreibzugriffe im
# Nur-Lese-Container-Layout.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LINKHOP_FORWARDED_ALLOW_IPS=127.0.0.1
RUN useradd -u 10001 -m linkhop
WORKDIR /app
COPY --from=build /wheels /wheels
# Wheel bringt uvicorn[standard] und asyncpg per pyproject.toml-Pins (0.44.*/0.31.*)
# transitiv mit — extra Pins hier wären entweder redundant oder würden pip
# in einen Resolve-Konflikt zwingen, sobald pyproject-Pin und Dockerfile-Pin
# auseinanderdriften (was historisch schon passiert ist).
RUN pip install --no-cache-dir /wheels/*.whl
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
