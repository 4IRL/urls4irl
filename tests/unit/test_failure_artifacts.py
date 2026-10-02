"""Unit tests for the pure UI failure-artifact capture helpers (no browser)."""

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from playwright.sync_api import BrowserContext

from tests.functional.failure_artifacts import (
    BUFFER_LIMIT,
    FAILED_REQUEST_LIMIT,
    NODEID_MAX_LENGTH,
    PAGE_ERROR_LIMIT,
    ArtifactSettings,
    ContextRecorder,
    capture_failure,
    discard_trace,
    load_settings,
    prune_runs,
    run_dir,
    sanitize_nodeid,
    write_failure_record,
    write_run_index,
)

# Aliased so pytest doesn't collect the helper as a test function.
from tests.functional.failure_artifacts import test_dir as artifact_test_dir

pytestmark = pytest.mark.unit

ROOTPATH = Path("/code/u4i")
NODEID = "tests/functional/urls_ui/test_access_url_ui.py::test_x[desktop-1]"


# --- Fakes -----------------------------------------------------------------


class FakeTracing:
    def __init__(self) -> None:
        self.stop_calls: list[Path | None] = []
        self.raise_on_stop = False

    def stop(self, path: Path | None = None) -> None:
        self.stop_calls.append(path)
        if self.raise_on_stop:
            raise RuntimeError("browser has been closed")
        if path is not None:
            Path(path).write_bytes(b"PK-fake-trace")


class FakePage:
    def __init__(
        self,
        *,
        url: str,
        title: str,
        raise_on_screenshot: bool = False,
        body: str = "",
    ) -> None:
        self.url = url
        self.page_title = title
        self.raise_on_screenshot = raise_on_screenshot
        self.body = body

    def screenshot(self, *, path: Path, full_page: bool) -> bytes:
        assert full_page is True
        if self.raise_on_screenshot:
            raise TimeoutError("screenshot timed out")
        Path(path).write_bytes(b"\x89PNG-fake")
        return b""

    def content(self) -> str:
        return f"<html><title>{self.page_title}</title>{self.body}</html>"

    def title(self) -> str:
        return self.page_title


class FakeContext:
    def __init__(self, pages: list[FakePage] | None = None) -> None:
        self.pages = pages if pages is not None else []
        self.tracing = FakeTracing()
        self.listeners: dict[str, Callable[[object], None]] = {}

    def on(self, event: str, handler: Callable[[object], None]) -> None:
        self.listeners[event] = handler

    def emit(self, event: str, payload: object) -> None:
        self.listeners[event](payload)


class FakeConsoleMessage:
    def __init__(self, *, msg_type: str, text: str) -> None:
        self.type = msg_type
        self.text = text
        self.location = {"url": "http://web/app.js", "lineNumber": 7}


class RaisingLocationMessage:
    type = "error"
    text = "location lookup explodes"

    @property
    def location(self) -> dict[str, object]:
        raise RuntimeError("target closed")


class BareMessage:
    """A console message missing every expected attribute."""


class FakeError:
    def __init__(self, *, message: str, stack: str | None) -> None:
        self.message = message
        self.stack = stack


class FakeWebError:
    def __init__(self, *, message: str, stack: str | None = "at f (app.js:1)") -> None:
        self.error = FakeError(message=message, stack=stack)


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status


class FakeRequest:
    def __init__(
        self,
        *,
        url: str,
        status: int | None = 200,
        failure: str | None = None,
        raise_on_response: bool = False,
    ) -> None:
        self.method = "GET"
        self.url = url
        self.resource_type = "fetch"
        self.failure = failure
        self.status = status
        self.raise_on_response = raise_on_response

    def response(self) -> FakeResponse | None:
        if self.raise_on_response:
            raise RuntimeError("target closed")
        return None if self.status is None else FakeResponse(self.status)


def as_context(fake: FakeContext) -> BrowserContext:
    return cast(BrowserContext, fake)


def attached_recorder(fake: FakeContext) -> ContextRecorder:
    recorder = ContextRecorder()
    recorder.attach(context=as_context(fake))
    return recorder


def capture(
    *, fake: FakeContext, recorder: ContextRecorder, dest: Path, trace: bool = True
) -> dict[str, object]:
    failure_path = capture_failure(
        context=as_context(fake),
        recorder=recorder,
        dest=dest,
        nodeid=NODEID,
        phase="call",
        error_summary="AssertionError: boom",
        worker="gw0",
        run_id="abcd1234",
        trace=trace,
    )
    assert failure_path == dest / "failure.json"
    return json.loads(failure_path.read_text())


