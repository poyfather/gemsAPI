# Lapidary improvement roadmap

A prioritised list of improvements to the project itself, written on 2026-10-23 from a read of the code at v0.0.2 plus the repository hygiene pull request that added this file. The root [ROADMAP.md](../ROADMAP.md) tracks delivery status of agreed items; this file is the reasoning: what to do, why, how big it is, and what it waits on.

Sizes: **S** is under half a day, **M** is one to three days, **L** is a week or more. Items are numbered so they can be referenced from issues and from the root roadmap.

Two lenses run through the list. Items 1 to 27 come from reading the code: correctness, security, developer experience. Items 14, 21, 22 and 28 to 31 come from asking what a person who writes prompts for a living needs from a prompt library, and are summarised in [For the prompt practitioner](#for-the-prompt-practitioner) at the end. If only one thread gets attention, that one is the product. Items 32 to 35 follow ADR-007, which turned gems into agent definitions with a thin run loop. Items 36 to 42 follow ADR-009, the Windows console that installs and connects the AI tools on a machine with Lapidary as the hub. Items 47 to 50 follow ADR-012 and come first among the console items: the platform is for someone who does not know AI yet and should get something great out of it on day one. Items 51 to 58 follow ADR-013 and now come first of all: see [Growth plan](#growth-plan-adr-013) below.

## Growth plan (ADR-013)

An outside review on 2026-10-26 read the public repository and docs and concluded that Lapidary has more functionality than its public presentation communicates. It does not need another dozen technical features right now. It needs a compelling first experience, easy distribution, and visible proof that it makes AI more useful. The biggest risk is adoption: the project speaks to developers, newcomers, IT administrators and organizations at once, and each expects something different. The biggest opportunity is that someone can understand it, try it and get something useful from it within five minutes.

**Positioning.** Sell the outcome, not the parts.

> **Your AI. Your instructions. Every app.**
> Create your best prompts once. Improve them with testing. Turn them into assistants. Use them across your favorite AI tools while keeping control of your data.

**Phases.** Work goes in this order; an item outside them waits unless it unblocks one.

| Phase | Goal | Items |
|---|---|---|
| 1. Attract | A visitor understands it and wants to try it | 51 live demo, 52 presentation and consistent docs |
| 2. Activate | A new user gets a first useful result | 53 gem gallery, 22 easy import, the first run (47, done) |
| 3. Retain | People come back and bring others | 54 visual builder, 55 usage and cost dashboard, 56 sharing, 57 trust for teams |
| Throughout | Know whether it is working | 58 measure the three numbers |

**What to measure.** Three numbers, defined in item 58:

1. The share of visitors who create their first gem.
2. The share of those who use it again seven days later.
3. The number who share a gem with another person.

**The first five minutes**, as the target experience: open the demo or install the console; pick a gem from the gallery or paste a prompt you already use; see it answer, then see the improved version answer better side by side; use it from Claude, ChatGPT or Cursor without copying anything.

## Already done in the hygiene pull request

These were found during the audit and fixed because CI could not pass without them. They are listed so the reasoning is on record.

- `backend/requirements.txt` was uninstallable: `supabase==2.9.1` needs `httpx<0.28`, `fastmcp==2.2.0` needs `httpx>=0.28.1`. Pins moved to `supabase==2.16.0` and `httpx==0.28.1`; the 8 unit tests pass on that set.
- `frontend/next.config.ts` was never loaded: Next.js 14 only reads `next.config.js` or `.mjs`, so `next dev`, `next lint` and `next build` all exited with an error. Renamed to `next.config.mjs` with the same rewrite rule.
- `frontend/app/chat/page.tsx` called `useSearchParams()` outside a Suspense boundary, which stops `next build` from prerendering `/chat`. Wrapped.
- Three ruff findings and a `ruff.toml` so the rule set does not drift with ruff releases; `frontend/.eslintrc.json` so `next lint` runs non-interactively; `frontend/package-lock.json` so `npm ci` works in CI and in `frontend/Dockerfile`.

## At a glance

| # | Item | Area | Size | Group |
|---|---|---|---|---|
| 1 | Make Docker Compose work end to end | DX, deployment | S | Now, done |
| 2 | 404, not 500, for unknown non-UUID gem ids | Correctness | S | Now, done |
| 3 | Fix `variables_used` and order-dependent substitution | Correctness | S | Now, done |
| 4 | Stop treating every `{...}` as a variable | Correctness | M | Now, done |
| 5 | Resolver and route tests with a fake database | Tests | M | Now, done |
| 6 | Constant-time key check, no provider errors in responses | Security | S | Now, done |
| 7 | Patched Next.js, then Next 15 | Security, DX | S then M | Now, done |
| 8 | Turn the strict TypeScript lint rules back on | DX | S | Now, done |
| 9 | Decide the Supabase RLS and key model | Security | M to L | Next, done |
| 10 | Per-client API keys, and auth for a hosted MCP server | Security | M | Now, done with 41 |
| 11 | Rate limits and spend guards on chat | Security, cost | M | Now, within 55 |
| 12 | API consistency and versioning | API, MCP | M | Next |
| 13 | Streaming in the chat UI | Product | M | Next, done |
| 14 | Prompt version history | Product | L | Now, done |
| 15 | Supabase CLI migrations instead of hand-run SQL | DX, data | M | Next |
| 16 | Make `prompts/` the single source of shipped gems | DX, data | S to M | Next |
| 17 | One place for model defaults, drop retired models | Correctness | S | Next, done |
| 18 | Timeouts and retries in `llm_service.py` | Reliability | S | Next, done |
| 19 | Resolver query batching and a prompt size budget | Performance | M | Later |
| 20 | Structured logging and a real health check | Operations | M | Later |
| 21 | Multi-user accounts | Product, security | L | Next, within 57 |
| 22 | Gem import and export, from ChatGPT, Claude, Cursor, Markdown and JSON | Product, growth | M to L | Now, phase 2 |
| 23 | Backend packaging, lock file, one-command dev | DX | M | Later |
| 24 | Frontend tests | Tests | M | Later |
| 25 | One version source and a tidy release process | Release | S | Later, done |
| 26 | Screenshots, API reference, resolution guide | Docs | S to M | Now, screenshots done with 52 |
| 27 | Split-deploy guide | Docs | S | Later |
| 28 | Evals per gem, runnable from the UI | Product, quality | M | Now, done |
| 29 | Typed variables with descriptions and defaults | Product, MCP | M | Now, done |
| 30 | Side-by-side runs | Product | M | Now, done |
| 31 | Few-shot examples as first-class data | Product | M | Now, done |
| 32 | Agent tools from remote MCP servers and HTTP endpoints | Agents | M | Next, MCP done |
| 33 | Approval gates with pause and resume | Agents, security | M | Next, done |
| 34 | Run viewer in the UI | Agents, product | M | Next, done |
| 35 | Managed Agents as an execution backend | Agents | M | Later |
| 36 | OpenAI-compatible API: gems and agents as models for Open WebUI | Console, API | M | Now, done |
| 37 | Console shell: Electron app, detection, config writers, sidecars | Console | L | Now, done |
| 38 | Storage layer with a SQLite backend | Console, data | L | Next, done |
| 39 | Installers and updates through winget and Docker; Open WebUI management | Console | L | Now, done |
| 40 | Settings and connections: keys, MCP servers, client configs | Console | M | Now, done |
| 41 | Lapidary's MCP server over HTTP for Claude Desktop and ChatGPT | Console, MCP | M | Now, done |
| 42 | Windows installer, CI build and smoke test, REA bundling, first run, helper service, signing | Console | M | Now, partly done |
| 43 | Lapidary Memory: observations across runs, chats and clients | Memory, product | L | Now, done |
| 44 | Local models as a provider, and the model policy (local, online, mix, auto, hand pick) | Providers, hybrid | M | Now, done |
| 45 | Gates: builder, tests, visual review, adversarial review, acceptance | Agents, quality | L | Now, done |
| 46 | Workbench: parallel runs on worktrees; Codex and OpenCode as clients | Console, agents | L | Later |
| 47 | Guided first run and recipes: outcomes in one click | Console, newcomers | L | Now, done |
| 48 | Plain-language pass over the console and the web UI | Console, newcomers | M | Now, done |
| 49 | Doctor: self-check with offered fixes | Console, newcomers | M | Now, done |
| 50 | Explainers: every screen says what it is for and why | Console, newcomers | S | Now, done |
| 51 | Live demo in the browser: no install, no key | Growth, attract | L | Now, phase 1 |
| 52 | Repository presentation: positioning, screenshots, demo video, install options, consistent docs | Growth, attract | S to M | Now, phase 1, partly done |
| 53 | Gem gallery: curated gems with preview, example output, quality score, one-click install | Growth, activate | L | Now, phase 2 |
| 54 | Visual builder for assistants, tools, tests and approvals | Growth, retain | L | Next, phase 3 |
| 55 | Usage, cost and performance dashboard with spend limits, alerts and rate limits | Growth, retain | M to L | Next, phase 3 |
| 56 | Sharing: publish a gem as a link, install someone's gem, update without losing your changes | Growth, retain | L | Next, phase 3 |
| 57 | Trust for teams: accounts and roles, approval workflows, scoped keys, signed installer, security review | Growth, security | L | Next, phase 3 |
| 58 | Measure first gem, seven-day return and sharing | Growth | M | Now, throughout |

## Now

Things that are broken or that a first contributor would trip over this week.

### 1. Make Docker Compose work end to end

**Status: done** (`output: "standalone"`, `public/`, `GEMS_API_KEY` to the frontend, health-gated start, `.dockerignore` files, a CI job that builds both images).


- **Why**: `docker compose up --build` cannot succeed today. `frontend/Dockerfile` copies `.next/standalone` and `public/`, but `frontend/next.config.mjs` does not set `output: "standalone"` and there is no `public/` directory, so the image build fails at the copy step. `docker-compose.yml` passes `BACKEND_URL` to the frontend service but not `GEMS_API_KEY`, so `frontend/middleware.ts` forwards requests without the header and every UI call returns 401. The `version: "3.9"` key is obsolete and Compose warns about it, and the backend service mounts `./backend:/app` with `--reload`, which is a development setting in what the README presents as the all-in-one deployment.
- **Size**: S.
- **Depends on**: nothing. A CI job that runs `docker compose build` would keep it working.

### 2. Return 404, not 500, for unknown gem ids that are not UUIDs

**Status: done** in PR 22 (`_find_gem()` in `routes/gems.py`; `PUT` and `DELETE` accept names too).


- **Why**: `GET /gems/{gem_id}` in `backend/app/routes/gems.py` looks the value up by name and then by id. When the name misses and the value is not a UUID, `get_gem_by_id` in `backend/app/services/gem_service.py` runs `.eq("id", gem_id)` against a `UUID` column, Postgres rejects the text and supabase-py raises, so the client gets a 500 for what is a plain not-found. `PUT` and `DELETE` accept ids only, so `frontend/lib/api.ts` and the MCP server cannot update or delete by name, while `GET` can.
- **Size**: S. Validate with `uuid.UUID(value)` before the id lookup, let `PUT` and `DELETE` resolve names too, add a test for each path.
- **Depends on**: 5 for the test harness, but the fix itself needs nothing.

### 3. Fix `variables_used` and order-dependent substitution

**Status: done** in PR 22 (`resolve_gem_detailed()` and single-pass `fill_variables()`).


- **Why**: in `resolve_gem` in `backend/app/routes/gems.py`, `variables_used` is computed as `sorted(provided & set(remaining_vars + list(provided)))`, which is always just the provided keys, so the field never says which variables the gem actually consumed. In `backend/app/services/gem_service.py`, `resolve_gem` fills variables with `str.replace` in dictionary order after expansion, so a value that itself contains `{other}` is substituted again on a later iteration, and the result depends on key order.
- **Size**: S. Compute `variables_used` as the intersection of provided keys with `extract_variables` of the pre-substitution prompt, and substitute with a single `re.sub` pass.
- **Depends on**: nothing.

### 4. Stop treating every `{...}` as a variable

**Status: done** in PR 22 for the identifier rule. No escape syntax was added; a literal `{name}` cannot be written in a prompt yet.


- **Why**: `_VAR_RE` in `backend/app/services/gem_service.py` is `\{([^{}]+)\}`, so any brace pair that is not a gem reference becomes a variable. A gem whose prompt shows a JSON example such as `{"name": "x"}` or a code snippet gets a variable named `"name": "x"`, which is stored in the `variables` column on save, rendered as an input field by `frontend/components/GemForm.tsx`, and reported as missing by `/gems/resolve`. The shipped gems avoid braces by accident (`prompt_enhancer` uses XML), so nothing in `tests/` catches it.
- **Size**: M. Restrict names to identifiers (`[A-Za-z_][A-Za-z0-9_]*`), define an escape for a literal brace, document it in the README gem syntax table and in `prompts/`, and add tests with JSON and code in prompts.
- **Depends on**: nothing, but decide the escape syntax before 14 so version history never has to migrate prompt text.

### 5. Resolver and route tests with a fake database

**Status: done** in PR 22 (`tests/conftest.py`, `test_resolver.py`, `test_routes.py`, `pytest.ini`; 29 tests). CRUD writes are still untested.


- **Why**: `tests/test_gem_service.py` covers only `extract_variables` and `extract_gem_refs`; `tests/test_smoke.py` is `assert True` from the project template. The actual product, `resolve_gem` (depth limit, cycle detection, variable propagation into embedded gems, missing gem errors) and the auth dependency in `backend/app/auth.py` have no tests, so items 2 to 4 cannot be fixed with confidence. The `sys.path.insert` at the top of each test file is a sign that the test layout was never settled.
- **Size**: M. Monkeypatch `get_gem_by_name` with an in-memory dict for resolver tests; use FastAPI's `TestClient` with `GEMS_API_KEY` set for route tests (401 without the header, 200 with it, 404 and 400 paths); add a `conftest.py` or a `pytest` `pythonpath` setting and drop the path hacks.
- **Depends on**: nothing. Unlocks 2, 3, 4, 12.

### 6. Constant-time key check, no provider errors in responses

**Status: done** (provider errors in PR 19, `secrets.compare_digest` in PR 22).


- **Why**: `require_api_key` in `backend/app/auth.py` compares with `x_api_key != expected`, which is not constant time; use `secrets.compare_digest`. `backend/app/routes/chat.py` returns `str(exc)` from any provider exception as the 502 `detail` and as an SSE `error` event, and `chat_with_gem` and `create_gem` in `backend/mcp_server.py` do the same, so provider error bodies (which can include request ids, model names and quota details) reach clients. Log them server side and return a short generic message.
- **Size**: S.
- **Depends on**: nothing.

### 7. Patched Next.js now, Next 15 next

**Status: done.** The 14.2.35 patch shipped in PR 19; the major migration went straight to Next 16 with React 19, ESLint 9 flat config and `proxy.ts` (15 would have been a stepping stone with no benefit). Tailwind 3 to 4 followed, driven by a build-time advisory in `postcss-selector-parser` that only Tailwind 4 could clear: theme colours moved from `tailwind.config.ts` into `@theme` in `globals.css`, `@tailwindcss/postcss` replaced the `tailwindcss` and `autoprefixer` PostCSS plugins, and the official upgrade tool renamed the handful of utilities that changed (`outline-none` to `outline-hidden`, `rounded` to `rounded-sm`).


- **Why**: `npm install` warns that `next@14.2.18` has a published security vulnerability (the December 2025 advisory). The fix is the latest 14.2.x patch, which Dependabot will now propose. Next 15 is the larger move: it restores `next.config.ts`, changes `useSearchParams` and caching defaults, and needs React 19.
- **Size**: S for the patch, M for Next 15.
- **Depends on**: CI build job (done). Do the patch before anything else in `frontend/`.

### 8. Turn the strict TypeScript lint rules back on

**Status: done** in PR 23.


- **Why**: `frontend/.eslintrc.json` extends only `next/core-web-vitals` and switches off `react/no-unescaped-entities`, because enabling `next/typescript` produced 19 errors: `catch (e: any)` in `app/gems/page.tsx`, `app/gems/[id]/page.tsx`, `app/gems/[id]/edit/page.tsx`, `app/chat/page.tsx` and `components/GemForm.tsx`; unused `useEffect`, `AvailableModels` and `chatApi` imports in `components/GemForm.tsx`; and unescaped quotes in three files. There is also a `react-hooks/exhaustive-deps` warning in `app/chat/page.tsx`. All are quick to fix, and the strict set is what catches real mistakes.
- **Size**: S.
- **Depends on**: nothing.

## Next

Design and security decisions that shape everything after them.

### 9. Decide the Supabase RLS and key model

**Status: decided and done** (ADR-006 in `DECISIONS.md`): single-tenant, the API key is the gate, the database trusts only the service role. The `allow_all` policy is gone, RLS has no policies for other roles, the anon key path is removed from `database.py` and `.env.example`, and `supabase/lock_down_rls.sql` updates existing installs. Multi-user stays item 21.

- **Why**: `supabase/schema.sql` enables row level security and then adds `allow_all ... USING (true) WITH CHECK (true)`, and the backend uses `SUPABASE_SERVICE_ROLE_KEY`, which bypasses RLS anyway. So RLS protects nothing today, while `SECURITY.md`, `CONTEXT.md` and ADR-001 all say to "tighten it before multi-user use" without saying how. The anon key path offered in `.env.example` would hit the same open policy. Either commit to single-tenant (drop the misleading policy, state that `GEMS_API_KEY` is the only gate, keep the service key off any public network) or design multi-user (an `owner_id` column, policies per user, user JWTs from Supabase Auth instead of the service key).
- **Size**: M for the single-tenant cleanup, L for multi-user.
- **Depends on**: a decision recorded in `DECISIONS.md`. Blocks 10, 14, 21.

### 10. Per-client API keys, and auth for a hosted MCP server

**Status: done with 41** (`GEMS_CLIENT_KEYS=name:key,name:key` in `backend/app/auth.py`; every check returns the client's name; the MCP server over HTTP sits behind the same keys). Not done: hashed keys in a table with scopes and an audit log; keys stay in the environment.

- **Why**: one shared `GEMS_API_KEY` serves the UI, scripts and anyone with the `.env`; there is no rotation, revocation or audit of who called what. The MCP server in `backend/mcp_server.py` imports the services directly, so it is not gated by the key at all; fine over stdio on one machine, but the moment it is run with an HTTP or SSE transport it is an open write path to the database and to paid LLM calls. Add an `api_keys` table (hashed key, label, scopes such as read-only, created and revoked timestamps), look keys up in `require_api_key`, and give the MCP server the same dependency when it runs over a network transport.
- **Size**: M.
- **Depends on**: 9.

### 11. Rate limits and spend guards on chat

- **Why**: `/chat` and `chat_with_gem` spend provider credit on every call with no per-key limit, `max_tokens` is fixed at 4096 in `backend/app/services/llm_service.py`, and `create_gem` over MCP accepts prompt text of any length that then feeds every future resolution. A simple per-key token bucket, a configurable `max_tokens` ceiling, and a size limit on `system_prompt` cover the obvious cases.
- **Size**: M.
- **Depends on**: 10 for per-key limits; a global limit needs nothing.

### 12. API consistency and versioning

- **Why**: several small inconsistencies will become compatibility promises once anyone scripts against the API. `GET /gems/{id}` accepts names, `PUT` and `DELETE` do not (see 2). The MCP server offers `create_gem` but no update or delete tool, so an agent cannot fix a gem it created. `search_gems` fetches every row and filters in Python, and the REST API has no search at all, so the UI filters client side. Errors are a mix of `HTTPException` details and `{"error": ...}` dicts from MCP tools. `app.version` in `backend/app/main.py` says `1.0.0` while the tags say `0.0.2`. Add `GET /gems?q=&tag=` backed by the existing GIN index, `update_gem` and `delete_gem` MCP tools, one error shape, and a `/v1` prefix before any external consumer exists.
- **Size**: M.
- **Depends on**: 5 for tests. Coordinate with 10 if scopes are added.

### 13. Streaming in the chat UI

**Status: done** with the run viewer: `chat.stream` in `lib/api.ts` reads the SSE body and the chat page renders chunks as they arrive.

- **Why**: `backend/app/routes/chat.py` already streams SSE when `stream=true`, but `frontend/lib/api.ts` only has a JSON `send` and `app/chat/page.tsx` shows a spinner until the whole response arrives. Already on the root roadmap; listed here for sequencing.
- **Size**: M. A `fetch` with `ReadableStream` parsing in `lib/api.ts` and incremental state updates in the chat page.
- **Depends on**: nothing.

### 14. Prompt version history

**Status: done** (a `gem_versions` table in both stores; `backend/app/services/version_service.py` records a version on every create and every save that changes something, written by the app rather than a Postgres trigger so SQLite and Supabase keep the same history; a gem from before history was kept gets its old state as version 1 on its first change; a note on each save; `GET /gems/{id}/versions`, `GET /gems/{id}/versions/{n}`, `GET /gems/{id}/diff` with a unified diff of the prompt, `POST /gems/{id}/versions/{n}/revert`, which saves the old fields as a new version and keeps the name; MCP tools `update_gem`, `gem_history`, `diff_gem_versions`, `revert_gem`; a History panel with diffs and Restore on the prompt page and a "what changed" note in the editor; `supabase/add_gem_versions.sql`; 7 tests). Not done: diffs between any two chosen versions in the UI (the API takes any pair).

- **Why**: the whole point of a prompt library is being able to see what changed and go back. Today the only trace is `updated_at`. For someone who edits prompts daily this is the single most valuable missing feature: the question is always "what changed between the version that worked and the one that stopped working", and nothing here can answer it. A `gem_versions` table filled by a trigger on `gems`, a `GET /gems/{id}/versions` route, a revert route, and a diff view in `app/gems/[id]/page.tsx`. Already on the root roadmap.
- **Size**: L.
- **Depends on**: 9 (ownership columns), 15 (so the schema change ships as a migration), 4 (so stored prompt text never needs rewriting).

### 15. Supabase CLI migrations instead of hand-run SQL

- **Why**: setup is "paste `supabase/schema.sql` into the SQL editor", and `supabase/add_prompt_enhancer.sql` exists because there was no other way to change an existing install. Nothing records which statements a given database has had applied. The Supabase CLI gives `supabase/migrations/` with ordered files, `supabase db push`, and a local Postgres for tests.
- **Size**: M.
- **Depends on**: nothing. Unlocks 14, 21, 22, and real integration tests in 5.

### 16. Make `prompts/` the single source of shipped gems

- **Why**: each shipped gem is written twice, once in `supabase/schema.sql` and once in `prompts/<name>.md`, and `STANDARDS.md` asks humans to keep them in sync. CI now checks that the names match, not the content. A small `scripts/sync_prompts.py` that renders the markdown files into the seed SQL (or upserts through the API) removes the duplication, and the CI check can then compare content.
- **Size**: S to M.
- **Depends on**: 15 if the output becomes a seed file; otherwise nothing.

### 17. One place for model defaults, drop retired models

**Status: done.** `backend/app/settings.py` holds the defaults (env-overridable); `GET /chat/models` and the MCP tool list each provider's live models with a cache and a pin; the frontend's hard-coded lists are gone; seeds and the eval use the new default; `supabase/update_default_models.sql` moves existing gems off retired models.

- **Why**: the default model string `claude-opus-4-5` appears in `backend/app/models.py`, `supabase/schema.sql`, `backend/mcp_server.py` and `evals/eval_prompt_enhancer.py`, and the `MODELS` dict in `backend/app/services/llm_service.py` still lists `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022` and `gpt-3.5-turbo`, which the providers have retired or are retiring. A single settings module (default model and provider from env, with the list of offered models loaded from config or from each provider's model list endpoint) keeps the UI dropdown honest.
- **Size**: S.
- **Depends on**: nothing.

### 18. Timeouts and retries in `llm_service.py`

**Status: done.** `LLM_TIMEOUT_SECONDS` and `LLM_MAX_RETRIES` on both clients, SDK failures wrapped in one `ProviderError`.

- **Why**: `ARCHITECTURE.md` already notes that timeouts and retries are inherited from SDK defaults and that there is no fallback. One slow provider call ties up a request indefinitely; a transient 429 or 5xx surfaces straight to the UI. Pass explicit `timeout` and `max_retries` to `AsyncAnthropic` and `AsyncOpenAI`, and map provider exceptions to one internal error type (which 6 needs anyway).
- **Size**: S.
- **Depends on**: nothing.

### 28. Evals per gem, runnable from the UI

**Status: done** (`eval_cases` and `eval_runs` in both stores; `backend/app/services/eval_service.py` with six checks: contains, not_contains, all_of, equals, json against a small schema subset, and an AI judge that ends with a verdict; there is deliberately no regex check, since a pattern typed into the UI and run on the server is an injection risk. Every run is recorded with the gem's version from item 14 and compared with a baseline (the first run until another is chosen), listing regressions and fixes. Spend guard: an estimate before every run (model calls, rough tokens, free when the AI runs on this PC), a per-run call cap `GEMS_EVAL_MAX_CALLS` that a request cannot raise, and a per-answer cap `GEMS_EVAL_MAX_TOKENS`. Agent gems are answered by a full run; one that stops for approval fails its case. Routes under `/gems/{id}/evals`, MCP tools `add_gem_eval` and `run_gem_evals`, a Tests panel on the prompt page, `supabase/add_evals.sql`; 11 tests). The rate limits and spend guards for chat in item 11 are still open.

- **Why**: `evals/eval_prompt_enhancer.py` is one script for one gem, run by hand with an API key in the environment. A prompt library earns its keep when every gem can carry a handful of input and expected-output pairs and a change can be scored before it is saved. That turns "I think this version is better" into a number, and it is the check that makes 14 (history) and 30 (side-by-side) useful rather than decorative. Store cases in a `gem_evals` table (input, expected, check type: contains, regex, JSON schema, LLM judge), add `POST /gems/{id}/evals/run`, show the score on the detail page, and record the baseline so a regression is visible. Keep live-API runs explicit and costed, as `STANDARDS.md` already requires.
- **Size**: M.
- **Depends on**: 15 (schema change as a migration), 11 (spend guard, since every run costs money).

### 29. Typed variables with descriptions and defaults

**Status: done** (a `variable_specs` column on gems in both stores: description, type (text, long_text, number, choice with options, boolean), default, required; specs are cleaned on save to the blanks the prompt has, and an impossible spec is refused. `gem_service.resolve_gem_detailed` fills defaults and checks values, with the embedded gems' specs applied and the outer gem winning; chats, runs and tests stop with a plain message, while the resolve preview reports `variable_errors` and `variables_defaulted`. Blanks without a spec behave as before. Specs are part of the version history and a past version in Compare uses its own. MCP `list_gems`, `get_gem` and the agent tool `get_gem` return `variables_schema` as a JSON schema; MCP `create_gem` and `update_gem` take specs. A Blanks section in the editor and typed inputs on the chat, prompt, Compare and Tests views. The editor now detects blanks with the backend's rule, so `{{gem:...}}` is no longer listed as one. `supabase/add_variable_specs.sql`; 8 tests).

- **Why**: a variable today is only a name scraped from the prompt by `extract_variables`. Nothing says what `{tone}` expects, whether it is required, or what a sensible default is. That makes a gem usable only by the person who wrote it, and it makes the MCP tools blind: an agent calling `resolve_gem_prompt` cannot know which values to supply. Add a `variable_specs` JSON column (name, description, type, enum values, default, required), validate on resolve, render proper inputs in `GemForm.tsx` and the chat page, and expose the specs in `list_gems` and `get_gem` so MCP clients can fill them correctly.
- **Size**: M.
- **Depends on**: 4 (variables are identifiers), 15 (migration). Unlocks a much better 12 (API shapes) and 31.

## Later

Worth doing once the foundations above are in.

### 19. Resolver query batching and a prompt size budget

- **Why**: ADR-003 accepts N+1 Supabase queries per nested gem. `engineering_lead` costs three round trips; a wider tree costs one per unique gem. Fetch all referenced gems of a level with one `in_` query, or cache by name and `updated_at` for a short TTL. Also enforce a resolved-prompt length ceiling, since nothing stops a tree from producing a prompt larger than any model's context.
- **Size**: M.
- **Depends on**: 5 for regression tests.

### 20. Structured logging and a real health check

- **Why**: `/health` in `backend/app/main.py` returns `ok` without touching Supabase, and `ARCHITECTURE.md` lists telemetry as "none". Add JSON logs with request ids, never logging keys or prompt bodies (as `STANDARDS.md` requires), and make `/health` check the database connection.
- **Size**: M.
- **Depends on**: nothing.

### 21. Multi-user accounts

- **Why**: the natural next step if more than one person shares an instance: Supabase Auth in the Next.js app, `owner_id` on gems, per-user keys, and RLS that finally does something. Everything about it depends on the model chosen in 9. Sequence it after 14, 28 and 29: a second person wants in once there is history to review, scores to compare and variables they can understand without reading the prompt.
- **Size**: L.
- **Depends on**: 9, 10, 15.

### 22. Gem import and export

**Status: moved to Now by ADR-013** (phase 2, activate). The scope grows from moving a library between instances to getting someone's existing prompts in without effort: paste instructions from ChatGPT custom instructions, Claude projects or Cursor rules; import Markdown and JSON files; let an AI split them into named gems with descriptions, tags and blanks, suggest improvements, and point out duplicates and near duplicates before anything is saved. Export stays the hand-readable bundle described below, and is the format sharing (56) builds on.

- **Why**: moving a library between instances, or backing it up, has no supported path. A JSON or YAML bundle with gems and their references, exported by a route and a script, imported with conflict handling. Already on the root roadmap. For a practitioner this is also how a library is shared with a colleague or published alongside a blog post, so the format should be readable by hand.
- **Size**: M.
- **Depends on**: 15 for a stable schema, 14 if versions should travel too.

### 23. Backend packaging, lock file, one-command dev

- **Why**: the backend is a loose directory with `sys.path` hacks in `tests/`, `evals/` and `backend/mcp_server.py`; the dependency conflict that blocked installation went unnoticed because nothing resolves and locks the set. A `pyproject.toml` with the app as a package, console entry points for the API and the MCP server, a lock file (uv or pip-tools), a `pytest` `pythonpath` setting, and a cross-platform task runner to pair with `scripts/setup.ps1` and `scripts/test.ps1`.
- **Size**: M.
- **Depends on**: nothing.

### 24. Frontend tests

- **Why**: `frontend/` has no tests at all. A Playwright smoke run against a mocked `/api` (list gems, create one, resolve preview, chat) and a component test for the variable detection in `components/GemForm.tsx` would catch the kind of regressions that the Suspense and config problems were.
- **Size**: M.
- **Depends on**: 8 so lint is strict first.

### 25. One version source and a tidy release process

**Status: done** with 0.3.0: `backend/app/version.py` feeds the API, `frontend/package.json` and the README badge carry the same string, CI fails when they or the changelog's top section disagree, and the version sequence restarts above the out-of-order 0.1.0 and 0.2.0 entries.

- **Why**: `CHANGELOG.md` lists 0.1.0 and 0.2.0 before 0.0.2, the only tag is `v0.0.2`, `backend/app/main.py` says `1.0.0`, and `frontend/package.json` says `1.0.0`. Pick a single source (a `VERSION` file or `pyproject.toml`), read it in the API root response and the README badge, and make the next tag `v0.3.0` or `v0.1.0` after deciding what 0.x means for this project. The release workflow added in the hygiene PR already builds release notes from the changelog section for the tag.
- **Size**: S.
- **Depends on**: nothing.

### 26. Screenshots, API reference, resolution guide

- **Why**: the UI is the most visible part of the project and the README has no picture of it. The REST API is documented only by Swagger on a running server, and the MCP tool list lives in a docstring in `backend/mcp_server.py` and in `ARCHITECTURE.md`. Add `docs/screenshots/`, export `openapi.json` into `docs/` in CI, and write a short page on how resolution works (depth, cycles, variable order, the escape from 4) with worked examples.
- **Size**: S to M.
- **Depends on**: 4 for the final syntax.

### 27. Split-deploy guide

- **Why**: `CONTEXT.md` and `ARCHITECTURE.md` mention Fly.io, Railway, Render and Vercel, and `next.config.mjs` and `CORS_ORIGINS` are built for it, but there is no walkthrough. One page with the env vars on each side, TLS in front of uvicorn, and the MCP server's place in that picture.
- **Size**: S.
- **Depends on**: 1 (working images), 27 can reuse the compose file.

### 32. Agent tools from remote MCP servers and HTTP endpoints

**Status: MCP servers done.** `backend/app/agents/mcp_sources.py` reads `configs/mcp_servers.json` (Claude Desktop's shape, stdio or streamable HTTP), lists each server's tools as `<server>.<tool>` with `<server>.*` wildcards, calls them through a fastmcp client, and marks them risky unless the entry says otherwise; the tool picker groups by server. The seed agent `rea_analyst` uses it. Plain HTTP endpoints as tools are still open.

- **Why**: ADR-007 shipped the loop with three built-in tools about the library itself. The useful agents need the user's own tools. FastMCP can act as a client, so a gem could list a remote MCP server (the same config a user pastes into Claude Desktop) and get its tools; a plain HTTP tool described by a JSON schema covers the rest. Both plug into `backend/app/agents/tools.py` as more sources behind the same registry, and both need an allowlist of hosts and a timeout.
- **Size**: M.
- **Depends on**: 33 (done), so remote tools that write can be marked risky from day one.

### 33. Approval gates with pause and resume

**Status: done.** A risky call without `allow_risky` saves the loop state on the run (`runs.state`), sets `waiting_approval` and emits `approval_requested`; `POST /runs/{id}/approve` (and the MCP `approve_run` tool) resumes from that call, approving or denying, with the rest of the run streamable; the chat bubble and the run page show Approve and Deny.

- **Why**: today a tool marked risky is simply refused unless the run opts in with `allow_risky`. Real use needs the run to pause, ask, and continue: a `waiting_approval` status, the pending call stored on the run, and `POST /runs/{id}/approve` that resumes the loop from the recorded messages. The run record already holds everything needed to rebuild the conversation.
- **Size**: M.
- **Depends on**: nothing. Needed before 32 adds tools that write.

### 34. Run viewer in the UI

**Status: done.** `GemForm` has a kind select and a tool picker from `GET /agents/tools`; the chat page runs agent gems with `agents.stream` and shows turns, tool calls and results as they happen, with a link to `app/runs/[id]`, which replays any stored run; cards and the detail page show the kind and tools. Not yet: a list of past runs (there is no list endpoint).

- **Why**: runs are only readable over REST and MCP. The chat page is the natural run viewer: pick an agent gem, send a message, watch the events stream in (turns, tool calls and results, tokens), and open an old run by id. This is where item 13 (streaming) lands, since `POST /agents/{name}/runs` already streams. `GemForm` also needs `kind` and a tool picker from `GET /agents/tools`.
- **Size**: M.
- **Depends on**: nothing.

### 35. Managed Agents as an execution backend

- **Why**: for Anthropic, Managed Agents can run the loop and host a sandbox with bash, files and code execution, which the in-process loop will never offer. An agent gem could be marked `backend: managed` and synced as an agent object, with sessions started per run and the session id and events mirrored into `runs`. The definition and the run record stay the same, so evals and the viewer keep working.
- **Size**: M.
- **Depends on**: 32 (tool definitions in one shape), 15 (schema change as a migration).

### 30. Side-by-side runs

**Status: done** (`backend/app/services/compare_service.py`: two to four columns, each a version from the history and an AI; one question through every column at the same time, or the gem's tests through every column as a pass and fail grid with totals, not recorded as eval runs. A past version is rebuilt from its stored prompt, provider and model with the new `gem_service.resolve_text`; the prompts it embeds resolve as they are now. An assistant runs its full loop, so only its current version can be compared, on different AIs. The call cap and the free-on-this-PC estimate from item 28 apply. `POST /gems/{id}/compare`, `/compare/tests`, `/compare/estimate`, the MCP tool `compare_gem`, and a Compare page reached from the prompt page; 10 tests). Not done: streaming each column as it answers; the columns appear together when all have answered.

- **Why**: the chat page runs one gem against one model. The everyday prompting question is comparative: this version or the last one, this model or that one, same input. A compare view that takes one input and two configurations (gem version from 14, or model and provider override) and shows the outputs next to each other, with the eval score from 28 if cases exist, is where the library becomes a workbench. The backend already has everything it needs; this is mostly `app/chat/page.tsx` and a small compare route that runs two completions.
- **Size**: M.
- **Depends on**: 14 for version-to-version compare, 13 so both panes stream; model-to-model compare needs neither.

### 31. Few-shot examples as first-class data

**Status: done** (an `examples` list on gems in both stores: input, output, a note for people; at most 50, empty ones dropped. The resolver renders each gem's examples as literal text inside `<examples>` tags at its `{{examples}}` marker, or at the end, after blanks are filled, so braces in an example never collide with the variable syntax; embedded gems bring their own, and the marker is never taken for a blank. Examples are versioned with item 14, a past version in Compare uses its own, and `POST /gems/{id}/examples/{index}/test` turns one into a judged test for item 28. MCP `get_gem` returns them and `add_gem_example` adds one; the resolve response reports `examples_used`. An Examples section in the editor (add, reorder, remove), an Examples card on the prompt page with "Make a test from it", and "Save as an example" on chat answers. `supabase/add_examples.sql`; 7 tests).

- **Why**: most strong prompts carry examples, and in this library they live inline in `system_prompt`, so adding or swapping one means editing the whole body and `prompts/<name>.md` by hand. Store examples as a list on the gem (input, output, optional note), render them into the resolved prompt at a marker such as `{{examples}}` inside `<examples>` tags, and let the UI add, reorder and remove them. Examples then version with 14, can be reused by 28 as eval cases, and stop colliding with the variable syntax.
- **Size**: M.
- **Depends on**: 4 (syntax decisions), 15 (migration), 29 (the same spec mechanism).

## Lapidary Console (ADR-009)

A Windows 11 application that installs, connects and manages the AI tools on a machine, with Lapidary as the hub. Items in dependency order.

### 36. OpenAI-compatible API: gems and agents as models for Open WebUI

**Status: done** (PR 42: `GET /v1/models` and `POST /v1/chat/completions` with bearer auth; prompt gems stream, agent gems run the loop and stream status lines).

- **Why**: Open WebUI, and most desktop and editor clients, speak the OpenAI chat completions API and nothing else. If Lapidary answers `GET /v1/models` with its gems and `POST /v1/chat/completions` with the gem's resolved prompt in front of the conversation, every gem and agent is a model in Open WebUI's picker, with Claude or GPT behind it as the gem says. The same bearer key as the REST API. Streaming in OpenAI's chunk format. Agent gems run the loop and stream their answer; their tool calls are visible in the run record.
- **Size**: M.
- **Depends on**: nothing. Done in `backend/app/routes/openai_compat.py`.

### 37. Console shell: Electron app, detection, config writers, sidecars

**Status: done** (PRs 42 and 46 to 49: the Electron shell, detection over an injected io, config writers, sidecars, the PowerShell view, the toolbox, the first run, the Doctor and the explainers).

- **Why**: the management surface. `desktop/` holds an Electron app whose main process detects what is installed (winget, Docker Desktop, Node, Claude Desktop, ChatGPT, Ollama, Open WebUI), writes client configs (Claude Desktop and ChatGPT MCP entries, an Open WebUI compose file with Lapidary, OpenAI and Ollama as providers), and starts the backend and the UI as sidecars; a console page shows status and offers the actions; the Lapidary UI is embedded for gems, chat and runs. The pure logic (paths, detection, config merging) lives in `desktop/lib/` with Node tests so it is checked on every platform.
- **Size**: L.
- **Depends on**: 36 for the Open WebUI connection to mean anything.

### 38. Storage layer with a SQLite backend

**Status: done.** `backend/app/storage/` holds the `Store` interface, `SQLiteStore` (one file, schema from `sqlite_schema.sql`, seeded from `supabase/schema.sql` on first use) and `SupabaseStore`; `gem_service` and `run_service` delegate to `get_store()`, chosen by `GEMS_STORAGE` (sqlite unless `SUPABASE_URL` is set). The packaged backend carries the seeds. Integration tests run the real routes against SQLite.

- **Why**: `gem_service.py` and `run_service.py` call supabase-py directly, so nothing runs without a Supabase project. The console needs a local database that works offline. One repository interface, two implementations (SQLite in the app data folder, Supabase as today), chosen by `GEMS_STORAGE`. `tests/conftest.py` already shows the shape.
- **Size**: L.
- **Depends on**: nothing; it also unlocks integration tests in CI.

### 39. Installers and updates through winget and Docker; Open WebUI management

**Status: done** (installs and updates through winget, Docker and npm from the Components view and the recipes; Open WebUI started from a generated compose file).

- **Why**: the Kaseya part. Install, update, start and stop from the console: Claude Desktop and ChatGPT through winget, Docker Desktop through winget, Ollama through winget, Open WebUI as a Docker container (or `pip install open-webui` where Docker is unwanted), REA through the bundled npm package, with versions and health shown on the dashboard and logs a click away.
- **Size**: L.
- **Depends on**: 37.

### 40. Settings and connections: keys, MCP servers, client configs

**Status: done** (the Settings view with keys in safeStorage, the model policy and local model; Connections writes the Claude Desktop and ChatGPT configs and, since item 41, shows the HTTP address).

- **Why**: keys for Anthropic and OpenAI entered once, stored with safeStorage, handed to the backend; the MCP server list edited in the UI; one button to register REA and Lapidary in Claude Desktop and ChatGPT and to point Open WebUI at Lapidary, OpenAI and Ollama; a connection test for each.
- **Size**: M.
- **Depends on**: 37, 39.

### 41. Lapidary's MCP server over HTTP for Claude Desktop and ChatGPT

**Status: done** (`backend/app/mcp_http.py` mounts the same FastMCP server on the API at `/mcp` as stateless streamable HTTP behind an ASGI key guard that takes `X-API-Key` or a bearer token; `GEMS_MCP_ALLOWED_HOSTS` for a tunnel's domain; per-client keys through `GEMS_CLIENT_KEYS` (item 10); the console's Connections view shows the address with copy buttons for the address, the key, a URL entry and an mcp-remote bridge entry; 6 tests). ChatGPT needs the address reachable over HTTPS from the internet, so a tunnel or a hosted deployment; the console does not set one up.

- **Why**: `backend/mcp_server.py` speaks stdio only. FastMCP also serves streamable HTTP; running it on localhost behind the API key lets ChatGPT (which only takes remote MCP) and Claude Desktop reach Lapidary's gems, agents and runs. Item 10's per-client keys belong here.
- **Size**: M.
- **Depends on**: 37.

### 42. Windows installer, CI build and smoke test, REA bundling, first run

**Status: partly done** (PR 52: the installer is built and the packaged backend is smoke-tested on every push to main; REA comes through npx on first use; the first run exists (item 47). Then: a per-machine installer with one administrator prompt, Lapidary Helper as a SYSTEM service for allowlisted installs and verified console updates, installed and checked on the CI runner, signing switched on by repository secrets, and the installer attached to each release with its checksum). Still open: signing credentials (desktop/README.md, Code signing) and running the console by hand on a real Windows 11 machine.

- **Why**: an NSIS installer from electron-builder, built on `windows-latest` with the backend as a PyInstaller single file, smoke-tested by launching and hitting `/health`; `rea-agents` bundled; a first-run screen that takes the keys, creates the database with the seed gems and opens the console.
- **Size**: M.
- **Depends on**: 37, 38, 40.

### 43. Lapidary Memory: observations across runs, chats and clients

**Status: done** (`memories` table with full-text search in both stores; `memory_service` with capture on every finished run, the `memory_summarizer` seed gem with the plain digest as the fallback, `<private>` stripping, three-step recall and the `<memory>` block for gems with `memory: true`; the four tools as built-in agent tools, MCP tools and `/memory` routes; the Memory page and the "remembers earlier work" checkbox in the web UI; `supabase/add_memory.sql` for existing installs; 13 tests). Later: embeddings behind the same interface, chats storing on request, the console showing memory on the Dashboard.

- **Why**: ADR-010. Every run and chat starts from nothing, and the console's whole point is that Claude Desktop, ChatGPT, Open WebUI and the agents share one place. Modelled on claude-mem: capture a compressed observation when a run finishes, keep it with full-text search in the storage layer, bring it back by search then fetch (`search_memory`, `get_memories`, `remember`, `forget`) as agent tools, MCP tools and REST, inject the top matches into gems marked `memory: true`, and show it all in a Memory view with delete. `<private>` text is never stored.
- **Size**: L.
- **Depends on**: 38 (done). Embeddings later, behind the same interface.

### 44. Local models as a provider, and the model policy

**Status: done.** `local` is a third provider over the OpenAI SDK with a base URL; `backend/app/services/router.py` implements the five modes with pins, overrides, role tags, availability and fallback, every decision with a reason; `GET /chat/policy` describes the world; the gem editor offers Auto and Local; the console's Settings asks "Which AI should we use?" and passes the answer to the backend. Nine router tests.

- **Why**: ADR-011 and ADR-012 together. The console manages Ollama already, and the reference stack shows what local models are for: the high-volume build and review work, with a frontier model kept for planning. A third provider, `local`, is any OpenAI-compatible server at `LOCAL_OPENAI_BASE_URL` (default Ollama's `http://127.0.0.1:11434/v1`), key optional; `available_models()` asks the server; the gem editor offers it; the console's Ollama entry fills the base URL. Above the providers, one setting, `GEMS_MODEL_POLICY`, with five modes a person picks in plain words: Local only (free, private), Online only (paid, by choice), Mix (planning and hard reasoning online, high-volume building and reviewing local, by rules), Let the system decide (the router chooses per task from what is installed, what has a key, the task's role and size, with fallback either way), and Hand pick (per gem and per run, as today). A gem may pin its provider; the policy decides for gems that do not; every run records which model answered and why. In the Basic first run this is the first question, worded for the person: "Which AI should we use?"
- **Size**: M.
- **Depends on**: 17 (done). Unlocks 47's no-key default path.

### 45. Gates: builder, tests, visual review, adversarial review, acceptance

**Status: done** (`pipelines` and `pipeline_runs` in both stores; `backend/app/agents/pipeline.py` runs the builder, then each gate with the task and the output, parses `VERDICT: PASS` or `FAIL`, feeds a failure back as findings and a memory lesson, retries up to `max_attempts`, pauses for a risky call or for acceptance and resumes from the saved state; routes under `/pipelines`, MCP tools `list_pipelines`, `run_pipeline`, `resume_pipeline`; the gate gems `test_runner` and `adversarial_reviewer` and the seed pipeline `build_and_check`; a Pipelines page and a run page in the web UI; `supabase/add_pipelines.sql`; 9 tests). A visual gate is a gate gem with a screenshot tool from an MCP server (item 32); none is shipped yet.

- **Why**: ADR-011, modelled on Ratchet Loop. A pipeline is an ordered list of gems with roles. The builder runs first; then each gate gem (a tester with `run_powershell` or a test tool, a visual reviewer with a vision model and screenshots from Playwright, an adversarial reviewer on a different model or provider) returns pass or fail with findings; a failure goes back to the builder with the findings and the pipeline retries up to a cap; acceptance is the existing approval gate. Every attempt is a run, and a failed gate's findings become a memory `lesson` (43). Surfaces: `POST /pipelines/{name}/runs`, a pipeline view in the UI, an MCP tool.
- **Size**: L.
- **Depends on**: 43, 44; 32 for a test or screenshot tool from an MCP server.

### 46. Workbench: parallel runs on worktrees; Codex and OpenCode as clients

- **Why**: ADR-011, modelled on Paseo. The console starts several runs or pipelines at once, each on its own git worktree when a repository is involved, and shows them side by side with their gates; Codex and OpenCode appear in Connections as MCP clients of Lapidary so they share its memory and gems.
- **Size**: L.
- **Depends on**: 45, 41.

## For the newcomer (ADR-012)

The person this is for does not know much about AI, installs the console, and should get something genuinely useful on day one. These items come before the rest of the console work.

### 47. Guided first run and recipes: outcomes in one click

**Status: done** (the Start view in the console: Basic asks "Which AI should we use?" and "What would you like?" and runs the recipe with progress and "here is what you can do now"; Advanced walks through components, AI, storage, connections, ports and folders, permissions, logging, and shows every file and command before applying; an Advanced toggle on every screen; eight recipes planned by `desktop/lib/recipes.js` from the machine's state; the newcomer gems `study_buddy`, `writing_coach`, `research_assistant` and `program_builder`). Still open from the description: a test button on the keys form, and the builder's review gates (item 45).

- **Why**: two kinds of people arrive at the first run. The Basic path is for anyone, a student, a parent, a marketing person: it asks two questions in plain words. First, "Which AI should we use?", with five answers: "The free one on this PC" (private, nothing leaves the computer, works offline), "The online ones" (Claude and ChatGPT, smarter, paid by use with your own key), "A mix" (recommended: online for the hard thinking, the free one for the rest), "Decide for me" (the system picks per task from what is set up and says what it picked), and "I'll choose each time". Then, "What would you like?", and it offers recipes: a private chat on this PC (Ollama, a small model, Open WebUI, connected, done; free, nothing leaves the PC), help with homework, writing and everyday questions (the same chat with a few ready-made prompts), summarise or ask questions about my own documents privately (Open WebUI's document chat on local models), a research assistant over my own documents, notes and sources (in the spirit of SurfSense or NotebookLM: collect sources, ask across them, get cited answers and summaries, all on this PC or with online help for the hard parts), build me a program (a builder agent with the gates of item 45, local models doing the volume, an online model doing the planning when a key exists), let Claude and ChatGPT use my prompts (keys form with a test button, the apps connected; explained as paid by use), an assistant that can run safe PowerShell for me (the `windows_operator` gem, with the approval gate explained), understand how an app works (REA and the `rea_analyst` gem). Each recipe installs and connects what it needs, shows progress in plain words, and ends with "here is what you can do now". Cloud keys are offered as an upgrade, never required. The Advanced path is for the system administrator: a walk through each choice (components, cloud keys or local models or both, SQLite or Supabase, which apps to connect, ports and data folders, what assistants may do without asking, logging and updates), with the same forms the Settings screens use and a summary of everything the console will write before it writes it. An Advanced toggle, available later on every screen, shows the details the Basic path hides.
- **Size**: L.
- **Depends on**: 37, 39, 40, 44 (local models so the default path needs no key).

### 48. Plain-language pass over the console and the web UI

**Status: done** (web UI: Prompts and assistants, blanks to fill, built from others, which AI, the prompt as sent, what the assistant did, "asks first" for risky tools, and `frontend/lib/words.ts` with `explain()` so every error says what to do next; console: connect instead of MCP, keys named by the AI they unlock, the acronyms and file names behind the Advanced switch, installer and Docker failures saying what to do; the API, the URLs and the docs keep the original words).

- **Why**: "MCP", "gem", "run", "provider", "RLS" are our words. The console and the web UI get a pass against ADR-012: connect instead of MCP, prompts and assistants instead of gems and agents where a newcomer reads, "what the assistant did" for runs, acronyms only in details, every error message saying what to do next. The retro look stays.
- **Size**: M.
- **Depends on**: nothing.

### 49. Doctor: self-check with offered fixes

**Status: done** (a Doctor view, key 3, and an "Ask the Doctor" button on the Dashboard. `desktop/lib/doctor.js` turns the facts the console gathers into findings in plain words, each with its fix where one click can do it: Lapidary and the web UI up or their ports taken by another program; the AI choice against what is there, so Ollama missing, stopped or without a model, or a cloud key missing or refused by the service; the private chat with Docker missing, stopped or the port taken; Claude Desktop and ChatGPT installed but not connected, or a damaged config; PowerShell 7; and a newer console release. Fixes reuse the recipe runner: restart, install, start, download, connect, open, or jump to Settings. 7 tests.)

- **Why**: when something does not work, a newcomer cannot read logs. A Doctor view runs the checks (services up, keys valid, Docker running, ports free, Ollama has a model, connections written, versions current) and offers the fix for each failure in one click, with a plain explanation.
- **Size**: M.
- **Depends on**: 37, 39.

### 50. Explainers: every screen says what it is for and why

**Status: done** (one sentence under the heading of every console view: Dashboard, Components, Connections, Settings, Logs, PowerShell, Lapidary; a cost or needs line on every component, green, after its blurb; a blurb and a needs line on every toolbox entry, with the category and source columns moved behind the Advanced switch; one sentence on the web UI's library, chat, run and prompt pages. Tests check that every component and toolbox entry has them.)

- **Why**: one sentence per component and per screen, in the person's language: what it is, what you get from it, what it costs or needs. Started in this PR with a blurb on every component and toolbox entry.
- **Size**: S.
- **Depends on**: nothing.

## For the prompt practitioner

The engineering items make the project safe to run. These are the ones that would make it worth recommending to someone who writes prompts for a living and has never heard of it, in the order they pay off:

1. Version history with diffs and rollback (14), done.
2. Evals per gem, run from the UI, with a recorded baseline (28), done.
3. Side-by-side runs across versions and models (30), done.
4. Typed variables with descriptions and defaults, exposed over MCP (29), done.
5. Few-shot examples as data rather than prose (31), done.
6. Import and export in a hand-readable format (22), now in phase 2 of the growth plan.
7. Accounts and sharing, once there is something worth sharing (9, 10, 21).

What the project already does well for that person: one named home per prompt, composition of small prompts into larger ones, and the MCP server, which lets Claude Desktop and Cursor fetch the right prompt themselves instead of the user pasting it.

## Growth (ADR-013)

These items carry the growth plan. They come first, in phase order. Each says what the visitor or user should be able to do, because that is how it will be judged.

### 51. Live demo in the browser: no install, no key

- **Why**: the first investment. A visitor opens a link and, without installing anything or entering a key, watches an ordinary prompt become a reusable, tested assistant: write or pick a prompt, add a blank, run it, improve it, and compare the original and the improved answers side by side with the tests scoring both. A hosted instance of the web UI in a read-only demo mode with a fixed library, a per-visitor sandbox that resets, and answers from a small hosted model or recorded responses so it costs nothing to keep up and cannot be abused. The demo ends with the two ways to keep going: install the console, or run it with Docker.
- **Size**: L.
- **Depends on**: 30 and 28 (compare and tests, done), 55's rate limits before any live model sits behind it.

### 52. Repository presentation: positioning, screenshots, demo video, install options, consistent docs

**Status: partly done** with ADR-013: the README leads with the positioning and real screenshots, the install options are side by side, and `CONTEXT.md`, `SECURITY.md`, `CONTRIBUTING.md`, `SUPPORT.md`, `STANDARDS.md`, the root roadmap and the architecture prose now agree with the code; the GitHub description leads with the positioning and the topics cover local models, testing, Windows and self-hosting. A 64-second demo video sits at the top of the README as a loop that opens the full video with sound (`docs/demo/`). Still open: a social preview image (uploaded in the repository settings).

- **Why**: the repository is the storefront. It showed no picture of the product, and some documents contradicted the code, which costs trust for a tool that holds AI credentials and runs tools on people's computers. From now on a document that disagrees with the code is a bug.
- **Size**: S to M.
- **Depends on**: nothing.

### 53. Gem gallery: curated gems with preview, example output, quality score, one-click install

- **Why**: people need something useful before they create anything themselves. 25 to 50 curated prompts and assistants across programming, writing, research, sales, IT and everyday productivity. Each has a one-line purpose, a preview of the prompt, an example question and answer, its tests and the score they give, and an Install button that adds it to your library with its history starting at version 1. Built on the export format of 22, so a gallery entry is just a published bundle. Community ratings, forks and public sharing come later with 56.
- **Size**: L.
- **Depends on**: 22 for the bundle format, 28 for the quality score.

### 54. Visual builder for assistants, tools, tests and approvals

- **Why**: pipelines and gates (45) already run work like "research a topic, draft a report, fact-check it, ask for approval", but only someone who writes JSON can set one up. A canvas where you connect assistants, the tools each may use, the tests and gates between steps, and where a person approves, saved as an ordinary pipeline so the API, MCP and the console run it unchanged.
- **Size**: L.
- **Depends on**: 45 (done), 33 (done).

### 55. Usage, cost and performance dashboard with spend limits, alerts and rate limits

- **Why**: a reason to keep opening Lapidary, and the guard rails it still lacks. Per gem: how often it is used, which models answered, approximate cost, response time, and how its tests score over time. Monthly spending limits, usage alerts and per-key rate limits close item 11. The data is already in `runs`, `run_events` and `eval_runs`; token prices per model are the new piece.
- **Size**: M to L.
- **Depends on**: 11 (absorbed here), 20 for structured logs.

### 56. Sharing: publish a gem as a link, install someone's gem, update without losing your changes

- **Why**: growth comes from people handing a good gem to someone else. Publish a gem (and what it is built from) as a link; anyone can preview it and install it; when the author improves it, the person who installed it gets the update as a new version merged with their own edits, with a diff to review, like a fork that can pull. The gallery (53) is the curated front of the same mechanism.
- **Size**: L.
- **Depends on**: 22, 14 (done), 53.

### 57. Trust for teams: accounts and roles, approval workflows, scoped keys, signed installer, security review

- **Why**: before Lapidary is deployed beyond one person or recommended to an organization. User accounts and role-based permissions (absorbs 21), approval workflows for publishing and for risky tools, API keys that are hashed and scoped to what a client may do, the Windows installer signed (42; the setup is in `desktop/README.md`, it waits on credentials), and a security review of the backend, the MCP surfaces and the helper service with the findings published.
- **Size**: L.
- **Depends on**: 9, 10 (done), 21, 42.

### 58. Measure first gem, seven-day return and sharing

- **Why**: the three numbers that say whether the plan works: the share of visitors who create their first gem, the share who use it again seven days later, and the number who share a gem with another person. The hosted demo and the gallery can count them directly. A self-hosted install counts nothing unless its owner opts in, because local-first is a promise; the console asks once, in plain words, and the setting is visible in the Doctor.
- **Size**: M.
- **Depends on**: 51, 53, 56 for the events to count.
