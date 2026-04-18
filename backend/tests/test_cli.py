import re

from click.testing import CliRunner

from linkhop.cli import cli


def test_key_create_prints_plain(tmp_path, monkeypatch):
    db_path = tmp_path / "db.sqlite"
    # Async-DSN-Form setzen — alle CLI-Commands nutzen create_async_engine.
    monkeypatch.setenv("LINKHOP_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    runner = CliRunner()
    # First: init (creates tables)
    r = runner.invoke(cli, ["init-db"])
    assert r.exit_code == 0, r.output

    # Then: key create
    r = runner.invoke(cli, ["key", "create", "--note", "paul"])
    assert r.exit_code == 0
    assert re.search(r"lhk_[A-Za-z0-9]+", r.output)


def test_key_list_and_revoke(tmp_path, monkeypatch):
    db_path = tmp_path / "db.sqlite"
    monkeypatch.setenv("LINKHOP_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    runner = CliRunner()
    # exit_code vor dem Weiterarbeiten prüfen — sonst würde ein stummer
    # Fehler (z.B. DB-Schema fehlt) erst an der Regex-Zeile mit "assert m"
    # ohne Kontext abbrechen.
    assert runner.invoke(cli, ["init-db"]).exit_code == 0
    created = runner.invoke(cli, ["key", "create", "--note", "a"])
    assert created.exit_code == 0, created.output
    # extract id from output (format: "id=<uuid> ...")
    m = re.search(r"id=([a-f0-9-]+)", created.output)
    assert m
    key_id = m.group(1)

    listed = runner.invoke(cli, ["key", "list"])
    assert key_id in listed.output

    revoked = runner.invoke(cli, ["key", "revoke", key_id])
    assert revoked.exit_code == 0

    listed2 = runner.invoke(cli, ["key", "list"])
    assert "revoked" in listed2.output.lower()


def test_revoke_unknown_id_fails_loudly(tmp_path, monkeypatch):
    # Ohne diesen Test läuft ein blindes UPDATE auf eine unbekannte UUID
    # lautlos als "revoked: …" durch — der Operator glaubt, ein Key sei
    # abgeschaltet, obwohl nichts passiert ist.
    db_path = tmp_path / "db.sqlite"
    monkeypatch.setenv("LINKHOP_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    runner = CliRunner()
    assert runner.invoke(cli, ["init-db"]).exit_code == 0

    result = runner.invoke(cli, ["key", "revoke", "00000000-0000-0000-0000-000000000000"])
    assert result.exit_code == 1
    assert "no such key" in (result.output + (result.stderr or "")).lower()
