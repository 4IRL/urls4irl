"""Unit tests for `scripts/failure_artifacts_report.py` (`make test-artifacts`).

Fixture trees are built in `tmp_path` with the same `failure.json` keys
`capture_failure` writes, and `index.json`/`latest.json` come from the real
`write_run_index`, so a schema change on the writer side breaks these tests
instead of silently breaking the reader.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from scripts import failure_artifacts_report
from scripts.failure_artifacts_report import (
    TRACE_HINT,
    ReportError,
    available_run_ids,
    main,
    render_report,
)
from tests.functional import failure_artifacts
from tests.functional.failure_artifacts import sanitize_nodeid, write_run_index
from tests.unit.stdlib_only_utils import assert_module_is_stdlib_only

pytestmark = pytest.mark.unit

RUN_ID = "a1b2c3d4"
OLDER_RUN_ID = "0f0f0f0f"
CALL_NODEID = "tests/functional/urls_ui/test_access_url_ui.py::test_open_popup[desktop]"
SETUP_NODEID = "tests/functional/splash_ui/test_login_ui.py::test_login"


def _write_failure(
    *,
    root: Path,
    run_id: str,
    nodeid: str,
    phase: str = "call",
    error_summary: str = "AssertionError: smoke\nassert False",
    page_count: int = 1,
    trace: bool = True,
    capture_errors: list[str] | None = None,
) -> Path:
    """One test dir shaped like `capture_failure`'s output."""
    test_path = root / run_id / sanitize_nodeid(nodeid=nodeid)
    test_path.mkdir(parents=True)
    pages: list[dict[str, object]] = []
    for index in range(page_count):
        (test_path / f"page-{index}.png").write_bytes(b"png")
        (test_path / f"page-{index}.html").write_text("<html></html>", encoding="utf-8")
        pages.append(
            {
                "index": index,
                "url": "http://web/",
                "title": "u4i",
                "screenshot": f"page-{index}.png",
                "dom": f"page-{index}.html",
            }
        )
    (test_path / "console.json").write_text("{}", encoding="utf-8")
    (test_path / "network.json").write_text("{}", encoding="utf-8")
    if trace:
        (test_path / "trace.zip").write_bytes(b"zip")
    record = {
        "nodeid": nodeid,
        "phase": phase,
        "error_summary": error_summary,
        "worker": "gw0",
        "run_id": run_id,
        "captured_at": "2026-10-01T12:00:00+00:00",
        "pages": pages,
        "trace": "trace.zip" if trace else None,
        "console": "console.json",
        "network": "network.json",
        "counts": {"console_errors": 2, "page_errors": 1, "failed_requests": 3},
        "capture_errors": capture_errors or [],
    }
    (test_path / "failure.json").write_text(json.dumps(record), encoding="utf-8")
    return test_path


def _seed_run(*, root: Path, run_id: str = RUN_ID) -> tuple[Path, Path]:
    call_path = _write_failure(
        root=root, run_id=run_id, nodeid=CALL_NODEID, page_count=2
    )
    setup_path = _write_failure(
        root=root,
        run_id=run_id,
        nodeid=SETUP_NODEID,
        phase="setup",
        error_summary="TimeoutError: page.goto timed out",
        trace=False,
        capture_errors=["page-0.screenshot: Error: Target closed"],
    )
    write_run_index(root=root, run_id=run_id)
    return call_path, setup_path


def test_latest_report_lists_every_failure_with_absolute_paths(tmp_path: Path) -> None:
    """
    GIVEN a run with a call failure (popup + trace) and a setup failure
    WHEN the report renders from latest.json
    THEN the header, per-failure details, absolute artifact paths and hint appear
    """
    call_path, setup_path = _seed_run(root=tmp_path)

    report = render_report(root=tmp_path, run_id=None)
    lines = report.splitlines()

    assert lines[0].startswith(f"run {RUN_ID} — 2 failure(s) — ")
    assert CALL_NODEID in lines
    assert SETUP_NODEID in lines
    assert "  phase: call" in lines
    assert "  phase: setup" in lines
    assert "  error: AssertionError: smoke" in lines
    assert "assert False" not in report
    assert "  error: TimeoutError: page.goto timed out" in lines
    assert "  counts: console errors 2 / page errors 1 / failed requests 3" in lines
    for name in (
        "failure.json",
        "page-0.png",
        "page-0.html",
        "page-1.png",
        "page-1.html",
        "console.json",
        "network.json",
        "trace.zip",
    ):
        expected = call_path / name
        assert expected.is_absolute()
        assert f"  {expected}" in lines
    assert f"  {setup_path / 'trace.zip'}" not in lines
    assert "  capture errors:" in lines
    assert "    - page-0.screenshot: Error: Target closed" in lines
    assert lines[-1] == TRACE_HINT


