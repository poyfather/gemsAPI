"""
Eval: prompt_enhancer gem

Measures whether the prompt_enhancer gem produces a structurally
valid response containing the required XML sections.

Usage:
    python evals/eval_prompt_enhancer.py

Requires ANTHROPIC_API_KEY in environment.
Records a baseline score so regressions are visible in diffs.

BASELINE (2026-04-15): 5/5 test cases passed (100%)
"""
import os
import sys
import re

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


TEST_CASES = [
    {
        "id": "tc-01",
        "description": "Vague single-sentence request",
        "input": "write me a prompt for a customer support bot",
    },
    {
        "id": "tc-02",
        "description": "Request with implied variables",
        "input": "make a prompt for a code reviewer that checks python",
    },
    {
        "id": "tc-03",
        "description": "Multi-step agentic task",
        "input": "write a prompt for an agent that researches competitors and writes a report",
    },
    {
        "id": "tc-04",
        "description": "Already reasonable prompt",
        "input": "You are a helpful assistant. Answer questions clearly and concisely.",
    },
    {
        "id": "tc-05",
        "description": "Creative task with format requirements",
        "input": "write a prompt for generating product descriptions for an e-commerce site",
    },
]

REQUIRED_SECTIONS = ["<analysis>", "<enhanced_prompt>", "<changes_made>"]


def score_response(response: str) -> dict:
    """Check that the response contains all required XML sections."""
    results = {}
    for section in REQUIRED_SECTIONS:
        results[section] = section in response
    results["passed"] = all(results.values())
    return results


def run_eval() -> None:
    try:
        import anthropic
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("ERROR: install backend deps first: pip install -r backend/requirements.txt")
        sys.exit(1)

    from app.services.gem_service import get_gem_by_name, resolve_gem
    import asyncio

    async def get_system_prompt() -> str:
        resolved, _ = await resolve_gem("prompt_enhancer", {})
        return resolved

    try:
        system_prompt = asyncio.run(get_system_prompt())
    except Exception as e:
        print(f"ERROR: Could not resolve prompt_enhancer gem: {e}")
        print("Make sure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set and the gem exists.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    passed = 0
    total = len(TEST_CASES)

    print(f"\n{'='*60}")
    print("EVAL: prompt_enhancer")
    print(f"{'='*60}\n")

    for tc in TEST_CASES:
        print(f"[{tc['id']}] {tc['description']}")
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": tc["input"]}],
        )
        text = response.content[0].text
        scores = score_response(text)

        status = "PASS" if scores["passed"] else "FAIL"
        if scores["passed"]:
            passed += 1
        print(f"  Status : {status}")
        for section, found in scores.items():
            if section != "passed":
                print(f"  {section:30s} {'✓' if found else '✗'}")
        print()

    print(f"{'='*60}")
    print(f"Result: {passed}/{total} passed ({100*passed//total}%)")
    print(f"{'='*60}\n")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    run_eval()
