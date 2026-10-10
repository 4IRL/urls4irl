# Development Reference

Reference material moved out of `CLAUDE.md`, which keeps the behavioral rules and points here. Run `make help` for the live list of every target.

## Makefile Shortcuts

Common tasks (see central Makefile-First Command Policy for the general rule):

| Command | Description |
|---|---|
| `make setup` | One-time per clone/worktree onboarding: `worktree-init` + `tools` + `hooks` + `capacity` (idempotent; a capacity failure, e.g. Docker down, is deferred — rerun `make capacity` to see the error) |
| `make capacity [U4I_N_UI=<n\|auto>] [U4I_N_INT=<n\|auto>] [U4I_MEM_FRACTION=<f\|auto>]` | Derive test worker counts + interlocks for this host into `docker/.capacity.generated.env` (overrides are sticky; `=auto` clears), then prints a `live:` line (usable memory now, its source, workers that fit) |
| `make tools` | Install the pinned host toolchain + `frontend/node_modules` (run by `make setup`; re-run after pin bumps) |
| `make hooks` | Install the pre-commit git hook in the main checkout (run by `make setup`; safe from any worktree — see `CLAUDE.md` → "Pre-commit hooks") |
| `make hooks-check` | Report whether the pre-commit hook is installed (exits 1 when missing; worktree-safe) |
| `make up [p=ui\|full] d=1` | Start the hub, then build and start this spoke's web + datastores (detached); `p=ui` adds vite and starts hub playwright, `p=full` also adds workflow. A narrower `p` stops the spoke services it no longer enables. Refuses a new spoke when live memory can't hold it idle plus a minimum test run, printing the numbers and the running spokes (`make down` one first; no live reading → the `U4I_SPOKE_MAX` count); a running spoke is always re-admitted |
| `make up-built [p=full] d=1` | Start the hub, then build and start with pre-built Vite assets (detached): web + datastores + vite one-shot build, waiting for the build and a healthy web, then start hub playwright; `p=full` also adds workflow |
| `make down` | Stop this spoke (every profile); the hub keeps running |
| `make build` | Rebuild this spoke's images without starting (every profile) |
| `make restart c=<service>` | Restart a **spoke** service (`c=` is required; reaches profiled services too; hub services are refused) |
| `make logs c=<service>` | Show a spoke service's logs, dev or built stack (e.g. `c=cloudflared`; hub services are refused) |
| `make stack-info` | Print this checkout's spoke project, aliases, URLs, hub project, hub `db` and `playwright` state (`Exited (0)` = idle-reaped) and attached spokes |
| `make worktree-init` | Link `.env` and `secrets/` from the primary clone into this worktree (no-op in the primary; run by `setup`, `up`, `up-built`, `start-built`, `tunnel`) |
| `make worktree-new name=<slug> [b=<branch>] [from=<ref>]` | Create a worktree under `.claude/worktrees/<slug>`: checks docker, the primary's `.env` and spoke admission first, links `.env`/`secrets/`, prints `make up d=1` (starts no stack). `from=` is the base ref (default `origin/<default branch>`; not `base=`, the affected-markers knob) |
| `make worktree-rm` | Run inside a worktree: `down -v --rmi local` its compose project, drop its hub dev DB, then non-force `git worktree remove` (branch kept). Refuses in the primary |
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
| `make test-artifacts [run=<id>]` | Print the latest run's UI failure-artifact index: per failing test its nodeid, phase, first error line, console/page-error/failed-request counts and the absolute paths of every evidence file (host-native, no stack; `run=<id>` for an older run, an unknown id exits 2 listing the available ones). See "UI failure artifacts" below |
| `make test-host-static [f=<paths>] [args=...]` | Host-only static tests (Makefile dry runs, compose YAML, playwright entrypoint; they skip inside `web`) in the primary clone's `venv/`; installs the test + prod pins on first use and again whenever `requirements-test.txt` / `requirements-prod.txt` is newer than the venv stamp |
| `make affected-markers [base=<ref>]` | Show which test markers the branch diff affects, and why: one line per changed file, then an `Integration:` / `UI:` / `Host-static:` footer (host-native, no stack, no budget). The diff is against `git merge-base <base> HEAD` (default `origin/main`) plus uncommitted and untracked files; an unmapped path selects everything |
| `make test-affected [base=<ref>]` | Run only the test markers the branch diff affects: the host-static tests (if a host-only file changed), then one budgeted integration run at `U4I_N_INT`, then one budgeted UI run at `U4I_N_UI` (starts vite + playwright only when UI markers are selected). Queues on the host token budget; shrinks to fit live memory unless `n=` is given. Prints `No affected markers — nothing to run` for an empty selection. If the selector fails (e.g. an unresolvable `base`), make stops with `affected_markers.py failed (exit N)` before any test runs; run `git fetch origin`. Its scope comes only from `base=<ref>` (`n=`, if given, applies to both runs): unlike every other `test-*` target, `f=`/`args=` are refused, because it selects its own scope from the diff; use `make test-host-static` or `make test-file-parallel` for a narrower, file-scoped run. `base` must not contain `$` or `'` |
| `make test-agent [base=<ref>]` | Agent tier: `typecheck` + `test-js` + `test-affected`; queues on the host token budget (target <60s on a single-domain diff; measured: an integration-only `backend/contact/` diff ≈ 28 s, a `backend/members/` diff ≈ 88 s, dominated by the UI run). Same scope rule as `test-affected` (`f=`/`args=` refused) |
| `make test-playwright-lifecycle` | Build the derived Playwright image and run its idle-reap / restart E2E harness in throwaway containers (~7 min) |
| `make vite-build` | Vite build verification |
| `make addmock` | Seed dev DB with all mock data |
| `make generate-types` | Regenerate TypeScript API types from OpenAPI spec + per-event dim shapes (metrics-dimensions.d.ts, metrics-dim-values.ts, metrics-events.ts) |
| `make generate-endpoints` | Regenerate `docs/endpoints/endpoint-registry.json` + `ENDPOINT_REGISTRY.md` from the live url_map (needs `web` up) |
| `make audit-endpoints` | Audit the committed endpoint registry against the live app: drift, `@api_route` JS linkage, stale `NO_JS_ENDPOINTS`/`INDIRECT_JS_ENDPOINTS` entries, markdown freshness (exits 1 on any finding; needs `web` up) |
| `make endpoint-info e=<route>` | Show what touches a route (`e=` endpoint, rule, or `'METHOD /rule'`), read from the committed JSON (host-native, no stack needed) |
| `make audit-pins` | Fail unless every dependency manifest, image tag, pip install and action ref is exactly pinned (host-only, no stack; also run by `make lint`) |
| `make help` | List all available make commands |

