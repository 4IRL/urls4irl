# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. 

Keep your replies extremely concise and focus on conveying the key information. No unnecessary fluff, no long code snippets.

Reference plan may have files in the @plans directory - please reference these if there's a relevant plan file in this directory.


## Workflow Rules

Always delegate work to subagents when a skill/workflow specifies subagent delegation. Never perform the work directly in the parent context.

### Asking the User Questions

Whenever you present the user with 2+ discrete options — approval, strategy choice, file selection, branching decisions, etc. — always use the `AskUserQuestion` tool. Never use a plain-text numbered list or `[y/n]` prompt for enumerable choices. If the tool schema is not loaded, load it via `ToolSearch query: "select:AskUserQuestion"` first. Open-ended questions without enumerable options (e.g. "What should I name this branch?") are the only exception.

## Project Overview

urls4irl is a full-stack web app for managing shared collections of URLs called "UTubs". Flask backend with Jinja2 templates and a vanilla JS frontend currently transitioning to Vite/ES6 modules.


## Project Structure

Review files are stored at the project root level (`reviews/`), NOT under the `plans/` directory. Always look for `reviews/` at the repository root.

### `plans/tmp/` Is Transient Only

`plans/tmp/` (and `$TMPDIR`) are for **transient intermediate files only** — e.g., subagent output that gets read and deleted in the same workflow. **Never store final documents** (plans, reviews, push reviews) in `plans/tmp/`. Final documents always go under `plans/<topic>/`. If no topic can be inferred, ask the user which topic to use.

### Endpoint Registry

`ENDPOINT_REGISTRY.md` at the project root maps every route through all implementation layers (handler → service → schema → template → JS module → tests). **When any code change adds, modifies, or removes an endpoint, its entry in the registry must be updated in the same commit.** This includes changes to:
- Route handlers, decorators, or URL paths
- Service functions called by routes
- Pydantic request schemas
- Templates rendered by routes
- JS modules that call endpoints
- Test files covering endpoints

### `.claude/`, `CLAUDE.md`, and `.gitignore`

Files under `.claude/` (skills, scripts, settings), `CLAUDE.md`, and `.gitignore` may be committed and pushed on **any branch**, regardless of the branch topic. Always include these changes alongside other work — never exclude them for being "unrelated."


### Squash-Merge Branch Hygiene (CRITICAL)

**After a PR is squash-merged into main, NEVER continue working on the same branch.** Squash merges create a new commit hash on main — the old branch commits become stale duplicates. Pushing the old branch creates a PR with a bloated diff that re-introduces already-merged code.

**Required workflow after a squash-merge:**
1. `git checkout main && git pull`
2. Create a new branch: `git checkout -b feature/<next-topic>`
3. Continue work on the new branch

**Before any push (`/git-push`):** Run `git cherry origin/main HEAD`. If ANY commit shows `-` (already in main), **STOP** and rebase before pushing. This check is mandatory and enforced in the `/git-push` skill as Step 0.


## Development and Coding Practices

Code should be concise, but readable. We are looking for maintainability and future proofing.


### Frontend - JavaScript/HTML/CSS

1. Never use window globals for module communiation


### Backend - Python/PostgreSQL/Redis

1. Use typehints! No shortcuts around this.
2. Never use quoted type hints (e.g. `"Utubs"`). All schema/model files use `from __future__ import annotations`, which makes every annotation lazy at runtime — so `TYPE_CHECKING`-only imports and self-referential return types can be written unquoted.
3. Never use single-letter variable names. All variables must be named descriptively to convey their purpose (e.g. `value` not `v`, `route_fn` not `f`, `validation_error` not `e`, `SchemaT` not `T`).

### Tests

Tests are a MUST. We are looking for nearly 100% code completion if possible.

0. Follow test patterns already established
1. All backend code must have integration tests that involve a test database and/or Redis.
2. All frontend code should have at least one happy and one sad path test associated with the UI, unless the UI is complex to warrant multiple tests.

#### Testing Best Practices

