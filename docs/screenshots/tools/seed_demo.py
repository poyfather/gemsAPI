"""
Seeds a running Lapidary with the README demo: tests on code_reviewer, a baseline
run on version 1, an improved version 2, and a run on it.

    GEMS_API_KEY=... python docs/screenshots/tools/seed_demo.py

Point the backend at a fresh SQLite file and a local model first (see ../README.md).
Every score comes from the model that answers; nothing is faked.
"""
from __future__ import annotations

import json
import os
import urllib.request

BASE = os.environ.get("LAPIDARY_URL", "http://127.0.0.1:8000")
KEY = os.environ["GEMS_API_KEY"]
CODE = "Review this:\n```python\ndef average(l):\n    return sum(l) / len(l)\n```"
TESTS = [
    ("catches the empty-list crash", "contains", "empty"),
    ("names the exception", "contains", "ZeroDivisionError"),
    ("says how to test it", "contains", "test"),
    ("short enough to act on", "judge",
     "The review is short and actionable: at most three numbered findings, most serious first, each with a concrete fix. "
     "It does not use section headings such as Summary, Issues, Suggestions or Verdict."),
]
IMPROVEMENT = ("\n\nWhen the code is short, skip those sections. Give at most three findings as a numbered list, most serious first. "
               "For each, name the exact fix, and say which test would catch it. No headings, no preamble.")


def call(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-API-Key": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:   # noqa: S310 - a local URL the person chose
        text = r.read()
        return json.loads(text) if text else None


def run_tests(gem_id: str) -> None:
    run = call("POST", f"/gems/{gem_id}/evals/run", {})["run"]
    print(f"version {run['gem_version']}: {run['passed']} of {run['total']}")


def main() -> None:
    gem_id = call("GET", "/gems/code_reviewer")["id"]
    for case in call("GET", f"/gems/{gem_id}/evals"):
        call("DELETE", f"/gems/{gem_id}/evals/{case['id']}")
    for name, check, expected in TESTS:
        call("POST", f"/gems/{gem_id}/evals", {"name": name, "input": CODE, "variables": {"language": "Python"}, "check": check, "expected": expected})
    run_tests(gem_id)
    first = call("GET", f"/gems/{gem_id}/evals/runs")[0]
    call("POST", f"/gems/{gem_id}/evals/runs/{first['id']}/baseline")
    prompt = call("GET", f"/gems/{gem_id}")["system_prompt"]
    call("PUT", f"/gems/{gem_id}", {"system_prompt": prompt.rstrip() + IMPROVEMENT,
                                    "note": "Short code gets a short review: three numbered findings, each with a fix and a test"})
    run_tests(gem_id)


if __name__ == "__main__":
    main()