## Metrics Verification (local stack)

The rules for bringing the stack up for metrics (and for `METRICS_ENABLED`) are in `CLAUDE.md` → "Metrics Verification (local stack)".

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

## Runtime debug logging (`debug(namespace)`)

The rule (never call `console.*` directly; use `debug(namespace)`) is in `CLAUDE.md` → Frontend rule 5.

Toggle namespaces via DevTools: `localStorage.debug = "metrics,ajax"` then refresh. The 5 splash namespaces (`splash`, `splash:login`, `splash:register`, `splash:password`, `splash:email`) are available to any user; all other namespaces require `APP_CONFIG.debugEnabled` (admin-only). The 20 active namespaces are: `ajax, csrf, metrics, config, init, cookie-banner, security, home-shell, utubs, urls, urls:cards, urls:tags, tags, members, onboarding, splash, splash:login, splash:register, splash:password, splash:email`.

## Host identity

**Host identity:** the local web image's `u4i-host` user is built with this host's `HOST_UID`/`HOST_GID` (from `make capacity`; build args in `docker/compose.local.yaml`, image default 1001), so files it writes into bind mounts are owned by you. The `vite` container runs as the same `HOST_UID:HOST_GID` (compose `user:` plus build args; its image re-owns `/app`), so `backend/static/dist` from `vite build` (built mode, `make vite-build`) is yours too and `git worktree remove` never hits `Permission denied`. A `dist` left root-owned by an older vite image makes the build fail (`EACCES`, see `make logs c=vite`); remove it once with `docker run --rm -v "$PWD/backend/static:/s" alpine:3 rm -rf /s/dist`. An `app_logs` volume created by an older image, or re-owned by a previous workflow start, can leave `/app/volume/logs` owned by another uid, and web would crash on its log file. `make up`/`up-built`/`start-built`/`tunnel` repair that automatically through the private `_logs-owner-fix` prerequisite, which prints `repairing app_logs ownership (was X, now UID:GID)` once and is silent otherwise. The workflow container keeps write access through the log dir's group.

## Running the App (without Docker)

```bash
flask db upgrade
flask shorturls add
flask managedb create          # optional: populate test data
flask run --host=0.0.0.0 --port=5000
```

## Frontend (Vite)

```bash
make vite-build  # build to backend/static/dist/ (= pnpm run build) in a one-off vite container
make test-js     # run JS unit tests (vitest) on the host
```

## Flask CLI Commands

```bash
flask addmock all             # populate DB with test data (Docker: `make addmock`)
flask managedb clear          # clear test data
flask managedb drop           # drop database tables
flask shorturls add           # register short URL routes
```

## Running tests outside Docker (if virtual environment is already activated)

