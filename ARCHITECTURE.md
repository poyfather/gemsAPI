# Architecture

Lapidary is three small programs around one table. A FastAPI service and a FastMCP server share the same Python package (`backend/app`) and the same resolver; a Next.js app is the human interface; Supabase Postgres holds the gems. This page is the map: what each part does, how a request moves through them, how gem composition works, what the data looks like, and where the trust boundaries are. The diagrams are Mermaid and render on GitHub.

## The big picture

```mermaid
flowchart LR
    subgraph callers["Who calls it"]
        UI["Web UI<br/>Next.js, port 3000"]
        REST["Scripts and apps<br/>REST with X-API-Key"]
        OWUI["Open WebUI and other<br/>OpenAI-compatible clients<br/>/v1, bearer key"]
        MCPC["MCP clients<br/>Claude Desktop, Cursor"]
    end

    subgraph core["Lapidary"]
        API["FastAPI service<br/>/gems and /chat, port 8000"]
        MCPS["FastMCP server<br/>17 tools, 3 resources, stdio or HTTP"]
        RES["Resolver<br/>expand gem references,<br/>fill variables"]
        LLM["LLM adapter<br/>complete and stream"]
        LOOP["Agent run loop<br/>tools (built in and from<br/>other MCP servers),<br/>step cap, run record"]
    end

    DB[("Supabase Postgres<br/>gems, runs, run_events")]

    subgraph providers["LLM providers"]
        ANT["Anthropic Messages API"]
        OAI["OpenAI Chat Completions"]
    end

    UI -- "/api/* proxy,<br/>key added server-side" --> API
    REST --> API
    OWUI --> API
    MCPC -- "stdio, or HTTP at /mcp with the key" --> MCPS
    API --> RES
    MCPS --> RES
    RES --> DB
    API --> LLM
    MCPS --> LLM
    API --> LOOP
    MCPS --> LOOP
    LOOP --> RES
    LOOP --> LLM
    LOOP --> DB
    LLM --> ANT
    LLM --> OAI
```

A **gem** is a named system prompt stored in Postgres. It can embed other gems with `{{gem:name}}` and leave `{variable}` placeholders to be filled at call time. Every surface (REST, UI, MCP) hands the gem to the same resolver, which expands the references recursively and fills the variables, and either returns the finished prompt or passes it to an LLM with the caller's messages.

## Architecture principles

- **Separation of concerns.** The backend (FastAPI), the frontend (Next.js) and the MCP server (FastMCP) are independently deployable units. The MCP server imports the backend's service layer directly rather than calling the HTTP API.
- **Provider abstraction.** All LLM calls go through `backend/app/services/llm_service.py`, which exposes `complete()` and `complete_stream()`. Routes, the MCP server and the resolver never import a provider SDK.
- **Single source of truth.** Gem content lives only in Supabase. Nothing is cached in memory or read from config files at runtime. The files in `prompts/` are a reviewable mirror of the shipped gems, not a runtime input.
- **Fail-safe recursion.** Resolution is depth-limited (10 levels) and cycle-detected before any further database call is made on a branch.
- **No client-side secrets.** The browser never holds an API key. The Next.js server (`proxy.ts`) injects `X-API-Key` on the proxy hop, and all LLM keys stay in the backend process.

## Component model

