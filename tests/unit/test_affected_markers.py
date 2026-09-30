"""Unit tests for `scripts/affected_markers.py` (`make affected-markers` / `test-affected`).

Resolution runs against a small inline registry; git is faked through the
`run` seam, so nothing shells out to git inside the container. The
table-consistency tests read the committed registry and pytest.ini, so a new
marker, blueprint or test directory without a table row fails loudly here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from scripts import affected_markers
from scripts.affected_markers import (
    BLUEPRINT_MARKERS,
    BROAD_GLOBS,
    DEFAULT_REGISTRY,
    ENDPOINT_MARKER_OVERRIDES,
    HOST_STATIC_GLOBS,
    PATH_MARKERS,
    PYTEST_INI,
    REPO_ROOT,
    UI_SUFFIX,
    Selection,
    SelectionError,
    collect_changed_files,
    format_expression,
    format_report,
    main,
    read_declared_markers,
    registry_staleness_warning,
    resolve_markers,
)

pytestmark = pytest.mark.unit

DECLARED_MARKERS: set[str] = read_declared_markers(PYTEST_INI)
DECLARED_MARKER_COUNT: int = 23
MERGE_BASE_SHA: str = "abc123"


def _row(
    *,
    endpoint: str,
    handler_file: str,
    services: list[str] | None = None,
    schemas: dict[str, Any] | None = None,
    templates: list[str] | None = None,
) -> dict[str, Any]:
    blueprint, function_name = endpoint.split(".", 1)
    return {
        "blueprint": blueprint,
        "decorators": ["api_route"],
        "endpoint": endpoint,
        "handler": f"{handler_file}:{function_name}",
        "js": {
            "indirect": None,
            "no_js": None,
            "route_keys": [],
            "template_url_for": [],
        },
        "methods": ["GET"],
        "rule": f"/{function_name}",
        "schemas": schemas,
        "services": services or [],
        "templates": templates or [],
    }


CREATE_URL_SERVICE = "backend.urls.services.create_urls:create_url"
SEARCH_SERVICE = "backend.search.services.cross_utub_search:search_across_user_utubs"

REGISTRY: dict[str, Any] = {
    "endpoints": [
        _row(
            endpoint="members.add_member",
            handler_file="backend/members/routes.py",
            services=["backend.members.services.create_members:create_utub_member"],
        ),
        _row(
            endpoint="urls.create_url",
            handler_file="backend/urls/routes.py",
            services=[CREATE_URL_SERVICE],
        ),
        _row(
            endpoint="api_v1.create_url",
            handler_file="backend/api_v1/url_routes.py",
            services=[CREATE_URL_SERVICE],
        ),
        _row(
            endpoint="search.search_utubs",
            handler_file="backend/search/routes.py",
            services=[SEARCH_SERVICE],
        ),
        _row(
            endpoint="api_v1.search_utubs",
            handler_file="backend/api_v1/routes.py",
            services=[SEARCH_SERVICE],
        ),
        _row(
            endpoint="utubs.get_single_utub",
            handler_file="backend/utubs/routes.py",
            schemas={
                "query": None,
                "request": None,
                "response": "backend.schemas.utubs.UtubDetailSchema",
                "status_codes": {
                    "200": "backend.schemas.utubs.UtubDetailSchema",
                    "404": "backend.schemas.errors.ErrorResponse",
                },
            },
        ),
        _row(
            endpoint="splash.splash_page",
            handler_file="backend/splash/routes.py",
            schemas=None,
            templates=["pages/splash.html"],
        ),
    ]
}
ADMIN_METRICS_REGISTRY: dict[str, Any] = {
    "endpoints": [
        _row(endpoint="admin.admin_metrics", handler_file="backend/admin/routes.py")
    ]
}


def _reader(texts: dict[str, str]) -> Callable[[str], str | None]:
    return texts.get


def _resolve(
    changed_files: list[str],
    *,
    registry: dict[str, Any] = REGISTRY,
    texts: dict[str, str] | None = None,
) -> Selection:
    return resolve_markers(
        changed_files, registry, DECLARED_MARKERS, _reader(texts or {})
    )


def _reason_for(selection: Selection, path: str) -> str:
    return next(reason for changed, reason, _ in selection.reasons if changed == path)


# --- resolve_markers: registry ------------------------------------------------


def test_route_file_resolves_through_its_registry_handler() -> None:
    """
    GIVEN a registry row whose handler is backend/members/routes.py
    WHEN that route file changes
    THEN it selects the members blueprint markers, naming the handler match
    """
    selection = _resolve(["backend/members/routes.py"])

    assert selection.markers == {"members", "members_ui"}
    assert not selection.everything
    assert "registry handler members.add_member" in _reason_for(
        selection, "backend/members/routes.py"
    )


def test_shared_service_fans_out_to_every_blueprint_that_calls_it() -> None:
    """
    GIVEN a urls service listed by both a urls row and an api_v1 row
    WHEN the service module changes
    THEN it selects the urls markers and mobile_api
    """
    selection = _resolve(["backend/urls/services/create_urls.py"])

    assert selection.markers >= {
        "urls",
        "urls_ui",
        "create_urls_ui",
        "update_urls_ui",
        "mobile_ui",
        "mobile_api",
    }
    assert "registry service" in _reason_for(
        selection, "backend/urls/services/create_urls.py"
    )


def test_search_service_uses_the_urls_integration_marker() -> None:
    """
    GIVEN the cross-UTub search service, called by search and api_v1 rows
    WHEN it changes
    THEN it selects urls + search_ui + mobile_api (there is no `search` marker)
    """
    selection = _resolve(["backend/search/services/cross_utub_search.py"])

    assert selection.markers == {"urls", "search_ui", "mobile_api"}


def test_endpoint_override_adds_on_top_of_the_blueprint_markers() -> None:
    """
    GIVEN only the admin.admin_metrics row in the registry
    WHEN backend/admin/routes.py changes
    THEN the override adds metrics_ui and cli to the admin markers
    """
    selection = _resolve(["backend/admin/routes.py"], registry=ADMIN_METRICS_REGISTRY)

    assert selection.markers == {"admin", "admin_ui", "metrics_ui", "cli"}
    assert "admin.admin_metrics" in _reason_for(selection, "backend/admin/routes.py")


def test_schema_module_matches_rows_that_reference_its_classes() -> None:
    """
    GIVEN a utubs row whose response schema lives in backend/schemas/utubs.py
    WHEN that schema module changes
    THEN it selects the utubs blueprint markers plus the schema's own path row
    """
    selection = _resolve(["backend/schemas/utubs.py"])

    assert selection.markers == {"unit", *BLUEPRINT_MARKERS["utubs"]}
    assert "registry schema utubs.get_single_utub" in _reason_for(
        selection, "backend/schemas/utubs.py"
    )


def test_render_template_matches_its_registry_row() -> None:
    """
    GIVEN a splash row rendering pages/splash.html
    WHEN the template changes
    THEN it selects the splash blueprint markers through the template match
    """
    selection = _resolve(["backend/templates/pages/splash.html"])

    assert selection.markers == set(BLUEPRINT_MARKERS["splash"])
    assert "registry template splash.splash_page" in _reason_for(
        selection, "backend/templates/pages/splash.html"
    )


def test_row_with_null_schemas_resolves_through_its_handler() -> None:
    """
    GIVEN a registry row with `schemas: null` (like the real splash.splash_page)
    WHEN its handler file changes
    THEN it resolves to the splash blueprint markers without raising
    """
    selection = _resolve(["backend/splash/routes.py"])

    assert selection.markers == set(BLUEPRINT_MARKERS["splash"])


def test_service_shared_by_many_rows_truncates_the_reason() -> None:
    """
    GIVEN four registry rows that all call one service module
    WHEN that service module changes
    THEN the reason lists the first three endpoints plus "(+1 more)", joined
        with the service file's own path row
    """
    shared_service = "backend.utubs.services.shared:do_it"
    registry = {
        "endpoints": [
            _row(
                endpoint=f"utubs.page_{index}",
                handler_file="backend/utubs/routes.py",
                services=[shared_service],
            )
            for index in range(4)
        ]
    }

    selection = _resolve(["backend/utubs/services/shared.py"], registry=registry)

    assert selection.markers == set(BLUEPRINT_MARKERS["utubs"])
    assert _reason_for(selection, "backend/utubs/services/shared.py") == (
        "registry service utubs.page_0, utubs.page_1, utubs.page_2 (+1 more); "
        "path backend/utubs/*"
    )


def test_unknown_blueprint_falls_back_to_everything() -> None:
    """
    GIVEN a registry row for a blueprint missing from BLUEPRINT_MARKERS
    WHEN its handler changes
    THEN selection falls back to everything rather than picking nothing
    """
    registry = {
        "endpoints": [
            _row(endpoint="newbp.page", handler_file="backend/newbp/routes.py")
        ]
    }

    selection = _resolve(["backend/newbp/routes.py"], registry=registry)

    assert selection.everything
    assert "unknown blueprint newbp" in _reason_for(
        selection, "backend/newbp/routes.py"
    )


# --- resolve_markers: test files ----------------------------------------------


def test_changed_test_file_selects_its_own_pytestmark() -> None:
    """
    GIVEN a changed test file whose text sets `pytestmark = pytest.mark.tags`
    WHEN it resolves
    THEN only its own marker is selected
    """
    path = "tests/integration/utubtags/test_x.py"
    texts = {path: "import pytest\n\npytestmark = pytest.mark.tags\n"}

    selection = _resolve([path], texts=texts)

    assert selection.markers == {"tags"}


def test_list_form_pytestmark_is_parsed_and_non_markers_are_ignored() -> None:
    """
    GIVEN a test file with list-form pytestmark and a parametrize decorator
    WHEN it resolves
    THEN both declared markers are selected and `parametrize` is not
    """
    path = "tests/functional/urls_ui/test_x.py"
    texts = {
        path: (
            "pytestmark = [pytest.mark.urls_ui, pytest.mark.mobile_ui]\n"
            "@pytest.mark.parametrize('value', [1])\n"
            "def test_it(value: int) -> None: ...\n"
        )
    }

    selection = _resolve([path], texts=texts)

    assert selection.markers == {"urls_ui", "mobile_ui"}


def test_marker_literals_in_strings_and_comments_are_ignored() -> None:
    """
    GIVEN a test file marked `unit` whose strings, docstrings and comments
        mention other `pytest.mark.X` names
    WHEN it resolves
    THEN only the marker it actually applies is selected
    """
    path = "tests/unit/test_x.py"
    texts = {
        path: (
            '"""Mentions pytest.mark.tags in a docstring."""\n'
            "import pytest\n\n"
            "pytestmark = pytest.mark.unit\n"
            "# pytest.mark.admin in a comment\n"
            "FIXTURE = 'pytestmark = [pytest.mark.urls_ui, pytest.mark.mobile_ui]'\n"
            "def test_it() -> None:\n"
            "    assert 'pytest.mark.members' in FIXTURE\n"
        )
    }

    selection = _resolve([path], texts=texts)

    assert selection.markers == {"unit"}


def test_multiline_pytestmark_and_decorator_marks_are_selected() -> None:
    """
    GIVEN a test file with a multi-line list pytestmark, a function-level
        and a class-level `@pytest.mark.X` decorator, and a
        `pytest.param(..., marks=pytest.mark.X)` inside a parametrize
    WHEN it resolves
    THEN every applied declared marker is selected
    """
    path = "tests/integration/test_x.py"
    texts = {
        path: (
            "import pytest\n\n"
            "pytestmark = [\n"
            "    pytest.mark.utubs,\n"
            "    pytest.mark.urls,\n"
            "]\n\n"
            "@pytest.mark.mobile_ui\n"
            "def test_mobile() -> None: ...\n\n"
            "@pytest.mark.members\n"
            "class TestMembers:\n"
            "    @pytest.mark.parametrize(\n"
            "        'value', [pytest.param(1, marks=pytest.mark.tags)]\n"
            "    )\n"
            "    def test_it(self, value: int) -> None: ...\n"
        )
    }

    selection = _resolve([path], texts=texts)

    assert selection.markers == {"utubs", "urls", "mobile_ui", "members", "tags"}


def test_unparseable_test_file_falls_back_to_a_text_scan() -> None:
    """
    GIVEN a changed test file that is not valid Python (e.g. mid-edit)
    WHEN it resolves
    THEN every declared `pytest.mark.X` in its text is selected (safe
        over-selection), never an error
    """
    path = "tests/integration/test_x.py"
    texts = {
        path: "pytestmark = pytest.mark.tags\ndef broken(:\n  'pytest.mark.urls'\n"
    }

    selection = _resolve([path], texts=texts)

    assert selection.markers == {"tags", "urls"}


def test_annotated_and_class_level_pytestmark_are_selected() -> None:
    """
    GIVEN a test file with an annotated module-level `pytestmark` and a
        plain `pytestmark` assignment inside a class body
    WHEN it resolves
    THEN the markers from both assignments are selected
    """
    path = "tests/integration/test_x.py"
    texts = {
        path: (
            "import pytest\n\n"
            "pytestmark: list[pytest.MarkDecorator] = [pytest.mark.urls]\n\n"
            "class TestTags:\n"
            "    pytestmark = pytest.mark.tags\n"
        )
    }

    selection = _resolve([path], texts=texts)

    assert selection.markers == {"urls", "tags"}


def test_aliased_pytest_and_mark_imports_are_selected() -> None:
    """
    GIVEN a test file that applies markers through `import pytest as pt`
        and `from pytest import mark`
    WHEN it resolves
    THEN both aliased markers are selected, not the directory default
    """
    path = "tests/integration/test_x.py"
    texts = {
        path: (
            "import pytest as pt\n"
            "from pytest import mark\n\n"
            "pytestmark = pt.mark.urls\n\n"
            "@mark.mobile_ui\n"
            "def test_it() -> None: ...\n"
        )
    }

    selection = _resolve([path], texts=texts)

    assert selection.markers == {"urls", "mobile_ui"}


def test_too_complex_test_file_falls_back_to_a_text_scan() -> None:
    """
    GIVEN a changed test file too deeply nested for the parser (it raises
        MemoryError rather than SyntaxError)
    WHEN it resolves
    THEN it falls back to the whole-text scan instead of crashing
    """
    path = "tests/integration/test_x.py"
    texts = {path: "pytestmark = pytest.mark.tags\nvalue = " + "-" * 200_000 + "1\n"}

    selection = _resolve([path], texts=texts)

    assert selection.markers == {"tags"}


def test_this_test_module_selects_only_its_own_unit_marker() -> None:
    """
    GIVEN the committed `tests/unit/test_affected_markers.py`, whose fixture
        strings mention many other markers
    WHEN it resolves with its real text
    THEN it selects only `unit`, its own pytestmark
    """
    path = "tests/unit/test_affected_markers.py"

    selection = _resolve([path], texts={path: (REPO_ROOT / path).read_text()})

    assert selection.markers == {"unit"}


def test_deleted_test_file_falls_back_to_its_directory_row() -> None:
    """
    GIVEN a deleted test file (read_text returns None)
    WHEN it resolves
    THEN its directory's PATH_MARKERS row supplies the markers
    """
    path = "tests/integration/utubtags/test_removed.py"

    selection = _resolve([path])

    assert selection.markers == {"tags"}
    assert not selection.everything
    assert "deleted test file" in _reason_for(selection, path)


def test_unmarked_test_file_falls_back_to_its_directory_row() -> None:
    """
    GIVEN a test file whose text carries no declared marker
    WHEN it resolves
    THEN its directory's PATH_MARKERS row supplies the markers
    """
    path = "tests/integration/utubtags/test_unmarked.py"

    selection = _resolve([path], texts={path: "def test_it() -> None: ...\n"})

    assert selection.markers == {"tags"}


# --- resolve_markers: path tables --------------------------------------------


def test_frontend_dir_resolves_through_the_path_table() -> None:
    """
    GIVEN a changed frontend tags-deck module
    WHEN it resolves
    THEN it selects the tags UI markers from PATH_MARKERS
    """
    selection = _resolve(["frontend/home/tags/deck.ts"])

    assert selection.markers == {"tags_ui", "mobile_ui"}


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        ".github/workflows/test.yml",
        ".claude/x",
        "frontend/lib/__tests__/csrf.test.ts",
    ],
)
def test_no_impact_paths_select_nothing(path: str) -> None:
    """
    GIVEN a docs/CI/tooling-only change
    WHEN it resolves
    THEN nothing is selected and the reason says so
    """
    selection = _resolve([path])

    assert selection.markers == frozenset()
    assert not selection.everything
    assert selection.reasons == ((path, "no test impact", ()),)


@pytest.mark.parametrize(
    ("path", "pattern"),
    [
        ("tests/conftest.py", "tests/conftest.py"),
        ("backend/models/users.py", "backend/models/*"),
        ("frontend/lib/ajax.ts", "frontend/lib/*"),
        (
            "tests/integration/system/metrics_helpers.py",
            "tests/integration/system/metrics_helpers.py",
        ),
        (
            "backend/templates/components/footer.html",
            "backend/templates/components/footer.html",
        ),
    ],
)
def test_broad_paths_select_everything(path: str, pattern: str) -> None:
    """
    GIVEN a shared fixture, model or frontend library change
    WHEN it resolves
    THEN everything is selected, naming the broad pattern
    """
    selection = _resolve([path])

    assert selection.everything
    assert _reason_for(selection, path) == f"broad: {pattern}"


def test_unmapped_path_is_a_safe_default_of_everything() -> None:
    """
    GIVEN a path no table knows
    WHEN it resolves
    THEN everything is selected rather than nothing
    """
    selection = _resolve(["some/unknown/file.py"])

    assert selection.everything
    assert (
        _reason_for(selection, "some/unknown/file.py") == "unmapped path — safe default"
    )


def test_committed_registry_json_is_not_no_impact() -> None:
    """
    GIVEN the generated endpoint registry JSON
    WHEN it changes
    THEN its readers' markers (unit, cli) are selected
    """
    selection = _resolve(["docs/endpoints/endpoint-registry.json"])

    assert selection.markers == {"unit", "cli"}
    assert not selection.everything


def test_rendered_endpoint_registry_markdown_is_exempt_from_no_impact() -> None:
    """
    GIVEN docs/endpoints/ENDPOINT_REGISTRY.md, a `*.md` file tests still read
    WHEN it changes
    THEN its readers' markers (unit, cli) are selected, not nothing or everything
    """
    selection = _resolve(["docs/endpoints/ENDPOINT_REGISTRY.md"])

    assert selection.markers == {"unit", "cli"}
    assert not selection.everything


def test_tags_ui_helper_selects_its_importers_markers() -> None:
    """
    GIVEN tags_ui/db_utils.py, imported via playwright_utils by other UI dirs
    WHEN it changes
    THEN the importers' markers, including urls_ui, are selected
    """
    selection = _resolve(["tests/functional/tags_ui/db_utils.py"])

    assert "urls_ui" in selection.markers
    assert not selection.everything


@pytest.mark.parametrize("path", ["Makefile", "docker/compose.local.yaml"])
def test_host_static_only_paths_select_no_pytest_markers(path: str) -> None:
    """
    GIVEN a Makefile or docker/ change
    WHEN it resolves
    THEN only host_static is set: no markers and not everything
    """
    selection = _resolve([path])

    assert selection.host_static
    assert selection.markers == frozenset()
    assert not selection.everything


def test_host_static_script_continues_into_its_path_row() -> None:
    """
    GIVEN scripts/capacity.py, a HOST_STATIC_GLOBS entry
    WHEN it resolves
    THEN host_static is set AND resolution continues into its `unit` row
    """
    selection = _resolve(["scripts/capacity.py"])

    assert selection.host_static
    assert selection.markers == {"unit"}
    assert not selection.everything


def test_empty_diff_selects_nothing() -> None:
    """
    GIVEN no changed files
    WHEN it resolves
    THEN the selection is empty, not everything
    """
    selection = _resolve([])

    assert selection == Selection(
        markers=frozenset(), everything=False, host_static=False, reasons=()
    )


def test_undeclared_marker_raises_value_error() -> None:
    """
    GIVEN a declared-marker set that lacks members_ui
    WHEN a members route resolves
    THEN resolve_markers refuses to emit an undeclared marker
    """
    declared = DECLARED_MARKERS - {"members_ui"}

    with pytest.raises(ValueError, match="members_ui"):
        resolve_markers(["backend/members/routes.py"], REGISTRY, declared, _reader({}))


# --- Selection ----------------------------------------------------------------


def test_selection_splits_integration_and_ui_markers() -> None:
    """
    GIVEN a mixed selection
    WHEN split by kind
    THEN each list is sorted and holds only its own kind
    """
    selection = _resolve(["backend/urls/services/create_urls.py"])

    assert selection.integration_markers(DECLARED_MARKERS) == ["mobile_api", "urls"]
    assert selection.ui_markers(DECLARED_MARKERS) == [
        "create_urls_ui",
        "mobile_ui",
        "update_urls_ui",
        "urls_ui",
    ]


def test_everything_selection_expands_to_every_declared_marker() -> None:
    """
    GIVEN an everything selection
    WHEN split by kind
    THEN every declared non-UI and UI marker is returned
    """
    selection = _resolve(["tests/conftest.py"])

    expected_ui = sorted(
        marker for marker in DECLARED_MARKERS if marker.endswith("_ui")
    )
    expected_integration = sorted(DECLARED_MARKERS - set(expected_ui))
    assert selection.integration_markers(DECLARED_MARKERS) == expected_integration
    assert selection.ui_markers(DECLARED_MARKERS) == expected_ui
    assert expected_integration
    assert expected_ui


# --- read_declared_markers ---------------------------------------------------


def test_read_declared_markers_reads_the_committed_pytest_ini() -> None:
    """
    GIVEN the committed pytest.ini
    WHEN its markers block is parsed
    THEN all 23 declared markers come back
    """
    assert len(DECLARED_MARKERS) == DECLARED_MARKER_COUNT
    assert {"unit", "mobile_api", "create_urls_ui", "admin_ui"} <= DECLARED_MARKERS


def test_read_declared_markers_ignores_other_indented_blocks(tmp_path: Path) -> None:
    """
    GIVEN a pytest.ini whose filterwarnings block has colon-bearing lines
    WHEN markers are read
    THEN only the markers block contributes, and parsing stops at the next key
    """
    pytest_ini = tmp_path / "pytest.ini"
    pytest_ini.write_text(
        "[pytest]\n"
        "filterwarnings =\n"
        "\tignore::DeprecationWarning:flask_wtf.*:\n"
        "markers =\n"
        "\ttags: associated with utub tags\n"
        "\tslow(reason): takes a while\n"
        "addopts = -v\n"
        "\tstray: not a marker\n",
        encoding="utf-8",
    )

    assert read_declared_markers(pytest_ini) == {"tags", "slow"}


def test_read_declared_markers_accepts_a_header_without_spaces(
    tmp_path: Path,
) -> None:
    """
    GIVEN a pytest.ini whose header is `markers=` (no spaces around `=`)
    WHEN markers are read
    THEN the block is still found and parsed
    """
    pytest_ini = tmp_path / "pytest.ini"
    pytest_ini.write_text("[pytest]\nmarkers=\n\tunit: unit tests\n", encoding="utf-8")

    assert read_declared_markers(pytest_ini) == {"unit"}


def test_read_declared_markers_skips_indented_comment_lines(tmp_path: Path) -> None:
    """
    GIVEN a markers block holding an indented `#` comment line
    WHEN markers are read
    THEN the comment is not parsed as a marker
    """
    pytest_ini = tmp_path / "pytest.ini"
    pytest_ini.write_text(
        "[pytest]\nmarkers =\n\t# UI markers\n\tsplash_ui: splash UI\n",
        encoding="utf-8",
    )

    assert read_declared_markers(pytest_ini) == {"splash_ui"}


def test_read_declared_markers_raises_when_no_markers_are_declared(
    tmp_path: Path,
) -> None:
    """
    GIVEN a pytest.ini with no markers block
    WHEN markers are read
    THEN ValueError is raised rather than an empty set
    """
    pytest_ini = tmp_path / "pytest.ini"
    pytest_ini.write_text("[pytest]\naddopts = -v\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no markers declared"):
        read_declared_markers(pytest_ini)


def test_read_declared_markers_rejects_an_invalid_marker_name(tmp_path: Path) -> None:
    """
    GIVEN a markers block declaring a name that is not a bare identifier
    WHEN markers are read
    THEN ValueError names the file and the bad marker, so it never reaches -m
    """
    pytest_ini = tmp_path / "pytest.ini"
    pytest_ini.write_text(
        "[pytest]\nmarkers =\n\tunit: unit tests\n\tx;y: bad\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match=r"invalid marker name in .*'x;y'"):
        read_declared_markers(pytest_ini)


# --- collect_changed_files ---------------------------------------------------


def _completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class _FakeGit:
    """Canned `git` responses keyed by subcommand, recording every call."""

    def __init__(self, responses: dict[str, subprocess.CompletedProcess[str]]) -> None:
        self.responses = responses
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(
        self, command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, kwargs))
        return self.responses[command[1]]


def test_collect_changed_files_unions_diff_and_untracked() -> None:
    """
    GIVEN a merge-base, a diff and untracked files that overlap
    WHEN changed files are collected
    THEN the sorted, de-duplicated union comes back
    """
    fake_git = _FakeGit(
        {
            "merge-base": _completed(0, f"{MERGE_BASE_SHA}\n"),
            "diff": _completed(0, "scripts/b.py\0Makefile\0"),
            "ls-files": _completed(0, "scripts/a.py\0Makefile\0docs/café.md\0"),
        }
    )

    changed = collect_changed_files("origin/main", run=fake_git)

    assert changed == ["Makefile", "docs/café.md", "scripts/a.py", "scripts/b.py"]
    commands = [command for command, _ in fake_git.calls]
    assert commands == [
        ["git", "merge-base", "origin/main", "HEAD"],
        ["git", "diff", "--name-only", "--no-renames", "-z", MERGE_BASE_SHA],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    ]
    for _, kwargs in fake_git.calls:
        assert kwargs == {
            "cwd": REPO_ROOT,
            "capture_output": True,
            "text": True,
            "check": False,
        }


def test_collect_changed_files_raises_on_unresolvable_merge_base() -> None:
    """
    GIVEN a base ref git cannot resolve
    WHEN changed files are collected
    THEN SelectionError names the base and the fix, without running the diff
    """
    fake_git = _FakeGit({"merge-base": _completed(128, stderr="fatal: bad ref\n")})

    with pytest.raises(SelectionError) as raised:
        collect_changed_files("refs/does-not-exist", run=fake_git)

    assert str(raised.value) == (
        "cannot resolve merge-base with refs/does-not-exist — run git fetch origin"
    )
    assert len(fake_git.calls) == 1


@pytest.mark.parametrize("failing_command", ["diff", "ls-files"])
def test_collect_changed_files_raises_when_a_listing_fails(
    failing_command: str,
) -> None:
    """
    GIVEN a resolvable merge-base but a failing diff or ls-files
    WHEN changed files are collected
    THEN SelectionError is raised instead of a silently partial list
    """
    responses = {
        "merge-base": _completed(0, f"{MERGE_BASE_SHA}\n"),
        "diff": _completed(0, "Makefile\0"),
        "ls-files": _completed(0, ""),
    }
    responses[failing_command] = _completed(1, stderr="fatal: broken\n")

    with pytest.raises(SelectionError, match="fatal: broken"):
        collect_changed_files("origin/main", run=_FakeGit(responses))


def test_collect_changed_files_rejects_an_option_like_base() -> None:
    """
    GIVEN a base that starts with "-" (would be parsed by git as an option)
    WHEN changed files are collected
    THEN SelectionError is raised before any git command runs
    """
    fake_git = _FakeGit({})

    with pytest.raises(SelectionError) as raised:
        collect_changed_files("--output=/tmp/x", run=fake_git)

    assert str(raised.value) == "base must not start with '-': --output=/tmp/x"
    assert fake_git.calls == []


def test_collect_changed_files_wraps_a_git_launch_failure() -> None:
    """
    GIVEN a run seam that raises OSError (e.g. git is not installed)
    WHEN changed files are collected
    THEN SelectionError names the launch failure
    """

    def missing_git(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(2, "No such file or directory", "git")

    with pytest.raises(SelectionError, match="cannot run git: .*No such file"):
        collect_changed_files("origin/main", run=missing_git)


def test_collect_changed_files_wraps_non_utf8_git_output() -> None:
    """
    GIVEN a run seam that raises UnicodeDecodeError (a non-UTF-8 file name)
    WHEN changed files are collected
    THEN SelectionError says the git output is not UTF-8
    """

    def undecodable_git(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    with pytest.raises(SelectionError, match="not UTF-8"):
        collect_changed_files("origin/main", run=undecodable_git)


# --- table consistency (committed registry + pytest.ini) ----------------------


def _committed_registry() -> dict[str, Any]:
    return json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))


def _all_table_markers() -> set[str]:
    groups = [
        *BLUEPRINT_MARKERS.values(),
        *ENDPOINT_MARKER_OVERRIDES.values(),
        *(markers for _, markers in PATH_MARKERS),
    ]
    return {marker for group in groups for marker in group}


def test_every_table_marker_is_declared_in_pytest_ini() -> None:
    """
    GIVEN every marker named by BLUEPRINT_MARKERS, overrides and PATH_MARKERS
    WHEN compared with pytest.ini's declared markers
    THEN none is undeclared
    """
    assert _all_table_markers() - DECLARED_MARKERS == set()


def test_every_declared_marker_is_reachable_from_a_table_row() -> None:
    """
    GIVEN pytest.ini's declared markers
    WHEN compared with every marker the tables name
    THEN each declared marker is reachable from some row
    """
    assert DECLARED_MARKERS - _all_table_markers() == set()


def test_blueprint_table_matches_the_committed_registry() -> None:
    """
    GIVEN the committed endpoint registry
    WHEN its blueprints are compared with BLUEPRINT_MARKERS
    THEN the two sets are identical
    """
    blueprints = {row["blueprint"] for row in _committed_registry()["endpoints"]}

    assert set(BLUEPRINT_MARKERS) == blueprints


def test_every_endpoint_override_names_a_real_endpoint() -> None:
    """
    GIVEN the committed endpoint registry
    WHEN ENDPOINT_MARKER_OVERRIDES keys are checked against it
    THEN every override names a real endpoint
    """
    endpoints = {row["endpoint"] for row in _committed_registry()["endpoints"]}

    assert set(ENDPOINT_MARKER_OVERRIDES) <= endpoints


@pytest.mark.parametrize("tests_subdir", ["integration", "functional"])
def test_every_test_directory_has_a_path_row(tests_subdir: str) -> None:
    """
    GIVEN every directory under tests/integration or tests/functional
    WHEN a helper file inside it is resolved
    THEN it matches a PATH_MARKERS row or a BROAD_GLOBS entry
    """
    test_dirs = sorted(
        child
        for child in (REPO_ROOT / "tests" / tests_subdir).iterdir()
        if child.is_dir() and child.name != "__pycache__"
    )
    assert test_dirs

    unmapped = [
        test_dir.name
        for test_dir in test_dirs
        if affected_markers._path_row(f"tests/{tests_subdir}/{test_dir.name}/helper.py")
        is None
        and affected_markers._first_match(
            f"tests/{tests_subdir}/{test_dir.name}/helper.py", BROAD_GLOBS
        )
        is None
    ]
    assert unmapped == []


def test_every_host_static_entry_has_an_explicit_path_disposition() -> None:
    """
    GIVEN every HOST_STATIC_GLOBS entry
    WHEN a probe path for it is looked up in PATH_MARKERS
    THEN each has an explicit row, so none falls through to everything
    """
    probes = {
        glob: glob.replace("*", "compose.local.yaml") for glob in HOST_STATIC_GLOBS
    }

    missing = [
        glob
        for glob, probe in probes.items()
        if affected_markers._path_row(probe) is None
    ]

    assert missing == []
    assert affected_markers._path_row("Makefile") == ("Makefile", ())
    assert affected_markers._path_row("docker/compose.local.yaml") == (
        "docker/*",
        (),
    )
    for script in (
        "scripts/token_budget.py",
        "scripts/capacity.py",
        "scripts/spoke_ports.py",
    ):
        path_row = affected_markers._path_row(script)
        assert path_row is not None
        assert path_row[1] == ("unit",)


def test_handler_files_resolve_to_a_superset_of_their_blueprint_markers() -> None:
    """
    GIVEN every handler file in the committed registry
    WHEN its PATH_MARKERS row is looked up
    THEN the row covers the blueprint's markers (catches a backend dir whose
        name differs from its blueprint, like backend/tags/)
    """
    mismatched: list[tuple[str, str]] = []
    for row in _committed_registry()["endpoints"]:
        handler_file = row["handler"].split(":")[0]
        path_row = affected_markers._path_row(handler_file)
        path_markers = set(path_row[1]) if path_row is not None else set()
        if not set(BLUEPRINT_MARKERS[row["blueprint"]]) <= path_markers:
            mismatched.append((row["endpoint"], handler_file))

    assert mismatched == []


def test_committed_registry_resolves_every_handler_without_everything() -> None:
    """
    GIVEN every real route file in the committed registry
    WHEN they resolve through that registry
    THEN named markers are selected, never the everything default
    """
    registry = _committed_registry()
    handler_files = sorted(
        {row["handler"].split(":")[0] for row in registry["endpoints"]}
    )

    selection = resolve_markers(handler_files, registry, DECLARED_MARKERS, _reader({}))

    assert not selection.everything
    assert "mobile_api" in selection.markers


# --- formatting ---------------------------------------------------------------


def test_format_expression_joins_sorted_markers_with_or() -> None:
    """
    GIVEN an unsorted marker set
    WHEN it is formatted as a pytest -m expression
    THEN the markers are sorted and joined with " or "
    """
    assert format_expression(frozenset({"urls", "mobile_api"})) == "mobile_api or urls"


def test_format_expression_of_nothing_is_empty() -> None:
    """
    GIVEN an empty marker set
    WHEN it is formatted
    THEN the expression is the empty string
    """
    assert format_expression(frozenset()) == ""


def test_format_report_lists_each_file_then_the_footer() -> None:
    """
    GIVEN a selection over a route file and a no-impact file
    WHEN it is formatted as a report
    THEN each file gets one `path  →  markers (reason)` line, then the footer
    """
    selection = _resolve(["README.md", "backend/members/routes.py"])

    report = format_report(selection, DECLARED_MARKERS)

    assert report.splitlines() == [
        "README.md  →  — (no test impact)",
        "backend/members/routes.py  →  members, members_ui "
        "(registry handler members.add_member; path backend/members/*)",
        "",
        "Integration: members",
        "UI: members_ui",
        "Host-static: no",
    ]


def test_format_report_names_an_everything_selection() -> None:
    """
    GIVEN a broad change that selects everything
    WHEN it is formatted as a report
    THEN the footer says everything and still lists the full marker sets
    """
    selection = _resolve(["tests/conftest.py", "Makefile"])

    footer = format_report(selection, DECLARED_MARKERS).splitlines()[-3:]

    assert footer[0].startswith("Integration: everything — account_and_support or ")
    assert footer[1].startswith("UI: everything — admin_ui or ")
    assert footer[2] == "Host-static: yes"


def test_format_report_of_an_empty_diff() -> None:
    """
    GIVEN no changed files
    WHEN it is formatted as a report
    THEN it says so and the footer selects nothing
    """
    report = format_report(_resolve([]), DECLARED_MARKERS)

    assert report.splitlines() == [
        "No changed files.",
        "",
        "Integration: none",
        "UI: none",
        "Host-static: no",
    ]


@pytest.mark.parametrize(
    ("changed_files", "warns"),
    [
        (["backend/members/routes.py"], True),
        (["backend/api_v1/url_routes.py"], True),
        (
            [
                "backend/members/routes.py",
                "docs/endpoints/endpoint-registry.json",
            ],
            False,
        ),
        (["backend/members/services/create_members.py"], False),
        ([], False),
    ],
)
def test_registry_staleness_warning(changed_files: list[str], warns: bool) -> None:
    """
    GIVEN a changed-file set
    WHEN it is checked for a route change without a registry regeneration
    THEN a warning is returned exactly when a route file changed alone
    """
    warning = registry_staleness_warning(changed_files)

    if warns:
        assert warning == (
            "WARNING: route file changed but endpoint registry not regenerated"
            " — run make generate-endpoints"
        )
    else:
        assert warning is None


# --- main() -------------------------------------------------------------------


def _write_registry(tmp_path: Path, registry: dict[str, Any] = REGISTRY) -> Path:
    registry_path = tmp_path / "endpoint-registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    return registry_path


def _run_main(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
    *,
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[int, str, str]:
    exit_code = main(argv, run=run)
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("integration", "members\n"), ("ui", "members_ui\n")],
)
def test_main_expr_prints_the_markers_of_one_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str, expected: str
) -> None:
    """
    GIVEN a members route file and a registry naming it
    WHEN `expr --kind <kind>` runs
    THEN only that kind's markers are printed, and it exits 0
    """
    registry_path = _write_registry(tmp_path)

    exit_code, out, err = _run_main(
        [
            "expr",
            "--kind",
            kind,
            "--files",
            "backend/members/routes.py",
            "--registry",
            str(registry_path),
        ],
        capsys,
    )

    assert (exit_code, out, err) == (0, expected, "")


def test_main_expr_joins_several_markers_with_or(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN a shared urls service that fans out to api_v1
    WHEN `expr --kind integration` runs
    THEN the sorted markers are joined with " or "
    """
    registry_path = _write_registry(tmp_path)

    exit_code, out, _ = _run_main(
        [
            "expr",
            "--kind",
            "integration",
            "--files",
            "backend/urls/services/create_urls.py",
            "--registry",
            str(registry_path),
        ],
        capsys,
    )

    assert (exit_code, out) == (0, "mobile_api or urls\n")


