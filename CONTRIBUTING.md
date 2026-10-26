# Contributing to Lapidary

Thanks for helping. The most useful contributions right now follow the growth plan in the [roadmap](docs/ROADMAP.md) (ADR-013): anything that makes Lapidary easier to understand, try and get value from in five minutes, well-tested gems for the gallery, and docs that match the code.

## Development setup

```sh
git clone https://github.com/poyfather/lapidary.git && cd lapidary
python -m venv backend/.venv && source backend/.venv/bin/activate   # Windows: backend\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt -r requirements.txt           # runtime deps, plus pytest and ruff
cd frontend && npm install && cd ..
```

On Windows, `scripts\setup.ps1` does the Python half and `scripts\test.ps1` runs the checks.

The unit tests use a temporary SQLite store and no LLM, so you can run them without credentials. To try the API, UI or MCP server for real you need only the env files described in the README; data goes to a SQLite file under `data/` unless you configure a Supabase project. A local model server (Ollama, LM Studio) lets you try chat and assistants with no cloud key. Never commit `.env` or `.env.local`; both are git-ignored.

## Code style

- **Python** (`backend/`, `tests/`, `evals/`): formatted and linted by [ruff](https://docs.astral.sh/ruff/) with the rules in `ruff.toml`. Type hints on public functions, Pydantic models for request and response shapes, `async` end to end, and every provider-specific call stays inside `backend/app/services/llm_service.py`.
- **TypeScript** (`frontend/`): strict mode, ESLint 9 with the flat config in `eslint.config.mjs` (`npm run lint`), Tailwind utilities rather than custom CSS, and every backend call goes through `frontend/lib/api.ts`.
- **Gems**: `snake_case` names. Each shipped gem exists twice on purpose: as a seed row in `supabase/schema.sql` and as `prompts/<name>.md` for review. Keep them identical.
- **Copy** in docs and UI: sentence case, no exclamation points, no em or en dashes (use commas, periods, or "to" for ranges).

[STANDARDS.md](STANDARDS.md) has the full conventions.

## Checks

CI runs these on every push and pull request; run them locally first.

```sh
ruff check .          # from the repo root
pytest -q             # from the repo root
```

```sh
cd frontend
npm run lint
npx tsc --noEmit
npm run build
```

```sh
cd desktop
npm run lint && npm test
```

CI also runs CodeQL, builds the Docker images, checks that every `prompts/*.md` has a matching seed row in `supabase/schema.sql`, and on Windows builds the console installer, installs it, checks the helper service and uninstalls it.

## Changing a gem

1. Edit `prompts/<name>.md` and the matching row in `supabase/schema.sql` (and add a one-off migration under `supabase/` if existing installs need it, like `add_prompt_enhancer.sql`).
2. Run the gem's eval, for example `python evals/eval_prompt_enhancer.py`. Evals make real API calls and cost money, so they are not part of CI; paste the score in the PR.
3. Do not let the score drop below the baseline recorded at the top of the eval file. If there is no eval for the gem yet, adding one is the best first step.

## Pull requests

1. Open an issue first for anything beyond a small fix, so we agree on the approach. Check [docs/ROADMAP.md](docs/ROADMAP.md) for what is already planned.
2. Branch from `main`. Keep each PR to one change.
3. Fill in the PR template: what changed, why, how you tested it.
4. Update `CHANGELOG.md` under **Unreleased**.
5. If an MCP tool signature or a REST route changed, update [ARCHITECTURE.md](ARCHITECTURE.md) and the tool list in the README.

## Releases

Releases are tagged `vX.Y.Z` and follow [semantic versioning](https://semver.org). To cut one: move the Unreleased items in `CHANGELOG.md` into a new dated `## [X.Y.Z]` section (one block per heading, Keep a Changelog order), set the same version in `backend/app/version.py`, `frontend/package.json` and the README badge, open a PR (CI fails if the four disagree), merge it, then push the tag from `main`. The release workflow turns that changelog section into the GitHub release notes.

## License

By contributing you agree your code is released under the MIT license in [LICENSE](LICENSE).
