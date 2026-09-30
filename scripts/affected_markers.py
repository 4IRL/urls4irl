"""Map a branch diff to the pytest markers it affects.

Feeds `make affected-markers` (print the selection and why),
`make test-affected` (run the selected integration markers, then the UI
markers) and `make test-agent` (typecheck + vitest + test-affected).

The changed files are the diff against the `git merge-base <base> HEAD`
(committed, staged and unstaged), plus untracked files. Each file resolves in
this order:
1. `NO_IMPACT_GLOBS` (minus `NO_IMPACT_EXEMPT`) -> no markers.
2. `HOST_STATIC_GLOBS` -> sets `host_static`, then keeps resolving.
3. `BROAD_GLOBS` -> everything.
4. A test file (`tests/**/test_*.py`) -> the markers in its own text; a
   deleted or unmarked one falls through to its `PATH_MARKERS` dir row.
5. Registry rows whose handler, services, schemas or templates name the file
   -> each row's `BLUEPRINT_MARKERS` (+ `ENDPOINT_MARKER_OVERRIDES`).
6. The first matching `PATH_MARKERS` row, unioned with step 5.
7. Unmatched -> everything. Selection never silently picks nothing.

Globs use `fnmatch`, so `*` also matches `/`. Stdlib only: it runs on the
host under bare mise python.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT: Path = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY: Path = REPO_ROOT / "docs" / "endpoints" / "endpoint-registry.json"
PYTEST_INI: Path = REPO_ROOT / "pytest.ini"

UI_SUFFIX: str = "_ui"
NO_IMPACT_REASON: str = "no test impact"
UNMAPPED_REASON: str = "unmapped path — safe default"
REASON_ENDPOINT_LIMIT: int = 3
_MARK_PATTERN: re.Pattern[str] = re.compile(r"pytest\.mark\.(\w+)")
_MARKERS_HEADER_PATTERN: re.Pattern[str] = re.compile(r"^markers\s*=")
_SKIPPED_SCHEMA_MODULES: frozenset[str] = frozenset({"backend.schemas.errors"})

MarkerRow = tuple[str, tuple[str, ...]]


class SelectionError(RuntimeError):
    """The changed-file set cannot be computed (e.g. an unresolvable base)."""


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def _union(*groups: tuple[str, ...]) -> tuple[str, ...]:
    """Concatenate marker groups, dropping repeats and keeping first-seen order."""
    return tuple(dict.fromkeys(marker for group in groups for marker in group))


_SPLASH: tuple[str, ...] = ("splash", "splash_ui", "mobile_ui")
_UTUBS: tuple[str, ...] = ("utubs", "utubs_ui", "home_ui", "mobile_ui")
_MEMBERS: tuple[str, ...] = ("members", "members_ui")
_URLS: tuple[str, ...] = (
    "urls",
    "urls_ui",
    "create_urls_ui",
    "update_urls_ui",
    "mobile_ui",
)
_TAGS: tuple[str, ...] = ("tags", "tags_ui", "mobile_ui")
_SEARCH: tuple[str, ...] = ("urls", "search_ui")
_USERS: tuple[str, ...] = ("account_and_support", "settings_ui")
_CONTACT: tuple[str, ...] = ("account_and_support",)
_ADMIN: tuple[str, ...] = ("admin", "admin_ui")
_METRICS: tuple[str, ...] = ("cli", "metrics_ui")
_SYSTEM: tuple[str, ...] = ("cli",)
_API_V1: tuple[str, ...] = ("mobile_api",)

BLUEPRINT_MARKERS: dict[str, tuple[str, ...]] = {
    "splash": _SPLASH,
    "utubs": _UTUBS,
    "members": _MEMBERS,
    "urls": _URLS,
    "utub_tags": _TAGS,
    "utub_url_tags": _TAGS,
    "search": _SEARCH,
    "users": _USERS,
    "contact": _CONTACT,
    "admin": _ADMIN,
    "metrics": _METRICS,
    "system": _SYSTEM,
    "api_v1": _API_V1,
}

# Added on top of the row's blueprint markers. The admin metrics page's own
# integration tests (tests/integration/system/) are marked `cli`.
ENDPOINT_MARKER_OVERRIDES: dict[str, tuple[str, ...]] = {
    "admin.admin_metrics": ("metrics_ui", "cli"),
}

NO_IMPACT_GLOBS: tuple[str, ...] = (
    "*.md",
    ".github/*",
    ".claude/*",
    "LICENSE",
    ".gitignore",
    ".dockerignore",
    ".git-blame-ignore-revs",
    ".env.example",
    ".gitmodules",
    ".pre-commit-config.yaml",
    "nginx/*",
    "docs/runbooks/*",
    "migrations/README",
    "frontend/.prettierignore",
    "frontend/eslint.config.js",
    # vitest files run under make test-js, not pytest.
    "frontend/*__tests__/*",
)

# Match a NO_IMPACT glob but are read by tests, so they resolve normally.
NO_IMPACT_EXEMPT: tuple[str, ...] = ("docs/endpoints/ENDPOINT_REGISTRY.md",)

# Everything: shared fixtures, app factory, models, shared strings/schemas,
# layout templates, dependency pins and frontend build config.
BROAD_GLOBS: tuple[str, ...] = (
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/integration/conftest.py",
    "tests/functional/conftest.py",
    "tests/utils_for_test.py",
    "tests/models_for_test.py",
    "tests/integration/utils.py",
    "tests/functional/playwright_utils.py",
    "tests/functional/playwright_assert_utils.py",
    "tests/functional/playwright_login_utils.py",
    "tests/functional/db_utils.py",
    "tests/functional/locators.py",
    "tests/functional/ui_test_setup.py",
    "tests/functional/metrics_helpers/*",
    "tests/integration/system/metrics_helpers.py",
    # Imported by tests/functional/conftest.py, so as broad as that conftest.
    "tests/functional/urls_ui/playwright_utils.py",
    "backend/__init__.py",
    "backend/config.py",
    "backend/db.py",
    "backend/app_logger.py",
    "run.py",
    "backend/models/*",
    "backend/api_common/*",
    "backend/utubs/guards.py",
    "backend/schemas/__init__.py",
    "backend/schemas/requests/__init__.py",
    "backend/schemas/base.py",
    "backend/schemas/errors.py",
    "backend/schemas/requests/_sanitize.py",
    "backend/utils/__init__.py",
    "backend/utils/all_routes.py",
    "backend/utils/oauth_config.py",
    "backend/utils/mailjet_utils.py",
    "backend/utils/constants.py",
    "backend/utils/session_utils.py",
    "backend/utils/db_table_names.py",
    "backend/utils/datetime_utils.py",
    "backend/utils/db_uri_builder.py",
    "backend/utils/short_urls.py",
    "backend/utils/strings/__init__.py",
    "backend/utils/strings/ui_testing_strs.py",
    "backend/utils/strings/model_strs.py",
    "backend/utils/strings/json_strs.py",
    "backend/utils/strings/form_strs.py",
    "backend/utils/strings/html_identifiers.py",
    "backend/utils/strings/config_strs.py",
    "backend/utils/strings/url_validation_strs.py",
    "backend/extensions/extension_utils.py",
    "backend/extensions/metrics/*",
    "backend/templates/pages/layout.html",
    "backend/templates/_config.html",
    "backend/templates/components/head/*",
    "backend/templates/components/nav/*",
    # Included by layout.html.
    "backend/templates/components/cookieBanner.html",
    "backend/templates/components/footer.html",
    "scripts/testrun_resources.py",
    "requirements/*",
    "pyproject.toml",
    "pytest.ini",
    ".mise.toml",
    "migrations/env.py",
    "migrations/alembic.ini",
    "frontend/package.json",
    "frontend/pnpm-lock.yaml",
    "frontend/pnpm-workspace.yaml",
    "frontend/vite.config.ts",
    "frontend/vitest.config.ts",
    "frontend/postcss.config.js",
    "frontend/setup-vendor.sh",
    "frontend/test-setup.ts",
    "frontend/tsconfig*.json",
    "frontend/lib/*",
    "frontend/store/*",
    "frontend/types/*",
    "frontend/styles/base.css",
    "frontend/styles/tokens.css",
)

# Checked by `make test-host-static` (host-only tests that skip inside web).
HOST_STATIC_GLOBS: tuple[str, ...] = (
    "Makefile",
    "docker/*",
    "scripts/token_budget.py",
    "scripts/capacity.py",
    "scripts/spoke_ports.py",
    "tests/unit/test_makefile_profiles.py",
    "tests/unit/test_compose_hub.py",
    "tests/unit/test_compose_profiles.py",
    "tests/unit/test_playwright_entrypoint.py",
)

# UI test directories -> the markers their files carry. Five host mobile-only
# files marked just `mobile_ui`; urls_ui hosts create_/update_urls_ui files.
_ADMIN_UI_DIR: tuple[str, ...] = ("admin_ui",)
_HOME_UI_DIR: tuple[str, ...] = ("home_ui", "mobile_ui")
_MEMBERS_UI_DIR: tuple[str, ...] = ("members_ui",)
_METRICS_UI_DIR: tuple[str, ...] = ("metrics_ui",)
_SEARCH_UI_DIR: tuple[str, ...] = ("search_ui",)
_SETTINGS_UI_DIR: tuple[str, ...] = ("settings_ui",)
_SPLASH_UI_DIR: tuple[str, ...] = ("splash_ui", "mobile_ui")
_TAGS_UI_DIR: tuple[str, ...] = ("tags_ui", "mobile_ui")
_URLS_UI_DIR: tuple[str, ...] = (
    "urls_ui",
    "create_urls_ui",
    "update_urls_ui",
    "mobile_ui",
)
_UTUBS_UI_DIR: tuple[str, ...] = ("utubs_ui", "mobile_ui")
_HOME_DECKS_UI: tuple[str, ...] = _union(
    _HOME_UI_DIR, _UTUBS_UI_DIR, _URLS_UI_DIR, _TAGS_UI_DIR, _MEMBERS_UI_DIR
)

# Ordered, first match wins: more specific globs come first.
PATH_MARKERS: tuple[MarkerRow, ...] = (
    # Host-static only: HOST_STATIC_GLOBS already set host_static.
    ("Makefile", ()),
    ("docker/*", ()),
    ("docs/endpoints/endpoint-registry.json", ("unit", "cli")),
    ("docs/endpoints/ENDPOINT_REGISTRY.md", ("unit", "cli")),
    # --- tests -----------------------------------------------------------
    ("tests/unit/*", ("unit",)),
    ("tests/integration/account_and_settings/*", ("account_and_support",)),
    ("tests/integration/admin/*", ("admin",)),
    ("tests/integration/cli/*", ("cli",)),
    ("tests/integration/mobile_api/*", ("mobile_api",)),
    ("tests/integration/search/*", ("urls",)),
    ("tests/integration/splash/*", ("splash",)),
    ("tests/integration/system/*", ("cli",)),
    ("tests/integration/utubmembers/*", ("members",)),
    ("tests/integration/utubs/*", ("utubs",)),
    ("tests/integration/utubtags/*", ("tags",)),
    ("tests/integration/utuburls/*", ("urls",)),
    # Per-dir UI helpers imported by other UI dirs: the importers' markers.
    (
        "tests/functional/members_ui/playwright_utils.py",
        _union(_MEMBERS_UI_DIR, _HOME_UI_DIR, _TAGS_UI_DIR, _UTUBS_UI_DIR),
    ),
    (
        "tests/functional/metrics_ui/playwright_utils.py",
        _union(_METRICS_UI_DIR, _ADMIN_UI_DIR),
    ),
    (
        "tests/functional/search_ui/playwright_utils.py",
        _union(_SEARCH_UI_DIR, _HOME_UI_DIR),
    ),
    (
        "tests/functional/tags_ui/*_utils.py",
        _union(_TAGS_UI_DIR, _HOME_UI_DIR, _URLS_UI_DIR, _UTUBS_UI_DIR),
    ),
    (
        "tests/functional/urls_ui/playwright_login_utils.py",
        _union(_URLS_UI_DIR, _TAGS_UI_DIR),
    ),
    (
        "tests/functional/utubs_ui/playwright_utils.py",
        _union(_UTUBS_UI_DIR, _HOME_UI_DIR, _TAGS_UI_DIR, _URLS_UI_DIR),
    ),
    ("tests/functional/admin_ui/*", _ADMIN_UI_DIR),
    ("tests/functional/home_ui/*", _HOME_UI_DIR),
    ("tests/functional/members_ui/*", _MEMBERS_UI_DIR),
    ("tests/functional/metrics_ui/*", _METRICS_UI_DIR),
    ("tests/functional/search_ui/*", _SEARCH_UI_DIR),
    ("tests/functional/settings_ui/*", _SETTINGS_UI_DIR),
    ("tests/functional/splash_ui/*", _SPLASH_UI_DIR),
    ("tests/functional/tags_ui/*", _TAGS_UI_DIR),
    ("tests/functional/urls_ui/*", _URLS_UI_DIR),
    ("tests/functional/utubs_ui/*", _UTUBS_UI_DIR),
    # --- backend extensions ------------------------------------------------
    ("backend/extensions/url_validation/*", ("urls", "unit")),
    ("backend/extensions/email_sender/*", ("splash", "account_and_support")),
    ("backend/extensions/audit/*", ("admin",)),
    ("backend/extensions/notifications/*", ("unit", "cli")),
    ("backend/extensions/request_timing.py", ("unit", "cli")),
    # --- per-domain strings (filename prefix) -------------------------------
    ("backend/utils/strings/admin_metrics_strs.py", _union(("unit",), _METRICS)),
    ("backend/utils/strings/metrics_strs.py", _union(("unit",), _METRICS)),
    ("backend/utils/strings/admin_portal_strs.py", _union(("unit",), _ADMIN)),
    ("backend/utils/strings/api_auth_strs.py", _union(("unit",), _API_V1)),
    ("backend/utils/strings/email_validation_strs.py", _union(("unit",), _SPLASH)),
    ("backend/utils/strings/reset_password_strs.py", _union(("unit",), _SPLASH)),
    ("backend/utils/strings/splash_*_strs.py", _union(("unit",), _SPLASH)),
    ("backend/utils/strings/oauth_strs.py", _union(("unit",), _SPLASH, _USERS)),
    (
        "backend/utils/strings/onboarding_strs.py",
        _union(("unit",), _UTUBS_UI_DIR, _MEMBERS_UI_DIR, _TAGS_UI_DIR),
    ),
    ("backend/utils/strings/openapi_strs.py", ("unit", "cli")),
    ("backend/utils/strings/search_strs.py", _union(("unit",), _SEARCH)),
    ("backend/utils/strings/tag_strs.py", _union(("unit",), _TAGS)),
    ("backend/utils/strings/url_strs.py", _union(("unit",), _URLS)),
    ("backend/utils/strings/user_settings_strs.py", _union(("unit",), _USERS)),
    ("backend/utils/strings/user_strs.py", _union(("unit",), _USERS)),
    ("backend/utils/strings/utub_strs.py", _union(("unit",), _UTUBS)),
    # --- per-domain schemas (response + request modules) --------------------
    ("backend/schemas/admin_actions.py", ("unit", "admin")),
    ("backend/schemas/requests/admin_actions.py", ("unit", "admin")),
    ("backend/schemas/api_v1.py", ("unit", "mobile_api")),
    ("backend/schemas/requests/api_auth.py", ("unit", "mobile_api")),
    ("backend/schemas/contact.py", ("unit", "account_and_support")),
    ("backend/schemas/requests/contact.py", ("unit", "account_and_support")),
    ("backend/schemas/exports.py", ("unit", "account_and_support")),
    ("backend/schemas/metrics.py", ("unit", "cli")),
    ("backend/schemas/requests/metrics.py", ("unit", "cli")),
    ("backend/schemas/search.py", ("unit", "urls")),
    ("backend/schemas/requests/search.py", ("unit", "urls")),
    ("backend/schemas/system.py", ("unit", "cli")),
    ("backend/schemas/tags.py", ("unit", "tags")),
    ("backend/schemas/requests/tags.py", ("unit", "tags")),
    ("backend/schemas/urls.py", ("unit", "urls")),
    ("backend/schemas/requests/urls.py", ("unit", "urls")),
    ("backend/schemas/users.py", ("unit", "account_and_support")),
    ("backend/schemas/requests/users.py", ("unit", "account_and_support")),
    ("backend/schemas/utubs.py", ("unit", "utubs")),
    ("backend/schemas/requests/utubs.py", ("unit", "utubs")),
    ("backend/schemas/requests/members.py", ("unit", "members")),
    ("backend/schemas/requests/splash.py", ("unit", "splash")),
    # --- templates (includes are not in the registry: dir convention) -------
    ("backend/templates/components/home/UTubDeck/*", _UTUBS_UI_DIR),
    ("backend/templates/components/home/URLDeck/*", _URLS_UI_DIR),
    ("backend/templates/components/home/TagsDeck/*", _TAGS_UI_DIR),
    ("backend/templates/components/home/MemberDeck/*", _MEMBERS_UI_DIR),
    ("backend/templates/components/home/SearchMode/*", _SEARCH_UI_DIR),
    ("backend/templates/components/splash/*", _SPLASH_UI_DIR),
    ("backend/templates/components/admin/*", _ADMIN),
    ("backend/templates/admin_portal/*", _ADMIN),
    ("backend/templates/error_pages/*", ("splash_ui",)),
    ("backend/templates/email_templates/*", ("splash", "account_and_support")),
    ("backend/templates/modals/splashModals.html", _SPLASH_UI_DIR),
    ("backend/templates/modals/transferOwnerModal.html", ("members_ui", "utubs_ui")),
    ("backend/templates/modals/homeModalBase.html", _HOME_DECKS_UI),
    ("backend/templates/pages/home.html", _union(_HOME_DECKS_UI, _SEARCH_UI_DIR)),
    ("backend/templates/pages/splash.html", _SPLASH_UI_DIR),
    ("backend/templates/pages/settings.html", _SETTINGS_UI_DIR),
    ("backend/templates/pages/admin_metrics.html", _METRICS_UI_DIR),
    ("backend/templates/pages/contact_us.html", _CONTACT),
    ("backend/templates/pages/privacy_policy.html", ("splash_ui",)),
    ("backend/templates/pages/terms_and_conditions.html", ("splash_ui",)),
    # --- backend domains (same markers as their blueprint) ------------------
    ("backend/testing/*", _union(_SPLASH, _USERS)),
    # Imported by splash (OAuth linking), users and members services.
    ("backend/utils/reauth_throttle.py", _union(_SPLASH, _USERS, _MEMBERS)),
    ("backend/splash/*", _SPLASH),
    ("backend/utubs/*", _UTUBS),
    ("backend/members/*", _MEMBERS),
    ("backend/urls/*", _URLS),
    # backend/tags/ serves the utub_tags and utub_url_tags blueprints.
    ("backend/tags/*", _TAGS),
    ("backend/search/*", _SEARCH),
    ("backend/users/*", _USERS),
    ("backend/contact/*", _CONTACT),
    ("backend/admin/*", _ADMIN),
    ("backend/metrics/*", _union(_METRICS, ("unit",))),
    ("backend/system/*", _SYSTEM),
    ("backend/api_v1/*", _API_V1),
    ("backend/cli/*", ("cli", "unit")),
    ("backend/endpoint_registry/*", ("unit", "cli")),
    ("migrations/versions/*", ("cli",)),
    ("migrations/script.py.mako", ("cli",)),
    # --- frontend (vitest files run under make test-js, not pytest) ---------
    ("frontend/vite-env.d.ts", ()),
    ("frontend/admin/metrics-*", _METRICS_UI_DIR),
    ("frontend/admin/render-*", _METRICS_UI_DIR),
    ("frontend/admin/*-card.ts", _METRICS_UI_DIR),
    ("frontend/admin-metrics.ts", _METRICS_UI_DIR),
    ("frontend/admin/*", _ADMIN_UI_DIR),
    ("frontend/admin.ts", _ADMIN_UI_DIR),
    ("frontend/home/urls/tags/*", _union(_TAGS_UI_DIR, _URLS_UI_DIR)),
    ("frontend/home/urls/*", _URLS_UI_DIR),
    ("frontend/home/tags/*", _TAGS_UI_DIR),
    ("frontend/home/members/*", _MEMBERS_UI_DIR),
    ("frontend/home/utubs/*", _UTUBS_UI_DIR),
    ("frontend/home/search/*", _SEARCH_UI_DIR),
    (
        "frontend/home/onboarding/*",
        _union(_UTUBS_UI_DIR, _MEMBERS_UI_DIR, _TAGS_UI_DIR),
    ),
    ("frontend/home/*", _HOME_UI_DIR),
    ("frontend/main.ts", _HOME_UI_DIR),
    ("frontend/splash/*", _SPLASH_UI_DIR),
    ("frontend/splash.ts", _SPLASH_UI_DIR),
    ("frontend/error.ts", ("splash_ui",)),
    ("frontend/settings/*", _SETTINGS_UI_DIR),
    ("frontend/settings.ts", _SETTINGS_UI_DIR),
    ("frontend/contact.ts", _CONTACT),
    ("frontend/navbar.ts", ("splash_ui", "home_ui")),
    (
        "frontend/logic/*",
        _union(_URLS_UI_DIR, _TAGS_UI_DIR, _MEMBERS_UI_DIR, _UTUBS_UI_DIR),
    ),
    ("frontend/styles/home/*", _HOME_DECKS_UI),
    ("frontend/styles/admin/*", _union(_ADMIN_UI_DIR, _METRICS_UI_DIR)),
    ("frontend/styles/settings/*", _SETTINGS_UI_DIR),
    ("frontend/styles/splash.css", _SPLASH_UI_DIR),
    ("frontend/styles/privacy-terms.css", ("splash_ui",)),
    # The contact page has no UI marker; its integration tests don't load CSS.
    ("frontend/styles/contact.css", ()),
    # --- scripts ------------------------------------------------------------
    ("scripts/flush_metrics.py", ("cli",)),
    ("scripts/sample_gauges.py", ("cli",)),
    ("scripts/purge_audit_log.py", ("admin",)),
    ("scripts/run_backup_if_requested.py", ("admin",)),
    ("scripts/*.py", ("unit",)),
    ("scripts/*.sh", ("unit", "admin")),
)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Selection:
    """The markers a set of changed files affects, and why, per file."""

    markers: frozenset[str]
    everything: bool
    host_static: bool
    reasons: tuple[tuple[str, str, tuple[str, ...]], ...]

    def _pick(self, declared: Collection[str], *, is_ui: bool) -> list[str]:
        pool = declared if self.everything else self.markers
        return sorted(marker for marker in pool if marker.endswith(UI_SUFFIX) == is_ui)

    def integration_markers(self, declared: Collection[str]) -> list[str]:
        """Sorted non-UI markers; every declared non-UI marker when `everything`."""
        return self._pick(declared, is_ui=False)

    def ui_markers(self, declared: Collection[str]) -> list[str]:
        """Sorted `*_ui` markers; every declared UI marker when `everything`."""
        return self._pick(declared, is_ui=True)


@dataclass(frozen=True)
class _RegistryLink:
    kind: str
    endpoint: str
    blueprint: str


def _first_match(path: str, globs: Iterable[str]) -> str | None:
    return next((glob for glob in globs if fnmatch.fnmatchcase(path, glob)), None)


def _path_row(path: str) -> MarkerRow | None:
    return next(
        (row for row in PATH_MARKERS if fnmatch.fnmatchcase(path, row[0])), None
    )


def _module_file(dotted_module: str) -> str:
    return dotted_module.replace(".", "/") + ".py"


def _schema_modules(schemas: dict[str, Any] | None) -> set[str]:
    """Dotted schema modules a row references (`errors` is broad, so skipped)."""
    if schemas is None:
        return set()
    dotted_classes = [schemas.get(part) for part in ("request", "query", "response")]
    dotted_classes.extend((schemas.get("status_codes") or {}).values())
    modules = {
        dotted_class.rsplit(".", 1)[0]
        for dotted_class in dotted_classes
        if isinstance(dotted_class, str) and dotted_class
    }
    return modules - _SKIPPED_SCHEMA_MODULES


def _registry_index(registry: dict[str, Any]) -> dict[str, list[_RegistryLink]]:
    """Repo-relative file -> the registry rows that name it, and how."""
    index: dict[str, list[_RegistryLink]] = {}

    def link(file_path: str, kind: str, row: dict[str, Any]) -> None:
        index.setdefault(file_path, []).append(
            _RegistryLink(
                kind=kind, endpoint=row["endpoint"], blueprint=row["blueprint"]
            )
        )

    for row in registry["endpoints"]:
        link(row["handler"].split(":")[0], "handler", row)
        for service in row.get("services") or []:
            link(_module_file(service.split(":")[0]), "service", row)
        for schema_module in sorted(_schema_modules(row["schemas"])):
            link(_module_file(schema_module), "schema", row)
        for template in row.get("templates") or []:
            link(f"backend/templates/{template}", "template", row)
    return index


def _registry_reason(links: list[_RegistryLink]) -> str:
    parts: list[str] = []
    for kind in ("handler", "service", "schema", "template"):
        endpoints = list(
            dict.fromkeys(link.endpoint for link in links if link.kind == kind)
        )
        if not endpoints:
            continue
        shown = ", ".join(endpoints[:REASON_ENDPOINT_LIMIT])
        hidden = len(endpoints) - REASON_ENDPOINT_LIMIT
        parts.append(
            f"registry {kind} {shown}" + (f" (+{hidden} more)" if hidden > 0 else "")
        )
    return "; ".join(parts)


def _is_test_file(path: str) -> bool:
    return path.startswith("tests/") and fnmatch.fnmatchcase(
        path.rsplit("/", 1)[-1], "test_*.py"
    )


@dataclass(frozen=True)
class _FileResult:
    markers: tuple[str, ...]
    reason: str
    everything: bool = False


def _resolve_file(
    path: str,
    *,
    index: dict[str, list[_RegistryLink]],
    declared_markers: Collection[str],
    read_text: Callable[[str], str | None],
    prefix: str,
) -> _FileResult:
    """Steps 3-7 for one file; `prefix` carries a step-2 host-static note."""
    broad_glob = _first_match(path, BROAD_GLOBS)
    if broad_glob is not None:
        return _FileResult((), f"{prefix}broad: {broad_glob}", everything=True)

    if _is_test_file(path):
        text = read_text(path)
        if text is not None:
            parsed = sorted(
                set(_MARK_PATTERN.findall(text)).intersection(declared_markers)
            )
            if parsed:
                return _FileResult(tuple(parsed), f"{prefix}pytestmark in test file")
        prefix += "deleted test file; " if text is None else "unmarked test file; "

    links = index.get(path, [])
    registry_markers: list[str] = []
    for registry_link in links:
        blueprint_markers = BLUEPRINT_MARKERS.get(registry_link.blueprint)
        if blueprint_markers is None:
            return _FileResult(
                (),
                f"{prefix}unknown blueprint {registry_link.blueprint} — safe default",
                everything=True,
            )
        registry_markers.extend(blueprint_markers)
        registry_markers.extend(
            ENDPOINT_MARKER_OVERRIDES.get(registry_link.endpoint, ())
        )

    reason_parts: list[str] = []
    if links:
        reason_parts.append(_registry_reason(links))
    row = _path_row(path)
    if row is not None:
        reason_parts.append(f"path {row[0]}")
    if not reason_parts:
        return _FileResult((), f"{prefix}{UNMAPPED_REASON}", everything=True)
    path_markers = row[1] if row is not None else ()
    return _FileResult(
        _union(tuple(registry_markers), path_markers),
        prefix + "; ".join(reason_parts),
    )


def resolve_markers(
    changed_files: list[str],
    registry: dict[str, Any],
    declared_markers: set[str],
    read_text: Callable[[str], str | None],
) -> Selection:
    """Map repo-relative changed files to the markers they affect."""
    index = _registry_index(registry)
    markers: set[str] = set()
    everything = False
    host_static = False
    reasons: list[tuple[str, str, tuple[str, ...]]] = []

    for path in changed_files:
        if (
            path not in NO_IMPACT_EXEMPT
            and _first_match(path, NO_IMPACT_GLOBS) is not None
        ):
            reasons.append((path, NO_IMPACT_REASON, ()))
            continue
        prefix = ""
        if _first_match(path, HOST_STATIC_GLOBS) is not None:
            host_static = True
            prefix = "host-static; "
        result = _resolve_file(
            path,
            index=index,
            declared_markers=declared_markers,
            read_text=read_text,
            prefix=prefix,
        )
        everything = everything or result.everything
        markers.update(result.markers)
        reasons.append((path, result.reason, tuple(sorted(result.markers))))

    undeclared = markers - set(declared_markers)
    if undeclared:
        raise ValueError(
            f"markers not declared in pytest.ini: {', '.join(sorted(undeclared))}"
        )
    return Selection(
        markers=frozenset(markers),
        everything=everything,
        host_static=host_static,
        reasons=tuple(reasons),
    )


def read_declared_markers(pytest_ini: Path) -> set[str]:
    """Marker names from the indented lines of pytest.ini's `markers =` block.

    Raises ValueError when no marker is declared: an empty set would make an
    everything selection expand to nothing.
    """
    declared: set[str] = set()
    in_markers_block = False
    for line in pytest_ini.read_text(encoding="utf-8").splitlines():
        if not in_markers_block:
            in_markers_block = _MARKERS_HEADER_PATTERN.match(line) is not None
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if not line.startswith(("\t", " ")):
            break
        if stripped.startswith("#"):
            continue
        declared.add(stripped.split(":", 1)[0].split("(", 1)[0].strip())
    if not declared:
        raise ValueError(f"no markers declared in {pytest_ini}")
    return declared


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


def _git(
    run: Callable[..., subprocess.CompletedProcess[str]], *git_args: str
) -> subprocess.CompletedProcess[str]:
    try:
        return run(
            ["git", *git_args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as os_error:
        raise SelectionError(f"cannot run git: {os_error}") from os_error


def _nul_separated_paths(completed: subprocess.CompletedProcess[str]) -> set[str]:
    """Paths from `-z` output: NUL-separated, never quoted, never stripped."""
    return {path for path in completed.stdout.split("\0") if path}


def collect_changed_files(
    base: str,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    """Sorted files changed since `git merge-base <base> HEAD`, plus untracked ones.

    `--no-renames` lists a rename as delete + add, so the old path still selects.
    """
    if base.startswith("-"):
        raise SelectionError(f"base must not start with '-': {base}")
    merge_base = _git(run, "merge-base", base, "HEAD")
    if merge_base.returncode != 0:
        raise SelectionError(
            f"cannot resolve merge-base with {base} — run git fetch origin"
        )
    merge_base_sha = merge_base.stdout.strip()

    diff = _git(run, "diff", "--name-only", "--no-renames", "-z", merge_base_sha)
    if diff.returncode != 0:
        raise SelectionError(
            f"git diff against {merge_base_sha} failed: {diff.stderr.strip()}"
        )
    untracked = _git(run, "ls-files", "--others", "--exclude-standard", "-z")
    if untracked.returncode != 0:
        raise SelectionError(f"git ls-files failed: {untracked.stderr.strip()}")
    return sorted(_nul_separated_paths(diff) | _nul_separated_paths(untracked))


__all__ = [
    "BLUEPRINT_MARKERS",
    "BROAD_GLOBS",
    "DEFAULT_REGISTRY",
    "ENDPOINT_MARKER_OVERRIDES",
    "HOST_STATIC_GLOBS",
    "NO_IMPACT_EXEMPT",
    "NO_IMPACT_GLOBS",
    "PATH_MARKERS",
    "PYTEST_INI",
    "REPO_ROOT",
    "Selection",
    "SelectionError",
    "collect_changed_files",
    "read_declared_markers",
    "resolve_markers",
]
