from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS control_documents (
  id TEXT PRIMARY KEY,
  version TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS trials (
  id TEXT PRIMARY KEY,
  loop_id TEXT NOT NULL,
  control_document_id TEXT NOT NULL,
  payload TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS loops (
  id TEXT PRIMARY KEY,
  control_document_id TEXT NOT NULL,
  workspace_path TEXT NOT NULL,
  best_commit TEXT,
  best_metric REAL,
  status TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS commit_nodes (
  hash TEXT PRIMARY KEY,
  parents TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  payload TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS board_posts (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  commit_hash TEXT,
  body TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS graph_nodes (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  label TEXT,
  payload TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS graph_edges (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  source TEXT NOT NULL,
  target TEXT NOT NULL,
  payload TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS resolution_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  op TEXT NOT NULL,
  from_id TEXT NOT NULL,
  to_id TEXT NOT NULL,
  evidence TEXT,
  reversed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS evaluations (
  id TEXT PRIMARY KEY,
  payload TEXT NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS budgets (
  id TEXT PRIMARY KEY,
  payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  control_document_id TEXT NOT NULL,
  budget_id TEXT NOT NULL,
  status TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT,
  kind TEXT NOT NULL,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_keys (
  key TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        cur = self._conn.execute(sql, tuple(params))
        self._conn.commit()
        return cur

    def fetchone(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self._conn.execute(sql, tuple(params)).fetchone()

    def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return list(self._conn.execute(sql, tuple(params)).fetchall())

    @staticmethod
    def dumps(obj: Any) -> str:
        return json.dumps(obj, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def loads(s: str) -> Any:
        return json.loads(s)
