# Changelog

All notable changes to Lapidary are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- The MCP server over HTTP (roadmap item 41). The backend mounts the same FastMCP server at `/mcp` (streamable HTTP, stateless) behind the API key as `X-API-Key` or a bearer token, so Claude Desktop and Claude Code connectors, Cursor, VS Code and, through a public HTTPS address, ChatGPT reach the gems, agents, memory and pipelines with no local process. `GEMS_MCP_HTTP_PATH` and `GEMS_MCP_ALLOWED_HOSTS` (a tunnel's host). The console's Connections view shows the address with copy buttons for the address, the key, a URL entry and an mcp-remote bridge entry.
- Per-client API keys (roadmap item 10): `GEMS_CLIENT_KEYS=name:key,name:key` adds accepted keys that can be rotated or revoked one at a time; every check returns the client's name.

### Planned
- The installer's first run on a real Windows machine (roadmap item 42), the workbench (46), prompt version history (`gem_versions`).

## [0.4.0] - 2026-10-26

The release that turns a prompt library into Lapidary: an agent harness, a Windows console made for people who do not know AI yet, local models and a model policy, memory, and gates. Everything below merged between 2026-10-25 and 2026-10-26 (pull requests 36 to 52).

### Added
- **Agent harness (ADR-007, roadmap items 13, 32 to 34).** A gem has a `kind` (`prompt` or `agent`) and a list of `tools`; `backend/app/agents/` holds a tool registry (`@tool` functions with a JSON schema from the signature, risky or not), a provider-neutral run loop with a step cap, and a run store (`runs`, `run_events`). Surfaces: `POST /agents/{name}/runs` (JSON or SSE), `GET /runs/{id}`, `GET /agents/tools`, the MCP tools `run_agent`, `approve_run` and `list_agent_tools`, the `runs://{id}` resource. Approval gates with pause and resume: a risky tool call pauses the run (`waiting_approval`, loop state in `runs.state`), `POST /runs/{id}/approve` continues it. Tools from other MCP servers through `configs/mcp_servers.json` (`<server>.<tool>`, `<server>.*`, risky unless the entry says otherwise). Built-in tools `search_gems`, `get_gem`, `resolve_gem` and `run_powershell` (risky). The web UI streams prompt gems token by token, runs agent gems with live events, replays any run at `/runs/{id}`, and the editor has a kind select and a tool picker. Seed agents `gem_librarian`, `rea_analyst` (for the REA tools) and `windows_operator`.
- **OpenAI-compatible API (roadmap item 36).** `GET /v1/models` and `POST /v1/chat/completions` with bearer auth on the same key, so Open WebUI and any OpenAI client see every gem as a model; agent gems stream their tool activity as status lines before the answer.
- **Lapidary Console (ADR-009, ADR-012, roadmap items 36 to 40, 47 to 50).** A Windows 11 Electron application in `desktop/` that installs, connects and manages the AI tools on a machine with Lapidary as the hub: detection and installs through winget, Docker and npm (PowerShell 7, Node, Docker Desktop, Claude Desktop, ChatGPT, Ollama, Open WebUI, REA); config writers that register Lapidary and REA in Claude Desktop and ChatGPT and start Open WebUI with Lapidary, OpenAI and Ollama as providers; keys in the operating system's credential store; the backend and the UI as sidecars; a PowerShell 7 view; a toolbox of seventeen Windows management tools installed from their publishers. Retro terminal design. A guided first run: Basic asks "Which AI should we use?" and "What would you like?" and runs one of eight recipes (a private chat on this PC, homework and writing help, ask my documents, a research assistant, build me a program, my prompts in Claude and ChatGPT, a safe PowerShell assistant, understand an app) with progress and "here is what you can do now"; Advanced walks a system administrator through every choice and shows every file before it is written; an Advanced switch reveals the details on every screen. The Doctor checks everything the console can see and offers one-click fixes. Every view and component explains what it is for and what it costs or needs. The Windows installer is built and smoke-tested in CI (`.github/workflows/desktop.yml`).
- **Storage layer (roadmap item 38).** `backend/app/storage/` with one `Store` interface and two backends: SQLite (one file, seeded on first use from the `INSERT` in `supabase/schema.sql`) and Supabase. Chosen by `GEMS_STORAGE`, SQLite unless `SUPABASE_URL` is set.
- **Local models and the model policy (ADR-011, roadmap item 44).** `local` is a third provider: any OpenAI-compatible server at `LOCAL_OPENAI_BASE_URL` (Ollama by default, LM Studio, oMLX, vLLM). `GEMS_MODEL_POLICY` answers "Which AI should we use?": `local`, `online`, `mix`, `auto` (the default) or `manual`; `backend/app/services/router.py` decides per call from the policy, the gem's role and what is available, with fallback and a plain-words reason returned in chat responses, run events and the MCP tool. `GET /chat/policy` describes the world for the UI. New gems default to `auto`.
- **Lapidary Memory (ADR-010, roadmap item 43).** A `memories` table in both stores with full-text search (FTS5 on SQLite, `tsvector` on Supabase) holding observations, summaries, decisions, preferences, lessons, handoffs and notes with a source, tags and a scope. When a run finishes an observation is stored, written by the `memory_summarizer` gem when a model is available and as a plain digest otherwise; text inside `<private>...</private>` is never stored. Recall in three steps: `search_memory`, `get_memories`, `remember` and `forget` as built-in agent tools, MCP tools and routes under `/memory`; a gem with `memory: true` gets the top matches inside a `<memory>` block before its prompt. A Memory page in the web UI. Settings `GEMS_MEMORY_CAPTURE`, `GEMS_MEMORY_SUMMARIZE`, `GEMS_MEMORY_RECALL_LIMIT`, `GEMS_MEMORY_RECALL_MAX_CHARS`, `GEMS_MEMORY_MAX_CHARS`.
- **Pipelines and gates (ADR-011, roadmap item 45).** A pipeline is a builder gem followed by gate gems with roles (test, visual, review, custom), an attempt cap and an acceptance step; each gate ends with `VERDICT: PASS` or `VERDICT: FAIL`, a fail becomes feedback for the next attempt and a memory lesson, every attempt and gate is an ordinary run, a risky call pauses the pipeline, and a pass through every gate waits for a person to accept. Tables `pipelines` and `pipeline_runs`, routes under `/pipelines`, MCP tools `list_pipelines`, `run_pipeline`, `resume_pipeline`, the gate gems `test_runner` and `adversarial_reviewer`, the seed pipeline `build_and_check`, a Pipelines page with a run page.
- **Seed gems.** `study_buddy`, `writing_coach`, `research_assistant`, `program_builder`, `memory_summarizer`, `test_runner`, `adversarial_reviewer`, `rea_analyst`, `windows_operator`, `gem_librarian`, each also in `prompts/`. One-off Supabase migrations for existing installs: `add_agent_runs.sql`, `add_rea_analyst.sql`, `add_windows_operator.sql`, `add_local_provider.sql`, `add_newcomer_gems.sql`, `add_memory.sql`, `add_pipelines.sql`.
- Settings `AGENT_MAX_STEPS`, `AGENT_TOOL_RESULT_MAX_CHARS`, `POWERSHELL_TIMEOUT_SECONDS`, `POWERSHELL_MAX_OUTPUT_CHARS`, `GEMS_MCP_SERVERS_FILE`, `GEMS_MCP_TOOLS_TTL_SECONDS`, `GEMS_MCP_CALL_TIMEOUT_SECONDS`, `GEMS_STORAGE`, `GEMS_SQLITE_PATH`, `GEMS_SEED_SQL_FILE`, `LOCAL_OPENAI_BASE_URL`, `LOCAL_OPENAI_API_KEY`, `GEMS_LOCAL_DEFAULT_MODEL`, `GEMS_MODEL_POLICY`, `GEMS_CLOUD_DEFAULT_PROVIDER`, `GEMS_CLOUD_DEFAULT_MODEL`, `GEMS_MODELS_LOCAL`.

### Changed
- **The project is now called Lapidary (ADR-008).** README, docs, the API title and root endpoint, the MCP server name (`lapidary`), the web UI branding and the frontend package name use it; the repository is `poyfather/lapidary` (old URLs redirect). The `GEMS_*` environment variables and the word gem are unchanged.
- **Plain language on screen (ADR-012, roadmap item 48).** In the web UI a gem is a prompt, an agent is an assistant, variables are blanks to fill, the resolved prompt is "the prompt as sent", a run is "what the assistant did", the provider is "which AI", and every error says what to do next (`frontend/lib/words.ts`). The console says connect instead of MCP and keeps acronyms, file names and flags behind the Advanced switch. The API, the URLs and the developer docs keep the original words.
- Run events `run_started` and `run_finished` carry the run id; `run_started` records which model answered and why.
- New decision records ADR-007 to ADR-012 in `DECISIONS.md`; `ARCHITECTURE.md` and `docs/ROADMAP.md` cover the harness, the console, memory and gates (items 32 to 50).

### Fixed
- The Windows installer's one-file backend did not start: `backend/run.py` handed uvicorn the app as a string, so PyInstaller left `app.main` and the routes out of the exe. The entry imports the app by name, the build collects uvicorn's submodules, and the smoke test lists the seed gems and prints the exe's output when it fails.
- The web UI could not list prompts behind the Next.js proxy: `/api/gems/` lost its trailing slash in the rewrite, the backend redirected to its own origin, and the browser followed without the key (a 401 on every library load). `next.config.mjs` keeps the slash.
- The editor and the detail page showed `{{gem:name}}` references with their first letter missing.

### Security
- Private text is stripped from memories with a linear scan instead of a regular expression that CodeQL flagged as polynomial on user text (py/polynomial-redos).

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

[Unreleased]: https://github.com/poyfather/lapidary/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/poyfather/lapidary/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/poyfather/lapidary/compare/v0.0.2...v0.3.0
[0.0.2]: https://github.com/poyfather/lapidary/releases/tag/v0.0.2
[0.2.0]: https://github.com/poyfather/lapidary/commit/8f4d13a
[0.1.0]: https://github.com/poyfather/lapidary/commit/9869354
