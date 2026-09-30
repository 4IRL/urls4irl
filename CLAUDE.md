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
- **Container runtime:** `make` targets only. Each checkout is its own compose project (a "spoke", `u4i-<slug>`, from `docker/compose.local.yaml`), and every spoke shares one per-user "hub" (`u4i-hub-<uid>`, from `docker/compose.hub.yaml`: the Postgres cluster + the Playwright browser server). `make stack-info` prints this checkout's project, URLs, hub and attached spokes. Raw `docker compose -f docker/compose.local.yaml …` fails fast (`required variable U4I_PROJECT is missing a value`): only the Makefile computes the names.
- **App URL (Playwright MCP):** `http://127.0.0.1:8659/` (primary clone; a worktree's web port is resolved per checkout, so read its URL from `make stack-info`)
- **Test login:** username `u4i_test1` (default) / password `<username>@urls4irl.app` (seeded local test creds; see `login-with-playwright` skill)
- **Commands:**
  | Purpose | Command |
  |---|---|
  | Integration tests | `make test-integration-parallel` (single marker: `make test-marker-parallel m=<marker>`) |
  | UI tests | `make test-ui-parallel-built` (`n` defaults to the derived `U4I_N_UI`; see Configuration surface) |
  | JS/unit tests | `make test-js` (host-native vitest — no stack needed) |
  | Build | `make vite-build` |
  | Lint / format | `make lint` · `make format-check` · `make typecheck` (fix: `make format`); onboard a clone/worktree with `make setup` (worktree-init `.env`/secrets links + toolchain + hook + capacity). The pre-commit hook runs these automatically **only if the hook is installed** (`make setup`, or `make hooks` alone; check with `make hooks-check`) |
  | Regenerate types | `make generate-types` |
- **Configuration surface:** every local knob, by tier. A spoke's compose reads `--env-file .env`, then `docker/.capacity.generated.env`, then `docker/.ports.generated.env`; shell env beats all three. The hub's compose always reads the **primary clone's** `.env` and capacity file, whichever checkout runs it. Use `make` targets: raw compose lacks the computed names and files.
  | Knob                                             | Tier                     | Default                                                              | Set by                                                                                                                                                                                                                                                                                                                             |
  | ------------------------------------------------ | ------------------------ | -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
  | `.env` secrets (`POSTGRES_*`, `SECRET_KEY`, …)   | secrets                  | per machine                                                          | hand-edited `.env` in the primary clone (a worktree's is a symlink from `make worktree-init`), read first via `--env-file .env` (missing `.env` fails loudly)                                                                                                                                                                      |
  | `U4I_N_UI` / `U4I_N_INT`                         | host capacity            | `clamp(cores·2/3, 2, 12)` / `clamp(cores, 2, 16)`, memory-guarded    | `make capacity`; `U4I_N_UI=<n>` / `U4I_N_INT=<n>` overrides are sticky until `=auto`                                                                                                                                                                                                                                               |
  | `U4I_MEM_FRACTION`                               | host capacity            | `0.70` (lower it on shared boxes)                                    | `make capacity` input; sticky (also reused by the automatic refresh) until `=auto`                                                                                                                                                                                                                                                 |
  | `REDIS_METRICS_DATABASES`                        | host capacity            | `max(16, pow2(1 + 2·n_max))`, `n_max = max(n_ui, n_int)`             | emitted by `make capacity` → the spoke's `redis-metrics --databases` (metrics lease pool sized for 2 concurrent runs)                                                                                                                                                                                                              |
  | `U4I_PG_TEST_CONN_LIMIT`                         | host capacity (hub)      | `n_max·15 + 50`                                                      | emitted by `make capacity`, read from the **primary clone's** file → the test role's `CONNECTION LIMIT` (applied by the hub's `cluster-init` on every `make up`; no teardown). One limit shared by every spoke's runs                                                                                                              |
  | `U4I_PG_MAX_CONN`                                | host capacity (hub)      | `U4I_PG_TEST_CONN_LIMIT + 30` (dev) `+ 3` (superuser)                | emitted by `make capacity`, read from the **primary clone's** file → the hub `db` cluster's `max_connections`. Hub-recreate interlock: `make down` in every spoke, then `make hub-down` + `make hub-up`                                                                                                                            |
  | `U4I_PG_SHARED_BUFFERS_MB`                       | host capacity (hub)      | `clamp(usable_mb / 64, 64, 256)`                                     | emitted by `make capacity`, read from the **primary clone's** file → the hub `db` cluster's `shared_buffers`. Hub-recreate interlock, like `U4I_PG_MAX_CONN`. Every capacity-file value is sized from stable memory (total × fraction, cgroup), never MemAvailable, so the file never flaps                                        |
  | `U4I_SPOKE_MAX`                                  | host capacity (hub)      | derived; formula in ARCHITECTURE.md → Docker (`compose.hub.yaml`)    | emitted by `make capacity` (with `U4I_USABLE_MB`, `U4I_HUB_IDLE_MB`, `U4I_SPOKE_IDLE_MB`): informational, the spokes that fit on an idle host from stable memory. Spoke admission reads **live** memory (see Hub and spokes) and falls back to this count only when live memory can't be read                                      |
  | `U4I_BASE_MB` / `U4I_WORKER_MB`                  | host capacity            | `2048` / `512`                                                       | emitted by `make capacity` (not interlocks): the per-run memory model (base + per worker) the token runner and spoke admission check against live memory                                                                                                                                                                           |
  | `U4I_MEMORY_WAIT`                                | per run                  | `600` (seconds)                                                      | Makefile knob → token runner `--memory-wait`: a run waiting for memory while no other run holds tokens exits 1 after this long (Testing Best Practices #7). Must be a plain number                                                                                                                                                 |
  | `U4I_SETTLE_SECONDS`                             | per run                  | `20` (seconds)                                                       | Makefile knob → `--settle-seconds`: starts stay serialised this long after a run's child starts, so the next start's live reading includes its ramp-up; a run granted ≤ 2 workers skips it. Must be a plain number                                                                                                                 |
  | `U4I_TOKEN_DIR`                                  | per user                 | `/tmp/u4i-test-tokens-<uid>`                                         | computed by the Makefile: the host token budget's lock dir (`turnstile.lock` + `slot-<i>` holder files), shared by all the user's checkouts. Created `0700`; refused if a symlink, foreign-owned or group/other-accessible. Budget = `U4I_N_MAX` in the **primary clone's** capacity file (Testing Best Practices #7)              |
  | `HOST_UID` / `HOST_GID`                          | host capacity            | `id -u` / `id -g` (image default 1001; a root host also gets 1001)   | emitted by `make capacity` → web + vite image build args, vite `user:`                                                                                                                                                                                                                                                             |
  | `METRICS_ENABLED`                                | tracked default          | `true` locally                                                       | opt a machine out with `METRICS_ENABLED=false` in `.env` (never a shell export)                                                                                                                                                                                                                                                    |
  | `U4I_SLUG`                                       | worktree identity        | `$(notdir $(CURDIR))`                                                | computed + exported by the Makefile, never stored; derives `U4I_DEV_DB` = `u4i_dev_<sanitized slug>` (the dev DB name) and the DNS-safe host slug behind the names below. Two checkouts with the same directory name share a project and dev DB, so keep worktree folder names unique                                              |
  | `U4I_PROJECT` / `U4I_WEB_HOST` / `U4I_VITE_HOST` | worktree identity        | `u4i-<slug>` / `web-<slug>` / `vite-<slug>`                          | computed by the Makefile: the spoke compose project and web's / vite's aliases on the shared network (the hub browser reaches a spoke by them)                                                                                                                                                                                     |
  | `U4I_WEB_PORT` / `U4I_VITE_PORT`                 | worktree identity        | primary `8659` / `5173`; a worktree `+ crc32(slug) % 99 + 1`         | resolved by `scripts/spoke_ports.py` before each stack start: a port another project or any host process holds is skipped, and the result is cached in gitignored `docker/.ports.generated.env`, so a spoke keeps its URL across `down`/`up`. An explicit `U4I_WEB_PORT=`/`U4I_VITE_PORT=` wins (and is cached) but fails if taken |
  | `U4I_SESSION_COOKIE_NAME`                        | worktree identity        | `<project>_session` locally; unset = `session` (prod/staging/CI)     | compose `web` env. Browsers scope cookies by host, not port, so spokes sharing `127.0.0.1` need distinct session cookies                                                                                                                                                                                                           |
  | `U4I_HUB_PROJECT` / `U4I_SHARED_NET`             | per user                 | `u4i-hub-<uid>` / `u4i-shared-<uid>` (`id -u`)                       | computed by the Makefile: the hub compose project and the external network the hub and every spoke join                                                                                                                                                                                                                            |
  | `U4I_PLAYWRIGHT_IDLE_MINUTES`                    | hub (per user)           | `15` (`0` disables reaping)                                          | the **primary clone's** `.env` → hub `playwright` env, read by `docker/playwright-entrypoint.sh` (exits 0 after this many minutes with no client). Applies on the next container created by `make playwright-rebuild`; `make playwright-up` restarts the existing container with its old config                                    |
  | `POSTGRES_TEST_USER`                             | tracked default          | `u4i_test` locally; unset (CI) = `POSTGRES_USER`                     | compose sets `${U4I_TEST_ROLE:-u4i_test}`, the expression the hub's `cluster-init` creates the role from (password = `POSTGRES_PASSWORD`; no CONNECT on `u4i_dev_*`)                                                                                                                                                               |
  | `make setup`                                     | onboarding target        | n/a                                                                  | once per clone/worktree: `worktree-init` + `tools` + `hooks` + `capacity` (idempotent; a failed capacity step, e.g. Docker down, is deferred)                                                                                                                                                                                      |
  | `make worktree-init`                             | onboarding target        | n/a                                                                  | links `.env` and `secrets/` from the primary clone into a worktree (no-op in the primary; never clobbers a real file); run by `setup`, `up`, `up-built`, `start-built`, `tunnel`                                                                                                                                                   |
  | `make stack-info`                                | worktree identity target | n/a                                                                  | prints this checkout's project, aliases, resolved URLs, hub project, hub `db` and `playwright` state (`hub playwright: Exited (0) …` = idle-reaped, `absent` = never created) and attached spokes                                                                                                                                  |
  | `make hub-up` / `make hub-down`                  | hub target               | n/a                                                                  | `hub-up` starts the hub `db` (never recreating it) and runs `cluster-init`; every stack start runs it. `hub-down` refuses while any spoke container (running or stopped) is attached, else stops the hub and removes the network                                                                                                   |
  | `make capacity`                                  | host capacity target     | n/a                                                                  | writes gitignored `docker/.capacity.generated.env`; stack-start and `-parallel` targets refresh it (`recreate required` = rerun `make up [p=…] d=1`; `hub recreate required` = the hub teardown above). In a linked worktree a hub-key change only prints a note: rerun `make capacity` in the primary clone                       |
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

1. **Use HTTP for all development tests** - Local development uses HTTP by default (`http://127.0.0.1:8659`; primary clone, in a worktree use the web URL from `make stack-info`), not HTTPS
2. **Run all tests in Docker, never on host** - Always use the Docker containers for backend/integration/UI tests. The one exception is `make test-js` (vitest JS/unit tests), which runs host-native like CI and `make typecheck`, and needs no stack
3. **Debug UI test failures with Playwright before changing code** - When a UI test fails and the root cause isn't clear from code inspection, use Playwright MCP to manually reproduce the issue and observe actual behavior BEFORE making code changes
4. **All test failures and errors are legitimate** - When running tests sequentially marker by marker, every failure or error (`playwright.sync_api.Error` (e.g. a `chromium.connect()` failure against the shared browser-server), `playwright.sync_api.TimeoutError`, 300+ second setup timeouts, assertion errors) must be recorded and investigated. There is no such thing as "browser connection exhaustion" as a dismissible category — if browser connections are dying, it indicates a real bug (e.g., a fixture not tearing down properly, a test hanging). Always record and investigate.
5. **Check Playwright browser-server health when connections repeatedly fail** - `playwright` lives in the per-user **hub** (`docker/compose.hub.yaml`), not in this checkout's spoke. `make playwright-up` starts it and waits until it is healthy (idempotent; restarts an idle-reaped container in place), and `make up p=ui`/`p=full`, `test-functional`/`test-ui-parallel`, the `*-built` targets, `test-marker*` with a `*_ui` marker and `test-file*` on a path that collects `tests/functional` run it for you; a bare `make up d=1` and `test-last-failed` do not.
   - **An `Exited (0)` hub playwright is normal**: it self-exits after `U4I_PLAYWRIGHT_IDLE_MINUTES` (default 15) with no client, and the next UI target restarts it. See it with `make stack-info` (`hub playwright: <status>`) or `docker ps -a --filter label=com.docker.compose.project=u4i-hub-$(id -u) --filter label=com.docker.compose.service=playwright` (`-a`, or a reaped container is invisible). A hung (not killed) pytest keeps its connection open, so the server is never reaped under it.
   - **Connect retry**: `build_page_browser` retries `chromium.connect` 3 times (15 s timeout each, 1 s / 2 s backoff, ≤ ~48 s total) for transient failures. `web` has no Docker access, so it cannot revive a reaped server: a final `RuntimeError` naming `make playwright-up` means run that, then rerun the tests. Residual window: a container at the very end of its idle window can be reaped just after `playwright-up` returns (≤ one watchdog poll, 30 s).
   - If `chromium.connect()` failures persist across test runs after `make playwright-up`, and only when no UI test run is in progress **in any spoke**, restart it with `make hub-restart c=playwright` (the one container serves every UI worker of every spoke, so a restart kills all in-flight workers; it does not wait for health; `make restart c=playwright` is refused, since `restart` is spoke-only). Pick up an image or compose-config change with `make playwright-rebuild`, not `hub-restart`. Still record and investigate the root cause. A `RuntimeError: PLAYWRIGHT_WS_URL env var is not set ...` (raised by `build_page_browser` in `tests/functional/conftest.py`) means the `web` service env is misconfigured (see `docker/compose.local.yaml`), not an unhealthy browser-server, so a restart won't fix it.
6. **`playwright.sync_api.TimeoutError` in UI tests always requires investigation** - never pre-existing or dismissible as "flaky" (see central Test Failures policy). Indicates either a UI logic bug or a genuine timing/stability issue.
7. **Prefer parallel make targets** - Use `make test-marker-parallel m=<marker>` (default `n` = derived `U4I_N_INT`, or `U4I_N_UI` for a `*_ui` marker) or `make test-ui-parallel` (UI, default `n` = derived `U4I_N_UI`) by default. Sequential targets are fallbacks only. "Parallel" means `-n` workers within a single invocation.
   - **Concurrent runs are isolated; concurrency is bounded by the host token budget.** Each run gets its own `testrun_uid`-keyed DBs and leased Redis indices. Budget = `U4I_N_MAX` tokens per user, shared by all checkouts (lock dir `U4I_TOKEN_DIR`): `-n k` holds `k`, a sequential run holds 1, the 3 Docker E2E harnesses hold 1 each. A run that doesn't fit queues, printing `token budget: waiting …` then a heartbeat every 30s: not hung. Ctrl-C while queued exits 130 and releases its tokens; an `n=` above the budget is refused, not queued. `args=`/`f=` on `test-file*` must not set `-n`/`--numprocesses` (refused at parse time: `args and f must not set -n/--numprocesses …`); combined short flags like `-vn4` are not detected, so never pass a worker count through `args=`/`f=` (use `n=`). A SIGKILLed runner's tokens are freed by the kernel, but its in-container pytest can keep running outside the budget until it finishes or `web` restarts; `make reset-test-dbs` reclaims its DBs/leases only after it exits. Mechanics: ARCHITECTURE.md → Testing, "Host token budget".
   - **Each start is also gated on live memory** (`/proc/meminfo`; on macOS the Colima VM's via the hub `db`; else static capacity, noted once). With no `n=`, a parallel run **shrinks to the workers that fit now**; an explicit `n=` is exact and waits (a default or sequential run also waits if not even one worker fits): `token budget: waiting for memory — need <X> GB for <m> workers, <Y> GB usable (<source>); runs holding tokens: …` (30s heartbeat). While other runs hold tokens it waits indefinitely; with none (outside pressure) it exits 1 after `U4I_MEMORY_WAIT` (600s) with `gave up … waiting for memory`: free memory or lower `n=`. Usable memory under 1 GB mid-run prints one `host memory low during <target>` warning (never kills the run).
   - **Concurrent spokes share one test-role connection limit.** Every spoke's runs connect as the same test role on the one hub cluster, and its `CONNECTION LIMIT` (`U4I_PG_TEST_CONN_LIMIT`) is sized for `U4I_N_MAX` workers. The token budget keeps the total workers across all concurrent runs ≤ `U4I_N_MAX`, so concurrent budgeted `make` runs no longer hit `FATAL: too many connections for role` (exceptions: an orphaned in-container pytest after its runner is killed, combined short flags in `args=`/`f=`, raw pytest outside `make`). **Two ceilings in a worktree:** `_require-n-fits` validates an explicit `n=` against **this checkout's own** capacity file, while the token budget reads `U4I_N_MAX` from **the primary clone's** file. A worktree whose sticky override raises its own ceiling above the primary's can pass `_require-n-fits` locally, then queue or be refused by the budget at the primary's lower number. This fails safe (the stricter ceiling wins), and the refusal names the primary file, so the divergence is never silent; change the effective budget with `make capacity` in the primary clone. The live memory gate reads no file, so it is the same in every checkout.
   - **Parallelism caps are derived per host (every suite, not just UI)** — `make capacity` sets the default worker counts (`U4I_N_UI` for UI targets, plus `test-marker-parallel*` with a `*_ui` marker and `test-file-parallel*` on a path that collects `tests/functional`, the whole tree included; `U4I_N_INT` for the other integration/marker/file runs; an explicit `n=` always wins) from the host's cores and memory, and sizes the interlocks to the larger of the two: the metrics lease pool (`redis-metrics --databases`) and the `db` cluster's connection limits. An explicit `n=` above this host's `U4I_N_MAX` is refused by `_require-n-fits` before pytest starts. To go higher, run `make capacity U4I_N_UI=<n>` (UI runs) or `make capacity U4I_N_INT=<n>` (other integration/marker/file runs), then `make up [p=…] d=1` (the same `p` the stack was started with) to apply the spoke interlock (the `redis-metrics` pool) and `U4I_PG_TEST_CONN_LIMIT` (re-applied by the hub's `cluster-init`). `U4I_PG_MAX_CONN` / `U4I_PG_SHARED_BUFFERS_MB` are hub interlocks (`hub recreate required`): `make down` in every spoke, then `make hub-down` + `make hub-up`. The hub reads only the **primary clone's** capacity file, so hub keys change only when `make capacity` runs there (a linked worktree prints a note instead); see the Configuration surface table. Overrides above the memory guard are refused, and n ≤ 30 is a hard per-run ceiling (the shared `redis` has `--databases 64`, leaving 62 leasable session indices: room for 2 concurrent runs at n = 30). A `RuntimeError: Redis lease pool '…' is exhausted` means every index is held, usually by leases a killed run leaked: run `make reset-test-dbs`, lower `n`, or run `make capacity` then `make up [p=…] d=1` to grow the pool. CI does not use `make capacity`; its `test.yml` matrix pins `XDIST_N`. Soft, secondary limit: host CPU/RAM load during concurrent startup. Each UI worker has its own Flask server and Postgres DB, plus its own `chromium.connect()` browser on the **one shared** Playwright browser-server container. The memory guard budgets for that, but heavy load can still slow setup.
   - **A failing run prints the capacity it ran under.** On a non-zero exit (other than 130), the token runner prints a `token budget: <target> exited <rc> — resolved capacity for this run:` block to stderr: tokens held of the budget, seconds queued and the other holders at start, `at ceiling: yes|no` (tokens in use including this run == budget), a `memory:` line (usable at start, lowest during the run, source), and the capacity file's `decision:` line. A lowest reading under 1 GB adds a hint that failures may be memory pressure. `at ceiling: yes` together with timeouts or spurious login failures means **rerun with a lower `n=` before debugging product code**: it is often capacity, not a product bug.
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

**Which `requirements/*.txt` file:** they nest dev ⊃ test ⊃ prod (`-r`), and each environment installs only its own file.

| File | Put a package here when… | Installed by |
|---|---|---|
| `requirements-prod.txt` | the app imports it at runtime (`backend/`, `migrations/`, runtime `scripts/`) | prod image (`docker/Dockerfile`) |
| `requirements-test.txt` | only `tests/`/conftest import it | **CI** (`test.yml`, `types-staleness.yml`, `event-coverage-staleness.yml`) |
| `requirements-dev.txt` | nothing imports it — local tooling only (`pre-commit` and its deps) | local `web` image (`docker/Dockerfile.Local`) |

The local container installs dev, so a misplaced pin passes every local test and only fails in CI, where it breaks collection for every pytest job at once. Before committing a new import, confirm the file CI installs has it. The workflow image pins its own venv in `docker/Dockerfile.Workflow` (versions match prod), so a new workflow dependency goes there too.

Security pins go in `frontend/pnpm-workspace.yaml` `overrides:` at the exact patched version. If one conflicts with a transitive consumer's peer-dep range, use `pnpm why <pkg>` to find the resolved version and pin the override to that **exact patch** rather than reverting to a caret. A pinned version younger than 90 days (`minimumReleaseAge`) also needs an exact `name@version` entry in `minimumReleaseAgeExclude` (no wildcards), or every install fails. Document the choice in the commit body.

pnpm is the only package manager: never run `npm install` in `frontend/`; `make lint` fails via `lockfile-check` if a `package-lock.json` appears. `verifyDepsBeforeRun: error` means pnpm never auto-installs, so after a `package.json`/lockfile change run `make tools` (host) and `make build` (containers; it rebuilds every profile's image, including the inactive `vite`/`workflow` ones). `make up`/`up-built`/`tunnel` pass `-V` so stale anonymous `node_modules` volumes are renewed.

When adding or bumping a dependency, never introduce a range — if you only need a security fix, pin to the exact patched version listed by `gh api .../dependabot/alerts`. After editing, run `make build` (every profile's image) then `make up [p=…] d=1` (the same `p` your stack was running), and verify the full test suite passes before committing: `make test-integration-parallel`, `make test-js`, and the UI suite via `make test-ui-parallel-built` (which brings up the built `ui`-profile stack itself).

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

- **Source matters:** the image must be of the **implemented** feature captured via Playwright MCP against the running app (`http://127.0.0.1:8659/`; primary clone, in a worktree use the web URL from `make stack-info`), NOT the upfront design mock. The stack must serve assets (`make up p=ui d=1` or `make up-built d=1`; see Playwright below). Reusing a pre-implementation mock does not satisfy this rule.
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
| `make setup` | One-time per clone/worktree onboarding: `worktree-init` + `tools` + `hooks` + `capacity` (idempotent; a capacity failure, e.g. Docker down, is deferred — rerun `make capacity` to see the error) |
| `make capacity [U4I_N_UI=<n\|auto>] [U4I_N_INT=<n\|auto>] [U4I_MEM_FRACTION=<f\|auto>]` | Derive test worker counts + interlocks for this host into `docker/.capacity.generated.env` (overrides are sticky; `=auto` clears), then prints a `live:` line (usable memory now, its source, workers that fit) |
| `make tools` | Install the pinned host toolchain + `frontend/node_modules` (run by `make setup`; re-run after pin bumps) |
| `make hooks` | Install the pre-commit git hook in the main checkout (run by `make setup`; safe from any worktree — see "Pre-commit hooks" below) |
| `make hooks-check` | Report whether the pre-commit hook is installed (exits 1 when missing; worktree-safe) |
| `make up [p=ui\|full] d=1` | Start the hub, then build and start this spoke's web + datastores (detached); `p=ui` adds vite and starts hub playwright, `p=full` also adds workflow. A narrower `p` stops the spoke services it no longer enables. Refuses a new spoke when live memory can't hold it idle plus a minimum test run, printing the numbers and the running spokes (`make down` one first; no live reading → the `U4I_SPOKE_MAX` count); a running spoke is always re-admitted |
| `make up-built [p=full] d=1` | Start the hub, then build and start with pre-built Vite assets (detached): web + datastores + vite one-shot build, waiting for the build and a healthy web, then start hub playwright; `p=full` also adds workflow |
| `make down` | Stop this spoke (every profile); the hub keeps running |
| `make build` | Rebuild this spoke's images without starting (every profile) |
| `make restart c=<service>` | Restart a **spoke** service (`c=` is required; reaches profiled services too; hub services are refused) |
| `make logs c=<service>` | Show a spoke service's logs, dev or built stack (e.g. `c=cloudflared`; hub services are refused) |
| `make stack-info` | Print this checkout's spoke project, aliases, URLs, hub project, hub `db` and `playwright` state (`Exited (0)` = idle-reaped) and attached spokes |
| `make worktree-init` | Link `.env` and `secrets/` from the primary clone into this worktree (no-op in the primary; run by `setup`, `up`, `up-built`, `start-built`, `tunnel`) |
| `make hub-up` | Start the per-user hub `db` and run `cluster-init` (idempotent; every stack start runs it) |
| `make playwright-up` | Start the hub's shared Playwright browser server and wait until healthy; restarts an idle-reaped one in place (idempotent; run by `p=ui\|full`, the UI test targets, `*-built`, and `test-marker*` / `test-file*` for UI markers/paths) |
| `make playwright-rebuild` | Rebuild the hub Playwright image and force-recreate it (picks up `Dockerfile.Playwright` / compose / `U4I_PLAYWRIGHT_IDLE_MINUTES` changes); refuses while any UI client is connected, or when it cannot read or count the connections |
| `make hub-down` | Stop the hub and remove the shared network; refuses while any spoke is attached (`make down` in each first) |
| `make hub-restart c=db\|playwright` | Restart a hub service (no health wait): drops every spoke's connections / in-flight runs, so only when no test run is in progress in any spoke. Image changes: `make playwright-rebuild` |
| `make test-integration-parallel [n=<N>]` | All non-UI integration tests in parallel (**preferred**; default `n` = derived `U4I_N_INT`). Every `test-*` target that runs pytest in `web` (not `test-host-static`), and the Docker E2E harnesses, queues on the host token budget (`U4I_N_MAX` tokens in `U4I_TOKEN_DIR`; `-n k` holds `k`, sequential holds 1) |
| `make test-integration` | All non-UI integration tests (sequential fallback) |
| `make test-ui-parallel [n=<N>]` | All UI/Playwright tests in parallel (**preferred**; default `n` = derived `U4I_N_UI`; starts vite + playwright itself) |
| `make test-functional` | All UI/Playwright functional tests (sequential fallback; starts vite + playwright itself) |
| `make test-js` | All JS unit tests (vitest, host-native — no stack needed) |
| `make test-marker-parallel m=<marker> [n=<N>]` | Tests for a specific marker in parallel (**preferred**; default `n` = derived `U4I_N_INT`, or `U4I_N_UI` for a `*_ui` marker, which also runs `playwright-up`) |
| `make test-marker m=<marker>` | Tests for a specific marker (sequential fallback) |
| `make test-file f=<path> [args=...]` | Single test file/path (a path that collects `tests/functional` runs `playwright-up`) |
| `make test-file-parallel f=<path> [n=<N>] [args=...]` | Test file/path in parallel (default `n` = derived `U4I_N_UI` for a path that collects `tests/functional`, the whole tree included, else `U4I_N_INT`) |
| `make test-host-static [f=<paths>] [args=...]` | Host-only static tests (Makefile dry runs, compose YAML, playwright entrypoint; they skip inside `web`) in the primary clone's `venv/`; installs the test + prod pins on first use and again whenever `requirements-test.txt` / `requirements-prod.txt` is newer than the venv stamp |
| `make test-playwright-lifecycle` | Build the derived Playwright image and run its idle-reap / restart E2E harness in throwaway containers (~7 min) |
| `make vite-build` | Vite build verification |
| `make addmock` | Seed dev DB with all mock data |
| `make generate-types` | Regenerate TypeScript API types from OpenAPI spec + per-event dim shapes (metrics-dimensions.d.ts, metrics-dim-values.ts, metrics-events.ts) |
| `make help` | List all available make commands |

### Metrics Verification (local stack)

Bring the stack up with `make up p=full d=1` to exercise the anonymous-metrics pipeline end-to-end: the flush/gauge `workflow` container is only in the `full` profile, and `metrics-flush-now`/`gauge-sample-now`/`notify-test` refuse to run (`workflow is not running — start it with: make up p=full d=1`) without it. Metrics are **on by default locally**: `docker/compose.local.yaml` declares the tracked default `METRICS_ENABLED=${METRICS_ENABLED:-true}`, so every `make up` enables them on every host (the web app still records into Redis on the default stack; only the flush to Postgres needs `p=full`) — **never prefix `METRICS_ENABLED=true` on local commands**. To opt a machine out (or exercise the disabled path), put `METRICS_ENABLED=false` in `.env`, which `make` passes via `--env-file .env`. **Remove any lingering `export METRICS_ENABLED=…` from your shell profile:** compose interpolation resolves the shell environment before `--env-file`, so a leftover export silently overrides the `.env` opt-out (check with `printenv METRICS_ENABLED`). Tests are unaffected (`ConfigTest.METRICS_ENABLED = False`). Prod (`docker/compose.yaml`) and dev (`docker/compose.dev.yaml`) both hard-set `METRICS_ENABLED=true`.

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

**CRITICAL:** Never run `make up` or `make up-built` without `d=1`. Without the detached flag, these commands stream Docker logs to stdout indefinitely and never exit. Always use `make up [p=ui|full] d=1` (or `make up-built [p=full] d=1`). With `d=1`, `make up` returns once the containers are started; `up-built d=1`, `start-built` and `tunnel` also wait for the vite build and a healthy `web` (see "Running the App"). Before starting containers, check what is already running with `make stack-info` (this checkout's project names, cached ports/URLs, hub `db` and `playwright` state and attached spokes). This spoke's container/health state is `docker ps --filter label=com.docker.compose.project=<project from stack-info>`; poll it until healthy.

**Local Postgres:** one `db` cluster in the per-user hub (`u4i-hub-<uid>`) holds every spoke's dev DB (`U4I_DEV_DB`, provisioned by each spoke's one-shot `db-init`) and every per-run test DB. The hub's one-shot `cluster-init` owns the cluster-wide objects (the test role and the base test DB). It runs `fsync=off`, so a host crash may corrupt `pgdata`. Recovery **deletes all dev data in every spoke**: `make down` in every spoke, `make hub-down`, `docker volume rm u4i-hub-$(id -u)_pgdata`, `make up d=1`, then `make reset-db` to reseed (in each spoke you use).

### Running the App (Docker - recommended)

**Hub and spokes.** Each checkout (the primary clone or any git worktree) runs its own compose project, a "spoke" named `u4i-<slug>` from `docker/compose.local.yaml`. Every spoke shares one per-user "hub" (`u4i-hub-<uid>`, `docker/compose.hub.yaml`): the Postgres `db`, its one-shot `cluster-init`, and the Playwright browser server, on the external network `u4i-shared-<uid>`. `setup`, `up`, `up-built`, `start-built` and `tunnel` run `worktree-init` (links `.env`/`secrets/` in a worktree); every stack start resolves this spoke's host ports and brings up the hub first; `make down` stops only this spoke, and `make hub-down` (refused while any spoke is attached) stops the hub. A new worktree needs only `make setup` (or just `make up d=1`). Its folder name must be unique among checkouts on the host, since the project and dev DB names derive from it. **Spoke admission:** every spoke start runs `_admit-spoke` (`capacity.py admit`), refusing when live usable memory can't hold one more idle spoke plus a minimum test run (plus the hub's idle cost if it is down): `spoke admission: refusing spoke <N+1> (<project>) — needs … GB, but only … GB is usable now (<source>). Running spokes: …`. Running spokes are already out of the reading, so none is counted twice. With no live reading it falls back to refusing spoke N+1 past `U4I_SPOKE_MAX` (its `… exceeds usable …` message). An already-running spoke is always re-admitted. `(clamped)` on the capacity file's `# decision:` line means the ceiling floored to 1; details in ARCHITECTURE.md → Docker.

Compose profiles pick the optional spoke services layered on the always-on core (`web`, `db-init`, `redis`, `redis-metrics`, plus the hub `db`):

```bash
make up d=1          # hub db + web + datastores only — enough for integration tests, generate-types, vite-build
make up p=ui d=1     # + vite (hot reload), and starts the hub playwright — needed to browse the dev app with styled pages
make up p=full d=1   # + workflow (metrics flush / gauge sampler / backups cron)
# never omit d=1 — see the CRITICAL note above. A narrower p stops services the previous p started (never hub playwright).

# Primary clone: Flask at http://localhost:8659, Vite at http://localhost:5173 (only with p=ui / p=full).
# A worktree gets its own ports; `make stack-info` prints this checkout's URLs.
# SSL is disabled by default. To enable HTTPS in local development:
# Set ENABLE_SSL=true and VITE_URL=https://localhost:${U4I_VITE_PORT:-5173} in docker/compose.local.yaml
```

**Built mode** (`make up-built`, `start-built`, `tunnel`) runs vite as a one-shot `vite build` that exits when done. Nothing can `depends_on` it, so `up-built d=1`, `start-built` and `tunnel` start the stack detached, then `docker wait` on the vite build container (failing if it exited non-zero; see `make logs c=vite`), then `up --wait web`. Attached `make up-built` (no `d=1`) streams logs instead and has no such wait.

**Host identity:** the local web image's `u4i-host` user is built with this host's `HOST_UID`/`HOST_GID` (from `make capacity`; build args in `docker/compose.local.yaml`, image default 1001), so files it writes into bind mounts are owned by you. The `vite` container runs as the same `HOST_UID:HOST_GID` (compose `user:` plus build args; its image re-owns `/app`), so `backend/static/dist` from `vite build` (built mode, `make vite-build`) is yours too and `git worktree remove` never hits `Permission denied`. A `dist` left root-owned by an older vite image makes the build fail (`EACCES`, see `make logs c=vite`); remove it once with `docker run --rm -v "$PWD/backend/static:/s" alpine:3 rm -rf /s/dist`. An `app_logs` volume created by an older image, or re-owned by a previous workflow start, can leave `/app/volume/logs` owned by another uid, and web would crash on its log file. `make up`/`up-built`/`start-built`/`tunnel` repair that automatically through the private `_logs-owner-fix` prerequisite, which prints `repairing app_logs ownership (was X, now UID:GID)` once and is silent otherwise. The workflow container keeps write access through the log dir's group.

#### Playwright

Use the following URL to access the website with Playwright MCP: `http://127.0.0.1:8659/` (primary clone; in a worktree use the web URL from `make stack-info`). Each spoke has its own session cookie name (`<project>_session`), so logins in two spokes don't log each other out. The stack must be up with `make up p=ui d=1` or `make up-built d=1`; on the default `make up d=1` stack there is no vite, so pages render unstyled.

### Running the App (without Docker)

```bash
flask db upgrade
flask shorturls add
flask managedb create          # optional: populate test data
flask run --host=0.0.0.0 --port=5000
```

### Frontend (Vite)

```bash
make vite-build  # build to backend/static/dist/ (= pnpm run build) in a one-off vite container
make test-js     # run JS unit tests (vitest) on the host
```

`make vite-build` and `make generate-types` run vite in a one-off container (`run --rm --no-deps vite`), so they need no `p=` (`generate-types` still needs `web` up, which the default `make up d=1` provides). `make test-js` runs on the host and needs no stack at all (`test-js-built` is just an alias). The Testing targets below `exec` into the running local stack, so it must be up (`make up d=1`); on the built stack (`make up-built`) use the `-built` variants (`vite-build-built`, `test-file-parallel-built`).

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

**Prefer parallel make targets** (`test-marker-parallel`, `test-integration-parallel`, `test-ui-parallel`) over sequential ones. "Parallel" means `-n` workers within a single invocation. Concurrent invocations are isolated from each other, and the host token budget queues any run that would push total workers past `U4I_N_MAX` (see Testing Best Practices #7).

**Always minimize wall-clock time**: omit `n=` so each target uses this host's derived maximum (`U4I_N_UI` for UI, including a `*_ui` marker or `tests/functional` path; `U4I_N_INT` for other integration/marker/file runs; see the parallelism-cap note above and `make capacity`). Never default to `n=2` for "quick" or "smoke" runs — low parallelism on the full suite just means paying the full test cost at slower cadence, and can expose latent timing flakes (e.g., shared Playwright browser-server connection idle-timeouts) that never occur at production cadence. A true "smoke" test is scoped by marker (`m=splash_ui`) or test path, NOT lowered parallelism on the full suite.

UI/functional tests require the shared Playwright browser-server, which lives in the per-user hub and serves every spoke: the hub `playwright` service runs `playwright run-server --port 3000 --host 0.0.0.0` from the derived image `u4i-playwright:<version>` (`docker/Dockerfile.Playwright`: the CLI is baked in, so a start never touches the npm registry; its `ARG PLAYWRIGHT_VERSION` is unit-tested to match the `playwright==` pin in `requirements/requirements-test.txt`), each spoke's `web` sets `PLAYWRIGHT_WS_URL=ws://playwright:3000/` (the hub service name on `u4i-shared-<uid>`), and `build_page_browser` in `tests/functional/conftest.py` calls `chromium.connect(config.TEST_PLAYWRIGHT_URI)` in Docker (falling back to `chromium.launch()` outside it). The hub browser reaches a spoke by its slugged aliases (`web-<slug>` via `U4I_WEB_HOST` → `UI_TEST_STRINGS.DOCKER_BASE_URL`, `vite-<slug>` via `VITE_INTERNAL_HOST`), since bare `web`/`vite` would be ambiguous across spokes. Playwright no longer `depends_on` web or vite (cross-project dependencies are impossible), so make targets order the start instead: `make test-functional`/`make test-ui-parallel` run `playwright-up`, then `up -d --wait web vite`; the `*-built` targets start them via `start-built`, which runs `playwright-up` **last** (after a healthy `web`) so a long rebuild can't eat the idle window before pytest connects (`up-built d=1` does the same).

Lifecycle: the entrypoint (`docker/playwright-entrypoint.sh`) supervises the server and exits 0 after `U4I_PLAYWRIGHT_IDLE_MINUTES` (default 15) with no non-loopback client, freeing ~500 MB. The service has a node TCP healthcheck (loopback, so it never counts as a client) and no restart policy. Its logs hold only a startup line (`playwright-entrypoint: serving :3000, reaping after 15m idle`, or `serving :3000, reaping disabled` with `IDLE_MINUTES=0`) and a reap line (`idle 15m with no clients — exiting`). `make playwright-up` restarts a reaped container in place (same container, no registry fetch) and waits for health; it never picks up an image/config change, which needs `make playwright-rebuild`. In dev mode, `make test-marker*` with a `*_ui` marker and `make test-file*` on a path that collects `tests/functional` (the whole tree included) run `playwright-up` themselves (and their `-parallel` / `-parallel-built` variants default `-n` to `U4I_N_UI`; an explicit `n=` wins), but still need `make up p=ui d=1` for web + vite. The `%_ui` word match ignores marker-expression semantics, so `m='not admin_ui'` also starts playwright and uses the UI cap: harmless (an extra start, fewer workers). `make test-last-failed` does not start it: run `make playwright-up` first if the last failures include UI tests. `make test-playwright-lifecycle` proves the image's reap/restart behavior in throwaway containers.

### Linting & Formatting

One definition per check, run host-native. The pre-commit hook and CI call the same targets:

```bash
make setup          # once per clone/worktree: .env/secrets links + tools + hooks + capacity (idempotent)
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
  mask**; recreate the container afterwards with `make down` then `make up p=ui d=1` (a fresh
  container gets fresh anonymous volumes; `make restart c=vite` keeps the old container and its
  detached mask) before `make tools` / `make test-js`.

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