# --- sanitize_nodeid / run_dir / test_dir ----------------------------------


def test_sanitize_nodeid_drops_prefix_and_maps_separators() -> None:
    assert (
        sanitize_nodeid(nodeid=NODEID)
        == "urls_ui__test_access_url_ui.py__test_x_desktop-1_"
    )


def test_sanitize_nodeid_keeps_non_functional_paths() -> None:
    assert (
        sanitize_nodeid(nodeid="tests/unit/test_a.py::test_b")
        == "tests__unit__test_a.py__test_b"
    )


def test_sanitize_nodeid_maps_disallowed_characters() -> None:
    assert sanitize_nodeid(nodeid="a/b.py::t[x y/é]") == "a__b.py__t_x_y____"


def test_sanitize_nodeid_short_ids_are_not_hashed() -> None:
    nodeid = "tests/functional/" + "x" * NODEID_MAX_LENGTH
    assert sanitize_nodeid(nodeid=nodeid) == "x" * NODEID_MAX_LENGTH


def test_sanitize_nodeid_truncates_with_sha1_suffix() -> None:
    nodeid = "tests/functional/" + "y" * 300
    slug = sanitize_nodeid(nodeid=nodeid)
    assert len(slug) == NODEID_MAX_LENGTH
    assert slug.endswith(hashlib.sha1(nodeid.encode()).hexdigest()[:8])


def test_sanitize_nodeid_long_ids_differing_past_cap_do_not_collide() -> None:
    base = "tests/functional/ui/test_x.py::test_y[" + "a" * 150
    first = sanitize_nodeid(nodeid=base + "-1]")
    second = sanitize_nodeid(nodeid=base + "-2]")
    assert first != second
    assert len(first) == len(second) == NODEID_MAX_LENGTH


def test_run_dir_and_test_dir(tmp_path: Path) -> None:
    assert run_dir(root=tmp_path, run_id="abcd1234") == tmp_path / "abcd1234"
    assert artifact_test_dir(root=tmp_path, run_id="abcd1234", nodeid=NODEID) == (
        tmp_path / "abcd1234" / sanitize_nodeid(nodeid=NODEID)
    )


# --- load_settings ----------------------------------------------------------


def test_load_settings_defaults() -> None:
    settings = load_settings(environ={}, rootpath=ROOTPATH)
    assert settings == ArtifactSettings(
        root=ROOTPATH / "tmp" / "test-artifacts", trace=False, keep_runs=10
    )


def test_load_settings_empty_trace_value_is_off() -> None:
    settings = load_settings(environ={"U4I_UI_TRACE": ""}, rootpath=ROOTPATH)
    assert settings.trace is False


def test_load_settings_relative_dir_resolves_against_rootpath() -> None:
    settings = load_settings(
        environ={"U4I_TEST_ARTIFACTS_DIR": "out/artifacts"}, rootpath=ROOTPATH
    )
    assert settings.root == ROOTPATH / "out" / "artifacts"


def test_load_settings_absolute_dir_is_kept() -> None:
    settings = load_settings(
        environ={"U4I_TEST_ARTIFACTS_DIR": "/var/artifacts"}, rootpath=ROOTPATH
    )
    assert settings.root == Path("/var/artifacts")


def test_load_settings_trace_off() -> None:
    settings = load_settings(environ={"U4I_UI_TRACE": "off"}, rootpath=ROOTPATH)
    assert settings.trace is False


def test_load_settings_trace_opt_in() -> None:
    settings = load_settings(
        environ={"U4I_UI_TRACE": "retain-on-failure"}, rootpath=ROOTPATH
    )
    assert settings.trace is True


def test_load_settings_rejects_unknown_trace_value() -> None:
    with pytest.raises(ValueError, match="retain-on-failure.*off"):
        load_settings(environ={"U4I_UI_TRACE": "on"}, rootpath=ROOTPATH)


def test_load_settings_keep_runs_override() -> None:
    settings = load_settings(
        environ={"U4I_TEST_ARTIFACTS_KEEP": "3"}, rootpath=ROOTPATH
    )
    assert settings.keep_runs == 3


