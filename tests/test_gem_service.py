"""Unit tests for gem_service helpers (no DB or LLM calls)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.services.gem_service import extract_variables, extract_gem_refs


def test_extract_variables_simple() -> None:
    prompt = "You are an expert in {language}. Follow {style_guide}."
    assert sorted(extract_variables(prompt)) == ["language", "style_guide"]


def test_extract_variables_ignores_gem_refs() -> None:
    prompt = "{{gem:base_assistant}} and use {language}."
    assert extract_variables(prompt) == ["language"]


def test_extract_gem_refs_single() -> None:
    prompt = "{{gem:base_assistant}}\nDo the thing."
    assert extract_gem_refs(prompt) == ["base_assistant"]


def test_extract_gem_refs_multiple() -> None:
    prompt = "{{gem:base_assistant}}\n{{gem:code_style}}\nMore text."
    assert sorted(extract_gem_refs(prompt)) == ["base_assistant", "code_style"]


def test_extract_gem_refs_deduplicates() -> None:
    prompt = "{{gem:base_assistant}} repeated {{gem:base_assistant}}."
    assert extract_gem_refs(prompt) == ["base_assistant"]


def test_extract_variables_empty() -> None:
    assert extract_variables("No placeholders here.") == []


def test_extract_gem_refs_empty() -> None:
    assert extract_gem_refs("No gem refs here.") == []