```mermaid
flowchart TB
    subgraph browser["Browser"]
        PAGES["app/ pages<br/>gems list, detail, new, edit,<br/>chat, runs/[id]"]
        COMPS["components/<br/>GemCard, GemForm, Navigation,<br/>RunEvents"]
        APITS["lib/api.ts<br/>typed client, calls /api/*,<br/>SSE reader for streams"]
        PAGES --> COMPS
        PAGES --> APITS
    end

    subgraph nextsrv["Next.js server (frontend/, port 3000)"]
        MW["proxy.ts<br/>adds X-API-Key from GEMS_API_KEY"]
        RW["next.config.mjs<br/>rewrites /api/* to BACKEND_URL"]
        MW --> RW
    end

    subgraph fastapi["FastAPI service (backend/app, port 8000)"]
        MAIN["main.py<br/>app, CORS, lifespan check, /health"]
        AUTH["auth.py<br/>require_api_key dependency"]
        RG["routes/gems.py<br/>CRUD and POST /gems/resolve"]
        RC["routes/chat.py<br/>POST /chat, GET /chat/models, SSE"]
        MAIN --> RG
        MAIN --> RC
        AUTH -.-> RG
        AUTH -.-> RC
    end

    subgraph mcpproc["MCP server process (backend/mcp_server.py, stdio)"]
        TOOLS["Tools<br/>list_gems, search_gems, get_gem,<br/>resolve_gem_prompt, chat_with_gem,<br/>create_gem, list_available_models"]
        RSRC["Resources<br/>gems://list, gems://{name}"]
    end

    subgraph services["Shared service layer (backend/app)"]
        GS["services/gem_service.py<br/>CRUD, extract_variables,<br/>extract_gem_refs, resolve_gem"]
        LS["services/llm_service.py<br/>complete, complete_stream,<br/>available_models"]
        MODELS["models.py<br/>Pydantic request and response shapes"]
        DBPY["database.py<br/>Supabase client singleton"]
        GS --> DBPY
        GS --> MODELS
    end

    SUPA[("Supabase Postgres<br/>gems table, RLS, trigger")]
    ANT["Anthropic"]
    OAI["OpenAI"]

    APITS -- "HTTP, same origin" --> MW
    RW -- "HTTP + X-API-Key" --> MAIN
    RG --> GS
    RC --> GS
    RC --> LS
    TOOLS --> GS
    TOOLS --> LS
    RSRC --> GS
    DBPY -- "supabase-py over HTTPS" --> SUPA
    LS -- "anthropic SDK" --> ANT
    LS -- "openai SDK" --> OAI
```

| Component | Where | Responsibility | Talks to | How |
|---|---|---|---|---|
| Web UI | `frontend/app`, `frontend/components` | Browse, search and tag gems; create and edit with a live resolved preview, kind and tool picker; chat against a gem with streamed replies; run agent gems with live events; view a run by id | `lib/api.ts` | React state, client components |
| API client | `frontend/lib/api.ts` | The only place the UI calls the network; typed wrappers for every route and one SSE reader used by `chat.stream` and `agents.stream` | Next.js server | `fetch("/api/...")`, same origin |
| Proxy and key injection | `frontend/proxy.ts`, `frontend/next.config.mjs` | Add `X-API-Key` from a server-only env var, then rewrite `/api/*` to the backend | FastAPI | HTTP to `BACKEND_URL` |
| FastAPI app | `backend/app/main.py` | App factory, CORS from `CORS_ORIGINS`, startup check that `GEMS_API_KEY` is set, `/` and `/health` | Routers | In-process |
| Auth | `backend/app/auth.py` | Router-level dependency: 401 unless `X-API-Key` matches `GEMS_API_KEY` | `/gems`, `/chat` | FastAPI `Security` |
| Gems routes | `backend/app/routes/gems.py` | List, create, get by name or id, update, soft delete, resolve | `gem_service` | Async calls |
| Chat routes | `backend/app/routes/chat.py` | Resolve the gem, pick model and provider, call the LLM, return JSON or an SSE stream | `gem_service`, `llm_service` | Async calls, `StreamingResponse` |
| OpenAI-compatible routes | `backend/app/routes/openai_compat.py` | `GET /v1/models`, `POST /v1/chat/completions` (streaming): every gem and agent as a model for Open WebUI and other OpenAI-compatible clients; bearer auth with the same key | `gem_service`, `llm_service`, `agents.runner` | Async calls, `StreamingResponse` |
| Agent routes | `backend/app/routes/agents.py` | `POST /agents/{name}/runs` (JSON or SSE), `GET /runs/{id}`, `GET /agents/tools` | `agents.runner`, `agents.run_service` | Async calls, a queue for SSE |
| Tool registry | `backend/app/agents/tools.py`, `builtin.py`, `mcp_sources.py` | `@tool` functions with a JSON schema from the signature; the three built-ins read the library; every tool of each MCP server in `configs/mcp_servers.json` as `<server>.<tool>`, listed and called through a fastmcp client, risky by default | `gem_service`, other MCP servers | In-process; stdio or streamable HTTP to the servers |
| Run loop | `backend/app/agents/runner.py` | Resolve the gem, call the model with its tools, execute calls, feed results back, stop on an answer or the step cap; record every event | `llm_service.complete_turn`, registry, run store | Async calls |
| Run store | `backend/app/agents/run_service.py` | `runs` and `run_events` through the storage layer | `storage/` | In-process |
| Resolver and CRUD | `backend/app/services/gem_service.py` | Supabase queries; `{variable}` and `{{gem:name}}` extraction; recursive, cycle-safe resolution | `database.py` | `supabase-py` table API |
| LLM adapter | `backend/app/services/llm_service.py` | One `complete()` and one `complete_stream()` for both providers, with timeouts and retries; `available_models()` with its cache | Anthropic, OpenAI | Official async SDKs |
| Data shapes | `backend/app/models.py` | Pydantic models for gems, resolve and chat requests and responses | Routes, services | Import |
| Storage layer | `backend/app/storage/` | One `Store` interface; `SQLiteStore` (one file, seeded from `supabase/schema.sql` on first use; the default without a Supabase project and what the console uses) and `SupabaseStore`; chosen by `GEMS_STORAGE` | `database.py` for Supabase | sqlite3 in process, or HTTPS |
| Database client | `backend/app/database.py` | Lazily built singleton from `SUPABASE_URL` and the service role key, the only credential accepted (hosted mode) | Supabase | HTTPS |
| MCP server | `backend/mcp_server.py`, `app/mcp_http.py` | Expose the library, agents, memory and pipelines to MCP clients as tools and resources; as its own stdio process (reads `backend/.env` itself), or mounted on the API at `/mcp` as stateless streamable HTTP behind the same keys | `gem_service`, `llm_service` | stdio, or HTTP in the API process |
| Database | `supabase/schema.sql` | The `gems` table, indexes, `updated_at` trigger, RLS with no policies, seed gems | | SQL, run once in the Supabase editor |
| Prompt mirror and evals | `prompts/`, `evals/` | Reviewable copies of shipped gems; live-API quality checks with recorded baselines | Supabase, Anthropic | Manual runs |

