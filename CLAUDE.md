# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. 

Keep your replies extremely concise and focus on conveying the key information. No unnecessary fluff, no long code snippets.

Plans, reviews and research live in the central store under `~/code/plans/urls4irl/{open,completed}/<topic>/` (see `Plans store (central)` below) - reference the relevant plan there if one exists.


## Claude Config

<!-- Consumed by the stronghold's central generic skills (see ~/code/CLAUDE.md).
     Stable keys — do not rename. Account-specific GraphQL IDs are intentionally NOT inlined here
     (secrets policy); the genericized workflow resolves them at runtime by name — see the
     GitHub project board key below. -->

The keys Plans store, Bot identity, Bot push script, Token generator, GitHub project board, Issue labels, PR reviewer, Plans bucket, Push gate and Stack are optional maintainer tooling, consumed only by the stronghold's central skills; the repo is fully usable without them. Commands, Container runtime and Configuration surface are repo docs.

- **Repo slug:** `4IRL/urls4irl`  (always pass `--repo 4IRL/urls4irl` to `gh`; `GPropersi/urls4irl` redirects but is not canonical)
- **Default branch:** `main`
- **Stack:** `flask-jinja-vanillajs-vite` (drives which opt-in plan-creator/plan-reviewer protocol reference files load — Python/Flask backend, SQLAlchemy, Jinja templates, vanilla-JS→Vite/ES6 frontend, Vitest + Playwright tests, pip/`requirements-*.txt` pinning)
- **Plans store (central):** `~/code/plans/urls4irl/{open,completed,research}/<topic>/` — plans now live in the central stronghold store, not this repo (bucket = the `Plans bucket` key below, `urls4irl`). Reviews/research/mocks are co-located per plan under its `<topic>/`; finished topics move `open/`→`completed/` as a unit. See `~/code/CLAUDE.md` "Central Plans Store". (Legacy in-repo `plans/` migrated 07-2026; the leftover `plans/tmp/` is gitignored scratch.)
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
  | UI tests | `make test-ui-parallel-built` (`n` defaults to the derived `U4I_N_UI`; see `docs/development.md` → "Configuration surface") |
  | JS/unit tests | `make test-js` (host-native vitest — no stack needed) |
  | Affected tests (diff-scoped) | `make test-affected` (agent tier: `make test-agent`; preview: `make affected-markers`) |
  | Build | `make vite-build` |
  | Lint / format | `make lint` · `make format-check` · `make typecheck` (fix: `make format`); onboard a clone/worktree with `make setup` (worktree-init `.env`/secrets links + toolchain + hook + capacity). The pre-commit hook runs these automatically **only if the hook is installed** (`make setup`, or `make hooks` alone; check with `make hooks-check`) |
  | Regenerate types | `make generate-types` |
  | Regenerate endpoint registry | `make generate-endpoints` (check: `make audit-endpoints`) |
  | Inspect UI failures | `make test-artifacts` (latest run's failure index + evidence paths; `run=<id>` for an older run) |
  | New worktree | `make worktree-new name=<slug> [b=<branch>] [from=<ref>]` |
  | Remove worktree | `make worktree-rm` (run inside the worktree) |
- **Configuration surface:** every local knob, by tier, lives in `docs/development.md` → "Configuration surface". A spoke's compose reads `--env-file .env`, then `docker/.capacity.generated.env`, then `docker/.ports.generated.env`; shell env beats all three. The hub's compose always reads the **primary clone's** `.env` and capacity file, whichever checkout runs it. Use `make` targets: raw compose lacks the computed names and files.
- **GitHub project board:** `URLS4IRL -> Real Life` (org project). Its project / status-field / option / bot-node GraphQL IDs are **resolved at runtime by name** via `gh api graphql` (from this board name + the `Bot identity` login) — never inlined here, per the secrets policy. Maintainer workflow (requires the stronghold's `/git-push`; optional for other contributors): the genericized `/git-push` performs the lookup; `~/code/.claude/skills/git-push/SKILL.md` (stronghold-owned) documents the mutations.
- **Issue labels:** the repo's existing set — resolve at runtime via `gh label list --repo 4IRL/urls4irl` (do not invent labels)
- **PR reviewer:** `GPropersi`
- **Worktree policy:** `full`
- **Worktree link:** `.env secrets`
- **Worktree setup:** `setup`
- **Worktree teardown:** `n/a` <!-- informational; the owned worktree-rm target does the teardown (down -v --rmi local, dev DB drop, git worktree remove) -->
- **Worktree ports:** `U4I_WEB_PORT=8659,U4I_VITE_PORT=5173` <!-- informational: primary bases; scripts/spoke_ports.py (repo-local, not the stronghold's resolver) owns the per-worktree values -->
- **Worktree allowed targets:** `n/a`
- **Worktree guarded targets:** `n/a`
- **Plans bucket:** `urls4irl`   <!-- directory under ~/code/plans/ for this repo's plans; explicit, never inferred from the slug or the directory name -->
- **Push gate:** (suites a push must pass; first matching row wins per changed path, all matched suites run sequentially)
  | Paths (space-separated globs) | Command |
  | ----------------------------- | ------- |
  | `docs/** **/*.md LICENSE .claude/** .gitignore .gitmodules .git-blame-ignore-revs .env.example .dockerignore` | na docs, markdown and repo-metadata paths run no suite |
  | `frontend/**` | `make test-js && make test-ui-parallel-built` |
  | `**` | `make test-integration-parallel && make test-ui-parallel-built` |


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

Review files are stored **co-located with each plan** in the central store at `~/code/plans/urls4irl/{open,completed}/<topic>/reviews/<plan-name>-review.md`, not in this repo. (An earlier version of this note claimed a repo-root `reviews/`; that was inaccurate and there is no repo-root `reviews/` directory.)

### Endpoint Registry

The endpoint registry is **generated** at `docs/endpoints/` (`endpoint-registry.json` is canonical; `ENDPOINT_REGISTRY.md` is rendered from it) by `make generate-endpoints`, and is never hand-edited — regenerate and commit `docs/endpoints/` after changing a route, its decorators, services, schemas, templates, or JS linkage.
Look up what touches a route with `make endpoint-info e=<endpoint | rule | 'METHOD /rule'>` (host-native, no stack needed).
The registry also feeds `make test-affected`: it maps a changed handler, service, schema or template to every blueprint that uses it (e.g. a `backend/urls/services/` change also selects `mobile_api`). A stale registry therefore under-selects, so `make affected-markers` warns when a route file changes without `docs/endpoints/endpoint-registry.json` changing too.
CI's `Endpoint Registry Audit` job (`make audit-endpoints` locally) fails on registry drift, or on an `@api_route` with no JS linkage in `backend/utils/all_routes.py` — it needs one of: a `JS_ROUTES`/`ADMIN_JS_ROUTES` key, a template `url_for`, an `INDIRECT_JS_ENDPOINTS` entry (the frontend calls it via a URL it gets indirectly — the page's own URL or a server-built one), or a `NO_JS_ENDPOINTS` reason (genuinely no web-JS caller). Never add a `NO_JS_ENDPOINTS` entry for an endpoint that has a JS caller.

### Metrics Coverage for New Endpoints

**Every new endpoint must be deliberately tied into the anonymous-metrics dashboard — never left untracked by default.** In the same PR as the route: (1) confirm the `API_HIT` middleware covers it (justify it if the route is in `_SKIP_ENDPOINTS`); (2) decide whether a DOMAIN `record_event(EventName.X, ...)` is warranted in the service layer, or say in the PR body that you deliberately rely on `API_HIT` only; (3) a new event needs full registry alignment (`EventName` + `EVENT_REGISTRY` + `DIMENSION_MODELS` + `EVENT_NAME_TO_RESOURCE`), then `make audit` (must exit 0) and `make generate-types` (stage `frontend/types/*`); (4) a new `Resource` category can flip existing negative dashboard/query tests, so rerun the metrics integration suites. Full checklist and the latency-metrics reference: `docs/development.md` → "Metrics coverage for new endpoints".

### GitHub Issue Linking

Maintainer workflow, automated by the stronghold's `/plan-creator`, `/master-plan-creator` and `/git-push` (plan frontmatter `github_issue:` / `github_issue_url:`; the PR body gets `Closes #<N>`; sub-plans of a master add `Part of #<umbrella>`). Always use `gh --repo 4IRL/urls4irl` (`GPropersi/urls4irl` redirects but is not canonical). Full flow: `docs/development.md` → "GitHub issue linking (maintainer workflow)".


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
3. Destructured object params for 2+ args or a bare boolean — enforced by `u4i/destructured-params`. Baselined legacy functions: when you touch one's signature, convert it and delete its key from `frontend/eslint-rules/destructured-params-baseline.json` (the rule flags stale keys).
4. **Established TS patterns** — use these existing patterns rather than inventing new ones:
   - **Type-guard dispatch** for field-level validation errors: `const FIELDS = [...] as const` + `isFieldName()` guard (see `splash/init.ts`, `tags/create.ts`)
   - **is429Handled(xhr)** guard at the top of every `.fail()` handler (`frontend/lib/ajax.ts`)
   - **Schema<>/SuccessResponse<>** type helpers from `frontend/types/api-helpers.d.ts` for typed AJAX
   - **offAndOnExact** jQuery plugin for rebinding listeners on repeatedly shown/hidden elements
   - **ajaxCall()** wrapper for all AJAX — never use `$.ajax` directly
   - **App store** (`frontend/store/app-store.ts`): `getState()`/`setState()` with `Object.assign` merges
   - **Event bus** (`frontend/lib/event-bus.ts`): typed `emit()`/`on()` with `AppEvents` enum — see ARCHITECTURE.md for full event reference
   - **Vitest mocks**: `vi.mock()` at top, `createMockJqXHRChainable()` from `frontend/__tests__/helpers/mock-jquery.ts`, `vi.importActual()` inside `it()` blocks only
5. **Runtime debug logging via `debug(namespace)`** — never call `console.*` directly in app code; enforced by ESLint `no-console` (rule in `frontend/eslint.config.js`; `lib/debug.ts` is the only whitelisted file). Use `import { debug } from "<path>/lib/debug.js"; const log = debug("subsystem"); log("event", data);`. The DevTools toggle, admin gating and the active namespace list: see `docs/development.md`.
6. Single-letter identifiers and type parameters are enforced by ESLint `id-length` + `@typescript-eslint/naming-convention` (`make lint`).


### Backend - Python/PostgreSQL/Redis

1. Use typehints! No shortcuts around this.
2. Quoted type hints (ruff UP037) and single-letter names (`scripts/check_identifier_names.py`) are enforced by `make lint`.

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
3. **Read the failure artifacts before reproducing** - Every failing UI test (setup or call phase) always writes a per-page screenshot + DOM, console/page errors and network to `tmp/test-artifacts/<run>/<test>/` (`failure.json` indexes them). Run `make test-artifacts` first and diagnose from that evidence. Playwright tracing is opt-in (it costs ~+30% UI-suite wall-clock): rerun the failing test with `U4I_UI_TRACE=retain-on-failure` to also get `trace.zip` (the knob is read when `web` is created, so use a `*-built` target, which recreates it, or restart the stack with it), then open it at trace.playwright.dev for the step-by-step timeline. CI uploads the same directory as the `ui-failure-artifacts-<marker>` artifact. Reproduce manually with Playwright MCP only when the artifacts leave the cause unclear. Layout and knobs: `docs/development.md` → "UI failure artifacts"
4. **All test failures and errors are legitimate** - When running tests sequentially marker by marker, every failure or error (`playwright.sync_api.Error` (e.g. a `chromium.connect()` failure against the shared browser-server), `playwright.sync_api.TimeoutError`, 300+ second setup timeouts, assertion errors) must be recorded and investigated. There is no such thing as "browser connection exhaustion" as a dismissible category — if browser connections are dying, it indicates a real bug (e.g., a fixture not tearing down properly, a test hanging). Always record and investigate.
5. **Check Playwright browser-server health when connections repeatedly fail** - `playwright` lives in the per-user hub, not this spoke. `make playwright-up` starts it and waits until healthy (idempotent; restarts an idle-reaped container); UI targets run it for you, a bare `make up d=1` and `test-last-failed` do not. An `Exited (0)` hub playwright is normal (it self-exits after `U4I_PLAYWRIGHT_IDLE_MINUTES`, default 15, with no client); a final `RuntimeError` naming `make playwright-up` means run that, then rerun. Only when `chromium.connect()` failures persist after that, and no UI run is in progress in any spoke, use `make hub-restart c=playwright` (it kills all in-flight workers of every spoke). `RuntimeError: PLAYWRIGHT_WS_URL env var is not set` is a `web` env misconfiguration (`docker/compose.local.yaml`), not an unhealthy browser-server. Still record and investigate the root cause. Details: `docs/development.md` → "Test infrastructure mechanics".
6. **`playwright.sync_api.TimeoutError` in UI tests always requires investigation** - never pre-existing or dismissible as "flaky" (see central Test Failures policy). Indicates either a UI logic bug or a genuine timing/stability issue.
7. **Prefer parallel make targets** - Use `make test-marker-parallel m=<marker>` or `make test-ui-parallel` by default; sequential targets are fallbacks only. "Parallel" means `-n` workers within a single invocation. Omit `n=` so the host-derived maximum is used (`make capacity` sets it). Runs queue behind a per-user token budget and a live-memory gate: `token budget: waiting …` is a queue, not a hang, and Ctrl-C exits 130. Never pass `-n`/`--numprocesses` through `args=`/`f=` (use `n=`). A failing run prints its resolved capacity: `at ceiling: yes` together with timeouts or spurious login failures means rerun with a lower `n=` before debugging product code. Mechanics (token budget, memory gate, connection limits, lease pools, capacity overrides): `docs/development.md` → "Test infrastructure mechanics".
8. **Reclaim leaked test resources** - An interrupted run leaves its per-run databases and Redis leases behind. `make reset-test-dbs` (`ttl=<minutes>`, default 10) drops idle, aged per-run test DBs and deletes the leases orphaned with them; it never drops a connected DB, never touches the dev DB, and never flushes Redis DB 0.

Flaky-test hardening and the never-dismiss-without-investigation protocol are covered centrally (see `~/code/CLAUDE.md` → Test Failures: Investigate, Don't Dismiss); the derived caps above are capacity limits, not flake thresholds. At or below them, flaky tests must be hardened to pass at the suite's normal (derived) parallelism.

### Code Style

This project is primarily Python with some JavaScript/HTML/CSS. When editing Python code, verify constant names, decorator types (`@model_validator` vs `@field_validator`), and imports against the actual codebase before making changes.

### Dependency Pinning

(see central Dependency Pinning rule for the general policy.) Exact pins everywhere — enforced by `make audit-pins` (manifests, Dockerfile `FROM`, compose `image:`, `pip install`, workflow `uses:`).

**Which `requirements/*.txt` file:** they nest dev ⊃ test ⊃ prod (`-r`), and each environment installs only its own file.

| File | Put a package here when… | Installed by |
|---|---|---|
| `requirements-prod.txt` | the app imports it at runtime (`backend/`, `migrations/`, runtime `scripts/`) | prod image (`docker/Dockerfile`) |
| `requirements-test.txt` | only `tests/`/conftest import it | **CI** (`test.yml`, `types-staleness.yml`, `event-coverage-staleness.yml`, `registry-staleness.yml`, `playwright-cache-warm.yml`) |
| `requirements-dev.txt` | nothing imports it — local tooling only (`pre-commit` and its deps) | local `web` image (`docker/Dockerfile.Local`) |

The local container installs dev, so a misplaced pin passes every local test and only fails in CI, where it breaks collection for every pytest job at once. Before committing a new import, confirm the file CI installs has it. The workflow image pins its own venv in `docker/Dockerfile.Workflow` (versions match prod), so a new workflow dependency goes there too.

Security pins go in `frontend/pnpm-workspace.yaml` `overrides:` at the exact patched version. If one conflicts with a transitive consumer's peer-dep range, use `pnpm why <pkg>` to find the resolved version and pin the override to that **exact patch** rather than reverting to a caret. A pinned version younger than 90 days (`minimumReleaseAge`) also needs an exact `name@version` entry in `minimumReleaseAgeExclude` (no wildcards), or every install fails. Document the choice in the commit body.

pnpm is the only package manager: never run `npm install` in `frontend/`; `make lint` fails via `lockfile-check` if a `package-lock.json` appears. `verifyDepsBeforeRun: error` means pnpm never auto-installs, so after a `package.json`/lockfile change run `make tools` (host) and `make build` (containers; it rebuilds every profile's image, including the inactive `vite`/`workflow` ones). `make up`/`up-built`/`tunnel` pass `-V` so stale anonymous `node_modules` volumes are renewed.

When adding or bumping a dependency, never introduce a range — if you only need a security fix, pin to the exact patched version listed by `gh api .../dependabot/alerts`. After editing, run `make build` (every profile's image) then `make up [p=…] d=1` (the same `p` your stack was running), and verify the full test suite passes before committing: `make test-integration-parallel`, `make test-js`, and the UI suite via `make test-ui-parallel-built` (which brings up the built `ui`-profile stack itself).

### Import Style

**Exception to the central top-level-imports-only rule — `vi.importActual()` inside vitest `it(...)` blocks**: vitest's `vi.mock()` hoisting runs before module-level code, so `vi.importActual()` calls used for partial mocking cannot be moved to module scope. Local usage inside `it(...)` closures is permitted for this specific pattern only.

### General

Tool-use rules, enforced by hooks that block a violation with the reason: write files with the `Write` tool, never `cat >`/heredocs/`tee`/`printf >`; no inline `python3 -c` with braces (write a script file and run it); no Bash brace expansion (`{a,b}`); never join commands with `&&`, `||` or `;` (pipes and `$(...)` are fine; extend `EXEMPT_PATTERNS` in `block-compound-commands.sh`, not the rule, if a legitimate chained pattern recurs).

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
- Surface the image to the user with `SendUserFile` (not just a saved path). Save screenshots under the gitignored `plans/tmp/` scratch (or the plan's `screenshots/` folder in the central store `~/code/plans/urls4irl/open/<topic>/`, which is gitignored in the stronghold).
- If the app cannot be brought up to capture the screenshot, say so explicitly rather than silently skipping this step.
- **Design mocks and screenshots must NEVER be checked into source control.** Keep them under gitignored paths only (`plans/tmp/` here, or the central store `~/code/plans/urls4irl/...`). Before committing, confirm no image artifact landed in a tracked location (e.g. project root, `backend/static/`); if one did, move it to a gitignored path rather than committing it.

## Generated Types Freshness

After any backend change that alters the OpenAPI surface, run `make generate-types` and stage the regenerated `frontend/types/*` files in the **same commit** as the backend change. CI's `Generated Types Freshness / Generated Types Staleness Check` job runs `make generate-types` then `git diff --exit-code frontend/types/`; if the committed types lag the spec, the job fails with `##[error]Generated types are stale.` and blocks the PR even when every other test passes.

**Triggers (any one is enough):**
- New or modified Pydantic request/response schema referenced by a route
- New or modified `api_route(query_schema=..., header_schema=..., path_schema=...)`
- New or removed route, or a decorator change that affects OpenAPI metadata
- Changes to metrics dimensions, events, or resources (regenerates `metrics-dimensions.d.ts`, `metrics-dim-values.ts`, `metrics-events.ts`, `metrics-resources.ts`)
- A route, decorator, service, schema, template, or `all_routes.py` JS-linkage change also needs `make generate-endpoints` — stage the regenerated `docs/endpoints/` in the same commit (CI's `Endpoint Registry Audit` fails otherwise; see "Endpoint Registry")

Before committing a backend change in any of those categories, run `make generate-types` and check `git status` for changes under `frontend/types/`. Stage them in the same commit as the backend change.

## Development Commands

### Makefile Shortcuts

Run `make help` for every target; annotated reference in `docs/development.md`.

### Metrics Verification (local stack)

Bring the stack up with `make up p=full d=1` to exercise the anonymous-metrics pipeline end-to-end: the flush/gauge `workflow` container is only in the `full` profile, and `metrics-flush-now`/`gauge-sample-now`/`notify-test` refuse to run (`workflow is not running — start it with: make up p=full d=1`) without it. Metrics are **on by default locally**: `docker/compose.local.yaml` declares the tracked default `METRICS_ENABLED=${METRICS_ENABLED:-true}`, so every `make up` enables them on every host (the web app still records into Redis on the default stack; only the flush to Postgres needs `p=full`) — **never prefix `METRICS_ENABLED=true` on local commands**. To opt a machine out (or exercise the disabled path), put `METRICS_ENABLED=false` in `.env`, which `make` passes via `--env-file .env`. **Remove any lingering `export METRICS_ENABLED=…` from your shell profile:** compose interpolation resolves the shell environment before `--env-file`, so a leftover export silently overrides the `.env` opt-out (check with `printenv METRICS_ENABLED`). Tests are unaffected (`ConfigTest.METRICS_ENABLED = False`). Prod (`docker/compose.yaml`) and dev (`docker/compose.dev.yaml`) both hard-set `METRICS_ENABLED=true`.

Metrics verification commands: see `docs/development.md`.

### Docker Execution Note

All `make`/`docker`/`docker compose` targets used by this repo are already listed in `sandbox.excludedCommands` (`.claude/settings.local.json`) and run unsandboxed automatically — no `dangerouslyDisableSandbox` flag needed. Never compound them with another command (see central "Working inside a sub-repo" note on first-token-only matching) — run cleanup/setup as its own Bash call, then the `make`/`docker` call alone.

**CRITICAL:** Never run `make up` or `make up-built` without `d=1`. Without the detached flag, these commands stream Docker logs to stdout indefinitely and never exit. Always use `make up [p=ui|full] d=1` (or `make up-built [p=full] d=1`). With `d=1`, `make up` returns once the containers are started; `up-built d=1`, `start-built` and `tunnel` also wait for the vite build and a healthy `web` (see "Running the App"). Before starting containers, check what is already running with `make stack-info` (this checkout's project names, cached ports/URLs, hub `db` and `playwright` state and attached spokes). This spoke's container/health state is `docker ps --filter label=com.docker.compose.project=<project from stack-info>`; poll it until healthy.

**Local Postgres:** one `db` cluster in the per-user hub holds every spoke's dev DB and every per-run test DB, and runs `fsync=off`, so a host crash may corrupt `pgdata`. Recovery **deletes all dev data in every spoke**: read `docs/development.md` → "Hub and spokes" (Local Postgres recovery) before running it.

### Running the App (Docker - recommended)

**Hub and spokes.** Each checkout (the primary clone or any git worktree) runs its own compose project, a "spoke" `u4i-<slug>`, sharing one per-user "hub" (`u4i-hub-<uid>`: the Postgres `db` and the Playwright browser server). `make down` stops only this spoke; `make hub-down` stops the hub (refused while any spoke is attached). Create a worktree with `make worktree-new name=<slug> [b=<branch>] [from=<ref>]` and remove it with `make worktree-rm` run inside it (see `docs/worktrees.md`); its folder name must be unique on the host. A `spoke admission: refusing spoke …` message means there is not enough usable memory for another spoke. Full mechanics: `docs/development.md` → "Hub and spokes".

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

Built mode: see ARCHITECTURE.md → Docker (`docker/compose.built.yaml`). Host identity (UID/GID) details: see `docs/development.md`.

#### Playwright

Use the following URL to access the website with Playwright MCP: `http://127.0.0.1:8659/` (primary clone; in a worktree use the web URL from `make stack-info`). Each spoke has its own session cookie name (`<project>_session`), so logins in two spokes don't log each other out. The stack must be up with `make up p=ui d=1` or `make up-built d=1`; on the default `make up d=1` stack there is no vite, so pages render unstyled.

### Running without Docker, Frontend (Vite) and Flask CLI

Running without Docker, Frontend (Vite) build commands, and Flask CLI commands: see `docs/development.md`.

`make vite-build` and `make generate-types` run vite in a one-off container (`run --rm --no-deps vite`), so they need no `p=` (`generate-types` still needs `web` up, which the default `make up d=1` provides). `make test-js` runs on the host and needs no stack at all (`test-js-built` is just an alias). The Testing targets below `exec` into the running local stack, so it must be up (`make up d=1`); on the built stack (`make up-built`) use the `-built` variants (`vite-build-built`, `test-file-parallel-built`).

### Testing

Run tests in Docker via the `make` targets (they activate the container's venv for you):

```bash
make test-file f=<test-path>              # single file or path (pass extra pytest args via args=...)

# Examples:
make test-file f=tests/functional/splash_ui/test_reset_password_ui.py
make test-marker-parallel m=unit
```

Running tests outside Docker and the test marker list: see `docs/development.md` (markers are defined in `pytest.ini`).

**Prefer parallel make targets** (`test-marker-parallel`, `test-integration-parallel`, `test-ui-parallel`) over sequential ones. "Parallel" means `-n` workers within a single invocation. Concurrent invocations are isolated from each other, and the host token budget queues any run that would push total workers past `U4I_N_MAX` (see Testing Best Practices #7).

**Always minimize wall-clock time**: omit `n=` so each target uses this host's derived maximum (`U4I_N_UI` for UI, including a `*_ui` marker or `tests/functional` path; `U4I_N_INT` for other integration/marker/file runs; see the parallelism-cap note above and `make capacity`). Never default to `n=2` for "quick" or "smoke" runs — low parallelism on the full suite just means paying the full test cost at slower cadence, and can expose latent timing flakes (e.g., shared Playwright browser-server connection idle-timeouts) that never occur at production cadence. A true "smoke" test is scoped by marker (`m=splash_ui`) or test path, NOT lowered parallelism on the full suite. `make test-agent` is the default pre-commit check for agents: it scopes by marker (the markers the diff affects, via `make test-affected`), never by lowering `n`.

Playwright browser-server mechanics and lifecycle: see `docs/development.md`.

### Linting & Formatting

One definition per check, run host-native. The pre-commit hook and CI call the same targets:

```bash
make setup          # once per clone/worktree: .env/secrets links + tools + hooks + capacity (idempotent)
make tools          # install the pinned toolchain, pnpm install --frozen-lockfile --ignore-scripts, set blame.ignoreRevsFile (run by setup)
make lint           # ruff check + identifier check + eslint + shellcheck + lockfile-check + lint-actions + audit-pins
make lint-actions   # actionlint on .github/workflows/ (also run by make lint)
make audit-pins     # exact-pin audit: manifests, Dockerfile FROM, compose image:, pip install, workflow uses: (also run by make lint)
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
