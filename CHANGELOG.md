# Changelog

All notable changes to Lapidary are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Plain-language pass over the web UI and the console (roadmap item 48, ADR-012). On screen a gem is a prompt, an agent is an assistant, variables are blanks to fill, embeds are "built from", the resolved prompt is "the prompt as sent", a run is "what the assistant did", the provider is "which AI" (Claude, ChatGPT, on this PC, decided per call), a risky tool "asks first", and run statuses read "waiting for you" or "stopped at the step limit". `frontend/lib/words.ts` holds the labels and `explain()`, which adds what to do next to every error (key mismatch, not found, the AI did not answer, Lapidary not running). The console says connect instead of MCP, names keys by the AI they unlock, moves acronyms, file names and flags behind the Advanced switch, and its installer, config and Docker failures say what to do. The API, the URLs, the environment variables and the developer docs keep the original words.

### Added
- The Doctor (roadmap item 49, ADR-012): a console view that checks Lapidary and the web UI (up, or their ports taken by another program), the AI choice against what is actually there (Ollama installed, running, with a model; a cloud key saved and accepted by the service), the private chat (Docker installed and running, the port free, the container up), the connections to Claude Desktop and ChatGPT (installed, connected, config file valid), PowerShell 7, and whether a newer console release exists. Each finding says what it means in plain words and, where one click can fix it, offers the fix: restart, install, start Ollama, download a model, start the chat, open Docker Desktop, connect an app, open Settings or the releases page. `desktop/lib/doctor.js` is pure and tested (7 tests); `main.js` gathers the facts (port probes, key probes against the providers' model lists, the apps' config files, the GitHub release).

### Fixed
- The web UI could not list prompts behind the Next.js proxy: `/api/gems/` lost its trailing slash in the rewrite, the backend answered with a redirect to its own origin, and the browser followed it without the key the proxy adds (a 401 on every library load). `next.config.mjs` now keeps the slash (`skipTrailingSlashRedirect` and a slashed rewrite rule).
- The editor and the detail page showed `{{gem:name}}` references with their first letter missing (`ase_assistant`).

### Added
- Guided first run and recipes in the console (roadmap item 47, ADR-012). A new Start view with two paths. Basic asks "Which AI should we use?" (the five model policies in plain words, with what is private and what costs money) and "What would you like?", then shows the steps for this machine before running them with progress and ends with "here is what you can do now". Eight recipes: a private chat on this PC, help with homework and writing, ask my own documents privately, a research assistant over my own sources, build me a program, let Claude and ChatGPT use my prompts, an assistant that runs safe PowerShell, understand how an app works. Advanced walks a system administrator through components, AI and keys, SQLite or Supabase, connections, ports and folders, what assistants may do without asking, logging and updates, and lists every file and command before applying. An Advanced switch in the top bar reveals the details on every screen. `desktop/lib/recipes.js` plans the steps from the machine's state (pure, 10 tests); the main process runs them (winget, `ollama serve` and `ollama pull`, docker compose, config files, settings) and streams progress. Ollama detection now lists the models it has.
- Four newcomer gems, provider `auto` so the model policy decides: `study_buddy` (explains and quizzes instead of doing the homework), `writing_coach` (edits and explains the edits, keeps your voice), `research_assistant` (answers only from your sources, with citations) and the agent `program_builder` (plans, writes and tests a program through approved PowerShell calls). Each also in `prompts/`.
- Console settings: `localModel` (the model the first run downloads and the backend prefers, `GEMS_LOCAL_DEFAULT_MODEL`).

### Changed
- The project is now called Lapidary (ADR-008). README, docs, the API title and root endpoint, the MCP server name (`lapidary`), the web UI branding and the frontend package name use it. The repository URL, the `GEMS_*` environment variables and the word gem are unchanged.

### Added
- Approval gates with pause and resume (roadmap item 33). A risky tool call pauses the run with status `waiting_approval`, its loop state saved in the new `runs.state` column and an `approval_requested` event; `POST /runs/{id}/approve` (JSON or SSE) and the MCP `approve_run` tool continue it, approving or denying the call, with `approval_decided` events. The chat bubble and the run page show Approve and Deny. `supabase/add_agent_runs.sql` adds the column and widens the status check on existing installs.

### Changed
- The project is now called Lapidary (ADR-008). README, docs, the API title and root endpoint, the MCP server name (`lapidary`), the web UI branding and the frontend package name use it. The repository URL, the `GEMS_*` environment variables and the word gem are unchanged.

