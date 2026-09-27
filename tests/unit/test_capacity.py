"""Unit tests for the host-side capacity derivation (`scripts/capacity.py`).

Every probe value is fabricated — no Docker, no `/proc` — so these run
identically on a laptop, inside the web container, and on a CI runner.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts import capacity
from scripts.capacity import (
    CONN_BASE,
    CONN_PER_WORKER,
    DEFAULT_MEM_FRACTION,
    DEFAULT_MEM_SAFETY,
    DOCKER_INFO_TIMEOUT_SECONDS,
    ENV_KEYS,
    HARD_N_CEILING,
    METRICS_REDIS_DB_BASE,
    Capacity,
    DockerInfoError,
    InfeasibleCapacity,
    Overrides,
    Probe,
    _memory_guard,
    _usable_gb,
    changed_interlocks,
    clamp,
    derive,
    fingerprint,
    main,
    parse_cgroup_max,
    parse_docker_info,
    parse_meminfo,
    probe,
    read_env,
    render_env,
    round_up_pow2,
    run_docker_info,
)
from tests.conftest import _METRICS_REDIS_DB_BASE

pytestmark = pytest.mark.unit

GIB: int = 1024**3
AMPLE_MEMORY_BYTES: int = 256 * GIB


def _probe(
    ncpu: int = 12,
    mem_total_bytes: int = AMPLE_MEMORY_BYTES,
    mem_available_bytes: int | None = None,
    cgroup_max_bytes: int | None = None,
) -> Probe:
    return Probe(
        ncpu=ncpu,
        mem_total_bytes=mem_total_bytes,
        mem_available_bytes=mem_available_bytes,
        cgroup_max_bytes=cgroup_max_bytes,
        host_uid=1000,
        host_gid=1000,
    )


def _derive(
    probe: Probe,
    overrides: Overrides | None = None,
    mem_fraction: float = DEFAULT_MEM_FRACTION,
) -> Capacity:
    return derive(
        probe,
        overrides if overrides is not None else Overrides(),
        mem_fraction,
        DEFAULT_MEM_SAFETY,
    )


# --- clamp / round_up_pow2 ---------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, 2), (2, 2), (5, 5), (12, 12), (13, 12)],
)
def test_clamp_boundaries(value: int, expected: int) -> None:
    assert clamp(value, 2, 12) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, 1), (2, 2), (3, 4), (16, 16), (17, 32), (20, 32), (32, 32), (33, 64)],
)
def test_round_up_pow2(value: int, expected: int) -> None:
    assert round_up_pow2(value) == expected


# --- CPU-derived worker counts -----------------------------------------------


@pytest.mark.parametrize(
    ("ncpu", "expected_n_ui"),
    [(1, 2), (3, 2), (12, 8), (18, 12), (32, 12)],
)
def test_derive_n_ui_from_cores(ncpu: int, expected_n_ui: int) -> None:
    assert _derive(_probe(ncpu=ncpu)).n_ui == expected_n_ui


@pytest.mark.parametrize(
    ("ncpu", "expected_n_int"),
    [(1, 2), (3, 3), (12, 12), (18, 16), (32, 16)],
)
def test_derive_n_int_from_cores(ncpu: int, expected_n_int: int) -> None:
    assert _derive(_probe(ncpu=ncpu)).n_int == expected_n_int


def test_derive_interlocks_at_twelve_cores_with_ample_memory() -> None:
    result = _derive(_probe(ncpu=12))
    assert result.n_ui == 8
    assert result.n_int == 12
    assert result.n_max == 12
    assert result.redis_metrics_databases == 32
    assert result.test_max_conn == 230
    assert result.binding_constraint == "cpu"


def test_derive_interlocks_use_max_of_ui_and_int() -> None:
    """n_int dominates n_ui at every core count, so interlocks follow n_int."""
    result = _derive(_probe(ncpu=3))
    assert result.n_max == max(result.n_ui, result.n_int) == 3
    assert result.test_max_conn == 3 * CONN_PER_WORKER + CONN_BASE


def test_redis_metrics_databases_floor_is_sixteen() -> None:
    result = _derive(_probe(ncpu=2))
    assert result.n_max == 2
    assert result.redis_metrics_databases == 16


# --- memory guard ------------------------------------------------------------


def test_memory_guard_binds_when_available_memory_is_low() -> None:
    # usable = min(32 * 0.7, 5 * 0.9) = 4.5 GiB -> floor((4.5 - 2.0) / 0.5) = 5
    result = _derive(
        _probe(ncpu=12, mem_total_bytes=32 * GIB, mem_available_bytes=5 * GIB)
    )
    assert result.usable_gb == pytest.approx(4.5)
    assert result.n_ui == 5
    assert result.n_int == 5
    assert result.n_max == 5
    assert result.binding_constraint == "memory"


def test_memory_guard_uses_min_of_available_and_cgroup() -> None:
    # available = min(20, 4) = 4 GiB -> usable = min(22.4, 3.6) = 3.6 -> n = 3
    result = _derive(
        _probe(
            ncpu=12,
            mem_total_bytes=32 * GIB,
            mem_available_bytes=20 * GIB,
            cgroup_max_bytes=4 * GIB,
        )
    )
    assert result.usable_gb == pytest.approx(3.6)
    assert result.n_int == 3
    assert result.binding_constraint == "memory"


def test_memory_guard_uses_cgroup_when_mem_available_unknown() -> None:
    result = _derive(
        _probe(ncpu=12, mem_total_bytes=32 * GIB, cgroup_max_bytes=4 * GIB)
    )
    assert result.usable_gb == pytest.approx(3.6)


def test_memory_guard_falls_back_to_total_when_availability_unknown() -> None:
    """macOS / Docker Desktop VM: no /proc/meminfo, no cgroup file."""
    # usable = 8 * 0.7 = 5.6 GiB -> floor((5.6 - 2.0) / 0.5) = 7
    result = _derive(_probe(ncpu=12, mem_total_bytes=8 * GIB))
    assert result.usable_gb == pytest.approx(5.6)
    assert result.n_ui == 7
    assert result.n_int == 7
    assert result.binding_constraint == "memory"


def test_memory_guard_never_reduces_below_one() -> None:
    result = _derive(_probe(ncpu=12, mem_total_bytes=1 * GIB))
    assert result.n_ui == 1
    assert result.n_int == 1
    assert result.binding_constraint == "memory"


def test_memory_guard_rounds_off_binary_float_underflow() -> None:
    """A 340 GiB host's usable_gb computes to 237.99999999999997, not 238.0.

    Naively flooring `(usable_gb - BASE_GB) / WORKER_GB` on that raw float
    yields 471 instead of the mathematically-correct 472; `_memory_guard`
    must round the ratio first so this binary-float underflow doesn't
    under-count by one worker.
    """
    host_probe = _probe(mem_total_bytes=340 * GIB)
    usable_gb = _usable_gb(host_probe, DEFAULT_MEM_FRACTION, DEFAULT_MEM_SAFETY)
    assert usable_gb == pytest.approx(238.0)
    assert usable_gb != 238.0  # exercises the actual binary-float underflow
    assert _memory_guard(usable_gb) == 472


def test_cpu_binds_when_memory_is_ample() -> None:
    result = _derive(
        _probe(ncpu=12, mem_total_bytes=64 * GIB, mem_available_bytes=40 * GIB)
    )
    assert result.binding_constraint == "cpu"


def test_mem_fraction_argument_scales_usable_memory() -> None:
    result = _derive(_probe(ncpu=12, mem_total_bytes=10 * GIB), mem_fraction=0.5)
    assert result.usable_gb == pytest.approx(5.0)
    assert result.n_int == 6


@pytest.mark.parametrize("mem_fraction", [0.0, -0.1, 1.5])
def test_mem_fraction_out_of_range_raises(mem_fraction: float) -> None:
    with pytest.raises(InfeasibleCapacity, match="U4I_MEM_FRACTION"):
        _derive(_probe(), mem_fraction=mem_fraction)


def test_mem_fraction_out_of_range_message_ends_with_corrective_command() -> None:
    with pytest.raises(InfeasibleCapacity) as excinfo:
        _derive(_probe(), mem_fraction=1.5)
    assert str(excinfo.value).split("; ")[-1].startswith("rerun with")


# --- overrides ---------------------------------------------------------------


def test_override_below_derived_is_accepted() -> None:
    result = _derive(_probe(ncpu=12), Overrides(n_ui=4, n_int=4))
    assert result.n_ui == 4
    assert result.n_int == 4
    assert result.n_max == 4
    assert result.redis_metrics_databases == 16
    assert result.test_max_conn == 110


def test_override_above_derived_recomputes_interlocks() -> None:
    result = _derive(_probe(ncpu=12), Overrides(n_ui=16))
    assert result.n_ui == 16
    assert result.n_int == 12
    assert result.n_max == 16
    assert result.redis_metrics_databases == 32
    assert result.test_max_conn == 290


def test_override_without_memory_pressure_reports_override_binding() -> None:
    assert _derive(_probe(ncpu=12), Overrides(n_ui=4)).binding_constraint == "override"


def test_memory_binding_wins_over_override_binding() -> None:
    result = _derive(_probe(ncpu=12, mem_total_bytes=8 * GIB), Overrides(n_ui=4))
    assert result.n_int == 7
    assert result.binding_constraint == "memory"


def test_override_at_hard_ceiling_is_accepted() -> None:
    result = _derive(_probe(ncpu=12), Overrides(n_int=HARD_N_CEILING))
    assert result.n_int == HARD_N_CEILING
    assert result.redis_metrics_databases == 64


def test_override_above_memory_guard_raises_naming_gb() -> None:
    # usable = 8 * 0.7 = 5.6 GiB; n_ui=20 needs 2.0 + 20 * 0.5 = 12.0 GiB
    with pytest.raises(InfeasibleCapacity) as excinfo:
        _derive(_probe(ncpu=12, mem_total_bytes=8 * GIB), Overrides(n_ui=20))
    message = str(excinfo.value)
    assert "U4I_N_UI=20" in message
    assert "12.0 GB" in message
    assert "5.6 GB" in message


def test_int_override_above_memory_guard_names_int_knob() -> None:
    with pytest.raises(InfeasibleCapacity, match="U4I_N_INT=20"):
        _derive(_probe(ncpu=12, mem_total_bytes=8 * GIB), Overrides(n_int=20))


def test_override_above_hard_ceiling_raises_naming_shared_redis() -> None:
    with pytest.raises(InfeasibleCapacity) as excinfo:
        _derive(_probe(ncpu=12), Overrides(n_ui=HARD_N_CEILING + 1))
    message = str(excinfo.value)
    assert "U4I_N_UI=31" in message
    assert "--databases 32" in message


@pytest.mark.parametrize("bad_value", [0, -3])
def test_override_below_one_raises(bad_value: int) -> None:
    with pytest.raises(InfeasibleCapacity, match="U4I_N_INT"):
        _derive(_probe(), Overrides(n_int=bad_value))


@pytest.mark.parametrize(
    "overrides",
    [
        Overrides(n_ui=0),
        Overrides(n_ui=HARD_N_CEILING + 1),
        Overrides(n_ui=20),
        Overrides(n_int=20),
    ],
)
def test_infeasible_messages_end_with_corrective_command(overrides: Overrides) -> None:
    with pytest.raises(InfeasibleCapacity) as excinfo:
        _derive(_probe(ncpu=12, mem_total_bytes=8 * GIB), overrides)
    assert str(excinfo.value).rstrip().split("; ")[-1].startswith("rerun with")


def test_override_mem_fraction_fed_by_caller_changes_guard() -> None:
    """The caller resolves `Overrides.mem_fraction`; derive only sees the float."""
    overrides = Overrides(mem_fraction=0.9)
    resolved = (
        overrides.mem_fraction
        if overrides.mem_fraction is not None
        else DEFAULT_MEM_FRACTION
    )
    result = _derive(_probe(ncpu=12, mem_total_bytes=8 * GIB), overrides, resolved)
    assert result.usable_gb == pytest.approx(7.2)
    assert result.n_int == 10


# --- contracts ---------------------------------------------------------------


def test_metrics_redis_db_base_matches_conftest() -> None:
    assert METRICS_REDIS_DB_BASE == _METRICS_REDIS_DB_BASE


def test_capacity_module_is_stdlib_only() -> None:
    """`capacity.py` runs on the host under bare mise python — stdlib only.

    Loaded by file path in a fresh interpreter with a pruned `sys.path` (no
    project root), so any third-party or `backend` import would either fail or
    show up in `sys.modules`.
    """
    probe_script = (
        "import importlib.util\n"
        "import sys\n"
        "sys.path = [p for p in sys.path if p not in ('', PROJECT_ROOT)]\n"
        "spec = importlib.util.spec_from_file_location('capacity_leaf', CAPACITY_FILE)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        # Register before exec so the frozen dataclasses can resolve their own
        # module under `from __future__ import annotations`.
        "sys.modules[spec.name] = module\n"
        "spec.loader.exec_module(module)\n"
        "forbidden = [name for name in sys.modules "
        "if name.split('.')[0] in ('flask', 'sqlalchemy', 'redis', 'backend')]\n"
        "assert forbidden == [], forbidden\n"
    )
    capacity_file = Path(capacity.__file__).resolve()
    project_root = capacity_file.parents[1]
    preamble = (
        f"PROJECT_ROOT = {str(project_root)!r}\n"
        f"CAPACITY_FILE = {str(capacity_file)!r}\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", preamble + probe_script],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"capacity module pulled in a non-stdlib import:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )


# --- parsers -----------------------------------------------------------------

MEMINFO_TEXT: str = "MemTotal:       16384000 kB\nMemFree:         1024000 kB\nMemAvailable:    9437184 kB\n"


def test_parse_meminfo_returns_bytes() -> None:
    assert parse_meminfo(MEMINFO_TEXT, "MemAvailable") == 9437184 * 1024


def test_parse_meminfo_missing_key_returns_none() -> None:
    assert parse_meminfo(MEMINFO_TEXT, "SwapTotal") is None


def test_parse_meminfo_does_not_match_key_prefix() -> None:
    assert parse_meminfo("MemAvailableX:  5 kB\n", "MemAvailable") is None


def test_parse_cgroup_max_unlimited_returns_none() -> None:
    assert parse_cgroup_max("max\n") is None


@pytest.mark.parametrize("meminfo_text", ["MemAvailable:\n", "MemAvailable: abc kB\n"])
def test_parse_meminfo_malformed_value_returns_none(meminfo_text: str) -> None:
    assert parse_meminfo(meminfo_text, "MemAvailable") is None


def test_parse_cgroup_max_returns_int() -> None:
    assert parse_cgroup_max("4294967296\n") == 4294967296


@pytest.mark.parametrize("cgroup_text", ["\n", "garbage\n"])
def test_parse_cgroup_max_malformed_value_returns_none(cgroup_text: str) -> None:
    assert parse_cgroup_max(cgroup_text) is None


def test_parse_docker_info_returns_cores_and_memory() -> None:
    assert parse_docker_info("12 15923847168\n") == (12, 15923847168)


@pytest.mark.parametrize(
    "output", ["", "12", "twelve 1024", "12 1024 extra", "\u00b2 1024"]
)
def test_parse_docker_info_rejects_malformed_output(output: str) -> None:
    with pytest.raises(DockerInfoError, match="unexpected docker info output"):
        parse_docker_info(output)


# --- run_docker_info ---------------------------------------------------------


def _completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["docker"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_run_docker_info_returns_stdout_with_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_kwargs: dict[str, object] = {}

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        recorded_kwargs.update(kwargs)
        return _completed(0, stdout="12 15923847168\n")

    monkeypatch.setattr(capacity.subprocess, "run", fake_run)

    assert run_docker_info() == "12 15923847168\n"
    assert recorded_kwargs["timeout"] == DOCKER_INFO_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    ("stderr", "expected_message"),
    [
        (
            "  Cannot connect to the Docker daemon\n",
            "Cannot connect to the Docker daemon",
        ),
        ("", "docker info exited 1"),
    ],
)
def test_run_docker_info_non_zero_exit_raises(
    monkeypatch: pytest.MonkeyPatch, stderr: str, expected_message: str
) -> None:
    monkeypatch.setattr(
        capacity.subprocess, "run", lambda *args, **kwargs: _completed(1, stderr=stderr)
    )
    with pytest.raises(DockerInfoError) as excinfo:
        run_docker_info()
    assert str(excinfo.value) == expected_message


@pytest.mark.parametrize(
    ("raised", "expected_fragment"),
    [
        (FileNotFoundError("No such file or directory: 'docker'"), "docker"),
        (PermissionError("Permission denied: 'docker'"), "Permission denied"),
        (
            subprocess.TimeoutExpired(
                cmd="docker", timeout=DOCKER_INFO_TIMEOUT_SECONDS
            ),
            f"timed out after {DOCKER_INFO_TIMEOUT_SECONDS}s",
        ),
    ],
)
def test_run_docker_info_launch_failures_raise_docker_info_error(
    monkeypatch: pytest.MonkeyPatch, raised: Exception, expected_fragment: str
) -> None:
    def failing_run(*args: object, **kwargs: object) -> None:
        raise raised

    monkeypatch.setattr(capacity.subprocess, "run", failing_run)
    with pytest.raises(DockerInfoError, match=expected_fragment):
        run_docker_info()


# --- probe -------------------------------------------------------------------


def test_probe_reads_injected_docker_info_and_files(tmp_path: Path) -> None:
    meminfo_path = tmp_path / "meminfo"
    meminfo_path.write_text(MEMINFO_TEXT)
    cgroup_path = tmp_path / "memory.max"
    cgroup_path.write_text("4294967296\n")

    result = probe(lambda: "12 15923847168", meminfo_path, cgroup_path)

    assert result.ncpu == 12
    assert result.mem_total_bytes == 15923847168
    assert result.mem_available_bytes == 9437184 * 1024
    assert result.cgroup_max_bytes == 4294967296
    assert result.host_uid == os.getuid()
    assert result.host_gid == os.getgid()


def test_probe_missing_files_give_none(tmp_path: Path) -> None:
    """The macOS / Docker Desktop path: no /proc/meminfo, no cgroup file."""
    result = probe(
        lambda: "8 8589934592", tmp_path / "no-meminfo", tmp_path / "no-cgroup"
    )
    assert result.mem_available_bytes is None
    assert result.cgroup_max_bytes is None


def test_probe_propagates_docker_info_error(tmp_path: Path) -> None:
    def failing_docker_info() -> str:
        raise DockerInfoError("Cannot connect to the Docker daemon")

    with pytest.raises(DockerInfoError, match="Cannot connect"):
        probe(failing_docker_info, tmp_path / "meminfo", tmp_path / "cgroup")


# --- fingerprint -------------------------------------------------------------


def test_fingerprint_is_stable_for_equal_inputs() -> None:
    assert fingerprint(_probe(), Overrides()) == fingerprint(_probe(), Overrides())


def test_fingerprint_ignores_mem_available() -> None:
    assert fingerprint(_probe(mem_available_bytes=1 * GIB), Overrides()) == fingerprint(
        _probe(mem_available_bytes=9 * GIB), Overrides()
    )


@pytest.mark.parametrize(
    ("changed_probe", "changed_overrides"),
    [
        (_probe(ncpu=8), Overrides()),
        (_probe(mem_total_bytes=64 * GIB), Overrides()),
        (_probe(cgroup_max_bytes=4 * GIB), Overrides()),
        (
            Probe(
                ncpu=12,
                mem_total_bytes=AMPLE_MEMORY_BYTES,
                mem_available_bytes=None,
                cgroup_max_bytes=None,
                host_uid=501,
                host_gid=1000,
            ),
            Overrides(),
        ),
        (_probe(), Overrides(n_ui=4)),
        (_probe(), Overrides(n_int=4)),
        (_probe(), Overrides(mem_fraction=0.5)),
    ],
)
def test_fingerprint_changes_with_each_input(
    changed_probe: Probe, changed_overrides: Overrides
) -> None:
    assert fingerprint(changed_probe, changed_overrides) != fingerprint(
        _probe(), Overrides()
    )


def test_fingerprint_is_sha256_hex() -> None:
    digest = fingerprint(_probe(), Overrides())
    assert len(digest) == 64
    int(digest, 16)


def test_fingerprint_hashes_the_documented_source_string() -> None:
    source = f"12|{AMPLE_MEMORY_BYTES}|None|1000|1000|None|None|None"
    assert (
        fingerprint(_probe(), Overrides())
        == hashlib.sha256(source.encode()).hexdigest()
    )


# --- render_env / read_env / changed_interlocks -------------------------------

RENDERED_KEYS: list[str] = [
    "U4I_N_UI",
    "U4I_N_INT",
    "U4I_N_MAX",
    "REDIS_METRICS_DATABASES",
    "U4I_TEST_MAX_CONN",
    "HOST_UID",
    "HOST_GID",
    "U4I_CAPACITY_FINGERPRINT",
    "U4I_OVERRIDE_N_UI",
    "U4I_OVERRIDE_N_INT",
    "U4I_OVERRIDE_MEM_FRACTION",
]


def _render(
    overrides: Overrides | None = None, probe_value: Probe | None = None
) -> str:
    resolved_overrides = overrides if overrides is not None else Overrides()
    resolved_probe = probe_value if probe_value is not None else _probe()
    result = _derive(resolved_probe, resolved_overrides)
    return render_env(
        result,
        resolved_probe,
        resolved_overrides,
        fingerprint(resolved_probe, resolved_overrides),
    )


def test_render_env_header_and_decision_comment() -> None:
    lines = _render().splitlines()
    assert lines[0] == "# GENERATED by make capacity — DO NOT EDIT"
    assert "# decision: n_ui=8 n_int=12 binding=cpu usable_gb=179.2" in lines


def test_render_env_emits_exactly_the_expected_keys() -> None:
    keys = [
        line.split("=", 1)[0]
        for line in _render().splitlines()
        if line and not line.startswith("#")
    ]
    assert keys == RENDERED_KEYS
    assert list(ENV_KEYS) == RENDERED_KEYS


def test_render_env_values() -> None:
    probe_value = _probe()
    rendered = _render(probe_value=probe_value)
    assert "U4I_N_UI=8\n" in rendered
    assert "U4I_N_INT=12\n" in rendered
    assert "U4I_N_MAX=12\n" in rendered
    assert "REDIS_METRICS_DATABASES=32\n" in rendered
    assert "U4I_TEST_MAX_CONN=230\n" in rendered
    assert "HOST_UID=1000\n" in rendered
    assert "HOST_GID=1000\n" in rendered
    assert (
        f"U4I_CAPACITY_FINGERPRINT={fingerprint(probe_value, Overrides())}\n"
        in rendered
    )
    assert "U4I_OVERRIDE_N_UI=\n" in rendered
    assert "U4I_OVERRIDE_N_INT=\n" in rendered
    assert "U4I_OVERRIDE_MEM_FRACTION=\n" in rendered


@pytest.mark.parametrize(
    ("overrides", "expected_mem_fraction"),
    [(Overrides(n_ui=4, mem_fraction=0.5), "0.5"), (Overrides(n_ui=4), "")],
)
def test_read_env_round_trips_render_env(
    tmp_path: Path, overrides: Overrides, expected_mem_fraction: str
) -> None:
    env_path = tmp_path / "capacity.env"
    env_path.write_text(_render(overrides))
    parsed = read_env(env_path)
    assert list(parsed) == RENDERED_KEYS
    assert parsed["U4I_OVERRIDE_N_UI"] == "4"
    assert parsed["U4I_OVERRIDE_N_INT"] == ""
    assert parsed["U4I_OVERRIDE_MEM_FRACTION"] == expected_mem_fraction


def test_read_env_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    env_path = tmp_path / "capacity.env"
    env_path.write_text("# comment\n\nKEY=value\n  # indented comment\n")
    assert read_env(env_path) == {"KEY": "value"}


def test_changed_interlocks_names_only_differing_interlocks() -> None:
    old = {
        "REDIS_METRICS_DATABASES": "32",
        "U4I_TEST_MAX_CONN": "230",
        "HOST_UID": "1000",
        "HOST_GID": "1000",
        "U4I_N_UI": "8",
        "U4I_CAPACITY_FINGERPRINT": "aaa",
    }
    new = {
        **old,
        "U4I_TEST_MAX_CONN": "110",
        "HOST_GID": "20",
        "U4I_N_UI": "4",
        "U4I_CAPACITY_FINGERPRINT": "bbb",
    }
    assert changed_interlocks(old, new) == ["U4I_TEST_MAX_CONN", "HOST_GID"]


def test_changed_interlocks_empty_when_equal() -> None:
    values = {"REDIS_METRICS_DATABASES": "32", "U4I_TEST_MAX_CONN": "230"}
    assert changed_interlocks(values, dict(values)) == []


# --- main: generate / ensure / show ------------------------------------------

OLD_MTIME_NS: int = 1_000_000_000 * 1_000_000_000


def _fixed_probe(probe_value: Probe) -> Callable[[], Probe]:
    return lambda: probe_value


def _run(argv: list[str], probe_value: Probe | None = None) -> int:
    return main(
        argv, _fixed_probe(probe_value if probe_value is not None else _probe())
    )


def _age(env_path: Path) -> None:
    """Backdate P so an untouched file is distinguishable from a rewrite."""
    os.utime(env_path, ns=(OLD_MTIME_NS, OLD_MTIME_NS))


def test_generate_writes_file_and_reports_regenerated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    assert _run(["generate", "--output", str(env_path)]) == 0
    assert env_path.read_text() == _render()
    out = capsys.readouterr().out
    assert out == f"capacity regenerated ({env_path})\n"


def test_generate_unchanged_leaves_file_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    _age(env_path)
    capsys.readouterr()

    assert _run(["generate", "--output", str(env_path)]) == 0

    assert capsys.readouterr().out == f"capacity unchanged ({env_path})\n"
    assert env_path.stat().st_mtime_ns == OLD_MTIME_NS


def test_generate_ignores_decision_comment_jitter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """usable_gb in the `# decision:` line tracks mem_available; not a change."""
    env_path = tmp_path / "capacity.env"
    first_probe = _probe(mem_available_bytes=100 * GIB)
    second_probe = _probe(mem_available_bytes=120 * GIB)
    _run(["generate", "--output", str(env_path)], first_probe)
    original_content = env_path.read_text()
    _age(env_path)
    capsys.readouterr()

    assert _run(["generate", "--output", str(env_path)], second_probe) == 0

    assert _derive(second_probe).binding_constraint == "cpu"
    assert _render(probe_value=second_probe) != original_content
    assert capsys.readouterr().out == f"capacity unchanged ({env_path})\n"
    assert env_path.read_text() == original_content
    assert env_path.stat().st_mtime_ns == OLD_MTIME_NS


def test_generate_and_ensure_reuse_recorded_mem_fraction_until_auto(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path), "--mem-fraction", "0.5"])
    assert read_env(env_path)["U4I_OVERRIDE_MEM_FRACTION"] == "0.5"

    _run(["generate", "--output", str(env_path)])
    assert read_env(env_path)["U4I_OVERRIDE_MEM_FRACTION"] == "0.5"

    recorded = read_env(env_path)
    env_path.write_text(
        env_path.read_text().replace(recorded["U4I_CAPACITY_FINGERPRINT"], "tampered")
    )
    _run(["ensure", "--output", str(env_path)])
    assert read_env(env_path)["U4I_OVERRIDE_MEM_FRACTION"] == "0.5"
    assert read_env(env_path)["U4I_CAPACITY_FINGERPRINT"] == fingerprint(
        _probe(), Overrides(mem_fraction=0.5)
    )

    _run(["generate", "--output", str(env_path), "--mem-fraction", "auto"])
    assert read_env(env_path)["U4I_OVERRIDE_MEM_FRACTION"] == ""


def test_generate_reuses_recorded_worker_overrides_until_auto(tmp_path: Path) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path), "--n-ui", "4", "--n-int", "5"])
    _run(["generate", "--output", str(env_path)])
    recorded = read_env(env_path)
    assert recorded["U4I_N_UI"] == "4"
    assert recorded["U4I_OVERRIDE_N_UI"] == "4"
    assert recorded["U4I_OVERRIDE_N_INT"] == "5"

    _run(["generate", "--output", str(env_path), "--n-ui", "auto"])
    recorded = read_env(env_path)
    assert recorded["U4I_OVERRIDE_N_UI"] == ""
    assert recorded["U4I_N_UI"] == "8"
    assert recorded["U4I_OVERRIDE_N_INT"] == "5"

    _run(["generate", "--output", str(env_path), "--n-int", "auto"])
    assert read_env(env_path)["U4I_OVERRIDE_N_INT"] == ""


def test_ensure_restores_tampered_fingerprint_without_recreate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    original_content = env_path.read_text()
    real_fingerprint = read_env(env_path)["U4I_CAPACITY_FINGERPRINT"]
    env_path.write_text(original_content.replace(real_fingerprint, "tampered"))
    capsys.readouterr()

    assert _run(["ensure", "--output", str(env_path)]) == 0

    out = capsys.readouterr().out
    assert out == f"capacity regenerated ({env_path})\n"
    assert "recreate required" not in out
    assert env_path.read_text() == original_content


def test_generate_reports_recreate_when_interlocks_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    capsys.readouterr()

    assert _run(["generate", "--output", str(env_path)], _probe(ncpu=4)) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"capacity regenerated ({env_path})"
    assert lines[1] == (
        "recreate required: run 'make up d=1' "
        "(changed: REDIS_METRICS_DATABASES, U4I_TEST_MAX_CONN)"
    )
    assert read_env(env_path)["U4I_TEST_MAX_CONN"] == "110"


def test_ensure_with_matching_fingerprint_prints_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    _age(env_path)
    capsys.readouterr()

    assert _run(["ensure", "--output", str(env_path)]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert env_path.stat().st_mtime_ns == OLD_MTIME_NS


def test_ensure_restores_deleted_key_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    original_content = env_path.read_text()
    env_path.write_text(original_content.replace("U4I_TEST_MAX_CONN=230\n", ""))
    assert "U4I_TEST_MAX_CONN" not in read_env(env_path)
    capsys.readouterr()

    assert _run(["ensure", "--output", str(env_path)]) == 0

    assert capsys.readouterr().out.startswith(f"capacity regenerated ({env_path})\n")
    assert env_path.read_text() == original_content


def test_ensure_infeasible_recorded_override_exits_non_zero_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path), "--n-ui", "10"])
    original_content = env_path.read_text()
    _age(env_path)
    capsys.readouterr()

    exit_code = _run(
        ["ensure", "--output", str(env_path)], _probe(mem_total_bytes=4 * GIB)
    )

    assert exit_code != 0
    assert "U4I_N_UI" in capsys.readouterr().err
    assert env_path.read_text() == original_content
    assert env_path.stat().st_mtime_ns == OLD_MTIME_NS


def test_ensure_creates_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    assert _run(["ensure", "--output", str(env_path)]) == 0
    assert env_path.read_text() == _render()
    assert capsys.readouterr().out == f"capacity regenerated ({env_path})\n"


def test_ensure_regenerates_when_probe_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    capsys.readouterr()

    assert _run(["ensure", "--output", str(env_path)], _probe(ncpu=4)) == 0

    out = capsys.readouterr().out
    assert out.startswith(f"capacity regenerated ({env_path})\n")
    assert "recreate required" in out


def test_generate_leaves_no_temp_files(tmp_path: Path) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    _run(["generate", "--output", str(env_path)], _probe(ncpu=4))
    assert sorted(path.name for path in tmp_path.iterdir()) == ["capacity.env"]


def test_show_prints_table_and_slug(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("U4I_SLUG", "cap-test")
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    capsys.readouterr()

    assert _run(["show", "--output", str(env_path)]) == 0

    out = capsys.readouterr().out
    assert "n_ui=8 n_int=12 binding=cpu" in out
    for key in RENDERED_KEYS:
        assert key in out
    assert "U4I_SLUG" in out
    assert "cap-test" in out


def test_show_missing_file_exits_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run(["show", "--output", str(tmp_path / "missing.env")]) != 0
    assert "make capacity" in capsys.readouterr().err


def test_docker_info_error_exits_non_zero_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def failing_probe() -> Probe:
        raise DockerInfoError("Cannot connect to the Docker daemon at unix:///x")

    env_path = tmp_path / "capacity.env"
    exit_code = main(["generate", "--output", str(env_path)], failing_probe)

    assert exit_code != 0
    assert capsys.readouterr().err == (
        "make capacity: docker info failed — "
        "Cannot connect to the Docker daemon at unix:///x\n"
    )
    assert not env_path.exists()


def test_infeasible_override_exits_non_zero_and_leaves_file_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    original_content = env_path.read_text()
    _age(env_path)
    capsys.readouterr()

    exit_code = _run(
        ["generate", "--output", str(env_path), "--n-ui", str(HARD_N_CEILING + 1)]
    )

    assert exit_code != 0
    assert "--databases 32" in capsys.readouterr().err
    assert env_path.read_text() == original_content
    assert env_path.stat().st_mtime_ns == OLD_MTIME_NS


@pytest.mark.parametrize(
    "flag_args",
    [["--n-ui", "abc"], ["--n-int", "1.5"], ["--mem-fraction", "lots"]],
)
def test_malformed_flag_values_are_rejected(
    tmp_path: Path, flag_args: list[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        _run(["generate", "--output", str(tmp_path / "capacity.env"), *flag_args])
    assert excinfo.value.code != 0


@pytest.mark.parametrize("mem_fraction", ["nan", "inf", "-inf"])
def test_non_finite_mem_fraction_exits_non_zero_without_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mem_fraction: str
) -> None:
    env_path = tmp_path / "capacity.env"
    exit_code = _run(
        ["generate", "--output", str(env_path), f"--mem-fraction={mem_fraction}"]
    )
    assert exit_code != 0
    assert "U4I_MEM_FRACTION" in capsys.readouterr().err
    assert not env_path.exists()


def test_generate_into_missing_directory_exits_non_zero_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "no-such-dir" / "capacity.env"

    assert _run(["generate", "--output", str(env_path)]) != 0

    assert capsys.readouterr().err.startswith("make capacity: ")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "override_key",
    ["U4I_OVERRIDE_N_UI", "U4I_OVERRIDE_N_INT", "U4I_OVERRIDE_MEM_FRACTION"],
)
def test_malformed_recorded_override_exits_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], override_key: str
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    env_path.write_text(
        env_path.read_text().replace(f"{override_key}=\n", f"{override_key}=x\n")
    )
    tampered_content = env_path.read_text()
    assert read_env(env_path)[override_key] == "x"
    _age(env_path)
    capsys.readouterr()

    assert _run(["generate", "--output", str(env_path)]) != 0
    assert override_key in capsys.readouterr().err
    assert env_path.read_text() == tampered_content
    assert env_path.stat().st_mtime_ns == OLD_MTIME_NS


def test_failed_replace_cleans_up_temp_file_and_keeps_original(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    original_content = env_path.read_text()
    capsys.readouterr()

    def failing_replace(
        source: str | os.PathLike[str], target: str | os.PathLike[str]
    ) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(capacity.os, "replace", failing_replace)

    # A changed probe forces a rewrite, so the temp file exists when replace fails.
    exit_code = _run(["generate", "--output", str(env_path)], _probe(ncpu=4))

    assert exit_code != 0
    assert capsys.readouterr().err == "make capacity: simulated replace failure\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["capacity.env"]
    assert env_path.read_text() == original_content
