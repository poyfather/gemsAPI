"""
The local backend: one SQLite file, created and seeded on first use.

sqlite3 is synchronous; calls are short and the app is single-process, so
they run inline under a lock rather than on a thread pool.
"""
from __future__ import annotations
import json
import logging
import pathlib
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from app.models import Gem, GemCreate, Run, RunEvent
from app.storage.seeds import load_seed_gems

logger = logging.getLogger(__name__)
_SCHEMA = pathlib.Path(__file__).with_name("sqlite_schema.sql").read_text()
_JSON_GEM = ("tags", "variables", "tools")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gem(row: sqlite3.Row) -> Gem:
    d = dict(row)
    for k in _JSON_GEM:
        d[k] = json.loads(d[k] or "[]")
    d["is_active"] = bool(d["is_active"])
    return Gem(**d)


def _run(row: sqlite3.Row) -> Run:
    d = dict(row)
    d.pop("state", None)
    return Run(**d)


def _event(row: sqlite3.Row) -> RunEvent:
    d = dict(row)
    d["data"] = json.loads(d["data"] or "{}")
    return RunEvent(seq=d["seq"], type=d["type"], data=d["data"], created_at=d["created_at"])


class SQLiteStore:
    def __init__(self, path: str, seed_sql_file: str | None = None) -> None:
        self.path = path
        if path != ":memory:":
            pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(_SCHEMA)
        self._seed(seed_sql_file)

    def close(self) -> None:
        self._db.close()

    def _seed(self, seed_sql_file: str | None) -> None:
        if self._db.execute("SELECT COUNT(*) FROM gems").fetchone()[0]:
            return
        gems = load_seed_gems(seed_sql_file) if seed_sql_file else []
        if not gems:
            logger.warning("No seed gems loaded (seed file: %s); the library starts empty.", seed_sql_file)
            return
        now = _now()
        with self._lock, self._db:
            for g in gems:
                self._db.execute(
                    "INSERT OR IGNORE INTO gems (id, name, description, system_prompt, model, provider, tags, variables, kind, tools, is_active, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                    (str(uuid.uuid4()), g["name"], g["description"], g["system_prompt"], g["model"], g["provider"],
                     json.dumps(g["tags"]), json.dumps(g["variables"]), g["kind"], json.dumps(g["tools"]), now, now),
                )
        logger.info("Seeded %d gems from %s", len(gems), seed_sql_file)

    # ---- gems
    async def list_gems(self) -> list[Gem]:
        rows = self._db.execute("SELECT * FROM gems WHERE is_active = 1 ORDER BY name").fetchall()
        return [_gem(r) for r in rows]

    async def get_gem_by_name(self, name: str) -> Gem | None:
        row = self._db.execute("SELECT * FROM gems WHERE name = ? AND is_active = 1", (name,)).fetchone()
        return _gem(row) if row else None

    async def get_gem_by_id(self, gem_id: str) -> Gem | None:
        row = self._db.execute("SELECT * FROM gems WHERE id = ?", (gem_id,)).fetchone()
        return _gem(row) if row else None

    async def create_gem(self, data: GemCreate, variables: list[str]) -> Gem:
        gem_id, now = str(uuid.uuid4()), _now()
        d = data.model_dump()
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO gems (id, name, description, system_prompt, model, provider, tags, variables, kind, tools, is_active, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (gem_id, d["name"], d["description"], d["system_prompt"], d["model"], d["provider"],
                 json.dumps(d["tags"]), json.dumps(variables), d["kind"], json.dumps(d["tools"]), now, now),
            )
        return await self.get_gem_by_id(gem_id)

    async def update_gem(self, gem_id: str, updates: dict) -> Gem:
        cols, vals = [], []
        for k, v in updates.items():
            cols.append(f"{k} = ?")
            vals.append(json.dumps(v) if k in _JSON_GEM else v)
        cols.append("updated_at = ?")
        vals.append(_now())
        with self._lock, self._db:
            self._db.execute(f"UPDATE gems SET {', '.join(cols)} WHERE id = ?", (*vals, gem_id))
        return await self.get_gem_by_id(gem_id)

    async def soft_delete_gem(self, gem_id: str) -> None:
        with self._lock, self._db:
            self._db.execute("UPDATE gems SET is_active = 0, updated_at = ? WHERE id = ?", (_now(), gem_id))

    # ---- runs
    async def create_run(self, gem_id, gem_name, model, provider, input_text) -> Run:
        run_id, now = str(uuid.uuid4()), _now()
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO runs (id, gem_id, gem_name, status, model, provider, input, created_at) VALUES (?, ?, ?, 'running', ?, ?, ?, ?)",
                (run_id, gem_id, gem_name, model, provider, input_text, now),
            )
        return _run(self._db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone())

    async def add_event(self, run_id, seq, type_, data) -> RunEvent:
        now = _now()
        with self._lock, self._db:
            self._db.execute("INSERT INTO run_events (id, run_id, seq, type, data, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                             (str(uuid.uuid4()), run_id, seq, type_, json.dumps(data, default=str), now))
        return RunEvent(seq=seq, type=type_, data=data, created_at=now)

    async def update_run(self, run_id, **fields) -> Run:
        if "state" in fields:
            fields["state"] = json.dumps(fields["state"], default=str) if fields["state"] is not None else None
        if fields:
            cols = ", ".join(f"{k} = ?" for k in fields)
            with self._lock, self._db:
                self._db.execute(f"UPDATE runs SET {cols} WHERE id = ?", (*fields.values(), run_id))
        return _run(self._db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone())

    async def get_run(self, run_id):
        row = self._db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        events = self._db.execute("SELECT * FROM run_events WHERE run_id = ? ORDER BY seq", (run_id,)).fetchall()
        return _run(row), [_event(e) for e in events]

    async def get_run_state(self, run_id):
        row = self._db.execute("SELECT state FROM runs WHERE id = ?", (run_id,)).fetchone()
        return json.loads(row["state"]) if row and row["state"] else None
