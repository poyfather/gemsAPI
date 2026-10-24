"""Recursive resolution, with the database replaced by `fake_library`."""
import asyncio

import pytest

from app.services.gem_service import MAX_DEPTH, fill_variables, resolve_gem, resolve_gem_detailed
from conftest import make_gem


def run(coro):
    return asyncio.run(coro)


def test_plain_gem_resolves_to_its_prompt(fake_library) -> None:
    fake_library["base"] = make_gem("base", "Be direct.")
    prompt, refs = run(resolve_gem("base"))
    assert prompt == "Be direct."
    assert refs == []


def test_nested_references_expand_depth_first_and_report_refs_in_order(fake_library) -> None:
    fake_library["base"] = make_gem("base", "BASE")
    fake_library["reviewer"] = make_gem("reviewer", "{{gem:base}}\nREVIEW")
    fake_library["lead"] = make_gem("lead", "{{gem:reviewer}}\nLEAD {{gem:base}}")
    prompt, refs = run(resolve_gem("lead"))
    assert prompt == "BASE\nREVIEW\nLEAD BASE"
    assert refs == ["reviewer", "base"]  # first seen order, no duplicates


def test_variables_fill_inside_embedded_gems(fake_library) -> None:
    fake_library["base"] = make_gem("base", "Language: {language}.")
    fake_library["outer"] = make_gem("outer", "{{gem:base}} Team of {team_size}.")
    result = run(resolve_gem_detailed("outer", {"language": "Python", "team_size": "4"}))
    assert result.resolved_prompt == "Language: Python. Team of 4."
    assert result.variables_expected == ["language", "team_size"]
    assert result.variables_used == ["language", "team_size"]
    assert result.variables_missing == []


def test_variables_used_only_counts_placeholders_that_exist(fake_library) -> None:
    fake_library["g"] = make_gem("g", "Hello {name}.")
    result = run(resolve_gem_detailed("g", {"name": "Ada", "unused": "x"}))
    assert result.variables_used == ["name"]
    assert result.variables_missing == []
    assert result.resolved_prompt == "Hello Ada."


def test_missing_variables_are_reported_and_left_in_place(fake_library) -> None:
    fake_library["g"] = make_gem("g", "Style {style}, tone {tone}.")
    result = run(resolve_gem_detailed("g", {"style": "terse"}))
    assert result.resolved_prompt == "Style terse, tone {tone}."
    assert result.variables_missing == ["tone"]


def test_a_value_containing_a_placeholder_is_not_substituted_again() -> None:
    out = fill_variables("{a} and {b}", {"a": "{b}", "b": "B"})
    assert out == "{b} and B"
    out = fill_variables("{b} and {a}", {"b": "B", "a": "{b}"})
    assert out == "B and {b}"


def test_json_and_code_braces_are_not_placeholders(fake_library) -> None:
    prompt = 'Reply as {"name": "x", "ok": true}. Use {language}. for (;;) {}'
    fake_library["g"] = make_gem("g", prompt)
    assert fake_library["g"].variables == ["language"]
    result = run(resolve_gem_detailed("g", {"language": "Go"}))
    assert result.resolved_prompt == 'Reply as {"name": "x", "ok": true}. Use Go. for (;;) {}'


def test_missing_gem_raises(fake_library) -> None:
    with pytest.raises(ValueError, match="not found"):
        run(resolve_gem("nope"))


def test_inactive_gem_counts_as_missing(fake_library) -> None:
    fake_library["old"] = make_gem("old", "x", is_active=False)
    with pytest.raises(ValueError, match="not found"):
        run(resolve_gem("old"))


def test_cycle_is_detected_before_recursing_forever(fake_library) -> None:
    fake_library["a"] = make_gem("a", "{{gem:b}}")
    fake_library["b"] = make_gem("b", "{{gem:a}}")
    with pytest.raises(ValueError, match="Circular"):
        run(resolve_gem("a"))


def test_self_reference_is_a_cycle(fake_library) -> None:
    fake_library["a"] = make_gem("a", "{{gem:a}}")
    with pytest.raises(ValueError, match="Circular"):
        run(resolve_gem("a"))


def test_depth_limit(fake_library) -> None:
    n = MAX_DEPTH + 2
    for i in range(n):
        fake_library[f"g{i}"] = make_gem(f"g{i}", f"{{{{gem:g{i + 1}}}}}" if i < n - 1 else "end")
    with pytest.raises(ValueError, match="depth"):
        run(resolve_gem("g0"))
    # A chain exactly at the limit is fine.
    fake_library.clear()
    for i in range(MAX_DEPTH + 1):
        fake_library[f"h{i}"] = make_gem(f"h{i}", f"{{{{gem:h{i + 1}}}}}" if i < MAX_DEPTH else "end")
    prompt, _ = run(resolve_gem("h0"))
    assert prompt == "end"
