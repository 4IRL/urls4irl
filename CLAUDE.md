# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. 

Keep your replies extremely concise and focus on conveying the key information. No unnecessary fluff, no long code snippets.

Reference plan may have files in the @plans directory - please reference these if there's a relevant plan file in this directory.


## Project Overview

urls4irl is a full-stack web app for managing shared collections of URLs called "UTubs". Flask backend with Jinja2 templates and a vanilla JS frontend currently transitioning to Vite/ES6 modules.


## Development and Coding Practices

Code should be concise, but readable. We are looking for maintainability and future proofing.


### Frontend - JavaScript/HTML/CSS

1. Never use window globals for module communiation


### Backend - Python/PostgreSQL/Redis

1. Use typehints! No shortcuts around this.

### Tests

Tests are a MUST. We are looking for nearly 100% code completion if possible.

0. Follow test patterns already established
1. All backend code must have integration tests that involve a test database and/or Redis.
2. All frontend code should have at least one happy and one sad path test associated with the UI, unless the UI is complex to warrant multiple tests.

#### Testing Best Practices

1. **Use HTTP for all development tests** - Local development uses HTTP by default (`http://127.0.0.1:8659`), not HTTPS
2. **Run all tests in Docker, never on host** - Always use the Docker containers for running tests
3. **Debug UI test failures with Playwright before changing code** - When a UI test fails and the root cause isn't clear from code inspection, use Playwright MCP to manually reproduce the issue and observe actual behavior BEFORE making code changes
4. **Rerun Selenium infrastructure errors separately** - If tests fail with `InvalidSessionIdException`, `SessionNotCreatedException`, 300+ second setup timeouts, or similar Selenium errors, rerun those specific tests individually to verify they're infrastructure issues, not code bugs. These errors indicate Selenium grid problems (session exhaustion, browser startup failures), not application bugs.
5. **Check Selenium container health for persistent failures** - If Selenium infrastructure errors persist after reruns, check the Selenium container health (`docker compose ps selenium`) and restart it if needed (`docker compose restart selenium`) before doing deeper investigations

### General

1. Always clean up temporary debug code (console.logs, window.* global exposures, debug hacks) before marking a task complete. Review all changes for leftover debugging artifacts.

## Build Verification

After editing JavaScript files, always run the Vite build (`docker compose exec vite npx vite build`) to verify no import path errors, missing exports, or syntax issues before reporting success.

## Development Commands

### Docker Execution Note

**CRITICAL:** All `docker` and `docker compose` commands must be run outside sandbox mode due to Docker socket access requirements. Always use `dangerouslyDisableSandbox: true` when running Docker commands.

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
docker exec u4i-local-vite npm run build  # production/dev build to src/static/dist/
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

## Architecture

### Backend Structure (`src/`)

Flask app factory pattern in `src/__init__.py` with `create_app()`. Config classes in `src/config.py`: `Config` (dev), `ConfigProd`, `ConfigTest`, `ConfigTestUI`.

**10 Flask blueprints** organized by domain:
- `splash` - auth (login, register, email validation, password reset)
- `utubs` - UTub CRUD
- `urls` - URL management within UTubs
- `members` - UTub member management
- `tags` (2 blueprints: `utub_tags`, `utub_url_tags`) - tag CRUD
- `users` - user profile, password change
- `contact` - contact form
- `system` - health check
- `assets` - static asset serving
- `debug` - dev-only debug routes (excluded in test/prod)

Each blueprint follows the pattern: `routes.py` (endpoints), `forms.py` (WTForms validation), `services/` (business logic), `constants.py`.

### Extensions (`src/extensions/`)

Custom Flask extensions registered on `app.extensions` and initialized via `init_app()`. Access them from route/service code using the safe getters in `src/extensions/extension_utils.py` (`safe_get_email_sender()`, `safe_get_notif_sender()`, `safe_get_url_validator()`).