Two things the diagram makes visible that the code does not say out loud: the MCP server is a **second entry point into the same service layer**, so anything added to `gem_service` is available to both REST and MCP for free; and the API key check lives on the **REST edge only**, so the MCP server is gated by whoever can start the process, not by the key.

## Request flows

### Chat from the web UI, streamed

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (chat page)
    participant N as Next.js server
    participant A as FastAPI
    participant G as gem_service
    participant S as Supabase
    participant L as llm_service
    participant P as Provider

    B->>N: POST /api/chat {gem_name, messages, variables, stream}
    N->>N: proxy.ts adds X-API-Key
    N->>A: POST /chat (rewritten)
    A->>A: require_api_key
    A->>G: resolve_gem(name, variables)
    loop one query per gem in the reference tree
        G->>S: select * from gems where name = ... and is_active
        S-->>G: row
    end
    G-->>A: resolved prompt, referenced gems
    A->>G: get_gem_by_name (default model and provider)
    G->>S: select
    S-->>A: gem
    A->>L: complete_stream(system, messages, model, provider)
    L->>P: streaming request
    P-->>L: text deltas
    L-->>A: chunks
    A-->>B: text/event-stream: data: {"content": ...} ... data: [DONE]
```

The chat page uses the streamed form for prompt gems and renders the chunks as they arrive. Without `stream`, step 13 onward is a single `complete()` call and the response is one `ChatResponse` JSON body. Provider errors are logged on the server and the client receives a fixed 502 message (or a fixed SSE `error` event), never the exception text.

### A tool call from an MCP client

```mermaid
sequenceDiagram
    autonumber
    participant C as Claude Desktop or Cursor
    participant M as mcp_server.py
    participant G as gem_service
    participant S as Supabase
    participant L as llm_service
    participant P as Provider

    C->>M: tools/call resolve_gem_prompt {name, variables} (stdio)
    M->>G: resolve_gem(name, variables)
    G->>S: select, once per gem in the tree
    S-->>G: rows
    G-->>M: resolved prompt, referenced gems
    M-->>C: {gem_name, resolved_prompt, referenced_gems, variables_missing}

    C->>M: tools/call chat_with_gem {gem_name, message}
    M->>G: resolve_gem, then get_gem_by_name
    M->>L: complete(system, [user message], model, provider)
    L->>P: request
    P-->>L: completion
    M-->>C: {gem_name, response, model, provider}
