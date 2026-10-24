# gemsAPI improvement roadmap

A prioritised list of improvements to the project itself, written on 2026-10-23 from a read of the code at v0.0.2 plus the repository hygiene pull request that added this file. The root [ROADMAP.md](../ROADMAP.md) tracks delivery status of agreed items; this file is the reasoning: what to do, why, how big it is, and what it waits on.

Sizes: **S** is under half a day, **M** is one to three days, **L** is a week or more. Items are numbered so they can be referenced from issues and from the root roadmap.

## Already done in the hygiene pull request

These were found during the audit and fixed because CI could not pass without them. They are listed so the reasoning is on record.

- `backend/requirements.txt` was uninstallable: `supabase==2.9.1` needs `httpx<0.28`, `fastmcp==2.2.0` needs `httpx>=0.28.1`. Pins moved to `supabase==2.16.0` and `httpx==0.28.1`; the 8 unit tests pass on that set.
- `frontend/next.config.ts` was never loaded: Next.js 14 only reads `next.config.js` or `.mjs`, so `next dev`, `next lint` and `next build` all exited with an error. Renamed to `next.config.mjs` with the same rewrite rule.
- `frontend/app/chat/page.tsx` called `useSearchParams()` outside a Suspense boundary, which stops `next build` from prerendering `/chat`. Wrapped.
- Three ruff findings and a `ruff.toml` so the rule set does not drift with ruff releases; `frontend/.eslintrc.json` so `next lint` runs non-interactively; `frontend/package-lock.json` so `npm ci` works in CI and in `frontend/Dockerfile`.

## At a glance

| # | Item | Area | Size | Group |
|---|---|---|---|---|
| 1 | Make Docker Compose work end to end | DX, deployment | S | Now |
| 2 | 404, not 500, for unknown non-UUID gem ids | Correctness | S | Now |
| 3 | Fix `variables_used` and order-dependent substitution | Correctness | S | Now |
| 4 | Stop treating every `{...}` as a variable | Correctness | M | Now |
| 5 | Resolver and route tests with a fake database | Tests | M | Now |
| 6 | Constant-time key check, no provider errors in responses | Security | S | Now |
| 7 | Patched Next.js, then Next 15 | Security, DX | S then M | Now |
| 8 | Turn the strict TypeScript lint rules back on | DX | S | Now |
| 9 | Decide the Supabase RLS and key model | Security | M to L | Next |
| 10 | Per-client API keys, and auth for a hosted MCP server | Security | M | Next |
| 11 | Rate limits and spend guards on chat | Security, cost | M | Next |
| 12 | API consistency and versioning | API, MCP | M | Next |
| 13 | Streaming in the chat UI | Product | M | Next |
| 14 | Prompt version history | Product | L | Next |
| 15 | Supabase CLI migrations instead of hand-run SQL | DX, data | M | Next |
| 16 | Make `prompts/` the single source of shipped gems | DX, data | S to M | Next |
| 17 | One place for model defaults, drop retired models | Correctness | S | Next |
| 18 | Timeouts and retries in `llm_service.py` | Reliability | S | Next |
| 19 | Resolver query batching and a prompt size budget | Performance | M | Later |
| 20 | Structured logging and a real health check | Operations | M | Later |
| 21 | Multi-user accounts | Product, security | L | Later |
| 22 | Gem import and export | Product | M | Later |
| 23 | Backend packaging, lock file, one-command dev | DX | M | Later |
| 24 | Frontend tests | Tests | M | Later |
| 25 | One version source and a tidy release process | Release | S | Later |
| 26 | Screenshots, API reference, resolution guide | Docs | S to M | Later |
| 27 | Split-deploy guide | Docs | S | Later |

## Now

Things that are broken or that a first contributor would trip over this week.

### 1. Make Docker Compose work end to end

- **Why**: `docker compose up --build` cannot succeed today. `frontend/Dockerfile` copies `.next/standalone` and `public/`, but `frontend/next.config.mjs` does not set `output: "standalone"` and there is no `public/` directory, so the image build fails at the copy step. `docker-compose.yml` passes `BACKEND_URL` to the frontend service but not `GEMS_API_KEY`, so `frontend/middleware.ts` forwards requests without the header and every UI call returns 401. The `version: "3.9"` key is obsolete and Compose warns about it, and the backend service mounts `./backend:/app` with `--reload`, which is a development setting in what the README presents as the all-in-one deployment.
- **Size**: S.
- **Depends on**: nothing. A CI job that runs `docker compose build` would keep it working.