- **`url_validation/url_validator.py`** - `UrlValidator`: Two-step URL processing used when users add URLs to UTubs. `normalize_url()` strips whitespace, prepends `https://` if no scheme, blocks credential-containing URLs (`user:pass@host`), and validates scheme against a whitelist. `validate_url()` parses with `ada_url` (Rust-based WHATWG URL parser), verifies hostname/TLD validity, and returns the canonicalized URL. Raises `InvalidURLError`, `URLWithCredentialsError`, or `AdaUrlParsingError`.
- **`email_sender/email_sender.py`** - `EmailSender`: Wraps the Mailjet REST API (`mailjet_rest.Client`) for transactional emails. Sends account email confirmations and password reset emails using Jinja2 templates from `src/templates/email_templates/`. Uses sandbox mode during tests. Production mode toggled via `in_production()`.
- **`notifications/notifications.py`** - `NotificationSender`: Sends webhook notifications (Discord) via HTTP POST. `send_notification()` is fire-and-forget (runs in a background `threading.Thread`). `send_contact_form_details()` is synchronous and returns success/failure. Non-production messages are wrapped with a testing disclaimer.

### Key Decorators (`src/api_common/auth_decorators.py`)

- `@email_validation_required` - requires login + validated email
- `@utub_membership_required` - requires membership in target UTub
- `@xml_http_request_only` - AJAX only (`X-Requested-With: XMLHttpRequest`)
- `@no_authenticated_users_allowed` - splash pages (logged-out only)

### Models (`src/models/`)

Core domain: `Users` -> `Utub_Members` (with `Member_Role`: CREATOR/EDITOR/VIEWER) -> `Utubs` -> `Utub_Urls` -> `Urls`. Tags: `Utub_Tags` <-> `Utub_Url_Tags` <-> `Utub_Urls`.

ORM is SQLAlchemy (1.4.x style) via Flask-SQLAlchemy. Database is PostgreSQL 16.3.

### Frontend Structure

JavaScript is organized as ES6 modules in `frontend/` and built by Vite. Entry points are `frontend/main.js` (home page) and `frontend/splash.js` (splash/auth pages). The `init_vite_app()` function in `src/__init__.py` handles manifest-based asset resolution for production and direct Vite dev server proxying for local dev.

jQuery (3.7.1) and Bootstrap (5.2.3) are loaded as global `<script>` tags and re-exported from `frontend/lib/globals.js` for use in modules.

Templates are Jinja2 in `src/templates/`.

### Security

- CSRF: Flask-WTF `CSRFProtect`. Forms use `csrf_token` field; AJAX uses `X-Csrftoken` header.
- Sessions: Redis-backed (or FileSystem fallback) via Flask-Session
- Rate limiting: Flask-Limiter with Redis backend (disabled in tests)
- CSP: Nonce-based inline script policy, set in `add_security_headers()`
- Passwords: Werkzeug `pbkdf2:sha256`

### API Pattern

Routes return HTML for page loads and JSON (`APIResponse`) for AJAX. JSON responses follow `{status, data, message}` shape. See `src/API_DOCUMENTATION.md` for full endpoint docs.

### Testing (`tests/`)

- `conftest.py` - fixtures, test DB setup, CSRF token helpers
- `models_for_test.py` - test data factories (users, UTubs, URLs, tags)
- `utils_for_test.py` - helpers (`clear_database()`, `get_csrf_token()`)
- CI runs 17 parallel test workers split by marker
- Config: `ConfigTest` (integration) / `ConfigTestUI` (Selenium, `SESSION_COOKIE_SECURE=False`)

### Docker

- `docker/Dockerfile` - production multi-stage build (Python 3.11-slim)
- `docker/Dockerfile.Local` - local dev
- `docker/Dockerfile.Vite` - Vite dev server container
- `docker/compose.local.yaml` - full local stack (web, vite, db, test-db, redis, selenium, workflow)
- `docker/compose.yaml` - production stack
- `docker/compose.dev.yaml` - dev server stack

### Environment Variables

Required: `SECRET_KEY`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `MAILJET_API_KEY`, `MAILJET_SECRET_KEY`. See `src/config.py` for the full list and `src/utils/strings/config_strs.py` for env var name constants.

### String Constants

All user-facing strings, model field names, and config keys are centralized in `src/utils/strings/` and `src/utils/constants.py`.
