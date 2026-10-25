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
- Context: Lapidary needs to be accessible from Claude Desktop and other MCP clients. Building the MCP protocol from scratch adds significant boilerplate.
- Decision: Use FastMCP 2.x (jlowin/fastmcp) which provides a decorator-based API over the official MCP SDK, stdio transport by default, and resource support.
- Consequences: Takes a dependency on a third-party library over the official Anthropic MCP SDK. FastMCP 2.x API is stable but relatively new.
- Alternatives Considered: Direct use of the `mcp` package (more boilerplate), HTTP/SSE transport (adds network complexity).
- Supersedes/Superseded By: None

### ADR-003 — Recursive `{{gem:name}}` composition with depth limit
- Date: 2026-04-15
- Status: Accepted
- Context: Composable prompts are the core differentiator of Lapidary. A gem should be able to embed another gem inline, enabling reusable building blocks (e.g. a `base_personality` gem shared across many specialized gems).
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
- Context: Lapidary was initially scaffolded without a documentation baseline. The poyfather Project-Template defines a standard set of root docs and scaffold directories for AI-oriented projects.
- Decision: Adopt Project-Template structure: add `AGENTS.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `CONTEXT.md`, `DECISIONS.md`, `ROADMAP.md`, `SECURITY.md`, `STANDARDS.md` at root; add `configs/`, `evals/`, `prompts/`, `scripts/`, `src/`, `tests/` directories; add root `requirements.txt` for dev tools.
- Consequences: Higher documentation discipline. `prompts/` directory provides a diff-friendly, code-reviewable home for gem prompt text. `evals/` provides a dedicated place for prompt quality measurement.
- Alternatives Considered: Keep minimal README only — faster initially but creates drift and makes collaboration harder.
- Supersedes/Superseded By: None

### ADR-006 — Single-tenant access model: the API key is the gate, the database trusts only the server
- Date: 2026-10-25
- Status: Accepted
- Context: ADR-001 enabled row level security on `gems` and then added an `allow_all` policy, while the backend connects with the service role key, which bypasses RLS entirely. So RLS protected nothing, the docs said "tighten before multi-user use" without saying how, and `.env.example` offered the anon key as an alternative that would have hit the same open policy. Roadmap item 9 asked for a decision between hardening the single-tenant model and designing multi-user access now.
- Decision: Lapidary is single-tenant for now. One deployment serves one person or one trusting team. Access control is the shared `GEMS_API_KEY` on the REST edge, checked in constant time by `backend/app/auth.py`. The database trusts only the server: the backend and the MCP server connect with the service role key, the `allow_all` policy is dropped, and no policy is defined for the `anon` or `authenticated` roles, so a leaked anon key reads nothing. The anon key path is removed from `database.py` and `.env.example`.
- Consequences: RLS now does something useful (default deny for every Supabase client except the service role) instead of pretending to. There is one secret to protect on the database side and one on the API side, which the docs can state plainly. Per-client API keys (roadmap item 10) can be added without touching the database model. Multi-user (item 21) remains possible later: it would add `owner_id`, policies for `authenticated`, and user JWTs from Supabase Auth, replacing the service role for user traffic. Nothing decided here blocks that, and the migration file pattern introduced with this change is how that schema change would ship.
- Alternatives Considered: Design multi-user now (an `owner_id` column, per-user policies, Supabase Auth in the UI). Rejected for now because there is no second user, the practitioner roadmap puts sharing last, and every item ahead of it (history, evals, typed variables) is easier to build on a single-tenant schema. Keep the anon key as a read-only path with a `SELECT` policy. Rejected because the anon key is designed to be public in Supabase apps and gem prompts are classified internal in `SECURITY.md`.
- Supersedes/Superseded By: Refines ADR-001 (the RLS clause). Will be superseded by the multi-user ADR when item 21 is taken up.

### ADR-007 — Agent harness: a thin loop in the backend, gems as agent definitions
- Date: 2026-10-25
- Status: Accepted
- Context: Lapidary stores, composes and serves prompts, and every surface makes exactly one model call. A harness needs three more things: tools the model may call, a loop that executes them and feeds results back, and a record of what happened. Three ways to get there were weighed: stay a control plane and delegate execution (for Anthropic, Managed Agents); own a thin loop in the backend; or build a full framework with memory, sub-agents and a sandbox.
- Decision: own a thin loop. A gem gains a `kind` (`prompt` or `agent`) and a list of `tools`. `backend/app/agents/` holds a tool registry (Python functions with a JSON schema derived from their signature, each marked risky or not), a provider-neutral run loop with a step limit, and a run store (`runs` and `run_events` tables) that records every model turn, tool call and tool result. `llm_service` gains one tool-capable turn per provider so the loop is the same for Anthropic and OpenAI. The loop is exposed as `POST /agents/{name}/runs` (JSON or SSE), `GET /runs/{id}`, and the MCP tool `run_agent`. The first tools are read-only and about gems themselves. Managed Agents stays an option as an execution backend for a gem later; the definition and the run record would be shared.
- Consequences: Lapidary can now act, not only answer, on both providers, from REST, MCP and (later) the UI. Run records make agents debuggable, evaluable (trajectory evals, roadmap item 28) and billable. The project owns context management, tool sandboxing and failure modes, which is why the first tools are boring, risky tools are refused unless a run opts in, and every run has a step cap. Approval gates with resume, remote MCP and HTTP tool sources, a run viewer in the UI and the Managed Agents backend are separate roadmap items.
- Alternatives Considered: Managed Agents only: smallest build and a hosted sandbox, but one provider and no loop of our own. A full framework: rejected, the unit of value stays a versioned, evaluated prompt that is now allowed to act.
- Supersedes/Superseded By: None.

### ADR-008 — Project renamed to Lapidary
- Date: 2026-10-25
- Status: Accepted
- Context: "gemsAPI" described the first version: an API over gems. Since ADR-007 the project is also a web UI, an MCP server and an agent harness, and the name no longer says what it is. A gem stays the unit of value, so the new name should keep the metaphor.
- Decision: The product is Lapidary, the craftsperson who cuts and polishes rough stones into gems. User-facing names change: the README and docs, the FastAPI title and root endpoint, the MCP server name (`lapidary`), the web UI branding and the frontend package name. Unchanged on purpose: the data model word "gem", the `GEMS_*` environment variables, the repository URL (renaming it is a separate, reversible GitHub action that redirects old links), and changelog history below 0.3.0.
- Consequences: MCP client configs that referenced the server as `gemsAPI` keep working (the key in the client config is the user's own label; the server name only shows in client UIs). No API path or env var changes, so existing installs need nothing.
- Alternatives Considered: Loupe (the jeweler's magnifier; strong on inspection, weak on composition), Facet (a face of a gem; too generic as a word), keeping gemsAPI (undersells the harness).
- Supersedes/Superseded By: None.

### ADR-009 — Lapidary Desktop: a Windows 11 application that runs all of Lapidary
- Date: 2026-10-25
- Status: Proposed (accepted when the first desktop PR merges)
- Context: Lapidary runs as two services and a Supabase project, started from a terminal. The owner wants it as one Windows 11 desktop application with Claude (Anthropic) and ChatGPT (OpenAI) connected, and the reverse engineering workflow from `rea_analyst` as the flagship use. The development machine is a Mac, so Windows builds and tests have to run in CI.
- Decision: Build the desktop app as an Electron shell around the existing pieces rather than a rewrite. The shell spawns two sidecars: the Next.js standalone server, run with Electron's bundled Node, and the FastAPI backend as a single-file executable built with PyInstaller on a Windows runner; the window loads the local UI. Storage gets a small repository layer with two backends, SQLite (default on the desktop, in the user's app data folder) and Supabase (the hosted mode as today). Provider keys are entered in a Settings screen and stored with Electron's safeStorage (DPAPI on Windows), passed to the backend as environment variables; MCP servers are configured on the same screen and written to the app's `mcp_servers.json`. REA ships as a bundled npm dependency so no global install is needed. "Connected" works both ways: Claude and ChatGPT as providers through keys, and Claude Desktop and ChatGPT as clients of Lapidary's own MCP server, which the app also exposes over streamable HTTP on localhost behind the API key. Packaging is an NSIS installer from electron-builder; CI on `windows-latest` builds the backend executable and the installer and smoke-tests a launch (health check, one prompt gem run against a fake provider).
- Consequences: Four new roadmap items (36 to 40), in dependency order: the storage layer first, because every other piece assumes a local database; then the shell and installer; then settings and the HTTP MCP endpoint; then REA bundling and first-run setup. Two build pipelines to maintain. The hosted mode keeps working unchanged. All verification of the Windows build happens in CI until someone runs it on a real machine.
- Alternatives Considered: Tauri (smaller binaries and a Rust shell; rejected for now because the team's toolchain is Node and Python and the sidecar story is the same work). A .NET WebView2 shell (native, but a third language). Keeping the services and shipping a PowerShell installer (no window, no settings screen, no key storage; it is what `scripts/setup.ps1` already is).
- Supersedes/Superseded By: None.
