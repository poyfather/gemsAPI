# Security policy

## Supported versions

| Version | Supported |
|---|---|
| Latest tagged release on `main` | Yes |
| Older tags | No |

Lapidary is pre-1.0. Fixes ship as a new tagged release with a note in `CHANGELOG.md`; there are no backport branches.

## Reporting a vulnerability

Please do **not** open a public issue for security problems.

Use GitHub's private vulnerability reporting: **Security, then Report a vulnerability** on this repository (https://github.com/poyfather/lapidary/security/advisories/new). If that is unavailable, contact the maintainer through the [poyfather](https://github.com/poyfather) profile with "Lapidary security" in the subject.

Include what you found, how to reproduce it, which component is affected (FastAPI backend, MCP server over stdio or at `/mcp`, Next.js frontend, the database schema, Docker Compose, Lapidary Console, the Lapidary Helper service, the Windows installer), and the version or commit. Do not include real API keys or Supabase keys in the report.

## Response

You will get an acknowledgement within 7 days and a fix or a decision within 30 days. Credential exposure and unauthorised data access are handled first. Credit is given in the release notes unless you ask otherwise.

## What to know before deploying

The rest of this file is the operating policy for running Lapidary. The short version: every REST call (including the OpenAI-compatible `/v1` routes) and every call to MCP over HTTP at `/mcp` needs an API key, either the shared `GEMS_API_KEY` or a per-client key from `GEMS_CLIENT_KEYS`, checked in constant time; only `/` and `/health` are open. A key grants the whole library; keys are not yet scoped (roadmap 57). The stdio MCP server has no gate of its own: it trusts whoever can start it on the machine. Hosted on Supabase, the database trusts only the service role key, with row level security on every table denying every other role (ADR-006 in `DECISIONS.md`); the default SQLite store is a file readable by the account that runs the backend. Keep the services on a private network or behind TLS and a reverse proxy.

## Security scope and ownership

- **Owner**: poyfather (repo maintainer).
- **Scope**: all components of Lapidary: FastAPI backend, FastMCP server (stdio and HTTP), Next.js frontend, the SQLite and Supabase schemas, Docker Compose configuration, environment variable handling, Lapidary Console, the Lapidary Helper service and the Windows installer.
- **Environments covered**: the Windows console on one PC, local development, self-hosted Docker, and split deploy (backend and frontend on separate hosts).

## Credential handling policy

- Store all secrets (Supabase URL, service role key, LLM API keys, `GEMS_API_KEY`) in `.env` files only. `.env` and `.env.local` are in `.gitignore` and must never be committed.
- Use `SUPABASE_SERVICE_ROLE_KEY` for server-side backend access. Never expose this key in frontend code or public endpoints.
- The anon key is not used anywhere. Row level security has no policies for the `anon` or `authenticated` roles, so a leaked anon key reads nothing. Do not add a permissive policy to make the anon key work; see ADR-006.
- Separate keys by environment (dev and prod). Do not reuse production keys in development.
- Give each client its own key in `GEMS_CLIENT_KEYS` (`name:key,name:key`) so one can be revoked without touching the others; the name is recorded with the call.
- Lapidary Console keeps provider keys encrypted with the operating system's credential protection (Electron `safeStorage`: DPAPI on Windows), generates its own `GEMS_API_KEY` on first start, and runs the backend and UI on `127.0.0.1` only.
- Rotate API keys immediately if a `.env` file is accidentally committed or a key is logged, screenshotted, or shared in any communication.
- Never log, print, or include API keys in error messages, prompts, screenshots, or tickets.

## Data access and classification policy

