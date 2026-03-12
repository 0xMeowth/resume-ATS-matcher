from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "ats_matcher.db"


def get_db_path() -> Path:
    env = os.environ.get("ATS_DB_PATH")
    return Path(env) if env else _DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    """Return a sqlite3 connection with foreign keys, WAL mode, and sqlite-vec loaded."""
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    _load_vec(conn)
    return conn


def _load_vec(conn: sqlite3.Connection) -> None:
    try:
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception:
        pass  # vec search unavailable; Phase 4 will surface this if needed
