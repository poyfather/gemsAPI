-- Lapidary on SQLite. Same shape as supabase/schema.sql; lists and JSON are TEXT.
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS gems (
  id            TEXT PRIMARY KEY,
  name          TEXT UNIQUE NOT NULL,
  description   TEXT NOT NULL DEFAULT '',
  system_prompt TEXT NOT NULL DEFAULT '',
  model         TEXT NOT NULL,
  provider      TEXT NOT NULL CHECK (provider IN ('anthropic', 'openai', 'local', 'auto')),
  tags          TEXT NOT NULL DEFAULT '[]',
  variables     TEXT NOT NULL DEFAULT '[]',
  kind          TEXT NOT NULL DEFAULT 'prompt' CHECK (kind IN ('prompt', 'agent')),
  tools         TEXT NOT NULL DEFAULT '[]',
  memory        INTEGER NOT NULL DEFAULT 0,
  is_active     INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS gems_active_idx ON gems (is_active);

CREATE TABLE IF NOT EXISTS runs (
  id            TEXT PRIMARY KEY,
  gem_id        TEXT,
  gem_name      TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'waiting_approval', 'finished', 'failed', 'max_steps')),
  model         TEXT NOT NULL,
  provider      TEXT NOT NULL,
  input         TEXT NOT NULL,
  output        TEXT,
  steps         INTEGER NOT NULL DEFAULT 0,
  input_tokens  INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  error         TEXT,
  state         TEXT,
  created_at    TEXT NOT NULL,
  finished_at   TEXT
);
CREATE INDEX IF NOT EXISTS runs_gem_name_idx ON runs (gem_name);
CREATE INDEX IF NOT EXISTS runs_created_at_idx ON runs (created_at DESC);

CREATE TABLE IF NOT EXISTS run_events (
  id         TEXT PRIMARY KEY,
  run_id     TEXT NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
  seq        INTEGER NOT NULL,
  type       TEXT NOT NULL,
  data       TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  UNIQUE (run_id, seq)
);

-- Lapidary Memory (ADR-010): observations and notes with full-text search.
CREATE TABLE IF NOT EXISTS memories (
  id         TEXT PRIMARY KEY,
  kind       TEXT NOT NULL DEFAULT 'note' CHECK (kind IN ('observation', 'summary', 'decision', 'preference', 'lesson', 'handoff', 'note')),
  text       TEXT NOT NULL,
  source     TEXT NOT NULL DEFAULT 'user' CHECK (source IN ('run', 'chat', 'mcp', 'console', 'user')),
  gem_name   TEXT,
  run_id     TEXT,
  tags       TEXT NOT NULL DEFAULT '[]',
  scope      TEXT NOT NULL DEFAULT 'default',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS memories_scope_idx ON memories (scope, created_at DESC);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5 (text, tags, content='memories', content_rowid='rowid');
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts (rowid, text, tags) VALUES (new.rowid, new.text, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts (memories_fts, rowid, text, tags) VALUES ('delete', old.rowid, old.text, old.tags);
END;

-- Pipelines and gates (ADR-011): a builder gem, then gate gems that pass or fail its output.
CREATE TABLE IF NOT EXISTS pipelines (
  id           TEXT PRIMARY KEY,
  name         TEXT UNIQUE NOT NULL,
  description  TEXT NOT NULL DEFAULT '',
  builder      TEXT NOT NULL,
  gates        TEXT NOT NULL DEFAULT '[]',
  max_attempts INTEGER NOT NULL DEFAULT 3,
  acceptance   INTEGER NOT NULL DEFAULT 1,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pipeline_runs (
  id             TEXT PRIMARY KEY,
  pipeline_name  TEXT NOT NULL,
  status         TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'waiting_approval', 'waiting_acceptance', 'passed', 'failed', 'max_attempts')),
  input          TEXT NOT NULL,
  output         TEXT,
  attempts       TEXT NOT NULL DEFAULT '[]',
  state          TEXT,
  waiting_run_id TEXT,
  error          TEXT,
  created_at     TEXT NOT NULL,
  finished_at    TEXT
);
CREATE INDEX IF NOT EXISTS pipeline_runs_created_at_idx ON pipeline_runs (created_at DESC);

-- Version history (roadmap 14): one row per save, the gem's fields as JSON.
CREATE TABLE IF NOT EXISTS gem_versions (
  id         TEXT PRIMARY KEY,
  gem_id     TEXT NOT NULL,
  version    INTEGER NOT NULL,
  snapshot   TEXT NOT NULL,
  note       TEXT NOT NULL DEFAULT '',
  source     TEXT NOT NULL DEFAULT 'api',
  created_at TEXT NOT NULL,
  UNIQUE (gem_id, version)
);

-- Evals per gem (roadmap 28): test cases, and the scored runs against them.
CREATE TABLE IF NOT EXISTS eval_cases (
  id         TEXT PRIMARY KEY,
  gem_id     TEXT NOT NULL,
  name       TEXT NOT NULL DEFAULT '',
  input      TEXT NOT NULL,
  variables  TEXT NOT NULL DEFAULT '{}',
  "check"    TEXT NOT NULL DEFAULT 'contains' CHECK ("check" IN ('contains', 'not_contains', 'all_of', 'equals', 'json', 'judge')),
  expected   TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS eval_cases_gem_idx ON eval_cases (gem_id);
CREATE TABLE IF NOT EXISTS eval_runs (
  id          TEXT PRIMARY KEY,
  gem_id      TEXT NOT NULL,
  gem_version INTEGER NOT NULL,
  provider    TEXT NOT NULL,
  model       TEXT NOT NULL,
  passed      INTEGER NOT NULL,
  total       INTEGER NOT NULL,
  results     TEXT NOT NULL DEFAULT '[]',
  baseline    INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS eval_runs_gem_idx ON eval_runs (gem_id, created_at DESC);
