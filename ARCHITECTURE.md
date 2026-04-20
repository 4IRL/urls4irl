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

TypeScript ES6 modules in `frontend/` built by Vite. jQuery (3.7.1) and Bootstrap (5.2.3) loaded as global `<script>` tags and re-exported from `frontend/lib/globals.ts`. Templates are Jinja2 in `backend/templates/`. `init_vite_app()` in `backend/__init__.py` handles manifest-based asset resolution.

### Entry Points

- **main.ts** — Home page: loads styles, jQuery plugins, CSRF, initial UTub state, then initializes all home modules
- **splash.ts** — Auth pages: jQuery plugins, CSRF, navbar, splash init, conditionally shows reset-password or email-validation modals
- **contact.ts** — Contact form with validation, AJAX POST, rate-limit fallback
- **error.ts** — Error page with refresh button (strips hash fragment)

### frontend/lib/ — Core Infrastructure

- **event-bus.ts** — Typed event emitter with `AppEvents` enum and `AppEventMap` payload interface (see Event Bus section below)
- **ajax.ts** — `ajaxCall()` wrapper with global 429 rate-limit redirect; `is429Handled()` guard for `.fail()` handlers
- **config.ts** — Loads app config (routes, constants, strings) from DOM-injected JSON; typed `AppConfig` with route functions
- **constants.ts** — Keyboard keys, form methods (CREATE/UPDATE), input types, tablet breakpoint (992px), icon sizes (ICON_SIZE_SM=20, ICON_SIZE_LG=30)
- **cookie-banner.ts** — Cookie consent banner, dismisses on interactive click or Enter
- **csrf.ts** — CSRF token in AJAX headers + global 429 handler via `ajaxPrefilter`
- **globals.ts** — Re-exports `$` and `bootstrap` from `window`; `getInputValue()` helper
- **initial-state.ts** — Loads initial UTub list from DOM script element into app store
- **jquery-plugins.ts** — Custom jQuery plugins: `offAndOn`, `onExact`, `offAndOnExact`, `removeClassStartingWith`, `showClassNormal/Flex`, `hideClass`, `enableTab/disableTab`
- **navbar-shared.ts** — Wires nav buttons with `data-route` to config URLs
- **page-utils.ts** — Replaces page content with AJAX HTML response (rate-limit pages)
- **security-check.ts** — XSS guard: redirects home if `<head>` is nearly empty

### frontend/store/ — State Management

- **app-store.ts** — Module-level state object with `getState()` / `setState()` / `resetStore()`. Fields: `utubs`, `activeUTubID`, `urls`, `tags` (UtubTag[]), `members` (MemberItem[]), `selectedTagIDs`, `utubOwnerID`, `isCurrentUserOwner`, `currentUserID`

### frontend/types/ — Type Definitions

- **api-helpers.d.ts** — `Schema<Name>` maps to OpenAPI schema components; `SuccessResponse<Op, Status>` maps operation+status to typed response body
- **url.ts** — `UtubUrlItem`, `UtubUrlDetail`, `UtubTagOnAddDelete`, `UtubTag` (from OpenAPI)
- **member.ts** — `MemberItem`, `MemberModifiedResponse`, `AddMemberRequest` (from OpenAPI)
- **utub.ts** — `UtubDetail` (with success envelope), `UtubSummaryItem` (from OpenAPI)

### frontend/logic/ — Pure Business Logic (No DOM)

- **deck-diffing.ts** — `diffIDLists()`: returns IDs to remove/add/update between old and new arrays
- **tag-filtering.ts** — `computeURLVisibility()`, `computeVisibleTagCounts()`, `sortTagsByCount()`
- **url-search.ts** — `filterURLsBySearchTerm()`: case-insensitive search against title and URL string
- **utub-search.ts** — `filterUTubsByName()`: case-insensitive name search
- **string-helpers.ts** — Re-exports `isEmptyString`
- **url-helpers.ts** — Re-exports `isValidURL`, `generateURLObj`, `modifyURLStringForDisplay`
- **utub-helpers.ts** — Re-exports `isValidUTubID`

### frontend/home/ — Home Page Modules

