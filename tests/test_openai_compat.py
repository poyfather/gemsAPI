"""The OpenAI-compatible surface: models, chat completions, streaming, bearer auth."""
import json

import pytest

from app.routes import openai_compat
from app.services.llm_service import ToolCall, ToolTurn
from conftest import TEST_API_KEY, make_gem

BEARER = {"Authorization": f"Bearer {TEST_API_KEY}"}


def test_bearer_token_is_accepted_everywhere(client, fake_library) -> None:
    assert client.get("/gems/", headers=BEARER).status_code == 200
    assert client.get("/v1/models", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/v1/models").status_code == 401


def test_models_list_gems_with_lapidary_metadata(client, fake_library) -> None:
    fake_library["writer"] = make_gem("writer", "Write.", tags=["x"])
    fake_library["lib"] = make_gem("lib", "L", kind="agent", tools=["get_gem"])
    body = client.get("/v1/models", headers=BEARER).json()
    assert body["object"] == "list"
    by_id = {m["id"]: m for m in body["data"]}
    assert by_id["writer"]["owned_by"] == "lapidary" and by_id["writer"]["lapidary"]["kind"] == "prompt"
    assert by_id["lib"]["lapidary"]["tools"] == ["get_gem"]
    assert client.get("/v1/models/writer", headers=BEARER).json()["id"] == "writer"
    assert client.get("/v1/models/nope", headers=BEARER).status_code == 404


def test_prompt_gem_completion_puts_the_resolved_prompt_first(client, fake_library, monkeypatch) -> None:
    fake_library["base"] = make_gem("base", "Be direct.")
    fake_library["writer"] = make_gem("writer", "{{gem:base}} You write {style}.")
    seen = {}

    async def fake_complete(system, messages, model, provider, max_tokens=None):
        seen.update(system=system, messages=messages, model=model, provider=provider)
        return "Here you go."

    monkeypatch.setattr(openai_compat, "complete", fake_complete)
    r = client.post("/v1/chat/completions", headers=BEARER, json={
        "model": "writer",
        "messages": [{"role": "system", "content": "Keep it short."}, {"role": "user", "content": "A haiku"}],
        "temperature": 0.2,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "chat.completion" and body["model"] == "writer"
    assert body["choices"][0]["message"] == {"role": "assistant", "content": "Here you go."}
    assert seen["system"] == "Be direct. You write {style}.\n\nKeep it short."
    assert seen["messages"] == [{"role": "user", "content": "A haiku"}]
    assert (seen["model"], seen["provider"]) == ("claude-opus-4-5", "anthropic")


def test_prompt_gem_streams_openai_chunks(client, fake_library, monkeypatch) -> None:
    fake_library["writer"] = make_gem("writer", "Write.")

    async def fake_stream(system, messages, model, provider, max_tokens=None):
        for piece in ["Hel", "lo"]:
            yield piece

    monkeypatch.setattr(openai_compat, "complete_stream", fake_stream)
    with client.stream("POST", "/v1/chat/completions", headers=BEARER, json={"model": "writer", "messages": [{"role": "user", "content": "hi"}], "stream": True}) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        text = "".join(r.iter_text())
    frames = [line[6:] for line in text.splitlines() if line.startswith("data: ")]
    assert frames[-1] == "[DONE]"
    chunks = [json.loads(f) for f in frames[:-1]]
    assert all(c["object"] == "chat.completion.chunk" for c in chunks)
    assert "".join(c["choices"][0]["delta"].get("content", "") for c in chunks) == "Hello"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_agent_gem_runs_the_loop_with_the_conversation(client, fake_library, fake_runs, monkeypatch) -> None:
    from app.agents import runner

    fake_library["x"] = make_gem("x", "X")
    fake_library["lib"] = make_gem("lib", "Librarian.", kind="agent", tools=["get_gem"])
    seen = []
    script = iter([
        ToolTurn(text="", tool_calls=[ToolCall(id="1", name="get_gem", input={"name": "x"})], assistant_message={"role": "assistant", "content": None}, stop_reason="tool_use"),
        ToolTurn(text="x is a gem.", tool_calls=[], assistant_message={"role": "assistant", "content": "x is a gem."}, stop_reason="end_turn"),
    ])

    async def turns(system_prompt, messages, model, provider, tools, max_tokens=None):
        seen.append((system_prompt, list(messages)))
        return next(script)

    monkeypatch.setattr(runner, "complete_turn", turns)
    r = client.post("/v1/chat/completions", headers=BEARER, json={
        "model": "lib",
        "messages": [{"role": "system", "content": "Answer briefly."}, {"role": "user", "content": "hi"},
                     {"role": "assistant", "content": "hello"}, {"role": "user", "content": "what is x?"}],
    })
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"] == "x is a gem."
    system, messages = seen[0]
    assert system == "Librarian.\n\nAnswer briefly."
    assert messages[:3] == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}, {"role": "user", "content": "what is x?"}]
    assert len(fake_runs["runs"]) == 1


def test_agent_gem_streaming_shows_tool_activity_then_the_answer(client, fake_library, fake_runs, monkeypatch) -> None:
    from app.agents import runner

    fake_library["x"] = make_gem("x", "X")
    fake_library["lib"] = make_gem("lib", "L", kind="agent", tools=["get_gem"])
    script = iter([
        ToolTurn(text="", tool_calls=[ToolCall(id="1", name="get_gem", input={"name": "x"})], assistant_message={"role": "assistant", "content": None}, stop_reason="tool_use"),
        ToolTurn(text="done", tool_calls=[], assistant_message={"role": "assistant", "content": "done"}, stop_reason="end_turn"),
    ])

    async def turns(*a, **k):
        return next(script)

    monkeypatch.setattr(runner, "complete_turn", turns)
    with client.stream("POST", "/v1/chat/completions", headers=BEARER, json={"model": "lib", "messages": [{"role": "user", "content": "go"}], "stream": True}) as r:
        text = "".join(r.iter_text())
    frames = [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ") and not line.endswith("[DONE]")]
    content = "".join(c["choices"][0]["delta"].get("content", "") for c in frames)
    assert content == "[tool: get_gem]\n\ndone"


def test_bad_requests_use_openai_error_shapes(client, fake_library) -> None:
    fake_library["writer"] = make_gem("writer", "Write.")
    r = client.post("/v1/chat/completions", headers=BEARER, json={"model": "nope", "messages": [{"role": "user", "content": "x"}]})
    assert r.status_code == 404 and r.json()["detail"]["type"] == "invalid_request_error"
    r = client.post("/v1/chat/completions", headers=BEARER, json={"model": "writer", "messages": [{"role": "assistant", "content": "x"}]})
    assert r.status_code == 400


@pytest.mark.parametrize("content,expected", [("plain", "plain"), ([{"type": "text", "text": "a"}, {"type": "image_url", "image_url": {}}, {"type": "text", "text": "b"}], "a\nb"), (None, "")])
def test_content_parts_are_flattened(content, expected) -> None:
    assert openai_compat._text(content) == expected