@pytest.mark.parametrize("files", [[], ["README.md"]])
def test_main_expr_of_an_empty_selection_prints_an_empty_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], files: list[str]
) -> None:
    """
    GIVEN no changed files, or only no-impact ones
    WHEN `expr` runs
    THEN an empty line is printed and it exits 0
    """
    registry_path = _write_registry(tmp_path)

    exit_code, out, _ = _run_main(
        [
            "expr",
            "--kind",
            "integration",
            "--registry",
            str(registry_path),
            "--files",
            *files,
        ],
        capsys,
    )

    assert (exit_code, out) == (0, "\n")


@pytest.mark.parametrize("kind", ["integration", "ui"])
def test_main_expr_of_everything_prints_every_declared_marker_of_its_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    """
    GIVEN a broad change (tests/conftest.py)
    WHEN `expr --kind <kind>` runs
    THEN every declared marker of that kind is printed, joined with " or "
    """
    registry_path = _write_registry(tmp_path)
    is_ui = kind == "ui"
    expected = " or ".join(
        sorted(
            marker for marker in DECLARED_MARKERS if marker.endswith(UI_SUFFIX) == is_ui
        )
    )

    exit_code, out, _ = _run_main(
        [
            "expr",
            "--kind",
            kind,
            "--files",
            "tests/conftest.py",
            "--registry",
            str(registry_path),
        ],
        capsys,
    )

    assert (exit_code, out) == (0, f"{expected}\n")


