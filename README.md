# URLS4IRL

*A simple, clean way to permanently save and share URLs.*

URLS4IRL is a collaborative URL sharing platform where users organize links into shared collections called **UTubs**. Try it at [urls.4irl.app](https://urls.4irl.app).

## Features

- **UTubs** - Create, edit, and delete shared URL collections with names and descriptions
- **URLs** - Add URLs with custom titles; automatic validation and canonicalization
- **Tags** - Organize URLs with up to 20 tags per URL, scoped per UTub
- **Members** - Invite users with role-based access (Creator, Co-Creator, Member)
- **Accounts** - Register with email validation, login, and password reset

## Tech Stack

| Category | Technologies |
|---|---|
| **Backend** | Flask, SQLAlchemy, PostgreSQL, Redis |
| **Frontend** | Jinja2, Vite, ES6 modules, jQuery |
| **Auth** | Flask-Login, Flask-WTF (CSRF), Mailjet (transactional email) |
| **Infrastructure** | Docker, Docker Compose, Gunicorn, Nginx |
| **Testing** | pytest, Playwright, Vitest |
| **Code Quality** | ruff, Prettier, ESLint, shellcheck/shfmt, pre-commit (via make targets) |

## Getting Started

### Prerequisites

**Recommended:** Docker & Docker Compose

**Without Docker:** Python 3.11, PostgreSQL, Redis, Node.js

### First-time clone setup

Run this **once per clone**, before your first commit:

```bash
make setup
```

`make setup` is idempotent (safe to re-run, and safe in a git worktree) and runs three steps:

1. `make tools` needs [mise](https://mise.jdx.dev/installing-mise.html). It installs the host lint
   toolchain pinned in `.mise.toml` (Python 3.11.14, node, pnpm, ruff, shellcheck, shfmt,
   actionlint), runs `pnpm install --frozen-lockfile --ignore-scripts` in `frontend/`, and points
   `git blame` at `.git-blame-ignore-revs`. Don't run `mise trust`: the config must stay pin-only,
   and `make mise-config-check` enforces that.
2. `make hooks` creates a gitignored `venv/` in the main checkout with the mise-pinned Python,
   installs the `pre-commit` version pinned in `requirements/requirements-dev.txt`, and installs
   the git pre-commit hook. `make hooks-check` reports whether the hook is present (it exits 1
   when it is missing).
3. `make capacity` sizes the local stack for this machine: test worker counts, the Redis and
   Postgres limits that depend on them, and the host UID/GID for the web image. It writes the
   gitignored `docker/.capacity.generated.env`. The same file sets the host-wide test token
   budget (`U4I_N_MAX`: concurrent test runs across every checkout queue rather than exceed it)
   and an informational spoke estimate (`U4I_SPOKE_MAX`: how many checkouts' stacks fit on an
   idle machine). Every value comes from stable inputs (cores, total memory), so the file doesn't
   change as free memory moves; test-run starts and stack starts read live free memory instead,
   and `make capacity` prints it on a `live:` line. If this step fails (for example, Docker isn't
   running yet), `make setup` defers it instead of failing and `make up` generates the file
   later; run `make capacity` to see the error.

**Why it matters:** the app itself is fully containerized, but git hooks run *on the host*.
Skip this step and `ruff`, `eslint`, `prettier` and `shellcheck`/`shfmt` silently never run on
your commits, and CI (`Check Formatting` / `Linting`) becomes the first thing that catches a
formatting error — after you've already pushed. The hooks and CI run the same targets:
`make lint`, `make format-check` and `make typecheck` (fix formatting with `make format`).

Two things to know once the hook is installed:

- **Hooks check the whole tree**, so untracked `.py`/`.ts` files with errors can block a commit.
- **GUI/IDE git clients need `mise` on their non-interactive PATH** (`~/.local/bin`), or the
  hooks fail with `host lint toolchain missing — run 'make tools'`.

### Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes | - | Flask secret key for session encryption |
| `POSTGRES_USER` | Yes | - | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | - | PostgreSQL password |
| `POSTGRES_DB` | Yes | - | PostgreSQL database name (locally, compose overrides it with the per-worktree `u4i_dev_<slug>`, which each spoke's `db-init` creates in the shared hub cluster) |
| `MAILJET_API_KEY` | Yes | - | Mailjet API key for transactional emails |
| `MAILJET_SECRET_KEY` | Yes | - | Mailjet secret key |
| `POSTGRES_TEST_DB` | No | - | Test database name prefix: each pytest run/worker gets `{POSTGRES_TEST_DB}_{uid8}_{worker}` (lowercase `[a-z0-9_]`; locally it must differ from the dev DB name `u4i_dev_<slug>`, or `db-init` refuses to provision) |
| `POSTGRES_TEST_USER` | No | `POSTGRES_USER` | Role tests connect as; local compose sets the `u4i_test` role, which cannot connect to the dev database |
| `REDIS_URI` | No | `memory://` | Redis connection URI |
| `METRICS_REDIS_URI` | No | `memory://` | Redis URI for the dedicated metrics counter buffer (separate from `REDIS_URI`) |
| `ENABLE_SSL` | No | `false` | Enable HTTPS in local dev (Flask + Vite) |
| `VITE_URL` | No | `http://localhost:5173` | Vite dev server URL (use `https://` when `ENABLE_SSL=true`); local compose sets `http://localhost:<this checkout's vite port>` |

See [`backend/config.py`](backend/config.py) for the full list.

### Running with Docker (recommended)

A `Makefile` is provided for common development tasks:

| Command | Description |
|---|---|
| `make setup` | One-time per clone/worktree: `.env`/`secrets/` links (worktrees), host toolchain, pre-commit hook, capacity file (idempotent) |
| `make capacity` | Derive test worker counts, the test token budget and stack limits for this machine (overrides: `U4I_N_UI=`, `U4I_N_INT=`, `U4I_MEM_FRACTION=`), then print a `live:` line with the memory usable right now |
| `make up [p=ui\|full] d=1` | Start the shared hub (`db`), then build and start this checkout's `web` + datastores (`redis`, `redis-metrics`); `p=ui` adds `vite` and starts the hub `playwright`, `p=full` also adds `workflow`. Refuses to start another checkout's stack when free memory can't hold it plus a minimum test run, with the memory numbers and the running checkouts |
| `make up-built [p=full] d=1` | Same, with pre-built Vite assets (always includes the `ui` profile's vite build + hub `playwright`) |
| `make down` | Stop this checkout's stack (every profile); the hub keeps running |
| `make build` | Rebuild images without starting (every profile) |
| `make restart c=<service>` | Restart one of this checkout's services (e.g. `make restart c=web`; `c=` is required) |
| `make logs c=<service>` | Show one of this checkout's service logs (e.g. `make logs c=cloudflared`) |
| `make stack-info` | Print this checkout's compose project, URLs, and the shared hub's `db` and `playwright` state (`hub playwright: Exited (0) …` = idle-reaped, normal) |
| `make hub-up` / `make hub-down` | Start / stop the shared hub (`hub-down` refuses while any checkout's stack is attached) |
| `make playwright-up` | Start the hub `playwright` browser server and wait until it is healthy; restarts an idle-reaped one in place (idempotent) |
| `make playwright-rebuild` | Rebuild the hub `playwright` image and recreate it, to pick up image/config changes; refuses while any UI run is connected |
| `make hub-restart c=db\|playwright` | Restart a hub service (no health wait): drops every checkout's connections / in-flight runs, so only when no test run is in progress in any checkout. Use `make playwright-rebuild` for image changes |
| `make test-integration` | Run all non-UI integration tests |
| `make test-functional` | Run all UI/Playwright functional tests (starts `vite` + `playwright` itself) |
| `make test-js` | Run all JS unit tests (vitest) on the host — no stack needed |
| `make test-marker m=<marker>` | Run tests for a specific pytest marker (e.g. `make test-marker m=utubs`) |
| `make test-integration-parallel [n=<N>]` | Run all non-UI integration tests in parallel (preferred; default `n` from `make capacity`) |
| `make test-ui-parallel [n=<N>]` | Run all UI/Playwright tests in parallel (preferred; default `n` from `make capacity`; starts `vite` + `playwright` itself) |
| `make test-marker-parallel m=<marker> [n=<N>]` | Run tests for a specific marker in parallel (preferred; default `n` from `make capacity`: the UI count for a `*_ui` marker, else the integration count) |
| `make vite-build` | Build Vite to verify no import/syntax errors (one-off `vite` container; no `p=` needed) |
| `make help` | List all available make commands |

Always pass `d=1` to `make up`; without it the command streams logs and never exits. `make up d=1` alone is enough for integration tests; browsing the dev app with styled pages needs `p=ui` (the Vite dev server).

To browse the dev app with styled pages (the `ui` profile enables `vite` and starts the hub `playwright`; `p=full` also adds `workflow`):

```bash
make up p=ui d=1
```

Always go through `make`: it computes the compose project and network names, resolves this checkout's host ports, generates the capacity env file, and starts the hub first. A raw `docker compose -f docker/compose.local.yaml …` fails fast on the unset `U4I_PROJECT`.

**Several checkouts at once.** Each checkout (the main clone or any `git worktree`) runs its own stack, compose project `u4i-<folder name>`, and all of them share one per-user hub (`docker/compose.hub.yaml`: the Postgres cluster and the Playwright browser server). A new worktree needs only `make setup` (or just `make up d=1`), which links `.env` from the main clone. Give each worktree a unique folder name. Each stack gets its own dev database and session cookie name. `make up` reads the machine's free memory at that moment and refuses a new stack unless it can hold one more idle stack plus a minimum test run (plus the hub, if it isn't running yet), naming the running stacks so you can `make down` one; re-running `make up` on an already-running stack is always allowed. If free memory can't be read (on macOS it is read from the Docker VM through the hub `db`), it falls back to the `U4I_SPOKE_MAX` count from `make capacity`.

**Concurrent test runs.** Every `make test-*` target that runs pytest in `web` (not `test-host-static`), plus the three Docker E2E harnesses, holds tokens from a host-wide, per-user budget of `U4I_N_MAX` (a run at `-n k` holds `k`, a sequential run holds 1), so test runs in several checkouts, or several in one checkout, never oversubscribe the machine. A run that doesn't fit prints `token budget: waiting for <k> of <budget> tokens — held by: …` (then a heartbeat every 30s) and starts as soon as tokens free up: it isn't hung. If tokens are free but another run just started, it prints `token budget: waiting for <slug>/<label> to settle — …` (starts pause briefly after each run starts). Each start also checks free memory: without `n=`, a parallel run shrinks to the workers that fit right now; with `n=` it waits (a default or sequential run also waits if not even one worker fits), printing `token budget: waiting for memory — need … GB for <n> workers, … GB usable (…); runs holding tokens: …`. If no other test run holds tokens (something else is using the memory), it gives up after `U4I_MEMORY_WAIT` seconds (default 600). A failing run prints the capacity and memory it ran under; `at ceiling: yes` with timeouts suggests rerunning with a lower `n=`, and a low-memory hint suggests memory pressure rather than a product bug.

- Flask: `http://localhost:8659` in the main clone
- Vite: `http://localhost:5173` in the main clone (only with the `ui` or `full` profile)
- A worktree's ports are picked automatically (a free port near those); `make stack-info` prints its URLs.

**Note:** SSL is disabled by default in local development. To enable HTTPS and avoid mixed content warnings:
1. Set `ENABLE_SSL=true` for both `web` and `vite` services in `docker/compose.local.yaml`
2. Change `VITE_URL` in the `web` service environment to `https://localhost:${U4I_VITE_PORT:-5173}`

### Running without Docker

```bash
flask db upgrade
flask shorturls add
flask run --host=0.0.0.0 --port=5000 --cert=adhoc
```

Optionally populate test data:

```bash
flask addmock all
```

### Logging In

1. Register on the splash page
2. Validate your email via the confirmation link
3. Log in to be redirected to `/home` to manage UTubs

For local development, `flask addmock all` creates mock users and data.

### Vendor JS Bundles

The project uses jQuery and Bootstrap loaded as global `<script>` tags. For offline development:

1. Download vendor bundles:
   ```bash
   ./frontend/setup-vendor.sh
   ```

2. (Optional) Enable offline mode by setting environment variable:
   ```bash
   USE_LOCAL_JS_BUNDLES=true
   ```

**Normal mode** (default): Loads from CDN with automatic fallback to local bundles if CDN fails.

**Offline mode**: Skips CDN entirely, loads local bundles only.

## Testing

```bash
pytest                   # all tests
pytest -m unit           # unit tests only
pytest -m splash         # auth integration tests
pytest -k "test_name"    # specific test
```

UI tests require the shared Playwright browser-server, which lives in the per-user hub and serves every checkout's stack: the hub `playwright` service runs `playwright run-server --port 3000 --host 0.0.0.0` from a thin derived image (`docker/Dockerfile.Playwright`, `u4i-playwright:<version>`, with the CLI baked in so a start never touches the npm registry; its version is kept in lockstep with `requirements/requirements-test.txt`). Each checkout's `web` service sets `PLAYWRIGHT_WS_URL=ws://playwright:3000/`, the browser reaches that checkout's app by its `web-<slug>` alias, and `build_page_browser` in `tests/functional/conftest.py` calls `chromium.connect(config.TEST_PLAYWRIGHT_URI)` in Docker (falling back to `chromium.launch()` outside it), retrying a few times on transient failures.

The server has a TCP healthcheck, and to free its ~500 MB it exits on its own after `U4I_PLAYWRIGHT_IDLE_MINUTES` (default 15; `0` disables it) with no connected client. An `Exited (0)` hub `playwright` is therefore normal: `make playwright-up` restarts it in place and waits for it to be healthy, and every UI target runs it for you (`make up p=ui`, `make test-functional`/`make test-ui-parallel`, the `*-built` targets, `make test-marker*` with a `*_ui` marker, and `make test-file*` on a path that collects `tests/functional`). A dev-mode UI run still needs `make up p=ui d=1` for `web` + `vite`. `make test-last-failed` does not start it: run `make playwright-up` first if the last failures include UI tests. After changing the image or its compose config, run `make playwright-rebuild`. See [`pytest.ini`](pytest.ini) for the full list of test markers.

## Project Structure

```
urls4irl/
├── backend/          # Flask app (blueprints, models, templates, static)
├── frontend/         # Vite/ES6 frontend modules
├── tests/            # pytest suite (unit, integration, UI)
├── docker/           # Dockerfiles and compose configs
├── migrations/       # Alembic database migrations
├── requirements/     # Python dependencies (dev, prod, test)
└── nginx/            # Nginx config (production)
```

## API Documentation

See [`backend/API_DOCUMENTATION.md`](backend/API_DOCUMENTATION.md) for full endpoint documentation.

## Contributing

1. Fork the repo and create a feature branch
2. Run `make lint && make format-check` before submitting
3. Run `pytest` to verify tests pass
4. Follow existing style (ruff for Python, Prettier for JS/TS)
5. Open a pull request

## License

[GPLv3](LICENSE)
