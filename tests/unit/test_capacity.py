"""Unit tests for the host-side capacity derivation (`scripts/capacity.py`).

Every probe value is fabricated — no Docker, no `/proc` — so these run
identically on a laptop, inside the web container, and on a CI runner.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts import capacity
from scripts.capacity import (
    BASE_GB,
    CONN_BASE,
    CONN_PER_WORKER,
    DEFAULT_MEM_FRACTION,
    DEFAULT_MEM_SAFETY,
    DEV_CONN_BUDGET,
    DOCKER_INFO_TIMEOUT_SECONDS,
    DOCKER_RUN_TIMEOUT_SECONDS,
    ENV_KEYS,
    HARD_N_CEILING,
    HUB_IDLE_GB,
    HUB_INTERLOCK_KEYS,
    INTERLOCK_KEYS,
    LEASE_CONCURRENT_RUNS,
    LIVE_MEMORY_DOCKER_TIMEOUT_SECONDS,
    LIVE_SOURCE_HOST,
    LIVE_SOURCE_NONE,
    LIVE_SOURCE_VM,
    METRICS_REDIS_RESERVED_DBS,
    PG_SHARED_BUFFERS_MAX_MB,
    PG_SHARED_BUFFERS_MIN_MB,
    SESSION_REDIS_RESERVED_DBS,
    SHARED_REDIS_DATABASES,
    SPOKE_IDLE_GB,
    SPOKE_INTERLOCK_KEYS,
    SUPERUSER_RESERVED,
    WORKER_GB,
    AdmissionResult,
    Capacity,
    DockerInfoError,
    DockerRunError,
    InfeasibleCapacity,
    LiveMemory,
    Overrides,
    Probe,
    _live_memory,
    _memory_guard,
    _run_docker_short,
    _usable_gb,
    admission_decision,
    changed_interlocks,
    clamp,
    derive,
    fingerprint,
    hub_vm_meminfo,
    live_usable_gb,
    main,
    parse_cgroup_max,
    parse_docker_info,
    parse_meminfo,
    probe,
    read_env,
    read_live_available,
    render_env,
    round_up_pow2,
    run_docker,
    run_docker_info,
    workers_that_fit,
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
    assert low.pg_shared_buffers_mb == high.pg_shared_buffers_mb


def test_derive_ignores_mem_available_for_every_file_value() -> None:
    """Every value written to the file comes from stable inputs: a memory-bound
    MemAvailable reading changes none of them (live memory gates each start)."""
    memory_bound = _derive(
        _probe(
            ncpu=12,
            mem_total_bytes=REFERENCE_HOST_MEM_TOTAL_BYTES,
            mem_available_bytes=4 * GIB,
        )
    )
    unknown = _derive(_probe(ncpu=12, mem_total_bytes=REFERENCE_HOST_MEM_TOTAL_BYTES))
    for field_name in (
        "n_ui",
        "n_int",
        "n_max",
        "redis_metrics_databases",
        "pg_test_conn_limit",
        "pg_max_conn",
        "usable_gb",
        "spoke_max",
    ):
        assert getattr(memory_bound, field_name) == getattr(unknown, field_name)


def test_derive_pg_shared_buffers_honors_cgroup_limit() -> None:
    # usable = min(64 * 0.7, 6 * 0.9) = 5.4 GiB = 5529 MiB -> 5529 // 64 = 86
    result = _derive(_probe(mem_total_bytes=64 * GIB, cgroup_max_bytes=6 * GIB))
    assert result.pg_shared_buffers_mb == 86


def test_derive_interlocks_use_max_of_ui_and_int() -> None:
    """n_int dominates n_ui at every core count, so interlocks follow n_int."""
    result = _derive(_probe(ncpu=3))
    assert result.n_max == max(result.n_ui, result.n_int) == 3
    assert result.pg_test_conn_limit == 3 * CONN_PER_WORKER + CONN_BASE


# The reference dev host's `docker info` MemTotal: usable_gb = 9.6 at the default fraction.
REFERENCE_HOST_MEM_TOTAL_BYTES: int = 14_725_602_158


def _rendered_values(
    probe_value: Probe, overrides: Overrides | None = None
) -> dict[str, str]:
    return capacity._parse_env(_render(overrides=overrides, probe_value=probe_value))


def test_spoke_max_on_reference_host_reserves_hub_and_one_minimum_run() -> None:
    """(9.6 - 0.6 hub - (2.0 base + 1 × 0.5 worker)) / 0.25 per idle spoke = 26."""
    reference_probe = _probe(ncpu=12, mem_total_bytes=REFERENCE_HOST_MEM_TOTAL_BYTES)
    result = _derive(reference_probe)
    assert f"{result.usable_gb:.1f}" == "9.6"
    assert (result.n_ui, result.n_int, result.n_max) == (8, 12, 12)
    assert result.binding_constraint == "cpu"
    assert result.spoke_max == 26
    assert result.spoke_max_clamped is False
    assert _rendered_values(reference_probe)["U4I_SPOKE_MAX"] == "26"


def test_spoke_max_clamps_to_one_on_a_memory_starved_host() -> None:
    """4 GiB total: usable 2.8 GB, and (2.8 - 0.6 - 2.5) / 0.25 < 1 → 1 (clamped)."""
    starved_probe = _probe(ncpu=12, mem_total_bytes=4 * GIB)
    result = _derive(starved_probe)
    assert result.usable_gb == pytest.approx(2.8)
    assert (result.usable_gb - HUB_IDLE_GB - BASE_GB - WORKER_GB) / SPOKE_IDLE_GB < 1
    assert result.spoke_max == 1
    assert result.spoke_max_clamped is True
    rendered = render_env(
        result, starved_probe, Overrides(), fingerprint(starved_probe, Overrides())
    )
    assert "U4I_SPOKE_MAX=1\n" in rendered
    decision_line = next(
        line for line in rendered.splitlines() if line.startswith("# decision: ")
    )
    assert decision_line.endswith(" spoke_max=1 (clamped)")


def test_usable_mb_matches_the_decision_usable_gb() -> None:
    reference_probe = _probe(ncpu=12, mem_total_bytes=REFERENCE_HOST_MEM_TOTAL_BYTES)
    result = _derive(reference_probe)
    values = _rendered_values(reference_probe)
    assert values["U4I_USABLE_MB"] == str(int(result.usable_gb * 1024)) == "9830"
    assert values["U4I_HUB_IDLE_MB"] == str(int(HUB_IDLE_GB * 1024))
    assert values["U4I_SPOKE_IDLE_MB"] == str(int(SPOKE_IDLE_GB * 1024))


def test_spoke_max_does_not_move_with_an_n_override() -> None:
    """The informational ceiling reserves one minimum test run, not n_max workers:
    (179.2 - 0.6 - 2.5) / 0.25 = 704 whatever U4I_N_UI is."""
    default_result = _derive(_probe())
    overridden_result = _derive(_probe(), Overrides(n_ui=16))
    assert overridden_result.n_max == 16 > default_result.n_max
    assert default_result.spoke_max == 704
    assert overridden_result.spoke_max == 704
    assert _rendered_values(_probe(), Overrides(n_ui=16))["U4I_SPOKE_MAX"] == "704"


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


def test_memory_guard_ignores_low_available_memory() -> None:
    """MemAvailable is live, so it never sizes the file: usable = 32 * 0.7 = 22.4
    GiB, not min(22.4, 5 * 0.9); the live gate in the token runner handles it."""
    result = _derive(
        _probe(ncpu=12, mem_total_bytes=32 * GIB, mem_available_bytes=5 * GIB)
    )
    assert result.usable_gb == pytest.approx(22.4)
    assert result.n_ui == 8
    assert result.n_int == 12
    assert result.binding_constraint == "cpu"


def test_memory_guard_uses_cgroup_even_with_ample_available_memory() -> None:
    # cgroup 4 GiB (stable) -> usable = min(22.4, 3.6) = 3.6 -> n = 3
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


@pytest.mark.parametrize(
    ("mem_total_gib", "fit"),
    [
        # usable = 4 * 0.7 = 2.8 GiB → floor((2.8 - 2.0) / 0.5) = 1 worker.
        (4, "at most 1 worker fits"),
        # usable = 8 * 0.7 = 5.6 GiB → floor((5.6 - 2.0) / 0.5) = 7 workers.
        (8, "at most 7 workers fit"),
    ],
)
def test_override_above_memory_guard_counts_workers_in_words(
    mem_total_gib: int, fit: str
) -> None:
    with pytest.raises(InfeasibleCapacity) as excinfo:
        _derive(
            _probe(ncpu=12, mem_total_bytes=mem_total_gib * GIB), Overrides(n_ui=20)
        )
    assert f"({fit});" in str(excinfo.value)


@pytest.mark.parametrize(("count", "phrase"), [(0, "0 workers"), (1, "1 worker")])
def test_workers_phrase_is_singular_only_for_one(count: int, phrase: str) -> None:
    assert capacity.workers_phrase(count) == phrase


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
    "U4I_USABLE_MB",
    "U4I_HUB_IDLE_MB",
    "U4I_SPOKE_IDLE_MB",
    "U4I_BASE_MB",
    "U4I_WORKER_MB",
    "U4I_SPOKE_MAX",
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
    assert (
        "# decision: n_ui=8 n_int=12 binding=cpu usable_gb=179.2 spoke_max=704" in lines
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# decision: n_ui=8 n_int=12 spoke_max=4\n", "4"),
        ("# decision: n_ui=8 n_int=12 spoke_max=1 (clamped)\n", "1"),
        ("U4I_SPOKE_MAX=4\n", None),
    ],
    ids=["plain", "clamped", "no_decision_line"],
)
def test_decision_spoke_max_parses_the_token(text: str, expected: str | None) -> None:
    assert capacity._decision_spoke_max(text) == expected


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
    assert "U4I_BASE_MB=2048\n" in rendered
    assert "U4I_WORKER_MB=512\n" in rendered
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


def test_generate_is_unchanged_when_only_mem_available_moves(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing in the file is sized from MemAvailable, so a MemAvailable-only
    difference renders identical text and leaves the file untouched."""
    env_path = tmp_path / "capacity.env"
    first_probe = _probe(mem_available_bytes=100 * GIB)
    second_probe = _probe(mem_available_bytes=120 * GIB)
    _run(["generate", "--output", str(env_path)], first_probe)
    original_content = env_path.read_text()
    _age(env_path)
    capsys.readouterr()

    assert _run(["generate", "--output", str(env_path)], second_probe) == 0

    assert _render(probe_value=second_probe) == original_content
    assert capsys.readouterr().out == f"capacity unchanged ({env_path})\n"
    assert env_path.read_text() == original_content
    assert env_path.stat().st_mtime_ns == OLD_MTIME_NS