1. **Use HTTP for all development tests** - Local development uses HTTP by default (`http://127.0.0.1:8659`), not HTTPS
2. **Run all tests in Docker, never on host** - Always use the Docker containers for running tests
3. **Debug UI test failures with Playwright before changing code** - When a UI test fails and the root cause isn't clear from code inspection, use Playwright MCP to manually reproduce the issue and observe actual behavior BEFORE making code changes
4. **All test failures and errors are legitimate** - When running tests sequentially marker by marker, every failure or error (`InvalidSessionIdException`, `SessionNotCreatedException`, 300+ second setup timeouts, assertion errors) must be recorded and investigated. There is no such thing as "Selenium session exhaustion" as a dismissible category — if sessions are dying, it indicates a real bug (e.g., a fixture not tearing down properly, a test hanging). Always record and investigate.
5. **Check Selenium container health when sessions repeatedly fail** - If `SessionNotCreatedException` or `InvalidSessionIdException` persist across multiple test runs, check the Selenium container health (`docker compose ps selenium`) and restart it if needed (`docker compose restart selenium`), but still record and investigate the root cause.
6. **`TimeoutException` in Selenium tests always requires investigation** - A `TimeoutException` is never pre-existing or dismissible as "flaky". It indicates either a UI logic bug introduced by recent changes, or a genuine timing/stability issue that must be diagnosed and fixed. Never dismiss a `TimeoutException` without identifying its root cause.
7. **Prefer parallel make targets** - Use `make test-marker-parallel m=<marker>` (integration) or `make test-ui-parallel` (UI, default n=8) by default. Sequential targets are fallbacks only. Never run two separate make test commands simultaneously — "parallel" means `-n` workers within a single invocation, not two concurrent terminal commands.
   - **CRITICAL: Never run integration and UI test suites at the same time** — even as background processes. They share a single test DB and Redis instance; concurrent `db.drop_all()` calls corrupt the DB. Always finish one suite completely before starting the other.
   - **UI parallelism cap: n=8 max** — Each UI worker needs a dedicated Flask server, Chrome session, and Postgres DB. Running n=12 saturates host CPU/RAM during concurrent startup, causing 120+ second fixture setup times that exceed Selenium wait timeouts and produce spurious login assertion failures. Individual markers pass at n=4; the full suite is stable at n=8.
8. **Reset bad database state** - If tests fail due to leftover state from previously interrupted or parallel test runs, restart the `web` and `test-db` containers: `make restart c=web && make restart c=test-db`
9. **Never dismiss test failures without investigation** - "File not modified on this branch" does not prove the failure is unrelated. Follow this structure for every failure:
   1. **Read the failing test** — understand what it asserts and how it sets up state
   2. **Check branch changes for indirect effects** — shared test utilities/fixtures, templates/CSS/JS the test's page depends on, schema/model changes affecting the endpoint, additive changes with potential side effects
   3. **Trace the full code path** — read the JS, template, route handler, and schema involved in the failing assertion end-to-end
   4. **Compare with passing sibling tests** — if a similar test passes (e.g., `_btn` vs `_key` variant), identify what differs (timing, interaction method, element targeting)
   5. **Check timeout/wait values** — compare with similar waits elsewhere in the codebase; tight timeouts under parallel load are a common flake source
   6. **Rerun in isolation** — run the test alone 2-3 times to determine if it's a parallelism/timing flake vs a deterministic failure
   7. **Identify specific root cause** — conclude with a concrete diagnosis (e.g., "3-second timeout too tight under 8-worker parallel load"), not a vague "flaky" or "pre-existing"

### Code Style

This project is primarily Python with some JavaScript/HTML/CSS. When editing Python code, verify constant names, decorator types (`@model_validator` vs `@field_validator`), and imports against the actual codebase before making changes.

### Import Style

Always use top-level (global) imports. Never use local imports (inside functions, methods, or conditional blocks) unless the user explicitly requests it as a design decision — no exceptions.

**Standing exemption — `vi.importActual()` inside vitest `it(...)` blocks**: vitest's `vi.mock()` hoisting runs before module-level code, so `vi.importActual()` calls used for partial mocking cannot be moved to module scope. Local usage inside `it(...)` closures is permitted for this specific pattern only.

