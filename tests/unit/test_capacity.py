"""Unit tests for the host-side capacity derivation (`scripts/capacity.py`).

Every probe value is fabricated — no Docker, no `/proc` — so these run
identically on a laptop, inside the web container, and on a CI runner.
"""

from __future__ import annotations

import hashlib
import os
import re
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
    DEV_CONN_BUDGET,
    DOCKER_INFO_TIMEOUT_SECONDS,
    DOCKER_RUN_TIMEOUT_SECONDS,
    ENV_KEYS,
    HARD_N_CEILING,
    HUB_INTERLOCK_KEYS,
    INTERLOCK_KEYS,
    LEASE_CONCURRENT_RUNS,
    METRICS_REDIS_RESERVED_DBS,
    PG_SHARED_BUFFERS_MAX_MB,
    PG_SHARED_BUFFERS_MIN_MB,
    SESSION_REDIS_RESERVED_DBS,
    SHARED_REDIS_DATABASES,
    SPOKE_INTERLOCK_KEYS,
    SUPERUSER_RESERVED,
    Capacity,
    DockerInfoError,
    DockerRunError,
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
    run_docker,
    run_docker_info,
)

pytestmark = pytest.mark.unit

GIB: int = 1024**3
AMPLE_MEMORY_BYTES: int = 256 * GIB
LOCAL_COMPOSE_FILE: Path = (
    Path(__file__).resolve().parents[2] / "docker" / "compose.local.yaml"
)
LITERAL_REDIS_DATABASES_PATTERN: re.Pattern[str] = re.compile(
    r"redis-server --databases (\d+)\s*$", re.MULTILINE
)


@pytest.fixture(autouse=True)
def _no_inherited_primary_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """A PRIMARY_ROOT exported by an outer make (pytest launched from a recipe) must not
    switch `_generate` into its linked-worktree messages; tests that need it set it."""
    monkeypatch.delenv("PRIMARY_ROOT", raising=False)


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
    assert result.pg_test_conn_limit == 230
    assert result.pg_max_conn == 263
    assert result.pg_shared_buffers_mb == PG_SHARED_BUFFERS_MAX_MB
    assert result.binding_constraint == "cpu"


def test_derive_interlocks_on_twelve_core_sixteen_gb_host() -> None:
    """The reference dev host: 12 cores, 15.9 GiB, no availability signal."""
    # usable = 15.9 * 0.7 = 11.13 GiB = 11397 MiB -> shared_buffers = 11397 // 64
    result = _derive(_probe(ncpu=12, mem_total_bytes=int(15.9 * GIB)))
    assert result.n_max == 12
    assert result.pg_test_conn_limit == 230
    assert result.pg_max_conn == 263
    assert result.pg_shared_buffers_mb == 178
    assert result.redis_metrics_databases == 32


def test_derive_pg_max_conn_adds_dev_budget_and_superuser_reserve() -> None:
    result = _derive(_probe(ncpu=3))
    assert result.pg_max_conn == (
        result.pg_test_conn_limit + DEV_CONN_BUDGET + SUPERUSER_RESERVED
    )


def test_derive_redis_metrics_databases_sizes_concurrent_run_leases() -> None:
    result = _derive(_probe(ncpu=12), Overrides(n_int=16))
    assert result.redis_metrics_databases == round_up_pow2(
        METRICS_REDIS_RESERVED_DBS + LEASE_CONCURRENT_RUNS * 16
    )
    assert result.redis_metrics_databases == 64


@pytest.mark.parametrize(
    ("mem_total_bytes", "expected_shared_buffers_mb"),
    [
        (1 * GIB, PG_SHARED_BUFFERS_MIN_MB),
        (8 * GIB, 89),
        (AMPLE_MEMORY_BYTES, PG_SHARED_BUFFERS_MAX_MB),
    ],
)
def test_derive_pg_shared_buffers_is_clamped_share_of_usable_memory(
    mem_total_bytes: int, expected_shared_buffers_mb: int
) -> None:
    result = _derive(_probe(ncpu=12, mem_total_bytes=mem_total_bytes))
    assert result.pg_shared_buffers_mb == expected_shared_buffers_mb


