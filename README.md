# gemsAPI

A self-hosted prompt library with recursive composition, a web UI, and dual access via REST and MCP.

```
gemsAPI/
├── backend/          FastAPI + FastMCP server
├── frontend/         Next.js 14 web interface
├── supabase/         Database schema
└── docker-compose.yml
```

---

## What it does

- **Manage prompts (gems)** — create, edit, tag, and search reusable system prompts in a clean web UI.
- **Variable substitution** — use `{variable}` placeholders filled at call time.
- **Recursive composition** — embed one gem inside another with `{{gem:name}}`. Depth-limited, cycle-safe.
- **Test in-browser** — built-in chat interface lets you test any gem against Anthropic or OpenAI models.
- **FastAPI** — REST access so any language or tool can fetch and use prompts programmatically.
- **FastMCP** — MCP server exposes your entire library to Claude Desktop, Cursor, or any MCP client.

---

## Quick Start

### 1. Supabase setup

1. Create a free project at [supabase.com](https://supabase.com).
2. Open **SQL Editor** and run `supabase/schema.sql` — this creates the `gems` table and seeds sample data.
3. Go to **Settings → API** and copy:
   - **Project URL** → `SUPABASE_URL`
   - **service_role key** (under "Secret") → `SUPABASE_SERVICE_ROLE_KEY`

### 2. Environment variables

```bash
cp .env.example .env
# Edit .env and fill in SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
# ANTHROPIC_API_KEY, and/or OPENAI_API_KEY
```

### 3. Run the backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# API running at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### 4. Run the frontend

```bash
cd frontend
cp .env.local.example .env.local   # default BACKEND_URL=http://localhost:8000
npm install
npm run dev
# Web UI at http://localhost:3000
```

### 5. (Optional) Docker Compose

```bash
cp .env.example .env   # fill in your keys
docker compose up --build
```

---

## MCP Setup

The MCP server lets Claude Desktop (or any MCP client) read, resolve, and chat with your gems.

### Run the server

```bash
cd backend
source venv/bin/activate
fastmcp run mcp_server.py
```

### Add to Claude Desktop

Edit `~/.claude_desktop_config.json`:

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

Restart Claude Desktop. You'll see gemsAPI tools available in your conversations.

### Available MCP tools

| Tool | Description |
|------|-------------|
| `list_gems` | Browse all gems in the library |
| `search_gems` | Filter by keyword or tag |
| `get_gem` | Read a gem's raw prompt |
| `resolve_gem_prompt` | Expand `{{gem:refs}}` and fill `{variables}` |
| `chat_with_gem` | Send a message using a gem as system prompt |
| `create_gem` | Add a new gem programmatically |
| `list_available_models` | See all supported models |

### MCP Resources

Gems are also exposed as resources that MCP clients can read directly:

```
gems://list          — formatted list of all gems
gems://{name}        — a specific gem's prompt text
```

---

## Gem Syntax

### Variables

Use `{variable_name}` anywhere in the prompt. Values are passed at call time.

```
You are an expert in {language}. Always follow {style_guide} conventions.
```

### Recursive gem embedding

Use `{{gem:name}}` to embed another gem's resolved content inline.

```
{{gem:base_assistant}}

You also specialize in code review. Review the following {language} code:
```

When `code_reviewer` is resolved, `{{gem:base_assistant}}` is replaced with that gem's full text — and if `base_assistant` itself references other gems, those are expanded too (up to 10 levels deep, cycle-safe).

---

## REST API Reference

Base URL: `http://localhost:8000`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/gems` | List all gems |
| POST | `/gems` | Create a gem |
| GET | `/gems/{id_or_name}` | Get a gem |
| PUT | `/gems/{id}` | Update a gem |
| DELETE | `/gems/{id}` | Soft-delete a gem |
| POST | `/gems/resolve` | Resolve a gem (expand refs + variables) |
| POST | `/chat` | Chat with a gem |
| GET | `/chat/models` | List available models |

Full interactive docs: **http://localhost:8000/docs**

### Resolve example

```bash
curl -X POST http://localhost:8000/gems/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "gem_name": "code_reviewer",
    "variables": { "language": "Python" }
  }'
```

### Chat example

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "gem_name": "code_reviewer",
    "messages": [{ "role": "user", "content": "Review this: def add(a,b): return a+b" }],
    "variables": { "language": "Python" }
  }'
```

---

## Project Structure

```
gemsAPI/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI app + CORS
│   │   ├── database.py          Supabase client (singleton)
│   │   ├── models.py            Pydantic request/response models
│   │   ├── routes/
│   │   │   ├── gems.py          CRUD + resolve endpoints
│   │   │   └── chat.py          Chat + streaming endpoints
│   │   └── services/
│   │       ├── gem_service.py   CRUD + recursive resolver
│   │       └── llm_service.py   Anthropic + OpenAI abstraction
│   ├── mcp_server.py            FastMCP server (tools + resources)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── layout.tsx           Root layout + navigation
│   │   ├── page.tsx             Redirects to /gems
│   │   ├── gems/
│   │   │   ├── page.tsx         Gems library (list, search, filter)
│   │   │   ├── new/page.tsx     Create gem form
│   │   │   └── [id]/
│   │   │       ├── page.tsx     Gem detail + resolve preview
│   │   │       └── edit/page.tsx  Edit form
│   │   └── chat/page.tsx        Chat testing interface
│   ├── components/
│   │   ├── Navigation.tsx
│   │   ├── GemCard.tsx
│   │   ├── GemForm.tsx          Create/edit with live preview
│   │   └── ChatInterface (inline in chat page)
│   ├── lib/api.ts               Typed API client
│   └── next.config.ts           /api/* proxy to backend
├── supabase/schema.sql
├── docker-compose.yml
└── .env.example
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Database | Supabase (Postgres) |
| Backend API | FastAPI + Uvicorn |
| MCP Server | FastMCP 2.x |
| LLM providers | Anthropic SDK, OpenAI SDK |
| Frontend | Next.js 14 (App Router) |
| Styling | Tailwind CSS |
| Language | Python 3.12, TypeScript |
