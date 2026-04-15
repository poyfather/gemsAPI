# STANDARDS

## Coding Standards

### Python (backend/)
- 4-space indentation, type hints on all public functions and return values.
- `snake_case` for modules, functions, and variables. `PascalCase` for classes. `UPPER_SNAKE_CASE` for module-level constants.
- All provider-specific LLM logic stays inside `llm_service.py` — routes and gem_service import only the `complete()` / `complete_stream()` interface.
- Use `async`/`await` throughout; no blocking I/O in request handlers.
- Pydantic models for all request/response shapes — no raw `dict` in route signatures.
- Lint with `ruff check .` from repo root. Zero warnings required before merge.

### TypeScript (frontend/)
- Strict TypeScript (`"strict": true` in `tsconfig.json`).
- `camelCase` for variables and functions, `PascalCase` for components and types.
- All API calls go through `lib/api.ts` — no raw `fetch` calls scattered across components.
- `"use client"` directive only on components that actually use React state or browser APIs.
- Tailwind utility classes only — no inline styles, no custom CSS except in `globals.css`.

### Naming Conventions
- Gem names: `snake_case`, descriptive, e.g. `code_reviewer`, `prompt_enhancer`.
- Prompt files in `prompts/`: `<gem_name>.md`, e.g. `prompt_enhancer.md`.
- Eval files in `evals/`: `eval_<gem_name>.py`, e.g. `eval_prompt_enhancer.py`.

## Testing Standards
- Unit tests in `tests/`. Use `pytest` with deterministic fixtures (mock Supabase and LLM calls).
- Keep tests fast — no real API calls in `tests/`. Reserve live calls for `evals/`.
- Add regression tests whenever a gem's resolution logic, variable extraction, or recursive expansion behavior changes.
- Run with `pytest -q` from repo root.

## Prompt Standards
- Store the canonical, current version of each shipped gem as `prompts/<gem_name>.md`.
- The database is the runtime source of truth; `prompts/` is the reviewable, diff-friendly source.
- Version prompts explicitly when behavior changes significantly: `prompts/prompt_enhancer.v2.md`.
- Document the purpose, variables, and any gem references at the top of each prompt file.

## Evaluation Standards
- Evals live in `evals/` and are separate from unit tests — they may make real API calls.
- Each eval file targets one gem and measures a specific quality dimension.
- Record baseline scores in the eval file itself so regressions are visible in diffs.
- Run evals manually before merging changes to any gem in `prompts/`.

## Frontend Standards
- For plain `html/css/js` interfaces (outside Next.js), prefer Bootstrap before custom CSS.
- Dark theme baseline: `#080810` background, `#0f0f1a` surface, `#7c3aed` accent.

## Review Standards
- PRs require passing `ruff check .` and `pytest -q`.
- Include rationale for any prompt change and reference the eval outcome.
- Update `CHANGELOG.md` for every merged change.
- Link code changes to updated docs when architecture, security, or standards change.

## Operational Standards
- Use structured logging (`uvicorn` access log format). Never log API keys, gem content, or user messages.
- Pin dependency versions in `backend/requirements.txt` for reproducible Docker builds.
- Track breaking dependency upgrades in `DECISIONS.md`.
