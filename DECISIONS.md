# DECISIONS

## Purpose
Track architectural decisions, including why they were made and their long-term impact.

## ADR Template
- Date:
- ID: ADR-000
- Status: Proposed | Accepted | Superseded | Deprecated
- Context:
- Decision:
- Consequences:
- Alternatives Considered:
- Supersedes/Superseded By:

---

## ADR Entries

### ADR-001 — Supabase as the gems database
- Date: 2026-04-15
- Status: Accepted
- Context: Gems need to be persisted, queried by name/tag, and accessible from both the FastAPI backend and the MCP server. A lightweight hosted Postgres with a free tier was preferred over SQLite (no good hosted option) or a custom file store.
- Decision: Use Supabase (hosted Postgres) via `supabase-py`. Row Level Security enabled on the `gems` table.
- Consequences: Requires a Supabase project for setup. Free tier is sufficient for personal use. RLS policy is open by default and must be tightened for multi-user deployments.
- Alternatives Considered: SQLite (local only, no shared access), PlanetScale (MySQL, less Python-native), raw Postgres (more ops overhead).
- Supersedes/Superseded By: None

### ADR-002 — FastMCP for the MCP server
- Date: 2026-04-15
- Status: Accepted
- Context: gemsAPI needs to be accessible from Claude Desktop and other MCP clients. Building the MCP protocol from scratch adds significant boilerplate.
- Decision: Use FastMCP 2.x (jlowin/fastmcp) which provides a decorator-based API over the official MCP SDK, stdio transport by default, and resource support.
- Consequences: Takes a dependency on a third-party library over the official Anthropic MCP SDK. FastMCP 2.x API is stable but relatively new.
- Alternatives Considered: Direct use of the `mcp` package (more boilerplate), HTTP/SSE transport (adds network complexity).
- Supersedes/Superseded By: None

### ADR-003 — Recursive `{{gem:name}}` composition with depth limit
- Date: 2026-04-15
- Status: Accepted
- Context: Composable prompts are the core differentiator of gemsAPI. A gem should be able to embed another gem inline, enabling reusable building blocks (e.g. a `base_personality` gem shared across many specialized gems).
- Decision: Implement recursive resolution in `gem_service.resolve_gem()` with a hard depth limit of 10 and a cycle-detection `frozenset` passed down the call stack. Variables are resolved after all gem references are expanded so the same variable values propagate into embedded gems.
- Consequences: Nested gems make N+1 Supabase queries (one per unique gem in the tree). For deeply nested structures this adds latency. Cached resolution is a future optimization.
- Alternatives Considered: Flat inclusion only (no recursion) — simpler but far less powerful. Pre-compilation at save time — more complex, harder to keep in sync.
- Supersedes/Superseded By: None

### ADR-004 — Next.js `/api/*` proxy rewrite instead of CORS
- Date: 2026-04-15
- Status: Accepted
- Context: The frontend needs to call the FastAPI backend. Exposing the backend directly to the browser requires CORS configuration and leaks the backend URL.
- Decision: Use Next.js `rewrites()` in `next.config.ts` to proxy `/api/*` → `http://localhost:8000/*`. In production, set `BACKEND_URL` env var. The browser only ever talks to the Next.js origin.
- Consequences: Slightly more complex Next.js config. Backend URL is opaque to the browser. Works cleanly in all deployment topologies.
- Alternatives Considered: Direct CORS headers on FastAPI (simpler but exposes backend URL and requires per-origin configuration).
- Supersedes/Superseded By: None

### ADR-005 — Project-Template structure adopted
- Date: 2026-04-15
- Status: Accepted
- Context: gemsAPI was initially scaffolded without a documentation baseline. The poyfather Project-Template defines a standard set of root docs and scaffold directories for AI-oriented projects.
- Decision: Adopt Project-Template structure: add `AGENTS.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `CONTEXT.md`, `DECISIONS.md`, `ROADMAP.md`, `SECURITY.md`, `STANDARDS.md` at root; add `configs/`, `evals/`, `prompts/`, `scripts/`, `src/`, `tests/` directories; add root `requirements.txt` for dev tools.
- Consequences: Higher documentation discipline. `prompts/` directory provides a diff-friendly, code-reviewable home for gem prompt text. `evals/` provides a dedicated place for prompt quality measurement.
- Alternatives Considered: Keep minimal README only — faster initially but creates drift and makes collaboration harder.
- Supersedes/Superseded By: None
