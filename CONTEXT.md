# CONTEXT

## System Purpose
gemsAPI is a self-hosted prompt library for LLM system prompts. It solves the problem of prompts living scattered across code files, Notion docs, and personal notes by giving them a proper home: a named, tagged, version-controlled database entry ("gem") accessible from a web UI, a REST API, and an MCP server. The recursive composition feature lets complex prompts be built from smaller reusable parts — the same way good software is built from functions and modules.

## Users & Stakeholders
- **Primary users**: AI engineers, product builders, and power users who work with multiple LLM prompts across projects and want a central place to manage and reuse them.
- **Technical owner**: poyfather (repo maintainer).
- **Adjacent tooling**: Claude Desktop and Cursor (MCP clients), Supabase (database), Anthropic and OpenAI APIs (LLM providers).

## Operational Context
- **Runtime environments**: local development (default), Docker Compose (self-hosted), or split-deploy (backend on Fly.io/Railway, frontend on Vercel).
- **External integrations**: Supabase (Postgres + Row Level Security), Anthropic Messages API, OpenAI Chat Completions API, any MCP-compatible client via FastMCP stdio transport.
- **Technical constraints**: Python 3.12+ for backend, Node 20+ for frontend, Supabase free tier for small deployments. Recursive gem resolution is depth-limited to 10 levels to prevent runaway queries.

## Domain Vocabulary
- **Gem**: a named, reusable LLM system prompt stored in Supabase. Analogous to a function in code.
- **Variable**: a `{placeholder}` in a gem's prompt filled at call time with a key-value dict.
- **Gem reference**: a `{{gem:name}}` tag in a prompt that embeds another gem's resolved content recursively.
- **Resolution**: the process of expanding all `{{gem:name}}` references and filling all `{variable}` placeholders to produce a final, ready-to-use system prompt.
- **Provider**: the LLM API used to run a gem — either `anthropic` or `openai`.
- **MCP**: Model Context Protocol — a standard interface for exposing tools and resources to AI agents.

## Current State
- **What exists**: full working scaffold — FastAPI backend, Next.js frontend, FastMCP server, Supabase schema with seed gems including `prompt_enhancer`, Docker Compose, and this documentation set.
- **Known limitations**: no authentication on the API (designed for private/local use); streaming uses SSE but the frontend currently renders completed messages only; no prompt versioning beyond Supabase `updated_at`.
- **Active risks**: API keys and the Supabase service role key must be kept out of version control; one shared `GEMS_API_KEY` means one leaked key exposes the whole library (per-client keys are roadmap item 10).

## Success Signals
- **Key outcomes**: all prompts live in one place; gems can be resolved and served in <200ms for non-recursive calls; MCP tools work seamlessly in Claude Desktop.
- **Quality signals**: `pytest` passes, `ruff check` passes, no committed secrets.
- **AI/evaluation signals**: `prompt_enhancer` gem produces measurably better prompts than the raw input on a defined eval set (see `evals/`).

## Guardrails
- Never commit API keys, Supabase service role keys, or any credentials to the repo.
- Do not add a permissive RLS policy or use the anon key from the backend; the service role is the only trusted database client (ADR-006).
- Do not allow `{{gem:name}}` resolution to exceed 10 levels of depth (enforced in `gem_service.py`).
- Do not expose the MCP server on a public network without authentication.

## Pointers
- High-level overview: `README.md`
- System design/details: `ARCHITECTURE.md`
- Security expectations: `SECURITY.md`
- Coding/testing/review conventions: `STANDARDS.md`
- Decision history: `DECISIONS.md`
