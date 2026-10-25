"""
Storage backends (roadmap item 38).

One interface, two implementations: SQLite (a file, the default when no
Supabase project is configured, and what Lapidary Console uses) and
Supabase (the hosted mode). gem_service and run_service call get_store().
"""
from __future__ import annotations
import logging

from app import settings
from app.storage.base import Store

logger = logging.getLogger(__name__)
_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        backend = settings.STORAGE
        if backend == "sqlite":
            from app.storage.sqlite_store import SQLiteStore
            _store = SQLiteStore(settings.SQLITE_PATH, seed_sql_file=settings.SEED_SQL_FILE)
        elif backend == "supabase":
            from app.storage.supabase_store import SupabaseStore
            _store = SupabaseStore()
        else:
            raise EnvironmentError(f"GEMS_STORAGE must be 'sqlite' or 'supabase', not '{backend}'.")
        logger.info("Storage: %s", backend)
    return _store


def reset_store() -> None:
    """Forget the cached store (tests, and the console when settings change)."""
    global _store
    if _store is not None and hasattr(_store, "close"):
        _store.close()
    _store = None