**Top-level shared modules:**
- **init.ts** — `setUIWhenNoUTubSelected()`, `resetHomePageToInitialState()`
- **btns-forms.ts** — `makeTextInput()`, `makeUpdateButton()`, `makeSubmitButton()`, `makeCancelButton()` with SVG icons; `initBtnsForms()` prevents form submission
- **visibility.ts** — `isHidden()`, `initVisibilityHandlers()` (tab focus, URL card focus styling)
- **navbar.ts** — `initNavbar()` sets up mobile nav buttons and toggler
- **collapsible-decks.ts** — Click-to-collapse/expand UTub/Member/Tag decks (desktop only, max 2 collapsed)
- **mobile.ts** — `isMobile()`, `initMobileLayout()`, mobile panel show/hide functions
- **window-events.ts** — Browser history (popstate) and page load (pageshow) for UTub selection state

**frontend/home/utubs/ — UTub Selector:**
- **deck.ts** — `buildUTubDeck()`, `resetUTubDeck()`, UTub event listeners
- **selectors.ts** — `getUTubInfo()` fetches full UTub data, `buildSelectedUTub()` populates all decks
- **create.ts** — UTub creation form and AJAX POST
- **delete.ts** — UTub deletion with confirmation
- **search.ts** — UTub name search with show/hide
- **stale-data.ts** — Stale data detection and handling
- **utils.ts** — `isValidUTubID()`, `getActiveUTubID()`, `isUTubSelected()`, `getNumOfUTubs()`, `getAllUTubs()`

**frontend/home/urls/ — URL Deck:**
- **deck.ts** — `resetURLDeck()`, `setURLDeckOnUTubSelected()`, `resetURLDeckOnDeleteUTub()`
- **search.ts** — URL search input with 200ms debounce, show/hide icon, card visibility, no-results message
- **validation.ts** — `isValidURL()` with protocol blocking, `generateURLObj()`
- **utils.ts** — `getNumOfURLs()`, `getNumOfVisibleURLs()`, arrow-key navigation
- **create-btns.ts** — Create URL button event listeners
- **access-all.ts** — Opens all visible URLs in new tabs
- **update-name.ts** — UTub name inline editing
- **update-description.ts** — UTub description inline editing