### Added
- Run viewer and streaming in the web UI (roadmap items 13 and 34). `lib/api.ts` gains an SSE reader, `chat.stream`, `agents.run`, `agents.stream`, `agents.tools` and `runs.get`. The chat page streams prompt gems token by token and runs agent gems with live events (turns, tool calls, results, outcome) plus a link to the run; `app/runs/[id]` replays any stored run; `GemForm` has a kind select and a tool picker; cards and the detail page show kind and tools. Run events `run_started` and `run_finished` now carry the run id.
- Agent harness (ADR-007). A gem has a `kind` (`prompt` or `agent`) and a list of `tools`; `backend/app/agents/` holds a tool registry (`@tool` functions with a JSON schema from the signature, risky or not), a provider-neutral run loop with a step cap and a run store (`runs`, `run_events`). `llm_service.complete_turn` and `tool_result_messages` give both providers one tool-use turn shape. Surfaces: `POST /agents/{name}/runs` (JSON or SSE), `GET /runs/{id}`, `GET /agents/tools`, and the MCP tools `run_agent` and `list_agent_tools` plus the `runs://{id}` resource. Three built-in read-only tools (`search_gems`, `get_gem`, `resolve_gem`) and a seed agent, `gem_librarian`. `supabase/add_agent_runs.sql` updates existing installs. Settings `AGENT_MAX_STEPS` and `AGENT_TOOL_RESULT_MAX_CHARS`. 17 new tests.

### Planned
- Prompt version history (`gem_versions` Supabase table).

## [0.3.0] - 2026-10-25

The first tagged release since v0.0.2 and the first one cut with the release workflow. It also restarts the version sequence: the 0.1.0 and 0.2.0 sections below predate the v0.0.2 tag, and nothing after that was tagged, so this release takes the next minor above the highest number in this file.

### Security
- ADR-006: single-tenant access model. The `allow_all` row level security policy is dropped from `supabase/schema.sql` and RLS has no policies for the `anon` or `authenticated` roles, so only the service role key used by the backend and the MCP server can read or write gems. `backend/app/database.py` accepts the service role key only; the anon key option is removed from `.env.example`. Existing installs run `supabase/lock_down_rls.sql` once (roadmap item 9).
- `backend/app/services/gem_service.py`: the `{{gem:name}}` pattern only matches identifier characters, so an unclosed tag can no longer make the resolver backtrack polynomially (CodeQL py/polynomial-redos). Regression tests added.
- `backend/app/routes/chat.py`: provider exceptions are logged server side and the client gets a generic 502 message, on both the JSON and the SSE path (CodeQL py/stack-trace-exposure).

### Added
- `tests/conftest.py` with an in-memory stand-in for the gems table, `tests/test_resolver.py` (nesting, variable propagation, cycles, depth limit, braces in prompts) and `tests/test_routes.py` (auth, lookups, 404s, resolve) through FastAPI's TestClient; `pytest.ini` sets `pythonpath` so the tests no longer patch `sys.path` (roadmap item 5). 29 tests.
- `LICENSE` (MIT), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `SUPPORT.md`.
- `.github/`: issue forms (bug report, feature request, gem proposal) with `config.yml`, a pull request template, `CODEOWNERS`, Dependabot for pip, npm, Docker and Actions.
- GitHub Actions: `ci.yml` (ruff, pytest, import check, `next lint`, `tsc`, `next build`, prompts and schema sync, dash check), `codeql.yml`, and `release.yml` which turns a `v*` tag into a GitHub release from this file.
- `ruff.toml` with an explicit rule set, `frontend/.eslintrc.json`, `frontend/package-lock.json` so `npm ci` works.
- `.gitattributes` with line-ending rules and `export-ignore` for repo housekeeping files.
- `docs/ROADMAP.md`: prioritised roadmap of correctness, security, API, DX and release improvements.

