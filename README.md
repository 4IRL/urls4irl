# URLS4IRL

*A simple, clean way to permanently save and share URLs.*

URLS4IRL is a collaborative URL sharing platform where users organize links into shared collections called **UTubs**. Try it at [urls.4irl.app](https://urls.4irl.app).

## Features

- **UTubs** - Create, edit, and delete shared URL collections with names and descriptions
- **URLs** - Add URLs with custom titles; automatic validation and canonicalization
- **Tags** - Organize URLs with up to 5 tags per URL, scoped per UTub
- **Members** - Invite users with role-based access (Creator, Co-Creator, Member)
- **Accounts** - Register with email validation, login, and password reset

## Tech Stack

| Category | Technologies |
|---|---|
| **Backend** | Flask, SQLAlchemy, PostgreSQL, Redis |
| **Frontend** | Jinja2, vanilla JS/jQuery (transitioning to Vite + ES6 modules) |
| **Auth** | Flask-Login, Flask-WTF (CSRF), Mailjet (transactional email) |
| **Infrastructure** | Docker, Docker Compose, Gunicorn, Nginx |
| **Testing** | pytest, Selenium |
| **Code Quality** | Black, Flake8, Prettier, ESLint, pre-commit |

## Getting Started

### Prerequisites

**Recommended:** Docker & Docker Compose

**Without Docker:** Python 3.11, PostgreSQL, Redis, Node.js

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
| `SELENIUM_URL` | No | - | Selenium Grid URL for UI tests |
| `ENABLE_SSL` | No | `false` | Enable HTTPS in local dev (Flask + Vite) |
| `VITE_URL` | No | `http://localhost:5173` | Vite dev server URL (use `https://` when `ENABLE_SSL=true`) |

See [`src/config.py`](src/config.py) for the full list.

### Running with Docker (recommended)

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

UI tests require Selenium (`SELENIUM_URL` env var). See [`pytest.ini`](pytest.ini) for the full list of test markers.

## Project Structure

```
urls4irl/
├── src/              # Flask app (blueprints, models, templates, static)
├── frontend/         # Vite/ES6 frontend modules
├── tests/            # pytest suite (unit, integration, UI)
├── docker/           # Dockerfiles and compose configs
├── migrations/       # Alembic database migrations
├── requirements/     # Python dependencies (dev, prod, test)
└── nginx/            # Nginx config (production)
```

## API Documentation

See [`src/API_DOCUMENTATION.md`](src/API_DOCUMENTATION.md) for full endpoint documentation.

## Contributing

1. Fork the repo and create a feature branch
2. Run `pre-commit run --all-files` before submitting
3. Run `pytest` to verify tests pass
4. Follow existing style (Black for Python, Prettier for JS)
5. Open a pull request

## License

[GPLv3](LICENSE)