@pytest.mark.parametrize("keep_value", ["0", "-1", "ten"])
def test_load_settings_rejects_invalid_keep_runs(keep_value: str) -> None:
    with pytest.raises(ValueError, match="U4I_TEST_ARTIFACTS_KEEP"):
        load_settings(
            environ={"U4I_TEST_ARTIFACTS_KEEP": keep_value}, rootpath=ROOTPATH
        )


def test_artifact_settings_is_frozen() -> None:
    settings = load_settings(environ={}, rootpath=ROOTPATH)
    with pytest.raises(AttributeError):
        settings.trace = False  # type: ignore[misc]


# --- ContextRecorder --------------------------------------------------------


def test_recorder_attaches_context_level_listeners() -> None:
    fake = FakeContext()
    attached_recorder(fake)
    assert set(fake.listeners) == {
        "console",
        "weberror",
        "request",
        "requestfinished",
        "requestfailed",
    }


def test_recorder_records_console_entries() -> None:
    fake = FakeContext()
    recorder = attached_recorder(fake)
    fake.emit("console", FakeConsoleMessage(msg_type="error", text="smoke"))
    assert list(recorder.console) == [
        {"type": "error", "text": "smoke", "url": "http://web/app.js", "line": 7}
    ]


def test_recorder_console_buffer_is_capped() -> None:
    fake = FakeContext()
    recorder = attached_recorder(fake)
    for index in range(BUFFER_LIMIT + 5):
        fake.emit("console", FakeConsoleMessage(msg_type="log", text=str(index)))
    assert len(recorder.console) == BUFFER_LIMIT
    assert recorder.console[0]["text"] == "5"


def test_recorder_records_page_errors_capped() -> None:
    fake = FakeContext()
    recorder = attached_recorder(fake)
    fake.emit("weberror", FakeWebError(message="TypeError: x is undefined"))
    assert recorder.page_errors == [
        {"message": "TypeError: x is undefined", "stack": "at f (app.js:1)"}
    ]
    for _ in range(PAGE_ERROR_LIMIT + 5):
        fake.emit("weberror", FakeWebError(message="again", stack=None))
    assert len(recorder.page_errors) == PAGE_ERROR_LIMIT


def test_recorder_records_finished_request_with_status() -> None:
    fake = FakeContext()
    recorder = attached_recorder(fake)
    request = FakeRequest(url="http://web/api?q=1", status=200)
    fake.emit("request", request)
    fake.emit("requestfinished", request)
    assert list(recorder.network) == [
        {
            "method": "GET",
            "url": "http://web/api?q=1",
            "resource_type": "fetch",
            "status": 200,
            "failure": None,
        }
    ]
    assert recorder.failed_requests == []


def test_recorder_flags_error_status_as_failed() -> None:
    fake = FakeContext()
    recorder = attached_recorder(fake)
    request = FakeRequest(url="http://web/missing", status=404)
    fake.emit("request", request)
    fake.emit("requestfinished", request)
    assert len(recorder.network) == 1
    assert recorder.failed_requests == [recorder.network[0]]
    assert recorder.failed_requests[0]["status"] == 404


def test_recorder_flags_network_failure() -> None:
    fake = FakeContext()
    recorder = attached_recorder(fake)
    request = FakeRequest(url="http://web/down", status=None, failure="net::ERR")
    fake.emit("request", request)
    fake.emit("requestfailed", request)
    assert recorder.failed_requests == [
        {
            "method": "GET",
            "url": "http://web/down",
            "resource_type": "fetch",
            "status": None,
            "failure": "net::ERR",
        }
    ]


def test_recorder_survives_response_lookup_error() -> None:
    fake = FakeContext()
    recorder = attached_recorder(fake)
    request = FakeRequest(url="http://web/x", raise_on_response=True)
    fake.emit("request", request)
    fake.emit("requestfinished", request)
    assert recorder.network[0]["status"] is None


def test_recorder_finish_without_request_event_still_records() -> None:
    fake = FakeContext()
    recorder = attached_recorder(fake)
    fake.emit("requestfinished", FakeRequest(url="http://web/late", status=500))
    assert recorder.network[0]["status"] == 500
    assert len(recorder.failed_requests) == 1


def test_recorder_failed_requests_capped() -> None:
    fake = FakeContext()
    recorder = attached_recorder(fake)
    for index in range(FAILED_REQUEST_LIMIT + 5):
        request = FakeRequest(url=f"http://web/{index}", status=500)
        fake.emit("request", request)
        fake.emit("requestfinished", request)
    assert len(recorder.failed_requests) == FAILED_REQUEST_LIMIT