### Import Ordering

Imports are sorted into three groups, each alphabetized internally, separated by a blank line:

1. Standard library modules
2. Third-party modules
3. Project modules (`backend.*`, `tests.*`, etc.)

### General

1. Always clean up temporary debug code (console.logs, window.* global exposures, debug hacks) before marking a task complete. Review all changes for leftover debugging artifacts.
2. **Never use Bash to write files** — use the `Write` tool instead of `cat >`, `cat <<`, `echo >`, `tee`, or `printf >`. Heredocs and redirects with JSON/code content trigger security prompts due to brace+quote detection. The `Write` tool bypasses this entirely.
3. **Never use inline `python3 -c` with braces** — write the script to a temp file and execute it. Inline Python with `{}` (dicts, f-strings, sets) triggers the same brace+quote security check.
4. **Never use Bash brace expansion** — `{a,b,c}` in shell commands triggers the same brace+quote security check. Use Glob tool, wildcards (`*.md`), or list files individually instead.

### Test Output Location

Always write test output to `/tmp/claude/` (e.g., `/tmp/claude/test-foo-results.txt`). Never use `$TMPDIR` — it resolves to different directories depending on sandbox mode, causing files written in one tool call to be invisible in the next. Never use project-level directories for test output.

## Testing & Verification

After making code changes, proactively check for downstream breakage (changed error messages, removed elements, renamed constants) before marking work complete.

## Build Verification

After editing JavaScript files, always run the Vite build (`docker compose exec vite npx vite build`) to verify no import path errors, missing exports, or syntax issues before reporting success.

## Development Commands

### Makefile Shortcuts

A `Makefile` is provided for common tasks. **Always prefer Makefile commands** over typing full Docker commands directly. Claude Code should use these for all standard operations:

| Command | Description |
|---|---|
| `make up` | Build and start the full stack |
| `make down` | Stop the stack |
| `make build` | Rebuild images without starting |
| `make restart c=<service>` | Restart a specific compose service |
| `make test-integration-parallel [n=4]` | All non-UI integration tests in parallel (**preferred**) |
| `make test-integration` | All non-UI integration tests (sequential fallback) |
| `make test-ui-parallel [n=8]` | All UI/Selenium tests in parallel (**preferred**, max n=8) |
| `make test-functional` | All UI/Selenium functional tests (sequential fallback) |
| `make test-js` | All JS unit tests (vitest) |
| `make test-marker-parallel m=<marker> [n=4]` | Tests for a specific marker in parallel (**preferred**) |
| `make test-marker m=<marker>` | Tests for a specific marker (sequential fallback) |
| `make vite-build` | Vite build verification |
| `make generate-types` | Regenerate TypeScript API types from OpenAPI spec |
| `make help` | List all available make commands |

### Docker Execution Note

**CRITICAL:** All `docker`, `docker compose`, and `make` commands must be run outside sandbox mode due to Docker socket access requirements. Always set `dangerouslyDisableSandbox: true` on every Bash call that runs these commands. Example: `Bash(command: "make test-marker-parallel m=urls > \"/tmp/claude/test-results.txt\" 2>&1", dangerouslyDisableSandbox: true)`

### Git Config Write Note

The sandbox blocks writes to `.git/config`. This means `git push -u` silently fails to save upstream tracking refs. After pushing a branch, always set tracking separately with `dangerouslyDisableSandbox: true`:

```bash
git branch --set-upstream-to=origin/$BRANCH $BRANCH
```

Without this, `git fetch -p` cannot detect merged/deleted remote branches as "gone", breaking branch cleanup workflows like `gmas`.

### Running the App (Docker - recommended)

```bash
# Local development with Vite hot reload, Selenium, PostgreSQL, Redis
docker-compose --project-directory . -f docker/compose.local.yaml up --build --remove-orphans

# OR, if docker-compose is not in use
docker compose --project-directory . -f docker/compose.local.yaml up --build --remove-orphans

# Flask available at http://localhost:8659, Vite at http://localhost:5173
# SSL is disabled by default. To enable HTTPS in local development:
# Set ENABLE_SSL=true and VITE_URL=https://localhost:5173 in docker/compose.local.yaml
```

