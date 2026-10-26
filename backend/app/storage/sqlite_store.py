"""
The local backend: one SQLite file, created and seeded on first use.

sqlite3 is synchronous; calls are short and the app is single-process, so
they run inline under a lock rather than on a thread pool.
"""
from __future__ import annotations
import json
import logging
import re
import pathlib
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

from app.models import EvalCase, EvalCaseCreate, EvalRun, Gem, GemCreate, GemVersion, Memory, MemoryCreate, Pipeline, PipelineCreate, PipelineRun, Run, RunEvent
from app.storage.seeds import load_seed_gems, load_seed_pipelines

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
    d["memory"] = bool(d.get("memory", 0))
    d["variable_specs"] = json.loads(d.get("variable_specs") or "{}")
    return Gem(**d)


def _run(row: sqlite3.Row) -> Run:
    d = dict(row)
    d.pop("state", None)
    return Run(**d)


def _memory(row: sqlite3.Row) -> Memory:
    d = dict(row)
    d.pop("rank", None)
    d["tags"] = json.loads(d["tags"] or "[]")
    return Memory(**d)


def _fts_query(query: str) -> str:
    """Any word of the query may match (OR), each quoted so FTS syntax in user text cannot break the search."""
    words = [w for w in re.findall(r"[\w'-]+", query.lower()) if len(w) > 1 and w not in _STOPWORDS]
    return " OR ".join(f'"{w}"' for w in dict.fromkeys(words))


_STOPWORDS = {"the", "and", "for", "with", "that", "this", "from", "what", "how", "was", "are", "did", "you", "about", "into", "when", "where", "which", "have", "has", "can", "not", "but", "all", "any", "our", "your", "its", "will", "should", "could", "would", "does", "them", "then", "than", "also", "just", "more", "some", "one", "two"}


def _pipeline(row: sqlite3.Row) -> Pipeline:
    d = dict(row)
    d["gates"] = json.loads(d["gates"] or "[]")
    d["acceptance"] = bool(d["acceptance"])
    return Pipeline(**d)