@pytest.mark.parametrize(
    "message",
    [RaisingLocationMessage(), BareMessage()],
    ids=["location-raises", "missing-attributes"],
)
def test_recorder_listener_errors_never_raise_into_dispatch(message: object) -> None:
    fake = FakeContext()
    recorder = attached_recorder(fake)
    fake.emit("console", message)
    fake.emit("weberror", BareMessage())
    fake.emit("request", BareMessage())
    fake.emit("requestfinished", BareMessage())
    fake.emit("requestfailed", BareMessage())
    assert list(recorder.console) == []
    assert recorder.page_errors == []


def test_recorder_in_flight_map_is_bounded() -> None:
    fake = FakeContext()
    recorder = attached_recorder(fake)
    for index in range(BUFFER_LIMIT + 5):
        fake.emit("request", FakeRequest(url=f"http://web/hang/{index}"))
        assert len(recorder._in_flight) <= BUFFER_LIMIT
    assert len(recorder._in_flight) == BUFFER_LIMIT
    oldest_kept = next(iter(recorder._in_flight))
    assert cast(FakeRequest, oldest_kept).url == "http://web/hang/5"


# --- write_failure_record ---------------------------------------------------


def test_write_failure_record_is_sorted_indented_and_atomic(tmp_path: Path) -> None:
    path = write_failure_record(dest=tmp_path, record={"zeta": 1, "alpha": [2]})
    assert path == tmp_path / "failure.json"
    assert path.read_text() == json.dumps(
        {"alpha": [2], "zeta": 1}, indent=2, sort_keys=True
    )
    assert list(tmp_path.glob("*.tmp")) == []


# --- capture_failure --------------------------------------------------------


def test_capture_failure_writes_all_artifacts(tmp_path: Path) -> None:
    fake = FakeContext([FakePage(url="http://web/home", title="Home")])
    recorder = attached_recorder(fake)
    fake.emit("console", FakeConsoleMessage(msg_type="error", text="smoke"))
    fake.emit("console", FakeConsoleMessage(msg_type="log", text="fine"))
    fake.emit("weberror", FakeWebError(message="boom"))
    failing = FakeRequest(url="http://web/api", status=500)
    fake.emit("request", failing)
    fake.emit("requestfinished", failing)
    dest = tmp_path / "run" / "slug"

    record = capture(fake=fake, recorder=recorder, dest=dest)

    assert (dest / "page-0.png").read_bytes() == b"\x89PNG-fake"
    assert "<title>Home</title>" in (dest / "page-0.html").read_text()
    assert (dest / "trace.zip").read_bytes() == b"PK-fake-trace"
    assert fake.tracing.stop_calls == [dest / "trace.zip"]
    console = json.loads((dest / "console.json").read_text())
    assert [entry["text"] for entry in console["console"]] == ["smoke", "fine"]
    assert console["page_errors"][0]["message"] == "boom"
    network = json.loads((dest / "network.json").read_text())
    assert network["recent"][0]["status"] == 500
    assert network["failed"][0]["url"] == "http://web/api"

    captured_at = record.pop("captured_at")
    assert isinstance(captured_at, str)
    assert captured_at.endswith("+00:00")
    assert record == {
        "nodeid": NODEID,
        "phase": "call",
        "error_summary": "AssertionError: boom",
        "worker": "gw0",
        "run_id": "abcd1234",
        "pages": [
            {
                "index": 0,
                "url": "http://web/home",
                "title": "Home",
                "screenshot": "page-0.png",
                "dom": "page-0.html",
            }
        ],
        "trace": "trace.zip",
        "console": "console.json",
        "network": "network.json",
        "counts": {"console_errors": 1, "page_errors": 1, "failed_requests": 1},
        "capture_errors": [],
    }


def test_capture_failure_continues_past_screenshot_error(tmp_path: Path) -> None:
    fake = FakeContext(
        [FakePage(url="http://web/home", title="Home", raise_on_screenshot=True)]
    )
    recorder = attached_recorder(fake)

    record = capture(fake=fake, recorder=recorder, dest=tmp_path)

    assert not (tmp_path / "page-0.png").exists()
    for name in ("page-0.html", "console.json", "network.json", "trace.zip"):
        assert (tmp_path / name).exists(), name
    assert record["capture_errors"] == [
        "page-0.screenshot: TimeoutError: screenshot timed out"
    ]
    assert record["pages"] == [
        {
            "index": 0,
            "url": "http://web/home",
            "title": "Home",
            "screenshot": None,
            "dom": "page-0.html",
        }
    ]


