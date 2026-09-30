from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from flask import Blueprint, Flask

from backend import create_app
from backend.config import ConfigTest
from backend.endpoint_registry.registry import (
    _service_function_def,
    build_registry,
    dump_registry_json,
    is_registry_endpoint,
)

pytestmark = pytest.mark.unit

RegistryRows = dict[str, dict[str, Any]]

FULL_PAGE_NAVIGATION = "full-page-navigation"
PROBE_SHARED_RULE = "/probe/shared"

UTUBS_HOME = "utubs.home"
SYSTEM_HEALTH = "system.health"
CONTACT_US = "contact.contact_us"
METRICS_QUERY_TOP = "metrics.query_top"
ADMIN_USER_SUSPEND = "admin.admin_user_suspend"

# ---------------------------------------------------------------------------
# Probe blueprint for the synthetic-app edge cases. Handlers must be
# module-level so the AST decorator lookup can find their `def`. They are
# declared deliberately out of order: `/b` before `/a`, and GET before DELETE
# on the shared path (sorted output puts DELETE first).
# ---------------------------------------------------------------------------

ordering_probe = Blueprint("ordering_probe", __name__)


@ordering_probe.route("/probe/b", methods=["GET"])
def probe_b() -> str:
    return ""


@ordering_probe.route("/probe/a", methods=["GET"])
def probe_a() -> str:
    return ""


@ordering_probe.route(PROBE_SHARED_RULE, methods=["GET"])
def probe_shared_get() -> str:
    return ""


@ordering_probe.route(PROBE_SHARED_RULE, methods=["DELETE"])
def probe_shared_delete() -> str:
    return ""


# Separate probe blueprint for the decorator sad path: `manual_handler` is a
# module-level def registered via add_url_rule, so it has no decorators at all
# (never attach this to the ordering_probe apps).
decorator_probe = Blueprint("decorator_probe", __name__)


def manual_handler() -> str:
    return ""


decorator_probe.add_url_rule("/probe/manual", view_func=manual_handler)


def _build_synthetic_app(*blueprints: Blueprint) -> Flask:
    app = Flask(__name__)
    for blueprint in blueprints:
        app.register_blueprint(blueprint)
    return app


@pytest.fixture(scope="module")
def full_app() -> Flask:
    # Pass the class, not an instance, so Config.__init__ env validation is skipped.
    app = create_app(ConfigTest)
    assert app is not None
    return app


@pytest.fixture(scope="module")
def registry_rows(full_app: Flask) -> RegistryRows:
    registry = build_registry(full_app)
    return {row["endpoint"]: row for row in registry["endpoints"]}


# ---------------------------------------------------------------------------
# is_registry_endpoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    [
        "static",
        "admin.static",
        "debugtoolbar.static",
        "debug.debug_page",
        "fake_oauth.authorize",
    ],
)
def test_is_registry_endpoint_excludes_non_app_routes(endpoint: str) -> None:
    """
    GIVEN a static, debug-toolbar, debug or fake-OAuth endpoint
    WHEN is_registry_endpoint is called
    THEN it returns False so the route never enters the registry
    """
    assert is_registry_endpoint(endpoint) is False


@pytest.mark.parametrize(
    "endpoint", ["utubs.create_utub", "splash.error_page", "debugging.page"]
)
def test_is_registry_endpoint_keeps_app_routes(endpoint: str) -> None:
    """
    GIVEN an application endpoint (including one merely prefixed 'debug')
    WHEN is_registry_endpoint is called
    THEN it returns True
    """
    assert is_registry_endpoint(endpoint) is True


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("endpoint", "expected_handler"),
    [
        ("utubs.create_utub", "backend/utubs/routes.py:create_utub"),
        (
            ADMIN_USER_SUSPEND,
            "backend/admin/action_routes.py:admin_user_suspend",
        ),
    ],
)
def test_handler_is_repo_relative_path_and_qualname(
    registry_rows: RegistryRows, endpoint: str, expected_handler: str
) -> None:
    """
    GIVEN the full app url_map
    WHEN the registry is built
    THEN each handler is `<repo-relative path>:<qualname>` of the unwrapped
        view function, with no line numbers
    """
    assert registry_rows[endpoint]["handler"] == expected_handler


