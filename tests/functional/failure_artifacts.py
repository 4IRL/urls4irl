"""Structured UI test-failure artifacts: what to record on failure, and where.

Leaf module — it imports nothing from any conftest or fixture module, so the
UI conftest (and pytester inner projects) can import it without a cycle.

On a failing UI test, `capture_failure` writes into
`<root>/<run_id>/<sanitized nodeid>/`:

- `page-<N>.png` / `page-<N>.html`: a full-page screenshot and DOM per open
  page in the context (popups included),
- `console.json`: recent console entries plus uncaught page errors,
- `network.json`: recent requests plus failed ones (status >= 400 or a
  network failure) — URLs only; headers and bodies are deliberately never
  captured (cookies/secrets),
- `trace.zip`: the Playwright trace (when tracing is on),
- `failure.json`: the record indexing all of the above.

Sensitivity: `console.json` / `network.json` exclude headers and bodies, but
`trace.zip` (Playwright tracing with snapshots) DOES include request/response
headers, cookies and bodies — keep it in local or private CI artifacts only,
never anywhere public.

Every capture step is isolated: a dead browser or full disk becomes an entry
in `failure.json["capture_errors"]`, never an exception in fixture teardown.
`write_run_index` then summarizes a run in `index.json` and points
`<root>/latest.json` at it; `prune_runs` bounds how many runs are kept.

It is also a pytest plugin, registered in the root `tests/conftest.py`
`pytest_plugins` (so its session hooks run on the xdist controller too, which
never imports `tests/functional/conftest.py`): `pytest_configure` pins one run
id shared by every worker (and rejects a bad knob as a usage error),
`pytest_sessionstart` prunes old runs, `pytest_runtest_makereport` stashes
each phase's report for `failure_phase`, and `pytest_sessionfinish` writes the
run index. The page fixtures wrap their browser context in
`recorded_context`, which captures on a failure and discards the trace
otherwise. Outside UI runs the hooks are inert: nothing is written unless a
test actually captured a failure, and an unreadable/unwritable artifact root
only warns, never fails the session.
"""

import hashlib
import json
import os
import re
import shutil
import uuid
import warnings
from collections import deque
from collections.abc import Callable, Generator, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

import pytest
from playwright.sync_api import BrowserContext, ConsoleMessage, Request, WebError

FUNCTIONAL_PREFIX = "tests/functional/"
NODEID_MAX_LENGTH = 120
NODEID_HASH_LENGTH = 8
DISALLOWED_SLUG_CHARS = re.compile(r"[^A-Za-z0-9._-]")

ARTIFACTS_DIR_ENV = "U4I_TEST_ARTIFACTS_DIR"
TRACE_ENV = "U4I_UI_TRACE"
KEEP_ENV = "U4I_TEST_ARTIFACTS_KEEP"
TRACE_RETAIN_ON_FAILURE = "retain-on-failure"
TRACE_OFF = "off"
TRACE_MODES = (TRACE_RETAIN_ON_FAILURE, TRACE_OFF)
DEFAULT_KEEP_RUNS = 10
# Run ids are the first 8 chars of a uuid4 hex; only such dirs are prunable.
RUN_ID_LENGTH = 8
RUN_ID_PATTERN = re.compile(rf"[0-9a-f]{{{RUN_ID_LENGTH}}}")
SUMMARY_FALLBACK_LENGTH = 500

BUFFER_LIMIT = 300
PAGE_ERROR_LIMIT = 100
FAILED_REQUEST_LIMIT = 100
FAILED_STATUS_FLOOR = 400

FAILURE_FILE = "failure.json"
CONSOLE_FILE = "console.json"
NETWORK_FILE = "network.json"
TRACE_FILE = "trace.zip"
INDEX_FILE = "index.json"
LATEST_FILE = "latest.json"

StepResult = TypeVar("StepResult")
EventPayload = TypeVar("EventPayload")


