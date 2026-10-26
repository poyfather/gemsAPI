# CONTEXT

## System Purpose
Lapidary (gemsAPI until October 2026) is a home for the instructions people give AI and for the assistants built from them, so they can keep their best AI instructions in one place and use them in every app (ADR-013). It solves the problem of prompts living scattered across chat windows, code files, notes and messages, copied and drifting apart. Each prompt becomes a named, tagged, versioned "gem" in one store, built from smaller gems the way good software is built from functions, with blanks filled at use, worked examples, tests and side-by-side comparison. A gem with tools runs as an assistant that asks before risky steps. It is reached from a web UI, a REST API, an OpenAI-compatible API, and an MCP server over stdio or HTTP, and on Windows 11 through Lapidary Console, which installs and connects everything in plain words.

## Users & Stakeholders
- **Primary users**: people who write prompts as part of their work and use them from more than one app; newcomers on Windows 11 served by the console's first run (ADR-012); system administrators on the console's Advanced path. Teams and organizations come later, with accounts and roles (roadmap 57).
- **Technical owner**: poyfather (repo maintainer).
- **Adjacent tooling**: Claude Desktop, ChatGPT, Cursor and other MCP clients; Open WebUI and other OpenAI-compatible clients; Anthropic and OpenAI APIs; local model servers (Ollama, LM Studio, oMLX, vLLM); SQLite or Supabase for storage; PowerShell 7, REA and other MCP servers as tools.

## Operational Context
- **Runtime environments**: the Windows console on one PC (backend and UI as local sidecars, SQLite in the user's profile), local development, Docker Compose, or a split deploy (backend on Fly.io, Railway or Render, frontend on Vercel).
- **External integrations**: SQLite (default) or Supabase Postgres with row level security; the Anthropic Messages API, the OpenAI API and any OpenAI-compatible local server; MCP clients over stdio or streamable HTTP at `/mcp`; tools from other MCP servers; winget and the PowerShell Gallery for the console's installs.
- **Technical constraints**: Python 3.12+ for the backend, Node 20+ for the frontend, Windows 11 for the console. Recursive gem resolution is depth-limited to 10 levels to prevent runaway queries.

## Domain Vocabulary
- **Gem**: a named, reusable LLM system prompt stored in Lapidary's store (SQLite or Supabase), with its history, tests and examples. Analogous to a function in code. A gem of kind `agent` lists tools and runs as an assistant.
- **Variable**: a `{placeholder}` in a gem's prompt filled at call time with a key-value dict. Its spec (roadmap 29) can give a description, a type, choices, a default and whether it is required; on screen it is a "blank".
- **Gem reference**: a `{{gem:name}}` tag in a prompt that embeds another gem's resolved content recursively.
- **Resolution**: the process of expanding all `{{gem:name}}` references and filling all `{variable}` placeholders to produce a final, ready-to-use system prompt.
- **Provider**: the LLM API used to run a gem: `anthropic`, `openai`, `local` (any OpenAI-compatible server on this PC) or `auto` (the model policy decides).
- **Memory**: what persists across runs, chats and clients (ADR-010): observations captured when a run finishes plus notes, decisions, preferences, lessons and handoffs, recalled by search then fetch, and prepended to gems that have memory on.
- **Pipeline** and **gate** (ADR-011): a builder gem followed by gate gems that pass or fail its output with findings; a fail goes back to the builder, a pass through every gate reaches acceptance by a person.
- **MCP**: Model Context Protocol, a standard interface for exposing tools and resources to AI agents.
- **On screen (ADR-012, roadmap 48)**: the web UI and the console use plain words for the same things. A gem is a prompt, an agent gem is an assistant, variables are blanks to fill, a gem reference is "built from", resolution gives "the prompt as sent", a run is "what the assistant did", a provider is "which AI", MCP is "connect", and a risky tool "asks first". The API, the URLs, the environment variables and these docs keep the words above; `frontend/lib/words.ts` does the translation.

## Current State
- **What exists**: the library with composition, typed blanks and worked examples; version history with diff and restore; tests per gem with a baseline; side-by-side compare; assistants with tools, approvals and recorded runs; pipelines with gates; memory; local models and the model policy; the web UI with streamed chat; REST, OpenAI-compatible and MCP (stdio and HTTP) surfaces; SQLite and Supabase storage; Docker Compose; and the Windows console with its installer and helper service. CI runs lint, tests, CodeQL, the Docker build and a Windows install check.
- **Known limitations**: one person per instance (no user accounts; roadmap 21 within 57); no spend limits or rate limits (11 within 55); no import or export yet (22); the Windows installer is unsigned until signing credentials are added; no live demo or gallery yet (51, 53).
- **Active risks**: API keys and the Supabase service role key must be kept out of version control; every REST and `/mcp` call needs an API key (`GEMS_API_KEY`, or per-client keys in `GEMS_CLIENT_KEYS` that can be revoked one at a time), but a key grants the whole library, since keys are not yet scoped (57); the stdio MCP server trusts whoever can start it.

## Success Signals
- **Key outcomes**: a newcomer understands, tries and gets something useful from Lapidary within five minutes (ADR-013); all prompts live in one place; gems resolve in under 200 ms for non-recursive calls; MCP tools work in Claude Desktop, ChatGPT and Cursor.
- **Growth signals (roadmap 58)**: the share of visitors who create their first gem, the share who use it again seven days later, and the number who share a gem with someone else. Self-hosted installs count nothing unless the owner opts in.
- **Quality signals**: `pytest` passes, `ruff check` passes, no committed secrets.
- **AI/evaluation signals**: `prompt_enhancer` gem produces measurably better prompts than the raw input on a defined eval set (see `evals/`).

## Guardrails
- Never commit API keys, Supabase service role keys, or any credentials to the repo.
- Do not add a permissive RLS policy or use the anon key from the backend; the service role is the only trusted database client (ADR-006).
- Do not allow `{{gem:name}}` resolution to exceed 10 levels of depth (enforced in `gem_service.py`).
- Do not expose the stdio MCP server on a network; over a network, use the API's `/mcp` path, which requires the same API keys.
- Keep the docs true: a document that contradicts the code is a bug (ADR-013).

## Pointers
- High-level overview: `README.md`
- System design/details: `ARCHITECTURE.md`
- Security expectations: `SECURITY.md`
- Coding/testing/review conventions: `STANDARDS.md`
- Decision history: `DECISIONS.md`
