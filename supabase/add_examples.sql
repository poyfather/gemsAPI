-- Run this in your Supabase SQL editor on an existing Lapidary installation so gems can
-- carry worked examples as data (roadmap item 31; also in schema.sql). Safe to rerun.

ALTER TABLE gems ADD COLUMN IF NOT EXISTS examples JSONB NOT NULL DEFAULT '[]';
