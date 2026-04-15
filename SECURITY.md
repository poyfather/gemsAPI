# SECURITY

## Security Scope and Ownership
- **Owner**: poyfather (repo maintainer).
- **Scope**: all components of gemsAPI — FastAPI backend, FastMCP server, Next.js frontend, Supabase schema, Docker Compose configuration, and environment variable handling.
- **Environments covered**: local development, self-hosted Docker, and split-deploy (backend + frontend on separate hosts).

## Credential Handling Policy
- Store all secrets (Supabase URL, service role key, LLM API keys) in `.env` files only. `.env` is in `.gitignore` and must never be committed.
- Use `SUPABASE_SERVICE_ROLE_KEY` for server-side backend access. Never expose this key in frontend code or public endpoints.
- Use least-privilege: if read-only gem access is sufficient for a use case, use `SUPABASE_ANON_KEY` with appropriate RLS policies.
- Separate keys by environment (dev/prod). Do not reuse production keys in development.
- Rotate API keys immediately if a `.env` file is accidentally committed or a key is logged, screenshotted, or shared in any communication.
- Never log, print, or include API keys in error messages, prompts, screenshots, or tickets.

## Data Access and Classification Policy
- **Public**: gem names, descriptions, tags, and model metadata — safe to display in the UI.
- **Internal**: gem system prompts — may contain business logic or proprietary instructions. Treat as internal.
- **Sensitive**: Supabase credentials and LLM API keys — server-side only, never sent to frontend or MCP clients.
- Grant database access by minimum required scope. The backend uses the service role key; this should be replaced with a scoped role for production multi-user deployments.
- Supabase RLS is enabled on the `gems` table with an open policy by default — **tighten this policy before any public or multi-user deployment**.

## AI Restrictions and Safety Boundaries
- gemsAPI is a prompt management tool, not an autonomous agent. It executes prompts only when explicitly triggered by a user action (chat request or MCP tool call).
- The `chat_with_gem` MCP tool sends real LLM requests and incurs API costs. Do not expose the MCP server on a public network without authentication.
- Human review is recommended before deploying a gem that will be used in automated or production pipelines.
- Validate gem output before using it in high-impact actions (sending emails, writing to databases, etc.).

## Environment and Deployment Controls
- Dev and production must use separate Supabase projects and separate API keys.
- The `.env.example` file documents required variables but contains no real secrets.
- For Docker Compose deployments, pass secrets via `.env` file — do not hardcode them in `docker-compose.yml`.
- Do not bind the FastAPI backend to `0.0.0.0` in production without a reverse proxy (nginx/Caddy) and TLS.
- The MCP server runs over stdio by default and does not expose a network port. If converting to SSE transport, add authentication.

## Incident Reporting and Response
- Report vulnerabilities by opening a private GitHub security advisory on this repo.
- For suspected credential exposure: immediately revoke the exposed key, rotate it, audit recent usage, and document the incident in `DECISIONS.md`.
- Triage priority: credential exposure and unauthorized data access are P0; functionality bugs are P2 or below.

## Compliance Notes
- gemsAPI is a private tool with no current regulatory or contractual compliance requirements.
- If deployed to handle user data or used in a commercial product, review GDPR/CCPA requirements for any prompt data that may contain PII.
