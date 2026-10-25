"""REST routes through FastAPI's TestClient, with the database faked."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from conftest import TEST_API_KEY, make_gem

KEY = {"X-API-Key": TEST_API_KEY}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_and_root_need_no_key(client) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200


def test_gems_require_the_api_key(client, fake_library) -> None:
    assert client.get("/gems/").status_code == 401
    assert client.get("/gems/", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post("/chat/", json={"gem_name": "x", "messages": []}).status_code == 401


def test_list_returns_active_gems_sorted(client, fake_library) -> None:
    fake_library["zeta"] = make_gem("zeta", "z")
    fake_library["alpha"] = make_gem("alpha", "a")
    fake_library["gone"] = make_gem("gone", "g", is_active=False)
    names = [g["name"] for g in client.get("/gems/", headers=KEY).json()]
    assert names == ["alpha", "zeta"]


def test_get_by_name_and_by_uuid(client, fake_library) -> None:
    gem = make_gem("base", "x", id="11111111-1111-4111-8111-111111111111")
    fake_library["base"] = gem
    assert client.get("/gems/base", headers=KEY).json()["id"] == gem.id
    assert client.get(f"/gems/{gem.id}", headers=KEY).json()["name"] == "base"


def test_unknown_name_that_is_not_a_uuid_is_404_not_500(client, fake_library) -> None:
    r = client.get("/gems/does-not-exist", headers=KEY)
    assert r.status_code == 404
    r = client.get("/gems/22222222-2222-4222-8222-222222222222", headers=KEY)
    assert r.status_code == 404


def test_delete_and_update_accept_a_name(client, fake_library, monkeypatch) -> None:
    from app.services import gem_service

    gem = make_gem("base", "x")
    fake_library["base"] = gem
    seen: dict[str, str] = {}

    async def soft_delete(gem_id: str) -> bool:
        seen["deleted"] = gem_id
        return True

    async def update(gem_id: str, data):
        seen["updated"] = gem_id
        return gem

    monkeypatch.setattr(gem_service, "soft_delete_gem", soft_delete)
    monkeypatch.setattr(gem_service, "update_gem", update)
    assert client.delete("/gems/base", headers=KEY).status_code == 200
    assert seen["deleted"] == gem.id
    assert client.put("/gems/base", headers=KEY, json={"description": "d"}).status_code == 200
    assert seen["updated"] == gem.id
    assert client.delete("/gems/missing", headers=KEY).status_code == 404


def test_resolve_reports_used_and_missing_variables(client, fake_library) -> None:
    fake_library["base"] = make_gem("base", "Lang {language}.")
    fake_library["lead"] = make_gem("lead", "{{gem:base}} Team {team_size}.")
    r = client.post(
        "/gems/resolve",
        headers=KEY,
        json={"gem_name": "lead", "variables": {"language": "Python", "extra": "ignored"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["resolved_prompt"] == "Lang Python. Team {team_size}."
    assert body["referenced_gems"] == ["base"]
    assert body["variables_used"] == ["language"]
    assert body["variables_missing"] == ["team_size"]


def test_resolve_errors_are_400(client, fake_library) -> None:
    fake_library["a"] = make_gem("a", "{{gem:a}}")
    assert client.post("/gems/resolve", headers=KEY, json={"gem_name": "a"}).status_code == 400
    assert client.post("/gems/resolve", headers=KEY, json={"gem_name": "zzz"}).status_code == 400


def test_chat_models_returns_the_available_models(client, monkeypatch) -> None:
    from app.routes import chat as chat_routes

    async def fake_models():
        return {"anthropic": ["claude-x"], "openai": []}

    monkeypatch.setattr(chat_routes, "available_models", fake_models)
    assert client.get("/chat/models", headers=KEY).json() == {"anthropic": ["claude-x"], "openai": []}
