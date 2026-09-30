from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from flask import Blueprint, Flask

from backend.config import ConfigTest
from backend.endpoint_registry.registry import (
    _js,
    _no_js_reason,
    _service_function_def,
    build_registry,
    dump_registry_json,
    is_registry_endpoint,
    render_markdown,
)
from backend.utils.all_routes import IndirectJsSource, NoJsReason
from tests.utils_for_test import create_secondary_app

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
    return create_secondary_app(ConfigTest)


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
        "indirect": None,
        "no_js": FULL_PAGE_NAVIGATION,
    }


@pytest.mark.parametrize(
    ("endpoint", "expected_no_js"),
    [
        pytest.param(SYSTEM_HEALTH, "infra-probe", id="exact-key"),
        pytest.param("api_v1.api_v1_get_me", "mobile-api", id="blueprint-wildcard"),
    ],
)
def test_no_js_reason_from_no_js_endpoints(
    registry_rows: RegistryRows, endpoint: str, expected_no_js: str
) -> None:
    """
    GIVEN an @api_route covered by NO_JS_ENDPOINTS (exact key or `<bp>.*`)
    WHEN the registry is built
    THEN no_js is the entry's reason as a plain string
    """
    no_js = registry_rows[endpoint]["js"]["no_js"]
    assert no_js == expected_no_js
    assert type(no_js) is str


def test_no_js_exact_key_wins_over_blueprint_wildcard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a NO_JS map with both `probe.*` and an exact `probe.special` key
    WHEN the reason is looked up
    THEN the exact key wins, other probe endpoints fall back to the wildcard,
        and an unmapped endpoint gets None
    """
    monkeypatch.setattr(
        "backend.endpoint_registry.registry.NO_JS_ENDPOINTS",
        {"probe.*": NoJsReason.MOBILE_API, "probe.special": NoJsReason.INFRA_PROBE},
    )
    assert _no_js_reason("probe.special") == "infra-probe"
    assert _no_js_reason("probe.other") == "mobile-api"
    assert _no_js_reason("unmapped.other") is None


def test_unlinked_api_route_has_null_no_js() -> None:
    """
    GIVEN an @api_route with no key, no template ref and no NO_JS entry
    WHEN its JS field is derived
    THEN no_js stays null rather than defaulting to full-page navigation
    """
    js_field = _js(
        "unmapped.endpoint", is_api_route=True, route_keys=[], template_url_for=[]
    )
    assert js_field["no_js"] is None
    assert js_field["indirect"] is None


@pytest.mark.parametrize(
    ("endpoint", "expected_indirect"),
    [
        ("users.link_oauth_provider", "server-built-url"),
        ("users.unlink_oauth_provider", "server-built-url"),
        ("splash.reset_password", "page-self-url"),
    ],
)
def test_indirect_js_source_from_indirect_js_endpoints(
    registry_rows: RegistryRows, endpoint: str, expected_indirect: str
) -> None:
    """
    GIVEN an endpoint the frontend calls through a URL it gets indirectly
    WHEN the registry is built
    THEN js.indirect is its INDIRECT_JS_ENDPOINTS source as a plain string,
        and no_js is null (it has a web-JS caller)
    """
    js_field = registry_rows[endpoint]["js"]
    assert js_field["indirect"] == expected_indirect
    assert type(js_field["indirect"]) is str
    assert js_field["no_js"] is None


def test_indirect_source_suppresses_full_page_navigation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a non-@api_route endpoint with no key or template ref but an
        INDIRECT_JS_ENDPOINTS entry
    WHEN its JS field is derived
    THEN it carries the indirect source and no full-page-navigation fallback
    """
    monkeypatch.setattr(
        "backend.endpoint_registry.registry.INDIRECT_JS_ENDPOINTS",
        {"probe.page": IndirectJsSource.PAGE_SELF_URL},
    )
    js_field = _js("probe.page", is_api_route=False, route_keys=[], template_url_for=[])
    assert js_field == {
        "route_keys": [],
        "template_url_for": [],
        "indirect": "page-self-url",
        "no_js": None,
    }


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


# ---------------------------------------------------------------------------
# render_markdown
# ---------------------------------------------------------------------------

MARKDOWN_HEADER = (
    "<!-- Generated by `flask endpoints generate` — DO NOT EDIT. -->\n"
    "<!-- Source of truth: docs/endpoints/endpoint-registry.json -->\n"
)


def _two_endpoint_registry() -> dict[str, Any]:
    """Hand-built registry: an @api_route in `utubs` and a page route in `admin`.

    `utubs` is listed first so the tests prove blueprint headings are sorted.
    """
    return {
        "generated_by": "flask endpoints generate — DO NOT EDIT",
        "source_of_truth": "test",
        "endpoints": [
            {
                "endpoint": "utubs.delete_utub",
                "blueprint": "utubs",
                "rule": "/utubs/<int:utub_id>",
                "methods": ["DELETE"],
                "handler": "backend/utubs/routes.py:delete_utub",
                "decorators": ["utub_membership_required", "api_route"],
                "services": ["backend.utubs.services.delete_utub:delete_utub"],
                "schemas": {
                    "request": "backend.schemas.utubs.UTubDeleteRequestSchema",
                    "query": "backend.schemas.utubs.UTubDeleteQuerySchema",
                    "response": "backend.schemas.utubs.UTubDeletedResponseSchema",
                    "status_codes": {
                        "200": "backend.schemas.utubs.Deleted",
                        "204": None,
                    },
                },
                "templates": [],
                "js": {
                    "route_keys": ["deleteUTub"],
                    "template_url_for": [],
                    "indirect": None,
                    "no_js": None,
                },
            },
            {
                "endpoint": "admin.admin_portal",
                "blueprint": "admin",
                "rule": "/admin",
                "methods": ["GET"],
                "handler": "backend/admin/routes.py:admin_portal",
                "decorators": [],
                "services": [],
                "schemas": None,
                "templates": ["admin_portal/index.html"],
                "js": {
                    "route_keys": [],
                    "template_url_for": ["admin_portal/users/detail.html"],
                    "indirect": None,
                    "no_js": "full-page-navigation",
                },
            },
        ],
    }