**frontend/home/urls/cards/ — URL Card Components:**
- **cards.ts** — `createURLBlock()` assembles full card; `updateURLAfterFindingStaleData()`
- **selection.ts** — `selectURLCard()`, `deselectURL()`, `getSelectedURLCard()`
- **create.ts** — URL creation form, validation, AJAX POST
- **delete.ts** — Delete confirmation modal, AJAX DELETE, DOM removal
- **get.ts** — `getUpdatedURL()` for stale-data checks
- **filtering.ts** — Tag-based URL visibility, tag count updates, `URL_TAG_FILTER_APPLIED` emit
- **copy.ts** — Clipboard copy with tooltip feedback
- **url-string.ts** — URL string display (clickable when selected) + edit form
- **url-title.ts** — URL title display + edit form
- **update-string.ts** — URL string update AJAX
- **update-title.ts** — URL title update AJAX
- **loading.ts** — Spinner show/hide with timeout
- **access.ts** — Open URL in new tab, warning modal for non-http
- **corner-access.ts** — Go-to-URL SVG icon in card corner
- **utils.ts** — `isEmptyString()`, alternating row colors, tabbable element helpers
- **options/** — Action buttons: `btns.ts` (assembler), `delete-btn.ts`, `copy-btn.ts`, `access-btn.ts`, `edit-string-btn.ts`, `tag-btn.ts`

**frontend/home/urls/tags/ — URL-Level Tags:**
- **tags.ts** — `createTagBadgesAndWrap()`, individual tag badge with delete button
- **create.ts** — Add tag to URL form and AJAX
- **delete.ts** — Remove tag from URL

**frontend/home/tags/ — UTub-Level Tag Deck:**
- **deck.ts** — `setTagDeckOnUTubSelected()`, `resetTagDeck()`, `updateTagDeck()` (diff-based sync)
- **tags.ts** — `buildTagFilterInDeck()` creates clickable filter with count; `toggleTagFilterSelected()`
- **create.ts** — Create UTub tag form and AJAX with field-level error dispatch
- **delete.ts** — Delete UTub tag
- **utils.ts** — `currentTagDeckIDs()`, `isTagInUTubTagDeck()`, `isATagSelected()`
- **unselect-all.ts** — Clear all tag filter selections
- **update-all.ts** — Bulk tag update operations

**frontend/home/members/ — Member Deck:**
- **deck.ts** — `setMemberDeckOnUTubSelected()`, `resetMemberDeck()`, `updateMemberDeck()` (diff-based)
- **members.ts** — `createOwnerBadge()`, `createMemberBadge()` badge factories
- **create.ts** — Add member form and AJAX with error handling
- **delete.ts** — Remove member / leave UTub with modals

**frontend/splash/ — Auth Pages:**
- **init.ts** — Form setup for login/register/forgot-password, modal switching, rate-limit handling
- **navbar.ts** — Mobile navbar toggler
- **login-form.ts**, **register-form.ts**, **forgot-password-form.ts**, **email-validation-form.ts**, **reset-password-form.ts** — Individual auth form modules

### Event Bus Reference (`frontend/lib/event-bus.ts`)

All inter-module communication uses typed events:

| Event | Payload | Emitted by | Consumed by |
|---|---|---|---|
| `UTUB_SELECTED` | `{utubID, utubName, urls[], tags[], members[], utubOwnerID, isCurrentUserOwner, currentUserID}` | utubs/selectors | All decks, mobile, search |
| `UTUB_DELETED` | `{utubID}` | utubs/delete | URL/tag/member decks |
| `TAG_FILTER_CHANGED` | `{selectedTagIDs[]}` | tags/tags | urls/cards/filtering |
| `TAG_DELETED` | `{utubTagID}` | tags/delete | urls/cards/filtering |
| `STALE_DATA_DETECTED` | `{utubID, urls[], tags[], members[]}` | utubs/stale-data | All decks |
| `URL_SEARCH_VISIBILITY_CHANGED` | void | urls/search | urls/cards/filtering |
| `URL_TAG_FILTER_APPLIED` | void | urls/cards/filtering | urls/search |

### Established TypeScript Patterns

**Type-guard dispatch** — For routing field-level validation errors. Define `const FIELDS = [...] as const`, derive union type, create `isFieldName(key): key is FieldName` guard, use in error loop. See `frontend/splash/init.ts`, `frontend/home/tags/create.ts`.

**is429Handled** — In every `.fail()` handler: `if (is429Handled(xhr)) return;` skips custom error UI when the global 429 handler already redirected. Located in `frontend/lib/ajax.ts`.

**Schema<>/SuccessResponse<>** — Type helpers in `frontend/types/api-helpers.d.ts`. Usage: `type Req = Schema<"AddTagRequest">; type Res = SuccessResponse<"createUtubTag">;` — eliminates verbose `components["schemas"]` chains.

**offAndOnExact** — jQuery plugin in `frontend/lib/jquery-plugins.ts`. Combines `.off()` + `.onExact()` to unbind stale listeners and rebind only on the exact element (not bubbled children). Critical for elements shown/hidden repeatedly.

**AJAX call pattern** — All calls go through `ajaxCall(method, url, data)` which returns chainable jqXHR. Chain `.done()` with typed response and status check, `.fail()` with `is429Handled()` guard then status-code dispatch.

**App store** — Simple module-level state in `frontend/store/app-store.ts`. `getState()` returns shallow copy, `setState()` merges partial updates via `Object.assign()`.

**Vitest mock pattern** — `vi.mock("../module.js", ...)` at file top (hoisted), `vi.importActual()` for partial mocks inside `it()` blocks only, `createMockJqXHRChainable()` from `frontend/__tests__/helpers/mock-jquery.ts` for AJAX mocks, `vi.clearAllMocks()` in `beforeEach`.

## Security

- CSRF: Flask-WTF `CSRFProtect`. Forms use `csrf_token` field; AJAX uses `X-Csrftoken` header.
- Sessions: Redis-backed (or FileSystem fallback) via Flask-Session
- Rate limiting: Flask-Limiter with Redis backend (disabled in tests)
- CSP: Nonce-based inline script policy, set in `add_security_headers()`
- Passwords: Werkzeug `pbkdf2:sha256`

## API Pattern

Routes return HTML for page loads and JSON (`APIResponse`) for AJAX. JSON responses follow `{status, data, message}` shape. AJAX write endpoints (`utubs`, `urls`, `members`, `tags`) and splash endpoints (`login`, `register`, `forgot-password`, `reset-password`) expect `Content-Type: application/json` with the CSRF token in the `X-Csrftoken` request header. The contact blueprint still uses `application/x-www-form-urlencoded` with WTForms. See `backend/API_DOCUMENTATION.md` for full endpoint docs.

## Testing (`tests/`)

Config: `ConfigTest` (integration) / `ConfigTestUI` (Selenium, `SESSION_COOKIE_SECURE=False`). CI runs 17 parallel test workers split by marker.

### Root Test Files

- `conftest.py` — Session fixtures (`build_app`, `worker_db_uri`, `worker_redis_uri`), per-test fixtures (`app`, `client`, `db_transaction`), auth flows (`register_first_user`, `login_first_user_with_register`, etc.), UTub/member setup fixtures
- `models_for_test.py` — Test data factories: `valid_user_1/2/3`, `valid_empty_utub_1`, `all_tags`, `maximum_tags`
- `utils_for_test.py` — `clear_database()`, `get_csrf_token()`

### tests/unit/ — Backend Unit Tests (13 files)

Covers: API response/route decorators, auth decorators, DB existence, error handlers, input sanitization, model serialization, URL validation, OpenAPI helpers. Marker: `unit`.

### tests/integration/ — Backend Integration Tests

Organized by domain with per-feature conftest files:
- `splash/` (marker: `splash`) — Auth flows: login, register, forgot/reset password, email validation
- `utubs/` (marker: `utubs`) — UTub CRUD
- `utubmembers/` (marker: `members`) — Member add/remove
- `utuburls/` (marker: `urls`) — URL CRUD within UTubs
- `utubtags/` (marker: `tags`) — Tag CRUD
- `account_and_settings/` (marker: `account_and_support`) — Profile, password change

### tests/functional/ — UI/Selenium Tests

**Shared infrastructure (tests/functional/ root):**
- `conftest.py` — Session-scoped: `build_app`, `build_driver`, browser fixtures (`browser`, `browser_mobile_portrait`), mock data fixtures (`create_test_users`, `create_test_utubs`, etc.)
- `locators.py` — Page object locator classes:
  - `GenericPageLocator` — Nav, footer, modals, error handlers
  - `HomePageLocators(GenericPageLocator)` — UTubs/URLs/Tags/Members decks, all modals (100+ selectors)
  - `SplashPageLocators(GenericPageLocator)` — Login/register/forgot-password modals (75+ selectors)
  - `ModalLocators` — Generic modal elements
- `selenium_utils.py` — 40+ helpers: `wait_then_click_element`, `wait_for_element_presence`, `clear_then_send_keys`, `wait_until_visible`, `wait_for_class_to_be_removed`
- `db_utils.py` — 20+ DB helpers: `get_utub_this_user_created`, `create_test_searchable_utubs`, `add_mock_urls`, `get_tag_on_url_in_utub`
- `assert_utils.py` — Common assertion utilities
- `login_utils.py` — Login/authentication helpers
- `ui_test_setup.py` — App initialization and server setup

**Feature-specific test directories** (each has its own `selenium_utils.py`):
- `splash_ui/` (marker: `splash_ui`) — Login, register, password reset, email validation
- `home_ui/` (marker: `home_ui`) — Dashboard page
- `utubs_ui/` (marker: `utubs_ui`) — UTub create/update/delete. Helpers: `create_utub()`, `update_utub_name()`, `update_utub_description()`
- `urls_ui/` (markers: `urls_ui`, `create_urls_ui`, `update_urls_ui`) — URL CRUD, search, copy. Helpers: `create_url()`, `open_url_search_box()`, `ClipboardMockHelper`
- `tags_ui/` (marker: `tags_ui`) — Tag/filter tests. Helpers: `add_tag_to_url()`, `get_utub_tag_filter_selector()`
- `members_ui/` (marker: `members_ui`) — Member management
- `mobile_ui/` (marker: `mobile_ui`) — Mobile viewport tests

### Frontend Tests (vitest)

- `frontend/__tests__/helpers/mock-jquery.ts` — Mock factories: `createMockJqXHR()`, `createMockJqXHRChainable()`, `createImmediateAlwaysJqXHR()`, `createMockModal()`
- Tests live in `__tests__/` subdirectories alongside source (e.g., `frontend/home/tags/__tests__/tags.test.ts`)
- `frontend/logic/__tests__/` — Pure logic tests (deck-diffing, tag-filtering, url-search, utub-search)

### Test Constants

- `backend/utils/strings/ui_testing_strs.py` — `UI_TEST_STRINGS` class: test usernames, passwords, URLs, search keywords, UTub/tag names, cookie banner text
- `backend/cli/mock_constants.py` — Mock data templates (USERNAME_BASE, MOCK_URL_STRINGS, etc.)
- `tests/models_for_test.py` — Typed test data objects

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
