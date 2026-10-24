# Contributing to gemsAPI

Thanks for helping. The most useful contributions right now are tests around the resolver, fixes from the [roadmap](docs/ROADMAP.md), and well-evaluated gems.

## Development setup

```sh
git clone https://github.com/poyfather/gemsAPI.git && cd gemsAPI
python -m venv backend/.venv && source backend/.venv/bin/activate   # Windows: backend\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt -r requirements.txt           # runtime deps, plus pytest and ruff
cd frontend && npm install && cd ..
```

On Windows, `scripts\setup.ps1` does the Python half and `scripts\test.ps1` runs the checks.

The unit tests do not touch Supabase or any LLM, so you can run them without credentials. To try the API, UI or MCP server for real you need a Supabase project with `supabase/schema.sql` applied and the env files described in the README. Never commit `.env` or `.env.local`; both are git-ignored.

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

CI also runs CodeQL and checks that every `prompts/*.md` has a matching seed row in `supabase/schema.sql`.

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

Releases are tagged `vX.Y.Z` and follow [semantic versioning](https://semver.org). To cut one: move the Unreleased items in `CHANGELOG.md` into a new dated `## [X.Y.Z]` section, update the version badge in the README and the `version` strings in `backend/app/main.py` and `frontend/package.json`, commit, then push the tag. The release workflow turns that changelog section into the GitHub release notes.

## License

By contributing you agree your code is released under the MIT license in [LICENSE](LICENSE).