def sanitize_nodeid(*, nodeid: str) -> str:
    """Turn a pytest nodeid into a filesystem-safe directory name.

    Drops the `tests/functional/` prefix, maps `/` and `::` to `__`, replaces
    every other character outside `[A-Za-z0-9._-]` with `_`, and caps the
    result at `NODEID_MAX_LENGTH`. A truncated slug ends in an 8-hex
    `sha1(nodeid)` suffix, so ids differing only past the cap don't collide.
    """
    trimmed = nodeid.removeprefix(FUNCTIONAL_PREFIX)
    slug = DISALLOWED_SLUG_CHARS.sub(
        "_", trimmed.replace("::", "__").replace("/", "__")
    )
    if len(slug) <= NODEID_MAX_LENGTH:
        return slug
    digest = hashlib.sha1(nodeid.encode()).hexdigest()[:NODEID_HASH_LENGTH]
    return f"{slug[: NODEID_MAX_LENGTH - NODEID_HASH_LENGTH - 1]}_{digest}"


def run_dir(*, root: Path, run_id: str) -> Path:
    return root / run_id


def test_dir(*, root: Path, run_id: str, nodeid: str) -> Path:
    return run_dir(root=root, run_id=run_id) / sanitize_nodeid(nodeid=nodeid)


@dataclass(frozen=True)
class ArtifactSettings:
    root: Path
    trace: bool
    keep_runs: int


def load_settings(*, environ: Mapping[str, str], rootpath: Path) -> ArtifactSettings:
    """Read the artifact knobs, failing loudly on a value we can't honor.

    - `U4I_TEST_ARTIFACTS_DIR`: artifact root (relative resolves against
      `rootpath`); default `<rootpath>/tmp/test-artifacts`.
    - `U4I_UI_TRACE`: `retain-on-failure` (default) or `off`.
    - `U4I_TEST_ARTIFACTS_KEEP`: run dirs kept per root, >= 1; default 10.
    """
    raw_root = environ.get(ARTIFACTS_DIR_ENV, "")
    # `rootpath / "/abs"` is `/abs`, so an absolute override is kept as-is.
    root = rootpath / raw_root if raw_root else rootpath / "tmp" / "test-artifacts"

    trace_mode = environ.get(TRACE_ENV, "") or TRACE_RETAIN_ON_FAILURE
    if trace_mode not in TRACE_MODES:
        raise ValueError(
            f"{TRACE_ENV}={trace_mode!r} is invalid; allowed values: "
            f"{', '.join(TRACE_MODES)}"
        )

    raw_keep = environ.get(KEEP_ENV, "") or str(DEFAULT_KEEP_RUNS)
    try:
        keep_runs = int(raw_keep)
    except ValueError:
        keep_runs = 0
    if keep_runs < 1:
        raise ValueError(f"{KEEP_ENV}={raw_keep!r} is invalid; must be an integer >= 1")

    return ArtifactSettings(
        root=root, trace=trace_mode == TRACE_RETAIN_ON_FAILURE, keep_runs=keep_runs
    )


def _guarded(
    *, handler: Callable[[EventPayload], None]
) -> Callable[[EventPayload], None]:
    """Wrap an event listener so it can never raise into Playwright's dispatch."""

    def listener(payload: EventPayload) -> None:
        try:
            handler(payload)
        except Exception:
            pass

    return listener


class ContextRecorder:
    """Buffers console, page-error and network events for one browser context.

    Listeners are context-level, so popups opened from the test's page are
    covered too. Buffers (including the in-flight request map) are bounded so a
    chatty page can't grow memory, and every listener is guarded so a recording
    bug can never raise into Playwright's event dispatch.
    """

    def __init__(self) -> None:
        self.console: deque[dict[str, object]] = deque(maxlen=BUFFER_LIMIT)
        self.network: deque[dict[str, object]] = deque(maxlen=BUFFER_LIMIT)
        self.page_errors: list[dict[str, object]] = []
        self.failed_requests: list[dict[str, object]] = []
        self._in_flight: dict[Request, dict[str, object]] = {}

    def attach(self, *, context: BrowserContext) -> None:
        context.on("console", _guarded(handler=self._on_console))
        context.on("weberror", _guarded(handler=self._on_weberror))
        context.on("request", _guarded(handler=self._on_request))
        context.on("requestfinished", _guarded(handler=self._on_request_finished))
        context.on("requestfailed", _guarded(handler=self._on_request_failed))

    def _on_console(self, message: ConsoleMessage) -> None:
        location = message.location
        self.console.append(
            {
                "type": message.type,
                "text": message.text,
                "url": location.get("url", ""),
                "line": location.get("lineNumber", 0),
            }
        )

    def _on_weberror(self, web_error: WebError) -> None:
        if len(self.page_errors) >= PAGE_ERROR_LIMIT:
            return
        error = web_error.error
        self.page_errors.append({"message": error.message, "stack": error.stack})

    def _on_request(self, request: Request) -> None:
        entry: dict[str, object] = {
            "method": request.method,
            "url": request.url,
            "resource_type": request.resource_type,
            "status": None,
            "failure": None,
        }
        self.network.append(entry)
        self._in_flight[request] = entry
        if len(self._in_flight) > BUFFER_LIMIT:
            # Requests that never settle (e.g. a closed page) must not leak.
            self._in_flight.pop(next(iter(self._in_flight)))

    def _settle(self, request: Request) -> dict[str, object]:
        if request not in self._in_flight:
            self._on_request(request)
        return self._in_flight.pop(request)

    def _flag_failed(self, entry: dict[str, object]) -> None:
        if len(self.failed_requests) < FAILED_REQUEST_LIMIT:
            self.failed_requests.append(entry)

    def _on_request_finished(self, request: Request) -> None:
        entry = self._settle(request)
        try:
            response = request.response()
        except Exception:
            response = None
        if response is None:
            return
        entry["status"] = response.status
        if response.status >= FAILED_STATUS_FLOOR:
            self._flag_failed(entry)

    def _on_request_failed(self, request: Request) -> None:
        entry = self._settle(request)
        entry["failure"] = request.failure
        self._flag_failed(entry)


