"""Unit tests for the spoke host-port resolver (`scripts/spoke_ports.py`).

Docker and the host's sockets are faked through `main`'s injected `owner_fn`
(compose project publishing a port) and `bindable_fn` (a test bind succeeds),
so these run identically on a laptop, inside the web container, and in CI.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path
import socket
import subprocess
import sys
import zlib

import pytest

from scripts import spoke_ports
from scripts.spoke_ports import (
    PORT_RANGE_SIZE,
    VITE_BASE_PORT,
    WEB_BASE_PORT,
    DockerPsError,
    docker_port_owner,
    main,
    port_is_bindable,
)

pytestmark = pytest.mark.unit

PROJECT = "u4i-wt-a"
SLUG = "wt-a"
WORKTREE_OFFSET = zlib.crc32(SLUG.encode()) % 99 + 1


class _FakeHost:
    """Scripted port state: `owners` maps port → compose project; `unbindable` fails the test bind."""

    def __init__(
        self,
        owners: dict[int, str] | None = None,
        unbindable: set[int] | None = None,
    ) -> None:
        self.owners = owners or {}
        self.unbindable = unbindable or set()

    def owner(self, port: int) -> str | None:
        return self.owners.get(port)

    def bindable(self, port: int) -> bool:
        return port not in self.unbindable


def _resolve(
    output: Path,
    host: _FakeHost,
    *extra_args: str,
    primary: bool = False,
) -> int:
    argv = [
        "resolve",
        "--project",
        PROJECT,
        "--slug",
        SLUG,
        *(["--primary"] if primary else []),
        *extra_args,
        "--output",
        str(output),
    ]
    return main(argv, host.owner, host.bindable)


def _cached_ports(output: Path) -> dict[str, int]:
    return {
        key: int(value)
        for key, value in (
            line.split("=", 1) for line in output.read_text().splitlines()
        )
    }


@pytest.fixture
def output(tmp_path: Path) -> Path:
    return tmp_path / ".ports.generated.env"


def test_primary_prefers_base_ports(output: Path) -> None:
    assert _resolve(output, _FakeHost(), primary=True) == 0
    assert _cached_ports(output) == {
        "U4I_WEB_PORT": WEB_BASE_PORT,
        "U4I_VITE_PORT": VITE_BASE_PORT,
    }


def test_worktree_prefers_crc_offset_port(output: Path) -> None:
    assert _resolve(output, _FakeHost()) == 0
    assert _cached_ports(output) == {
        "U4I_WEB_PORT": WEB_BASE_PORT + WORKTREE_OFFSET,
        "U4I_VITE_PORT": VITE_BASE_PORT + WORKTREE_OFFSET,
    }


def test_port_held_by_another_project_is_skipped(
    output: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    preferred = WEB_BASE_PORT + WORKTREE_OFFSET
    host = _FakeHost(owners={preferred: "u4i-other"})

    assert _resolve(output, host) == 0

    assert _cached_ports(output)["U4I_WEB_PORT"] == preferred + 1
    assert (
        f"{preferred} was held by u4i-other; using {preferred + 1}"
        in capsys.readouterr().out
    )


def test_port_held_by_a_host_process_is_skipped(
    output: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    preferred = VITE_BASE_PORT + WORKTREE_OFFSET
    host = _FakeHost(unbindable={preferred})

    assert _resolve(output, host) == 0

    assert _cached_ports(output)["U4I_VITE_PORT"] == preferred + 1
    assert "was held by a host process" in capsys.readouterr().out


def test_port_published_by_this_project_is_kept(
    output: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    preferred = WEB_BASE_PORT + WORKTREE_OFFSET
    host = _FakeHost(owners={preferred: PROJECT}, unbindable={preferred})

    assert _resolve(output, host) == 0

    assert _cached_ports(output)["U4I_WEB_PORT"] == preferred
    assert "was held" not in capsys.readouterr().out


def test_cached_port_is_reused_while_free(output: Path) -> None:
    output.write_text("U4I_WEB_PORT=8700\nU4I_VITE_PORT=5200\n")
    assert 8700 != WEB_BASE_PORT + WORKTREE_OFFSET

    assert _resolve(output, _FakeHost()) == 0

    assert _cached_ports(output) == {"U4I_WEB_PORT": 8700, "U4I_VITE_PORT": 5200}


def test_cached_port_taken_by_another_project_is_re_resolved(
    output: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output.write_text("U4I_WEB_PORT=8700\nU4I_VITE_PORT=5200\n")
    host = _FakeHost(owners={8700: "u4i-other"})

    assert _resolve(output, host) == 0

    assert _cached_ports(output) == {
        "U4I_WEB_PORT": WEB_BASE_PORT + WORKTREE_OFFSET,
        "U4I_VITE_PORT": 5200,
    }
    assert "8700 was held by u4i-other" in capsys.readouterr().out


def test_malformed_cache_is_ignored(output: Path) -> None:
    output.write_text("U4I_WEB_PORT=eighty\nU4I_VITE_PORT=99999\n")

    assert _resolve(output, _FakeHost(), primary=True) == 0

    assert _cached_ports(output) == {
        "U4I_WEB_PORT": WEB_BASE_PORT,
        "U4I_VITE_PORT": VITE_BASE_PORT,
    }


def test_explicit_override_wins(output: Path) -> None:
    output.write_text("U4I_WEB_PORT=8700\nU4I_VITE_PORT=5200\n")

    assert _resolve(output, _FakeHost(), "--web-port", "9001") == 0

    assert _cached_ports(output) == {"U4I_WEB_PORT": 9001, "U4I_VITE_PORT": 5200}


def test_explicit_override_that_is_taken_fails(
    output: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    host = _FakeHost(owners={9001: "u4i-other"})

    assert _resolve(output, host, "--web-port", "9001") != 0

    stderr = capsys.readouterr().err
    assert "u4i-other" in stderr
    assert "U4I_WEB_PORT=9001" in stderr
    assert not output.exists()


def test_explicit_ports_must_differ(
    output: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        _resolve(output, _FakeHost(), "--web-port", "9001", "--vite-port", "9001") != 0
    )
    assert "U4I_VITE_PORT=9001" in capsys.readouterr().err


def test_explicit_port_moves_an_auto_resolved_service_off_it(
    output: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output.write_text("U4I_WEB_PORT=8700\n")
    assert 8700 != WEB_BASE_PORT + WORKTREE_OFFSET

    assert _resolve(output, _FakeHost(), "--vite-port", "8700") == 0

    assert _cached_ports(output) == {
        "U4I_WEB_PORT": WEB_BASE_PORT + WORKTREE_OFFSET,
        "U4I_VITE_PORT": 8700,
    }
    assert "8700 was held by this spoke's other service" in capsys.readouterr().out


def test_exhausted_range_fails_with_holders(
    output: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    web_range = range(WEB_BASE_PORT, WEB_BASE_PORT + PORT_RANGE_SIZE)
    host = _FakeHost(owners={port: "u4i-other" for port in web_range})

    assert _resolve(output, host, primary=True) != 0

    stderr = capsys.readouterr().err
    assert f"{WEB_BASE_PORT}=u4i-other" in stderr
    assert f"{WEB_BASE_PORT + PORT_RANGE_SIZE - 1}=u4i-other" in stderr
    assert "U4I_WEB_PORT" in stderr
    assert not output.exists()


def test_docker_failure_fails_loudly(
    output: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def failing_owner(port: int) -> str | None:
        raise DockerPsError("Cannot connect to the Docker daemon")

    assert (
        main(
            ["resolve", "--project", PROJECT, "--slug", SLUG, "--output", str(output)],
            failing_owner,
            lambda port: True,
        )
        != 0
    )

    assert "Cannot connect to the Docker daemon" in capsys.readouterr().err
    assert not output.exists()


def test_output_file_is_rewritten_atomically(
    output: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output.write_text("stale\n")
    replacements: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(source: str | Path, destination: str | Path) -> None:
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(spoke_ports.os, "replace", recording_replace)

    assert _resolve(output, _FakeHost(), primary=True) == 0

    assert len(replacements) == 1
    source, destination = replacements[0]
    assert destination == output
    assert source.parent == output.parent and source != output
    assert output.read_text() == (
        f"U4I_WEB_PORT={WEB_BASE_PORT}\nU4I_VITE_PORT={VITE_BASE_PORT}\n"
    )
    assert [path.name for path in output.parent.iterdir()] == [output.name]


def test_show_prints_cached_urls(
    output: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output.write_text("U4I_WEB_PORT=8700\nU4I_VITE_PORT=5200\n")

    assert main(["show", "--output", str(output)]) == 0

    assert "http://127.0.0.1:8700/" in capsys.readouterr().out


def test_show_before_resolution_points_at_make_up(
    output: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["show", "--output", str(output)]) == 0
    assert "not resolved yet — run make up" in capsys.readouterr().out


@pytest.mark.parametrize(
    "cached_line",
    [
        pytest.param("U4I_WEB_PORT=8700", id="missing-vite"),
        pytest.param("U4I_VITE_PORT=5200", id="missing-web"),
    ],
)
def test_show_with_partial_cache_points_at_make_up(
    output: Path, capsys: pytest.CaptureFixture[str], cached_line: str
) -> None:
    output.write_text(f"{cached_line}\n")

    assert main(["show", "--output", str(output)]) == 0

    stdout = capsys.readouterr().out
    assert "not resolved yet — run make up" in stdout
    assert "http://" not in stdout


def test_real_bind_probe_detects_a_listener() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("0.0.0.0", 0))
        listener.listen()
        assert port_is_bindable(listener.getsockname()[1]) is False


class _DeniedBindSocket:
    """A socket stand-in whose bind fails with EACCES, as on a privileged port."""

    def __init__(self, family: int, kind: int) -> None:
        pass

    def __enter__(self) -> _DeniedBindSocket:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def setsockopt(self, level: int, option: int, value: int) -> None:
        return None

    def bind(self, address: tuple[str, int]) -> None:
        raise OSError(errno.EACCES, "Permission denied")


def test_non_address_in_use_bind_error_is_reported(
    output: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(spoke_ports.socket, "socket", _DeniedBindSocket)

    with pytest.raises(OSError, match="Permission denied"):
        port_is_bindable(80)
    assert (
        main(
            ["resolve", "--project", PROJECT, "--slug", SLUG, "--output", str(output)],
            lambda port: None,
        )
        == 1
    )
    assert "Permission denied" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        pytest.param("", None, id="unpublished"),
        pytest.param("u4i-other\n", "u4i-other", id="compose-project"),
        pytest.param(
            "\n", spoke_ports.UNLABELLED_CONTAINER_HOLDER, id="non-compose-container"
        ),
    ],
)
def test_docker_port_owner_reads_the_compose_label(
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
    expected: str | None,
) -> None:
    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        assert command[:4] == ["docker", "ps", "--filter", "publish=8659"]
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(spoke_ports.subprocess, "run", fake_run)
    assert docker_port_owner(8659) == expected


def test_docker_port_owner_raises_on_docker_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "daemon down\n")

    monkeypatch.setattr(spoke_ports.subprocess, "run", fake_run)
    with pytest.raises(DockerPsError, match="daemon down"):
        docker_port_owner(8659)


def test_module_is_stdlib_only() -> None:
    """`spoke_ports.py` runs on the host under bare mise python — stdlib only."""
    probe_script = (
        "import importlib.util\n"
        "import sys\n"
        "sys.path = [p for p in sys.path if p not in ('', PROJECT_ROOT)]\n"
        "spec = importlib.util.spec_from_file_location('spoke_ports_leaf', MODULE_FILE)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        # Register before exec so the frozen dataclasses can resolve their own
        # module under `from __future__ import annotations`.
        "sys.modules[spec.name] = module\n"
        "spec.loader.exec_module(module)\n"
        "forbidden = [name for name in sys.modules "
        "if name.split('.')[0] in ('flask', 'sqlalchemy', 'redis', 'backend')]\n"
        "assert forbidden == [], forbidden\n"
    )
    module_file = Path(spoke_ports.__file__).resolve()
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
        f"spoke_ports pulled in a non-stdlib import:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
