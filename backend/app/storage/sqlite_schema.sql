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