def _write_json_atomic(*, path: Path, payload: object) -> Path:
    # Unique per writer, so concurrent writers (e.g. to latest.json) can't race.
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    os.replace(temp_path, path)
    return path


def write_failure_record(*, dest: Path, record: dict[str, object]) -> Path:
    return _write_json_atomic(path=dest / FAILURE_FILE, payload=record)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_error(*, step: str, errors: list[str], exc: Exception) -> None:
    errors.append(f"{step}: {type(exc).__name__}: {exc}")


def _attempt(
    *, step: str, errors: list[str], action: Callable[[], StepResult]
) -> StepResult | None:
    """Run one value-returning capture step; record (never raise) any error."""
    try:
        return action()
    except Exception as exc:
        _record_error(step=step, errors=errors, exc=exc)
        return None


def _run_step(*, step: str, errors: list[str], action: Callable[[], object]) -> bool:
    """Run one side-effect capture step; True on success, error recorded else."""
    try:
        action()
    except Exception as exc:
        _record_error(step=step, errors=errors, exc=exc)
        return False
    return True


def _capture_pages(
    *, context: BrowserContext, dest: Path, errors: list[str]
) -> list[dict[str, object]]:
    pages = _attempt(step="pages", errors=errors, action=lambda: list(context.pages))
    records: list[dict[str, object]] = []
    for index, page in enumerate(pages or []):
        screenshot_name = f"page-{index}.png"
        dom_name = f"page-{index}.html"
        screenshot_taken = _run_step(
            step=f"page-{index}.screenshot",
            errors=errors,
            action=lambda: page.screenshot(path=dest / screenshot_name, full_page=True),
        )
        dom_written = _run_step(
            step=f"page-{index}.dom",
            errors=errors,
            action=lambda: (dest / dom_name).write_text(
                page.content(), encoding="utf-8"
            ),
        )
        records.append(
            {
                "index": index,
                "url": _attempt(
                    step=f"page-{index}.url", errors=errors, action=lambda: page.url
                ),
                "title": _attempt(
                    step=f"page-{index}.title", errors=errors, action=page.title
                ),
                "screenshot": screenshot_name if screenshot_taken else None,
                "dom": dom_name if dom_written else None,
            }
        )
    return records


