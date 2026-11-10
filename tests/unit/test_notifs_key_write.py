"""Behavior of `scripts/notifs-key-write.sh`, the host-side hub key writer.

Real bash against a `tmp_path` directory, with a stub `mv` on PATH for the move-failure
cases. Host-static: no stack, no Docker.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
SCRIPT: Path = REPO_ROOT / "scripts" / "notifs-key-write.sh"
PROD_DEPLOY: Path = REPO_ROOT / ".github" / "workflows" / "prod-deploy.yml"
NOTIFS_EXCHANGE: Path = REPO_ROOT / ".github" / "workflows" / "notifs-exchange.yml"
GID_OVERRIDE: str = "NOTIFS_KEY_EXPECTED_GID"
FILE_NAMES: tuple[str, ...] = (
    "access_client_id",
    "access_client_secret",
    "delivery_key",
)
KEY: str = "dak_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0-_U"
OLD_KEY: str = "dak_" + "Z" * 43
CLIENT_ID: str = "client-id-value.access"
CLIENT_SECRET: str = "client-secret-value-0123456789abcdef"
SKIP_AS_ROOT = pytest.mark.skipif(
    os.geteuid() == 0, reason="root ignores directory permission bits"
)

_REAL_MV: str = shutil.which("mv") or "/bin/mv"
_HEX64 = re.compile(r"\b[0-9a-f]{64}\b")


@pytest.fixture
def key_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "notifs-key"
    directory.mkdir()
    directory.chmod(0o2750)
    return directory


def _env(directory: Path, extra_path: Path | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env[GID_OVERRIDE] = str(directory.stat().st_gid)
    if extra_path is not None:
        env["PATH"] = f"{extra_path}{os.pathsep}{env['PATH']}"
    return env


def _run(
    mode: str,
    directory: Path,
    stdin: str = "",
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), mode, str(directory)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env if env is not None else _env(directory),
        check=False,
    )


def _stdin(
    key: str = KEY, client_id: str = CLIENT_ID, secret: str = CLIENT_SECRET
) -> str:
    return f"{key}\n{client_id}\n{secret}\n"


def _seed_old(directory: Path) -> dict[str, bytes]:
    old = {
        "access_client_id": b"old-id\n",
        "access_client_secret": b"old-secret\n",
        "delivery_key": f"{OLD_KEY}\n".encode(),
    }
    for name, content in old.items():
        (directory / name).write_bytes(content)
    return old


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {entry.name: entry.read_bytes() for entry in sorted(directory.iterdir())}


def _assert_no_secrets(result: subprocess.CompletedProcess[str]) -> None:
    combined = result.stdout + result.stderr
    for secret in (KEY, OLD_KEY, CLIENT_SECRET, CLIENT_ID):
        assert secret not in combined


def _mv_stub(tmp_path: Path, fail_on_call: int) -> Path:
    bin_dir = tmp_path / "stub-bin"
    bin_dir.mkdir()
    counter = tmp_path / "mv-calls"
    counter.write_text("0")
    stub = bin_dir / "mv"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'count=$(( $(cat "{counter}") + 1 ))\n'
        f'echo "$count" > "{counter}"\n'
        f'if [ "$count" -eq {fail_on_call} ]; then exit 1; fi\n'
        f'exec "{_REAL_MV}" "$@"\n'
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return bin_dir


def test_first_write_installs_three_files_with_dir_group_and_mode(key_dir: Path):
    """
    GIVEN an empty valid directory
    WHEN a write runs with valid stdin
    THEN three 640 files exist with the directory's group and the hash is printed.
    """
    result = _run("--write", key_dir, _stdin())

    assert result.returncode == 0, result.stderr
    assert sorted(entry.name for entry in key_dir.iterdir()) == sorted(FILE_NAMES)
    for name in FILE_NAMES:
        info = (key_dir / name).stat()
        assert stat.S_IMODE(info.st_mode) == 0o640
        assert info.st_gid == key_dir.stat().st_gid
    assert (key_dir / "delivery_key").read_text() == KEY + "\n"
    assert (key_dir / "access_client_id").read_text() == CLIENT_ID + "\n"
    assert (key_dir / "access_client_secret").read_text() == CLIENT_SECRET + "\n"
    assert result.stdout.strip() == hashlib.sha256((KEY + "\n").encode()).hexdigest()
    _assert_no_secrets(result)


def test_write_replaces_existing_key_and_token(key_dir: Path):
    """
    GIVEN a directory holding an older key and token
    WHEN a new write runs
    THEN all three files hold the new values.
    """
    _seed_old(key_dir)

    result = _run("--write", key_dir, _stdin())

    assert result.returncode == 0, result.stderr
    assert (key_dir / "delivery_key").read_text() == KEY + "\n"
    assert (key_dir / "access_client_secret").read_text() == CLIENT_SECRET + "\n"
    assert len(list(key_dir.iterdir())) == 3


@pytest.mark.parametrize(
    "stdin",
    [
        _stdin(key="dak_short"),
        _stdin(key="notdak_" + "A" * 43),
        _stdin(key=KEY + "extra"),
        f"{KEY}\n{CLIENT_ID}\n",
        f"{KEY}\n{CLIENT_ID}",
        _stdin(secret=""),
        _stdin(client_id=""),
        _stdin() + "fourth-line\n",
    ],
    ids=[
        "short-key",
        "wrong-prefix",
        "long-key",
        "two-lines",
        "unterminated-two-lines",
        "empty-secret",
        "empty-client-id",
        "four-lines",
    ],
)
def test_bad_input_fails_leaving_previous_files_untouched(key_dir: Path, stdin: str):
    """
    GIVEN a directory with previous files
    WHEN stdin is malformed
    THEN the write fails, previous files are byte-identical, no temps remain, no value is echoed.
    """
    old = _seed_old(key_dir)

    result = _run("--write", key_dir, stdin)

    assert result.returncode != 0
    assert _snapshot(key_dir) == old
    assert not _HEX64.search(result.stdout)
    _assert_no_secrets(result)


@pytest.mark.parametrize("failing_move", [1, 2, 3])
def test_failing_move_keeps_previous_key_and_leaves_no_temps(
    key_dir: Path, tmp_path: Path, failing_move: int
):
    """
    GIVEN a mv that fails on its Nth call
    WHEN a write replaces existing files
    THEN it exits non-zero, the previous delivery_key is byte-identical, no temps remain and no hash prints.
    """
    old = _seed_old(key_dir)
    stub_bin = _mv_stub(tmp_path, failing_move)

    result = _run("--write", key_dir, _stdin(), env=_env(key_dir, stub_bin))

    assert result.returncode != 0
    assert (key_dir / "delivery_key").read_bytes() == old["delivery_key"]
    assert sorted(entry.name for entry in key_dir.iterdir()) == sorted(FILE_NAMES)
    assert not _HEX64.search(result.stdout)
    _assert_no_secrets(result)


@SKIP_AS_ROOT
def test_read_only_directory_fails_before_any_move(key_dir: Path):
    """
    GIVEN a read-only directory with previous files
    WHEN a write runs
    THEN preflight fails and the previous files are intact.
    """
    old = _seed_old(key_dir)
    key_dir.chmod(0o2550)

    result = _run("--write", key_dir, _stdin())

    key_dir.chmod(0o2750)
    assert result.returncode != 0
    assert _snapshot(key_dir) == old


def test_check_passes_for_a_valid_directory(key_dir: Path):
    """
    GIVEN a directory with the expected group and mode
    WHEN --check runs
    THEN it exits 0 with no output.
    """
    result = _run("--check", key_dir)

    assert result.returncode == 0, result.stderr


def test_check_fails_for_missing_directory(tmp_path: Path):
    """
    GIVEN a path that does not exist
    WHEN --check runs
    THEN it exits non-zero with one line.
    """
    result = _run("--check", tmp_path / "absent", env=dict(os.environ))

    assert result.returncode != 0
    assert len(result.stderr.strip().splitlines()) == 1


def test_check_fails_for_a_file_path(tmp_path: Path):
    """
    GIVEN a path that is a regular file
    WHEN --check runs
    THEN it exits non-zero.
    """
    path = tmp_path / "plain-file"
    path.write_text("x")

    result = _run("--check", path, env=dict(os.environ))

    assert result.returncode != 0


@pytest.mark.parametrize("mode", [0o750, 0o2755, 0o2770, 0o2700])
def test_check_fails_for_wrong_mode(key_dir: Path, mode: int):
    """
    GIVEN a directory whose mode is not 2750
    WHEN --check runs
    THEN it exits non-zero naming the mode.
    """
    key_dir.chmod(mode)

    result = _run("--check", key_dir)

    assert result.returncode != 0
    assert "mode" in result.stderr


def test_check_fails_for_wrong_group(key_dir: Path):
    """
    GIVEN a directory whose gid differs from the expected gid
    WHEN --check runs
    THEN it exits non-zero naming the group.
    """
    env = _env(key_dir)
    env[GID_OVERRIDE] = str(key_dir.stat().st_gid + 1)

    result = _run("--check", key_dir, env=env)

    assert result.returncode != 0
    assert "group" in result.stderr


def test_default_expected_gid_is_1001(key_dir: Path):
    """
    GIVEN the override is unset and the directory's gid is not 1001
    WHEN --check runs
    THEN it fails.
    """
    if key_dir.stat().st_gid == 1001:
        pytest.skip("dev host group is already 1001")
    env = dict(os.environ)
    env.pop(GID_OVERRIDE, None)

    result = _run("--check", key_dir, env=env)

    assert result.returncode != 0
    assert "1001" in result.stderr


@SKIP_AS_ROOT
def test_check_fails_for_unwritable_directory(key_dir: Path):
    """
    GIVEN a directory without write permission
    WHEN --check runs
    THEN it exits non-zero.
    """
    key_dir.chmod(0o2550)

    result = _run("--check", key_dir)

    key_dir.chmod(0o2750)
    assert result.returncode != 0


@pytest.mark.parametrize("workflow", [PROD_DEPLOY, NOTIFS_EXCHANGE])
def test_workflows_never_set_the_expected_gid_override(workflow: Path):
    """
    GIVEN the production deploy and exchange workflows
    WHEN their text is read
    THEN neither mentions the test-only gid override.
    """
    if not workflow.exists():
        pytest.skip(f"{workflow.name} not created yet (Step 4)")

    assert GID_OVERRIDE not in workflow.read_text()
