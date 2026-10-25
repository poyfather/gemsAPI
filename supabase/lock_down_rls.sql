-- Run this in your Supabase SQL editor on an existing Lapidary installation
-- created before ADR-006 (October 2026). Safe to run more than once.
--
-- It removes the open "allow_all" policy. Row level security stays enabled
-- with no policies, so only the service role key (used by the backend and
-- the MCP server) can read or write gems; the anon and authenticated roles
-- get nothing. Nothing else changes.

ALTER TABLE gems ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow_all" ON gems;
