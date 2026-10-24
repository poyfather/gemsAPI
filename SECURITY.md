# Security policy

## Supported versions

| Version | Supported |
|---|---|
| Latest tagged release on `main` | Yes |
| Older tags | No |

gemsAPI is pre-1.0. Fixes ship as a new tagged release with a note in `CHANGELOG.md`; there are no backport branches.

## Reporting a vulnerability

Please do **not** open a public issue for security problems.

Use GitHub's private vulnerability reporting: **Security, then Report a vulnerability** on this repository (https://github.com/poyfather/gemsAPI/security/advisories/new). If that is unavailable, contact the maintainer through the [poyfather](https://github.com/poyfather) profile with "gemsAPI security" in the subject.

Include what you found, how to reproduce it, which component is affected (FastAPI backend, MCP server, Next.js frontend, Supabase schema, Docker Compose), and the version or commit. Do not include real API keys or Supabase keys in the report.

## Response

You will get an acknowledgement within 7 days and a fix or a decision within 30 days. Credential exposure and unauthorised data access are handled first. Credit is given in the release notes unless you ask otherwise.

## What to know before deploying

The rest of this file is the operating policy for running gemsAPI. The short version: the only gate on the REST API is the shared `GEMS_API_KEY`, the MCP server talks to Supabase directly with no gate of its own, and the default row level security policy is open. Keep both services on a private network unless you have read [docs/ROADMAP.md](docs/ROADMAP.md) and tightened them.

## Security scope and ownership

- **Owner**: poyfather (repo maintainer).
- **Scope**: all components of gemsAPI: FastAPI backend, FastMCP server, Next.js frontend, Supabase schema, Docker Compose configuration, and environment variable handling.
- **Environments covered**: local development, self-hosted Docker, and split deploy (backend and frontend on separate hosts).

## Credential handling policy

- Store all secrets (Supabase URL, service role key, LLM API keys, `GEMS_API_KEY`) in `.env` files only. `.env` and `.env.local` are in `.gitignore` and must never be committed.
- Use `SUPABASE_SERVICE_ROLE_KEY` for server-side backend access. Never expose this key in frontend code or public endpoints.
- Use least privilege: if read-only gem access is sufficient for a use case, use `SUPABASE_ANON_KEY` with appropriate RLS policies.
- Separate keys by environment (dev and prod). Do not reuse production keys in development.
- Rotate API keys immediately if a `.env` file is accidentally committed or a key is logged, screenshotted, or shared in any communication.
- Never log, print, or include API keys in error messages, prompts, screenshots, or tickets.

## Data access and classification policy

- **Public**: gem names, descriptions, tags, and model metadata. Safe to display in the UI.
- **Internal**: gem system prompts. They may contain business logic or proprietary instructions. Treat as internal.
- **Sensitive**: Supabase credentials and LLM API keys. Server-side only, never sent to the frontend or to MCP clients.
- Grant database access by minimum required scope. The backend uses the service role key; replace it with a scoped role for production multi-user deployments.
- Supabase RLS is enabled on the `gems` table with an open `allow_all` policy by default. **Tighten this policy before any public or multi-user deployment.**

## AI restrictions and safety boundaries

- gemsAPI is a prompt management tool, not an autonomous agent. It executes prompts only when explicitly triggered by a user action (chat request or MCP tool call).
- The `chat_with_gem` MCP tool and the `/chat` endpoint send real LLM requests and incur API costs. Do not expose either on a public network without authentication and a rate limit.
- Human review is recommended before deploying a gem that will be used in automated or production pipelines.
- Validate gem output before using it in high-impact actions (sending emails, writing to databases, and so on).

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

- gemsAPI is a personal tool with no current regulatory or contractual compliance requirements.
- If deployed to handle user data or used in a commercial product, review GDPR and CCPA requirements for any prompt data that may contain personal information.
