# Support

## Something is broken

Open a **Bug report** issue: https://github.com/poyfather/gemsAPI/issues/new/choose. Say which part failed (backend, MCP server, UI, resolution, schema), the version or commit, and paste the error with any keys redacted.

## How do I set it up

The README quick start covers the Supabase project, the `.env` files, running the backend and frontend, Docker Compose and the Claude Desktop MCP config. [ARCHITECTURE.md](ARCHITECTURE.md) explains the request flow and lists the MCP tools. A running backend serves its own API reference at `/docs`.

Common first-run problems:

- **Server refuses to start with "GEMS_API_KEY is not set".** Add the key to `.env` in `backend/` (or the repo root for Docker Compose). The same value goes in `frontend/.env.local`.
- **UI shows 401 on every request.** The frontend's `GEMS_API_KEY` does not match the backend's, or `frontend/.env.local` is missing.
- **"Gem not found" for a seed gem.** Run `supabase/schema.sql` in the Supabase SQL editor; it is idempotent.
- **MCP client cannot see the tools.** The MCP server reads `backend/.env`, so run it with an absolute path to `backend/mcp_server.py` and the backend's virtualenv Python.

## I want to add or change a gem

Open a **Gem proposal** issue, or a pull request that updates both `prompts/<name>.md` and `supabase/schema.sql` with an eval note. [CONTRIBUTING.md](CONTRIBUTING.md) has the details.

## I have a question that is not a bug

Open a **Feature request** issue and say it is a question. Discussions are not enabled on this repo yet.

## Security

See [SECURITY.md](SECURITY.md). Please do not report security problems in public issues.
