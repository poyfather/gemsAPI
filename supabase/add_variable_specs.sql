-- Run this in your Supabase SQL editor on an existing Lapidary installation so blanks
-- can carry a description, type, choices and a default (roadmap item 29; also in schema.sql).
-- Safe to rerun.

ALTER TABLE gems ADD COLUMN IF NOT EXISTS variable_specs JSONB NOT NULL DEFAULT '{}';
