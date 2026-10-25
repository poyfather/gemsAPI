-- Run this in your Supabase SQL editor on an existing Lapidary installation so gems may
-- name the local provider or leave the choice to the model policy (ADR-011). Safe to rerun.

ALTER TABLE gems DROP CONSTRAINT IF EXISTS gems_provider_check;
ALTER TABLE gems ADD CONSTRAINT gems_provider_check CHECK (provider IN ('anthropic', 'openai', 'local', 'auto'));