```

The MCP server does not go through HTTP or `auth.py`. It calls the same functions the routes call, in its own process, with the credentials from `backend/.env`.

## Agent runs

ADR-007 added the loop. A gem of kind `agent` lists tool names; the loop gives the model those tools and keeps going until it answers without one.

```mermaid
sequenceDiagram
    autonumber
    participant C as Caller (REST, MCP)
    participant R as runner.run_agent
    participant G as gem_service
    participant T as Tool registry
    participant L as llm_service.complete_turn
    participant P as Provider
    participant S as runs, run_events

    C->>R: run_agent(gem, message, variables)
    R->>G: resolve_gem_detailed, get_gem_by_name
    R->>S: insert run (status running)
    R->>S: event run_started
    loop until the model answers without tools, or AGENT_MAX_STEPS
        R->>L: complete_turn(system, messages, tools)
        L->>P: messages.create with tools (Anthropic) or chat.completions with functions (OpenAI)
        P-->>L: text and zero or more tool calls
        L-->>R: ToolTurn (neutral shape)
        R->>S: event model_turn
        alt tool calls present
            R->>S: on a risky call without allow_risky: status waiting_approval, state saved, event approval_requested; stop here until POST /runs/{id}/approve resumes
            R->>T: execute each call (unknown: an error string; denied: an error string)
            T-->>R: result text, truncated at AGENT_TOOL_RESULT_MAX_CHARS
            R->>S: events tool_call, tool_result
            R->>R: append results in the provider's shape (one user message for Anthropic, one tool message per call for OpenAI)
        end
    end
    R->>S: event run_finished, update run (status, output, steps, tokens)
    R-->>C: RunResult (run + events), or the events as SSE while it happens
```

What the loop promises: a tool error never escapes the run (unknown tool, denied tool, bad arguments and tool exceptions all go back to the model as text); a provider failure ends the run as `failed` with a record; every run has at most `AGENT_MAX_STEPS` model turns; nothing is held in memory between requests. A risky tool call pauses the run instead of running: the loop state (conversation, calls still to execute, results so far) is saved in the `runs.state` column, `approval_requested` is the last event, and `resume_run()` picks up from that call once `POST /runs/{id}/approve` arrives, approving (the call runs) or denying (the model gets an error result), then continues the turn and the loop, pausing again at the next risky call. Tools from other MCP servers are listed when a run or the tools endpoint asks for them (cached), and each call opens the server's transport for that call. What it does not do yet: plain HTTP endpoints as tools without an MCP server in front, a token budget per run, or a list of past runs (roadmap item 35; the viewer itself is `app/runs/[id]` and the chat page).

## Gem composition and resolution

Gems compose by reference. The seed library ships a three-level example:

```mermaid
flowchart TD
    EL["engineering_lead<br/>uses {team_size}"]
    CR["code_reviewer<br/>uses {language}"]
    BA["base_assistant<br/>no variables, no references"]
    CW["creative_writer<br/>uses {style}, {tone}, {genre}"]
    SUM["summarizer<br/>uses {depth}, {target_length}"]
    PE["prompt_enhancer<br/>standalone"]

    EL -- "{{gem:code_reviewer}}" --> CR
    CR -- "{{gem:base_assistant}}" --> BA
    CW -- "{{gem:base_assistant}}" --> BA
```

Resolving `engineering_lead` with `{"language": "Python", "team_size": "4"}`:

```mermaid
flowchart TD
    A["Step 1<br/>Load engineering_lead"] --> B["Step 2<br/>Find {{gem:code_reviewer}},<br/>recurse (depth 1)"]
    B --> C["Step 3<br/>Find {{gem:base_assistant}},<br/>recurse (depth 2)"]
    C --> D["Step 4<br/>base_assistant has no refs:<br/>return its text"]
    D --> E["Step 5<br/>Splice into code_reviewer,<br/>return"]
    E --> F["Step 6<br/>Splice into engineering_lead"]
    F --> G["Step 7<br/>Fill {language} and {team_size}<br/>across the whole text"]
    G --> H["Resolved prompt +<br/>referenced_gems: [code_reviewer, base_assistant]"]