def test_derive_pg_shared_buffers_ignores_mem_available_jitter() -> None:
    """shared_buffers is an interlock, so it must not move with MemAvailable."""
    low = _derive(_probe(mem_total_bytes=16 * GIB, mem_available_bytes=6 * GIB))
    high = _derive(_probe(mem_total_bytes=16 * GIB, mem_available_bytes=7 * GIB))
    assert low.usable_gb != high.usable_gb
    assert low.pg_shared_buffers_mb == high.pg_shared_buffers_mb


def test_derive_pg_shared_buffers_honors_cgroup_limit() -> None:
    # usable = min(64 * 0.7, 6 * 0.9) = 5.4 GiB = 5529 MiB -> 5529 // 64 = 86
    result = _derive(_probe(mem_total_bytes=64 * GIB, cgroup_max_bytes=6 * GIB))
    assert result.pg_shared_buffers_mb == 86


def test_derive_interlocks_use_max_of_ui_and_int() -> None:
    """n_int dominates n_ui at every core count, so interlocks follow n_int."""
    result = _derive(_probe(ncpu=3))
    assert result.n_max == max(result.n_ui, result.n_int) == 3
    assert result.pg_test_conn_limit == 3 * CONN_PER_WORKER + CONN_BASE


def test_shared_redis_databases_hold_concurrent_runs_at_hard_ceiling() -> None:
    assert SHARED_REDIS_DATABASES == max(
        32,
        round_up_pow2(
            SESSION_REDIS_RESERVED_DBS + LEASE_CONCURRENT_RUNS * HARD_N_CEILING
        ),
    )
    assert SHARED_REDIS_DATABASES == 64
    leasable_indices = SHARED_REDIS_DATABASES - SESSION_REDIS_RESERVED_DBS
    assert leasable_indices >= LEASE_CONCURRENT_RUNS * HARD_N_CEILING


def test_local_compose_shared_redis_databases_match_capacity() -> None:
    """compose.local.yaml hardcodes the shared redis count; it must track capacity."""
    literal_counts = LITERAL_REDIS_DATABASES_PATTERN.findall(
        LOCAL_COMPOSE_FILE.read_text()
    )
    assert literal_counts == [str(SHARED_REDIS_DATABASES)]


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
    assert result.pg_test_conn_limit == 110
    assert result.pg_max_conn == 143


def test_override_above_derived_recomputes_interlocks() -> None:
    result = _derive(_probe(ncpu=12), Overrides(n_ui=16))
    assert result.n_ui == 16
    assert result.n_int == 12
    assert result.n_max == 16
    assert result.redis_metrics_databases == 64
    assert result.pg_test_conn_limit == 290
    assert result.pg_max_conn == 323


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
    assert f"--databases {SHARED_REDIS_DATABASES}" in message


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
    "U4I_PG_TEST_CONN_LIMIT",
    "U4I_PG_MAX_CONN",
    "U4I_PG_SHARED_BUFFERS_MB",
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
    assert "U4I_PG_TEST_CONN_LIMIT=230\n" in rendered
    assert "U4I_PG_MAX_CONN=263\n" in rendered
    assert f"U4I_PG_SHARED_BUFFERS_MB={PG_SHARED_BUFFERS_MAX_MB}\n" in rendered
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
        "U4I_PG_TEST_CONN_LIMIT": "230",
        "HOST_UID": "1000",
        "HOST_GID": "1000",
        "U4I_N_UI": "8",
        "U4I_CAPACITY_FINGERPRINT": "aaa",
    }
    new = {
        **old,
        "U4I_PG_TEST_CONN_LIMIT": "110",
        "HOST_GID": "20",
        "U4I_N_UI": "4",
        "U4I_CAPACITY_FINGERPRINT": "bbb",
    }
    assert changed_interlocks(old, new) == ["U4I_PG_TEST_CONN_LIMIT", "HOST_GID"]


def test_interlock_keys_are_the_values_baked_into_containers() -> None:
    assert INTERLOCK_KEYS == (
        "REDIS_METRICS_DATABASES",
        "U4I_PG_TEST_CONN_LIMIT",
        "HOST_UID",
        "HOST_GID",
        "U4I_PG_MAX_CONN",
        "U4I_PG_SHARED_BUFFERS_MB",
    )
    assert set(INTERLOCK_KEYS) <= set(ENV_KEYS)


