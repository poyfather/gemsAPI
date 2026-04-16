# CHANGELOG

All notable changes to gemsAPI are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]
- Prompt version history (gem_versions Supabase table).
- SSE streaming in the Next.js chat UI.
- GitHub Actions CI pipeline (ruff + pytest on PRs).
- Eval harness for prompt_enhancer gem.

## [0.0.2] - 2026-04-16
### Added
- `backend/app/auth.py` — FastAPI `Security` dependency that validates `X-API-Key` request header against `GEMS_API_KEY` environment variable.
- `frontend/middleware.ts` — Next.js middleware that injects `X-API-Key` server-side on all `/api/*` requests before the rewrite forwards them to FastAPI. Key never reaches the browser bundle.

### Changed
- `backend/app/routes/gems.py` and `chat.py` — router-level `dependencies=[Depends(require_api_key)]` protects every endpoint automatically.
- `backend/app/main.py` — startup lifespan validates `GEMS_API_KEY` is present at boot; server refuses to start rather than silently running unprotected.
- `.env.example` — added `GEMS_API_KEY` field with generation command.
- `frontend/.env.local.example` — added `GEMS_API_KEY` field with usage note (no `NEXT_PUBLIC_` prefix).
- `ROADMAP.md` — API Authentication marked Complete.

## [0.2.0] - 2026-04-15
### Added
- Full Project-Template structure: `AGENTS.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `CONTEXT.md`, `DECISIONS.md`, `ROADMAP.md`, `SECURITY.md`, `STANDARDS.md`.
- Scaffold directories: `configs/`, `evals/`, `prompts/`, `scripts/`, `src/`, `tests/`.
- `prompts/` directory with canonical `.md` files for all shipped gems.
- `evals/eval_prompt_enhancer.py` — baseline eval for the prompt_enhancer gem.
- `scripts/setup.ps1` and `scripts/test.ps1` for Windows convenience.
- Root `requirements.txt` with `pytest` and `ruff` for dev tooling.
- `tests/test_smoke.py` and `tests/test_gem_service.py` for unit test baseline.
- `supabase/add_prompt_enhancer.sql` for adding the prompt_enhancer gem to existing installs.
- ADRs 001–005 documenting all major design decisions.

## [0.1.0] - 2026-04-15
### Added
- Initial project scaffold.
- FastAPI backend with full CRUD for gems (`/gems`), recursive resolution (`/gems/resolve`), and chat endpoint (`/chat`) with SSE streaming support.
- `gem_service.py` with depth-limited, cycle-safe recursive `{{gem:name}}` expansion and `{variable}` substitution.
- `llm_service.py` abstracting Anthropic and OpenAI providers behind a uniform interface.
- FastMCP server (`mcp_server.py`) exposing `list_gems`, `get_gem`, `resolve_gem_prompt`, `chat_with_gem`, `create_gem`, `search_gems`, and `list_available_models` tools; `gems://list` and `gems://{name}` resources.
- Next.js 14 frontend with gem library (search, filter by tag), gem detail page with live resolve preview, create/edit forms, and chat testing interface.
- Supabase schema with `gems` table, RLS, indexes, and 5 seed gems: `base_assistant`, `code_reviewer`, `creative_writer`, `summarizer`, `engineering_lead`, `prompt_enhancer`.
- Docker Compose for local all-in-one deployment.
- `.env.example` with all required environment variables documented.