# ---------------------------------------------------------------------------
# Route / methods
# ---------------------------------------------------------------------------


def test_shared_rule_rows_have_distinct_single_methods(
    registry_rows: RegistryRows,
) -> None:
    """
    GIVEN two member endpoints sharing one rule
    WHEN the registry is built
    THEN both rows carry that rule and distinct single methods (HEAD/OPTIONS dropped)
    """
    shared_rule = "/utubs/<int:utub_id>/members/<int:user_id>"
    remove_row = registry_rows["members.remove_member"]
    modify_row = registry_rows["members.modify_member_role"]

    assert remove_row["rule"] == shared_rule
    assert modify_row["rule"] == shared_rule
    assert remove_row["methods"] == ["DELETE"]
    assert modify_row["methods"] == ["PATCH"]


def test_get_route_methods_drop_head_and_options(
    registry_rows: RegistryRows,
) -> None:
    """
    GIVEN a GET route (Flask auto-adds HEAD and OPTIONS)
    WHEN the registry is built
    THEN its methods list is exactly ["GET"]
    """
    assert registry_rows[UTUBS_HOME]["methods"] == ["GET"]
    assert registry_rows[UTUBS_HOME]["blueprint"] == "utubs"


# ---------------------------------------------------------------------------
# Decorators (AST)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("endpoint", "expected_decorators"),
    [
        (
            "splash.login",
            [
                "no_authenticated_users_allowed",
                "api_route",
                "limiter.limit(SPLASH_AUTH_RATE_LIMIT, methods=['POST'])",
            ],
        ),
        (SYSTEM_HEALTH, ["limiter.exempt", "api_route"]),
        (UTUBS_HOME, ["email_validation_required"]),
    ],
)
def test_decorators_come_from_ast_without_route_decorator(
    registry_rows: RegistryRows, endpoint: str, expected_decorators: list[str]
) -> None:
    """
    GIVEN a route's source decorator stack
    WHEN the registry is built
    THEN the route decorator is dropped, api_route(...) collapses to 'api_route',
        and every other decorator is ast.unparse'd in source order
    """
    assert registry_rows[endpoint]["decorators"] == expected_decorators


def test_nested_handler_raises_clear_error() -> None:
    """
    GIVEN a view function defined inside another function (not module-level)
    WHEN the registry is built
    THEN a ValueError names the endpoint instead of emitting a wrong row
    """
    nested_probe = Blueprint("nested_probe", __name__)

    @nested_probe.route("/probe/nested", methods=["GET"])
    def nested_handler() -> str:
        return ""

    app = _build_synthetic_app(nested_probe)

    with pytest.raises(ValueError, match="nested_probe.nested_handler"):
        build_registry(app)


def test_handler_without_route_decorator_raises_clear_error(tmp_path: Path) -> None:
    """
    GIVEN a module-level view registered via add_url_rule (no `@<bp>.route`)
    WHEN the registry is built
    THEN a ValueError names the endpoint instead of emitting a wrong row
    """
    app = _build_synthetic_app(decorator_probe)

    with pytest.raises(ValueError, match="decorator_probe.manual_handler"):
        build_registry(app, templates_root=tmp_path)


# ---------------------------------------------------------------------------
# Service (AST, widened predicate)
# ---------------------------------------------------------------------------