def test_pages_list_in_numeric_order(tmp_path: Path) -> None:
    """
    GIVEN a failure with 11 pages
    WHEN the report renders
    THEN page-2 is listed before page-10 (numeric, not lexical)
    """
    test_path = _write_failure(
        root=tmp_path, run_id=RUN_ID, nodeid=CALL_NODEID, page_count=11
    )
    write_run_index(root=tmp_path, run_id=RUN_ID)

    report = render_report(root=tmp_path, run_id=None)

    assert report.index(str(test_path / "page-2.png")) < report.index(
        str(test_path / "page-10.png")
    )


def test_explicit_run_reports_an_older_run(tmp_path: Path) -> None:
    """
    GIVEN two runs, latest.json pointing at the newer one
    WHEN run_id names the older run
    THEN that run is reported
    """
    _write_failure(root=tmp_path, run_id=OLDER_RUN_ID, nodeid=SETUP_NODEID)
    write_run_index(root=tmp_path, run_id=OLDER_RUN_ID)
    _seed_run(root=tmp_path)

    report = render_report(root=tmp_path, run_id=OLDER_RUN_ID)

    assert report.splitlines()[0].startswith(f"run {OLDER_RUN_ID} — 1 failure(s) — ")
    assert CALL_NODEID not in report


def test_relative_root_resolves_to_absolute_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN the Makefile's relative --root tmp/test-artifacts
    WHEN the report renders from the checkout root
    THEN artifact paths are still absolute
    """
    root = tmp_path / "tmp" / "test-artifacts"
    call_path, _setup_path = _seed_run(root=root)
    monkeypatch.chdir(tmp_path)

    report = render_report(root=Path("tmp/test-artifacts"), run_id=None)

    assert f"  {call_path.resolve() / 'failure.json'}" in report.splitlines()


@pytest.mark.parametrize("root_exists", [True, False], ids=["empty-root", "no-root"])
def test_no_latest_json_exits_zero_with_a_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], root_exists: bool
) -> None:
    """
    GIVEN no latest.json (an empty or absent root)
    WHEN main runs
    THEN it exits 0 and says nothing was recorded
    """
    root = tmp_path / "test-artifacts"
    if root_exists:
        root.mkdir()

    exit_code = main(["--root", str(root)])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == (
        f"no UI failure artifacts recorded under {root.resolve()}"
    )


def test_unknown_run_exits_two_listing_available_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    GIVEN a recorded run
    WHEN main is given a run id that doesn't exist
    THEN it exits 2 and lists the available run ids on stderr
    """
    _seed_run(root=tmp_path)

    exit_code = main(["--root", str(tmp_path), "--run", "deadbeef"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "unknown run 'deadbeef'" in captured.err
    assert f"available run ids: {RUN_ID}" in captured.err


@pytest.mark.parametrize("run_value", ["../etc", "", RUN_ID + "/.."])
def test_run_outside_the_known_ids_is_refused(tmp_path: Path, run_value: str) -> None:
    """
    GIVEN a recorded run
    WHEN run_id is a traversal or empty value
    THEN it is an unknown run (exit 2), never a path lookup
    """
    _seed_run(root=tmp_path)

    with pytest.raises(ReportError) as raised:
        render_report(root=tmp_path, run_id=run_value)

    assert raised.value.exit_code == 2


def test_unknown_run_with_no_runs_says_none(tmp_path: Path) -> None:
    with pytest.raises(ReportError, match="available run ids: none"):
        render_report(root=tmp_path, run_id=RUN_ID)


def test_available_runs_are_newest_first_and_need_an_index(tmp_path: Path) -> None:
    """
    GIVEN two indexed runs, an index-less run dir and a non-run sibling
    WHEN available run ids are listed
    THEN only indexed runs appear, newest index first
    """
    _write_failure(root=tmp_path, run_id=OLDER_RUN_ID, nodeid=SETUP_NODEID)
    older_index = write_run_index(root=tmp_path, run_id=OLDER_RUN_ID)
    _seed_run(root=tmp_path)
    assert older_index is not None
    os.utime(older_index, (1_000_000, 1_000_000))
    (tmp_path / "cafebabe").mkdir()
    (tmp_path / "not-a-run").mkdir()

    assert available_run_ids(root=tmp_path) == [RUN_ID, OLDER_RUN_ID]


@pytest.mark.parametrize(
    "latest_content",
    ["not json", "[]", '{"run_id": 5}'],
    ids=["garbage", "list", "bad-id"],
)
def test_unreadable_latest_json_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], latest_content: str
) -> None:
    (tmp_path / "latest.json").write_text(latest_content, encoding="utf-8")

    assert main(["--root", str(tmp_path)]) == 1
    assert "unreadable" in capsys.readouterr().err