### Changed
- `backend/app/settings.py` is the one home for runtime defaults: `GEMS_DEFAULT_PROVIDER` and `GEMS_DEFAULT_MODEL` (now `claude-opus-5-5`) for new gems over REST, UI and MCP; `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` and `LLM_MAX_TOKENS` for provider calls (roadmap items 17 and 18).
- `GET /chat/models` and the MCP `list_available_models` tool return each provider's live model list (OpenAI's filtered to chat models), cached for `GEMS_MODEL_LIST_TTL_SECONDS`, with `GEMS_MODELS_ANTHROPIC` and `GEMS_MODELS_OPENAI` as pins and a static fallback. The static list with retired `claude-3-5-*` and `gpt-3.5-turbo` entries is gone, and so are the hard-coded lists in `GemForm.tsx`.
- Both SDK clients are built with an explicit timeout and retry count; any SDK failure becomes one `ProviderError`, logged server side.
- Seed gems and the eval use the new default model; `supabase/update_default_models.sql` moves existing gems off retired models.
- Frontend on Tailwind CSS 4 (`@tailwindcss/postcss`), migrated with the official upgrade tool: the `gem-*` colours and the mono font stack live in an `@theme` block in `app/globals.css`, `tailwind.config.ts` and `autoprefixer` are gone, and the renamed utilities (`outline-none` to `outline-hidden`, `rounded` to `rounded-sm`) are updated in six files. Clears the `postcss-selector-parser` advisory that Dependabot PR 28 could only fix this way.
- Frontend on Next.js 16.4.3 with React 19.3, `eslint` 9 and a flat `eslint.config.mjs` (`next lint` is gone in Next 16, so `npm run lint` runs `eslint .`), `tsconfig.json` as Next 16 requires it (`jsx: react-jsx`, `target: ES2017`), and `frontend/middleware.ts` renamed to `frontend/proxy.ts` by the official codemod. The gems list page loads without a synchronous state update inside its effect, which the React 19 lint rules flag (roadmap item 7).
- README "Why" rewritten in plain language: the problem (instructions scattered across tools), the drawer analogy, the two tricks (prompts inside prompts, blanks), and who it is and is not for yet.
- `docs/ROADMAP.md`: four product items for prompt practitioners (28 evals per gem from the UI, 29 typed variables, 30 side-by-side runs, 31 few-shot examples as data), a closing "For the prompt practitioner" order of payoff, and stronger reasoning on 14, 21 and 22.
- Frontend lint runs the strict `next/typescript` rule set: `catch (e: any)` is gone in favour of an `errorMessage()` helper in `lib/api.ts`, unused imports in `GemForm.tsx` removed, quotes in JSX escaped, and the chat page effect lists its dependency (roadmap item 8).
- `ARCHITECTURE.md` rewritten around nine Mermaid diagrams (big picture, component model, two request sequences, gem composition, resolution walkthrough, data model, trust boundaries, deployment topologies) with a component table; the ASCII box drawing is gone. The big-picture diagram also sits in the README under "How it fits together".
- README rewritten: one-line pitch, badges, three-step quick start, MCP client config with the real Claude Desktop config path, env var table, project layout.
- `SECURITY.md` now opens with supported versions, how to report privately and the response window; the deployment policy follows.
- `frontend/next.config.ts` is now `frontend/next.config.mjs`. Next.js 14 does not load a TypeScript config, so `next dev`, `next lint` and `next build` all failed before.
- Backend: fastapi 0.156.4, uvicorn 0.54.0, supabase 2.33.0, anthropic 1.17.0, openai 3.35.1, fastmcp 4.1.3, pydantic 2.14.1, python-dotenv 1.2.4, python-multipart 0.0.32. Verified with the unit tests, the import check and the MCP tool registry on fastmcp 4.
- Frontend: next and eslint-config-next 14.2.35 (security patch), lucide-react 0.577.0. Next 15 and 16, React 19, Tailwind 4, ESLint 9 and 10 and TypeScript 7 are migrations tracked in `docs/ROADMAP.md` item 7 and are ignored by Dependabot until then.
- Node 24 in CI and in `frontend/Dockerfile` (Node 20 reached end of life in April 2026). Actions: checkout v7, setup-python v7, setup-node v7, codeql-action v4.
- `.github/dependabot.yml`: one pip entry at the root (it already scanned `backend/`), grouped monthly PRs per ecosystem, and major versions ignored for the frontend toolchain and the Node image.

### Fixed
- Docker Compose builds and runs: `next.config.mjs` sets `output: "standalone"` and `frontend/public/` exists, so `frontend/Dockerfile` can copy what it expects; the frontend container receives `GEMS_API_KEY` and `BACKEND_URL` (and nothing else) and starts only after the backend's `/health` passes; the backend service no longer bind-mounts source or runs `--reload`; `.dockerignore` files keep `node_modules`, `.next` and `.venv` out of the build contexts; the obsolete `version` key is gone. CI builds both images (roadmap item 1).
- `GET`, `PUT` and `DELETE /gems/{id}` accept a name or a UUID; an unknown value that is not a UUID is a 404 instead of a Postgres error surfacing as a 500 (roadmap item 2).
- `POST /gems/resolve` reports `variables_used` as the placeholders that were actually present and filled, not the keys that were sent; the MCP `resolve_gem_prompt` tool returns the same field (roadmap item 3).
- Variables are filled in a single pass after expansion, so a value containing `{other}` is never substituted again and the result no longer depends on dict order (roadmap item 3).
- Only identifier-shaped `{name}` placeholders are variables; JSON and code braces in a prompt no longer produce bogus variables or form fields (roadmap item 4).
- The API key check uses `secrets.compare_digest` (roadmap item 6).
- `backend/requirements.txt` could not be installed: `supabase==2.9.1` requires `httpx<0.28` while `fastmcp==2.2.0` requires `httpx>=0.28.1`. Now `supabase==2.16.0` and `httpx==0.28.1`.
- `frontend/app/chat/page.tsx` wraps `useSearchParams()` in a Suspense boundary, which `next build` requires to prerender the page.
- Lint: an unused import in `evals/eval_prompt_enhancer.py`, a shadowed `create_gem` import in `backend/mcp_server.py`, and a combined import line in `tests/test_gem_service.py`.

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

[Unreleased]: https://github.com/poyfather/lapidary/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/poyfather/lapidary/compare/v0.0.2...v0.3.0
[0.0.2]: https://github.com/poyfather/lapidary/releases/tag/v0.0.2
[0.2.0]: https://github.com/poyfather/lapidary/commit/8f4d13a
[0.1.0]: https://github.com/poyfather/lapidary/commit/9869354
