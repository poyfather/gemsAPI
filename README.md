# Lapidary

A self-hosted prompt library and agent harness. Store reusable LLM system prompts ("gems") in Supabase, compose them with `{{gem:name}}`, fill `{variable}` placeholders at call time, give a gem tools and run it as an agent, and serve all of it over a REST API, a web UI and an MCP server that Claude Desktop, Cursor and other MCP clients can call directly.

A lapidary is the craftsperson who cuts and polishes rough stones into gems. That is the job here: rough prompts become named, composable, versioned gems, and the polished ones get to act. The project was called gemsAPI until October 2026; the repository URL and the `GEMS_*` environment variables are unchanged.

[![CI](https://github.com/poyfather/lapidary/actions/workflows/ci.yml/badge.svg)](https://github.com/poyfather/lapidary/actions/workflows/ci.yml)
[![CodeQL](https://github.com/poyfather/lapidary/actions/workflows/codeql.yml/badge.svg)](https://github.com/poyfather/lapidary/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-1B2A4A.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.3.0-7c3aed.svg)](CHANGELOG.md)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg)](backend/requirements.txt)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-000000.svg)](frontend/package.json)

## Why

If you use AI tools a lot, you end up writing instructions for them: "you are a careful code reviewer, check for bugs first, then style." Good ones are worth keeping. The trouble is where they end up: one in a chat window, one in a text file, one pasted into Slack, three slightly different copies of the same thing. When you improve one, the others stay stale.

Lapidary is a labelled drawer for those instructions. Each one gets a name, a description and tags, and lives in one database. You can fetch it from a web page, from your own code, or straight from Claude Desktop and Cursor, which can open the drawer themselves and pull out the right prompt instead of you pasting it in.

Two tricks make the drawer more than a list:

- **Prompts can contain other prompts.** Write a short `base_assistant` once ("be direct, be honest about uncertainty"), then start `code_reviewer` with `{{gem:base_assistant}}` and add only the review rules. Improve the base, and everything built on it improves too.
- **Prompts can have blanks.** Leave `{language}` or `{tone}` in the text and fill it in at the moment you use it, so one prompt serves many situations.

Who it is for: anyone who writes prompts as part of their work and uses them from more than one place. Who it is not for yet: a casual user with three prompts in a notes app, since setting up a database and two services is more than that problem needs. [docs/ROADMAP.md](docs/ROADMAP.md) lists what would change that, starting with version history and per-prompt evals.

## How it fits together

```mermaid
flowchart LR
    subgraph callers["Who calls it"]
        UI["Web UI<br/>Next.js, port 3000"]
        REST["Scripts and apps<br/>REST with X-API-Key"]
        MCPC["MCP clients<br/>Claude Desktop, Cursor"]
    end

    subgraph core["Lapidary"]
        API["FastAPI service<br/>/gems and /chat, port 8000"]
        MCPS["FastMCP server<br/>7 tools, 2 resources, stdio"]
        RES["Resolver<br/>expand gem references,<br/>fill variables"]
        LLM["LLM adapter<br/>complete and stream"]
    end

    DB[("Supabase Postgres<br/>gems table")]

    subgraph providers["LLM providers"]
        ANT["Anthropic Messages API"]
        OAI["OpenAI Chat Completions"]
    end

    UI -- "/api/* proxy,<br/>key added server-side" --> API
    REST --> API
    MCPC -- "stdio" --> MCPS
    API --> RES
    MCPS --> RES
    RES --> DB
    API --> LLM
    MCPS --> LLM
    LLM --> ANT
    LLM --> OAI
```

Every surface hands the gem to the same resolver, which expands `{{gem:name}}` references recursively, fills `{variable}` placeholders, and either returns the finished prompt or sends it to a provider with the caller's messages. [ARCHITECTURE.md](ARCHITECTURE.md) has the component model, request sequences, the data model and the trust boundaries as further diagrams.

## What you get

| Surface | What it does |
|---|---|
| **Web UI** (Next.js 16, port 3000) | Browse, search and tag gems, edit them with a live resolved preview, test any gem in a chat view with streamed replies, run agent gems and watch each tool call as it happens, and open any past run by id |
| **REST API** (FastAPI, port 8000) | CRUD on `/gems`, `POST /gems/resolve` to expand a gem, `POST /chat` with optional SSE streaming, Swagger at `/docs` |
| **MCP server** (FastMCP, stdio) | Tools `list_gems`, `search_gems`, `get_gem`, `resolve_gem_prompt`, `chat_with_gem`, `create_gem`, `run_agent`, `list_agent_tools`, `list_available_models`, plus `gems://list`, `gems://{name}` and `runs://{id}` resources |
| **Agent runs** | A gem of kind `agent` lists tools it may call; `POST /agents/{name}/runs` runs the loop (model turn, tool calls, results, repeat) and records every step in `runs` and `run_events` |
| **Seed gems** | `base_assistant`, `code_reviewer`, `creative_writer`, `summarizer`, `engineering_lead`, `prompt_enhancer`, and the agents `gem_librarian` and `rea_analyst`, each also kept as a reviewable file in [`prompts/`](prompts/) |

## Quick start

You need Python 3.12 or newer, Node 20 or newer, a free [Supabase](https://supabase.com) project, and an `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` (the chat features need at least one; the library itself works without).

1. **Create the database and your env files.** In the Supabase SQL editor, run [`supabase/schema.sql`](supabase/schema.sql); it creates the `gems` table and the seed gems and is safe to run twice. Then:
   ```sh
   git clone https://github.com/poyfather/lapidary.git && cd lapidary
   cp .env.example backend/.env                    # Supabase URL and key, LLM keys, GEMS_API_KEY
   cp frontend/.env.local.example frontend/.env.local   # the same GEMS_API_KEY
   python -c "import secrets; print(secrets.token_urlsafe(32))"   # a value for GEMS_API_KEY
   ```
2. **Run the backend.**
   ```sh
   cd backend
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn app.main:app --reload                       # http://localhost:8000, Swagger at /docs
   ```
3. **Run the frontend** in a second terminal.
   ```sh
   cd frontend && npm install && npm run dev           # http://localhost:3000
   ```

The server refuses to start until `GEMS_API_KEY` is set, and every `/gems` and `/chat` request needs it in an `X-API-Key` header. The frontend adds that header server-side in [`frontend/proxy.ts`](frontend/proxy.ts), so the key never reaches the browser.

<details>
<summary>Connect an MCP client (Claude Desktop, Cursor)</summary>

The MCP server runs over stdio and reads `backend/.env`, so point the client at the backend's virtualenv Python and the absolute path of [`backend/mcp_server.py`](backend/mcp_server.py). For Claude Desktop the config file is `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS and `%APPDATA%\Claude\claude_desktop_config.json` on Windows:

```json
{
  "mcpServers": {
    "lapidary": {
      "command": "/absolute/path/to/lapidary/backend/.venv/bin/python",
      "args": ["/absolute/path/to/lapidary/backend/mcp_server.py"]
    }
  }
}
```

Restart the client. You can also run it by hand with `fastmcp run mcp_server.py` from `backend/`.
</details>

<details>
<summary>Docker Compose</summary>

```sh
cp .env.example .env
docker compose up --build
```

Compose builds both images, waits for the backend's `/health` before starting the frontend, and passes the frontend only `BACKEND_URL` and `GEMS_API_KEY` (the LLM and Supabase keys stay in the backend container). Then open http://localhost:3000. CI builds both images on every pull request.
</details>

## Gem syntax

| Syntax | Purpose |
|---|---|
| `{variable}` | Placeholder filled from the `variables` map at call time. Names are identifiers (`[A-Za-z_][A-Za-z0-9_]*`), so JSON or code braces such as `{"key": 1}` or `{}` are left alone |
| `{{gem:name}}` | Embed another gem. Expanded first, recursively, up to 10 levels, with cycle detection |

Variables are substituted after all references are expanded, so a value passed to the outer gem also fills placeholders in embedded gems. For example, the seed gem `engineering_lead` embeds `code_reviewer`, which embeds `base_assistant` and uses `{language}`:

```sh
curl -s http://localhost:8000/gems/resolve \
  -H "X-API-Key: $GEMS_API_KEY" -H "Content-Type: application/json" \
  -d '{"gem_name": "engineering_lead", "variables": {"language": "Python", "team_size": "4"}}'
```

The response carries `resolved_prompt`, `referenced_gems` (`["code_reviewer", "base_assistant"]`), `variables_used` and `variables_missing` for anything left unfilled. Gems can be fetched, updated and deleted by name or by id.

## Agents

A gem can act as well as answer. Set its `kind` to `agent` and list the tools it may call; the run loop then lets the model call those tools, feeds the results back, and repeats until the model answers or `AGENT_MAX_STEPS` is reached. Every model turn, tool call and tool result is recorded, so a run can be read back, compared and evaluated.

The built-in tools are read-only and about the library itself (`search_gems`, `get_gem`, `resolve_gem`). Any other MCP server's tools can be added: copy [`configs/mcp_servers.example.json`](configs/mcp_servers.example.json) to `configs/mcp_servers.json` (the same `mcpServers` shape as a Claude Desktop config) and every tool of each server appears as `<server>.<tool>`, with `<server>.*` meaning all of them. Tools from other servers count as risky unless the entry says `"risky": false` or lists the risky ones by name. `GET /agents/tools` lists everything with argument schemas and sources. The seed agent `gem_librarian` uses the three built-ins:

```sh
curl -s http://localhost:8000/agents/gem_librarian/runs \
  -H "X-API-Key: $GEMS_API_KEY" -H "Content-Type: application/json" \
  -d '{"message": "Which gems take a language variable, and what does code_reviewer expand to for Python?"}'
```

A second seed agent, `rea_analyst`, shows the point of remote tools. With [REA (Reverse Engineer Anything)](https://www.npmjs.com/package/rea-agents) configured as the `rea` server, it follows an evidence-first process (scope the target, map the surface, trace the feature from its UI trigger, collect evidence, reconstruct, verify, report) over the `rea.*` tools, with `{target_app}` and `{feature}` as its variables. Only analyse software you own or are authorised to examine; the gem says so too.

The response is the run (status, output, steps, tokens) plus its events; `GET /runs/{id}` returns the same later, and `"stream": true` delivers the events as Server-Sent Events while the run happens. The web UI does the same: mark a gem as an agent and pick its tools in the editor, send it a message on the chat page to watch the turns, tool calls and results stream in, then open the run at `/runs/{id}`. Over MCP the same loop is the `run_agent` tool, so Claude Desktop or Cursor can hand a task to one of your agents and get the answer and the run id back. A call to a tool marked risky pauses the run (status `waiting_approval`) with the call shown in the chat bubble or on the run page; approve or deny it there, or with `POST /runs/{id}/approve`, and the loop carries on from that exact point. A run started with `allow_risky` skips the gate. None of the shipped tools are risky. [ARCHITECTURE.md](ARCHITECTURE.md) has the loop as a sequence diagram, and ADR-007 in [DECISIONS.md](DECISIONS.md) explains the design.

## Configuration

Backend variables live in `backend/.env` (template: [`.env.example`](.env.example)); frontend variables in `frontend/.env.local` (template: [`frontend/.env.local.example`](frontend/.env.local.example)).

| Variable | Where | What it does |
|---|---|---|
| `SUPABASE_URL` | backend | Your project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | backend | Server-side key, the only Supabase credential the backend accepts. RLS has no policies for any other role, so the anon key reads nothing |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | backend | Providers for `/chat` and `chat_with_gem`. Set the ones you use |
| `GEMS_API_KEY` | backend and frontend | Shared secret for the `X-API-Key` header. Required |
| `CORS_ORIGINS` | backend | Comma-separated allowed origins, default `http://localhost:3000` |
| `BACKEND_URL` | frontend | Where `/api/*` is proxied, default `http://localhost:8000` |
| `GEMS_DEFAULT_PROVIDER`, `GEMS_DEFAULT_MODEL` | backend | Provider and model for new gems, default `anthropic` and `claude-opus-5-5` |
| `GEMS_MODELS_ANTHROPIC`, `GEMS_MODELS_OPENAI` | backend | Optional comma-separated model lists. When unset, `GET /chat/models` asks each configured provider for its current models and caches the answer for `GEMS_MODEL_LIST_TTL_SECONDS` (default 600) |
| `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `LLM_MAX_TOKENS` | backend | Per-attempt timeout (60), SDK retries on 429 and 5xx (2), and the completion cap (4096) |
| `AGENT_MAX_STEPS`, `AGENT_TOOL_RESULT_MAX_CHARS` | backend | Model turns per agent run (8) and the longest tool result sent back to the model (8000) |
| `GEMS_MCP_SERVERS_FILE`, `GEMS_MCP_TOOLS_TTL_SECONDS`, `GEMS_MCP_CALL_TIMEOUT_SECONDS` | backend | Where the MCP server list lives (`configs/mcp_servers.json`), how long a server's tool list is cached (300), and the per-call timeout (120) |

## Project layout

```
backend/app/        FastAPI app: routes/ (gems, chat, agents), services/ (gem_service resolver, llm_service), agents/ (tool registry, run loop, run store), auth.py, models.py
backend/mcp_server.py   FastMCP server over the same services
frontend/           Next.js 16 app router UI (app/ including runs/[id], components/ including RunEvents, lib/api.ts with the SSE client, proxy.ts)
configs/            mcp_servers.json (copy the example) for tools from other MCP servers
supabase/           schema.sql (tables, RLS, seed gems) and one-off migrations such as lock_down_rls.sql and add_agent_runs.sql
prompts/            the shipped gems as markdown, one file per gem
evals/              live-API quality checks for gems (eval_prompt_enhancer.py)
tests/              pytest unit tests, no network
scripts/            setup.ps1 and test.ps1 for Windows
docs/               ROADMAP.md
```

## Development

From the repo root, with the backend virtualenv active:

```sh
pip install -r requirements.txt   # pytest and ruff
ruff check .
pytest -q
```

In `frontend/`: `npm run lint`, `npx tsc --noEmit`, `npm run build`. CI runs all of these on every pull request, plus CodeQL and a check that every file in `prompts/` has a seed row in `supabase/schema.sql`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and [STANDARDS.md](STANDARDS.md) for conventions.

## Documentation map

- [CONTEXT.md](CONTEXT.md): purpose, users, vocabulary and guardrails
- [ARCHITECTURE.md](ARCHITECTURE.md): diagrams of the components, request flows, gem composition, data model and trust boundaries
- [DECISIONS.md](DECISIONS.md): architecture decision records
- [STANDARDS.md](STANDARDS.md): coding, testing, prompt and eval conventions
- [AGENTS.md](AGENTS.md): how AI coding agents should work in this repo
- [docs/ROADMAP.md](docs/ROADMAP.md): prioritised improvements, and [ROADMAP.md](ROADMAP.md) for delivery status
- [CHANGELOG.md](CHANGELOG.md): release notes

## Contributing

Bug reports, gem proposals and pull requests are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md) and [SUPPORT.md](SUPPORT.md). Security concerns go through [SECURITY.md](SECURITY.md), not the issue tracker.

## License

[MIT](LICENSE).