def test_unreadable_index_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_run(root=tmp_path)
    (tmp_path / RUN_ID / "index.json").write_text("{", encoding="utf-8")

    assert main(["--root", str(tmp_path)]) == 1
    assert "unreadable" in capsys.readouterr().err


def test_latest_pointing_at_a_pruned_run_is_unknown(tmp_path: Path) -> None:
    """
    GIVEN latest.json whose run dir was pruned
    WHEN the report renders
    THEN it is an unknown run (exit 2), not a crash
    """
    _seed_run(root=tmp_path)
    shutil.rmtree(tmp_path / RUN_ID)

    with pytest.raises(ReportError) as raised:
        render_report(root=tmp_path, run_id=None)

    assert raised.value.exit_code == 2


def test_invalid_test_dir_in_index_is_not_followed(tmp_path: Path) -> None:
    """
    GIVEN an index entry whose dir would escape the run dir
    WHEN the report renders
    THEN the entry is flagged and no path outside the run dir is printed
    """
    _seed_run(root=tmp_path)
    index_path = tmp_path / RUN_ID / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["failures"][0]["dir"] = "../.."
    index_path.write_text(json.dumps(index), encoding="utf-8")

    report = render_report(root=tmp_path, run_id=None)

    assert "  files: <missing or invalid test dir in index>" in report.splitlines()


def test_symlinked_test_dir_is_not_followed(tmp_path: Path) -> None:
    """
    GIVEN an index entry whose test dir is a symlink to a dir outside the run
    WHEN the report renders
    THEN the entry is flagged and nothing under the link target is printed
    """
    call_path, _setup_path = _seed_run(root=tmp_path)
    outside = tmp_path / "outside"
    shutil.move(call_path, outside)
    call_path.symlink_to(outside, target_is_directory=True)

    report = render_report(root=tmp_path, run_id=None)

    assert "  files: <missing or invalid test dir in index>" in report.splitlines()
    assert str(call_path / "failure.json") not in report


def test_deeply_nested_index_is_unreadable_not_a_crash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_run(root=tmp_path)
    (tmp_path / RUN_ID / "index.json").write_text("[" * 100_000, encoding="utf-8")

    assert main(["--root", str(tmp_path)]) == 1
    assert "unreadable" in capsys.readouterr().err


def test_schema_constants_match_the_writer() -> None:
    """
    GIVEN the reader duplicates the writer's file names (it must stay stdlib-only)
    WHEN compared to tests/functional/failure_artifacts.py
    THEN they agree
    """
    for name in (
        "FAILURE_FILE",
        "CONSOLE_FILE",
        "NETWORK_FILE",
        "TRACE_FILE",
        "INDEX_FILE",
        "LATEST_FILE",
    ):
        assert getattr(failure_artifacts_report, name) == getattr(
            failure_artifacts, name
        )
    assert (
        failure_artifacts_report.RUN_ID_PATTERN.pattern
        == failure_artifacts.RUN_ID_PATTERN.pattern
    )


def test_failure_artifacts_report_module_is_stdlib_only() -> None:
    """
    GIVEN failure_artifacts_report.py, which runs on the host under bare mise python
    WHEN it is loaded in a fresh interpreter without the project root
    THEN no third-party, backend or tests module is imported
    """
    assert_module_is_stdlib_only(
        Path(failure_artifacts_report.__file__),
        ("flask", "sqlalchemy", "redis", "backend", "tests", "playwright", "pytest"),
    )
