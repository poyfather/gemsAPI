-- Run this in your Supabase SQL editor on an existing gemsAPI installation
-- to move gems off models that the providers have retired. Safe to rerun.
-- Adjust the target model if you have set GEMS_DEFAULT_MODEL to something else.

ALTER TABLE gems ALTER COLUMN model SET DEFAULT 'claude-opus-5-5';

UPDATE gems
SET model = 'claude-opus-5-5'
WHERE provider = 'anthropic'
  AND model IN (
    'claude-opus-4-5', 'claude-sonnet-4-5', 'claude-haiku-4-5',
    'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022',
    'claude-3-opus-20240229', 'claude-3-sonnet-20240229', 'claude-3-haiku-20240307'
  );
