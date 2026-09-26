"""Host capacity derivation, run by `make capacity` from the repo root.

Derives the UI and integration pytest-xdist worker counts from the Docker
host's cores and memory, plus the ceilings that must grow with them (the
metrics-Redis database count and the test-db `max_connections`). Stdlib only:
it runs on the host under bare mise python, before any container exists.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

METRICS_REDIS_DB_BASE: int = 8  # mirrors tests.conftest._METRICS_REDIS_DB_BASE
CONN_PER_WORKER: int = 15  # SQLAlchemy QueuePool size 5 + max_overflow 10
CONN_BASE: int = 50
# Shared redis runs `--databases 32`; each xdist worker uses index gwN + 2.
HARD_N_CEILING: int = 30
BASE_GB: float = 2.0
WORKER_GB: float = 0.5
DEFAULT_MEM_FRACTION: float = 0.70
DEFAULT_MEM_SAFETY: float = 0.90

N_UI_MIN: int = 2
N_UI_MAX: int = 12
N_INT_MIN: int = 2
N_INT_MAX: int = 16
REDIS_METRICS_DATABASES_FLOOR: int = 16
BYTES_PER_GB: int = 1024**3

BINDING_CPU: str = "cpu"
BINDING_MEMORY: str = "memory"
BINDING_OVERRIDE: str = "override"


class InfeasibleCapacity(ValueError):
    """A requested worker count or memory fraction cannot run on this host."""


@dataclass(frozen=True)
class Probe:
    ncpu: int
    mem_total_bytes: int
    mem_available_bytes: int | None
    cgroup_max_bytes: int | None
    host_uid: int
    host_gid: int


@dataclass(frozen=True)
class Overrides:
    n_ui: int | None = None
    n_int: int | None = None
    mem_fraction: float | None = None


@dataclass(frozen=True)
class Capacity:
    n_ui: int
    n_int: int
    n_max: int
    redis_metrics_databases: int
    test_max_conn: int
    usable_gb: float
    binding_constraint: str


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


def round_up_pow2(value: int) -> int:
    return 1 << max(value - 1, 0).bit_length()


def _usable_gb(probe: Probe, mem_fraction: float, mem_safety: float) -> float:
    total_gb = probe.mem_total_bytes / BYTES_PER_GB * mem_fraction
    known_available = [
        available_bytes
        for available_bytes in (probe.mem_available_bytes, probe.cgroup_max_bytes)
        if available_bytes is not None
    ]
    if not known_available:
        return total_gb
    return min(total_gb, min(known_available) / BYTES_PER_GB * mem_safety)


def _memory_guard(usable_gb: float) -> int:
    # Round before flooring: binary-float rounding on usable_gb (e.g. 237.99999999999997
    # instead of 238.0) can otherwise make the floor under-count by one worker.
    return max(1, math.floor(round((usable_gb - BASE_GB) / WORKER_GB, 6)))


def _gb_needed(worker_count: int) -> float:
    return BASE_GB + worker_count * WORKER_GB


def _resolve_workers(
    knob: str,
    cpu_derived: int,
    override: int | None,
    memory_guard: int,
    usable_gb: float,
) -> tuple[int, bool]:
    """Return (worker count, whether memory reduced the CPU-derived value)."""
    if override is None:
        return min(cpu_derived, memory_guard), memory_guard < cpu_derived
    if override < 1:
        raise InfeasibleCapacity(
            f"{knob}={override} is below 1 worker; "
            f"rerun with {knob}>=1 (or {knob}=auto)"
        )
    if override > HARD_N_CEILING:
        raise InfeasibleCapacity(
            f"{knob}={override} exceeds the hard ceiling of {HARD_N_CEILING} "
            f"(shared redis runs --databases 32, one database per worker at gwN+2); "
            f"rerun with {knob}<={HARD_N_CEILING}"
        )
    if override > memory_guard:
        raise InfeasibleCapacity(
            f"{knob}={override} needs {_gb_needed(override):.1f} GB but only "
            f"{usable_gb:.1f} GB is usable (at most {memory_guard} workers fit); "
            f"rerun with a smaller {knob} or raise U4I_MEM_FRACTION on a dedicated host"
        )
    return override, False


def derive(
    probe: Probe,
    overrides: Overrides,
    mem_fraction: float,
    mem_safety: float,
) -> Capacity:
    """Derive worker counts and interlocks from a host probe.

    `mem_fraction` is caller-resolved: `overrides.mem_fraction` when set,
    else `DEFAULT_MEM_FRACTION`. Raises `InfeasibleCapacity` when an override
    cannot run on this host.

    `mem_safety` is always the internal `DEFAULT_MEM_SAFETY` constant, not a
    user-exposed knob (no override path feeds it), so it is not validated here.
    """
    if not 0 < mem_fraction <= 1:
        raise InfeasibleCapacity(
            f"U4I_MEM_FRACTION={mem_fraction} is outside (0, 1]; "
            f"rerun with U4I_MEM_FRACTION between 0 and 1 (or U4I_MEM_FRACTION=auto)"
        )
    usable_gb = _usable_gb(probe, mem_fraction, mem_safety)
    memory_guard = _memory_guard(usable_gb)

    n_ui, ui_memory_bound = _resolve_workers(
        "U4I_N_UI",
        clamp(probe.ncpu * 2 // 3, N_UI_MIN, N_UI_MAX),
        overrides.n_ui,
        memory_guard,
        usable_gb,
    )
    n_int, int_memory_bound = _resolve_workers(
        "U4I_N_INT",
        clamp(probe.ncpu, N_INT_MIN, N_INT_MAX),
        overrides.n_int,
        memory_guard,
        usable_gb,
    )

    if ui_memory_bound or int_memory_bound:
        binding_constraint = BINDING_MEMORY
    elif overrides.n_ui is not None or overrides.n_int is not None:
        binding_constraint = BINDING_OVERRIDE
    else:
        binding_constraint = BINDING_CPU

    n_max = max(n_ui, n_int)
    return Capacity(
        n_ui=n_ui,
        n_int=n_int,
        n_max=n_max,
        redis_metrics_databases=max(
            REDIS_METRICS_DATABASES_FLOOR,
            round_up_pow2(METRICS_REDIS_DB_BASE + n_max),
        ),
        test_max_conn=n_max * CONN_PER_WORKER + CONN_BASE,
        usable_gb=usable_gb,
        binding_constraint=binding_constraint,
    )
