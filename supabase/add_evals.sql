-- Run this in your Supabase SQL editor on an existing Lapidary installation to add
-- evals per gem (roadmap item 28; also in schema.sql). Safe to rerun.

-- ============================================================
-- EVALS PER GEM (roadmap item 28)
-- Test cases for a gem, and the scored runs against them, each
-- recorded with the gem's version so a regression is visible.
-- ============================================================
CREATE TABLE IF NOT EXISTS eval_cases (
  id         UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
  gem_id     UUID        NOT NULL REFERENCES gems (id),
  name       TEXT        NOT NULL DEFAULT '',
  input      TEXT        NOT NULL,
  variables  JSONB       NOT NULL DEFAULT '{}',
  "check"    TEXT        NOT NULL DEFAULT 'contains'
                         CHECK ("check" IN ('contains', 'not_contains', 'all_of', 'equals', 'json', 'judge')),
  expected   TEXT        NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS eval_cases_gem_idx ON eval_cases (gem_id);
CREATE TABLE IF NOT EXISTS eval_runs (
  id          UUID        PRIMARY KEY,
  gem_id      UUID        NOT NULL REFERENCES gems (id),
  gem_version INTEGER     NOT NULL,
  provider    TEXT        NOT NULL,
  model       TEXT        NOT NULL,
  passed      INTEGER     NOT NULL,
  total       INTEGER     NOT NULL,
  results     JSONB       NOT NULL DEFAULT '[]',
  baseline    BOOLEAN     NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS eval_runs_gem_idx ON eval_runs (gem_id, created_at DESC);
ALTER TABLE eval_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE eval_runs ENABLE ROW LEVEL SECURITY;
