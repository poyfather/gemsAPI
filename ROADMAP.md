# ROADMAP

## Purpose
Track Lapidary development priorities, sequencing, and delivery status.
This file tracks delivery status of agreed items. The prioritised list of improvements, with reasons, sizes and dependencies, is in [docs/ROADMAP.md](docs/ROADMAP.md).

---

## Now

### Project-Template Alignment
- Goal: adopt poyfather Project-Template structure across the repo.
- Status: Complete
- Owner: poyfather
- Dependencies: None
- Success Criteria: all required root docs exist, scaffold dirs present, `pytest -q` and `ruff check .` pass.
- Links: `AGENTS.md`, `DECISIONS.md` (ADR-005)

### Smoke Test and Lint Baseline
- Goal: `pytest -q` and `ruff check .` pass from repo root with zero warnings/failures.
- Status: Complete (CI runs `ruff check .` and `pytest -q` on every PR)
- Owner: poyfather
- Dependencies: Project-Template alignment
- Success Criteria: CI-ready test and lint baseline established.
- Links: `STANDARDS.md`, `tests/`

---

## Next

### Prompt Eval Harness
- Goal: `evals/eval_prompt_enhancer.py` provides a repeatable quality score for the `prompt_enhancer` gem so regressions are caught before merge.
- Status: Planned
- Owner: poyfather
- Dependencies: Anthropic API key in env, `prompt_enhancer` gem stable
- Success Criteria: eval script runs, produces a numeric score, and records a baseline.
- Links: `evals/`, `prompts/prompt_enhancer.md`, `ARCHITECTURE.md`

### Prompt Version History
- Goal: add a `gem_versions` table to Supabase that snapshots `system_prompt` on every update, enabling rollback and diff.
- Status: Planned
- Owner: poyfather
- Dependencies: Supabase schema migration
- Success Criteria: update a gem via UI → previous version visible in history → revert works.
- Links: `ARCHITECTURE.md`, `supabase/`

### API Authentication
- Goal: add API key authentication to FastAPI endpoints so the backend can be safely exposed beyond localhost.
- Status: Complete
- Owner: poyfather
- Dependencies: None
- Success Criteria: unauthenticated requests return 401; authenticated requests work normally.
- Links: `SECURITY.md`, `backend/app/auth.py`

### Streaming in Chat UI
- Goal: wire SSE streaming from FastAPI through to the Next.js chat interface so responses appear token-by-token.
- Status: Planned
- Owner: poyfather
- Dependencies: None
- Success Criteria: chat messages stream visibly in the UI; no full-response wait.
- Links: `frontend/app/chat/page.tsx`, `backend/app/routes/chat.py`

---

## Later

### CI Pipeline
- Goal: GitHub Actions workflow that runs `ruff check .` and `pytest -q` on every PR.
- Status: Complete (`.github/workflows/ci.yml`)
- Owner: poyfather
- Dependencies: smoke test baseline
- Success Criteria: PRs blocked on lint/test failure.
- Links: `STANDARDS.md`

### One-Command Deployment
- Goal: `scripts/deploy.ps1` (or bash equivalent) that builds and pushes Docker images and applies Supabase migrations in one step.
- Status: Planned
- Owner: poyfather
- Dependencies: stable Docker Compose config, Supabase CLI integration
- Success Criteria: fresh environment setup in under 5 minutes.
- Links: `scripts/`, `docker-compose.yml`

### Gem Import / Export
- Goal: CLI or UI feature to export all gems as a JSON/YAML bundle and import them into another Lapidary instance.
- Status: Planned
- Owner: poyfather
- Dependencies: stable schema
- Success Criteria: export produces a portable file; import populates gems without conflicts.
- Links: `scripts/`, `supabase/schema.sql`