def test_changed_interlocks_empty_when_equal() -> None:
    values = {"REDIS_METRICS_DATABASES": "32", "U4I_PG_TEST_CONN_LIMIT": "230"}
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


HUB_RECREATE_LINE: str = (
    "hub recreate required: run 'make down' in every spoke, "
    "then 'make hub-down' and 'make hub-up'"
)


def test_generate_reports_recreate_when_interlocks_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    capsys.readouterr()

    assert _run(["generate", "--output", str(env_path)], _probe(ncpu=4)) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        f"capacity regenerated ({env_path})",
        "recreate required: run 'make up [p=…] d=1' "
        "(changed: REDIS_METRICS_DATABASES, U4I_PG_TEST_CONN_LIMIT)",
        f"{HUB_RECREATE_LINE} (changed: U4I_PG_MAX_CONN)",
    ]
    assert read_env(env_path)["U4I_PG_TEST_CONN_LIMIT"] == "110"


@pytest.mark.parametrize(
    ("changed_key", "expected_line"),
    [
        pytest.param(
            "REDIS_METRICS_DATABASES",
            "recreate required: run 'make up [p=…] d=1' "
            "(changed: REDIS_METRICS_DATABASES)",
            id="spoke-redis",
        ),
        # cluster-init re-applies the role's CONNECTION LIMIT on every `make up`: no hub teardown.
        pytest.param(
            "U4I_PG_TEST_CONN_LIMIT",
            "recreate required: run 'make up [p=…] d=1' "
            "(changed: U4I_PG_TEST_CONN_LIMIT)",
            id="spoke-test-conn-limit",
        ),
        pytest.param(
            "U4I_PG_MAX_CONN",
            f"{HUB_RECREATE_LINE} (changed: U4I_PG_MAX_CONN)",
            id="hub-max-conn",
        ),
        pytest.param(
            "U4I_PG_SHARED_BUFFERS_MB",
            f"{HUB_RECREATE_LINE} (changed: U4I_PG_SHARED_BUFFERS_MB)",
            id="hub-shared-buffers",
        ),
    ],
)
def test_generate_names_only_the_tier_an_interlock_lives_in(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    changed_key: str,
    expected_line: str,
) -> None:
    """One recorded interlock drifts; regenerating names only that key's tier."""
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    recorded_value = read_env(env_path)[changed_key]
    env_path.write_text(
        env_path.read_text().replace(
            f"{changed_key}={recorded_value}\n", f"{changed_key}=1{recorded_value}\n"
        )
    )
    capsys.readouterr()

    assert _run(["generate", "--output", str(env_path)]) == 0

    assert capsys.readouterr().out.splitlines() == [
        f"capacity regenerated ({env_path})",
        expected_line,
    ]


def _drift_and_regenerate(
    env_path: Path, changed_key: str, capsys: pytest.CaptureFixture[str]
) -> list[str]:
    """Generate, drift one recorded interlock, regenerate; return the second run's lines."""
    _run(["generate", "--output", str(env_path)])
    recorded_value = read_env(env_path)[changed_key]
    env_path.write_text(
        env_path.read_text().replace(
            f"{changed_key}={recorded_value}\n", f"{changed_key}=1{recorded_value}\n"
        )
    )
    capsys.readouterr()
    assert _run(["generate", "--output", str(env_path)]) == 0
    return capsys.readouterr().out.splitlines()


@pytest.mark.parametrize(
    "changed_key",
    ["U4I_PG_MAX_CONN", "U4I_PG_SHARED_BUFFERS_MB", "U4I_PG_TEST_CONN_LIMIT"],
)
def test_worktree_capacity_file_notes_that_the_hub_reads_the_primary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    changed_key: str,
) -> None:
    """A linked worktree's own file never reaches the hub: note, no recreate guidance."""
    primary_root = tmp_path / "primary"
    monkeypatch.setenv("PRIMARY_ROOT", str(primary_root))
    worktree_docker_dir = tmp_path / "worktree" / "docker"
    worktree_docker_dir.mkdir(parents=True)

    lines = _drift_and_regenerate(
        worktree_docker_dir / ".capacity.generated.env", changed_key, capsys
    )

    assert lines == [
        f"capacity regenerated ({worktree_docker_dir / '.capacity.generated.env'})",
        "note: the hub reads the primary clone's capacity file, so these apply only "
        f"after 'make capacity' in {primary_root} (changed: {changed_key})",
    ]


