-- Run this in your Supabase SQL editor on an existing Lapidary installation
-- to add agent gems and run records (DECISIONS.md, ADR-007). Safe to rerun.

ALTER TABLE gems ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'prompt';
ALTER TABLE gems DROP CONSTRAINT IF EXISTS gems_kind_check;
ALTER TABLE gems ADD CONSTRAINT gems_kind_check CHECK (kind IN ('prompt', 'agent'));
ALTER TABLE gems ADD COLUMN IF NOT EXISTS tools TEXT[] NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS runs (
  id            UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
  gem_id        UUID        REFERENCES gems (id),
  gem_name      TEXT        NOT NULL,
  status        TEXT        NOT NULL DEFAULT 'running'
                            CHECK (status IN ('running', 'finished', 'failed', 'max_steps')),
  model         TEXT        NOT NULL,
  provider      TEXT        NOT NULL,
  input         TEXT        NOT NULL,
  output        TEXT,
  steps         INTEGER     NOT NULL DEFAULT 0,
  input_tokens  INTEGER     NOT NULL DEFAULT 0,
  output_tokens INTEGER     NOT NULL DEFAULT 0,
  error         TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS run_events (
  id         UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
  run_id     UUID        NOT NULL REFERENCES runs (id) ON DELETE CASCADE,
  seq        INTEGER     NOT NULL,
  type       TEXT        NOT NULL,
  data       JSONB       NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (run_id, seq)
);

CREATE INDEX IF NOT EXISTS runs_gem_name_idx   ON runs (gem_name);
CREATE INDEX IF NOT EXISTS runs_created_at_idx ON runs (created_at DESC);

ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE run_events ENABLE ROW LEVEL SECURITY;

-- The example agent gem shipped with 0.4.0 (also in schema.sql).
INSERT INTO gems (name, description, system_prompt, model, provider, tags, variables, kind, tools) VALUES
(
  'gem_librarian',
  'Agent that finds, reads and resolves gems in this library on request.',
  '{{gem:base_assistant}}

You are the librarian for this prompt library. The user asks about gems; you answer by using your tools, never from memory:
- search_gems to find candidates by keyword or tag
- get_gem to read a gem''s raw prompt, variables and references
- resolve_gem to show the fully expanded prompt with variables filled

Call the smallest number of tools that answers the question, then reply in plain prose. Quote gem names exactly. If nothing matches, say so and suggest the closest tags.',
  'claude-opus-5-5',
  'anthropic',
  ARRAY['agent', 'library', 'utility'],
  ARRAY[]::TEXT[],
  'agent',
  ARRAY['search_gems', 'get_gem', 'resolve_gem']
)
ON CONFLICT (name) DO NOTHING;
