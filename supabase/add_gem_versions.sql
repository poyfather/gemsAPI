-- Run this in your Supabase SQL editor on an existing Lapidary installation to keep
-- a version history of every gem (roadmap item 14; also in schema.sql). Safe to rerun.
-- Gems saved before this table existed get their first version the next time they change.

-- ============================================================
-- VERSION HISTORY (roadmap item 14)
-- One row per save of a gem: its fields as JSON, a note and where
-- the change came from. Written by the app on every create and
-- change, so SQLite and Supabase keep the same history.
-- ============================================================
CREATE TABLE IF NOT EXISTS gem_versions (
  id         UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
  gem_id     UUID        NOT NULL REFERENCES gems (id),
  version    INTEGER     NOT NULL,
  snapshot   JSONB       NOT NULL,
  note       TEXT        NOT NULL DEFAULT '',
  source     TEXT        NOT NULL DEFAULT 'api',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (gem_id, version)
);
ALTER TABLE gem_versions ENABLE ROW LEVEL SECURITY;