def test_capture_failure_writes_non_ascii_dom_as_utf8(tmp_path: Path) -> None:
    fake = FakeContext([FakePage(url="http://web/", title="Café", body="é ✓")])
    recorder = attached_recorder(fake)

    record = capture(fake=fake, recorder=recorder, dest=tmp_path)

    assert record["capture_errors"] == []
    dom = (tmp_path / "page-0.html").read_text(encoding="utf-8")
    assert dom == "<html><title>Café</title>é ✓</html>"


def test_capture_failure_trace_off_never_stops_tracing(tmp_path: Path) -> None:
    fake = FakeContext([FakePage(url="http://web/", title="Splash")])
    recorder = attached_recorder(fake)

    record = capture(fake=fake, recorder=recorder, dest=tmp_path, trace=False)

    assert fake.tracing.stop_calls == []
    assert record["trace"] is None
    assert not (tmp_path / "trace.zip").exists()


def test_capture_failure_records_trace_stop_error(tmp_path: Path) -> None:
    fake = FakeContext([FakePage(url="http://web/", title="Splash")])
    fake.tracing.raise_on_stop = True
    recorder = attached_recorder(fake)

    record = capture(fake=fake, recorder=recorder, dest=tmp_path)

    assert record["trace"] is None
    assert record["capture_errors"] == ["trace: RuntimeError: browser has been closed"]


def test_capture_failure_captures_popup_pages(tmp_path: Path) -> None:
    fake = FakeContext(
        [
            FakePage(url="http://web/home", title="Home"),
            FakePage(url="https://example.com/", title="Popup"),
        ]
    )
    recorder = attached_recorder(fake)

    record = capture(fake=fake, recorder=recorder, dest=tmp_path)

    for name in ("page-0.png", "page-0.html", "page-1.png", "page-1.html"):
        assert (tmp_path / name).exists(), name
    pages = record["pages"]
    assert isinstance(pages, list)
    assert [page["title"] for page in pages] == ["Home", "Popup"]