def test_home_resolves_all_five_services(registry_rows: RegistryRows) -> None:
    """
    GIVEN utubs.home calling five imported service functions
    WHEN the registry is built
    THEN all five appear as sorted, unique `module:function` strings
    """
    assert registry_rows[UTUBS_HOME]["services"] == [
        "backend.splash.services.change_email:build_email_change_banner",
        "backend.users.services.preferences_service:build_display_preferences_context",
        "backend.utubs.services.home_page:render_home_page",
        "backend.utubs.services.home_page:validate_home_query_params",
        "backend.utubs.services.home_page:validate_user_is_member_of_utub_on_home_page_with_query_param",
    ]


def test_contact_us_allowlisted_service_module(
    registry_rows: RegistryRows,
) -> None:
    """
    GIVEN contact.contact_us calling backend.contact.contact_us (no `.services.`)
    WHEN the registry is built
    THEN the explicitly allowlisted module is still counted as a service
    """
    assert registry_rows[CONTACT_US]["services"] == [
        "backend.contact.contact_us:load_contact_us_page"
    ]


def test_module_object_attribute_call_resolves_service(
    registry_rows: RegistryRows,
) -> None:
    """
    GIVEN metrics.query_top calling query_service.top_events(...) where
        query_service is bound by `from backend.metrics import query_service`
    WHEN the registry is built
    THEN the attribute call resolves through the unified qualified map
    """
    assert registry_rows[METRICS_QUERY_TOP]["services"] == [
        "backend.metrics.query_service:top_events"
    ]


@pytest.mark.parametrize(
    ("endpoint", "expected_services"),
    [
        (
            "admin.admin_user_detail",
            [
                "backend.admin.account_data_service:is_tombstoned",
                "backend.admin.user_service:get_user_detail",
            ],
        ),
        (
            "admin.admin_db_table",
            ["backend.admin.db_browser_service:get_table_page"],
        ),
    ],
)
def test_admin_direct_and_submodule_calls_resolve_through_unified_map(
    registry_rows: RegistryRows, endpoint: str, expected_services: list[str]
) -> None:
    """
    GIVEN backend/admin/routes.py importing both functions
        (`from backend.admin.user_service import get_user_detail`) and a
        submodule object (`from backend.admin import db_browser_service`)
    WHEN the registry is built
    THEN direct calls and submodule attribute calls both resolve to
        `module:function`
    """
    assert registry_rows[endpoint]["services"] == expected_services


@pytest.mark.parametrize(
    "service",
    [
        # Attribute call on an imported class: the "module" half is a class path.
        "backend.utils.all_routes.JsRoute:_make",
        # Resolvable module, but the target is a dict, not a function.
        "backend.utils.all_routes:ADMIN_JS_ROUTES",
    ],
)
def test_service_function_def_returns_none_for_unresolvable_targets(
    service: str,
) -> None:
    """
    GIVEN a service string that is not a module-level function
    WHEN _service_function_def resolves it for the template hop
    THEN it returns None instead of raising
    """
    assert _service_function_def(service, {}) is None


def test_inline_handler_has_no_services(registry_rows: RegistryRows) -> None:
    """
    GIVEN system.health, which calls only non-service helpers
    WHEN the registry is built
    THEN its services list is empty
    """
    assert registry_rows[SYSTEM_HEALTH]["services"] == []


# ---------------------------------------------------------------------------
# Schema (runtime stash)
# ---------------------------------------------------------------------------


def test_api_route_with_request_and_response_schema(
    registry_rows: RegistryRows,
) -> None:
    """
    GIVEN utubs.create_utub declaring request + response schemas
    WHEN the registry is built
    THEN both are rendered as `<module>.<qualname>` strings
    """
    schemas = registry_rows["utubs.create_utub"]["schemas"]
    assert schemas["request"] == "backend.schemas.requests.utubs.CreateUTubRequest"
    assert schemas["response"] == "backend.schemas.utubs.UtubCreatedResponseSchema"


