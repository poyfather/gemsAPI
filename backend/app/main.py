import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routes import gems, chat

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate required env vars at startup so misconfiguration is caught immediately.
    from app.auth import _get_configured_key
    _get_configured_key()   # raises RuntimeError if GEMS_API_KEY is missing
    yield


app = FastAPI(
    lifespan=lifespan,
    title="gemsAPI",
    description=(
        "Manage and serve reusable LLM prompts (gems) with variable substitution "
        "and recursive {{gem:name}} composition. Accessible via REST and MCP."
    ),
    version="1.0.0",
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


@app.get("/", tags=["meta"])
def root():
    return {
        "name": "gemsAPI",
        "version": "1.0.0",
        "description": "Prompt library with recursive composition, REST + MCP access",
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
            "mcp_server":   "Run: fastmcp run mcp_server.py",
        },
    }


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