def _pipeline_run(row: sqlite3.Row) -> PipelineRun:
    d = dict(row)
    d.pop("state", None)
    d["attempts"] = json.loads(d["attempts"] or "[]")
    return PipelineRun(**d)


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
        self._migrate()
        self._seed(seed_sql_file)

    def close(self) -> None:
        self._db.close()

    def _migrate(self) -> None:
        """Columns added after a database was created (CREATE TABLE IF NOT EXISTS does not add them)."""
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(gems)").fetchall()}
        if "memory" not in cols:
            with self._lock, self._db:
                self._db.execute("ALTER TABLE gems ADD COLUMN memory INTEGER NOT NULL DEFAULT 0")
        if "variable_specs" not in cols:
            with self._lock, self._db:
                self._db.execute("ALTER TABLE gems ADD COLUMN variable_specs TEXT NOT NULL DEFAULT '{}'")

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
        self._seed_pipelines(seed_sql_file)

    def _seed_pipelines(self, seed_sql_file: str | None) -> None:
        if self._db.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0] or not seed_sql_file:
            return
        now = _now()
        with self._lock, self._db:
            for p in load_seed_pipelines(seed_sql_file):
                self._db.execute(
                    "INSERT OR IGNORE INTO pipelines (id, name, description, builder, gates, max_attempts, acceptance, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), p["name"], p.get("description", ""), p["builder"], json.dumps(p.get("gates", [])), int(p.get("max_attempts", 3)), int(bool(p.get("acceptance", True))), now, now),
                )

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
                "INSERT INTO gems (id, name, description, system_prompt, model, provider, tags, variables, kind, tools, memory, variable_specs, is_active, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (gem_id, d["name"], d["description"], d["system_prompt"], d["model"], d["provider"],
                 json.dumps(d["tags"]), json.dumps(variables), d["kind"], json.dumps(d["tools"]), int(bool(d.get("memory"))),
                 json.dumps(d.get("variable_specs") or {}), now, now),
            )
        return await self.get_gem_by_id(gem_id)

    async def update_gem(self, gem_id: str, updates: dict) -> Gem:
        cols, vals = [], []
        for k, v in updates.items():
            cols.append(f"{k} = ?")
            vals.append(json.dumps(v) if k in _JSON_GEM or k == "variable_specs" else (int(v) if k == "memory" else v))
        cols.append("updated_at = ?")
        vals.append(_now())
        with self._lock, self._db:
            self._db.execute(f"UPDATE gems SET {', '.join(cols)} WHERE id = ?", (*vals, gem_id))
        return await self.get_gem_by_id(gem_id)

    async def soft_delete_gem(self, gem_id: str) -> None:
        with self._lock, self._db:
            self._db.execute("UPDATE gems SET is_active = 0, updated_at = ? WHERE id = ?", (_now(), gem_id))

    # ---- gem versions (roadmap 14)
    async def add_gem_version(self, gem_id, version, snapshot, note, source) -> GemVersion:
        now = _now()
        with self._lock, self._db:
            self._db.execute("INSERT INTO gem_versions (id, gem_id, version, snapshot, note, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (str(uuid.uuid4()), gem_id, version, json.dumps(snapshot), note or "", source, now))
        return GemVersion(gem_id=gem_id, version=version, snapshot=snapshot, note=note or "", source=source, created_at=now)

    async def list_gem_versions(self, gem_id) -> list[GemVersion]:
        rows = self._db.execute("SELECT * FROM gem_versions WHERE gem_id = ? ORDER BY version", (gem_id,)).fetchall()
        return [GemVersion(gem_id=r["gem_id"], version=r["version"], snapshot=json.loads(r["snapshot"]), note=r["note"], source=r["source"], created_at=r["created_at"]) for r in rows]

    # ---- evals (roadmap 28)
    @staticmethod
    def _case(r: sqlite3.Row) -> EvalCase:
        d = dict(r)
        d["variables"] = json.loads(d["variables"] or "{}")
        return EvalCase(**d)

    @staticmethod
    def _eval_run(r: sqlite3.Row) -> EvalRun:
        d = dict(r)
        d["results"] = json.loads(d["results"] or "[]")
        d["baseline"] = bool(d["baseline"])
        return EvalRun(**d)

    async def list_eval_cases(self, gem_id) -> list[EvalCase]:
        return [self._case(r) for r in self._db.execute("SELECT * FROM eval_cases WHERE gem_id = ? ORDER BY created_at, rowid", (gem_id,)).fetchall()]

    async def add_eval_case(self, gem_id, data: EvalCaseCreate) -> EvalCase:
        cid, now = str(uuid.uuid4()), _now()
        d = data.model_dump()
        with self._lock, self._db:
            self._db.execute('INSERT INTO eval_cases (id, gem_id, name, input, variables, "check", expected, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                             (cid, gem_id, d["name"], d["input"], json.dumps(d["variables"]), d["check"], d["expected"], now))
        return self._case(self._db.execute("SELECT * FROM eval_cases WHERE id = ?", (cid,)).fetchone())

    async def update_eval_case(self, case_id, updates) -> EvalCase | None:
        if updates:
            cols = ", ".join(f'"{k}" = ?' for k in updates)
            vals = [json.dumps(v) if k == "variables" else v for k, v in updates.items()]
            with self._lock, self._db:
                self._db.execute(f"UPDATE eval_cases SET {cols} WHERE id = ?", (*vals, case_id))
        row = self._db.execute("SELECT * FROM eval_cases WHERE id = ?", (case_id,)).fetchone()
        return self._case(row) if row else None

    async def delete_eval_case(self, case_id) -> bool:
        with self._lock, self._db:
            cur = self._db.execute("DELETE FROM eval_cases WHERE id = ?", (case_id,))
        return cur.rowcount > 0

    async def add_eval_run(self, run: EvalRun) -> EvalRun:
        d = run.model_dump(mode="json")
        with self._lock, self._db:
            self._db.execute("INSERT INTO eval_runs (id, gem_id, gem_version, provider, model, passed, total, results, baseline, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             (d["id"], d["gem_id"], d["gem_version"], d["provider"], d["model"], d["passed"], d["total"], json.dumps(d["results"]), int(d["baseline"]), d["created_at"]))
        return run

    async def list_eval_runs(self, gem_id, limit=50) -> list[EvalRun]:
        rows = self._db.execute("SELECT * FROM eval_runs WHERE gem_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?", (gem_id, limit)).fetchall()
        return [self._eval_run(r) for r in rows]

    async def set_eval_baseline(self, gem_id, run_id) -> EvalRun | None:
        if not self._db.execute("SELECT 1 FROM eval_runs WHERE id = ? AND gem_id = ?", (run_id, gem_id)).fetchone():
            return None
        with self._lock, self._db:
            self._db.execute("UPDATE eval_runs SET baseline = (id = ?) WHERE gem_id = ?", (run_id, gem_id))
        return self._eval_run(self._db.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,)).fetchone())

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

    # ---- memory (ADR-010)
    async def add_memory(self, data: MemoryCreate) -> Memory:
        mem_id, now = str(uuid.uuid4()), _now()
        d = data.model_dump()
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO memories (id, kind, text, source, gem_name, run_id, tags, scope, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (mem_id, d["kind"], d["text"], d["source"], d["gem_name"], d["run_id"], json.dumps(d["tags"]), d["scope"], now),
            )
        return _memory(self._db.execute("SELECT * FROM memories WHERE id = ?", (mem_id,)).fetchone())

    async def search_memories(self, query: str, *, scope: str | None = None, kinds: list[str] | None = None, limit: int = 20) -> list[Memory]:
        where, params = [], []
        if scope:
            where.append("m.scope = ?")
            params.append(scope)
        if kinds:
            where.append(f"m.kind IN ({', '.join('?' for _ in kinds)})")
            params.extend(kinds)
        match = _fts_query(query or "")
        if match:
            sql = (
                "SELECT m.*, bm25(memories_fts) AS rank FROM memories_fts f JOIN memories m ON m.rowid = f.rowid "
                f"WHERE memories_fts MATCH ? {'AND ' + ' AND '.join(where) if where else ''} ORDER BY rank, m.created_at DESC LIMIT ?"
            )
            rows = self._db.execute(sql, (match, *params, limit)).fetchall()
        else:
            sql = f"SELECT m.* FROM memories m {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY m.created_at DESC LIMIT ?"
            rows = self._db.execute(sql, (*params, limit)).fetchall()
        return [_memory(r) for r in rows]

    async def get_memories(self, ids: list[str]) -> list[Memory]:
        if not ids:
            return []
        rows = self._db.execute(f"SELECT * FROM memories WHERE id IN ({', '.join('?' for _ in ids)})", ids).fetchall()
        by_id = {r["id"]: _memory(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    async def delete_memory(self, memory_id: str) -> bool:
        with self._lock, self._db:
            cur = self._db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return cur.rowcount > 0

    # ---- pipelines (ADR-011)
    async def list_pipelines(self) -> list[Pipeline]:
        return [_pipeline(r) for r in self._db.execute("SELECT * FROM pipelines ORDER BY name").fetchall()]

    async def get_pipeline(self, name: str) -> Pipeline | None:
        row = self._db.execute("SELECT * FROM pipelines WHERE name = ?", (name,)).fetchone()
        return _pipeline(row) if row else None

    async def create_pipeline(self, data: PipelineCreate) -> Pipeline:
        pid, now = str(uuid.uuid4()), _now()
        d = data.model_dump()
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO pipelines (id, name, description, builder, gates, max_attempts, acceptance, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (pid, d["name"], d["description"], d["builder"], json.dumps(d["gates"]), d["max_attempts"], int(d["acceptance"]), now, now),
            )
        return await self.get_pipeline(d["name"])

    async def update_pipeline(self, name: str, updates: dict) -> Pipeline:
        cols, vals = [], []
        for k, v in updates.items():
            cols.append(f"{k} = ?")
            vals.append(json.dumps(v) if k == "gates" else (int(v) if k == "acceptance" else v))
        cols.append("updated_at = ?")
        vals.append(_now())
        with self._lock, self._db:
            self._db.execute(f"UPDATE pipelines SET {', '.join(cols)} WHERE name = ?", (*vals, name))
        return await self.get_pipeline(name)

    async def delete_pipeline(self, name: str) -> bool:
        with self._lock, self._db:
            cur = self._db.execute("DELETE FROM pipelines WHERE name = ?", (name,))
        return cur.rowcount > 0

    async def create_pipeline_run(self, pipeline_name: str, input_text: str) -> PipelineRun:
        rid, now = str(uuid.uuid4()), _now()
        with self._lock, self._db:
            self._db.execute("INSERT INTO pipeline_runs (id, pipeline_name, status, input, created_at) VALUES (?, ?, 'running', ?, ?)", (rid, pipeline_name, input_text, now))
        return await self.get_pipeline_run(rid)

    async def update_pipeline_run(self, run_id: str, **fields) -> PipelineRun:
        for k in ("attempts", "state"):
            if k in fields and fields[k] is not None:
                fields[k] = json.dumps(fields[k], default=str)
        if fields:
            cols = ", ".join(f"{k} = ?" for k in fields)
            with self._lock, self._db:
                self._db.execute(f"UPDATE pipeline_runs SET {cols} WHERE id = ?", (*fields.values(), run_id))
        return await self.get_pipeline_run(run_id)

    async def get_pipeline_run(self, run_id: str) -> PipelineRun | None:
        row = self._db.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        return _pipeline_run(row) if row else None

    async def get_pipeline_run_state(self, run_id: str) -> dict | None:
        row = self._db.execute("SELECT state FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
        return json.loads(row["state"]) if row and row["state"] else None
