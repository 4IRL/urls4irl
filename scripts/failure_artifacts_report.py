"""Print what failed in a UI test run and where each piece of evidence is.

Run by `make test-artifacts [run=<id>]` on the host, with no stack: it reads the
artifact tree the UI page fixtures write on failure
(`tmp/test-artifacts/<run_id>/<test>/...`, see
`tests/functional/failure_artifacts.py`) and prints, per failing test, its
nodeid, phase, first error line, console/page/network counts and the absolute
paths of every artifact file.

With no `--run`, the run comes from `<root>/latest.json`. Exit codes: 0 on a
report (or when nothing was ever recorded), 1 on an unreadable index, 2 on an
unknown `--run` (the available run ids are listed). Stdlib only: it runs on the
host under bare mise python, so it must not import `tests/` — the schema keys
below duplicate `tests/functional/failure_artifacts.py`; change both together.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Mirrors of tests/functional/failure_artifacts.py (FAILURE_FILE, CONSOLE_FILE,
# NETWORK_FILE, TRACE_FILE, INDEX_FILE, LATEST_FILE, RUN_ID_PATTERN).
FAILURE_FILE: str = "failure.json"
CONSOLE_FILE: str = "console.json"
NETWORK_FILE: str = "network.json"
TRACE_FILE: str = "trace.zip"
INDEX_FILE: str = "index.json"
LATEST_FILE: str = "latest.json"
RUN_ID_PATTERN: re.Pattern[str] = re.compile(r"[0-9a-f]{8}")
PAGE_FILE_PATTERN: re.Pattern[str] = re.compile(r"page-(\d+)\.(png|html)")

DEFAULT_ROOT: Path = Path("tmp") / "test-artifacts"
UNKNOWN_COUNT: str = "?"
TRACE_HINT: str = (
    "open a trace: https://trace.playwright.dev (drag trace.zip)"
    " — console/network/DOM are plain files"
)

EXIT_UNREADABLE: int = 1
EXIT_UNKNOWN_RUN: int = 2


class ReportError(Exception):
    """A report that can't be rendered; carries the CLI exit code."""

    def __init__(self, message: str, *, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _read_json_object(path: Path) -> dict[str, object] | None:
    """The JSON object at `path`, or None if it is missing, unreadable or not an object."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return None
    return payload if isinstance(payload, dict) else None


def available_run_ids(*, root: Path) -> list[str]:
    """Run ids under `root` that have an `index.json`, newest first (by mtime)."""
    if not root.is_dir():
        return []
    runs: list[tuple[float, str]] = []
    for path in root.iterdir():
        if not RUN_ID_PATTERN.fullmatch(path.name):
            continue
        index_path = path / INDEX_FILE
        try:
            if path.is_symlink() or not index_path.is_file():
                continue
            runs.append((index_path.stat().st_mtime, path.name))
        except OSError:
            continue
    runs.sort(reverse=True)
    return [run_id for _mtime, run_id in runs]


def _unknown_run(*, root: Path, run_id: str) -> ReportError:
    available = available_run_ids(root=root)
    listing = ", ".join(available) if available else "none"
    return ReportError(
        f"unknown run '{run_id}' under {root} — available run ids: {listing}",
        exit_code=EXIT_UNKNOWN_RUN,
    )


def _first_line(value: object) -> str:
    lines = str(value or "").strip().splitlines()
    return lines[0] if lines else ""


def _count(counts: object, key: str) -> str:
    if isinstance(counts, dict) and isinstance(counts.get(key), int):
        return str(counts[key])
    return UNKNOWN_COUNT


def _page_sort_key(path: Path) -> tuple[int, str]:
    match = PAGE_FILE_PATTERN.fullmatch(path.name)
    return (int(match.group(1)) if match else 0, path.name)


def _artifact_paths(*, test_path: Path) -> list[Path]:
    """Every artifact file present in one test dir, in a stable reading order."""
    paths = [test_path / FAILURE_FILE]
    paths.extend(
        sorted(
            (
                path
                for path in test_path.glob("page-*")
                if PAGE_FILE_PATTERN.fullmatch(path.name)
            ),
            key=_page_sort_key,
        )
    )
    paths.extend(test_path / name for name in (CONSOLE_FILE, NETWORK_FILE, TRACE_FILE))
    return [path for path in paths if path.is_file()]


def _render_failure(*, run_path: Path, failure: dict[str, object]) -> list[str]:
    slug = str(failure.get("dir") or "")
    lines = [str(failure.get("nodeid") or slug or "<unknown test>")]
    lines.append(f"  phase: {failure.get('phase') or UNKNOWN_COUNT}")
    lines.append(f"  error: {_first_line(failure.get('error_summary'))}")
    counts = failure.get("counts")
    lines.append(
        f"  counts: console errors {_count(counts, 'console_errors')}"
        f" / page errors {_count(counts, 'page_errors')}"
        f" / failed requests {_count(counts, 'failed_requests')}"
    )
    # The slug is a single real directory name; anything else (incl. a symlink,
    # as for run dirs) could escape the run dir.
    test_path = run_path / slug
    if (
        not slug
        or Path(slug).name != slug
        or slug in (".", "..")
        or test_path.is_symlink()
    ):
        lines.append("  files: <missing or invalid test dir in index>")
        return lines
    artifact_paths = _artifact_paths(test_path=test_path)
    if not artifact_paths:
        lines.append(f"  files: <none found under {test_path}>")
    lines.extend(f"  {path}" for path in artifact_paths)
    record = _read_json_object(test_path / FAILURE_FILE) or {}
    capture_errors = record.get("capture_errors")
    if isinstance(capture_errors, list) and capture_errors:
        lines.append("  capture errors:")
        lines.extend(f"    - {error}" for error in capture_errors)
    return lines


def render_report(*, root: Path, run_id: str | None) -> str:
    """The report for `run_id` (or the run `latest.json` points at, when None).

    Raises `ReportError` for an unknown run id or an unreadable index.
    """
    root = root.resolve()
    if run_id is None:
        latest_path = root / LATEST_FILE
        if not latest_path.exists():
            return f"no UI failure artifacts recorded under {root}"
        latest = _read_json_object(latest_path)
        latest_run = latest.get("run_id") if latest else None
        if not isinstance(latest_run, str):
            raise ReportError(
                f"unreadable {latest_path} — rerun the UI tests or pass run=<id>",
                exit_code=EXIT_UNREADABLE,
            )
        run_id = latest_run

    if run_id not in available_run_ids(root=root):
        raise _unknown_run(root=root, run_id=run_id)
    run_path = root / run_id
    index = _read_json_object(run_path / INDEX_FILE)
    failures = index.get("failures") if index else None
    if not isinstance(failures, list):
        raise ReportError(
            f"unreadable {run_path / INDEX_FILE}", exit_code=EXIT_UNREADABLE
        )

    lines = [
        f"run {run_id} — {index.get('failure_count', len(failures))} failure(s)"
        f" — {index.get('created') or UNKNOWN_COUNT}"
    ]
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        lines.append("")
        lines.extend(_render_failure(run_path=run_path, failure=failure))
    lines.append("")
    lines.append(TRACE_HINT)
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="failure_artifacts_report",
        description="Print the UI failure-artifact index for the latest (or a given) run.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="artifact root (default: tmp/test-artifacts)",
    )
    parser.add_argument(
        "--run", default=None, help="run id to report (default: latest.json's run)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        report = render_report(root=args.root, run_id=args.run)
    except ReportError as report_error:
        print(str(report_error), file=sys.stderr)
        return report_error.exit_code
    print(report)
    return 0


__all__ = ["ReportError", "available_run_ids", "main", "render_report"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
