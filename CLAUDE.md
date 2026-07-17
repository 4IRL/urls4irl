# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. 

Keep your replies extremely concise and focus on conveying the key information. No unnecessary fluff, no long code snippets.

Reference plan may have files in the @plans directory - please reference these if there's a relevant plan file in this directory.


## Claude Config

<!-- Consumed by the stronghold's central generic skills (see ~/code/CLAUDE.md).
     Stable keys — do not rename. Account-specific GraphQL IDs are intentionally NOT inlined here
     (secrets policy); the genericized workflow resolves them at runtime by name — see the
     GitHub project board key below. -->

- **Repo slug:** `4IRL/urls4irl`  (always pass `--repo 4IRL/urls4irl` to `gh`; `GPropersi/urls4irl` redirects but is not canonical)
- **Default branch:** `main`
- **Stack:** `flask-jinja-vanillajs-vite` (drives which opt-in plan-creator/plan-reviewer protocol reference files load — Python/Flask backend, SQLAlchemy, Jinja templates, vanilla-JS→Vite/ES6 frontend, Vitest + Selenium tests, pip/`requirements-*.txt` pinning)
- **Plans store (central):** `~/code/plans/urls4irl/{open,completed,research}/<topic>/` — plans now live in the central stronghold store, not this repo (bucket = this repo's slug basename `urls4irl`). Reviews/research/mocks are co-located per plan under its `<topic>/`; finished topics move `open/`→`completed/` as a unit. See `~/code/CLAUDE.md` "Central Plans Store". (Legacy in-repo `plans/` migrated 07-2026; the leftover `plans/tmp/` is gitignored scratch.)
- **Bot identity:** `u4i-claude-code[bot]` `141576524+u4i-claude-code[bot]@users.noreply.github.com`
- **Bot push script:** `.claude/scripts/gh-app-push.sh` (or the central `~/code/.claude/scripts/gh-app-push.sh`, which derives the repo from `origin`)
- **Token generator:** `~/.claude/generate-gh-token.sh`
- **Container runtime:** `docker compose --project-directory . -f docker/compose.local.yaml`
- **App URL (Playwright MCP):** `http://127.0.0.1:8659/`
- **Test login:** username `u4i_test1` (default) / password `<username>@urls4irl.app` (seeded local test creds; see `login-with-playright` skill)
- **Commands:**
  | Purpose | Command |
  |---|---|
  | Integration tests | `make test-integration-parallel` (single marker: `make test-marker-parallel m=<marker>`) |
  | UI tests | `make test-ui-parallel-built` (max `n=8`) |
  | JS/unit tests | `make test-js` |
  | Build | `make vite-build` |
  | Lint / format | `pre-commit run --all-files` (runs automatically on commit — do not run manually unless asked) |
  | Regenerate types | `make generate-types` |
- **GitHub project board:** `URLS4IRL -> Real Life` (org project). Its project / status-field / option / bot-node GraphQL IDs are **resolved at runtime by name** via `gh api graphql` (from this board name + the `Bot identity` login) — never inlined here, per the secrets policy. The genericized `/git-push` performs the lookup; `.claude/skills/git-push/SKILL.md` documents the mutations.
- **Issue labels:** the repo's existing set — resolve at runtime via `gh label list --repo 4IRL/urls4irl` (do not invent labels)
- **PR reviewer:** `GPropersi`


## Project Overview

urls4irl is a full-stack web app for managing shared collections of URLs called "UTubs". Flask backend with Jinja2 templates and a vanilla JS frontend currently transitioning to Vite/ES6 modules.

### Environment & Branch Terminology (IMPORTANT — non-standard)

This project's naming differs from most companies. Do not assume the conventional meanings:

| This project | Conventional equivalent | What it actually is |
|---|---|---|
| **`dev`** | **Staging** | A **remote** server that replicates **prod**. It is updated when **PRs are merged**. Treat `dev` as the staging/pre-prod environment — NOT a developer's local machine. |
| **`local`** | **Dev** | The **local** environment you run on your own machine (the Docker stack via `make up d=1`) **before** opening a PR. This is "development" in the usual sense. |

- When this repo (configs, compose files, env vars, scripts, docs) says **`dev`**, read it as **staging** (remote, prod-like, updated on merge).
- When it says **`local`**, read it as **local development** (your machine, pre-PR).
- So the promotion path is: **`local` (your machine) → PR → merge → `dev` (remote staging) → prod.**


## Project Structure

Review files are stored **co-located with each plan** at `plans/<topic>/reviews/<plan-name>-review.md` — this matches the 30+ existing review folders in the repo. (An earlier version of this note claimed a repo-root `reviews/`; that was inaccurate and there is no repo-root `reviews/` directory.)

### Endpoint Registry

`ENDPOINT_REGISTRY.md` at the project root maps every route through all implementation layers (handler → service → schema → template → JS module → tests). **When any code change adds, modifies, or removes an endpoint, its entry in the registry must be updated in the same commit.** This includes changes to:
- Route handlers, decorators, or URL paths
- Service functions called by routes
- Pydantic request schemas
- Templates rendered by routes
- JS modules that call endpoints
- Test files covering endpoints

### Metrics Coverage for New Endpoints

**Every new endpoint must be deliberately tied into the anonymous-metrics dashboard — never left untracked by default.** When adding (or materially changing) a route, decide and act on its metrics coverage in the same PR:

1. **Confirm `API_HIT` covers it.** The `after_request` middleware (`backend/extensions/metrics/middleware.py`) auto-counts every request by `endpoint × method × status_code × device_type` — *unless* the endpoint is in `_SKIP_ENDPOINTS` or the metrics blueprint. This gives volume + status distribution for free. If the new route is in the skip-set, justify it.
2. **Decide whether a DOMAIN event is warranted.** For a meaningful user action (a search performed, a resource created/opened, a flow completed), add an explicit `record_event(EventName.X, ...)` in the **service layer**, mirroring `UTUB_OPENED`. Prefer a low-cardinality closed-set dimension when it makes the metric actionable (e.g. `has_results: true/false`). If you deliberately rely on `API_HIT` only, say so in the PR body rather than silently skipping.
3. **Full three-way registry alignment is mandatory for any new event:** `EventName` (`events.py`) + `EVENT_REGISTRY` (`event_registry.py`) + `DIMENSION_MODELS`/dim model (`dimension_models.py`) + `EVENT_NAME_TO_RESOURCE` (`resources.py`). The dim model's `Literal[...]` must exactly match the registry `dimensions` tuple. Then run `make audit` (must exit 0) and `make generate-types` (stage regenerated `frontend/types/*`).
4. **Watch for resource-set fallout.** Introducing a `Resource` into a new category (e.g. adding `Resource.SEARCH` to DOMAIN) can flip previously-invalid `(category, resource)` query pairs to valid — update any negative dashboard/query tests that asserted the old invalid pair. Run the metrics query/service/CLI integration suites, not just unit, after such a change.

Performance/latency **is** measured. `backend/extensions/request_timing.py` records per-request durations into `Anonymous_Latency_Samples` (raw, ~35-day retention via `LATENCY_RAW_RETENTION_DAYS`), which the Flask-less flush worker rolls up nightly into `Anonymous_Latency_Daily_Rollups` (stored p50/p95/p99 per endpoint×method). Query it via `backend/metrics/query_service.py` `latency_percentiles(...)` (rows ordered by p95 desc; `.approximate=True` when served from rollups) / `latency_timeseries(...)`. It surfaces in the metrics dashboard's "Backend Performance" tab and, as a "slowest endpoint (p95)" headline stat, on the admin system-health dashboard (`backend/admin/health_service.py`). The single latency metric today is `LatencyMetricName.API_REQUEST_DURATION` (`"api_request_duration"`).

### GitHub Issue Linking

Every plan and every PR has a linked GitHub issue. The **issue** carries the public-facing WHY (Problem / Why / Outcome — read at a glance); the **plan** is the source of truth for HOW (detailed steps, file paths, code shapes).

**Single-plan flow:**
1. `/plan-creator` creates the plan file, then creates a GitHub issue (or links to an existing matching one) and writes `github_issue:` + `github_issue_url:` into the plan's YAML frontmatter.
2. `/git-push` reads the frontmatter and appends `Closes #<N>` to the PR body. GitHub auto-closes the issue when the PR merges.

**Master-plan flow:**
1. `/master-plan-creator` writes the master and creates an **umbrella issue** linked via the master file's frontmatter.
2. Each sub-plan (created by `/plan-creator` from a phase) gets its own issue, with `Part of #<umbrella>` appended to the body.
3. The **final sub-PR** appends both `Closes #<sub>` and `Closes #<umbrella>` to its body, closing both on merge.

**No-plan PRs (hotfixes):** `/git-push` auto-drafts a minimal issue from branch name + commit messages, prompts the user to confirm/edit/link/skip, then proceeds with `Closes #<N>`.

**Issue metadata:** category labels (from the existing 16) + `URLS4IRL -> Real Life` project board + bot assignee. No milestone — that stays PR-only.

**Repo for `gh` commands:** always `--repo 4IRL/urls4irl`. (`GPropersi/urls4irl` redirects but is not canonical.)


## Development and Coding Practices

Code should be concise, but readable. We are looking for maintainability and future proofing.


### Frontend - TypeScript/HTML/CSS

1. Never use window globals for module communication
2. **User-facing strings — bridge only what TS or tests actually read.** The bridge (`backend/utils/strings/<domain>_strs.py` → `STRINGS` class → `generate_strings_js()` → `frontend/test-setup.ts` mock → `APP_CONFIG.strings.KEY_NAME`) is a 5-file round-trip. Pay it only when there's a real consumer; otherwise the literal belongs in Jinja.

   The right test is **who reads the string**:

   | Where the string is read from | What to do |
   |---|---|
   | Production TypeScript reads `APP_CONFIG.strings.X` (dynamic DOM, dropdown options, time-ago text, error banners, etc.) | **Full bridge.** Backend constant + `STRINGS` + `generate_strings_js()` + `test-setup.ts` mock. |
   | Only Jinja renders it AND a Python UI test asserts the rendered DOM text | **Backend constant only.** Define it in `<domain>_strs.py` and reference it from `ui_testing_strs.py` so the Python test imports it. Do **not** add it to `generate_strings_js()` or `test-setup.ts`. |
   | Only Jinja renders it AND nothing asserts against the literal (static section heading, ARIA label, window radio label, placeholder) | **No bridge.** Write the literal directly in the Jinja template. |

   Hard rules that still apply: never hardcode display strings in TypeScript (always go through `APP_CONFIG.strings`); `ui_testing_strs.py` constants must import from the backend source, never duplicate the literal.
3. **Destructured object parameters** — any function taking 2+ parameters (or even a single boolean/enum-ish parameter where the call site would otherwise be a bare literal) must accept a single destructured object so call sites are self-documenting. Prefer `emitMetric({ name, utubId, urlId })` over `emitMetric(name, utubId, urlId)`; `openModal({ dismissible: false })` over `openModal(false)`. Applies to new functions and to edits that touch an existing signature — when modifying a positional-args function, convert it as part of the change.
4. **Established TS patterns** — use these existing patterns rather than inventing new ones:
   - **Type-guard dispatch** for field-level validation errors: `const FIELDS = [...] as const` + `isFieldName()` guard (see `splash/init.ts`, `tags/create.ts`)
   - **is429Handled(xhr)** guard at the top of every `.fail()` handler (`frontend/lib/ajax.ts`)
   - **Schema<>/SuccessResponse<>** type helpers from `frontend/types/api-helpers.d.ts` for typed AJAX
   - **offAndOnExact** jQuery plugin for rebinding listeners on repeatedly shown/hidden elements
   - **ajaxCall()** wrapper for all AJAX — never use `$.ajax` directly
   - **App store** (`frontend/store/app-store.ts`): `getState()`/`setState()` with `Object.assign` merges
   - **Event bus** (`frontend/lib/event-bus.ts`): typed `emit()`/`on()` with `AppEvents` enum — see ARCHITECTURE.md for full event reference
   - **Vitest mocks**: `vi.mock()` at top, `createMockJqXHRChainable()` from `frontend/__tests__/helpers/mock-jquery.ts`, `vi.importActual()` inside `it()` blocks only
5. **Runtime debug logging via `debug(namespace)`** — never call `console.*` directly in app code; enforced by ESLint `no-console` (rule in `frontend/eslint.config.js`; `lib/debug.ts` is the only whitelisted file). Use `import { debug } from "<path>/lib/debug.js"; const log = debug("subsystem"); log("event", data);`. Toggle namespaces via DevTools: `localStorage.debug = "metrics,ajax"` then refresh. The 5 splash namespaces (`splash`, `splash:login`, `splash:register`, `splash:password`, `splash:email`) are available to any user; all other namespaces require `APP_CONFIG.debugEnabled` (admin-only). The 19 active namespaces are: `ajax, csrf, metrics, config, init, cookie-banner, security, home-shell, utubs, urls, urls:cards, urls:tags, tags, members, splash, splash:login, splash:register, splash:password, splash:email`.


### Backend - Python/PostgreSQL/Redis

1. Use typehints! No shortcuts around this.
2. Never use quoted type hints (e.g. `"Utubs"`). All schema/model files use `from __future__ import annotations`, which makes every annotation lazy at runtime — so `TYPE_CHECKING`-only imports and self-referential return types can be written unquoted.
3. Never use single-letter variable names. All variables must be named descriptively to convey their purpose (e.g. `value` not `v`, `route_fn` not `f`, `validation_error` not `e`, `SchemaT` not `T`).

### Tests

Tests are a MUST. We are looking for nearly 100% code completion if possible.

0. Follow test patterns already established
1. All backend code must have integration tests that involve a test database and/or Redis.
2. All frontend code should have at least one happy and one sad path test associated with the UI, unless the UI is complex to warrant multiple tests.

#### Test Infrastructure Quick Reference

- **Locators**: `tests/functional/locators.py` — `HomePageLocators`, `SplashPageLocators`, `GenericPageLocator`, `ModalLocators`
- **Shared Selenium helpers**: `tests/functional/selenium_utils.py` (40+ helpers: `wait_then_click_element`, `wait_for_element_presence`, `clear_then_send_keys`)
- **Shared DB helpers**: `tests/functional/db_utils.py` (20+ helpers: `get_utub_this_user_created`, `create_test_searchable_utubs`, `add_mock_urls`)
- **Feature-specific helpers**: Each `tests/functional/<feature>_ui/` has its own `selenium_utils.py` with domain helpers (e.g., `urls_ui/selenium_utils.py` has `create_url()`, `open_url_search_box()`)
- **Test constants**: `backend/utils/strings/ui_testing_strs.py` (`UI_TEST_STRINGS` class), `tests/models_for_test.py` (typed test data objects)
- **Frontend test mocks**: `frontend/__tests__/helpers/mock-jquery.ts` — `createMockJqXHRChainable()`, `createMockModal()`
- **Full details**: See ARCHITECTURE.md Testing section

#### Testing Best Practices

1. **Use HTTP for all development tests** - Local development uses HTTP by default (`http://127.0.0.1:8659`), not HTTPS
2. **Run all tests in Docker, never on host** - Always use the Docker containers for running tests
3. **Debug UI test failures with Playwright before changing code** - When a UI test fails and the root cause isn't clear from code inspection, use Playwright MCP to manually reproduce the issue and observe actual behavior BEFORE making code changes
4. **All test failures and errors are legitimate** - When running tests sequentially marker by marker, every failure or error (`InvalidSessionIdException`, `SessionNotCreatedException`, 300+ second setup timeouts, assertion errors) must be recorded and investigated. There is no such thing as "Selenium session exhaustion" as a dismissible category — if sessions are dying, it indicates a real bug (e.g., a fixture not tearing down properly, a test hanging). Always record and investigate.
5. **Check Selenium container health when sessions repeatedly fail** - If `SessionNotCreatedException` or `InvalidSessionIdException` persist across multiple test runs, check the Selenium container health (`docker compose ps selenium`) and restart it if needed (`docker compose restart selenium`), but still record and investigate the root cause.
6. **`TimeoutException` in Selenium tests always requires investigation** - never pre-existing or dismissible as "flaky" (see central Test Failures policy). Indicates either a UI logic bug or a genuine timing/stability issue.
7. **Prefer parallel make targets** - Use `make test-marker-parallel m=<marker>` (integration) or `make test-ui-parallel` (UI, default n=8) by default. Sequential targets are fallbacks only. Never run two separate make test commands simultaneously — "parallel" means `-n` workers within a single invocation, not two concurrent terminal commands.
   - **CRITICAL: Never run integration and UI test suites at the same time** — even as background processes. They share a single test DB and Redis instance; concurrent `db.drop_all()` calls corrupt the DB. Always finish one suite completely before starting the other.
   - **UI parallelism cap: n=8 max** — Each UI worker needs a dedicated Flask server, Chrome session, and Postgres DB. Running n=12 saturates host CPU/RAM during concurrent startup, causing 120+ second fixture setup times that exceed Selenium wait timeouts and produce spurious login assertion failures. Individual markers pass at n=4; the full suite is stable at n=8.
8. **Reset bad database state** - If tests fail due to leftover state from previously interrupted or parallel test runs, restart the `web` and `test-db` containers: `make restart c=web && make restart c=test-db`

Flaky-test hardening and the never-dismiss-without-investigation protocol are covered centrally (see `~/code/CLAUDE.md` → Test Failures: Investigate, Don't Dismiss); the parallelism cap (`n=8`) above is this repo's specific instantiation of "harden to the suite's normal parallelism."

### Code Style

This project is primarily Python with some JavaScript/HTML/CSS. When editing Python code, verify constant names, decorator types (`@model_validator` vs `@field_validator`), and imports against the actual codebase before making changes.

### Dependency Pinning

(see central Dependency Pinning rule for the general policy — this repo's manifests/forms:)

| Manifest                                       | Required form                                                                          | Forbidden forms                           |
|------------------------------------------------|----------------------------------------------------------------------------------------|-------------------------------------------|
| `requirements*.txt` (pip)                      | `package==X.Y.Z`                                                                       | `>=`, `~=`, `<=`, `*`, unpinned           |
| `frontend/package.json` direct deps & devDeps  | `"pkg": "X.Y.Z"`                                                                       | `^X.Y.Z`, `~X.Y.Z`, `>=`, `*`, `latest`  |
| `frontend/package.json` `overrides`            | `"pkg": "X.Y.Z"` (exact patch that satisfies all peer-deps and any open security alert) | `^`, `~`, ranges                          |

If an exact-pin override conflicts with a transitive consumer's peer-dep range (e.g., npm reports `invalid: "X.Y.Z" from node_modules/...`), bump the override to the **exact patch version npm naturally resolves to** rather than reverting to a caret. Document the choice in the commit body.

When adding or bumping a dependency, never introduce a range — if you only need a security fix, pin to the exact patched version listed by `gh api .../dependabot/alerts`. After editing, run `make build && make up d=1` and verify the full test suite passes before committing.

### Import Style

**Exception to the central top-level-imports-only rule — `vi.importActual()` inside vitest `it(...)` blocks**: vitest's `vi.mock()` hoisting runs before module-level code, so `vi.importActual()` calls used for partial mocking cannot be moved to module scope. Local usage inside `it(...)` closures is permitted for this specific pattern only.

### Import Ordering

Imports are sorted into three groups, each alphabetized internally, separated by a blank line:

1. Standard library modules
2. Third-party modules
3. Project modules (`backend.*`, `tests.*`, etc.)

### General

1. **Never use Bash to write files** — use the `Write` tool instead of `cat >`, `cat <<`, `echo >`, `tee`, or `printf >`. Heredocs and redirects with JSON/code content trigger security prompts due to brace+quote detection. The `Write` tool bypasses this entirely.
2. **Never use inline `python3 -c` with braces** — write the script to a temp file and execute it. Inline Python with `{}` (dicts, f-strings, sets) triggers the same brace+quote security check.
3. **Never use Bash brace expansion** — `{a,b,c}` in shell commands triggers the same brace+quote security check. Use Glob tool, wildcards (`*.md`), or list files individually instead.
4. **Never join commands with `&&`, `||`, or `;`** — the `block-compound-commands.sh` PreToolUse hook **denies** any Bash call that chains commands with a sequence operator. Run independent commands as **separate Bash tool calls in the same message** (they execute in parallel). This keeps each command individually permission-checked and stops a destructive op (e.g. `rm -rf`) from hiding mid-chain. **Pipes (`|`) and command-substitution `$(...)` are NOT compounds** and remain fine (`ls | head`, `grep x | wc -l`). Two patterns are exempted in the hook's `EXEMPT_PATTERNS`: the Docker pytest invocation (`... bash -c "source /code/venv/bin/activate && ... pytest ..."`) and the `GH_TOKEN=$(...)` / `BRANCH=$(...)` push prefixes — extend that list (not the rule) if a new legitimate chained pattern recurs.

## Testing & Verification

After making code changes, proactively check for downstream breakage (changed error messages, removed elements, renamed constants) before marking work complete.

### Test Runs Always Use Synchronous Bash

All `make test-*` invocations — integration, UI, single-marker, parallel, full suite — run via the synchronous `Bash` tool, either directly in the orchestrator or inside a subagent the orchestrator launched. **Never** wrap test runs in a `Monitor`, **never** use `run_in_background` for tests, and **never** poll a subagent's result file while the subagent is still in flight. A subagent's Agent-tool reply IS the completion signal; the orchestrator reads the temp result file after that reply lands.

## Build Verification

After editing JavaScript files, always run the Vite build (`docker compose exec vite npx vite build`) to verify no import path errors, missing exports, or syntax issues before reporting success.

## UI Verification Screenshot

**At the end of any UI-affecting change — whether done manually or via `/run-plan` — capture and provide a Playwright screenshot of the actual built feature before reporting the work complete.** A green test suite proves behavior; a screenshot proves the rendered result looks right (and catches things tests miss, e.g. CSS that compiles and passes assertions but renders invisibly).

- **Source matters:** the image must be of the **implemented** feature captured via Playwright MCP against the running app (`http://127.0.0.1:8659/`), NOT the upfront design mock. Reusing a pre-implementation mock does not satisfy this rule.
- Use the `login-with-playright` skill to reach the home page; for mobile features, set the viewport to a mobile width (e.g. 420px) before capturing. Capture the key state(s) of the change (e.g. open AND closed for a toggle/sheet).
- Surface the image to the user with `SendUserFile` (not just a saved path). Save screenshots under `plans/<topic>/screenshots/` (gitignored, like the rest of `plans/`).
- If the app cannot be brought up to capture the screenshot, say so explicitly rather than silently skipping this step.
- **Design mocks and screenshots must NEVER be checked into source control.** Keep them under gitignored paths only (`plans/**`). Before committing, confirm no image artifact landed in a tracked location (e.g. project root, `backend/static/`); if one did, move it under `plans/<topic>/` rather than committing it.

## Generated Types Freshness

After any backend change that alters the OpenAPI surface, run `make generate-types` and stage the regenerated `frontend/types/*` files in the **same commit** as the backend change. CI's `Generated Types Freshness / Generated Types Staleness Check` job runs `make generate-types` then `git diff --exit-code frontend/types/`; if the committed types lag the spec, the job fails with `##[error]Generated types are stale.` and blocks the PR even when every other test passes.

**Triggers (any one is enough):**
- New or modified Pydantic request/response schema referenced by a route
- New or modified `api_route(query_schema=..., header_schema=..., path_schema=...)`
- New or removed route, or a decorator change that affects OpenAPI metadata
- Changes to metrics dimensions, events, or resources (regenerates `metrics-dimensions.d.ts`, `metrics-dim-values.ts`, `metrics-events.ts`, `metrics-resources.ts`)

Before committing a backend change in any of those categories, run `make generate-types` and check `git status` for changes under `frontend/types/`. Stage them in the same commit as the backend change.

## Development Commands

### Makefile Shortcuts

Common tasks (see central Makefile-First Command Policy for the general rule):

| Command | Description |
|---|---|
| `make up d=1` | Build and start the full stack (detached) |
| `make up-built d=1` | Build and start with pre-built Vite assets (detached) |
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
| `make generate-types` | Regenerate TypeScript API types from OpenAPI spec + per-event dim shapes (metrics-dimensions.d.ts, metrics-dim-values.ts, metrics-events.ts) |
| `make help` | List all available make commands |

### Metrics Verification (local stack)

Bring the stack up with `make up d=1` to exercise the anonymous-metrics pipeline end-to-end. The local developer shell exports `METRICS_ENABLED=true`, so a bare `make up d=1` picks it up — **never prefix `METRICS_ENABLED=true` on local commands**. The compose file declares `METRICS_ENABLED=${METRICS_ENABLED:-false}`, but the shell export wins for this stack. To exercise the disabled path, set `METRICS_ENABLED=false` explicitly. Prod is hard-`false` by rollout strategy; dev is hard-`true`.

| Command | Description |
|---|---|
| `make metrics-watch` | Live tail of Redis ops on metrics DB 2 |
| `make metrics-snapshot` | Dump current `metrics:counter:*` keys with values |
| `make metrics-flush-now` | Trigger an immediate flush worker run (Redis → Postgres) |
| `make metrics-rows` | Show last 25 rows from `AnonymousMetrics` |
| `make metrics-smoke-test` | E2E: snapshot → flush → rows |
| `make metrics-clear-counters` | UNLINK pending Redis state (counters + batch nonces); leaves flush lock/sentinel intact |
| `make metrics-clear-rows` | `TRUNCATE "AnonymousMetrics"` |
| `make metrics-clear-all` | Wipe Redis pending + Postgres flushed |

### Docker Execution Note

All `make`/`docker`/`docker compose` targets used by this repo are already listed in `sandbox.excludedCommands` (`.claude/settings.local.json`) and run unsandboxed automatically — no `dangerouslyDisableSandbox` flag needed. Never compound them with another command (see central "Working inside a sub-repo" note on first-token-only matching) — run cleanup/setup as its own Bash call, then the `make`/`docker` call alone.

**CRITICAL:** Never run `make up` or `make up-built` without `d=1`. Without the detached flag, these commands stream Docker logs to stdout indefinitely and never exit. Always use `make up d=1` (or `make up-built d=1`), then poll `docker compose ps` until services are healthy. Before starting containers, check if they're already running with `docker compose --project-directory . -f docker/compose.local.yaml ps`.

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

Test markers (used for CI parallelization): `unit`, `splash`, `utubs`, `members`, `urls`, `tags`, `account_and_support`, `cli`, `splash_ui`, `home_ui`, `utubs_ui`, `members_ui`, `urls_ui`, `create_urls_ui`, `update_urls_ui`, `tags_ui`, `mobile_ui`, `metrics_ui`, `settings_ui`, `search_ui`, `mobile_api`, `admin`, `admin_ui`

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

**Every migration must be tested in BOTH directions, against the full mock dataset, before it is committed.** A migration that "passes" only because the table happens to be empty has not actually been tested.

**Required steps:**

1. **Seed all relevant mock data first.** `flask addmock all` populates users, UTubs, members, URLs, tags, AND `AnonymousMetrics` (9 deterministic rows via the bundled `seed-uniform-test-data` helper). If a future table is added that isn't covered, extend `_add_all()` in `backend/cli/mock_options.py` rather than leaving developers to remember a follow-up command.
2. **Run `flask db upgrade`** and assert the expected post-state (row counts, dimension keys, column values, FK integrity).
3. **Run `flask db downgrade`** (no arg = back one revision; or pass the target revision id explicitly) and assert the expected reverted state — or that it raised the intended "irreversible" error. **A no-op downgrade still gets run** to confirm it executes without raising.
4. **Run `flask db upgrade` again** and confirm the upgrade is idempotent / re-applies cleanly.
5. For data migrations whose downgrade is intentionally a no-op, document the irreversibility in a comment in `downgrade()`.

This rule applies even when the migration is purely additive, purely data, or "obviously safe." The cost of running two extra commands is far less than the cost of a deploy-time migration failure.

## Review Workflow

(scroll-to-end-first convention is centralized — see central CLAUDE.md)

1. Be conservative with file reads during plan reviews. Read only the files directly referenced in the plan steps, not every potentially related file. Token limits are a real constraint.
2. Do not append 'Verification' reminders or checklists after applying review items to plans. Just apply the edit and provide the staff-engineer critique.


## Architecture

See `ARCHITECTURE.md` for full codebase structure (blueprints, models, extensions, frontend, security, Docker, env vars). Not loaded automatically — read it when navigating unfamiliar parts of the codebase.