@pytest.mark.parametrize(
    ("files", "expected"),
    [(["Makefile"], "1\n"), (["backend/members/routes.py"], "0\n"), ([], "0\n")],
)
def test_main_host_static_prints_one_or_zero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    files: list[str],
    expected: str,
) -> None:
    """
    GIVEN a changed-file set
    WHEN `host-static` runs
    THEN it prints 1 when a host-static file changed, else 0
    """
    registry_path = _write_registry(tmp_path)

    exit_code, out, _ = _run_main(
        ["host-static", "--registry", str(registry_path), "--files", *files], capsys
    )

    assert (exit_code, out) == (0, expected)


def test_main_report_prints_the_report_and_warns_on_a_stale_registry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN a changed route file without a regenerated registry
    WHEN `report` runs
    THEN the report goes to stdout and the staleness warning to stderr
    """
    registry_path = _write_registry(tmp_path)

    exit_code, out, err = _run_main(
        [
            "report",
            "--files",
            "backend/members/routes.py",
            "--registry",
            str(registry_path),
        ],
        capsys,
    )

    assert exit_code == 0
    assert out.startswith("backend/members/routes.py  →  members, members_ui (")
    assert out.endswith("Integration: members\nUI: members_ui\nHost-static: no\n")
    assert err == (
        "WARNING: route file changed but endpoint registry not regenerated"
        " — run make generate-endpoints\n"
    )


def test_main_report_does_not_warn_when_the_registry_was_regenerated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN a changed route file alongside the regenerated registry JSON
    WHEN `report` runs
    THEN no staleness warning is printed
    """
    registry_path = _write_registry(tmp_path)

    exit_code, _, err = _run_main(
        [
            "report",
            "--files",
            "backend/members/routes.py",
            "docs/endpoints/endpoint-registry.json",
            "--registry",
            str(registry_path),
        ],
        capsys,
    )

    assert (exit_code, err) == (0, "")