def test_worktree_capacity_file_keeps_spoke_guidance_for_spoke_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("PRIMARY_ROOT", str(tmp_path / "primary"))
    worktree_docker_dir = tmp_path / "worktree" / "docker"
    worktree_docker_dir.mkdir(parents=True)

    lines = _drift_and_regenerate(
        worktree_docker_dir / ".capacity.generated.env",
        "REDIS_METRICS_DATABASES",
        capsys,
    )

    assert lines[1:] == [
        "recreate required: run 'make up [p=…] d=1' (changed: REDIS_METRICS_DATABASES)"
    ]


@pytest.mark.parametrize(
    ("changed_key", "expected_line"),
    [
        pytest.param(
            "U4I_PG_MAX_CONN",
            f"{HUB_RECREATE_LINE} (changed: U4I_PG_MAX_CONN)",
            id="hub-max-conn",
        ),
        pytest.param(
            "U4I_PG_TEST_CONN_LIMIT",
            "recreate required: run 'make up [p=…] d=1' "
            "(changed: U4I_PG_TEST_CONN_LIMIT)",
            id="test-conn-limit",
        ),
    ],
)
def test_primary_capacity_file_keeps_the_tier_guidance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    changed_key: str,
    expected_line: str,
) -> None:
    primary_docker_dir = tmp_path / "primary" / "docker"
    primary_docker_dir.mkdir(parents=True)
    env_path = primary_docker_dir / ".capacity.generated.env"
    monkeypatch.setenv("PRIMARY_ROOT", str(env_path.parent.parent))

    lines = _drift_and_regenerate(env_path, changed_key, capsys)

    assert lines == [f"capacity regenerated ({env_path})", expected_line]


def test_interlock_tiers_partition_the_interlock_keys() -> None:
    assert set(SPOKE_INTERLOCK_KEYS).isdisjoint(HUB_INTERLOCK_KEYS)
    assert set(SPOKE_INTERLOCK_KEYS) | set(HUB_INTERLOCK_KEYS) == set(INTERLOCK_KEYS)
    assert HUB_INTERLOCK_KEYS == ("U4I_PG_MAX_CONN", "U4I_PG_SHARED_BUFFERS_MB")


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
    env_path.write_text(original_content.replace("U4I_PG_TEST_CONN_LIMIT=230\n", ""))
    assert "U4I_PG_TEST_CONN_LIMIT" not in read_env(env_path)
    capsys.readouterr()

    assert _run(["ensure", "--output", str(env_path)]) == 0

    assert capsys.readouterr().out.startswith(f"capacity regenerated ({env_path})\n")
    assert env_path.read_text() == original_content