```bash
pytest                        # run all tests
pytest -m unit                # unit tests only
pytest -m splash              # integration tests for auth
pytest -m utubs               # integration tests for UTubs
pytest tests/unit/test_foo.py # single test file
pytest -k "test_name"         # single test by name
```

Test markers (used for CI parallelization): `unit`, `splash`, `utubs`, `members`, `urls`, `tags`, `account_and_support`, `cli`, `splash_ui`, `home_ui`, `utubs_ui`, `members_ui`, `urls_ui`, `create_urls_ui`, `update_urls_ui`, `tags_ui`, `mobile_ui`, `metrics_ui`, `settings_ui`, `search_ui`, `mobile_api`, `admin`, `admin_ui`

## Playwright browser-server mechanics and lifecycle

UI/functional tests require the shared Playwright browser-server, which lives in the per-user hub and serves every spoke: the hub `playwright` service runs `playwright run-server --port 3000 --host 0.0.0.0` from the derived image `u4i-playwright:<version>` (`docker/Dockerfile.Playwright`: the CLI is baked in, so a start never touches the npm registry; its `ARG PLAYWRIGHT_VERSION` is unit-tested to match the `playwright==` pin in `requirements/requirements-test.txt`), each spoke's `web` sets `PLAYWRIGHT_WS_URL=ws://playwright:3000/` (the hub service name on `u4i-shared-<uid>`), and `build_page_browser` in `tests/functional/conftest.py` calls `chromium.connect(config.TEST_PLAYWRIGHT_URI)` in Docker (falling back to `chromium.launch()` outside it). The hub browser reaches a spoke by its slugged aliases (`web-<slug>` via `U4I_WEB_HOST` → `UI_TEST_STRINGS.DOCKER_BASE_URL`, `vite-<slug>` via `VITE_INTERNAL_HOST`), since bare `web`/`vite` would be ambiguous across spokes. Playwright no longer `depends_on` web or vite (cross-project dependencies are impossible), so make targets order the start instead: `make test-functional`/`make test-ui-parallel` run `playwright-up`, then `up -d --wait web vite`; the `*-built` targets start them via `start-built`, which runs `playwright-up` **last** (after a healthy `web`) so a long rebuild can't eat the idle window before pytest connects (`up-built d=1` does the same).

Lifecycle: the entrypoint (`docker/playwright-entrypoint.sh`) supervises the server and exits 0 after `U4I_PLAYWRIGHT_IDLE_MINUTES` (default 15) with no non-loopback client, freeing ~500 MB. The service has a node TCP healthcheck (loopback, so it never counts as a client) and no restart policy. Its logs hold only a startup line (`playwright-entrypoint: serving :3000, reaping after 15m idle`, or `serving :3000, reaping disabled` with `IDLE_MINUTES=0`) and a reap line (`idle 15m with no clients — exiting`). `make playwright-up` restarts a reaped container in place (same container, no registry fetch) and waits for health; it never picks up an image/config change, which needs `make playwright-rebuild`. In dev mode, `make test-marker*` with a `*_ui` marker and `make test-file*` on a path that collects `tests/functional` (the whole tree included) run `playwright-up` themselves (and their `-parallel` / `-parallel-built` variants default `-n` to `U4I_N_UI`; an explicit `n=` wins), but still need `make up p=ui d=1` for web + vite. The `%_ui` word match ignores marker-expression semantics, so `m='not admin_ui'` also starts playwright and uses the UI cap: harmless (an extra start, fewer workers). `make test-last-failed` does not start it: run `make playwright-up` first if the last failures include UI tests. `make test-playwright-lifecycle` proves the image's reap/restart behavior in throwaway containers.

## UI failure artifacts

Every failing UI test (desktop or mobile) writes its evidence automatically, so the first read after a red run is the evidence, not a guess. Capture lives in `tests/functional/failure_artifacts.py`: the two page fixtures (`page_without_cookie_banner_cookie`, `page_mobile_portrait_without_cookie_banner_cookie`) wrap their browser context in `recorded_context` right after `new_context()`, so it also covers a failure before the fixture yields (e.g. a `page.goto()` timeout). The module is registered as a root pytest plugin (`tests/conftest.py` `pytest_plugins`), so its session hooks also run on the xdist controller. Read the result with `make test-artifacts`.

The same page fixtures also apply `tests/functional/third_party_stubs.py` to their context. When `frontend/public/vendor` is populated by `frontend/setup-vendor.sh` (CI and host runs), the UI tests serve the jQuery/Bootstrap CDN scripts from it, keeping the production markup; local container runs do not mount that directory, so they keep using the real CDN. The script exits non-zero on any download failure. Tests that request the `metrics_redis_client` fixture (the `*_metrics_ui.py` modules) are never stubbed: any route makes Chromium pause every request, which can abort the `sendBeacon` the metrics client fires while a page unloads and lose the event those tests assert on.

