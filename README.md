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
make tools
make hooks
```

`make tools` needs [mise](https://mise.jdx.dev/installing-mise.html). It installs the host lint
toolchain pinned in `.mise.toml` (Python 3.11.14, node, ruff, shellcheck, shfmt), runs
`npm ci --ignore-scripts` in `frontend/`, and points `git blame` at `.git-blame-ignore-revs`.
Don't run `mise trust`: the config must stay pin-only, and `make mise-config-check` enforces that.

`make hooks` creates a local `venv/` (gitignored), installs the `pre-commit` version pinned in
`requirements/requirements-dev.txt`, and installs the git pre-commit hook. `make hooks-check`
reports whether the hook is present in the current clone.

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
| `POSTGRES_DB` | Yes | - | PostgreSQL database name |
| `MAILJET_API_KEY` | Yes | - | Mailjet API key for transactional emails |
| `MAILJET_SECRET_KEY` | Yes | - | Mailjet secret key |
| `POSTGRES_TEST_DB` | No | - | Test database name for pytest |
| `REDIS_URI` | No | `memory://` | Redis connection URI |
| `METRICS_REDIS_URI` | No | `memory://` | Redis URI for the dedicated metrics counter buffer (separate from `REDIS_URI`) |
| `ENABLE_SSL` | No | `false` | Enable HTTPS in local dev (Flask + Vite) |
| `VITE_URL` | No | `http://localhost:5173` | Vite dev server URL (use `https://` when `ENABLE_SSL=true`) |

See [`backend/config.py`](backend/config.py) for the full list.

### Running with Docker (recommended)

A `Makefile` is provided for common development tasks:

| Command | Description |
|---|---|
| `make up` | Build and start the full stack |
| `make down` | Stop the stack |
| `make build` | Rebuild images without starting |
| `make restart c=<service>` | Restart a specific compose service (e.g. `make restart c=web`) |
| `make test-integration` | Run all non-UI integration tests |
| `make test-functional` | Run all UI/Playwright functional tests |
| `make test-js` | Run all JS unit tests (vitest) |
| `make test-marker m=<marker>` | Run tests for a specific pytest marker (e.g. `make test-marker m=utubs`) |
| `make test-integration-parallel [n=4]` | Run all non-UI integration tests in parallel (preferred) |
| `make test-ui-parallel [n=8]` | Run all UI/Playwright tests in parallel (preferred, max n=8) |
| `make test-marker-parallel m=<marker> [n=4]` | Run tests for a specific marker in parallel (preferred) |
| `make vite-build` | Build Vite to verify no import/syntax errors |
| `make help` | List all available make commands |

Or run directly:

```bash
docker compose --project-directory . -f docker/compose.local.yaml up --build --remove-orphans
```

- Flask: `http://localhost:8659`
- Vite: `http://localhost:5173`

**Note:** SSL is disabled by default in local development. To enable HTTPS and avoid mixed content warnings:
1. Set `ENABLE_SSL=true` for both `web` and `vite` services in `docker/compose.local.yaml`
2. Change `VITE_URL=https://localhost:5173` in the `web` service environment

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

UI tests require the shared Playwright browser-server: the `playwright` service runs `npx -y playwright@1.60.0 run-server --port 3000 --host 0.0.0.0`, the `web` service sets `PLAYWRIGHT_WS_URL=ws://playwright:3000/`, and `build_page_browser` in `tests/functional/conftest.py` calls `chromium.connect(config.TEST_PLAYWRIGHT_URI)` in Docker (falling back to `chromium.launch()` outside it). See [`pytest.ini`](pytest.ini) for the full list of test markers.

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
