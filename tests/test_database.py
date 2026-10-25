"""database.py builds its client from the service role key only (ADR-006)."""
import pytest

from app import database


@pytest.fixture(autouse=True)
def reset_client(monkeypatch):
    monkeypatch.setattr(database, "_client", None)
    yield
    database._client = None


def test_missing_service_role_key_is_an_error(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-is-not-accepted")
    with pytest.raises(EnvironmentError, match="SUPABASE_SERVICE_ROLE_KEY"):
        database.get_supabase()


def test_client_is_built_once_from_the_service_role_key(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_create_client(url: str, key: str):
        calls.append((url, key))
        return object()

    monkeypatch.setattr(database, "create_client", fake_create_client)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    first = database.get_supabase()
    second = database.get_supabase()
    assert first is second
    assert calls == [("https://example.supabase.co", "service-role-key")]