def capture_failure(
    *,
    context: BrowserContext,
    recorder: ContextRecorder,
    dest: Path,
    nodeid: str,
    phase: str,
    error_summary: str,
    worker: str,
    run_id: str,
    trace: bool,
) -> Path:
    """Write every artifact for one failing test into `dest`; never raises.

    Returns the `failure.json` path (which may not exist if even the final
    record write failed — e.g. `dest` is unwritable).
    """
    errors: list[str] = []
    _run_step(
        step="mkdir",
        errors=errors,
        action=lambda: dest.mkdir(parents=True, exist_ok=True),
    )
    pages = _capture_pages(context=context, dest=dest, errors=errors)
    _run_step(
        step="console",
        errors=errors,
        action=lambda: _write_json_atomic(
            path=dest / CONSOLE_FILE,
            payload={
                "console": list(recorder.console),
                "page_errors": recorder.page_errors,
            },
        ),
    )
    _run_step(
        step="network",
        errors=errors,
        action=lambda: _write_json_atomic(
            path=dest / NETWORK_FILE,
            payload={
                "recent": list(recorder.network),
                "failed": recorder.failed_requests,
            },
        ),
    )
    trace_name: str | None = None
    if trace:
        trace_stopped = _run_step(
            step="trace",
            errors=errors,
            action=lambda: context.tracing.stop(path=dest / TRACE_FILE),
        )
        trace_name = TRACE_FILE if trace_stopped else None

    record: dict[str, object] = {
        "nodeid": nodeid,
        "phase": phase,
        "error_summary": error_summary,
        "worker": worker,
        "run_id": run_id,
        "captured_at": _utc_now_iso(),
        "pages": pages,
        "trace": trace_name,
        "console": CONSOLE_FILE,
        "network": NETWORK_FILE,
        "counts": {
            "console_errors": sum(
                1 for entry in recorder.console if entry["type"] == "error"
            ),
            "page_errors": len(recorder.page_errors),
            "failed_requests": len(recorder.failed_requests),
        },
        "capture_errors": errors,
    }
    _run_step(
        step="record",
        errors=errors,
        action=lambda: write_failure_record(dest=dest, record=record),
    )
    return dest / FAILURE_FILE


def discard_trace(*, context: BrowserContext) -> None:
    """Stop tracing without saving it — the passing-test path."""
    try:
        context.tracing.stop()
    except Exception:
        pass


def write_run_index(*, root: Path, run_id: str) -> Path | None:
    """Summarize a run's failures into `index.json` and repoint `latest.json`.

    Writes nothing (and returns None) when the run recorded no failure.
    """
    current_run_dir = run_dir(root=root, run_id=run_id)
    failures: list[dict[str, object]] = []
    for failure_path in current_run_dir.glob(f"*/{FAILURE_FILE}"):
        try:
            record = json.loads(failure_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict):
            continue
        failures.append(
            {
                "nodeid": record.get("nodeid"),
                "dir": failure_path.parent.name,
                "phase": record.get("phase"),
                "error_summary": record.get("error_summary"),
                "counts": record.get("counts"),
                "trace": bool(record.get("trace")),
            }
        )
    if not failures:
        return None

    failures.sort(key=lambda failure: str(failure["nodeid"]))
    created = _utc_now_iso()
    index_path = _write_json_atomic(
        path=current_run_dir / INDEX_FILE,
        payload={
            "run_id": run_id,
            "created": created,
            "failure_count": len(failures),
            "failures": failures,
        },
    )
    _write_json_atomic(
        path=root / LATEST_FILE,
        payload={
            "run_id": run_id,
            "index": f"{run_id}/{INDEX_FILE}",
            "failure_count": len(failures),
            "created": created,
        },
    )
    return index_path


def prune_runs(*, root: Path, keep: int) -> list[Path]:
    """Keep the newest `keep` run dirs (by mtime) under `root`; delete the rest.

    Only real (non-symlink) subdirectories named like a run id
    (`RUN_ID_PATTERN`, 8 lowercase hex) are candidates, so a misconfigured
    root never deletes unrelated siblings. Entries that vanish mid-scan are
    skipped.
    """
    if not root.is_dir():
        return []
    candidates: list[tuple[float, Path]] = []
    for path in root.iterdir():
        if not RUN_ID_PATTERN.fullmatch(path.name):
            continue
        try:
            if path.is_symlink() or not path.is_dir():
                continue
            mtime = path.stat().st_mtime
        except OSError:
            continue
        candidates.append((mtime, path))
    candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    removed = [path for _mtime, path in candidates[keep:]]
    for path in removed:
        shutil.rmtree(path, ignore_errors=True)
    return removed


# --- pytest wiring -----------------------------------------------------------

PHASE_REPORTS_KEY: pytest.StashKey[dict[str, pytest.TestReport]] = pytest.StashKey()


def _is_xdist_worker(*, config: pytest.Config) -> bool:
    return hasattr(config, "workerinput")


