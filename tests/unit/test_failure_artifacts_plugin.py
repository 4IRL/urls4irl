"""pytester proof that the failure-artifacts plugin wires capture into pytest.

Each test writes an inner project whose root conftest registers
`tests.functional.failure_artifacts` as a plugin (as the real root conftest
does) and wraps a fake browser context in `recorded_context`, then runs it in
a subprocess so the repo's heavy conftest and in-process plugin state never
leak in. The fake tracing logs every start/stop call to a file for assertions.
"""

import json
import os
from pathlib import Path

import pytest

from tests.functional.failure_artifacts import RUN_ID_LENGTH

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIRNAME = "artifacts"
TRACING_LOG = "tracing-calls.log"

INNER_CONFTEST = """
import os
from pathlib import Path

import pytest

# Registered (not imported) like the real root conftest does; an import here
# would pre-empt pytest's assertion rewriting of the plugin module.
PLUGIN_NAME = "tests.functional.failure_artifacts"
pytest_plugins = [PLUGIN_NAME]

TRACING_LOG = "tracing-calls.log"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "pre_yield_timeout: raise before the fake page fixture yields"
    )
    config.addinivalue_line(
        "markers", "pre_yield_fail: pytest.fail before the fake page fixture yields"
    )


class FakeTracing:
    def __init__(self, log_path):
        self.log_path = log_path

    def _log(self, entry):
        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(entry + "\\n")

    def start(self, **options):
        self._log("start")

    def stop(self, path=None):
        self._log("stop:" + ("none" if path is None else "path"))
        if path is not None:
            Path(path).write_bytes(b"PK-fake-trace")


class FakePage:
    url = "http://fake.test/"

    def screenshot(self, *, path, full_page):
        Path(path).write_bytes(b"fake-png")

    def content(self):
        return "<html></html>"

    def title(self):
        return "fake"


class FakeContext:
    def __init__(self, log_path):
        self.tracing = FakeTracing(log_path)
        self.pages = [FakePage()]

    def on(self, event, handler):
        pass


@pytest.fixture
def page(request, worker_id):
    plugin = request.config.pluginmanager.get_plugin(PLUGIN_NAME)
    settings = plugin.load_settings(
        environ=os.environ, rootpath=request.config.rootpath
    )
    context = FakeContext(request.config.rootpath / TRACING_LOG)
    with plugin.recorded_context(
        context=context, request=request, settings=settings, worker_id=worker_id
    ):
        if request.node.get_closest_marker("pre_yield_timeout"):
            raise TimeoutError("goto timed out")
        if request.node.get_closest_marker("pre_yield_fail"):
            pytest.fail("boom-pre-yield-fail", pytrace=False)
        yield context
"""


