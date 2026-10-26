# ROADMAP

## Purpose
Track Lapidary's delivery status: what is being worked on, in what order, and what done looks like. The reasoning behind every item, with sizes and dependencies, is in [docs/ROADMAP.md](docs/ROADMAP.md). The order comes from ADR-013 in [DECISIONS.md](DECISIONS.md): make Lapidary understandable, tryable and useful within five minutes before adding more features.

Success is measured by three numbers (item 58): the share of visitors who create their first gem, the share who use it again seven days later, and the number who share a gem with another person.

---

## Now: phase 1, attract

### Repository presentation and consistent docs (52)
- Goal: a visitor understands what Lapidary does for them from the top of the README, sees the product, and can pick an install path; every document agrees with the code.
- Status: Partly done. Positioning, screenshots, install options and the doc reconciliation are in. Open: a 90-second demo video, GitHub topics and description, a social preview image.
- Owner: poyfather
- Dependencies: None
- Success Criteria: README shows the product above the fold; no document contradicts the code.
- Links: `README.md`, `docs/screenshots/`, `CONTEXT.md`, `SECURITY.md`

### Live demo in the browser (51)
- Goal: try Lapidary from a link with no install and no key; watch a prompt become a tested assistant and compare the original and improved answers.
- Status: Planned
- Owner: poyfather
- Dependencies: compare and tests (done), rate limits from 55 before a live model sits behind it
- Success Criteria: a first-time visitor gets from the link to a side-by-side comparison in under five minutes.
- Links: `docs/ROADMAP.md` item 51

---

## Now: phase 2, activate

### Easy import (22)
- Goal: paste instructions from ChatGPT, Claude or Cursor, or import Markdown and JSON, and get named gems with AI-suggested improvements and duplicates flagged; export to a hand-readable bundle.
- Status: Planned (moved up by ADR-013)
- Owner: poyfather
- Dependencies: a stable schema
- Success Criteria: a person's existing prompts become a tidy library in one sitting.
- Links: `docs/ROADMAP.md` item 22

### Gem gallery (53)
- Goal: 25 to 50 curated gems with a preview, example output, a quality score and one-click install.
- Status: Planned
- Owner: poyfather
- Dependencies: 22 for the bundle format
- Success Criteria: a new user installs a gallery gem and gets a useful answer before writing any prompt.
- Links: `docs/ROADMAP.md` item 53

---

## Next: phase 3, retain

### Visual builder (54)
- Goal: connect assistants, tools, tests and approvals on a canvas, saved as an ordinary pipeline.
- Status: Planned
- Links: `docs/ROADMAP.md` item 54

### Usage, cost and performance dashboard (55)
- Goal: per-gem use, models, approximate cost, response time and test trend; monthly spend limits, alerts and rate limits (closes item 11).
- Status: Planned
- Links: `docs/ROADMAP.md` item 55

### Sharing (56)
- Goal: publish a gem as a link, install someone else's, and take their updates without losing your own changes.
- Status: Planned
- Links: `docs/ROADMAP.md` item 56

### Trust for teams (57)
- Goal: accounts and roles (item 21), approval workflows, hashed and scoped API keys, a signed Windows installer (item 42), and a published security review.
- Status: Planned. Installer signing is wired in CI and waits on credentials (`desktop/README.md`, Code signing).
- Links: `docs/ROADMAP.md` item 57

### Measurement (58)
- Goal: count the three numbers on the hosted demo and gallery; on self-hosted installs only with the owner's opt-in.
- Status: Planned
- Links: `docs/ROADMAP.md` item 58

---

## Done

The foundations the growth plan builds on, with the full list in [CHANGELOG.md](CHANGELOG.md):

- One library with composition, typed blanks and worked examples (items 4, 29, 31).
- Version history with diffs and restore, tests with a baseline, side-by-side compare (14, 28, 30).
- Assistants with tools, approvals and a run viewer; pipelines with gates; memory (32 to 34, 43, 45).
- Local models and the model policy (44); SQLite by default with Supabase as the hosted option (38).
- REST, the OpenAI-compatible API, and MCP over stdio and over HTTP with per-client keys (10, 36, 41).
- The Windows console: first run and recipes, plain language, the Doctor, explainers, the installer and its helper service (37, 39, 40, 42 partly, 47 to 50).
- Streaming chat, API key authentication, CI with lint, tests, CodeQL, Docker and the Windows installer (6, 13, 25).
