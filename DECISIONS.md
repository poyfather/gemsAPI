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
- Consequences: Requires a Supabase project for setup. Free tier is sufficient for personal use. The original open RLS policy was replaced by ADR-006.
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

### ADR-006 — Single-tenant access model: the API key is the gate, the database trusts only the server
- Date: 2026-10-25
- Status: Accepted
- Context: ADR-001 enabled row level security on `gems` and then added an `allow_all` policy, while the backend connects with the service role key, which bypasses RLS entirely. So RLS protected nothing, the docs said "tighten before multi-user use" without saying how, and `.env.example` offered the anon key as an alternative that would have hit the same open policy. Roadmap item 9 asked for a decision between hardening the single-tenant model and designing multi-user access now.
- Decision: gemsAPI is single-tenant for now. One deployment serves one person or one trusting team. Access control is the shared `GEMS_API_KEY` on the REST edge, checked in constant time by `backend/app/auth.py`. The database trusts only the server: the backend and the MCP server connect with the service role key, the `allow_all` policy is dropped, and no policy is defined for the `anon` or `authenticated` roles, so a leaked anon key reads nothing. The anon key path is removed from `database.py` and `.env.example`.
- Consequences: RLS now does something useful (default deny for every Supabase client except the service role) instead of pretending to. There is one secret to protect on the database side and one on the API side, which the docs can state plainly. Per-client API keys (roadmap item 10) can be added without touching the database model. Multi-user (item 21) remains possible later: it would add `owner_id`, policies for `authenticated`, and user JWTs from Supabase Auth, replacing the service role for user traffic. Nothing decided here blocks that, and the migration file pattern introduced with this change is how that schema change would ship.
- Alternatives Considered: Design multi-user now (an `owner_id` column, per-user policies, Supabase Auth in the UI). Rejected for now because there is no second user, the practitioner roadmap puts sharing last, and every item ahead of it (history, evals, typed variables) is easier to build on a single-tenant schema. Keep the anon key as a read-only path with a `SELECT` policy. Rejected because the anon key is designed to be public in Supabase apps and gem prompts are classified internal in `SECURITY.md`.
- Supersedes/Superseded By: Refines ADR-001 (the RLS clause). Will be superseded by the multi-user ADR when item 21 is taken up.
