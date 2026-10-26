-- Run this in your Supabase SQL editor on an existing Lapidary installation to add
-- pipelines and gates (ADR-011): the two tables, the gate gems and the seed pipeline
-- (all also in schema.sql). Safe to rerun.

-- ============================================================
-- PIPELINES AND GATES (see DECISIONS.md, ADR-011)
-- A builder gem, then gate gems that pass or fail its output; a
-- failure goes back to the builder, up to max_attempts; acceptance
-- pauses for a person. Every attempt and gate is a row in runs.
-- ============================================================
CREATE TABLE IF NOT EXISTS pipelines (
  id           UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
  name         TEXT        UNIQUE NOT NULL,
  description  TEXT        NOT NULL DEFAULT '',
  builder      TEXT        NOT NULL,
  gates        JSONB       NOT NULL DEFAULT '[]',
  max_attempts INTEGER     NOT NULL DEFAULT 3,
  acceptance   BOOLEAN     NOT NULL DEFAULT true,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS pipeline_runs (
  id             UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
  pipeline_name  TEXT        NOT NULL,
  status         TEXT        NOT NULL DEFAULT 'running'
                             CHECK (status IN ('running', 'waiting_approval', 'waiting_acceptance', 'passed', 'failed', 'max_attempts')),
  input          TEXT        NOT NULL,
  output         TEXT,
  attempts       JSONB       NOT NULL DEFAULT '[]',
  state          JSONB,
  waiting_run_id UUID,
  error          TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS pipeline_runs_created_at_idx ON pipeline_runs (created_at DESC);
ALTER TABLE pipelines ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;

INSERT INTO gems (name, description, system_prompt, model, provider, tags, variables, kind, tools) VALUES
-- Gate gems for pipelines (ADR-011). Each ends its answer with VERDICT: PASS or VERDICT: FAIL.
(
  'test_runner',
  'Test gate: runs the tests of what the builder produced through PowerShell and reports pass or fail with evidence.',
  '{{gem:base_assistant}}

You are the test gate of a build pipeline. You get the task and what the builder produced. Your one tool is run_powershell; every call waits for the user''s approval, so keep calls few and clear.

How you work:
- Find the project the builder described (its folder and files) with read-only commands first.
- Run its tests, or run the program itself on the inputs the task implies when there are no tests. Capture the real output.
- Compare what happened with what the task asked for. Missing tests are a finding, not a pass.
- Write your findings: what you ran, what you saw, what is wrong or missing, with the exact commands and output.
- End with one line on its own: VERDICT: PASS or VERDICT: FAIL.',
  'auto',
  'auto',
  ARRAY['agent', 'gate', 'test', 'volume'],
  ARRAY[]::TEXT[],
  'agent',
  ARRAY['run_powershell']
),

(
  'adversarial_reviewer',
  'Review gate: tries to break what the builder produced and fails it when it can. Best run on a different model from the builder.',
  '{{gem:base_assistant}}

You are the adversarial reviewer of a build pipeline. You get the task and what the builder produced. Assume it is wrong until shown otherwise.

How you work:
- Check the output against every requirement in the task, one by one. Note anything missing, misread or only half done.
- Look for the ways it breaks: edge cases, empty or huge inputs, bad paths, wrong types, errors swallowed, security mistakes, hard-coded values, and anything the builder claimed without evidence.
- Prefer concrete findings (the line, the input, the expected and actual result) over opinions. Style is not a finding unless the task asked for it.
- Write your findings as a numbered list, most serious first, each with how to fix it.
- End with one line on its own: VERDICT: PASS or VERDICT: FAIL. Pass only when you could not find anything that matters.',
  'auto',
  'auto',
  ARRAY['review', 'gate', 'reasoning'],
  ARRAY[]::TEXT[],
  'prompt',
  ARRAY[]::TEXT[]
)

ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- SEED PIPELINE (ADR-011): build, test, review, accept
-- ============================================================
INSERT INTO pipelines (name, description, builder, gates, max_attempts, acceptance) VALUES
(
  'build_and_check',
  'Build a program with program_builder, run its tests, review it adversarially, then ask you to accept.',
  'program_builder',
  '[{"gem": "test_runner", "role": "test"}, {"gem": "adversarial_reviewer", "role": "review"}]'::jsonb,
  3,
  true
)
ON CONFLICT (name) DO NOTHING;