Layout, under `tmp/test-artifacts/` (gitignored; `web` bind-mounts it, and every stack-start target pre-creates it host-owned, so the files are yours):

```
tmp/test-artifacts/
├── latest.json                   ← points at the newest run that had a failure
└── <run>/                        ← 8-hex run id, shared by every xdist worker of one pytest invocation
    ├── index.json                ← every failure in the run: nodeid, dir, phase, error_summary, counts, trace
    └── <test>/                   ← sanitized nodeid (tests/functional/ dropped, / and :: → __, capped at 120 chars + hash)
        ├── failure.json          ← the record: nodeid, phase, error_summary, worker, captured_at, pages, counts, capture_errors
        ├── page-<N>.png          ← full-page screenshot per open page (popups get page-1, page-2, …)
        ├── page-<N>.html         ← that page's DOM at failure time
        ├── console.json          ← last 300 console entries + up to 100 uncaught page errors
        ├── network.json          ← last 300 requests (method, URL, type, status, failure) + up to 100 failed ones (status ≥ 400 or a network failure)
        └── trace.zip             ← only with U4I_UI_TRACE=retain-on-failure
```

A green run writes nothing (no run dir, no `index.json`, `latest.json` untouched). Each capture step is isolated: if the browser is already gone (e.g. the hub `playwright` idle-reaped mid-test) or the disk is full, the failing step is recorded in `failure.json`'s `capture_errors` and the rest is still written; capture never raises in fixture teardown.

What is and is not captured:

- **Setup and call phases only.** Teardown-phase failures are not captured: pytest reports them after the page fixture has already closed its context, so there is no browser left to read from.
- **No headers or bodies, but full URLs.** `console.json` and `network.json` hold full request URLs (path and query string), methods, statuses and messages only; request/response headers, cookies and bodies are deliberately excluded. Full URLs can still carry secrets: the password-reset link puts a live token in the path (`/reset-password/<token>`), so artifacts from the splash reset/forgot-password suites (also `failure.json`'s `pages[].url`) must not be pasted into issues, PR comments or chat. `trace.zip` is more sensitive still: a Playwright trace **does** contain headers, cookies and bodies, so keep it local or in private CI artifacts.

Knobs (compose `web` env, read when `web` is created; set them in `.env` or on a command that (re)creates `web`):

| Knob | Default | Effect |
|---|---|---|
| `U4I_UI_TRACE` | `off` | `retain-on-failure` also records a Playwright trace (screenshots on, DOM snapshots and sources off) and keeps it as `trace.zip` only for a failing test. Any other value fails the session as a usage error. Tracing is opt-in because it measured too slow to leave on: with DOM snapshots on, the median wall-clock of `make test-ui-parallel-built` rose **+45%** (580 s vs 400 s); with snapshots off it still rose **+30%** (524 s vs 403 s), with ~+420 MiB of median peak hub `playwright` memory. Screenshot, DOM, console, network and `failure.json` are captured on every failure regardless |
| `U4I_TEST_ARTIFACTS_KEEP` | `10` | Run dirs kept per checkout. Each pytest session prunes the oldest 8-hex run dirs (by mtime) beyond this at start, so a failing run can briefly leave `keep + 1`. Must be ≥ 1 |
| `U4I_TEST_ARTIFACTS_DIR` | `<rootdir>/tmp/test-artifacts` | Artifact root (a relative path resolves against pytest's rootdir). Not passed through compose: only for runs outside Docker |

To get a trace for one failure, rerun just that test traced. The `*-built` targets recreate `web`, so a per-command prefix works there: `U4I_UI_TRACE=retain-on-failure make test-file-parallel-built f=<path>`. The dev-mode `make test-file` / `test-marker*` targets `exec` into the running `web`, so restart it traced first: `U4I_UI_TRACE=retain-on-failure make up p=ui d=1`, then run the test, then `make up p=ui d=1` again to turn tracing back off. Open the zip by dragging it onto https://trace.playwright.dev (step-by-step action timeline, screencast, console, network).

**CI:** when a `Tests-UI` matrix row fails, `.github/workflows/test.yml` uploads that row's `tmp/test-artifacts/` as the `ui-failure-artifacts-<marker>` artifact (kept 7 days). CI does not set `U4I_UI_TRACE`, so those artifacts carry no `trace.zip`. Download one from the run page, or with the stronghold helper (run from `~/code`): `.claude/scripts/gh-log-fetch.sh run download <run-id> --repo 4IRL/urls4irl --name ui-failure-artifacts-<marker> --dir /tmp/claude/ci-artifacts/<run-id>`, then point `make test-artifacts` at it with `mise exec python -- python scripts/failure_artifacts_report.py --root /tmp/claude/ci-artifacts/<run-id>`.