### 2. Return 404, not 500, for unknown gem ids that are not UUIDs

- **Why**: `GET /gems/{gem_id}` in `backend/app/routes/gems.py` looks the value up by name and then by id. When the name misses and the value is not a UUID, `get_gem_by_id` in `backend/app/services/gem_service.py` runs `.eq("id", gem_id)` against a `UUID` column, Postgres rejects the text and supabase-py raises, so the client gets a 500 for what is a plain not-found. `PUT` and `DELETE` accept ids only, so `frontend/lib/api.ts` and the MCP server cannot update or delete by name, while `GET` can.
- **Size**: S. Validate with `uuid.UUID(value)` before the id lookup, let `PUT` and `DELETE` resolve names too, add a test for each path.
- **Depends on**: 5 for the test harness, but the fix itself needs nothing.

### 3. Fix `variables_used` and order-dependent substitution

- **Why**: in `resolve_gem` in `backend/app/routes/gems.py`, `variables_used` is computed as `sorted(provided & set(remaining_vars + list(provided)))`, which is always just the provided keys, so the field never says which variables the gem actually consumed. In `backend/app/services/gem_service.py`, `resolve_gem` fills variables with `str.replace` in dictionary order after expansion, so a value that itself contains `{other}` is substituted again on a later iteration, and the result depends on key order.
- **Size**: S. Compute `variables_used` as the intersection of provided keys with `extract_variables` of the pre-substitution prompt, and substitute with a single `re.sub` pass.
- **Depends on**: nothing.

### 4. Stop treating every `{...}` as a variable

- **Why**: `_VAR_RE` in `backend/app/services/gem_service.py` is `\{([^{}]+)\}`, so any brace pair that is not a gem reference becomes a variable. A gem whose prompt shows a JSON example such as `{"name": "x"}` or a code snippet gets a variable named `"name": "x"`, which is stored in the `variables` column on save, rendered as an input field by `frontend/components/GemForm.tsx`, and reported as missing by `/gems/resolve`. The shipped gems avoid braces by accident (`prompt_enhancer` uses XML), so nothing in `tests/` catches it.
- **Size**: M. Restrict names to identifiers (`[A-Za-z_][A-Za-z0-9_]*`), define an escape for a literal brace, document it in the README gem syntax table and in `prompts/`, and add tests with JSON and code in prompts.
- **Depends on**: nothing, but decide the escape syntax before 14 so version history never has to migrate prompt text.

### 5. Resolver and route tests with a fake database

- **Why**: `tests/test_gem_service.py` covers only `extract_variables` and `extract_gem_refs`; `tests/test_smoke.py` is `assert True` from the project template. The actual product, `resolve_gem` (depth limit, cycle detection, variable propagation into embedded gems, missing gem errors) and the auth dependency in `backend/app/auth.py` have no tests, so items 2 to 4 cannot be fixed with confidence. The `sys.path.insert` at the top of each test file is a sign that the test layout was never settled.
- **Size**: M. Monkeypatch `get_gem_by_name` with an in-memory dict for resolver tests; use FastAPI's `TestClient` with `GEMS_API_KEY` set for route tests (401 without the header, 200 with it, 404 and 400 paths); add a `conftest.py` or a `pytest` `pythonpath` setting and drop the path hacks.
- **Depends on**: nothing. Unlocks 2, 3, 4, 12.

### 6. Constant-time key check, no provider errors in responses

- **Why**: `require_api_key` in `backend/app/auth.py` compares with `x_api_key != expected`, which is not constant time; use `secrets.compare_digest`. `backend/app/routes/chat.py` returns `str(exc)` from any provider exception as the 502 `detail` and as an SSE `error` event, and `chat_with_gem` and `create_gem` in `backend/mcp_server.py` do the same, so provider error bodies (which can include request ids, model names and quota details) reach clients. Log them server side and return a short generic message.
- **Size**: S.
- **Depends on**: nothing.

### 7. Patched Next.js now, Next 15 next

