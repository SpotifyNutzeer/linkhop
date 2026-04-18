from __future__ import annotations

import asyncio

import click
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from linkhop.api_keys import ApiKeyService
from linkhop.config import Settings
from linkhop.models.db import Base


@click.group()
def cli() -> None:
    """linkhop-admin — verwalte linkhop-Instanz."""


@cli.command("init-db")
def init_db() -> None:
    # Async-Pfad via run_sync(create_all), damit wir keinen zusätzlichen
    # Sync-Treiber (psycopg2) als Dependency brauchen — die DSN ist bereits
    # in asyncpg/aiosqlite-Form, und Base.metadata.create_all akzeptiert die
    # Sync-API auf einer Sync-Connection, die run_sync liefert.
    async def _run() -> None:
        settings = Settings()
        engine = create_async_engine(settings.database_url)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await engine.dispose()
    asyncio.run(_run())
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
    async def _run() -> int:
        engine, factory = _make_async_session_factory()
        try:
            async with factory() as session:
                return await ApiKeyService(session).revoke(key_id)
        finally:
            await engine.dispose()
    hit = asyncio.run(_run())
    if hit == 0:
        click.echo(f"no such key: {key_id}", err=True)
        raise click.exceptions.Exit(code=1)
    click.echo(f"revoked: {key_id}")


def main() -> None:
    cli()
