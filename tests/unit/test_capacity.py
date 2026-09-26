"""Unit tests for the host-side capacity derivation (`scripts/capacity.py`).

Every probe value is fabricated — no Docker, no `/proc` — so these run
identically on a laptop, inside the web container, and on a CI runner.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts import capacity
from scripts.capacity import (
    CONN_BASE,
    CONN_PER_WORKER,
    DEFAULT_MEM_FRACTION,
    DEFAULT_MEM_SAFETY,
    HARD_N_CEILING,
    METRICS_REDIS_DB_BASE,
    Capacity,
    InfeasibleCapacity,
    Overrides,
    Probe,
    _memory_guard,
    _usable_gb,
    clamp,
    derive,
    round_up_pow2,
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
    probe = _probe(mem_total_bytes=340 * GIB)
    usable_gb = _usable_gb(probe, DEFAULT_MEM_FRACTION, DEFAULT_MEM_SAFETY)
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
