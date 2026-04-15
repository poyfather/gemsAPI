# gemsAPI

## Overview
gemsAPI is a self-hosted prompt library that stores, versions, and serves reusable LLM system prompts ("gems") from a Supabase database. It provides a web UI for managing prompts, a chat interface for testing them, a FastAPI REST layer for programmatic access, and a FastMCP server so any MCP-capable client (Claude Desktop, Cursor, etc.) can read and use gems directly.

## Audience
Engineers and AI builders who want a central, version-controlled store for their LLM system prompts — accessible from code, the browser, and AI agent tooling.

## Core Capabilities
- **Gem management**: create, edit, tag, and search named system prompts via a Next.js web UI.
- **Recursive composition**: embed one gem inside another with `{{gem:name}}` syntax; variables filled at call time with `{variable}` placeholders. Depth-limited (10 levels), cycle-safe.
- **Multi-provider chat testing**: test any gem in-browser against Anthropic (Claude) or OpenAI (GPT) models.
- **REST API**: full CRUD + resolve endpoint via FastAPI. Swagger at `/docs`.
- **MCP server**: FastMCP exposes `list_gems`, `get_gem`, `resolve_gem_prompt`, `chat_with_gem`, and `create_gem` as tools plus `gems://` resources — compatible with Claude Desktop and any MCP client.

## Quickstart

### Prerequisites
- Python 3.12+, Node 20+
- A free [Supabase](https://supabase.com) project
- `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY`

### Setup
```bash
# 1. Clone
git clone https://github.com/poyfather/gemsAPI.git && cd gemsAPI

# 2. Environment
cp .env.example .env
# Fill in: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY

# 3. Supabase — run supabase/schema.sql in your project SQL editor

# 4. Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
# API: http://localhost:8000  |  Docs: http://localhost:8000/docs

# 5. Frontend (new terminal)
cd frontend && npm install && npm run dev
# UI: http://localhost:3000

# 6. Dev tools (from repo root)
pip install -r requirements.txt   # installs pytest + ruff
.\scripts\setup.ps1               # Windows convenience
.\scripts\test.ps1                # lint + test
```

### Docker (all-in-one)
```bash
cp .env.example .env
docker compose up --build
```

### MCP (Claude Desktop)
Add to `~/.claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "gemsAPI": {
      "command": "python",
      "args": ["/absolute/path/to/gemsAPI/backend/mcp_server.py"]
    }
  }
}
```

## Gem Syntax
| Syntax | Purpose |
|--------|---------|
| `{variable}` | Placeholder filled at call time |
| `{{gem:name}}` | Embed another gem recursively |

## Documentation Map
- System context and goals: `CONTEXT.md`
- Architecture and data flow: `ARCHITECTURE.md`
- Security policy: `SECURITY.md`
- Coding and testing standards: `STANDARDS.md`
- Decision history (ADRs): `DECISIONS.md`
- Development roadmap: `ROADMAP.md`
- Release notes: `CHANGELOG.md`
- Agent workflow guide: `AGENTS.md`

## Template Bootstrap Checklist
- [x] Required docs exist at root.
- [x] Scaffold directories exist (`src/`, `tests/`, `prompts/`, `evals/`, `configs/`, `scripts/`).
- [x] Backend dependencies install from `backend/requirements.txt`.
- [x] Root dev dependencies install from `requirements.txt` (`pytest`, `ruff`).
- [ ] `ruff check .` passes.
- [ ] `pytest -q` passes.
- [ ] Supabase schema applied and seed gems visible in UI.