def test_ensure_migrates_legacy_test_max_conn_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pre-rename file (U4I_TEST_MAX_CONN, no U4I_PG_*) heals on the next ensure."""
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    current_content = env_path.read_text()
    shared_buffers_line = f"U4I_PG_SHARED_BUFFERS_MB={PG_SHARED_BUFFERS_MAX_MB}\n"
    legacy_content = (
        current_content.replace("U4I_PG_TEST_CONN_LIMIT=", "U4I_TEST_MAX_CONN=")
        .replace("U4I_PG_MAX_CONN=263\n", "")
        .replace(shared_buffers_line, "")
    )
    env_path.write_text(legacy_content)
    capsys.readouterr()

    assert _run(["ensure", "--output", str(env_path)]) == 0

    assert capsys.readouterr().out.splitlines() == [
        f"capacity regenerated ({env_path})",
        "recreate required: run 'make up [p=…] d=1' (changed: U4I_PG_TEST_CONN_LIMIT)",
        f"{HUB_RECREATE_LINE} (changed: U4I_PG_MAX_CONN, U4I_PG_SHARED_BUFFERS_MB)",
    ]
    assert env_path.read_text() == current_content
    assert "U4I_TEST_MAX_CONN" not in read_env(env_path)


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
    assert f"--databases {SHARED_REDIS_DATABASES}" in capsys.readouterr().err
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


def test_generated_file_is_owner_only(tmp_path: Path) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    assert env_path.stat().st_mode & 0o777 == 0o600

    # A rewrite keeps the owner-only mode.
    _run(["generate", "--output", str(env_path)], _probe(ncpu=4))
    assert env_path.stat().st_mode & 0o777 == 0o600


# --- logs-owner-fix ----------------------------------------------------------

LOGS_PROJECT: str = "u4i-cap-test"
WEB_IMAGE_ID: str = "0123456789ab"


def _logs_names(project: str) -> tuple[str, list[str], list[str]]:
    """The volume name, volume lookup and image lookup logs-owner-fix derives from `project`."""
    volume_lookup = [
        "volume",
        "ls",
        "-q",
        "--filter",
        f"label=com.docker.compose.project={project}",
        "--filter",
        "label=com.docker.compose.volume=app_logs",
    ]
    image_lookup = ["image", "ls", "-q", f"{project}-web:latest"]
    return f"{project}_app_logs", volume_lookup, image_lookup


LOGS_VOLUME, VOLUME_LOOKUP, IMAGE_LOOKUP = _logs_names(LOGS_PROJECT)


def _root_run(volume: str = LOGS_VOLUME) -> list[str]:
    return [
        "run",
        "--rm",
        "--user",
        "root",
        "-v",
        f"{volume}:/app/volume",
        WEB_IMAGE_ID,
    ]


ROOT_RUN: list[str] = _root_run()
STAT_CALL: list[str] = [*ROOT_RUN, "stat", "-c", "%u:%g", "/app/volume/logs"]


@pytest.fixture
def logs_project(monkeypatch: pytest.MonkeyPatch) -> None:
    """logs-owner-fix reads the spoke's compose project from U4I_PROJECT (make exports it)."""
    monkeypatch.setenv("U4I_PROJECT", LOGS_PROJECT)


def _repair_call(owner: str) -> list[str]:
    return [
        *ROOT_RUN,
        "sh",
        "-c",
        f"chown -R {owner} /app/volume/logs && chmod 775 /app/volume/logs",
    ]


class _FakeDocker:
    """Scripted docker runner: answers each lookup and records every call."""

    def __init__(
        self,
        volume: str = LOGS_VOLUME,
        image: str = WEB_IMAGE_ID,
        owner: str | None = "1000:1000",
        lookup_returncode: int = 0,
        repair_returncode: int = 0,
        project: str = LOGS_PROJECT,
    ) -> None:
        self.volume = volume
        self.image = image
        self.owner = owner
        self.lookup_returncode = lookup_returncode
        self.repair_returncode = repair_returncode
        _, self.volume_lookup, self.image_lookup = _logs_names(project)
        self.stat_call = [
            *_root_run(volume),
            "stat",
            "-c",
            "%u:%g",
            "/app/volume/logs",
        ]
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if args in (self.volume_lookup, self.image_lookup):
            if self.lookup_returncode != 0:
                return _completed(self.lookup_returncode, stderr="daemon down\n")
            found = self.volume if args == self.volume_lookup else self.image
            return _completed(0, stdout=f"{found}\n" if found else "")
        if args == self.stat_call:
            if self.owner is None:
                return _completed(1, stderr="stat: cannot stat '/app/volume/logs'\n")
            return _completed(0, stdout=f"{self.owner}\n")
        if self.repair_returncode != 0:
            return _completed(self.repair_returncode, stderr="chown: denied\n")
        return _completed(0)


def _capacity_ids(
    tmp_path: Path, host_uid: str = "1000", host_gid: str = "1000"
) -> Path:
    env_path = tmp_path / "capacity.env"
    env_path.write_text(f"HOST_UID={host_uid}\nHOST_GID={host_gid}\n")
    return env_path


def _no_probe() -> Probe:
    raise AssertionError("logs-owner-fix must not probe the host")


