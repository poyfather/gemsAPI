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

### ADR-009 — Lapidary Console: a Windows 11 management application for AI tooling
- Date: 2026-10-25
- Status: Proposed (accepted when the first desktop PR merges)
- Context: The owner wants one Windows 11 application with a GUI that installs and manages the AI tools on a machine and connects them to each other, the way Kaseya or ManageEngine are consoles for IT: Claude Desktop, ChatGPT, Open WebUI (https://github.com/open-webui/open-webui), local models through Ollama, and MCP servers such as REA (Reverse Engineer Anything). Lapidary today is a prompt library and agent harness with an MCP server; it runs as two services plus Supabase, started from a terminal, and only MCP clients can reach it. The development machine is a Mac, so Windows builds and tests run in CI.
- Decision: Lapidary becomes the hub and gains a console around it. The hub: Lapidary exposes an OpenAI-compatible API (`/v1/models`, `/v1/chat/completions` with streaming, bearer auth with the same key) so every gem and agent is a model to Open WebUI and any OpenAI-compatible client, keeps its MCP server for Claude Desktop and ChatGPT (stdio now, streamable HTTP in the app), and keeps the agent loop with tools from other MCP servers. The console: an Electron application in `desktop/` with a management UI of its own (dashboard, components, connections, settings, logs) that embeds the Lapidary UI for gems, chat and runs. Its main process does the privileged work: detect what is installed (winget, Docker Desktop, Node, Claude Desktop, ChatGPT, Ollama, Open WebUI), install and update through winget and Docker, start and stop the pieces, write client configs (Claude Desktop and ChatGPT MCP entries for REA and for Lapidary, Open WebUI's provider list pointing at Lapidary, OpenAI and Ollama), store provider keys with Electron safeStorage, run the backend (PyInstaller single file) and the Next.js standalone server as sidecars, and tail their logs. Storage on the desktop is SQLite behind a repository layer, Supabase stays for the hosted mode. REA ships as a bundled npm dependency. Packaging is an NSIS installer from electron-builder, built and smoke-tested on `windows-latest`.
- Consequences: Roadmap items 36 to 42 in dependency order. The OpenAI-compatible API is first because it is pure backend, testable on any machine, and is the connection to Open WebUI. Two build pipelines to maintain. The hosted mode keeps working unchanged. Everything Windows-specific is verified in CI until it runs on a real machine.
- Alternatives Considered: Tauri (smaller binaries, Rust shell; rejected for now, the toolchain is Node and Python and REA is an npm package). A .NET WebView2 shell (native Windows, a third language). Building the console into Open WebUI as a plugin (it would not be able to install Open WebUI itself).
- Supersedes/Superseded By: None.

### ADR-010 — Lapidary Memory: observations that persist across runs, chats and clients
- Date: 2026-10-25
- Status: Proposed (accepted when the first memory PR merges)
- Context: Every run and chat starts from nothing. claude-mem (https://github.com/thedotmack/claude-mem) shows what persistent memory for an agent looks like: observations captured from sessions, compressed by a model into summaries, kept in SQLite with full-text search, and brought back by progressive disclosure (search a compact index, then fetch the few records that matter) so context stays small. Lapidary now has the pieces to do the same for every surface at once: a storage layer, a run record, built-in tools, an MCP server and an OpenAI-compatible API.
- Decision: Add a `memories` table to both storage backends (id, kind: observation, summary, decision, preference, lesson, handoff or note; text; source: run, chat, mcp, console or user; gem_name; run_id; tags; scope; created_at) with full-text search (FTS5 in SQLite, `tsvector` in Postgres). Capture: when a run finishes, a short summary of what was asked, which tools ran and what was found or changed is stored as an observation, written by a `memory_summarizer` gem when a provider key is available and as a deterministic digest otherwise; text inside `<private>` tags is never stored; chats store nothing unless asked. Recall, in claude-mem's three steps: `search_memory(query, scope, limit)` returns a compact index (ids, dates, one line each), `get_memories(ids)` returns full text, `remember(text, tags)` and `forget(id)` write. These are built-in agent tools, MCP tools (so Claude Desktop, ChatGPT and Open WebUI share one memory through Lapidary) and REST routes under `/memory`. Injection: a gem with `memory: true` gets the top matches for the user's message prepended to its prompt inside a `<memory>` block, capped in size. A Memory view in the web UI lists, searches and deletes. Embeddings are a later addition behind the same interface.
- Consequences: One memory for every client on the machine, which is the point of the console. Memory is scoped (default `default`) so projects can be kept apart. Everything stored is readable and deletable by the owner. Summaries cost one small model call per run and are skipped without a key.
- Alternatives Considered: Running claude-mem itself alongside Lapidary (it is Claude Code centred, hook driven and Bun based; the ideas transfer, the process does not). Vector search first (more moving parts than a local app needs on day one; FTS covers recall for one person's history).
- Supersedes/Superseded By: None.

### ADR-011 — Hybrid local and cloud: gates, shared memory, local models, parallel work
- Date: 2026-10-25
- Status: Proposed
- Context: A hybrid development stack was shared as a reference (Paseo for launching parallel worktrees and agents, Codex for planning and hard reasoning, OpenCode for local coding agents, oMLX serving Qwen3-Coder, Devstral and Qwen3-VL on Apple Silicon, Ratchet Loop to force every checkpoint through tests, visual verification, adversarial review and acceptance, and Second Brain MCP for memory shared by every agent). Its principle is the one Lapidary Console should adopt: keep high-volume implementation and review local, spend a frontier model where reasoning quality is worth it, and never let a model decide it is done.
- Decision: Four additions, each on top of what exists. (1) **Local models as a provider**: a third provider, `local`, is any OpenAI-compatible server (Ollama on Windows, oMLX on Apple Silicon, LM Studio, vLLM) at a configured base URL; its model list comes from the server; gems pick it like any provider, so one pipeline can put Claude on planning and a local model on the build and the review. (2) **Gates**: a pipeline is an ordered list of gems with roles (builder, then gates: tests, visual or behaviour verification, adversarial review by a different model or provider, human acceptance); a gate gem returns pass or fail with findings, a failure is fed back to the builder with the findings, and the pipeline only reaches acceptance when every gate passed; the existing approval gate is the acceptance step; every attempt is a run, so the record shows what failed and why. (3) **Shared memory** per ADR-010, with the kinds Second Brain uses (decisions, preferences, lessons, handoffs) and exposure over MCP so Codex, OpenCode, Claude Desktop and ChatGPT read and write the same memory. (4) **Workbench**: the console launches parallel runs, each in its own git worktree when a repository is involved, and shows them side by side. Codex and OpenCode join the Connections view as MCP clients of Lapidary.
- Consequences: Roadmap items 44 to 46. Local models make the console useful without any cloud key and cheap at volume; gates are where the value of memory and runs compounds, because a failed gate becomes a lesson. Nothing is 100 percent local by design.
- Alternatives Considered: Adopting the reference tools as they are (Ratchet Loop and Second Brain are their author's own projects, Codex-centred and Bun or Cloudflare based; the ideas transfer, the processes are rebuilt inside Lapidary so every client gets them). Vision review with a cloud model only (fine as a default; a local vision model is just another `local` entry).
- Supersedes/Superseded By: None.

### ADR-012 — Made for someone who does not know AI yet
- Date: 2026-10-25
- Status: Accepted
- Context: The console is for two kinds of people. Anyone at all on the Basic path, a student, a parent, a marketing person, someone at home, who does not know much about AI but should be able to install this platform and get something genuinely useful from it; and a system administrator in IT on the Advanced path who wants to choose components, keys, storage, servers, ports and policies and see everything. Every earlier decision (the hub, the harness, memory, gates, local models) is a capability; this one is about who they are for and therefore how they must appear.
- Decision: The console speaks plain language and ships working defaults. Rules: (1) No jargon on the surface. "MCP" is "connect", a "gem" is "a prompt" where the person is new, a "run" is "what the assistant did"; acronyms appear only in the details. (2) Nothing requires editing a file. Keys, servers and connections are forms with a test button; the console writes the files. (3) Working on day one without a cloud key: the first run offers local models (Ollama) and the local chat (Open WebUI) as the default path, cloud keys as an upgrade. (4) Outcomes, not components: the home screen offers recipes, one click each ("a private chat on this PC", "let Claude and ChatGPT use my prompts", "an assistant that can run safe PowerShell for me", "understand how an app works"), and each recipe installs and connects what it needs and explains what it did. (5) Every component says what it is for in one sentence and why you would want it. (6) Safe by default: anything that changes the machine asks first, in plain words, and can be undone or explained. (7) A self-check ("Doctor") that finds what is broken and offers the fix. (8) The power-user surfaces (the web UI, the API, pipelines) stay one click away but never in the way. (9) Two setup paths on the same screens: **Basic** asks what you want and does the rest with recipes and defaults, says in plain words what is private (local models keep everything on this PC) and what costs money (cloud keys are paid by use), and never needs an account to get started; **Advanced** walks a system administrator through each choice (which components, cloud keys or local models or both, SQLite or Supabase, which servers to connect, ports, where data lives, what assistants may do without asking, logging) and can be switched on later as an Advanced toggle that reveals the details on every screen. One UI, one more switch, not two products.
- Consequences: Roadmap items 47 to 50 go ahead of the hybrid work in the console: the guided first run and recipes first, the plain-language pass second, the doctor third. The console's copy, names and defaults are reviewed against this record in every PR that touches them. The retro look stays; it is the words that get simpler.
- Alternatives Considered: Two separate applications or UIs for the two people (twice the surface to maintain, and the expert one leaks through); the Advanced toggle on one UI is the answer. Hiding capability (the opposite of the goal; the point is that a newcomer gets the real thing).
- Supersedes/Superseded By: Governs ADR-009 and ADR-011 wherever a surface choice is involved.
