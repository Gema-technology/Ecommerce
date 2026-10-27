from sqlalchemy.sql.elements import TextClause

from app.scripts.upgrade_database import MIGRATION_LOCK_KEY, upgrade_head


class _Conn:
    def __init__(self, dialect_name: str, calls: list) -> None:
        self.dialect = type("Dialect", (), {"name": dialect_name})()
        self.calls = calls

    def execute(self, statement, params=None):
        sql = statement.text if isinstance(statement, TextClause) else str(statement)
        self.calls.append(("execute", sql, params))

    def commit(self):
        self.calls.append(("commit",))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Engine:
    def __init__(self, conn: _Conn, calls: list) -> None:
        self.conn = conn
        self.calls = calls

    def connect(self):
        return self.conn

    def dispose(self):
        self.calls.append(("dispose",))


def test_upgrade_head_locks_postgres_then_upgrades(monkeypatch):
    calls: list = []
    conn = _Conn("postgresql", calls)
    engine = _Engine(conn, calls)

    monkeypatch.setattr(
        "app.scripts.upgrade_database.create_engine",
        lambda *args, **kwargs: engine,
    )

    monkeypatch.setattr(
        "app.scripts.upgrade_database.command.upgrade",
        lambda cfg, revision: calls.append(("upgrade", revision)),
    )

    upgrade_head()

    assert ("upgrade", "head") in calls
    lock_sql = [item for item in calls if item[0] == "execute"]
    assert lock_sql[0][1] == "SELECT pg_advisory_lock(:key)"
    assert lock_sql[0][2] == {"key": MIGRATION_LOCK_KEY}
    assert lock_sql[1][1] == "SELECT pg_advisory_unlock(:key)"
    assert calls[-1] == ("dispose",)


def test_upgrade_head_skips_lock_on_sqlite(monkeypatch):
    calls: list = []
    conn = _Conn("sqlite", calls)
    engine = _Engine(conn, calls)
    monkeypatch.setattr(
        "app.scripts.upgrade_database.create_engine",
        lambda *args, **kwargs: engine,
    )
    monkeypatch.setattr(
        "app.scripts.upgrade_database.command.upgrade",
        lambda cfg, revision: calls.append(("upgrade", revision)),
    )

    upgrade_head()

    assert ("upgrade", "head") in calls
    assert not any(item[0] == "execute" for item in calls)