def _fix(env_path: Path, docker: _FakeDocker) -> int:
    return main(["logs-owner-fix", "--output", str(env_path)], _no_probe, docker)


@pytest.mark.usefixtures("logs_project")
def test_logs_owner_fix_matching_owner_is_quiet_no_op(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docker = _FakeDocker(owner="1000:1000")

    assert _fix(_capacity_ids(tmp_path), docker) == 0

    assert docker.calls == [VOLUME_LOOKUP, IMAGE_LOOKUP, STAT_CALL]
    # Literal production names, independent of the _logs_names helper that builds the fakes.
    assert "label=com.docker.compose.project=u4i-cap-test" in docker.calls[0]
    assert docker.calls[1] == ["image", "ls", "-q", "u4i-cap-test-web:latest"]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.usefixtures("logs_project")
def test_logs_owner_fix_repairs_mismatched_owner(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docker = _FakeDocker(owner="1001:1001")

    assert _fix(_capacity_ids(tmp_path), docker) == 0

    assert docker.calls == [
        VOLUME_LOOKUP,
        IMAGE_LOOKUP,
        STAT_CALL,
        _repair_call("1000:1000"),
    ]
    assert capsys.readouterr().out == (
        "repairing app_logs ownership (was 1001:1001, now 1000:1000)\n"
    )


@pytest.mark.parametrize(
    ("volume", "image"), [("", WEB_IMAGE_ID), (LOGS_VOLUME, ""), ("", "")]
)
@pytest.mark.usefixtures("logs_project")
def test_logs_owner_fix_skips_without_volume_or_image(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], volume: str, image: str
) -> None:
    """A fresh machine skips before reading the capacity file (it may not exist)."""
    docker = _FakeDocker(volume=volume, image=image)

    assert _fix(tmp_path / "missing.env", docker) == 0

    assert docker.calls == [VOLUME_LOOKUP, IMAGE_LOOKUP]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.usefixtures("logs_project")
def test_logs_owner_fix_skips_when_lookups_fail_and_forwards_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docker = _FakeDocker(lookup_returncode=1)

    assert _fix(_capacity_ids(tmp_path), docker) == 0

    assert docker.calls == [VOLUME_LOOKUP, IMAGE_LOOKUP]
    assert capsys.readouterr().err == "daemon down\ndaemon down\n"


@pytest.mark.usefixtures("logs_project")
def test_logs_owner_fix_skips_quietly_without_log_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docker = _FakeDocker(owner=None)

    assert _fix(_capacity_ids(tmp_path), docker) == 0

    assert docker.calls == [VOLUME_LOOKUP, IMAGE_LOOKUP, STAT_CALL]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize(
    ("host_uid", "host_gid", "expected_owner"),
    [
        ("0", "0", "1001:1001"),
        ("0", "1000", "1001:1000"),
        ("1000", "0", "1000:1001"),
    ],
)
@pytest.mark.usefixtures("logs_project")
def test_logs_owner_fix_maps_root_ids_to_1001(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    host_uid: str,
    host_gid: str,
    expected_owner: str,
) -> None:
    docker = _FakeDocker(owner="1000:1000")

    assert _fix(_capacity_ids(tmp_path, host_uid, host_gid), docker) == 0

    assert docker.calls[-1] == _repair_call(expected_owner)
    assert f"now {expected_owner})" in capsys.readouterr().out


@pytest.mark.usefixtures("logs_project")
def test_logs_owner_fix_root_host_already_1001_is_no_op(tmp_path: Path) -> None:
    docker = _FakeDocker(owner="1001:1001")
    assert _fix(_capacity_ids(tmp_path, "0", "0"), docker) == 0
    assert docker.calls == [VOLUME_LOOKUP, IMAGE_LOOKUP, STAT_CALL]


@pytest.mark.parametrize(
    ("host_uid", "host_gid"),
    [("", "1000"), ("1000", ""), ("abc", "1000"), ("1000", "-1"), ("1.5", "1000")],
)
@pytest.mark.usefixtures("logs_project")
def test_logs_owner_fix_non_numeric_ids_exit_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], host_uid: str, host_gid: str
) -> None:
    env_path = _capacity_ids(tmp_path, host_uid, host_gid)
    docker = _FakeDocker()

    assert _fix(env_path, docker) != 0

    assert docker.calls == [VOLUME_LOOKUP, IMAGE_LOOKUP]
    assert capsys.readouterr().err == (
        f"make capacity: HOST_UID/HOST_GID invalid in {env_path} — run 'make capacity'\n"
    )


