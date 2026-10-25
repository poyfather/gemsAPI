import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routes import agents, chat, gems
from app.version import __version__

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate required env vars at startup so misconfiguration is caught immediately.
    from app.auth import _get_configured_key
    _get_configured_key()   # raises RuntimeError if GEMS_API_KEY is missing
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Lapidary",
    description=(
        "Prompt library and agent harness. Gems are reusable system prompts with "
        "{variable} placeholders and recursive {{gem:name}} composition; agent gems "
        "may call tools in a loop. Served over REST, a web UI and MCP."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow the Next.js dev server and any configured origins
_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gems.router)
app.include_router(chat.router)
app.include_router(agents.router)
app.include_router(agents.runs_router)


@app.get("/", tags=["meta"])
def root():
    return {
        "name": "Lapidary",
        "version": __version__,
        "description": "Prompt library and agent harness: gems compose, run as agents, served over REST, UI and MCP",
        "docs": "/docs",
        "endpoints": {
            "list_gems":    "GET  /gems",
            "create_gem":   "POST /gems",
            "get_gem":      "GET  /gems/{id_or_name}",
            "update_gem":   "PUT  /gems/{id}",
            "delete_gem":   "DELETE /gems/{id}",
            "resolve_gem":  "POST /gems/resolve",
            "chat":         "POST /chat",
            "models":       "GET  /chat/models",
            "run_agent":    "POST /agents/{name}/runs",
            "get_run":      "GET  /runs/{id}",
            "tools":        "GET  /agents/tools",
            "mcp_server":   "Run: fastmcp run mcp_server.py",
        },
    }


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
