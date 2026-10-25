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

Include what you found, how to reproduce it, which component is affected (FastAPI backend, MCP server, Next.js frontend, Supabase schema, Docker Compose), and the version or commit. Do not include real API keys or Supabase keys in the report.

## Response

You will get an acknowledgement within 7 days and a fix or a decision within 30 days. Credential exposure and unauthorised data access are handled first. Credit is given in the release notes unless you ask otherwise.

## What to know before deploying

The rest of this file is the operating policy for running Lapidary. The short version: the only gate on the REST API is the shared `GEMS_API_KEY`; the MCP server talks to Supabase directly with no gate of its own; and the database trusts only the service role key, with row level security denying every other Supabase role (ADR-006 in `DECISIONS.md`). Keep both services on a private network or behind TLS and a reverse proxy.

## Security scope and ownership

- **Owner**: poyfather (repo maintainer).
- **Scope**: all components of Lapidary: FastAPI backend, FastMCP server, Next.js frontend, Supabase schema, Docker Compose configuration, and environment variable handling.
- **Environments covered**: local development, self-hosted Docker, and split deploy (backend and frontend on separate hosts).

## Credential handling policy

- Store all secrets (Supabase URL, service role key, LLM API keys, `GEMS_API_KEY`) in `.env` files only. `.env` and `.env.local` are in `.gitignore` and must never be committed.
- Use `SUPABASE_SERVICE_ROLE_KEY` for server-side backend access. Never expose this key in frontend code or public endpoints.
- The anon key is not used anywhere. Row level security has no policies for the `anon` or `authenticated` roles, so a leaked anon key reads nothing. Do not add a permissive policy to make the anon key work; see ADR-006.
- Separate keys by environment (dev and prod). Do not reuse production keys in development.
- Rotate API keys immediately if a `.env` file is accidentally committed or a key is logged, screenshotted, or shared in any communication.
- Never log, print, or include API keys in error messages, prompts, screenshots, or tickets.

## Data access and classification policy

- **Public**: gem names, descriptions, tags, and model metadata. Safe to display in the UI.
- **Internal**: gem system prompts. They may contain business logic or proprietary instructions. Treat as internal.
- **Sensitive**: Supabase credentials and LLM API keys. Server-side only, never sent to the frontend or to MCP clients.
- Grant database access by minimum required scope. The backend uses the service role key; replace it with a scoped role for production multi-user deployments.
- Supabase RLS is enabled on the `gems` table with no policies: only the service role, used by the backend and the MCP server, can read or write. Installations created before October 2026 should run `supabase/lock_down_rls.sql` to drop the old `allow_all` policy. A multi-user deployment needs an `owner_id` column and per-user policies first (roadmap item 21).

## AI restrictions and safety boundaries

- Lapidary is a prompt management tool, not an autonomous agent. It executes prompts only when explicitly triggered by a user action (chat request or MCP tool call).
- The `chat_with_gem` MCP tool and the `/chat` endpoint send real LLM requests and incur API costs. Do not expose either on a public network without authentication and a rate limit.
- Human review is recommended before deploying a gem that will be used in automated or production pipelines.
- Validate gem output before using it in high-impact actions (sending emails, writing to databases, and so on).
- Tools from other MCP servers (`configs/mcp_servers.json`) run with that server's privileges on the machine that runs the backend. They are risky by default, which pauses a run for approval; mark a server `"risky": false` only when its tools cannot change anything. The config file may hold auth headers and is git-ignored.

## Environment and deployment controls

- Dev and production must use separate Supabase projects and separate API keys.
- The `.env.example` file documents required variables but contains no real secrets.
- For Docker Compose deployments, pass secrets via the `.env` file. Do not hardcode them in `docker-compose.yml`.
- Do not bind the FastAPI backend to `0.0.0.0` in production without a reverse proxy (nginx or Caddy) and TLS.
- The MCP server runs over stdio by default and does not expose a network port. If converting to an HTTP or SSE transport, add authentication first.

## Incident response

- For suspected credential exposure: immediately revoke the exposed key, rotate it, audit recent usage, and document the incident in `DECISIONS.md`.
- Triage priority: credential exposure and unauthorised data access are P0; functionality bugs are P2 or below.

## Compliance notes

- Lapidary is a personal tool with no current regulatory or contractual compliance requirements.
- If deployed to handle user data or used in a commercial product, review GDPR and CCPA requirements for any prompt data that may contain personal information.
