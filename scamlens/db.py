"""SQLite persistence for ScamLens. Standard library only."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    verdict TEXT NOT NULL,          -- SAFE | SUSPICIOUS | SCAM
    confidence REAL NOT NULL,       -- 0..100
    red_flags TEXT NOT NULL,        -- JSON array of {phrase, category, why}
    trick_en TEXT NOT NULL,         -- plain-English explanation of the trick
    trick_ta TEXT NOT NULL,         -- Tamil explanation of the trick
    checklist TEXT NOT NULL,        -- JSON array of safety checklist strings
    mode TEXT NOT NULL,             -- llm | rules
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def now() -> float:
    return time.time()