@pytest.mark.usefixtures("logs_project")
def test_logs_owner_fix_missing_id_keys_exit_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    env_path.write_text("U4I_N_UI=8\n")

    assert _fix(env_path, _FakeDocker()) != 0
    assert "HOST_UID/HOST_GID invalid" in capsys.readouterr().err


@pytest.mark.usefixtures("logs_project")
def test_logs_owner_fix_failed_repair_exits_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docker = _FakeDocker(owner="1001:1001", repair_returncode=1)

    assert _fix(_capacity_ids(tmp_path), docker) != 0

    captured = capsys.readouterr()
    assert captured.out.startswith("repairing app_logs ownership")
    assert captured.err == "make capacity: docker failed — chown: denied\n"


@pytest.mark.usefixtures("logs_project")
def test_logs_owner_fix_docker_launch_failure_exits_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def unlaunchable_docker(args: list[str]) -> subprocess.CompletedProcess[str]:
        raise DockerRunError("No such file or directory: 'docker'")

    exit_code = main(
        ["logs-owner-fix", "--output", str(_capacity_ids(tmp_path))],
        _no_probe,
        unlaunchable_docker,
    )

    assert exit_code != 0
    assert capsys.readouterr().err == (
        "make capacity: docker failed — No such file or directory: 'docker'\n"
    )


def test_logs_owner_fix_follows_another_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("U4I_PROJECT", "u4i-wt-a")
    other_volume, other_volume_lookup, other_image_lookup = _logs_names("u4i-wt-a")
    docker = _FakeDocker(volume=other_volume, owner="1000:1000", project="u4i-wt-a")

    assert _fix(_capacity_ids(tmp_path), docker) == 0

    assert docker.calls == [other_volume_lookup, other_image_lookup, docker.stat_call]


@pytest.mark.parametrize("project_value", [None, ""], ids=["unset", "empty"])
def test_logs_owner_fix_requires_u4i_project(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    project_value: str | None,
) -> None:
    """Never a silent skip: without the project it would miss the spoke's volume."""
    monkeypatch.delenv("U4I_PROJECT", raising=False)
    if project_value is not None:
        monkeypatch.setenv("U4I_PROJECT", project_value)
    docker = _FakeDocker()

    assert _fix(_capacity_ids(tmp_path), docker) != 0

    assert docker.calls == []
    err = capsys.readouterr().err
    assert "U4I_PROJECT" in err
    assert "through make" in err


def test_run_docker_prefixes_docker_and_sets_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        recorded["command"] = command
        recorded.update(kwargs)
        return _completed(0, stdout="ok\n")

    monkeypatch.setattr(capacity.subprocess, "run", fake_run)

    assert run_docker(IMAGE_LOOKUP).stdout == "ok\n"
    assert recorded["command"] == ["docker", *IMAGE_LOOKUP]
    assert recorded["timeout"] == DOCKER_RUN_TIMEOUT_SECONDS
    assert recorded["capture_output"] is True


@pytest.mark.parametrize(
    ("raised", "expected_fragment"),
    [
        (FileNotFoundError("No such file or directory: 'docker'"), "docker"),
        (
            subprocess.TimeoutExpired(cmd="docker", timeout=DOCKER_RUN_TIMEOUT_SECONDS),
            f"docker image timed out after {DOCKER_RUN_TIMEOUT_SECONDS}s",
        ),
    ],
)
def test_run_docker_launch_failures_raise_docker_run_error(
    monkeypatch: pytest.MonkeyPatch, raised: Exception, expected_fragment: str
) -> None:
    def failing_run(*args: object, **kwargs: object) -> None:
        raise raised

    monkeypatch.setattr(capacity.subprocess, "run", failing_run)
    with pytest.raises(DockerRunError, match=expected_fragment):
        run_docker(IMAGE_LOOKUP)
