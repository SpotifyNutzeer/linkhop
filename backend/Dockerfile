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
# Wheel bringt uvicorn[standard] und asyncpg per pyproject.toml-Pins (0.44.*/0.31.*)
# transitiv mit — extra Pins hier wären entweder redundant oder würden pip
# in einen Resolve-Konflikt zwingen, sobald pyproject-Pin und Dockerfile-Pin
# auseinanderdriften (was historisch schon passiert ist).
RUN pip install --no-cache-dir /wheels/*.whl
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
USER linkhop
EXPOSE 8080
CMD ["uvicorn", "linkhop.main:app", "--host", "0.0.0.0", "--port", "8080", \
     "--proxy-headers", "--forwarded-allow-ips=127.0.0.1"]