#### Playright

Use the following URL to access the website with Playwright MCP: `http://127.0.0.1:8659/`

### Running the App (without Docker)

```bash
flask db upgrade
flask shorturls add
flask managedb create          # optional: populate test data
flask run --host=0.0.0.0 --port=5000
```

### Frontend (Vite)

```bash
docker exec u4i-local-vite npm run build  # production/dev build to backend/static/dist/
docker compose exec vite npm test          # run JS unit tests (vitest) from repo root
```

### Testing

**CRITICAL: When running tests in Docker containers, the virtual environment must be activated first:**

```bash
# Running tests in Docker (web container)
docker compose --project-directory . -f docker/compose.local.yaml exec web bash -c "source /code/venv/bin/activate && python -m pytest [test-path]"

# Examples:
docker compose exec web bash -c "source /code/venv/bin/activate && python -m pytest tests/functional/splash_ui/test_reset_password_ui.py -v"
docker compose exec web bash -c "source /code/venv/bin/activate && python -m pytest -m unit"
```

**Running tests outside Docker (if virtual environment is already activated):**

```bash
pytest                        # run all tests
pytest -m unit                # unit tests only
pytest -m splash              # integration tests for auth
pytest -m utubs               # integration tests for UTubs
pytest tests/unit/test_foo.py # single test file
pytest -k "test_name"         # single test by name
```

Test markers (used for CI parallelization): `unit`, `splash`, `utubs`, `members`, `urls`, `tags`, `account_and_support`, `cli`, `splash_ui`, `home_ui`, `utubs_ui`, `members_ui`, `urls_ui`, `create_urls_ui`, `update_urls_ui`, `tags_ui`, `mobile_ui`

**Prefer parallel make targets** (`test-marker-parallel`, `test-integration-parallel`, `test-ui-parallel`) over sequential ones. "Parallel" means `-n` workers within a single invocation — never run two separate `make test-*` commands simultaneously, as they share a single test DB and Redis instance.

**Always minimize wall-clock time**: use the highest safe `n` value (n=8 for UI per the cap above; n=8+ for integration). Never default to `n=2` for "quick" or "smoke" runs — low parallelism on the full suite just means paying the full test cost at slower cadence, and can expose latent timing flakes (e.g., Selenium session idle-timeout reaps) that never occur at production cadence. A true "smoke" test is scoped by marker (`m=splash_ui`) or test path, NOT lowered parallelism on the full suite.

UI/functional tests require Selenium (`SELENIUM_URL` env var pointing to a Selenium grid).

### Linting & Formatting

```bash
# Python
black .                       # format
flake8                        # lint (E501 line length ignored)

# JavaScript
npx prettier --write .        # format
npx eslint .                  # lint

# All at once via pre-commit
pre-commit run --all-files
```

**Note:** Never run `pre-commit`, `black`, or `flake8` manually unless explicitly asked — pre-commit runs all of these automatically as a git hook on commit.

### Flask CLI Commands

```bash
flask addmock all             # populate DB with test data
flask managedb clear          # clear test data
flask managedb drop           # drop database tables
flask shorturls add           # register short URL routes
```

### Database Migrations

```bash
flask db upgrade              # apply migrations
flask db migrate -m "msg"     # generate new migration
flask db downgrade            # rollback last migration
```

## Review Workflow

1. When reading review files, always scroll to the END of the file first to find the latest revision/pass. Never assume the highest line number found in an initial read is the last revision — the file may be longer than what was initially loaded.
2. Be conservative with file reads during plan reviews. Read only the files directly referenced in the plan steps, not every potentially related file. Token limits are a real constraint.
3. Do not append 'Verification' reminders or checklists after applying review items to plans. Just apply the edit and provide the staff-engineer critique.


## Architecture

See `ARCHITECTURE.md` for full codebase structure (blueprints, models, extensions, frontend, security, Docker, env vars). Not loaded automatically — read it when navigating unfamiliar parts of the codebase.
