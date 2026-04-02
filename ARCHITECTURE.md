# Architecture

Reference document for urls4irl codebase structure. Not loaded into Claude Code context automatically — consult when navigating unfamiliar parts of the codebase.

## Backend Structure (`backend/`)

Flask app factory pattern in `backend/__init__.py` with `create_app()`. Config classes in `backend/config.py`: `Config` (dev), `ConfigProd`, `ConfigTest`, `ConfigTestUI`.

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

Each blueprint follows the pattern: `routes.py` (endpoints), `services/` (business logic), `constants.py`. The `contact` blueprint additionally has `forms.py` (WTForms) for HTML form validation. All AJAX blueprints (`utubs`, `urls`, `members`, `tags`) and the `splash` blueprint use Pydantic schemas in `backend/schemas/` for JSON request validation.

## Extensions (`backend/extensions/`)

Custom Flask extensions registered on `app.extensions` and initialized via `init_app()`. Access them from route/service code using the safe getters in `backend/extensions/extension_utils.py` (`safe_get_email_sender()`, `safe_get_notif_sender()`, `safe_get_url_validator()`).

- **`url_validation/url_validator.py`** - `UrlValidator`: Two-step URL processing used when users add URLs to UTubs. `normalize_url()` strips whitespace, prepends `https://` if no scheme, blocks credential-containing URLs (`user:pass@host`), and validates scheme against a whitelist. `validate_url()` parses with `ada_url` (Rust-based WHATWG URL parser), verifies hostname/TLD validity, and returns the canonicalized URL. Raises `InvalidURLError`, `URLWithCredentialsError`, or `AdaUrlParsingError`.
- **`email_sender/email_sender.py`** - `EmailSender`: Wraps the Mailjet REST API (`mailjet_rest.Client`) for transactional emails. Sends account email confirmations and password reset emails using Jinja2 templates from `backend/templates/email_templates/`. Uses sandbox mode during tests. Production mode toggled via `in_production()`.
- **`notifications/notifications.py`** - `NotificationSender`: Sends webhook notifications (Discord) via HTTP POST. `send_notification()` is fire-and-forget (runs in a background `threading.Thread`). `send_contact_form_details()` is synchronous and returns success/failure. Non-production messages are wrapped with a testing disclaimer.

## Schemas (`backend/schemas/`)

Pydantic models for request parsing and response serialization used by the AJAX blueprints.

- **`requests/utubs.py`** - `CreateUTubRequest`, `UpdateUTubNameRequest`, `UpdateUTubDescriptionRequest`
- **`requests/urls.py`** - `CreateURLRequest`, `UpdateURLStringRequest`, `UpdateURLTitleRequest`
- **`requests/members.py`** - `AddMemberRequest`
- **`requests/tags.py`** - `AddTagRequest`
- **`requests/_sanitize.py`** - `SanitizedStr` / `OptionalSanitizedStr`: Pydantic annotated types that reject input containing HTML special characters (any value that sanitization would modify raises a `ValidationError`).
- **`utubs.py`, `urls.py`, `tags.py`, `users.py`** - Response models passed as `APIResponse.data`; serialized via `model_dump(by_alias=True)`.

## Key Decorators (`backend/api_common/auth_decorators.py`)

- `@email_validation_required` - requires login + validated email
- `@utub_membership_required` - requires membership in target UTub
- `@no_authenticated_users_allowed` - splash pages (logged-out only)
- **`backend/api_common/parse_request.py`** - `@api_route(request_schema, response_schema, error_message, error_code, ajax_required)`: unified decorator for API routes. Enforces AJAX (`X-Requested-With: XMLHttpRequest`) by default (`ajax_required=True`); splash POST routes, contact, and health opt out with `ajax_required=False`. When `request_schema` is provided, validates `request.get_json()` against a Pydantic schema and injects a kwarg named after the schema (e.g. `LoginRequest` → `login_request`); returns 400 on missing body or validation failure. `response_schema` declares the expected response type for future OpenAPI generation.

## Models (`backend/models/`)

Core domain: `Users` -> `Utub_Members` (with `Member_Role`: CREATOR/EDITOR/VIEWER) -> `Utubs` -> `Utub_Urls` -> `Urls`. Tags: `Utub_Tags` <-> `Utub_Url_Tags` <-> `Utub_Urls`.

ORM is SQLAlchemy (1.4.x style) via Flask-SQLAlchemy. Database is PostgreSQL 16.3.

## Frontend Structure

JavaScript is organized as ES6 modules in `frontend/` and built by Vite. Entry points are `frontend/main.js` (home page) and `frontend/splash.js` (splash/auth pages). The `init_vite_app()` function in `backend/__init__.py` handles manifest-based asset resolution for production and direct Vite dev server proxying for local dev.

jQuery (3.7.1) and Bootstrap (5.2.3) are loaded as global `<script>` tags and re-exported from `frontend/lib/globals.js` for use in modules.

Templates are Jinja2 in `backend/templates/`.

## Security

- CSRF: Flask-WTF `CSRFProtect`. Forms use `csrf_token` field; AJAX uses `X-Csrftoken` header.
- Sessions: Redis-backed (or FileSystem fallback) via Flask-Session
- Rate limiting: Flask-Limiter with Redis backend (disabled in tests)
- CSP: Nonce-based inline script policy, set in `add_security_headers()`
- Passwords: Werkzeug `pbkdf2:sha256`

## API Pattern

Routes return HTML for page loads and JSON (`APIResponse`) for AJAX. JSON responses follow `{status, data, message}` shape. AJAX write endpoints (`utubs`, `urls`, `members`, `tags`) and splash endpoints (`login`, `register`, `forgot-password`, `reset-password`) expect `Content-Type: application/json` with the CSRF token in the `X-Csrftoken` request header. The contact blueprint still uses `application/x-www-form-urlencoded` with WTForms. See `backend/API_DOCUMENTATION.md` for full endpoint docs.

## Testing (`tests/`)

- `conftest.py` - fixtures, test DB setup, CSRF token helpers
- `models_for_test.py` - test data factories (users, UTubs, URLs, tags)
- `utils_for_test.py` - helpers (`clear_database()`, `get_csrf_token()`)
- CI runs 17 parallel test workers split by marker
- Config: `ConfigTest` (integration) / `ConfigTestUI` (Selenium, `SESSION_COOKIE_SECURE=False`)

## Docker

- `docker/Dockerfile` - production multi-stage build (Python 3.11-slim)
- `docker/Dockerfile.Local` - local dev
- `docker/Dockerfile.Vite` - Vite dev server container
- `docker/compose.local.yaml` - full local stack (web, vite, db, test-db, redis, selenium, workflow)
- `docker/compose.yaml` - production stack
- `docker/compose.dev.yaml` - dev server stack

## Environment Variables

Required: `SECRET_KEY`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `MAILJET_API_KEY`, `MAILJET_SECRET_KEY`. See `backend/config.py` for the full list and `backend/utils/strings/config_strs.py` for env var name constants.

## String Constants

All user-facing strings, model field names, and config keys are centralized in `backend/utils/strings/` and `backend/utils/constants.py`.
