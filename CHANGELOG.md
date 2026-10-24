# Changelog

All notable changes to gemsAPI are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Frontend on Tailwind CSS 4 (`@tailwindcss/postcss`), migrated with the official upgrade tool: the `gem-*` colours and the mono font stack live in an `@theme` block in `app/globals.css`, `tailwind.config.ts` and `autoprefixer` are gone, and the renamed utilities (`outline-none` to `outline-hidden`, `rounded` to `rounded-sm`) are updated in six files. Clears the `postcss-selector-parser` advisory that Dependabot PR 28 could only fix this way.

### Changed
- Frontend on Next.js 16.4.3 with React 19.3, `eslint` 9 and a flat `eslint.config.mjs` (`next lint` is gone in Next 16, so `npm run lint` runs `eslint .`), `tsconfig.json` as Next 16 requires it (`jsx: react-jsx`, `target: ES2017`), and `frontend/middleware.ts` renamed to `frontend/proxy.ts` by the official codemod. The gems list page loads without a synchronous state update inside its effect, which the React 19 lint rules flag (roadmap item 7).

### Changed
- README "Why" rewritten in plain language: the problem (instructions scattered across tools), the drawer analogy, the two tricks (prompts inside prompts, blanks), and who it is and is not for yet.

### Changed
- `docs/ROADMAP.md`: four product items for prompt practitioners (28 evals per gem from the UI, 29 typed variables, 30 side-by-side runs, 31 few-shot examples as data), a closing "For the prompt practitioner" order of payoff, and stronger reasoning on 14, 21 and 22.

### Fixed
- Docker Compose builds and runs: `next.config.mjs` sets `output: "standalone"` and `frontend/public/` exists, so `frontend/Dockerfile` can copy what it expects; the frontend container receives `GEMS_API_KEY` and `BACKEND_URL` (and nothing else) and starts only after the backend's `/health` passes; the backend service no longer bind-mounts source or runs `--reload`; `.dockerignore` files keep `node_modules`, `.next` and `.venv` out of the build contexts; the obsolete `version` key is gone. CI builds both images (roadmap item 1).

### Fixed
- `GET`, `PUT` and `DELETE /gems/{id}` accept a name or a UUID; an unknown value that is not a UUID is a 404 instead of a Postgres error surfacing as a 500 (roadmap item 2).
- `POST /gems/resolve` reports `variables_used` as the placeholders that were actually present and filled, not the keys that were sent; the MCP `resolve_gem_prompt` tool returns the same field (roadmap item 3).
- Variables are filled in a single pass after expansion, so a value containing `{other}` is never substituted again and the result no longer depends on dict order (roadmap item 3).
- Only identifier-shaped `{name}` placeholders are variables; JSON and code braces in a prompt no longer produce bogus variables or form fields (roadmap item 4).
- The API key check uses `secrets.compare_digest` (roadmap item 6).

### Added
- `tests/conftest.py` with an in-memory stand-in for the gems table, `tests/test_resolver.py` (nesting, variable propagation, cycles, depth limit, braces in prompts) and `tests/test_routes.py` (auth, lookups, 404s, resolve) through FastAPI's TestClient; `pytest.ini` sets `pythonpath` so the tests no longer patch `sys.path` (roadmap item 5). 29 tests.

### Changed
- Frontend lint runs the strict `next/typescript` rule set: `catch (e: any)` is gone in favour of an `errorMessage()` helper in `lib/api.ts`, unused imports in `GemForm.tsx` removed, quotes in JSX escaped, and the chat page effect lists its dependency (roadmap item 8).

### Changed
- `ARCHITECTURE.md` rewritten around nine Mermaid diagrams (big picture, component model, two request sequences, gem composition, resolution walkthrough, data model, trust boundaries, deployment topologies) with a component table; the ASCII box drawing is gone. The big-picture diagram also sits in the README under "How it fits together".

### Security
- `backend/app/services/gem_service.py`: the `{{gem:name}}` pattern only matches identifier characters, so an unclosed tag can no longer make the resolver backtrack polynomially (CodeQL py/polynomial-redos). Regression tests added.
- `backend/app/routes/chat.py`: provider exceptions are logged server side and the client gets a generic 502 message, on both the JSON and the SSE path (CodeQL py/stack-trace-exposure).

### Dependencies
- Backend: fastapi 0.156.4, uvicorn 0.54.0, supabase 2.33.0, anthropic 1.17.0, openai 3.35.1, fastmcp 4.1.3, pydantic 2.14.1, python-dotenv 1.2.4, python-multipart 0.0.32. Verified with the unit tests, the import check and the MCP tool registry on fastmcp 4.
- Frontend: next and eslint-config-next 14.2.35 (security patch), lucide-react 0.577.0. Next 15 and 16, React 19, Tailwind 4, ESLint 9 and 10 and TypeScript 7 are migrations tracked in `docs/ROADMAP.md` item 7 and are ignored by Dependabot until then.
- Node 24 in CI and in `frontend/Dockerfile` (Node 20 reached end of life in April 2026). Actions: checkout v7, setup-python v7, setup-node v7, codeql-action v4.
- `.github/dependabot.yml`: one pip entry at the root (it already scanned `backend/`), grouped monthly PRs per ecosystem, and major versions ignored for the frontend toolchain and the Node image.

### Added
- `LICENSE` (MIT), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `SUPPORT.md`.
- `.github/`: issue forms (bug report, feature request, gem proposal) with `config.yml`, a pull request template, `CODEOWNERS`, Dependabot for pip, npm, Docker and Actions.
- GitHub Actions: `ci.yml` (ruff, pytest, import check, `next lint`, `tsc`, `next build`, prompts and schema sync, dash check), `codeql.yml`, and `release.yml` which turns a `v*` tag into a GitHub release from this file.
- `ruff.toml` with an explicit rule set, `frontend/.eslintrc.json`, `frontend/package-lock.json` so `npm ci` works.
- `.gitattributes` with line-ending rules and `export-ignore` for repo housekeeping files.
- `docs/ROADMAP.md`: prioritised roadmap of correctness, security, API, DX and release improvements.

### Changed
- README rewritten: one-line pitch, badges, three-step quick start, MCP client config with the real Claude Desktop config path, env var table, project layout.
- `SECURITY.md` now opens with supported versions, how to report privately and the response window; the deployment policy follows.
- `frontend/next.config.ts` is now `frontend/next.config.mjs`. Next.js 14 does not load a TypeScript config, so `next dev`, `next lint` and `next build` all failed before.

### Fixed
- `backend/requirements.txt` could not be installed: `supabase==2.9.1` requires `httpx<0.28` while `fastmcp==2.2.0` requires `httpx>=0.28.1`. Now `supabase==2.16.0` and `httpx==0.28.1`.
- `frontend/app/chat/page.tsx` wraps `useSearchParams()` in a Suspense boundary, which `next build` requires to prerender the page.
- Lint: an unused import in `evals/eval_prompt_enhancer.py`, a shadowed `create_gem` import in `backend/mcp_server.py`, and a combined import line in `tests/test_gem_service.py`.

### Planned (carried over)
- Prompt version history (`gem_versions` Supabase table).
- SSE streaming in the Next.js chat UI.

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

[Unreleased]: https://github.com/poyfather/gemsAPI/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/poyfather/gemsAPI/releases/tag/v0.0.2
[0.2.0]: https://github.com/poyfather/gemsAPI/commit/8f4d13a
[0.1.0]: https://github.com/poyfather/gemsAPI/commit/9869354