@pytest.fixture
def inner_project(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An inner project with the fake-page conftest and a pinned artifact root."""
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(path for path in (str(REPO_ROOT), existing_pythonpath) if path),
    )
    monkeypatch.setenv("U4I_TEST_ARTIFACTS_DIR", ARTIFACTS_DIRNAME)
    monkeypatch.delenv("U4I_UI_TRACE", raising=False)
    monkeypatch.delenv("U4I_TEST_ARTIFACTS_KEEP", raising=False)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    # xdist (the `-n` test) is loaded via plugin autoload.
    monkeypatch.delenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", raising=False)
    pytester.makeconftest(INNER_CONFTEST)
    return pytester.path / ARTIFACTS_DIRNAME


def run_dirs(*, root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir())


def failure_records(*, root: Path) -> list[dict[str, object]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("*/*/failure.json"))
    ]


def tracing_calls(*, pytester: pytest.Pytester) -> list[str]:
    log_path = pytester.path / TRACING_LOG
    if not log_path.exists():
        return []
    return log_path.read_text(encoding="utf-8").split()


def test_failing_call_writes_failure_record(
    pytester: pytest.Pytester, inner_project: Path
) -> None:
    pytester.makepyfile(
        test_inner="""
        def test_fails(page):
            assert 1 == 2, "boom-call"
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(failed=1)

    (run_path,) = run_dirs(root=inner_project)
    assert len(run_path.name) == RUN_ID_LENGTH
    (record,) = failure_records(root=inner_project)
    assert record["phase"] == "call"
    assert "boom-call" in str(record["error_summary"])
    assert record["run_id"] == run_path.name
    assert (run_path / "test_inner.py__test_fails" / "trace.zip").read_bytes()
    index = json.loads((run_path / "index.json").read_text(encoding="utf-8"))
    assert index["failure_count"] == 1
    latest = json.loads((inner_project / "latest.json").read_text(encoding="utf-8"))
    assert latest["run_id"] == run_path.name


def test_passing_test_discards_trace_and_writes_nothing(
    pytester: pytest.Pytester, inner_project: Path
) -> None:
    pytester.makepyfile(
        test_inner="""
        def test_passes(page):
            assert True
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(passed=1)

    assert run_dirs(root=inner_project) == []
    assert not (inner_project / "latest.json").exists()
    assert tracing_calls(pytester=pytester) == ["start", "stop:none"]


def test_setup_failure_after_page_yield_is_setup_phase(
    pytester: pytest.Pytester, inner_project: Path
) -> None:
    pytester.makepyfile(
        test_inner="""
        import pytest

        @pytest.fixture
        def broken(page):
            raise RuntimeError("boom-setup")

        def test_never_runs(page, broken):
            pass
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(errors=1)

    (record,) = failure_records(root=inner_project)
    assert record["phase"] == "setup"
    assert "boom-setup" in str(record["error_summary"])


def test_pre_yield_timeout_is_captured_and_reraised(
    pytester: pytest.Pytester, inner_project: Path
) -> None:
    pytester.makepyfile(
        test_inner="""
        import pytest

        @pytest.mark.pre_yield_timeout
        def test_never_runs(page):
            pass
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*TimeoutError: goto timed out*"])

    (record,) = failure_records(root=inner_project)
    assert record["phase"] == "setup"
    assert record["error_summary"] == "TimeoutError: goto timed out"
    assert record["trace"] == "trace.zip"
    (trace_path,) = inner_project.glob("*/*/trace.zip")
    assert trace_path.stat().st_size > 0


def test_plain_pytest_fail_in_call_is_captured(
    pytester: pytest.Pytester, inner_project: Path
) -> None:
    pytester.makepyfile(
        test_inner="""
        import pytest

        def test_fails(page):
            pytest.fail("boom-plain", pytrace=False)
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(failed=1)

    (record,) = failure_records(root=inner_project)
    assert record["phase"] == "call"
    assert "boom-plain" in str(record["error_summary"])


def test_pre_yield_pytest_fail_is_captured_as_setup(
    pytester: pytest.Pytester, inner_project: Path
) -> None:
    pytester.makepyfile(
        test_inner="""
        import pytest

        @pytest.mark.pre_yield_fail
        def test_never_runs(page):
            pass
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(errors=1)

    (record,) = failure_records(root=inner_project)
    assert record["phase"] == "setup"
    assert "boom-pre-yield-fail" in str(record["error_summary"])


def test_invalid_trace_mode_is_a_usage_error(
    pytester: pytest.Pytester, inner_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("U4I_UI_TRACE", "bogus")
    pytester.makepyfile(
        test_inner="""
        def test_passes(page):
            assert True
        """
    )
    result = pytester.runpytest_subprocess()

    assert result.ret == pytest.ExitCode.USAGE_ERROR
    assert "U4I_UI_TRACE" in result.stderr.str()
    assert "INTERNALERROR" not in result.stdout.str() + result.stderr.str()


def test_teardown_failure_after_pass_is_not_captured(
    pytester: pytest.Pytester, inner_project: Path
) -> None:
    pytester.makepyfile(
        test_inner="""
        import pytest

        @pytest.fixture
        def bad_teardown(page):
            yield
            raise RuntimeError("boom-teardown")

        def test_passes(page, bad_teardown):
            assert True
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(passed=1, errors=1)

    assert run_dirs(root=inner_project) == []
    assert tracing_calls(pytester=pytester) == ["start", "stop:none"]


XDIST_TESTS = """
def test_fails(page):
    assert False, "boom-xdist"

def test_passes(page):
    assert True
"""


def assert_single_xdist_failure(*, root: Path) -> None:
    (run_path,) = run_dirs(root=root)
    failure_dirs = [path for path in run_path.iterdir() if path.is_dir()]
    assert len(failure_dirs) == 1
    index = json.loads((run_path / "index.json").read_text(encoding="utf-8"))
    assert index["run_id"] == run_path.name
    assert index["failure_count"] == 1
    assert index["failures"][0]["dir"] == failure_dirs[0].name
    assert index["failures"][0]["nodeid"].endswith("::test_fails")
    latest = json.loads((root / "latest.json").read_text(encoding="utf-8"))
    assert latest["run_id"] == run_path.name


def test_xdist_workers_and_controller_share_one_run_id(
    pytester: pytest.Pytester, inner_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytester.makepyfile(test_inner=XDIST_TESTS)
    result = pytester.runpytest_subprocess("-n", "2")
    result.assert_outcomes(passed=1, failed=1)
    assert_single_xdist_failure(root=inner_project)

    # Same proof with the tests nested like tests/functional/<domain>_ui/.
    (pytester.path / "test_inner.py").unlink()
    nested_dir = pytester.path / "inner" / "sub" / "pkg"
    nested_dir.mkdir(parents=True)
    (nested_dir / "test_nested.py").write_text(XDIST_TESTS, encoding="utf-8")
    nested_root = pytester.path / "nested-artifacts"
    monkeypatch.setenv("U4I_TEST_ARTIFACTS_DIR", str(nested_root))
    nested_result = pytester.runpytest_subprocess("-n", "2")
    nested_result.assert_outcomes(passed=1, failed=1)
    assert_single_xdist_failure(root=nested_root)


def test_trace_off_never_starts_tracing(
    pytester: pytest.Pytester, inner_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("U4I_UI_TRACE", "off")
    pytester.makepyfile(
        test_inner="""
        def test_fails(page):
            assert False
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(failed=1)

    assert tracing_calls(pytester=pytester) == []
    (record,) = failure_records(root=inner_project)
    assert record["trace"] is None


@pytest.mark.parametrize(
    ("inner_test", "expected_runs"),
    [
        ("def test_passes(page):\n    assert True\n", 2),
        ("def test_fails(page):\n    assert False\n", 3),
    ],
    ids=["passing-run", "failing-run"],
)
def test_session_start_prunes_to_keep(
    pytester: pytest.Pytester,
    inner_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    inner_test: str,
    expected_runs: int,
) -> None:
    monkeypatch.setenv("U4I_TEST_ARTIFACTS_KEEP", "2")
    # Run-id-named (8-hex) dirs: prune_runs ignores anything else.
    seeded = ["aaaaaaa1", "aaaaaaa2", "aaaaaaa3"]
    for age_rank, run_id in enumerate(seeded):
        seeded_dir = inner_project / run_id
        seeded_dir.mkdir(parents=True)
        mtime = 1_000_000 + age_rank * 1_000
        os.utime(seeded_dir, (mtime, mtime))
    pytester.makepyfile(test_inner=inner_test)
    pytester.runpytest_subprocess()

    remaining = {path.name for path in run_dirs(root=inner_project)}
    assert len(remaining) == expected_runs
    assert {"aaaaaaa2", "aaaaaaa3"} <= remaining
    assert "aaaaaaa1" not in remaining