```

Rules enforced in `resolve_gem`:

- **Depth limit.** More than 10 nested levels raises a `ValueError` (400 on REST, an `error` field on MCP).
- **Cycle detection.** The chain of names already on the stack travels with the recursion as a frozenset; meeting one again raises before any query.
- **References first, variables last.** All `{{gem:...}}` tags are expanded before any `{variable}` is filled, so a value given to the outer gem also fills placeholders inside embedded gems.
- **Reference names are identifiers.** The pattern accepts `[A-Za-z0-9_.-]+` only, which keeps matching linear on malformed input.
- **Referenced gems are reported** in order of first appearance, without duplicates.
- **Token budget: none.** Nothing caps the size of a resolved prompt. See `docs/ROADMAP.md` item 19.

## Data model

```mermaid
erDiagram
    GEMS {
        uuid id PK "uuid_generate_v4()"
        text name UK "snake_case, unique"
        text description
        text system_prompt "may contain {variable} and {{gem:name}}"
        text model "default from GEMS_DEFAULT_MODEL"
        text provider "anthropic or openai (CHECK)"
        text_array tags "GIN indexed"
        text_array variables "derived from system_prompt on save"
        boolean is_active "soft delete flag"
        timestamptz created_at
        timestamptz updated_at "trigger sets NOW() on update"
    }
```

- The same tables exist in both backends: Postgres on Supabase (`supabase/schema.sql`) and SQLite (`backend/app/storage/sqlite_schema.sql`, lists and JSON as text). The seed gems have one source, the `INSERT` in `schema.sql`, which the SQLite backend parses on first start.
- References between gems are text inside `system_prompt`, resolved by name at read time; there is no foreign key, so a referenced gem can be renamed or soft-deleted and the reference only fails at resolution.
- `variables` is recomputed by `gem_service` whenever `system_prompt` is written, so the UI can render inputs without parsing the prompt.
- Row level security is enabled with no policies, so only the service role key, used by the backend and the MCP server, can read or write rows; the anon key gets nothing. The API key on the REST edge is the access control for callers (ADR-006).
- Deletes are soft (`is_active = false`); listing and name lookups filter on `is_active`, lookups by id do not.
- `prompts/<name>.md` mirrors each shipped gem for review; CI checks that every file has a seed row of the same name in `supabase/schema.sql`.
- `gem_versions` (roadmap 14) holds one row per save of a gem: the version number, the gem's fields as JSON, a note and the source (api, mcp, revert, baseline). The app writes it in `version_service`, not a trigger, so both stores keep the same history; it is never edited or deleted, and a revert is a new row.
- `memories` (ADR-010) holds one row per observation, summary, decision, preference, lesson, handoff or note: text, source (run, chat, mcp, console, user), the gem and run it came from, tags, a scope, and a full-text index (FTS5 on SQLite, a generated `tsvector` on Postgres). `gems.memory` marks the gems that get the top matches for a message inside a `<memory>` block before their prompt. RLS on, no policies, like the rest.
- `pipelines` (ADR-011) holds a builder gem, its gates as JSON (gem, role, provider and model overrides, instructions), `max_attempts` and whether a person accepts at the end; `pipeline_runs` holds one row per pipeline run with its attempts (builder run id and status, output, each gate's run id, verdict and findings, the feedback given) and the loop state while it waits for an approval or an acceptance. The agent runs themselves are in `runs`.
- `kind` (`prompt` or `agent`) and `tools` (registered tool names) make a gem runnable by the agent loop. `runs` holds one row per run (status, model, tokens, output, and `state` while it waits for an approval) and `run_events` one row per model turn, tool call, tool result, approval request or decision, or failure, in order. Both tables have RLS enabled with no policies, like `gems`.

## Model and provider integration

- **Adapter.** `llm_service.complete(system, messages, model, provider)` and `complete_stream(...)` are the whole interface. `provider` selects an `AsyncAnthropic` or `AsyncOpenAI` client, built lazily from `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`.
- **Providers.** Three: `anthropic`, `openai`, and `local`, which is any OpenAI-compatible server at `LOCAL_OPENAI_BASE_URL` (Ollama, LM Studio, oMLX, vLLM) and uses the OpenAI SDK with that base URL.
- **Model choice.** `backend/app/services/router.py` decides per call from the model policy (`GEMS_MODEL_POLICY`: local, online, mix, auto, manual), the gem's own pin if it has one, what is available (keys in the environment, a local server that answers) and the gem's role (its tags and kind), and returns a provider, a model and a reason; chat, agent runs, the MCP `chat_with_gem` tool and the OpenAI-compatible API all go through it, and the reason is recorded. A chat request can override both. `GET /chat/models` and the `list_available_models` tool return `llm_service.available_models()`: each provider's live model list (OpenAI's filtered to chat models), cached for ten minutes, with an environment pin or a static fallback when a key is missing or the call fails. The UI's dropdowns read that endpoint; nothing in the frontend names a model.
- **Retries and timeouts.** Both SDK clients are built with `LLM_TIMEOUT_SECONDS` per attempt and `LLM_MAX_RETRIES` (the SDKs retry connection errors, 408, 409, 429 and 5xx with backoff). Any SDK failure is wrapped in `ProviderError`, logged, and surfaced as a generic 502 or SSE error. There is no cross-provider fallback.
- **Rate limits and cost.** Not handled. Every `/chat` and `chat_with_gem` call spends provider credit (`docs/ROADMAP.md` item 11).

## Trust boundaries

```mermaid
flowchart LR
    subgraph z1["Browser"]
        UI2["Web UI<br/>holds no secrets"]
    end
    subgraph z2["Next.js server"]
        MW2["proxy + rewrite<br/>holds GEMS_API_KEY only"]
    end
    subgraph z3["FastAPI service"]
        API2["/gems and /chat<br/>behind require_api_key<br/>holds GEMS_API_KEY,<br/>Supabase key, LLM keys"]
    end
    subgraph z4["MCP process"]
        MCP2["mcp_server.py<br/>no API key check<br/>holds Supabase key, LLM keys"]
    end
    SUP2[("Supabase<br/>RLS denies all but<br/>the service role")]
    PROV["Providers"]

    UI2 --> MW2 --> API2 --> SUP2
    API2 --> PROV
    MCP2 --> SUP2
    MCP2 --> PROV