- **Public**: gem names, descriptions, tags, and model metadata. Safe to display in the UI.
- **Internal**: gem system prompts. They may contain business logic or proprietary instructions. Treat as internal.
- **Sensitive**: Supabase credentials and LLM API keys. Server-side only, never sent to the frontend or to MCP clients.
- Grant database access by minimum required scope. The backend uses the service role key; replace it with a scoped role for production multi-user deployments.
- Supabase RLS is enabled on every table (`gems`, `gem_versions`, `eval_cases`, `eval_runs`, `runs`, `run_events`, `memories`, `pipelines`, `pipeline_runs`) with no policies: only the service role, used by the backend and the MCP server, can read or write.
- Memory stores what runs learned and what users or clients asked it to remember; text inside `<private>` tags is never stored. Treat memories as internal, like prompts. Installations created before October 2026 should run `supabase/lock_down_rls.sql` to drop the old `allow_all` policy. A multi-user deployment needs an `owner_id` column and per-user policies first (roadmap item 21).

## AI restrictions and safety boundaries

- Lapidary runs prompts, assistants and pipelines only when a person or an authenticated client asks (a chat, a run, a test, an MCP tool call). It schedules nothing on its own. Assistants (gems of kind `agent`) then work step by step with the tools their gem lists, up to `AGENT_MAX_STEPS` model turns, and every step is recorded in `runs` and `run_events`.
- Chat, runs, tests, comparisons and the MCP `chat_with_gem`, `run_agent` and `run_gem_evals` tools send real requests to cloud providers and incur cost unless a local model answers. There are no spend limits or rate limits yet (roadmap 55); do not expose the API on a public network without a rate limit in front of it. Tests and comparisons show an estimate first and are capped by `GEMS_EVAL_MAX_CALLS`.
- Pipelines never let a model decide it is done: a builder's output passes test, visual and adversarial gates, and a person accepts the result.
- Human review is recommended before deploying a gem that will be used in automated or production pipelines.
- Validate gem output before using it in high-impact actions (sending emails, writing to databases, and so on).
- The built-in `run_powershell` tool runs scripts as the backend's user. It is risky, so a run pauses for approval before every call; the `windows_operator` gem is written to read before it changes anything. Do not mark it safe.
- Tools from other MCP servers (`configs/mcp_servers.json`) run with that server's privileges on the machine that runs the backend. They are risky by default, which pauses a run for approval; mark a server `"risky": false` only when its tools cannot change anything. The config file may hold auth headers and is git-ignored.

- Lapidary Helper, the console's Windows service, runs as SYSTEM so installs and updates need no administrator prompt. It is the most privileged part of the project, so it accepts only fixed requests over a local pipe (no remote clients; SYSTEM, Administrators and signed-in users only), installs only allowlisted winget and PowerShell Gallery ids written at build time, never runs a command it is sent, and updates the console only to a newer GitHub release that matches its published checksum and, on signed builds, is signed by the exact publisher pinned at build time. Any signed-in user of the PC can start it and ask it to install an allowlisted tool or update the console; that is the point, and nothing else is reachable. Only administrators can stop, change or remove it. Reports about the helper are treated as P0. See `desktop/README.md`.

## Environment and deployment controls

- Dev and production must use separate Supabase projects and separate API keys.
- The `.env.example` file documents required variables but contains no real secrets.
- For Docker Compose deployments, pass secrets via the `.env` file. Do not hardcode them in `docker-compose.yml`.
- Do not bind the FastAPI backend to `0.0.0.0` in production without a reverse proxy (nginx or Caddy) and TLS.
- The stdio MCP server exposes no network port. MCP over HTTP is the API's `/mcp` path, behind the same API keys; set `GEMS_MCP_ALLOWED_HOSTS` when a tunnel or proxy fronts it.
- The Windows installer is unsigned until signing credentials are configured (`desktop/README.md`, Code signing). Until then, verify a download against the `.sha256` file published with the release; once signing is on, the helper accepts console updates only from the pinned publisher.

## Incident response

- For suspected credential exposure: immediately revoke the exposed key, rotate it, audit recent usage, and document the incident in `DECISIONS.md`.
- Triage priority: credential exposure and unauthorised data access are P0; functionality bugs are P2 or below.

## Compliance notes

- Lapidary is a personal tool with no current regulatory or contractual compliance requirements.
- If deployed to handle user data or used in a commercial product, review GDPR and CCPA requirements for any prompt data that may contain personal information.