def test_generate_restores_a_hand_edited_spoke_max(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A U4I_SPOKE_MAX that disagrees with the file's own `# decision:` line is a
    hand edit, not jitter, so `make capacity` restores the derived value."""
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    derived_line = f"U4I_SPOKE_MAX={_derive(_probe()).spoke_max}\n"
    original_content = env_path.read_text()
    assert derived_line in original_content
    env_path.write_text(original_content.replace(derived_line, "U4I_SPOKE_MAX=1\n"))
    capsys.readouterr()

    assert _run(["generate", "--output", str(env_path)]) == 0

    assert capsys.readouterr().out == f"capacity regenerated ({env_path})\n"
    assert env_path.read_text() == original_content


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

    lines = _drift_and_regenerate(env_path, changed_key, capsys)

    assert lines == [f"capacity regenerated ({env_path})", expected_line]


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


def test_ensure_migrates_file_missing_admission_keys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pre-admission file (no idle-cost/spoke-ceiling keys) heals on the next ensure,
    with no recreate message: no container reads the new keys."""
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    current_content = env_path.read_text()
    admission_keys = (
        "U4I_USABLE_MB",
        "U4I_HUB_IDLE_MB",
        "U4I_SPOKE_IDLE_MB",
        "U4I_SPOKE_MAX",
    )
    legacy_content = "".join(
        line
        for line in current_content.splitlines(keepends=True)
        if not line.startswith(tuple(f"{key}=" for key in admission_keys))
    )
    env_path.write_text(legacy_content)
    assert not set(admission_keys) & set(read_env(env_path))
    capsys.readouterr()

    assert _run(["ensure", "--output", str(env_path)]) == 0

    assert capsys.readouterr().out.splitlines() == [
        f"capacity regenerated ({env_path})"
    ]
    assert env_path.read_text() == current_content


def test_ensure_migrates_file_missing_memory_model_keys(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file from before the per-run memory model (no U4I_BASE_MB/U4I_WORKER_MB)
    heals on the next ensure, with no recreate message: they are not interlocks."""
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    current_content = env_path.read_text()
    memory_model_keys = ("U4I_BASE_MB", "U4I_WORKER_MB")
    legacy_content = "".join(
        line
        for line in current_content.splitlines(keepends=True)
        if not line.startswith(tuple(f"{key}=" for key in memory_model_keys))
    )
    env_path.write_text(legacy_content)
    assert not set(memory_model_keys) & set(read_env(env_path))
    capsys.readouterr()

    assert _run(["ensure", "--output", str(env_path)]) == 0

    assert capsys.readouterr().out.splitlines() == [
        f"capacity regenerated ({env_path})"
    ]
    assert env_path.read_text() == current_content


def test_ensure_restores_a_hand_edited_spoke_max(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A U4I_SPOKE_MAX that disagrees with its `# decision:` token is a hand edit:
    `ensure` regenerates it even though the fingerprint still matches."""
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    derived_line = f"U4I_SPOKE_MAX={_derive(_probe()).spoke_max}\n"
    original_content = env_path.read_text()
    assert derived_line in original_content
    env_path.write_text(original_content.replace(derived_line, "U4I_SPOKE_MAX=1\n"))
    capsys.readouterr()

    assert _run(["ensure", "--output", str(env_path)]) == 0

    assert capsys.readouterr().out.splitlines() == [
        f"capacity regenerated ({env_path})"
    ]
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


def test_ensure_infeasible_override_with_matching_fingerprint_exits_untouched(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fingerprint match still re-derives (the consistency check), so an
    infeasible recorded override fails loudly there and leaves the file as is."""
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    recorded = read_env(env_path)
    infeasible_overrides = Overrides(n_ui=HARD_N_CEILING + 1)
    edited_content = (
        env_path.read_text()
        .replace("U4I_OVERRIDE_N_UI=\n", f"U4I_OVERRIDE_N_UI={HARD_N_CEILING + 1}\n")
        .replace(
            recorded["U4I_CAPACITY_FINGERPRINT"],
            fingerprint(_probe(), infeasible_overrides),
        )
    )
    env_path.write_text(edited_content)
    _age(env_path)
    capsys.readouterr()

    assert _run(["ensure", "--output", str(env_path)]) != 0

    assert "U4I_N_UI" in capsys.readouterr().err
    assert env_path.read_text() == edited_content
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
    # Without --hub-project, show reads the host file: keep it off the real /proc.
    monkeypatch.setattr(capacity, "DEFAULT_MEMINFO_PATH", tmp_path / "no-meminfo")
    monkeypatch.setattr(capacity, "DEFAULT_CGROUP_PATH", tmp_path / "no-cgroup")
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
    raise AssertionError("logs-owner-fix and admit must not probe the host")


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


# --- live memory -------------------------------------------------------------

LIVE_HUB: str = "u4i-hub-1000"
HUB_DB_ID: str = "f00dfeedbeef"
MEMINFO_AVAILABLE_BYTES: int = 9437184 * 1024
HUB_DB_PS_ARGS: list[str] = [
    "ps",
    "-q",
    "--filter",
    f"label=com.docker.compose.project={LIVE_HUB}",
    "--filter",
    "label=com.docker.compose.service=db",
    "--filter",
    "status=running",
]
HUB_DB_EXEC_ARGS: list[str] = ["exec", HUB_DB_ID, "cat", "/proc/meminfo"]


def _vm_never_called() -> str | None:
    raise AssertionError("the VM reader must not run when the host file is readable")


def _meminfo_file(tmp_path: Path, text: str = MEMINFO_TEXT) -> Path:
    meminfo_path = tmp_path / "meminfo"
    meminfo_path.write_text(text)
    return meminfo_path


class _ScriptedDocker:
    """Docker runner answering each call from a script (a result or an exception)."""

    def __init__(
        self, *responses: subprocess.CompletedProcess[str] | Exception
    ) -> None:
        self.responses = list(responses)
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_read_live_available_reads_host_meminfo(tmp_path: Path) -> None:
    result = read_live_available(
        _meminfo_file(tmp_path), tmp_path / "no-cgroup", _vm_never_called
    )
    assert result == LiveMemory(MEMINFO_AVAILABLE_BYTES, LIVE_SOURCE_HOST)


@pytest.mark.parametrize(
    ("cgroup_text", "expected_bytes"),
    [
        ("4294967296\n", 4 * GIB),
        (f"{20 * GIB}\n", MEMINFO_AVAILABLE_BYTES),
        ("max\n", MEMINFO_AVAILABLE_BYTES),
    ],
    ids=["lower-cgroup-wins", "higher-cgroup-ignored", "unlimited-cgroup"],
)
def test_read_live_available_caps_host_reading_at_the_cgroup_limit(
    tmp_path: Path, cgroup_text: str, expected_bytes: int
) -> None:
    cgroup_path = tmp_path / "memory.max"
    cgroup_path.write_text(cgroup_text)

    result = read_live_available(_meminfo_file(tmp_path), cgroup_path, _vm_never_called)

    assert result == LiveMemory(expected_bytes, LIVE_SOURCE_HOST)


def test_read_live_available_falls_back_to_the_vm(tmp_path: Path) -> None:
    result = read_live_available(
        tmp_path / "no-meminfo", tmp_path / "no-cgroup", lambda: MEMINFO_TEXT
    )
    assert result == LiveMemory(MEMINFO_AVAILABLE_BYTES, LIVE_SOURCE_VM)


def test_read_live_available_gives_none_when_nothing_is_readable(
    tmp_path: Path,
) -> None:
    result = read_live_available(
        tmp_path / "no-meminfo", tmp_path / "no-cgroup", lambda: None
    )
    assert result == LiveMemory(None, LIVE_SOURCE_NONE)


@pytest.mark.parametrize(
    "bad_meminfo",
    ["MemAvailable: abc kB\n", "MemTotal: 16384000 kB\n", ""],
    ids=["malformed-value", "missing-key", "empty-file"],
)
def test_read_live_available_malformed_host_reading_falls_through_to_the_vm(
    tmp_path: Path, bad_meminfo: str
) -> None:
    result = read_live_available(
        _meminfo_file(tmp_path, bad_meminfo),
        tmp_path / "no-cgroup",
        lambda: MEMINFO_TEXT,
    )
    assert result == LiveMemory(MEMINFO_AVAILABLE_BYTES, LIVE_SOURCE_VM)


def test_read_live_available_undecodable_host_file_falls_through_to_the_vm(
    tmp_path: Path,
) -> None:
    meminfo_path = tmp_path / "meminfo"
    meminfo_path.write_bytes(b"MemAvailable: \xff\xfe kB\n")

    result = read_live_available(
        meminfo_path, tmp_path / "no-cgroup", lambda: MEMINFO_TEXT
    )

    assert result == LiveMemory(MEMINFO_AVAILABLE_BYTES, LIVE_SOURCE_VM)


def test_read_live_available_malformed_vm_reading_gives_none(tmp_path: Path) -> None:
    result = read_live_available(
        tmp_path / "no-meminfo",
        tmp_path / "no-cgroup",
        lambda: "MemAvailable: abc kB\n",
    )
    assert result == LiveMemory(None, LIVE_SOURCE_NONE)


def test_hub_vm_meminfo_reads_the_hub_db_container() -> None:
    docker = _ScriptedDocker(
        _completed(0, stdout=f"{HUB_DB_ID}\n"), _completed(0, stdout=MEMINFO_TEXT)
    )

    assert hub_vm_meminfo(LIVE_HUB, docker) == MEMINFO_TEXT
    assert docker.calls == [HUB_DB_PS_ARGS, HUB_DB_EXEC_ARGS]


def test_hub_vm_meminfo_without_a_running_hub_db_gives_none() -> None:
    docker = _ScriptedDocker(_completed(0, stdout="\n"))

    assert hub_vm_meminfo(LIVE_HUB, docker) is None
    assert docker.calls == [HUB_DB_PS_ARGS]


@pytest.mark.parametrize(
    "responses",
    [
        (_completed(1, stderr="daemon down\n"),),
        (DockerRunError("docker ps timed out after 10s"),),
        (FileNotFoundError("No such file or directory: 'docker'"),),
        (_completed(0, stdout=f"{HUB_DB_ID}\n"), _completed(1, stderr="gone\n")),
        (
            _completed(0, stdout=f"{HUB_DB_ID}\n"),
            DockerRunError("docker exec timed out after 10s"),
        ),
        (
            _completed(0, stdout=f"{HUB_DB_ID}\n"),
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
        ),
    ],
    ids=[
        "ps-exits-non-zero",
        "ps-raises",
        "ps-launch-fails",
        "exec-exits-non-zero",
        "exec-raises",
        "exec-output-undecodable",
    ],
)
def test_hub_vm_meminfo_never_raises_on_docker_failure(
    responses: tuple[subprocess.CompletedProcess[str] | Exception, ...],
) -> None:
    assert hub_vm_meminfo(LIVE_HUB, _ScriptedDocker(*responses)) is None


def test_run_docker_short_uses_the_live_memory_timeout(
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

    assert _run_docker_short(HUB_DB_PS_ARGS).stdout == "ok\n"
    assert recorded["command"] == ["docker", *HUB_DB_PS_ARGS]
    assert recorded["timeout"] == LIVE_MEMORY_DOCKER_TIMEOUT_SECONDS
    assert LIVE_MEMORY_DOCKER_TIMEOUT_SECONDS < DOCKER_RUN_TIMEOUT_SECONDS


@pytest.mark.parametrize(
    ("raised", "expected_fragment"),
    [
        (FileNotFoundError("No such file or directory: 'docker'"), "docker"),
        (
            subprocess.TimeoutExpired(
                cmd="docker", timeout=LIVE_MEMORY_DOCKER_TIMEOUT_SECONDS
            ),
            f"docker ps timed out after {LIVE_MEMORY_DOCKER_TIMEOUT_SECONDS}s",
        ),
    ],
)
def test_run_docker_short_launch_failures_raise_docker_run_error(
    monkeypatch: pytest.MonkeyPatch, raised: Exception, expected_fragment: str
) -> None:
    def failing_run(*args: object, **kwargs: object) -> None:
        raise raised

    monkeypatch.setattr(capacity.subprocess, "run", failing_run)
    with pytest.raises(DockerRunError, match=expected_fragment):
        _run_docker_short(HUB_DB_PS_ARGS)


def test_live_usable_gb_applies_the_safety_margin() -> None:
    assert live_usable_gb(LiveMemory(10 * GIB, LIVE_SOURCE_HOST)) == pytest.approx(
        10 * DEFAULT_MEM_SAFETY
    )
    assert live_usable_gb(LiveMemory(None, LIVE_SOURCE_NONE)) is None


@pytest.mark.parametrize(
    ("usable_gb", "expected_workers"),
    [
        (3.6, 3),
        (4.0, 4),
        # Float noise a hair under an exact fit: rounding before the floor keeps
        # it at 3 workers rather than 2.
        (BASE_GB + 3 * WORKER_GB - 1e-12, 3),
        (2.2, 0),
        (1.0, 0),
    ],
)
def test_workers_that_fit_rounds_before_flooring_and_can_be_zero(
    usable_gb: float, expected_workers: int
) -> None:
    assert workers_that_fit(usable_gb, BASE_GB, WORKER_GB) == expected_workers


def _show_with_live(
    env_path: Path, live: LiveMemory, hub_project: str | None
) -> list[str]:
    """Run `show` with an injected live reader; return the hubs it was asked for."""
    asked: list[str] = []

    def fake_live_memory(hub: str) -> LiveMemory:
        asked.append(hub)
        return live

    argv = ["show", "--output", str(env_path)]
    if hub_project is not None:
        argv += ["--hub-project", hub_project]
    assert main(argv, _no_probe, _ScriptedDocker(), fake_live_memory) == 0
    return asked


def test_show_prints_the_live_line_from_the_hub_reader(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    capsys.readouterr()

    asked = _show_with_live(
        env_path,
        LiveMemory(int(4.0 / DEFAULT_MEM_SAFETY * GIB), LIVE_SOURCE_VM),
        LIVE_HUB,
    )

    assert asked == [LIVE_HUB]
    out_lines = capsys.readouterr().out.splitlines()
    assert out_lines[-1] == "live: 4.0 GB usable now (vm) — 4 workers fit"


def test_show_live_line_is_singular_for_one_worker(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    capsys.readouterr()

    # floor((2.5 − 2.0) / 0.5) = 1 worker.
    _show_with_live(
        env_path,
        LiveMemory(int(2.5 / DEFAULT_MEM_SAFETY * GIB), LIVE_SOURCE_VM),
        LIVE_HUB,
    )

    out_lines = capsys.readouterr().out.splitlines()
    assert out_lines[-1] == "live: 2.5 GB usable now (vm) — 1 worker fits"


def test_show_prints_unavailable_when_live_memory_cannot_be_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    capsys.readouterr()

    _show_with_live(env_path, LiveMemory(None, LIVE_SOURCE_NONE), LIVE_HUB)

    out_lines = capsys.readouterr().out.splitlines()
    assert out_lines[-1] == "live: unavailable — static capacity applies"


def test_show_without_hub_project_reads_only_the_host_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    capsys.readouterr()
    monkeypatch.setattr(capacity, "DEFAULT_MEMINFO_PATH", _meminfo_file(tmp_path))
    monkeypatch.setattr(capacity, "DEFAULT_CGROUP_PATH", tmp_path / "no-cgroup")

    asked = _show_with_live(env_path, LiveMemory(None, LIVE_SOURCE_NONE), None)

    assert asked == []
    # 9437184 kB × 0.9 = 8.1 GB usable → floor((8.1 − 2.0) / 0.5) = 12 workers.
    out_lines = capsys.readouterr().out.splitlines()
    assert out_lines[-1] == "live: 8.1 GB usable now (host) — 12 workers fit"


def test_show_without_hub_project_never_tries_the_vm(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / "capacity.env"
    _run(["generate", "--output", str(env_path)])
    capsys.readouterr()
    monkeypatch.setattr(capacity, "DEFAULT_MEMINFO_PATH", tmp_path / "no-meminfo")
    monkeypatch.setattr(capacity, "DEFAULT_CGROUP_PATH", tmp_path / "no-cgroup")
    docker = _ScriptedDocker()

    assert main(["show", "--output", str(env_path)], _no_probe, docker) == 0

    assert docker.calls == []
    out_lines = capsys.readouterr().out.splitlines()
    assert out_lines[-1] == "live: unavailable — static capacity applies"


def test_default_live_memory_reads_the_vm_with_the_short_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded: list[tuple[list[str], object]] = []

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        recorded.append((command, kwargs["timeout"]))
        if command[1] == "ps":
            return _completed(0, stdout=f"{HUB_DB_ID}\n")
        return _completed(0, stdout=MEMINFO_TEXT)

    monkeypatch.setattr(capacity.subprocess, "run", fake_run)
    monkeypatch.setattr(capacity, "DEFAULT_MEMINFO_PATH", tmp_path / "no-meminfo")
    monkeypatch.setattr(capacity, "DEFAULT_CGROUP_PATH", tmp_path / "no-cgroup")

    assert _live_memory(LIVE_HUB) == LiveMemory(MEMINFO_AVAILABLE_BYTES, LIVE_SOURCE_VM)
    assert recorded == [
        (["docker", *HUB_DB_PS_ARGS], LIVE_MEMORY_DOCKER_TIMEOUT_SECONDS),
        (["docker", *HUB_DB_EXEC_ARGS], LIVE_MEMORY_DOCKER_TIMEOUT_SECONDS),
    ]


# --- admit (spoke admission) -------------------------------------------------

ADMIT_SELF: str = "u4i-self"
ADMIT_HUB: str = "u4i-hub-1000"
ADMIT_NETWORK: str = "u4i-shared-1000"
# The full argv `admit` issues; the runner receives it without the leading
# "docker", which `run_docker` prepends.
ADMIT_PS_ARGV: list[str] = [
    "docker",
    "ps",
    "--filter",
    f"network={ADMIT_NETWORK}",
    "--filter",
    "status=running",
    "--format",
    '{{.Label "com.docker.compose.project"}}',
]
ADMIT_CAPACITY_LINES: dict[str, str] = {
    "U4I_N_MAX": "12",
    "U4I_USABLE_MB": "9830",
    "U4I_HUB_IDLE_MB": "614",
    "U4I_SPOKE_IDLE_MB": "256",
    "U4I_SPOKE_MAX": "2",
    "U4I_BASE_MB": "2048",
    "U4I_WORKER_MB": "512",
}
# No live reading: admission falls back to the static U4I_SPOKE_MAX count rule.
STATIC_LIVE: LiveMemory = LiveMemory(None, LIVE_SOURCE_NONE)


def _live_usable(usable_gb: float, source: str = LIVE_SOURCE_HOST) -> LiveMemory:
    """A live reading whose usable share (after DEFAULT_MEM_SAFETY) is `usable_gb`,
    rounded up to the byte so a boundary value never truncates just below it."""
    return LiveMemory(math.ceil(usable_gb / DEFAULT_MEM_SAFETY * GIB), source)


class _FakeLive:
    """`admit`'s live-memory reader: returns a fixed reading, records each hub project."""

    def __init__(self, reading: LiveMemory) -> None:
        self.reading = reading
        self.hub_projects: list[str] = []

    def __call__(self, hub_project: str) -> LiveMemory:
        self.hub_projects.append(hub_project)
        return self.reading


class _FakePsDocker:
    """Scripted runner for `admit`'s `docker ps`: fixed output, records every call."""

    def __init__(
        self,
        stdout: str = "",
        returncode: int = 0,
        stderr: str = "",
        raises: Exception | None = None,
    ) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr
        self.raises = raises
        self.calls: list[list[str]] = []

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if self.raises is not None:
            raise self.raises
        return _completed(self.returncode, stdout=self.stdout, stderr=self.stderr)


def _admit_capacity(tmp_path: Path, omit: str | None = None) -> Path:
    env_path = tmp_path / "capacity.env"
    env_path.write_text(
        "".join(
            f"{key}={value}\n"
            for key, value in ADMIT_CAPACITY_LINES.items()
            if key != omit
        )
    )
    return env_path


def _admit(
    env_path: Path,
    docker: _FakePsDocker,
    live_memory: Callable[[str], LiveMemory] | None = None,
) -> int:
    """Run `admit` for ADMIT_SELF; without `live_memory` there is no live reading."""
    return main(
        [
            "admit",
            "--output",
            str(env_path),
            "--project",
            ADMIT_SELF,
            "--hub-project",
            ADMIT_HUB,
            "--network",
            ADMIT_NETWORK,
        ],
        _no_probe,
        docker,
        live_memory if live_memory is not None else _FakeLive(STATIC_LIVE),
    )


def _running(*projects: str) -> str:
    return "".join(f"{project}\n" for project in projects)


@pytest.mark.parametrize(
    "running",
    [(), ("u4i-alpha",)],
    ids=["no-other-spokes", "one-other-spoke"],
)
def test_admit_admits_silently_under_the_ceiling(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], running: tuple[str, ...]
) -> None:
    docker = _FakePsDocker(stdout=_running(*running))

    assert _admit(_admit_capacity(tmp_path), docker) == 0

    assert ["docker", *docker.calls[0]] == ADMIT_PS_ARGV
    assert len(docker.calls) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_admit_without_live_memory_refuses_past_the_spoke_max_with_the_static_numbers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No live reading → today's count rule and its refusal text, byte for byte."""
    docker = _FakePsDocker(stdout=_running("u4i-beta", "u4i-alpha"))

    assert _admit(_admit_capacity(tmp_path), docker, _FakeLive(STATIC_LIVE)) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "spoke admission: refusing spoke 3 (u4i-self) — hub 0.60 GB + 3 × 0.25 GB "
        "idle spokes + one full test run (2.00 + 12 × 0.50 GB) = 9.35 GB exceeds "
        "usable 9.60 GB (U4I_SPOKE_MAX=2). Running spokes: u4i-alpha, u4i-beta. "
        "Stop one with 'make down' in its checkout.\n"
    )


@pytest.mark.parametrize(
    "usable_gb",
    [4.0, 2.75],
    ids=["ample", "exactly-the-minimum"],
)
def test_admit_live_admits_past_the_spoke_max_when_memory_holds_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], usable_gb: float
) -> None:
    """Hub up, 2 others running (static would refuse spoke 3): needs only
    0.25 GB idle + 2.50 GB minimum run = 2.75 GB — running spokes aren't re-counted."""
    docker = _FakePsDocker(stdout=_running("u4i-alpha", ADMIT_HUB, "u4i-beta"))
    live = _FakeLive(_live_usable(usable_gb))

    assert _admit(_admit_capacity(tmp_path), docker, live) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_admit_live_refuses_with_the_numbers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docker = _FakePsDocker(stdout=_running("u4i-beta", ADMIT_HUB, "u4i-alpha"))

    assert _admit(_admit_capacity(tmp_path), docker, _FakeLive(_live_usable(2.5))) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "spoke admission: refusing spoke 3 (u4i-self) — needs 0.25 GB idle + 2.50 GB "
        "for a minimum test run = 2.75 GB, but only 2.50 GB is usable now (host). "
        "Running spokes: u4i-alpha, u4i-beta. "
        "Free memory or stop one with 'make down' in its checkout.\n"
    )