def test_render_markdown_header_and_title() -> None:
    """
    GIVEN a hand-built 2-endpoint registry
    WHEN render_markdown is called
    THEN it starts with the DO-NOT-EDIT comments, has the title and no
        `Last updated` line, and ends with a single trailing newline
    """
    markdown = render_markdown(_two_endpoint_registry())

    assert markdown.startswith(MARKDOWN_HEADER)
    assert "\n# Endpoint Registry\n" in markdown
    assert "Last updated" not in markdown
    assert markdown.endswith("\n")
    assert not markdown.endswith("\n\n")


def test_render_markdown_intro_hints_endpoint_info() -> None:
    """
    GIVEN a hand-built registry
    WHEN render_markdown is called
    THEN the intro paragraph (before the first blueprint heading) points at
        `make endpoint-info` and `make generate-endpoints`
    """
    markdown = render_markdown(_two_endpoint_registry())
    intro = markdown.split("\n## ", 1)[0]

    assert "make endpoint-info e=<route>" in intro
    assert "make generate-endpoints" in intro


def test_render_markdown_groups_by_sorted_blueprint() -> None:
    """
    GIVEN a registry whose rows list `utubs` before `admin`
    WHEN render_markdown is called
    THEN `## admin` precedes `## utubs`, each followed by its endpoint heading
    """
    markdown = render_markdown(_two_endpoint_registry())

    admin_index = markdown.index("\n## admin\n")
    utubs_index = markdown.index("\n## utubs\n")
    admin_heading_index = markdown.index("### `GET /admin` — `admin.admin_portal`")
    utubs_heading_index = markdown.index(
        "### `DELETE /utubs/<int:utub_id>` — `utubs.delete_utub`"
    )

    assert admin_index < admin_heading_index < utubs_index < utubs_heading_index


def test_render_markdown_api_route_bullets() -> None:
    """
    GIVEN an @api_route row with services, request/query/response schemas, a
        schema-less status code and a JS route key
    WHEN render_markdown is called
    THEN its six unpadded bullets render each column, the Schema bullet lists
        request, query, response then status (a schema-less code renders bare),
        and `—` marks no template
    """
    markdown = render_markdown(_two_endpoint_registry())

    expected_block = (
        "### `DELETE /utubs/<int:utub_id>` — `utubs.delete_utub`\n"
        "\n"
        "- **Handler:** `backend/utubs/routes.py:delete_utub`\n"
        "- **Decorators:** `utub_membership_required`, `api_route`\n"
        "- **Service:** `backend.utubs.services.delete_utub:delete_utub`\n"
        "- **Schema:** request: `backend.schemas.utubs.UTubDeleteRequestSchema`"
        "; query: `backend.schemas.utubs.UTubDeleteQuerySchema`"
        "; response: `backend.schemas.utubs.UTubDeletedResponseSchema`"
        "; status: 200 `backend.schemas.utubs.Deleted`, 204\n"
        "- **Template:** —\n"
        "- **JS:** keys: `deleteUTub`\n"
    )
    assert expected_block in markdown


def test_render_markdown_page_route_bullets() -> None:
    """
    GIVEN a page route with no decorators, services or schemas
    WHEN render_markdown is called
    THEN empty columns render as `—` and JS shows template url_for + no-js
    """
    markdown = render_markdown(_two_endpoint_registry())

    expected_block = (
        "### `GET /admin` — `admin.admin_portal`\n"
        "\n"
        "- **Handler:** `backend/admin/routes.py:admin_portal`\n"
        "- **Decorators:** —\n"
        "- **Service:** —\n"
        "- **Schema:** —\n"
        "- **Template:** `admin_portal/index.html`\n"
        "- **JS:** template url_for: `admin_portal/users/detail.html`"
        "; no-js: full-page-navigation\n"
    )
    assert expected_block in markdown


def test_render_markdown_indirect_js_source() -> None:
    """
    GIVEN an @api_route row whose only JS linkage is an indirect source
    WHEN render_markdown is called
    THEN its JS bullet reads `indirect: <source>`
    """
    registry = _two_endpoint_registry()
    registry["endpoints"][0]["js"] = {
        "route_keys": [],
        "template_url_for": [],
        "indirect": "server-built-url",
        "no_js": None,
    }

    markdown = render_markdown(registry)

    assert "- **JS:** indirect: server-built-url\n" in markdown


def test_render_markdown_full_app_has_one_heading_per_endpoint(
    full_app: Flask,
) -> None:
    """
    GIVEN the full app's registry, round-tripped through JSON
    WHEN render_markdown is called
    THEN the markdown has exactly one endpoint heading per registry endpoint
    """
    registry = json.loads(dump_registry_json(build_registry(full_app)))

    markdown = render_markdown(registry)

    assert markdown.count("\n### `") == len(registry["endpoints"])