def resolve_run_id(*, config: pytest.Config) -> str:
    """The run id shared by the controller and every xdist worker of one run."""
    if _is_xdist_worker(config=config):
        return config.workerinput["testrunuid"][:RUN_ID_LENGTH]
    return config.option.testrunuid[:RUN_ID_LENGTH]


def failure_phase(*, item: pytest.Item) -> tuple[str, str] | None:
    """Return `(phase, error_summary)` if the test's call or setup failed.

    Teardown-phase failures are deliberately not captured: pytest reports
    them only after every fixture (the page fixture included) has already
    torn down, so there is no live browser context left to capture from.
    """
    reports = item.stash.get(PHASE_REPORTS_KEY, {})
    for phase in ("call", "setup"):
        report = reports.get(phase)
        if report is None or not report.failed:
            continue
        crash = getattr(report.longrepr, "reprcrash", None)
        message = getattr(crash, "message", None)
        summary = message if message else str(report.longrepr)[:SUMMARY_FALLBACK_LENGTH]
        return phase, summary
    return None


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    item.stash.setdefault(PHASE_REPORTS_KEY, {})[report.when] = report
    return report


def pytest_configure(config: pytest.Config) -> None:
    # Pin the run id before xdist's NodeManager reads --testrunuid (it does so
    # at session start), so every worker inherits this same uid.
    if _is_xdist_worker(config=config):
        return
    if not getattr(config.option, "testrunuid", None):
        config.option.testrunuid = uuid.uuid4().hex
    # Validate the knobs up front: a bad value is a clean usage error, not an
    # INTERNALERROR from a later session hook.
    try:
        load_settings(environ=os.environ, rootpath=config.rootpath)
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc


def pytest_sessionstart(session: pytest.Session) -> None:
    if _is_xdist_worker(config=session.config):
        return
    settings = load_settings(environ=os.environ, rootpath=session.config.rootpath)
    try:
        prune_runs(root=settings.root, keep=settings.keep_runs)
    except OSError as exc:
        warnings.warn(
            f"failure artifacts: could not prune old runs under {settings.root}: {exc}",
            stacklevel=1,
        )


def pytest_sessionfinish(session: pytest.Session) -> None:
    if _is_xdist_worker(config=session.config):
        return
    settings = load_settings(environ=os.environ, rootpath=session.config.rootpath)
    try:
        write_run_index(
            root=settings.root, run_id=resolve_run_id(config=session.config)
        )
    except OSError as exc:
        warnings.warn(
            f"failure artifacts: could not write the run index under "
            f"{settings.root}: {exc}",
            stacklevel=1,
        )


@contextmanager
def recorded_context(
    *,
    context: BrowserContext,
    request: pytest.FixtureRequest,
    settings: ArtifactSettings,
    worker_id: str,
) -> Iterator[ContextRecorder]:
    """Record a page fixture's context; capture artifacts if its test failed.

    Open it right after `new_context()`, around the whole fixture body
    including its `yield`, so tracing and listeners cover setup too:

    - an exception escaping the block (a pre-yield setup failure, e.g. a
      `page.goto()` timeout — pytest has no setup report for it yet) is
      captured as `phase="setup"` and re-raised;
    - on normal exit, a failed call/setup report (`failure_phase`) is
      captured, otherwise the trace is discarded.
    """
    recorder = ContextRecorder()
    recorder.attach(context=context)
    if settings.trace:
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
    item = request.node

    def capture(*, phase: str, error_summary: str) -> None:
        run_id = resolve_run_id(config=request.config)
        capture_failure(
            context=context,
            recorder=recorder,
            dest=test_dir(root=settings.root, run_id=run_id, nodeid=item.nodeid),
            nodeid=item.nodeid,
            phase=phase,
            error_summary=error_summary,
            worker=worker_id,
            run_id=run_id,
            trace=settings.trace,
        )

    try:
        yield recorder
    except (Exception, pytest.fail.Exception) as exc:
        # `pytest.fail` raises a BaseException subclass; skip and
        # KeyboardInterrupt still propagate uncaptured.
        capture(phase="setup", error_summary=f"{type(exc).__name__}: {exc}")
        raise

    failure = failure_phase(item=item)
    if failure is not None:
        phase, error_summary = failure
        capture(phase=phase, error_summary=error_summary)
    elif settings.trace:
        discard_trace(context=context)