```

Keep the FastAPI service and the MCP server on a private network or behind TLS and a reverse proxy; see `SECURITY.md`.

## Deployment topologies

```mermaid
flowchart TB
    subgraph local["Local development"]
        L1["uvicorn app.main:app --reload :8000"]
        L2["next dev :3000"]
        L3["python mcp_server.py (started by the MCP client)"]
    end
    subgraph compose["Docker Compose"]
        C1["backend image, python:3.12-slim"]
        C2["frontend image, node:24-alpine"]
        C1 --- C2
    end
    subgraph split["Split deploy"]
        S1["Backend on Fly.io, Railway or Render"]
        S2["Frontend on Vercel, BACKEND_URL set"]
        S2 -- "/api/* rewrite" --> S1
    end
    SB[("Supabase cloud")]
    local --> SB
    compose --> SB
    split --> SB
```

Compose builds a standalone Next.js server and a uvicorn image, gates the frontend on the backend's `/health`, and hands the frontend only `BACKEND_URL` and `GEMS_API_KEY`. The MCP server is always a local process started by the client over stdio; hosting it over HTTP would need authentication first.

## Evaluation and quality gates

- Unit tests in `tests/` cover the extraction helpers and the regex behaviour; they make no network calls and run in CI with ruff, the import check and the frontend build.
- Offline evals in `evals/` call the real Anthropic API for a gem and record a baseline score in the file. Run one before merging a change to the matching gem in `prompts/`; the score must not regress.
- CI also checks that every `prompts/*.md` has a seed row in `supabase/schema.sql`.

## Operational integration points

- **REST API**: port 8000, OpenAPI at `/docs` and `/redoc`, `X-API-Key` header on everything except `/` and `/health`.
- **Frontend**: port 3000, proxies `/api/*`; needs `GEMS_API_KEY` and `BACKEND_URL`.
- **MCP**: stdio, configured in the client's MCP settings with the backend virtualenv's Python and the absolute path of `backend/mcp_server.py`.
- **Storage**: Supabase Postgres through `supabase-py` with the service role key.
- **Telemetry**: uvicorn access logs and Python logging; no metrics or tracing yet (`docs/ROADMAP.md` item 20).

## Known gaps

The prioritised list, with sizes and dependencies, is [docs/ROADMAP.md](docs/ROADMAP.md). The ones this page touches: Docker build (1), 404 for unknown ids (2), variable regex scope (4), resolver tests (5), RLS and key model (9), MCP auth when hosted (10), streaming in the UI (13), version history (14), N+1 queries and a size budget (19).