def test_admit_live_adds_the_hub_idle_cost_when_the_hub_is_not_running(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Hub label absent → its idle cost isn't in MemAvailable yet: 2.75 + 0.60 = 3.35 GB."""
    capacity_file = _admit_capacity(tmp_path)
    running = _running("u4i-alpha", "u4i-beta")
    enough = _FakeLive(_live_usable(3.35))
    short = _FakeLive(_live_usable(3.0))

    assert _admit(capacity_file, _FakePsDocker(stdout=running), enough) == 0
    assert _admit(capacity_file, _FakePsDocker(stdout=running), short) == 1

    assert capsys.readouterr().err == (
        "spoke admission: refusing spoke 3 (u4i-self) — needs 0.25 GB idle + 2.50 GB "
        "for a minimum test run + 0.60 GB hub = 3.35 GB, but only 3.00 GB is usable "
        "now (host). Running spokes: u4i-alpha, u4i-beta. "
        "Free memory or stop one with 'make down' in its checkout.\n"
    )


def test_admit_live_refusal_with_no_other_spokes_names_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docker = _FakePsDocker(stdout=_running(ADMIT_HUB))
    live = _FakeLive(_live_usable(1.0, LIVE_SOURCE_VM))

    assert _admit(_admit_capacity(tmp_path), docker, live) == 1

    assert capsys.readouterr().err == (
        "spoke admission: refusing spoke 1 (u4i-self) — needs 0.25 GB idle + 2.50 GB "
        "for a minimum test run = 2.75 GB, but only 1.00 GB is usable now (vm). "
        "Running spokes: none. "
        "Free memory or stop one with 'make down' in its checkout.\n"
    )


def test_admit_live_never_refuses_a_spoke_that_is_already_running(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docker = _FakePsDocker(stdout=_running("u4i-alpha", ADMIT_SELF, ADMIT_HUB))
    live = _FakeLive(LiveMemory(0, LIVE_SOURCE_HOST))

    assert _admit(_admit_capacity(tmp_path), docker, live) == 0
    assert capsys.readouterr().err == ""


def test_admit_reads_live_memory_for_the_hub_project_after_docker_ps(
    tmp_path: Path,
) -> None:
    docker = _FakePsDocker(stdout=_running(ADMIT_HUB))
    live = _FakeLive(_live_usable(4.0))

    assert _admit(_admit_capacity(tmp_path), docker, live) == 0

    assert live.hub_projects == [ADMIT_HUB]
    assert ["docker", *docker.calls[0]] == ADMIT_PS_ARGV
    assert len(docker.calls) == 1


def test_admit_never_refuses_a_spoke_that_is_already_running(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docker = _FakePsDocker(stdout=_running("u4i-alpha", ADMIT_SELF, "u4i-beta"))

    assert _admit(_admit_capacity(tmp_path), docker) == 0
    assert capsys.readouterr().err == ""


def test_admit_ignores_the_hub_and_empty_labels(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docker = _FakePsDocker(stdout=_running(ADMIT_HUB, "", "u4i-alpha", ADMIT_HUB, ""))

    assert _admit(_admit_capacity(tmp_path), docker) == 0
    assert capsys.readouterr().err == ""


def test_admit_counts_a_project_with_several_containers_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docker = _FakePsDocker(stdout=_running("u4i-alpha", "u4i-alpha", "u4i-alpha"))

    assert _admit(_admit_capacity(tmp_path), docker) == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    ("docker", "expected_err"),
    [
        (
            _FakePsDocker(returncode=1, stderr="Cannot connect to the Docker daemon\n"),
            "spoke admission: docker ps failed — Cannot connect to the Docker daemon\n",
        ),
        (
            _FakePsDocker(returncode=125),
            "spoke admission: docker ps failed — exited 125\n",
        ),
        (
            _FakePsDocker(
                raises=FileNotFoundError("No such file or directory: 'docker'")
            ),
            "spoke admission: docker ps failed — No such file or directory: 'docker'\n",
        ),
        (
            _FakePsDocker(raises=DockerRunError("docker ps timed out after 120s")),
            "spoke admission: docker ps failed — docker ps timed out after 120s\n",
        ),
    ],
    ids=["non-zero-exit", "non-zero-exit-no-stderr", "not-installed", "timeout"],
)
def test_admit_docker_failure_is_loud_and_never_admits(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    docker: _FakePsDocker,
    expected_err: str,
) -> None:
    live = _FakeLive(_live_usable(4.0))

    assert _admit(_admit_capacity(tmp_path), docker, live) == 1

    assert capsys.readouterr().err == expected_err
    assert live.hub_projects == []


@pytest.mark.parametrize(
    "live", [STATIC_LIVE, _live_usable(4.0)], ids=["static", "live"]
)
@pytest.mark.parametrize("missing_key", list(ADMIT_CAPACITY_LINES))
def test_admit_capacity_file_missing_a_key_exits_non_zero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    missing_key: str,
    live: LiveMemory,
) -> None:
    env_path = _admit_capacity(tmp_path, omit=missing_key)

    assert _admit(env_path, _FakePsDocker(), _FakeLive(live)) == 1

    assert capsys.readouterr().err == (
        f"spoke admission: {missing_key} missing or invalid in {env_path} "
        "— run 'make capacity'\n"
    )


def test_admit_non_integer_value_exits_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = _admit_capacity(tmp_path)
    env_path.write_text(
        env_path.read_text().replace("U4I_SPOKE_MAX=2", "U4I_SPOKE_MAX=two")
    )

    assert _admit(env_path, _FakePsDocker()) == 1
    assert "U4I_SPOKE_MAX missing or invalid" in capsys.readouterr().err


def test_admit_missing_capacity_file_exits_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "absent.env"
    docker = _FakePsDocker()

    assert _admit(env_path, docker) == 1

    assert docker.calls == []
    assert capsys.readouterr().err == (
        f"spoke admission: {env_path} does not exist — run 'make capacity'\n"
    )


def test_admit_unreadable_capacity_file_exits_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env_path = tmp_path / "capacity.env"
    env_path.write_bytes(b"\xff\xfe\x00")
    docker = _FakePsDocker()

    assert _admit(env_path, docker) == 1

    assert docker.calls == []
    captured_err = capsys.readouterr().err
    assert captured_err.startswith("spoke admission: ")
    assert captured_err.endswith("— run 'make capacity'\n")


@pytest.mark.parametrize(
    ("refusing_live", "message_start"),
    [
        (STATIC_LIVE, "refusing spoke 3 (u4i-self) — hub 0.60 GB"),
        (_live_usable(2.5), "refusing spoke 3 (u4i-self) — needs 0.25 GB idle"),
    ],
    ids=["static", "live"],
)
def test_admission_decision_reports_the_other_running_spokes(
    refusing_live: LiveMemory, message_start: str
) -> None:
    env = dict(ADMIT_CAPACITY_LINES)

    admitted = admission_decision(
        ["u4i-alpha", ADMIT_SELF], ADMIT_SELF, ADMIT_HUB, env, refusing_live
    )
    refused = admission_decision(
        ["u4i-beta", "u4i-alpha", ADMIT_HUB], ADMIT_SELF, ADMIT_HUB, env, refusing_live
    )

    assert admitted == AdmissionResult(admitted=True, others=("u4i-alpha",), message="")
    assert refused.admitted is False
    assert refused.others == ("u4i-alpha", "u4i-beta")
    assert refused.message.startswith(message_start)
