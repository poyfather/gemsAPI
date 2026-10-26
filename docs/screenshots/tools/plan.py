"""
Writes plan.json for capture.mjs: the six README screenshots.

    python docs/screenshots/tools/plan.py > /tmp/plan.json
    node docs/screenshots/tools/capture.mjs /tmp/plan.json

Needs the web UI on :3000 (with the seeded demo) and a console preview served from
CONSOLE_PREVIEW (a folder with console.html renamed index.html, plus the mock files).
"""
from __future__ import annotations

import json
import os
import pathlib
import urllib.request

OUT = pathlib.Path(__file__).resolve().parent.parent
UI = os.environ.get("LAPIDARY_UI", "http://localhost:3000")
CONSOLE = os.environ.get("CONSOLE_PREVIEW", "")
SET = ("(sel, val) => { const el = document.querySelector(sel); if (!el) return false; "
       "const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; "
       "Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, val); el.dispatchEvent(new Event('input', { bubbles: true })); return true; }")
CLICK = "(label) => { const b = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === label); if (b) b.click(); return !!b; }"
IDLE = "![...document.querySelectorAll('button')].some(b => b.disabled && /Compare/.test(b.textContent))"
QUESTION = json.dumps("Review this:\n```python\ndef average(l):\n    return sum(l) / len(l)\n```")


def gem_id(name: str) -> str:
    req = urllib.request.Request(f"{os.environ.get('LAPIDARY_URL', 'http://127.0.0.1:8000')}/gems/{name}",
                                 headers={"X-API-Key": os.environ["GEMS_API_KEY"]})
    with urllib.request.urlopen(req) as r:   # noqa: S310 - a local URL the person chose
        return json.loads(r.read())["id"]


def main() -> None:
    gid = gem_id("code_reviewer")
    fill = [{"js": f"({SET})('[placeholder=\"The question every column answers\"]', {QUESTION})"},
            {"js": f"({SET})('[placeholder=\"Value for language\"]', 'Python')"}]
    plan = [
        {"url": f"{UI}/gems", "out": str(OUT / "library.png")},
        {"url": f"{UI}/gems/{gid}", "out": str(OUT / "prompt-page.png"), "width": 1100, "clipHeight": 850, "load": 5000},
        {"url": f"{UI}/gems/{gid}/compare", "out": str(OUT / "compare-answers.png"), "clipHeight": 1100, "load": 5000,
         "steps": fill + [{"js": f"({CLICK})('Compare answers')", "wait": 3000, "until": IDLE}]},
        {"url": f"{UI}/gems/{gid}/compare", "out": str(OUT / "compare-tests.png"), "clipHeight": 810, "load": 5000,
         "steps": fill + [{"js": f"({CLICK})('Compare on the 4 tests')", "wait": 3000, "until": IDLE}]},
        {"url": f"{UI}/chat?gem=code_reviewer", "out": str(OUT / "chat.png"), "load": 5000,
         "steps": [{"js": f"({SET})('textarea', {QUESTION})"},
                   {"js": "document.querySelector('textarea').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}))",
                    "wait": 3000, "until": "!![...document.querySelectorAll('button')].find(b => b.textContent.includes('Save as an example'))"}]},
    ]
    if CONSOLE:
        plan += [
            {"url": f"{CONSOLE}/index.html", "out": str(OUT / "console-start.png"), "width": 1280, "height": 820, "load": 1500,
             "steps": [{"js": "document.querySelector('[data-path=\"basic\"]').click()", "wait": 1500}]},
            {"url": f"{CONSOLE}/index.html", "out": str(OUT / "console-doctor.png"), "width": 1280, "height": 820, "load": 1500,
             "steps": [{"js": "document.querySelector('[data-view=\"doctor\"]').click()", "wait": 2500}]},
        ]
    print(json.dumps(plan, indent=1))


if __name__ == "__main__":
    main()