def test_status_code_only_schema(registry_rows: RegistryRows) -> None:
    """
    GIVEN splash.google_login declaring only status_codes={302: EmptyRedirectSchema}
    WHEN the registry is built
    THEN request/query/response are null and status_codes has one string key
    """
    assert registry_rows["splash.google_login"]["schemas"] == {
        "request": None,
        "query": None,
        "response": None,
        "status_codes": {"302": "backend.schemas.base.EmptyRedirectSchema"},
    }


def test_health_has_two_status_codes(registry_rows: RegistryRows) -> None:
    """
    GIVEN system.health declaring 200 and 503 status-code schemas
    WHEN the registry is built
    THEN both codes appear as string keys
    """
    assert registry_rows[SYSTEM_HEALTH]["schemas"]["status_codes"] == {
        "200": "backend.schemas.system.HealthResponseSchema",
        "503": "backend.schemas.base.StatusMessageResponseSchema",
    }


def test_page_route_has_null_schemas(registry_rows: RegistryRows) -> None:
    """
    GIVEN users.settings, a page route without @api_route
    WHEN the registry is built
    THEN its schemas field is null
    """
    assert registry_rows["users.settings"]["schemas"] is None


# ---------------------------------------------------------------------------
# Template (literal + 1 hop)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("endpoint", "expected_templates"),
    [
        ("admin.admin_portal", ["admin_portal/index.html"]),
        (UTUBS_HOME, ["pages/home.html"]),
        ("splash.google_callback", ["pages/splash.html"]),
        (CONTACT_US, ["pages/contact_us.html"]),
        ("urls.create_url", []),
    ],
)
def test_templates_literal_and_one_hop(
    registry_rows: RegistryRows, endpoint: str, expected_templates: list[str]
) -> None:
    """
    GIVEN handlers rendering templates directly or via one service hop
    WHEN the registry is built
    THEN each template literal appears once, sorted
    """
    assert registry_rows[endpoint]["templates"] == expected_templates


# ---------------------------------------------------------------------------
# JS linkage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("endpoint", "expected_route_keys"),
    [
        ("utubs.get_single_utub", ["getUTub"]),
        ("utubs.delete_utub", ["deleteUTub"]),
        (METRICS_QUERY_TOP, ["metricsQueryTop"]),
    ],
)
def test_js_route_keys_inverted_from_route_tables(
    registry_rows: RegistryRows, endpoint: str, expected_route_keys: list[str]
) -> None:
    """
    GIVEN JS_ROUTES | ADMIN_JS_ROUTES
    WHEN the registry is built
    THEN each endpoint lists exactly the keys that target it
    """
    assert registry_rows[endpoint]["js"]["route_keys"] == expected_route_keys


def test_template_url_for_reference(registry_rows: RegistryRows) -> None:
    """
    GIVEN an admin action route referenced by a Jinja url_for data attribute
    WHEN the registry is built
    THEN the referencing template appears in template_url_for and no_js is null
    """
    js_field = registry_rows[ADMIN_USER_SUSPEND]["js"]
    assert "admin_portal/users/detail.html" in js_field["template_url_for"]
    assert js_field["route_keys"] == []
    assert js_field["no_js"] is None


def test_unlinked_page_route_is_full_page_navigation(
    registry_rows: RegistryRows,
) -> None:
    """
    GIVEN users.privacy_policy: not @api_route, no route key, no template url_for
    WHEN the registry is built
    THEN no_js is 'full-page-navigation'
    """
    js_field = registry_rows["users.privacy_policy"]["js"]
    assert js_field == {
        "route_keys": [],
        "template_url_for": [],
        "no_js": FULL_PAGE_NAVIGATION,
    }


def test_unlinked_api_route_has_null_no_js(registry_rows: RegistryRows) -> None:
    """
    GIVEN system.health: an @api_route with no key, no template ref, and (until
        NO_JS_ENDPOINTS exists) no no-js reason
    WHEN the registry is built
    THEN no_js stays null rather than defaulting to full-page navigation
    """
    assert registry_rows[SYSTEM_HEALTH]["js"]["no_js"] is None


