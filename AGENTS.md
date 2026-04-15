# AI Agent Workflow Guide

## Purpose
`AGENTS.md` defines AI agents used in gemsAPI development workflows, their boundaries, and handoff rules.

## Required Project Docs
- `README.md`: high-level project description and quickstart.
- `CONTEXT.md`: system context, domain vocabulary, and guardrails.
- `ARCHITECTURE.md`: component model, data flow, and integration details.
- `SECURITY.md`: credential handling, data access, and AI safety boundaries.
- `STANDARDS.md`: coding, testing, prompt, and eval conventions.
- `DECISIONS.md`: architectural decision records (ADRs).
- `ROADMAP.md`: development priorities, sequencing, and status.
- `CHANGELOG.md`: release history.

## Workflow Stages
1. **Context intake**: read `README.md`, `CONTEXT.md`, and current `DECISIONS.md`.
2. **Design**: update `ARCHITECTURE.md`, document tradeoffs in `DECISIONS.md`.
3. **Implementation**: apply changes under `src/` (or `backend/`/`frontend/`), `prompts/`, `configs/`, and `scripts/`.
4. **Verification**: run `pytest -q` and `ruff check .`; run relevant `evals/` scripts; record evidence.
5. **Documentation and release**: update affected root docs and `CHANGELOG.md`.

## Agent Catalog

### Planner Agent
- **Purpose**: turn requests into decision-complete implementation plans for gemsAPI changes.
- **Inputs**: user request, `CONTEXT.md`, `ARCHITECTURE.md`, `ROADMAP.md`, current gem list.
- **Outputs**: ordered implementation plan with acceptance criteria.
- **Allowed actions**: analysis, repo inspection, non-mutating checks, reading `prompts/` and `evals/`.
- **Disallowed actions**: editing files, running LLM evals, or modifying Supabase during planning-only tasks.
- **Handoff to**: Implementer Agent.
- **Update triggers**: planning workflow or acceptance criteria policy changes.

### Implementer Agent
- **Purpose**: implement approved plans — code, prompt, config, and doc changes — keeping behavior and docs aligned.
- **Inputs**: approved plan, codebase state, `STANDARDS.md`, `SECURITY.md`.
- **Outputs**: code/doc changes, test results, risk notes.
- **Allowed actions**: edit files under `backend/`, `frontend/`, `prompts/`, `configs/`, `scripts/`, `tests/`, root docs; run build/test/lint/eval commands.
- **Disallowed actions**: bypassing security policy, committing `.env` files, undocumented behavior changes, editing Supabase production data directly.
- **Handoff to**: Reviewer Agent.
- **Update triggers**: coding workflow, tooling, or execution constraints change.

### Reviewer Agent
- **Purpose**: detect defects, regressions, and policy violations in gemsAPI changes.
- **Inputs**: diffs, test evidence, eval results, `STANDARDS.md`, `SECURITY.md`.
- **Outputs**: prioritized findings and required fixes.
- **Allowed actions**: static review, risk analysis, validation checks, reading `evals/` output.
- **Disallowed actions**: approving unresolved critical findings; approving prompt changes without eval evidence.
- **Handoff to**: Implementer Agent or Docs Agent.
- **Update triggers**: review gates or severity policy changes.

### Docs Agent
- **Purpose**: keep root docs accurate and the `prompts/` directory in sync with gems in Supabase.
- **Inputs**: merged behavior/design/policy changes, current gem list.
- **Outputs**: synchronized updates to affected markdown docs; updated `prompts/<gem_name>.md` files.
- **Allowed actions**: edit docs, improve cross-links, update `prompts/`, clarify ownership.
- **Disallowed actions**: changing product behavior in docs-only tasks; editing `backend/` or `frontend/` source.
- **Handoff to**: Release Agent.
- **Update triggers**: document ownership, prompt content, or template structure changes.

### Release Agent
- **Purpose**: finalize `CHANGELOG.md` and version-facing updates before merging to `main`.
- **Inputs**: merged changes, ADRs, and test/eval outcomes.
- **Outputs**: `CHANGELOG.md` updates and release summary.
- **Allowed actions**: compile release deltas and readiness notes.
- **Disallowed actions**: shipping without passing `pytest -q`, `ruff check .`, and relevant eval baseline.
- **Handoff to**: none.
- **Update triggers**: release process or changelog policy changes.

## gemsAPI-Specific Agent Notes
- The **MCP server** (`mcp_server.py`) is itself an AI agent interface. Changes to MCP tool signatures require updating `ARCHITECTURE.md` and any affected prompt files in `prompts/`.
- When a gem's `system_prompt` changes in Supabase, the **Docs Agent** must also update the corresponding `prompts/<gem_name>.md` file so the repo reflects the live state.
- The **Implementer Agent** must never hardcode API keys or credentials in any file. All secrets flow through `.env` only.

## Coordination Rules
- Do not skip handoffs when ownership changes between planning, implementation, review, docs, and release.
- Resolve conflicts using source-of-truth docs in this order: `SECURITY.md`, `STANDARDS.md`, `ARCHITECTURE.md`, `CONTEXT.md`, `README.md`.
- For plain `html/css/js` interfaces, prefer Bootstrap before custom CSS.
- PowerShell is acceptable and preferred on Windows automation paths.

## Pull Request Policy
- Include summary, rationale, and verification evidence (`pytest -q`, `ruff check .`, eval notes as needed).
- Update `AGENTS.md` when agent roles, allowed actions, disallowed actions, handoffs, or update triggers change.

Companion docs update rules when scope changes:
- `CONTEXT.md`: assumptions, stakeholders, guardrails, or domain vocabulary.
- `ARCHITECTURE.md`: component model, data flow, provider strategy, or MCP tool signatures.
- `STANDARDS.md`: conventions, quality gates, prompt/eval procedures, or ops procedures.
- `SECURITY.md`: credential, data-access, or AI safety policy changes.
- `DECISIONS.md`: architecture changes, major tradeoffs, and superseded design choices.
- `ROADMAP.md`: priority, sequencing, ownership, or milestone status changes.
- `prompts/`: any gem content changes (keep in sync with Supabase).
