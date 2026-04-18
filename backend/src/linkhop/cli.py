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
