import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

_client: Client | None = None


def get_supabase() -> Client:
    """Return a singleton Supabase client."""
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "").strip()
        # Service role only (ADR-006): the server is the one trusted database
        # client, RLS has no policies for anyone else, and the anon key would
        # see zero rows.
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not key:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in your .env file."
            )
        _client = create_client(url, key)
    return _client