def test_template_scan_uses_given_templates_root(tmp_path: Path) -> None:
    """
    GIVEN a custom templates_root holding one template that url_for's a probe route
    WHEN build_registry is called with that root
    THEN the probe row's template_url_for lists the relative template path
    """
    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    (nested_dir / "probe.html").write_text(
        "<a href=\"{{ url_for(\n  'ordering_probe.probe_a') }}\">a</a>",
        encoding="utf-8",
    )
    app = _build_synthetic_app(ordering_probe)

    registry = build_registry(app, templates_root=tmp_path)
    rows = {row["endpoint"]: row for row in registry["endpoints"]}

    assert rows["ordering_probe.probe_a"]["js"]["template_url_for"] == [
        "nested/probe.html"
    ]
    assert rows["ordering_probe.probe_a"]["js"]["no_js"] is None
    assert rows["ordering_probe.probe_b"]["js"]["no_js"] == FULL_PAGE_NAVIGATION


def test_missing_templates_root_raises(tmp_path: Path) -> None:
    """
    GIVEN a templates_root that does not exist
    WHEN build_registry is called
    THEN a ValueError is raised instead of silently scanning nothing
    """
    app = _build_synthetic_app(ordering_probe)

    with pytest.raises(ValueError, match="templates_root is not a directory"):
        build_registry(app, templates_root=tmp_path / "missing")


# ---------------------------------------------------------------------------
# build_registry ordering + envelope
# ---------------------------------------------------------------------------


def test_endpoints_sorted_by_rule_methods_endpoint(tmp_path: Path) -> None:
    """
    GIVEN a synthetic app registering /b before /a, and GET before DELETE on a
        shared path
    WHEN build_registry is called
    THEN rows are sorted by (rule, methods, endpoint) regardless of
        registration order
    """
    app = _build_synthetic_app(ordering_probe)

    registry = build_registry(app, templates_root=tmp_path)
    ordered = [(row["rule"], row["methods"]) for row in registry["endpoints"]]

    assert ordered == [
        ("/probe/a", ["GET"]),
        ("/probe/b", ["GET"]),
        (PROBE_SHARED_RULE, ["DELETE"]),
        (PROBE_SHARED_RULE, ["GET"]),
    ]


def test_registry_envelope_has_no_timestamp(tmp_path: Path) -> None:
    """
    GIVEN a synthetic app
    WHEN build_registry is called
    THEN the envelope carries only generated_by, source_of_truth and endpoints
    """
    registry = build_registry(
        _build_synthetic_app(ordering_probe), templates_root=tmp_path
    )

    assert set(registry) == {"generated_by", "source_of_truth", "endpoints"}
    assert "DO NOT EDIT" in registry["generated_by"]
    assert set(registry["endpoints"][0]) == {
        "endpoint",
        "blueprint",
        "rule",
        "methods",
        "handler",
        "decorators",
        "services",
        "schemas",
        "templates",
        "js",
    }


# ---------------------------------------------------------------------------
# dump_registry_json determinism
# ---------------------------------------------------------------------------


def test_dump_is_deterministic_and_excludes_non_app_routes(full_app: Flask) -> None:
    """
    GIVEN the full app
    WHEN build_registry is dumped twice
    THEN the JSON text is byte-identical, ends with a newline, round-trips, and
        contains no static/debug/fake_oauth endpoints
    """
    first_dump = dump_registry_json(build_registry(full_app))
    second_dump = dump_registry_json(build_registry(full_app))

    assert first_dump == second_dump
    assert first_dump.endswith("}\n")

    endpoints = [row["endpoint"] for row in json.loads(first_dump)["endpoints"]]
    assert endpoints
    assert not any(
        endpoint == "static"
        or endpoint.endswith(".static")
        or endpoint.startswith(("debug.", "fake_oauth."))
        for endpoint in endpoints
    )
