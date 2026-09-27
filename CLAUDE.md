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
- **Stack:** `flask-jinja-vanillajs-vite` (drives which opt-in plan-creator/plan-reviewer protocol reference files load — Python/Flask backend, SQLAlchemy, Jinja templates, vanilla-JS→Vite/ES6 frontend, Vitest + Playwright tests, pip/`requirements-*.txt` pinning)
- **Plans store (central):** `~/code/plans/urls4irl/{open,completed,research}/<topic>/` — plans now live in the central stronghold store, not this repo (bucket = this repo's slug basename `urls4irl`). Reviews/research/mocks are co-located per plan under its `<topic>/`; finished topics move `open/`→`completed/` as a unit. See `~/code/CLAUDE.md` "Central Plans Store". (Legacy in-repo `plans/` migrated 07-2026; the leftover `plans/tmp/` is gitignored scratch.)
- **Bot identity:** `gpropersi-claude[bot]` `141576524+gpropersi-claude[bot]@users.noreply.github.com`  <!-- renamed from u4i-claude-code; same App, same bot user id -->
- **Bot push script:** `~/code/.claude/scripts/gh-app-push.sh` (central, repo-agnostic; derives the repo from `origin`, pushes as the shared bot)
- **Token generator:** `~/code/.claude/scripts/generate-gh-token.sh` (tracked in the stronghold — the shared consolidated `gpropersi-claude` App; one generator serves every repo, auto-resolves the installation from the repo's owner. Only the private key `~/.claude/u4i-app.pem` lives outside git)
- **Container runtime:** `docker compose --project-directory . -f docker/compose.local.yaml`
- **App URL (Playwright MCP):** `http://127.0.0.1:8659/`
- **Test login:** username `u4i_test1` (default) / password `<username>@urls4irl.app` (seeded local test creds; see `login-with-playwright` skill)
- **Commands:**
  | Purpose | Command |
  |---|---|
  | Integration tests | `make test-integration-parallel` (single marker: `make test-marker-parallel m=<marker>`) |
  | UI tests | `make test-ui-parallel-built` (`n` defaults to the derived `U4I_N_UI`; see Configuration surface) |
  | JS/unit tests | `make test-js` |
  | Build | `make vite-build` |
  | Lint / format | `make lint` · `make format-check` · `make typecheck` (fix: `make format`); onboard a clone/worktree with `make setup` (toolchain + hook + capacity). The pre-commit hook runs these automatically **only if the hook is installed** (`make setup`, or `make hooks` alone; check with `make hooks-check`) |
  | Regenerate types | `make generate-types` |
- **Configuration surface:** every local knob, by tier. Compose reads `--env-file .env` then `--env-file docker/.capacity.generated.env`; shell env beats both. A bare `docker compose` without those flags recreates `db` with default capacity settings, so use `make` targets.
  | Knob                                           | Tier                 | Default                                                              | Set by                                                                                                                                                |
  | ---------------------------------------------- | -------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
  | `.env` secrets (`POSTGRES_*`, `SECRET_KEY`, …) | secrets              | per machine                                                          | hand-edited `.env`, read first via `--env-file .env` (missing `.env` fails loudly)                                                                    |
  | `U4I_N_UI` / `U4I_N_INT`                       | host capacity        | `clamp(cores·2/3, 2, 12)` / `clamp(cores, 2, 16)`, memory-guarded    | `make capacity`; `U4I_N_UI=<n>` / `U4I_N_INT=<n>` overrides are sticky until `=auto`                                                                  |
  | `U4I_MEM_FRACTION`                             | host capacity        | `0.70` (lower it on shared boxes)                                    | `make capacity` input; sticky (also reused by the automatic refresh) until `=auto`                                                                    |
  | `REDIS_METRICS_DATABASES`                      | host capacity        | `max(16, pow2(1 + 2·n_max))`, `n_max = max(n_ui, n_int)`             | emitted by `make capacity` → `redis-metrics --databases` (metrics lease pool sized for 2 concurrent runs)                                             |
  | `U4I_PG_TEST_CONN_LIMIT`                       | host capacity        | `n_max·15 + 50`                                                      | emitted by `make capacity` → the test role's `CONNECTION LIMIT` (applied by `db-init`)                                                                |
  | `U4I_PG_MAX_CONN`                              | host capacity        | `U4I_PG_TEST_CONN_LIMIT + 30` (dev) `+ 3` (superuser)                | emitted by `make capacity` → the `db` cluster's `max_connections`                                                                                     |
  | `U4I_PG_SHARED_BUFFERS_MB`                     | host capacity        | `clamp(usable_mb / 64, 64, 256)`; usable memory ignores MemAvailable | emitted by `make capacity` → the `db` cluster's `shared_buffers`                                                                                      |
  | `HOST_UID` / `HOST_GID`                        | host capacity        | `id -u` / `id -g` (image default 1001; a root host also gets 1001)   | emitted by `make capacity` → web image build args                                                                                                     |
  | `METRICS_ENABLED`                              | tracked default      | `true` locally                                                       | opt a machine out with `METRICS_ENABLED=false` in `.env` (never a shell export)                                                                       |
  | `U4I_SLUG`                                     | worktree identity    | `$(notdir $(CURDIR))`                                                | computed + exported by the Makefile, never stored; derives `U4I_DEV_DB` = `u4i_dev_<sanitized slug>`, the dev DB name                                 |
  | `POSTGRES_TEST_USER`                           | tracked default      | `u4i_test` locally; unset (CI) = `POSTGRES_USER`                     | compose sets `${U4I_TEST_ROLE:-u4i_test}`, the expression `db-init` creates the role from (password = `POSTGRES_PASSWORD`; no CONNECT on `u4i_dev_*`) |
  | `make setup`                                   | onboarding target    | n/a                                                                  | once per clone/worktree: `tools` + `hooks` + `capacity` (idempotent; a failed capacity step, e.g. Docker down, is deferred)                           |
  | `make capacity`                                | host capacity target | n/a                                                                  | writes gitignored `docker/.capacity.generated.env`; stack-start and `-parallel` targets refresh it (`recreate required` = rerun `make up d=1`)        |
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
5. **Runtime debug logging via `debug(namespace)`** — never call `console.*` directly in app code; enforced by ESLint `no-console` (rule in `frontend/eslint.config.js`; `lib/debug.ts` is the only whitelisted file). Use `import { debug } from "<path>/lib/debug.js"; const log = debug("subsystem"); log("event", data);`. Toggle namespaces via DevTools: `localStorage.debug = "metrics,ajax"` then refresh. The 5 splash namespaces (`splash`, `splash:login`, `splash:register`, `splash:password`, `splash:email`) are available to any user; all other namespaces require `APP_CONFIG.debugEnabled` (admin-only). The 20 active namespaces are: `ajax, csrf, metrics, config, init, cookie-banner, security, home-shell, utubs, urls, urls:cards, urls:tags, tags, members, onboarding, splash, splash:login, splash:register, splash:password, splash:email`.


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
- **Shared Playwright helpers**: `tests/functional/playwright_utils.py` (68 helpers: `wait_then_click_element`, `wait_for_element_presence`, `clear_then_send_keys`)
- **Shared Playwright assertions**: `tests/functional/playwright_assert_utils.py` (23 helpers: `assert_visible_css_selector`, `assert_no_page_errors`)
- **Shared Playwright login helpers**: `tests/functional/playwright_login_utils.py` (8 helpers: `login_user_and_select_utub_by_utubid`)
- **Shared DB helpers**: `tests/functional/db_utils.py` (20+ helpers: `get_utub_this_user_created`, `create_test_searchable_utubs`, `add_mock_urls`)
- **Feature-specific helpers**: Each `tests/functional/<feature>_ui/` has its own `playwright_utils.py` (plus `playwright_assert_utils.py` / `playwright_login_utils.py` / `db_utils.py` where applicable) with domain helpers, e.g. `urls_ui/playwright_utils.py` has `create_url()`, `open_url_search_box()`
- **Test constants**: `backend/utils/strings/ui_testing_strs.py` (`UI_TEST_STRINGS` class), `tests/models_for_test.py` (typed test data objects)
- **Frontend test mocks**: `frontend/__tests__/helpers/mock-jquery.ts` — `createMockJqXHRChainable()`, `createMockModal()`
- **Full details**: See ARCHITECTURE.md Testing section

#### Testing Best Practices

1. **Use HTTP for all development tests** - Local development uses HTTP by default (`http://127.0.0.1:8659`), not HTTPS
2. **Run all tests in Docker, never on host** - Always use the Docker containers for running tests
3. **Debug UI test failures with Playwright before changing code** - When a UI test fails and the root cause isn't clear from code inspection, use Playwright MCP to manually reproduce the issue and observe actual behavior BEFORE making code changes
4. **All test failures and errors are legitimate** - When running tests sequentially marker by marker, every failure or error (`playwright.sync_api.Error` (e.g. a `chromium.connect()` failure against the shared browser-server), `playwright.sync_api.TimeoutError`, 300+ second setup timeouts, assertion errors) must be recorded and investigated. There is no such thing as "browser connection exhaustion" as a dismissible category — if browser connections are dying, it indicates a real bug (e.g., a fixture not tearing down properly, a test hanging). Always record and investigate.
5. **Check Playwright browser-server health when connections repeatedly fail** - If `chromium.connect()` failures against the shared browser-server persist across test runs, check it with `docker compose --project-directory . -f docker/compose.local.yaml ps playwright` and, only when no UI test run is in progress, restart it with `make restart c=playwright` (the one container serves every UI worker, so a restart kills all in-flight workers). Still record and investigate the root cause. A `RuntimeError: PLAYWRIGHT_WS_URL env var is not set ...` (raised by `build_page_browser` in `tests/functional/conftest.py`) means the `web` service env is misconfigured (see `docker/compose.local.yaml`), not an unhealthy browser-server, so a restart won't fix it.
6. **`playwright.sync_api.TimeoutError` in UI tests always requires investigation** - never pre-existing or dismissible as "flaky" (see central Test Failures policy). Indicates either a UI logic bug or a genuine timing/stability issue.
7. **Prefer parallel make targets** - Use `make test-marker-parallel m=<marker>` (integration, default `n` = derived `U4I_N_INT`) or `make test-ui-parallel` (UI, default `n` = derived `U4I_N_UI`) by default. Sequential targets are fallbacks only. "Parallel" means `-n` workers within a single invocation.
   - **Concurrent runs are isolated; concurrency is bounded by capacity, not correctness.** Every pytest invocation gets its own databases (`{POSTGRES_TEST_DB}_{uid8}_{worker}`, keyed on xdist's `testrun_uid`) and leased Redis indices (self-expiring `u4i:test_lease:*` keys on shared-redis DB 0), so two runs never touch each other's state. Resource rule: at most **one pytest invocation per spoke** at a time.
   - **Parallelism caps are derived per host (every suite, not just UI)** — `make capacity` sets the default worker counts (`U4I_N_UI` for UI targets, `U4I_N_INT` for integration/marker/file targets) from the host's cores and memory, and sizes the interlocks to the larger of the two: the metrics lease pool (`redis-metrics --databases`) and the `db` cluster's connection limits. An explicit `n=` above this host's `U4I_N_MAX` is refused by `_require-n-fits` before pytest starts. To go higher, run `make capacity U4I_N_UI=<n>` (UI targets) or `make capacity U4I_N_INT=<n>` (integration/marker/file targets), then `make up d=1` to recreate the stack with the new interlocks. Overrides above the memory guard are refused, and n ≤ 30 is a hard per-run ceiling (the shared `redis` has `--databases 64`, leaving 62 leasable session indices: room for 2 concurrent runs at n = 30). A `RuntimeError: Redis lease pool '…' is exhausted` means every index is held, usually by leases a killed run leaked: run `make reset-test-dbs`, lower `n`, or run `make capacity` then `make up d=1` to grow the pool. CI does not use `make capacity`; its `test.yml` matrix pins `XDIST_N`. Soft, secondary limit: host CPU/RAM load during concurrent startup. Each UI worker has its own Flask server and Postgres DB, plus its own `chromium.connect()` browser on the **one shared** Playwright browser-server container. The memory guard budgets for that, but heavy load can still slow setup.
8. **Reclaim leaked test resources** - An interrupted run leaves its per-run databases and Redis leases behind. `make reset-test-dbs` (`ttl=<minutes>`, default 10) drops idle, aged per-run test DBs and deletes the leases orphaned with them; it never drops a connected DB, never touches the dev DB, and never flushes Redis DB 0.

Flaky-test hardening and the never-dismiss-without-investigation protocol are covered centrally (see `~/code/CLAUDE.md` → Test Failures: Investigate, Don't Dismiss); the derived caps above are capacity limits, not flake thresholds. At or below them, flaky tests must be hardened to pass at the suite's normal (derived) parallelism.

### Code Style

This project is primarily Python with some JavaScript/HTML/CSS. When editing Python code, verify constant names, decorator types (`@model_validator` vs `@field_validator`), and imports against the actual codebase before making changes.

### Dependency Pinning

(see central Dependency Pinning rule for the general policy — this repo's manifests/forms:)

| Manifest                                       | Required form                                                                          | Forbidden forms                           |
|------------------------------------------------|----------------------------------------------------------------------------------------|-------------------------------------------|
| `requirements*.txt` (pip)                      | `package==X.Y.Z`                                                                       | `>=`, `~=`, `<=`, `*`, unpinned           |
| `frontend/package.json` direct deps & devDeps  | `"pkg": "X.Y.Z"`                                                                       | `^X.Y.Z`, `~X.Y.Z`, `>=`, `*`, `latest`   |
| `frontend/pnpm-workspace.yaml` `overrides:`    | `pkg: X.Y.Z` (exact patch that satisfies all peer-deps and any open security alert)    | `^`, `~`, ranges                          |

Security pins go in `frontend/pnpm-workspace.yaml` `overrides:` at the exact patched version. If one conflicts with a transitive consumer's peer-dep range, use `pnpm why <pkg>` to find the resolved version and pin the override to that **exact patch** rather than reverting to a caret. A pinned version younger than 90 days (`minimumReleaseAge`) also needs an exact `name@version` entry in `minimumReleaseAgeExclude` (no wildcards), or every install fails. Document the choice in the commit body.

pnpm is the only package manager: never run `npm install` in `frontend/`; `make lint` fails via `lockfile-check` if a `package-lock.json` appears. `verifyDepsBeforeRun: error` means pnpm never auto-installs, so after a `package.json`/lockfile change run `make tools` (host) and `make build` (containers). `make up`/`up-built`/`tunnel` pass `-V` so stale anonymous `node_modules` volumes are renewed.

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

After editing JavaScript files, always run the Vite build (`make vite-build`) to verify no import path errors, missing exports, or syntax issues before reporting success.

## UI Verification Screenshot

**At the end of any UI-affecting change — whether done manually or via `/run-plan` — capture and provide a Playwright screenshot of the actual built feature before reporting the work complete.** A green test suite proves behavior; a screenshot proves the rendered result looks right (and catches things tests miss, e.g. CSS that compiles and passes assertions but renders invisibly).

- **Source matters:** the image must be of the **implemented** feature captured via Playwright MCP against the running app (`http://127.0.0.1:8659/`), NOT the upfront design mock. Reusing a pre-implementation mock does not satisfy this rule.
- Use the `login-with-playwright` skill to reach the home page; for mobile features, set the viewport to a mobile width (e.g. 420px) before capturing. Capture the key state(s) of the change (e.g. open AND closed for a toggle/sheet).
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
| `make setup` | One-time per clone/worktree onboarding: `tools` + `hooks` + `capacity` (idempotent; a capacity failure, e.g. Docker down, is deferred — rerun `make capacity` to see the error) |
| `make capacity [U4I_N_UI=<n\|auto>] [U4I_N_INT=<n\|auto>] [U4I_MEM_FRACTION=<f\|auto>]` | Derive test worker counts + interlocks for this host into `docker/.capacity.generated.env` (overrides are sticky; `=auto` clears) |
| `make tools` | Install the pinned host toolchain + `frontend/node_modules` (run by `make setup`; re-run after pin bumps) |
| `make hooks` | Install the pre-commit git hook in the main checkout (run by `make setup`; safe from any worktree — see "Pre-commit hooks" below) |
| `make hooks-check` | Report whether the pre-commit hook is installed (exits 1 when missing; worktree-safe) |
| `make up d=1` | Build and start the full stack (detached) |
| `make up-built d=1` | Build and start with pre-built Vite assets (detached) |
| `make down` | Stop the stack |
| `make build` | Rebuild images without starting |
| `make restart c=<service>` | Restart a specific compose service |
| `make test-integration-parallel [n=<N>]` | All non-UI integration tests in parallel (**preferred**; default `n` = derived `U4I_N_INT`) |
| `make test-integration` | All non-UI integration tests (sequential fallback) |
| `make test-ui-parallel [n=<N>]` | All UI/Playwright tests in parallel (**preferred**; default `n` = derived `U4I_N_UI`) |
| `make test-functional` | All UI/Playwright functional tests (sequential fallback) |
| `make test-js` | All JS unit tests (vitest) |
| `make test-marker-parallel m=<marker> [n=<N>]` | Tests for a specific marker in parallel (**preferred**; default `n` = derived `U4I_N_INT`) |
| `make test-marker m=<marker>` | Tests for a specific marker (sequential fallback) |
| `make test-file f=<path> [args=...]` | Single test file/path |
| `make vite-build` | Vite build verification |
| `make addmock` | Seed dev DB with all mock data |
| `make generate-types` | Regenerate TypeScript API types from OpenAPI spec + per-event dim shapes (metrics-dimensions.d.ts, metrics-dim-values.ts, metrics-events.ts) |
| `make help` | List all available make commands |

### Metrics Verification (local stack)

Bring the stack up with `make up d=1` to exercise the anonymous-metrics pipeline end-to-end. Metrics are **on by default locally**: `docker/compose.local.yaml` declares the tracked default `METRICS_ENABLED=${METRICS_ENABLED:-true}`, so a bare `make up d=1` enables them on every host — **never prefix `METRICS_ENABLED=true` on local commands**. To opt a machine out (or exercise the disabled path), put `METRICS_ENABLED=false` in `.env`, which `make` passes via `--env-file .env`. **Remove any lingering `export METRICS_ENABLED=…` from your shell profile:** compose interpolation resolves the shell environment before `--env-file`, so a leftover export silently overrides the `.env` opt-out (check with `printenv METRICS_ENABLED`). Tests are unaffected (`ConfigTest.METRICS_ENABLED = False`). Prod (`docker/compose.yaml`) and dev (`docker/compose.dev.yaml`) both hard-set `METRICS_ENABLED=true`.

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

**Local Postgres:** one `db` cluster holds the dev DB (`U4I_DEV_DB`, provisioned by the one-shot `db-init`) and every per-run test DB. It runs `fsync=off`, so a host crash may corrupt `pgdata`. Recovery **deletes all dev data**: `make down`, `docker volume rm u4i-local_pgdata`, `make up d=1`, then `make reset-db` to reseed.

### Running the App (Docker - recommended)

```bash
# Local development with Vite hot reload, Playwright, PostgreSQL, Redis
make up d=1    # never omit d=1 — see the CRITICAL note above

# Flask available at http://localhost:8659, Vite at http://localhost:5173
# SSL is disabled by default. To enable HTTPS in local development:
# Set ENABLE_SSL=true and VITE_URL=https://localhost:5173 in docker/compose.local.yaml
```

**Host identity:** the local web image's `u4i-host` user is built with this host's `HOST_UID`/`HOST_GID` (from `make capacity`; build args in `docker/compose.local.yaml`, image default 1001), so files it writes into bind mounts are owned by you. An `app_logs` volume created by an older image, or re-owned by a previous workflow start, can leave `/app/volume/logs` owned by another uid, and web would crash on its log file. `make up`/`up-built`/`start-built`/`tunnel` repair that automatically through the private `_logs-owner-fix` prerequisite, which prints `repairing app_logs ownership (was X, now UID:GID)` once and is silent otherwise. The workflow container keeps write access through the log dir's group.

#### Playwright

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
make vite-build  # build to backend/static/dist/ (= pnpm run build)
make test-js     # run JS unit tests (vitest)
```

These and the Testing targets below `exec` into the running local stack, so it must be up (`make up d=1`); on the built stack (`make up-built`) use the `-built` variants (`vite-build-built`, `test-js-built`, `test-file-parallel-built`).

### Testing

Run tests in Docker via the `make` targets (they activate the container's venv for you):

```bash
make test-file f=<test-path>              # single file or path (pass extra pytest args via args=...)

# Examples:
make test-file f=tests/functional/splash_ui/test_reset_password_ui.py
make test-marker-parallel m=unit
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

**Prefer parallel make targets** (`test-marker-parallel`, `test-integration-parallel`, `test-ui-parallel`) over sequential ones. "Parallel" means `-n` workers within a single invocation. Concurrent invocations are isolated from each other, but keep to one per spoke (see Testing Best Practices #7).

**Always minimize wall-clock time**: omit `n=` so each target uses this host's derived maximum (`U4I_N_UI` for UI, `U4I_N_INT` for integration/marker/file; see the parallelism-cap note above and `make capacity`). Never default to `n=2` for "quick" or "smoke" runs — low parallelism on the full suite just means paying the full test cost at slower cadence, and can expose latent timing flakes (e.g., shared Playwright browser-server connection idle-timeouts) that never occur at production cadence. A true "smoke" test is scoped by marker (`m=splash_ui`) or test path, NOT lowered parallelism on the full suite.

UI/functional tests require the shared Playwright browser-server: the `playwright` service runs `npx -y playwright@1.60.0 run-server --port 3000 --host 0.0.0.0`, the `web` service sets `PLAYWRIGHT_WS_URL=ws://playwright:3000/`, and `build_page_browser` in `tests/functional/conftest.py` calls `chromium.connect(config.TEST_PLAYWRIGHT_URI)` in Docker (falling back to `chromium.launch()` outside it).

### Linting & Formatting

One definition per check, run host-native. The pre-commit hook and CI call the same targets:

```bash
make setup          # once per clone/worktree: tools + hooks + capacity (idempotent)
make tools          # install the pinned toolchain, pnpm install --frozen-lockfile --ignore-scripts, set blame.ignoreRevsFile (run by setup)
make lint           # ruff check + eslint + shellcheck + lockfile-check + lint-actions
make lint-actions   # actionlint on .github/workflows/ (also run by make lint)
make format-check   # ruff format --check + prettier --check + shfmt -d (no writes)
make typecheck      # tsc on frontend/tsconfig.json + tsconfig.test.json (no stack needed)
make format         # apply ruff format + prettier --write + shfmt -w
```

`.mise.toml` is the single pin location (python 3.11.14, node, pnpm, ruff, shellcheck, shfmt, actionlint); prettier is pinned in `frontend/package.json`; ruff config lives in `pyproject.toml`. Don't run `mise trust`: the config must stay pin-only, and `make mise-config-check` enforces that. `.git-blame-ignore-revs` hides the format-only pass from blame (GitHub honors it automatically).

**Note:** Never run `pre-commit`, `ruff`, `eslint`, `prettier`, `make lint`, or `make format` manually unless explicitly asked — pre-commit runs all of these automatically as a git hook on commit.

#### Pre-commit hooks (verify before trusting the note above)

The hook is **per-clone** and is **not** installed by cloning. Because this app is fully
containerized (the venv is baked into the image, nothing installs on the host), a fresh clone has
no host `pre-commit` and therefore **no hook runs on any commit** — silently. Verify with
`make hooks-check` (worktree-safe; exits 1 when missing); install with `make setup`, which runs
`make tools` (the host toolchain the hooks need, since they are `language: system` calls to the
make targets above), then `make hooks` (creates a gitignored `venv/` in the main checkout with the
mise-pinned Python, installs the `pre-commit` pin from `requirements/requirements-dev.txt`, and
installs the hook — safe to run from any worktree), then `make capacity`.

**When committing here, confirm the hook actually ran.** A successful commit that printed no
`ruff-lint...Passed` / `ruff-format...Passed` (or `eslint`, `prettier`, `typecheck`, `shell-lint`,
`shell-format`) lines means no hook was installed and nothing was checked — report that rather than
assuming formatting is clean.

Known rough edges, so these aren't mistaken for code problems:
- **Hooks check the whole tree**, not just staged files, so untracked `.py`/`.ts` scratch files with
  errors can block a commit.
- **GUI/IDE git clients need `mise` on the non-interactive PATH** (`~/.local/bin`); otherwise the hooks
  fail with `host lint toolchain missing — run 'make tools'`.
- **Deleting host `frontend/node_modules` while `vite` runs detaches the container's anonymous-volume
  mask**; recreate it afterwards
  (`docker compose --project-directory . -f docker/compose.local.yaml up -d --force-recreate vite`)
  before `make tools` / `make test-js`.

### Flask CLI Commands

```bash
flask addmock all             # populate DB with test data (Docker: `make addmock`)
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