- **Why**: `npm install` warns that `next@14.2.18` has a published security vulnerability (the December 2025 advisory). The fix is the latest 14.2.x patch, which Dependabot will now propose. Next 15 is the larger move: it restores `next.config.ts`, changes `useSearchParams` and caching defaults, and needs React 19.
- **Size**: S for the patch, M for Next 15.
- **Depends on**: CI build job (done). Do the patch before anything else in `frontend/`.

### 8. Turn the strict TypeScript lint rules back on

- **Why**: `frontend/.eslintrc.json` extends only `next/core-web-vitals` and switches off `react/no-unescaped-entities`, because enabling `next/typescript` produced 19 errors: `catch (e: any)` in `app/gems/page.tsx`, `app/gems/[id]/page.tsx`, `app/gems/[id]/edit/page.tsx`, `app/chat/page.tsx` and `components/GemForm.tsx`; unused `useEffect`, `AvailableModels` and `chatApi` imports in `components/GemForm.tsx`; and unescaped quotes in three files. There is also a `react-hooks/exhaustive-deps` warning in `app/chat/page.tsx`. All are quick to fix, and the strict set is what catches real mistakes.
- **Size**: S.
- **Depends on**: nothing.

## Next

Design and security decisions that shape everything after them.

### 9. Decide the Supabase RLS and key model

- **Why**: `supabase/schema.sql` enables row level security and then adds `allow_all ... USING (true) WITH CHECK (true)`, and the backend uses `SUPABASE_SERVICE_ROLE_KEY`, which bypasses RLS anyway. So RLS protects nothing today, while `SECURITY.md`, `CONTEXT.md` and ADR-001 all say to "tighten it before multi-user use" without saying how. The anon key path offered in `.env.example` would hit the same open policy. Either commit to single-tenant (drop the misleading policy, state that `GEMS_API_KEY` is the only gate, keep the service key off any public network) or design multi-user (an `owner_id` column, policies per user, user JWTs from Supabase Auth instead of the service key).
- **Size**: M for the single-tenant cleanup, L for multi-user.
- **Depends on**: a decision recorded in `DECISIONS.md`. Blocks 10, 14, 21.

### 10. Per-client API keys, and auth for a hosted MCP server

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

- **Why**: `backend/app/routes/chat.py` already streams SSE when `stream=true`, but `frontend/lib/api.ts` only has a JSON `send` and `app/chat/page.tsx` shows a spinner until the whole response arrives. Already on the root roadmap; listed here for sequencing.
- **Size**: M. A `fetch` with `ReadableStream` parsing in `lib/api.ts` and incremental state updates in the chat page.
- **Depends on**: nothing.

### 14. Prompt version history

- **Why**: the whole point of a prompt library is being able to see what changed and go back. Today the only trace is `updated_at`. A `gem_versions` table filled by a trigger on `gems`, a `GET /gems/{id}/versions` route, a revert route, and a diff view in `app/gems/[id]/page.tsx`. Already on the root roadmap.
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

- **Why**: the default model string `claude-opus-4-5` appears in `backend/app/models.py`, `supabase/schema.sql`, `backend/mcp_server.py` and `evals/eval_prompt_enhancer.py`, and the `MODELS` dict in `backend/app/services/llm_service.py` still lists `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022` and `gpt-3.5-turbo`, which the providers have retired or are retiring. A single settings module (default model and provider from env, with the list of offered models loaded from config or from each provider's model list endpoint) keeps the UI dropdown honest.
- **Size**: S.
- **Depends on**: nothing.

### 18. Timeouts and retries in `llm_service.py`

- **Why**: `ARCHITECTURE.md` already notes that timeouts and retries are inherited from SDK defaults and that there is no fallback. One slow provider call ties up a request indefinitely; a transient 429 or 5xx surfaces straight to the UI. Pass explicit `timeout` and `max_retries` to `AsyncAnthropic` and `AsyncOpenAI`, and map provider exceptions to one internal error type (which 6 needs anyway).
- **Size**: S.
- **Depends on**: nothing.

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

- **Why**: the natural next step if more than one person shares an instance: Supabase Auth in the Next.js app, `owner_id` on gems, per-user keys, and RLS that finally does something. Everything about it depends on the model chosen in 9.
- **Size**: L.
- **Depends on**: 9, 10, 15.

### 22. Gem import and export

- **Why**: moving a library between instances, or backing it up, has no supported path. A JSON or YAML bundle with gems and their references, exported by a route and a script, imported with conflict handling. Already on the root roadmap.
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
