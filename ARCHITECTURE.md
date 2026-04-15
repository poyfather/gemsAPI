# ARCHITECTURE

## Architecture Principles
- **Separation of concerns**: backend (Python/FastAPI), frontend (Next.js), and MCP server (FastMCP) are independent deployable units.
- **Provider abstraction**: all LLM calls route through `llm_service.py`, which presents a uniform `complete()` / `complete_stream()` interface regardless of provider.
- **Single source of truth**: gem content lives exclusively in Supabase; no gem state is held in memory or config files.
- **Fail-safe recursion**: gem resolution is depth-limited (10 levels) and cycle-detected before any database calls are made on a branch.
- **No client-side secrets**: the Next.js frontend never holds API keys; all LLM calls are proxied through the FastAPI backend.

## Component Model

```
┌────────────────────┐     HTTP/SSE      ┌─────────────────────────────────┐
│   Next.js UI       │ ◄────────────────► │   FastAPI Backend               │
│   (port 3000)      │   /api/* rewrite   │   (port 8000)                   │
│                    │                    │                                 │
│  - Gems library    │                    │  Routes:                        │
│  - Create / Edit   │                    │    GET/POST/PUT/DELETE /gems     │
│  - Chat tester     │                    │    POST /gems/resolve           │
│  - Resolve preview │                    │    POST /chat  (SSE stream)     │
└────────────────────┘                    │    GET  /chat/models            │
                                          │                                 │
                                          │  Services:                      │
┌────────────────────┐     stdio MCP      │    gem_service  — CRUD +        │
│   MCP Client       │ ◄────────────────► │      recursive resolver         │
│  (Claude Desktop,  │                    │    llm_service  — Anthropic /   │
│   Cursor, etc.)    │                    │      OpenAI abstraction         │
└────────────────────┘                    │                                 │
         ▲                                │  database.py — Supabase client  │
         │                                └────────────────┬────────────────┘
┌────────┴───────────┐                                     │ supabase-py
│  FastMCP Server    │                                     ▼
│  (mcp_server.py)   │                    ┌─────────────────────────────────┐
│                    │                    │   Supabase (Postgres)           │
│  Tools:            │                    │   Table: gems                   │
│  - list_gems       │                    │   RLS: open (tighten for prod)  │
│  - get_gem         │                    └─────────────────────────────────┘
│  - resolve_gem_    │
│    prompt          │                    ┌─────────────────────────────────┐
│  - chat_with_gem   │──────────────────► │   LLM Providers                 │
│  - create_gem      │                    │   Anthropic Messages API        │
│  Resources:        │                    │   OpenAI Chat Completions API   │
│  - gems://list     │                    └─────────────────────────────────┘
│  - gems://{name}   │
└────────────────────┘
```

## Inference and Data Flow

**Standard chat request:**
1. Frontend sends `POST /api/chat` with `gem_name`, `messages`, and optional `variables`.
2. Next.js rewrites `/api/*` → FastAPI backend.
3. `chat.py` calls `gem_service.resolve_gem(name, variables)`.
4. `resolve_gem` loads the gem from Supabase, expands `{{gem:ref}}` tags recursively (depth-first, cycle-checked), fills `{variable}` placeholders.
5. Resolved prompt + messages passed to `llm_service.complete()` or `complete_stream()`.
6. Response returned as JSON or SSE stream.

**MCP tool call (e.g. `resolve_gem_prompt`):**
1. MCP client sends tool call over stdio.
2. FastMCP routes to the decorated handler in `mcp_server.py`.
3. Handler calls the same `gem_service` functions used by the REST API.
4. Result returned as structured MCP tool response.

## Model and Provider Integration
- **Adapters**: `llm_service.py` exposes `complete(system, messages, model, provider)` and `complete_stream(...)` — callers never import Anthropic or OpenAI SDKs directly.
- **Providers**: `anthropic` (default) uses `AsyncAnthropic`; `openai` uses `AsyncOpenAI`.
- **Fallback policy**: none currently — if a provider call fails, the error propagates to the caller. Future: add retry with exponential backoff.
- **Timeout/retry**: inherited from SDK defaults. Add `httpx_client` with explicit timeouts for production hardening.
- **Rate limits**: not handled beyond SDK defaults. For high-volume use, wrap `complete()` with a rate-limiter.

## Prompt and Context Pipeline
- **Storage**: gems stored as plain text in `system_prompt` column with `updated_at` timestamp.
- **Versioning**: implicit via Supabase `updated_at`; no explicit version field. See `ROADMAP.md` for planned versioning.
- **Resolution**: `gem_service.resolve_gem()` does a depth-first recursive expansion. Variables are substituted after all gem refs are resolved (so embedded gems can also use the same variable values).
- **Token budget**: not enforced. Callers should be aware that deeply nested gem trees can produce very long prompts.
- **Prompt files**: canonical source-of-truth versions of shipped gems are also stored in `prompts/` as `.md` files for readability and code review.

## Evaluation and Quality Gates
- Offline evals live in `evals/`. Currently includes a smoke eval for `prompt_enhancer`.
- Minimum acceptance criteria for prompt changes: eval score must not regress from baseline.
- See `STANDARDS.md` for eval conventions.

## Operational Integration Points
- **API**: FastAPI at port 8000, documented at `/docs`.
- **Frontend**: Next.js at port 3000, proxies `/api/*` to backend.
- **MCP**: FastMCP stdio transport, configured in MCP client config files.
- **Storage**: Supabase Postgres, accessed via `supabase-py` service-role key.
- **Telemetry**: none currently. Add structured logging to `uvicorn` access logs for production.
- **Deployment**: Docker Compose for local. Backend deployable to any Python host (Fly.io, Railway, Render). Frontend deployable to Vercel (set `BACKEND_URL` env var).
