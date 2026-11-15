"""Tiny DB layer: sqlite3 (default) or Postgres (psycopg) with the same portable SQL.

SQL is written with `?` placeholders; for Postgres they are converted to `%s`.
All ids are TEXT and all times are epoch milliseconds (BIGINT) so one schema fits both.
"""
import sqlite3
import threading
from typing import Any, Iterable, List, Optional

MIGRATIONS: List[str] = [
    # 1: users
    """CREATE TABLE users (
        id TEXT PRIMARY KEY,
        google_sub TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        display_name TEXT NOT NULL,
        picture TEXT,
        default_lang TEXT NOT NULL DEFAULT 'en',
        mic_default INTEGER NOT NULL DEFAULT 1,
        cam_default INTEGER NOT NULL DEFAULT 1,
        subtitles_only INTEGER NOT NULL DEFAULT 0,
        theme TEXT NOT NULL DEFAULT 'system',
        created_at BIGINT NOT NULL
    )""",
    # 2: meetings
    """CREATE TABLE meetings (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        host_id TEXT NOT NULL,
        created_at BIGINT NOT NULL,
        ended_at BIGINT
    )""",
    # 3: participations
    """CREATE TABLE participations (
        id TEXT PRIMARY KEY,
        meeting_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        participant_id TEXT NOT NULL,
        role TEXT NOT NULL,
        joined_at BIGINT NOT NULL,
        left_at BIGINT
    )""",
    "CREATE INDEX idx_part_user ON participations(user_id, joined_at)",
    "CREATE INDEX idx_part_meeting ON participations(meeting_id)",
    "CREATE INDEX idx_part_pid ON participations(participant_id)",
    # 4: history hidden
    """CREATE TABLE history_hidden (
        user_id TEXT NOT NULL,
        meeting_id TEXT NOT NULL,
        PRIMARY KEY (user_id, meeting_id)
    )""",
    # 5: friends
    """CREATE TABLE friendships (
        user_a TEXT NOT NULL,
        user_b TEXT NOT NULL,
        created_at BIGINT NOT NULL,
        PRIMARY KEY (user_a, user_b)
    )""",
    """CREATE TABLE friend_requests (
        id TEXT PRIMARY KEY,
        from_id TEXT NOT NULL,
        to_id TEXT NOT NULL,
        created_at BIGINT NOT NULL
    )""",
    # 6: invites
    """CREATE TABLE invites (
        id TEXT PRIMARY KEY,
        meeting_id TEXT NOT NULL,
        from_id TEXT NOT NULL,
        to_id TEXT NOT NULL,
        created_at BIGINT NOT NULL
    )""",
]


class IntegrityError(Exception):
    pass


class Database:
    def __init__(self, url: str):
        self.url = url
        self.lock = threading.RLock()
        if url.startswith("sqlite"):
            self.kind = "sqlite"
            path = url.split("sqlite:///", 1)[1] if "sqlite:///" in url else ":memory:"
            self.conn = sqlite3.connect(path or ":memory:", check_same_thread=False, isolation_level=None)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self._ph = "?"
        elif url.startswith("postgres"):
            import psycopg  # type: ignore
            from psycopg.rows import dict_row  # type: ignore
            self.kind = "postgres"
            self._connect_pg = lambda: psycopg.connect(url, autocommit=True, row_factory=dict_row)
            self.conn = self._connect_pg()
            self._ph = "%s"
        else:
            raise ValueError("DATABASE_URL must start with sqlite:/// or postgresql://")

    def _sql(self, sql: str) -> str:
        return sql if self._ph == "?" else sql.replace("?", "%s")

    def _exec(self, sql: str, params):
        """Run one statement; on a dropped Postgres connection reconnect once and retry."""
        try:
            return self.conn.execute(self._sql(sql), tuple(params))
        except Exception as e:
            if self.kind == "postgres" and e.__class__.__name__ in ("OperationalError", "InterfaceError"):
                self.conn = self._connect_pg()
                return self.conn.execute(self._sql(sql), tuple(params))
            raise

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self.lock:
            try:
                cur = self._exec(sql, params)
                return cur.rowcount
            except Exception as e:
                if "UNIQUE" in str(e).upper() or "unique" in str(e) or "duplicate key" in str(e):
                    raise IntegrityError(str(e)) from e
                raise

    def all(self, sql: str, params: Iterable[Any] = ()) -> List[dict]:
        with self.lock:
            cur = self._exec(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def one(self, sql: str, params: Iterable[Any] = ()) -> Optional[dict]:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def migrate(self):
        with self.lock:
            self.conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")
            done = {r["version"] for r in self.all("SELECT version FROM schema_migrations")}
            for i, stmt in enumerate(MIGRATIONS, start=1):
                if i in done:
                    continue
                self.conn.execute(stmt)
                self.execute("INSERT INTO schema_migrations(version) VALUES (?)", (i,))

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
