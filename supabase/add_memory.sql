-- Run this in your Supabase SQL editor on an existing Lapidary installation to add
-- Lapidary Memory (ADR-010): the memories table, the gem memory flag and the
-- memory_summarizer gem (all also in schema.sql). Safe to rerun.

ALTER TABLE gems ADD COLUMN IF NOT EXISTS memory BOOLEAN NOT NULL DEFAULT false;

-- ============================================================
-- LAPIDARY MEMORY (see DECISIONS.md, ADR-010)
-- Observations captured from runs, and notes, decisions, preferences,
-- lessons and handoffs written by people and clients. Full-text search
-- over the text and tags; scope keeps projects apart.
-- ============================================================
CREATE TABLE IF NOT EXISTS memories (
  id         UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
  kind       TEXT        NOT NULL DEFAULT 'note'
                         CHECK (kind IN ('observation', 'summary', 'decision', 'preference', 'lesson', 'handoff', 'note')),
  text       TEXT        NOT NULL,
  source     TEXT        NOT NULL DEFAULT 'user'
                         CHECK (source IN ('run', 'chat', 'mcp', 'console', 'user')),
  gem_name   TEXT,
  run_id     UUID,
  tags       TEXT[]      NOT NULL DEFAULT '{}',
  scope      TEXT        NOT NULL DEFAULT 'default',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  search     TSVECTOR    GENERATED ALWAYS AS (to_tsvector('english', text || ' ' || array_to_string(tags, ' '))) STORED
);
CREATE INDEX IF NOT EXISTS memories_scope_idx  ON memories (scope, created_at DESC);
CREATE INDEX IF NOT EXISTS memories_search_idx ON memories USING GIN (search);
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;

INSERT INTO gems (name, description, system_prompt, model, provider, tags, variables, kind, tools) VALUES
-- The gem that writes memory observations when a run finishes (ADR-010). Provider auto; volume work, so a mix keeps it local.
(
  'memory_summarizer',
  'Writes a two or three sentence observation of a finished run for Lapidary Memory.',
  'You write the memory of an assistant run so a later run can use it. You get a plain digest and a transcript. Write two or three sentences, in the past tense, that say: what was asked, what was done or found (name the tools, files, programs or sources that matter), and how it ended, including anything that failed and why. Keep exact names, paths, numbers and error messages; drop pleasantries and reasoning. Never include anything marked private. Output the sentences only.',
  'auto',
  'auto',
  ARRAY['memory', 'volume', 'utility'],
  ARRAY[]::TEXT[],
  'prompt',
  ARRAY[]::TEXT[]
)

ON CONFLICT (name) DO NOTHING;