def test_main_collects_the_diff_when_no_files_are_given(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN no --files, so the changed set comes from git
    WHEN `expr` runs with a custom --base
    THEN the faked git diff drives the selection against that base
    """
    registry_path = _write_registry(tmp_path)
    fake_git = _FakeGit(
        {
            "merge-base": _completed(0, f"{MERGE_BASE_SHA}\n"),
            "diff": _completed(0, "backend/members/routes.py\0"),
            "ls-files": _completed(0, ""),
        }
    )

    exit_code, out, _ = _run_main(
        [
            "expr",
            "--kind",
            "integration",
            "--base",
            "origin/dev",
            "--registry",
            str(registry_path),
        ],
        capsys,
        run=fake_git,
    )

    assert (exit_code, out) == (0, "members\n")
    assert fake_git.calls[0][0] == ["git", "merge-base", "origin/dev", "HEAD"]


@pytest.mark.parametrize(
    "command",
    [["expr", "--kind", "integration"], ["expr", "--kind", "ui"], ["host-static"]],
)
def test_main_defaults_the_base_to_origin_main(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    """
    GIVEN no --base
    WHEN a subcommand collects the diff
    THEN git resolves the merge-base against origin/main
    """
    registry_path = _write_registry(tmp_path)
    fake_git = _FakeGit(
        {
            "merge-base": _completed(0, f"{MERGE_BASE_SHA}\n"),
            "diff": _completed(0, ""),
            "ls-files": _completed(0, ""),
        }
    )

    exit_code, _, _ = _run_main(
        [*command, "--registry", str(registry_path)], capsys, run=fake_git
    )

    assert exit_code == 0
    assert fake_git.calls[0][0] == ["git", "merge-base", "origin/main", "HEAD"]


SUBCOMMANDS: list[list[str]] = [
    ["expr", "--kind", "integration"],
    ["expr", "--kind", "ui"],
    ["host-static"],
    ["report"],
]


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_main_reports_a_missing_registry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    """
    GIVEN a --registry path that does not exist
    WHEN any subcommand runs
    THEN it exits 1 with the regenerate hint on stderr and nothing on stdout
    """
    missing_path = tmp_path / "absent.json"

    exit_code, out, err = _run_main(
        [*command, "--files", "Makefile", "--registry", str(missing_path)], capsys
    )

    assert (exit_code, out) == (1, "")
    assert err == (
        f"endpoint registry not found: {missing_path} — run make generate-endpoints\n"
    )


@pytest.mark.parametrize(
    "registry_text",
    ["{not json", '{"no_endpoints": []}', '{"endpoints": [{"blueprint": "x"}]}'],
)
def test_main_reports_a_malformed_registry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], registry_text: str
) -> None:
    """
    GIVEN a registry that is not JSON, or lacks the expected shape
    WHEN `report` runs
    THEN it exits 1 with "endpoint registry unreadable" on stderr
    """
    registry_path = tmp_path / "endpoint-registry.json"
    registry_path.write_text(registry_text, encoding="utf-8")

    exit_code, out, err = _run_main(
        ["report", "--files", "Makefile", "--registry", str(registry_path)], capsys
    )

    assert (exit_code, out) == (1, "")
    assert err.startswith(f"endpoint registry unreadable: {registry_path} — ")


@pytest.mark.parametrize("command", SUBCOMMANDS)
def test_main_surfaces_a_selection_error_from_every_subcommand(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    """
    GIVEN a base git cannot resolve
    WHEN any subcommand collects the diff
    THEN it exits 1 with the SelectionError message on stderr and empty stdout
    """
    registry_path = _write_registry(tmp_path)
    fake_git = _FakeGit({"merge-base": _completed(128, stderr="fatal: bad ref\n")})

    exit_code, out, err = _run_main(
        [*command, "--base", "refs/does-not-exist", "--registry", str(registry_path)],
        capsys,
        run=fake_git,
    )

    assert (exit_code, out) == (1, "")
    assert err == (
        "cannot resolve merge-base with refs/does-not-exist — run git fetch origin\n"
    )


def test_main_reports_an_unreadable_pytest_ini(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN a --pytest-ini that declares no markers
    WHEN `expr` runs
    THEN it exits 1 naming the file, with empty stdout
    """
    registry_path = _write_registry(tmp_path)
    pytest_ini = tmp_path / "pytest.ini"
    pytest_ini.write_text("[pytest]\naddopts = -v\n", encoding="utf-8")

    exit_code, out, err = _run_main(
        [
            "expr",
            "--kind",
            "integration",
            "--files",
            "Makefile",
            "--registry",
            str(registry_path),
            "--pytest-ini",
            str(pytest_ini),
        ],
        capsys,
    )

    assert (exit_code, out) == (1, "")
    assert err == f"no markers declared in {pytest_ini}\n"


def test_main_requires_a_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    """
    GIVEN no subcommand
    WHEN main() runs
    THEN argparse exits 2 with a usage error
    """
    with pytest.raises(SystemExit) as raised:
        main([])

    assert raised.value.code == 2
    assert "affected_markers.py" in capsys.readouterr().err


def test_read_repo_file_returns_none_for_a_missing_file() -> None:
    """
    GIVEN a repo-relative path that does not exist (a deleted test file)
    WHEN it is read through the default read_text seam
    THEN None comes back, and an existing file returns its text
    """
    assert affected_markers._read_repo_file("tests/unit/test_gone_forever.py") is None
    assert "pytestmark = pytest.mark.unit" in (
        affected_markers._read_repo_file("tests/unit/test_affected_markers.py") or ""
    )


# --- stdlib-only guard --------------------------------------------------------


def test_affected_markers_module_is_stdlib_only() -> None:
    """
    GIVEN affected_markers.py, which runs on the host under bare mise python
    WHEN it is loaded in a fresh interpreter without the project root
    THEN no third-party or backend module is imported (stdlib only)

    Loaded by file path in a fresh interpreter with a pruned `sys.path` (no
    project root), so any third-party or `backend` import would either fail or
    show up in `sys.modules`.
    """
    probe_script = (
        "import importlib.util\n"
        "import sys\n"
        "sys.path = [p for p in sys.path if p not in ('', PROJECT_ROOT)]\n"
        "spec = importlib.util.spec_from_file_location('affected_leaf', MODULE_FILE)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        # Register before exec so the frozen dataclasses can resolve their own
        # module under `from __future__ import annotations`.
        "sys.modules[spec.name] = module\n"
        "spec.loader.exec_module(module)\n"
        "forbidden = [name for name in sys.modules "
        "if name.split('.')[0] in ('flask', 'sqlalchemy', 'redis', 'backend')]\n"
        "assert forbidden == [], forbidden\n"
    )
    module_file = Path(affected_markers.__file__).resolve()
    project_root = module_file.parents[1]
    preamble = (
        f"PROJECT_ROOT = {str(project_root)!r}\nMODULE_FILE = {str(module_file)!r}\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", preamble + probe_script],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"affected_markers module pulled in a non-stdlib import:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