def test_capture_failure_never_raises_when_dest_unwritable(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a dir")
    fake = FakeContext([FakePage(url="http://web/", title="Splash")])
    recorder = attached_recorder(fake)

    failure_path = capture_failure(
        context=as_context(fake),
        recorder=recorder,
        dest=blocker / "slug",
        nodeid=NODEID,
        phase="setup",
        error_summary="TimeoutError: goto",
        worker="master",
        run_id="abcd1234",
        trace=True,
    )

    assert failure_path == blocker / "slug" / "failure.json"
    assert not failure_path.exists()


# --- discard_trace ----------------------------------------------------------


def test_discard_trace_stops_without_path() -> None:
    fake = FakeContext()
    discard_trace(context=as_context(fake))
    assert fake.tracing.stop_calls == [None]


def test_discard_trace_swallows_errors() -> None:
    fake = FakeContext()
    fake.tracing.raise_on_stop = True
    discard_trace(context=as_context(fake))
    assert fake.tracing.stop_calls == [None]


# --- write_run_index --------------------------------------------------------


def seed_failure(
    *, root: Path, run_id: str, nodeid: str, trace: str | None = "trace.zip"
) -> Path:
    dest = artifact_test_dir(root=root, run_id=run_id, nodeid=nodeid)
    dest.mkdir(parents=True)
    write_failure_record(
        dest=dest,
        record={
            "nodeid": nodeid,
            "phase": "call",
            "error_summary": f"failed {nodeid}",
            "counts": {"console_errors": 0, "page_errors": 0, "failed_requests": 0},
            "trace": trace,
        },
    )
    return dest


def test_write_run_index_without_failures_writes_nothing(tmp_path: Path) -> None:
    (tmp_path / "abcd1234").mkdir()
    assert write_run_index(root=tmp_path, run_id="abcd1234") is None
    assert not (tmp_path / "abcd1234" / "index.json").exists()
    assert not (tmp_path / "latest.json").exists()


def test_write_run_index_missing_run_dir_writes_nothing(tmp_path: Path) -> None:
    assert write_run_index(root=tmp_path / "absent", run_id="abcd1234") is None
    assert not (tmp_path / "absent").exists()


def test_write_run_index_lists_failures_sorted(tmp_path: Path) -> None:
    second = "tests/functional/z_ui/test_z.py::test_z"
    first = "tests/functional/a_ui/test_a.py::test_a"
    seed_failure(root=tmp_path, run_id="abcd1234", nodeid=second, trace=None)
    first_dir = seed_failure(root=tmp_path, run_id="abcd1234", nodeid=first)

    index_path = write_run_index(root=tmp_path, run_id="abcd1234")

    assert index_path == tmp_path / "abcd1234" / "index.json"
    index = json.loads(index_path.read_text())
    assert index["run_id"] == "abcd1234"
    assert index["failure_count"] == 2
    assert isinstance(index["created"], str)
    assert index["failures"][0] == {
        "nodeid": first,
        "dir": first_dir.name,
        "phase": "call",
        "error_summary": f"failed {first}",
        "counts": {"console_errors": 0, "page_errors": 0, "failed_requests": 0},
        "trace": True,
    }
    assert index["failures"][1]["nodeid"] == second
    assert index["failures"][1]["trace"] is False

    latest = json.loads((tmp_path / "latest.json").read_text())
    assert latest == {
        "run_id": "abcd1234",
        "index": "abcd1234/index.json",
        "failure_count": 2,
        "created": index["created"],
    }


def test_write_run_index_skips_unreadable_and_non_dict_records(
    tmp_path: Path,
) -> None:
    valid = "tests/functional/a_ui/test_a.py::test_a"
    seed_failure(root=tmp_path, run_id="abcd1234", nodeid=valid)
    invalid_json_dir = tmp_path / "abcd1234" / "broken"
    invalid_json_dir.mkdir()
    (invalid_json_dir / "failure.json").write_text("{not json", encoding="utf-8")
    list_dir = tmp_path / "abcd1234" / "listed"
    list_dir.mkdir()
    (list_dir / "failure.json").write_text('["nodeid"]', encoding="utf-8")

    index_path = write_run_index(root=tmp_path, run_id="abcd1234")

    assert index_path is not None
    index = json.loads(index_path.read_text())
    assert index["failure_count"] == 1
    assert [failure["nodeid"] for failure in index["failures"]] == [valid]


# --- prune_runs -------------------------------------------------------------


def make_run(*, root: Path, name: str, mtime: int) -> Path:
    path = root / name
    path.mkdir()
    (path / "slug").mkdir()
    os.utime(path, (mtime, mtime))
    return path


def test_prune_runs_missing_root_is_noop(tmp_path: Path) -> None:
    assert prune_runs(root=tmp_path / "absent", keep=2) == []


def test_prune_runs_keeps_newest_by_mtime(tmp_path: Path) -> None:
    names = ["aaaa0001", "aaaa0002", "aaaa0003", "aaaa0004"]
    for age, name in enumerate(names):
        make_run(root=tmp_path, name=name, mtime=1_700_000_000 - age * 100)
    (tmp_path / "latest.json").write_text("{}")

    removed = prune_runs(root=tmp_path, keep=2)

    assert sorted(removed) == [tmp_path / "aaaa0003", tmp_path / "aaaa0004"]
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "aaaa0001",
        "aaaa0002",
        "latest.json",
    ]


def test_prune_runs_fewer_than_keep_removes_nothing(tmp_path: Path) -> None:
    (tmp_path / "0badf00d").mkdir()
    assert prune_runs(root=tmp_path, keep=10) == []
    assert (tmp_path / "0badf00d").is_dir()


def test_prune_runs_ignores_non_run_dirs_and_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    make_run(root=root, name="bbbb0001", mtime=1_700_000_000)
    make_run(root=root, name="bbbb0002", mtime=1_699_999_000)
    keepme = make_run(root=root, name="keepme", mtime=1_600_000_000)
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "precious.txt").write_text("keep")
    link = root / "cccc0003"
    link.symlink_to(target, target_is_directory=True)

    removed = prune_runs(root=root, keep=1)

    assert removed == [root / "bbbb0002"]
    assert (root / "bbbb0001").is_dir()
    assert keepme.is_dir()
    assert link.is_symlink()
    assert (target / "precious.txt").read_text() == "keep"
