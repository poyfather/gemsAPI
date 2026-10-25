"""
Entry point for the packaged backend (Lapidary Console).

    lapidary-backend            serve the API on 127.0.0.1:8000
    lapidary-backend --mcp      run the MCP server over stdio (for Claude Desktop and ChatGPT)
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled and not os.environ.get("GEMS_SEED_SQL_FILE"):
        os.environ["GEMS_SEED_SQL_FILE"] = os.path.join(bundled, "supabase", "schema.sql")
    if "--mcp" in sys.argv:
        import mcp_server
        mcp_server.mcp.run()
        return
    import uvicorn
    uvicorn.run("app.main:app", host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
