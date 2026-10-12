import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def data_dir() -> Path:
    path = Path(os.environ.get("ASAY_DATA_DIR", ".data")).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "asay.sqlite3"


@contextmanager
def connect():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES cases(id),
            source_kind TEXT NOT NULL DEFAULT 'web',
            source_url TEXT NOT NULL DEFAULT '',
            platform TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            author TEXT NOT NULL DEFAULT '',
            posted_at TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            captured_at TEXT NOT NULL,
            capture_status TEXT NOT NULL DEFAULT 'ok',
            sha256 TEXT NOT NULL,
            raw_html_file TEXT NOT NULL DEFAULT '',
            screenshot_file TEXT NOT NULL DEFAULT '',
            attachment_sha256 TEXT NOT NULL DEFAULT '',
            html_sha256 TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            warning TEXT NOT NULL DEFAULT '',
            parent_id INTEGER,
            FOREIGN KEY (parent_id) REFERENCES evidence(id)
        );
        CREATE INDEX IF NOT EXISTS evidence_by_case ON evidence(case_id, captured_at DESC);
        """)


def rows(statement, params=()):
    with connect() as con:
        return con.execute(statement, params).fetchall()


def row(statement, params=()):
    with connect() as con:
        return con.execute(statement, params).fetchone()


def execute(statement, params=()):
    with connect() as con:
        cursor = con.execute(statement, params)
        return cursor.lastrowid
