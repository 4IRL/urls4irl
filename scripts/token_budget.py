"""Host-wide test token budget, run on the host around every budgeted test target.

The Makefile's `BUDGETED` macro wraps the pytest line of every pytest-in-`web`
target (`test-integration[-parallel]`, `test-functional[-built]`,
`test-ui-parallel[-built]`, `test-marker[-built|-parallel|-parallel-built]`,
`test-last-failed`, `test-file[-parallel|-parallel-built]`) and the harness-run
line of `test-backup-pipeline`, `test-db-provision` and
`test-playwright-lifecycle`:

    token_budget.py run --capacity-file <primary file> --lock-dir <dir> \
        [--min-tokens <m>] --tokens <k> --label <target> -- <command…>

A run at `-n k` holds `k` tokens (a sequential run holds 1) out of the budget
`U4I_N_MAX` read from the primary clone's capacity file. Tokens are `flock`ed
slot files in a per-user lock dir, so the kernel releases them when the runner
dies — there is no ledger to go stale. A run that doesn't fit queues (and says
so) instead of oversubscribing the host; a failing run prints the capacity it
ran under.

Each start is also gated on live available memory (this host's /proc/meminfo,
else the Docker VM's via the hub db container, else static capacity). An
elastic run (`--min-tokens m < --tokens k`) is granted as many of its `k`
workers as fit right now, at least `m`, and `@TOKENS@` in its command becomes
that count; an exact run waits until all `k` fit. A memory wait with no other
run holding tokens (outside pressure) gives up after `--memory-wait` seconds.
Stdlib only: it runs on the host under bare mise python.
"""

from __future__ import annotations

import argparse
import fcntl
import math
import os
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import FrameType
from typing import TextIO

POLL_SECONDS: float = 1.0
HEARTBEAT_SECONDS: int = 30
TURNSTILE_NAME: str = "turnstile.lock"
SLOT_PREFIX: str = "slot-"
LOCK_DIR_MODE: int = 0o700
LOCK_FILE_MODE: int = 0o600
BUDGET_KEY: str = "U4I_N_MAX"
DECISION_PREFIX: str = "# decision: "
SLUG_ENV_VAR: str = "U4I_SLUG"
UNKNOWN: str = "-"
MESSAGE_PREFIX: str = "token budget: "
# Exit codes: a child killed by signal N reports 128 + N, as a shell would.
EXIT_INTERRUPTED: int = 130
EXIT_CANNOT_RUN: int = 127
SIGNAL_EXIT_BASE: int = 128
FORWARDED_SIGNALS: tuple[signal.Signals, ...] = (signal.SIGINT, signal.SIGTERM)
CEILING_HINT: str = (
    "timeouts or spurious login failures at the ceiling are often capacity, "
    "not product bugs — rerun with a lower n="
)
BASE_MB_KEY: str = "U4I_BASE_MB"
WORKER_MB_KEY: str = "U4I_WORKER_MB"
# Replaced in every argv element by the granted worker count before the child starts.
TOKENS_PLACEHOLDER: str = "@TOKENS@"
# Defaults of --settle-seconds / --memory-wait (the Makefile's U4I_SETTLE_SECONDS /
# U4I_MEMORY_WAIT).
SETTLE_SECONDS: int = 20
MEMORY_WAIT_SECONDS: int = 600
NO_HOLDERS: str = "none"
WAIT_TOKENS: str = "tokens"
WAIT_MEMORY: str = "memory"

# Live memory: duplicated from capacity.py (the two scripts can't import each
# other); test_token_budget.py's parity tests pin every copy to the original.
MEM_SAFETY: float = 0.90
LIVE_MEMORY_DOCKER_TIMEOUT_SECONDS: int = 10
DEFAULT_MEMINFO_PATH: Path = Path("/proc/meminfo")
DEFAULT_CGROUP_PATH: Path = Path("/sys/fs/cgroup/memory.max")
BYTES_PER_KB: int = 1024
BYTES_PER_GB: int = 1024**3
MB_PER_GB: int = 1024
LIVE_SOURCE_HOST: str = "host"  # this host's /proc/meminfo (Linux)
LIVE_SOURCE_VM: str = "vm"  # the Docker VM's, via the hub db container (macOS/Colima)
LIVE_SOURCE_NONE: str = "none"  # unreadable: static capacity applies


class BudgetError(ValueError):
    """A refusal: printed as `token budget: <message>`, exit 1."""


@dataclass(frozen=True)
class LiveMemory:
    """Available memory right now (bytes, None when unreadable) and its LIVE_SOURCE_*."""

    available_bytes: int | None
    source: str


@dataclass(frozen=True)
class BudgetFile:
    """What the runner reads from the capacity file: the token budget, the
    `# decision:` text, and the per-run memory model (GB)."""

    budget: int
    decision: str
    base_gb: float
    worker_gb: float


@dataclass(frozen=True)
class Acquired:
    """The slot fds a run holds, plus what it waited for and shared the host with.

    `granted` is how many workers the run may start (== len(fds));
    `memory_wait_seconds` is the part of the queue spent waiting for memory.
    """

    fds: tuple[int, ...]
    queued_seconds: float
    others_at_start: tuple[str, ...]
    in_use_at_start: int
    granted: int
    live_at_start: LiveMemory
    memory_wait_seconds: float


@dataclass(frozen=True)
class _Holder:
    name: str  # "<slug>/<label>"
    slots: int


# --- capacity file -----------------------------------------------------------


def read_budget(path: Path) -> BudgetFile:
    """Read U4I_N_MAX, the `# decision:` line's text and the per-run memory
    model (U4I_BASE_MB, U4I_WORKER_MB) from the capacity file."""
    invalid = BudgetError(
        f"{path} missing or has no valid {BUDGET_KEY} — run 'make capacity'"
    )
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError) as read_error:
        raise invalid from read_error
    values: dict[str, int | None] = {}
    decision = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(DECISION_PREFIX):
            decision = stripped.removeprefix(DECISION_PREFIX)
            continue
        key, separator, value = stripped.partition("=")
        if separator and key in (BUDGET_KEY, BASE_MB_KEY, WORKER_MB_KEY):
            values[key] = int(value) if _is_ascii_digits(value) else None
    budget = values.get(BUDGET_KEY)
    if budget is None or budget < 1:
        raise invalid
    base_mb = values.get(BASE_MB_KEY)
    worker_mb = values.get(WORKER_MB_KEY)
    if base_mb is None or worker_mb is None or worker_mb < 1:
        raise BudgetError(
            f"{path} missing or has no valid {BASE_MB_KEY}/{WORKER_MB_KEY} — run "
            "'make capacity'"
        )
    return BudgetFile(
        budget=budget,
        decision=decision,
        base_gb=base_mb / MB_PER_GB,
        worker_gb=worker_mb / MB_PER_GB,
    )


def _is_ascii_digits(text: str) -> bool:
    # str.isdigit alone accepts e.g. "²", which int() rejects.
    return text.isascii() and text.isdigit()


def _parse_tokens(raw: str, flag: str) -> int:
    if not _is_ascii_digits(raw) or int(raw) < 1:
        raise BudgetError(f"{flag} must be a positive integer, got {raw!r}")
    return int(raw)


def _validate_seconds(seconds: float | None, flag: str) -> None:
    """Refuse a NaN, infinite or negative seconds value (None = flag unset)."""
    if seconds is not None and (not math.isfinite(seconds) or seconds < 0):
        raise BudgetError(
            f"{flag} must be a finite number of seconds >= 0, got {seconds}"
        )


def ensure_lock_dir(lock_dir: Path) -> None:
    """Create the per-user lock dir 0700; refuse any existing one we can't trust.

    lstat (not stat) so a symlink planted at the path is refused rather than
    followed; a dir another uid owns, or one group/other can reach, is refused too.
    """
    try:
        lock_dir.mkdir(mode=LOCK_DIR_MODE)
        # mkdir's mode is filtered by the umask; set it exactly.
        os.chmod(lock_dir, LOCK_DIR_MODE)
    except FileExistsError:
        pass
    status = os.lstat(lock_dir)
    if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
        raise BudgetError(
            f"{lock_dir} is a symlink or not a directory — remove it and rerun "
            "(the runner recreates it 0700)"
        )
    if status.st_uid != os.getuid():
        raise BudgetError(
            f"{lock_dir} is owned by uid {status.st_uid}, not {os.getuid()} — remove "
            "it as its owner (the runner recreates it 0700)"
        )
    if status.st_mode & 0o077 != 0:
        raise BudgetError(
            f"{lock_dir} dir mode is {stat.S_IMODE(status.st_mode):04o}, expected "
            f"{LOCK_DIR_MODE:04o} — remove it and rerun"
        )


# --- live memory -------------------------------------------------------------
# Behaviourally identical copies of capacity.py's functions; keep the two in step
# (parity tests). hub_vm_meminfo's error handling is adapted: with no
# DockerRunError here, it catches the raw subprocess errors directly.

DockerRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def parse_meminfo(text: str, key: str) -> int | None:
    """Return `key`'s value from /proc/meminfo text in bytes, or None.

    A malformed value is treated like a missing key (unknown), not an error.
    """
    for line in text.splitlines():
        name, _, rest = line.partition(":")
        if name == key:
            try:
                return int(rest.split()[0]) * BYTES_PER_KB
            except (IndexError, ValueError):
                return None
    return None


def parse_cgroup_max(text: str) -> int | None:
    """Return a cgroup v2 `memory.max` limit in bytes; None for `max` or malformed."""
    limit = text.strip()
    if limit == "max":
        return None
    try:
        return int(limit)
    except ValueError:
        return None


def _read_optional(path: Path) -> str | None:
    try:
        return path.read_text()
    except (OSError, UnicodeDecodeError):
        return None


def read_live_available(
    meminfo_path: Path, cgroup_path: Path, vm_meminfo: Callable[[], str | None]
) -> LiveMemory:
    """Available memory now: this host's MemAvailable (capped by the cgroup limit),
    else the Docker VM's via `vm_meminfo`, else unknown. Malformed readings fall
    through to the next source."""
    meminfo_text = _read_optional(meminfo_path)
    host_available = (
        parse_meminfo(meminfo_text, "MemAvailable") if meminfo_text else None
    )
    if host_available is not None:
        cgroup_text = _read_optional(cgroup_path)
        cgroup_max = parse_cgroup_max(cgroup_text) if cgroup_text else None
        if cgroup_max is not None:
            host_available = min(host_available, cgroup_max)
        return LiveMemory(host_available, LIVE_SOURCE_HOST)
    vm_text = vm_meminfo()
    vm_available = parse_meminfo(vm_text, "MemAvailable") if vm_text else None
    if vm_available is not None:
        return LiveMemory(vm_available, LIVE_SOURCE_VM)
    return LiveMemory(None, LIVE_SOURCE_NONE)


def _run_docker_short(args: list[str]) -> subprocess.CompletedProcess[str]:
    """`docker <args>` with the live-memory read's short timeout (may raise)."""
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=LIVE_MEMORY_DOCKER_TIMEOUT_SECONDS,
    )


def hub_vm_meminfo(hub_project: str, docker: DockerRunner) -> str | None:
    """The Docker VM's /proc/meminfo, read inside the running hub db container
    (a container sees its kernel's meminfo). None on any failure; never raises."""
    ps_args = [
        "ps",
        "-q",
        "--filter",
        f"label=com.docker.compose.project={hub_project}",
        "--filter",
        "label=com.docker.compose.service=db",
        "--filter",
        "status=running",
    ]
    try:
        listed = docker(ps_args)
        container_ids = listed.stdout.split() if listed.returncode == 0 else []
        if not container_ids:
            return None
        meminfo = docker(["exec", container_ids[0], "cat", "/proc/meminfo"])
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None
    return meminfo.stdout if meminfo.returncode == 0 else None


def live_usable_gb(live: LiveMemory) -> float | None:
    """The tests' usable share of the live reading (the MEM_SAFETY margin applied)."""
    if live.available_bytes is None:
        return None
    return live.available_bytes * MEM_SAFETY / BYTES_PER_GB


def workers_that_fit(usable_gb: float, base_gb: float, worker_gb: float) -> int:
    """Test workers a run can start in `usable_gb`; 0 when not even one fits.
    Round before flooring, as in capacity.py's `_memory_guard`."""
    return max(0, math.floor(round((usable_gb - base_gb) / worker_gb, 6)))


def _live_memory_reader(
    meminfo_path: Path, cgroup_path: Path, hub_project: str | None
) -> Callable[[], LiveMemory]:
    """The production reading: `meminfo_path` (capped by `cgroup_path`), else
    (given a hub project) the VM."""

    def vm_meminfo() -> str | None:
        if hub_project is None:
            return None
        return hub_vm_meminfo(hub_project, _run_docker_short)

    def read() -> LiveMemory:
        return read_live_available(meminfo_path, cgroup_path, vm_meminfo)

    return read


# --- slots -------------------------------------------------------------------


def _open_lock_file(path: Path) -> int:
    return os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, LOCK_FILE_MODE)


def _try_lock(path: Path) -> int | None:
    """An fd holding an exclusive lock on `path`, or None if another holds it."""
    descriptor = _open_lock_file(path)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(descriptor)
        return None
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _slot_path(lock_dir: Path, index: int) -> Path:
    return lock_dir / f"{SLOT_PREFIX}{index}"


def _write_slot(descriptor: int, slug: str, label: str, tokens: int) -> None:
    since = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    line = (
        f"pid={os.getpid()} slug={slug} label={label} tokens={tokens} since={since}\n"
    )
    os.ftruncate(descriptor, 0)
    os.pwrite(descriptor, line.encode(), 0)


def _release(descriptors: tuple[int, ...] | list[int]) -> None:
    """Blank each slot (its contents are then never mistaken for a holder) and unlock."""
    for descriptor in descriptors:
        try:
            os.ftruncate(descriptor, 0)
        except OSError:
            pass
        os.close(descriptor)


def _parse_slot(text: str) -> dict[str, str]:
    return dict(field.split("=", 1) for field in text.split() if "=" in field)


def _is_locked(path: Path) -> bool:
    """Probe a slot another runner may hold. Only safe while holding the turnstile."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return False
    try:
        fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    finally:
        os.close(descriptor)
    return False


def _pid_alive(pid_text: str) -> bool:
    if not _is_ascii_digits(pid_text):
        return False
    try:
        os.kill(int(pid_text), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Holders share our uid (per-user lock dir): a foreign-uid pid is a reused one.
        return False
    return True


def _holders(
    lock_dir: Path, budget: int, own: set[int], probe_locks: bool
) -> list[_Holder]:
    """Who holds the other slots, grouped by runner pid, in slot order.

    Holding the turnstile, the slot locks are probed (exact). Without it they
    must not be locked, so the contents are read best-effort instead: a slot is
    blanked on release, and one left by a killed runner is skipped by its pid.
    """
    counts: dict[str, int] = {}
    names: dict[str, str] = {}
    for index in range(budget):
        if index in own:
            continue
        path = _slot_path(lock_dir, index)
        if probe_locks and not _is_locked(path):
            continue
        try:
            fields = _parse_slot(path.read_text())
        except (OSError, UnicodeDecodeError):
            fields = {}
        pid = fields.get("pid", "")
        if not probe_locks and not _pid_alive(pid):
            continue
        key = pid or f"slot-{index}"
        names.setdefault(
            key, f"{fields.get('slug', UNKNOWN)}/{fields.get('label', UNKNOWN)}"
        )
        counts[key] = counts.get(key, 0) + 1
    return [_Holder(name=names[key], slots=counts[key]) for key in counts]


def _describe(holders: list[_Holder]) -> str:
    return ", ".join(f"{holder.name} ({holder.slots})" for holder in holders) or UNKNOWN


def _memory_target(live: LiveMemory, tokens: int, budget_file: BudgetFile) -> int:
    """Workers a run of `tokens` may start now: as many as fit in live memory,
    capped at `tokens`; all of them when live memory is unreadable (static)."""
    usable_gb = live_usable_gb(live)
    if usable_gb is None:
        return tokens
    fit = workers_that_fit(usable_gb, budget_file.base_gb, budget_file.worker_gb)
    return min(tokens, fit)


def _lock_slots(
    lock_dir: Path,
    budget: int,
    wanted: int,
    held: dict[int, int],
    stamped: dict[int, int],
    slug: str,
    label: str,
) -> None:
    """Trim `held` down to `wanted` slots (highest index first), then lock free
    slots until it holds `wanted` or none is free. `stamped` records the
    `tokens=` count written into each held slot."""
    for index in sorted(held)[wanted:]:
        _release([held.pop(index)])
        del stamped[index]
    for index in range(budget):
        if len(held) >= wanted:
            return
        if index in held:
            continue
        descriptor = _try_lock(_slot_path(lock_dir, index))
        if descriptor is not None:
            held[index] = descriptor
            _write_slot(descriptor, slug, label, wanted)
            stamped[index] = wanted


def acquire(
    lock_dir: Path,
    tokens: int,
    min_tokens: int,
    budget_file: BudgetFile,
    label: str,
    slug: str,
    max_wait: float | None,
    memory_wait: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    live_memory: Callable[[], LiveMemory],
    out: TextIO,
) -> Acquired:
    """Lock between `min_tokens` and `tokens` of the budget's slot files, as many
    as live memory fits, polling — never a blocking flock.

    Only the turnstile holder reads live memory and accumulates slots, and it
    keeps the turnstile until it is granted, so starts are serialised, runs never
    hold-and-wait on each other, and a large request can't be starved by smaller
    ones arriving after it. While fewer than `min_tokens` workers fit, it waits for
    memory keeping the turnstile and every slot it holds; extras past a lower fit
    are released once the fit is back at or above `min_tokens` (when it locks
    toward the new target). That wait
    gives up after `memory_wait` seconds summed over polls where no other run
    holds tokens (outside pressure); behind our own runs it waits like a token
    wait. `max_wait` bounds the whole wait. Default SIGINT handling stays in
    place: Ctrl-C unwinds this loop (KeyboardInterrupt) and every fd taken so far
    is closed on the way out.
    """
    budget = budget_file.budget
    started = clock()
    deadline = None if max_wait is None else started + max_wait
    turnstile: int | None = None
    held: dict[int, int] = {}
    stamped: dict[int, int] = {}
    announced_at: dict[str, float] = {}
    live = LiveMemory(None, LIVE_SOURCE_NONE)
    noted_static = False
    previous = started
    memory_short = False
    others_holding = False
    memory_waited = 0.0
    outside_pressure_waited = 0.0
    try:
        while True:
            now = clock()
            if memory_short:
                memory_waited += now - previous
                if not others_holding:
                    outside_pressure_waited += now - previous
            previous = now
            wanted = tokens
            memory_short = False
            if turnstile is None:
                turnstile = _try_lock(lock_dir / TURNSTILE_NAME)
            if turnstile is not None:
                live = live_memory()
                if live.available_bytes is None and not noted_static:
                    print(
                        f"{MESSAGE_PREFIX}live memory unavailable — using static "
                        "capacity",
                        file=out,
                        flush=True,
                    )
                    noted_static = True
                wanted = _memory_target(live, tokens, budget_file)
                if wanted >= min_tokens:
                    _lock_slots(lock_dir, budget, wanted, held, stamped, slug, label)
                    if len(held) == wanted:
                        break
                else:
                    memory_short = True
            reason = WAIT_MEMORY if memory_short else WAIT_TOKENS
            last_announced = announced_at.get(reason)
            announce = (
                last_announced is None or now - last_announced >= HEARTBEAT_SECONDS
            )
            holders = (
                _holders(lock_dir, budget, set(held), turnstile is not None)
                if memory_short or announce
                else []
            )
            others_holding = bool(holders)
            if memory_short:
                need = (
                    f"{budget_file.base_gb + min_tokens * budget_file.worker_gb:.2f} GB"
                )
                usable = f"{live_usable_gb(live):.2f} GB usable ({live.source})"
                waiting = "memory"
                detail = (
                    f"need {need} for {min_tokens} workers, {usable}; runs holding "
                    f"tokens: {_describe(holders) if holders else NO_HOLDERS}"
                )
            else:
                waiting = f"{wanted} of {budget} tokens"
                detail = f"held by: {_describe(holders)}"
            if announce:
                if last_announced is None:
                    line = f"waiting for {waiting} — {detail}"
                else:
                    line = (
                        f"still waiting for {waiting} ({now - started:.0f}s) — {detail}"
                    )
                print(f"{MESSAGE_PREFIX}{line}", file=out, flush=True)
                announced_at[reason] = now
            if (
                memory_short
                and not others_holding
                and outside_pressure_waited >= memory_wait
            ):
                raise BudgetError(
                    f"gave up after {outside_pressure_waited:.0f}s waiting for memory "
                    f"with no other test run holding tokens — need {need}, {usable}; "
                    f"lower n= or free host memory (U4I_MEMORY_WAIT={memory_wait:g})"
                )
            if deadline is not None and now >= deadline:
                raise BudgetError(
                    f"gave up after {now - started:.1f}s waiting for {waiting} "
                    "(--max-wait)"
                )
            sleep(POLL_SECONDS)
        granted = len(held)
        for index, descriptor in held.items():
            if stamped[index] != granted:
                _write_slot(descriptor, slug, label, granted)
        others = _holders(lock_dir, budget, set(held), probe_locks=True)
    except BaseException:
        _release(list(held.values()))
        raise
    finally:
        if turnstile is not None:
            os.close(turnstile)
    return Acquired(
        fds=tuple(held.values()),
        queued_seconds=clock() - started,
        others_at_start=tuple(holder.name for holder in others),
        in_use_at_start=sum(holder.slots for holder in others),
        granted=granted,
        live_at_start=live,
        memory_wait_seconds=memory_waited,
    )


# --- the child ---------------------------------------------------------------


def _should_relay(signum: int, child_pid: int) -> bool:
    """SIGTERM always; SIGINT only to a child outside the runner's process group."""
    if signum != signal.SIGINT:
        return True
    try:
        return os.getpgid(child_pid) != os.getpgrp()
    except ProcessLookupError:
        return False


def _run_child(command: list[str]) -> int:
    """Run `command`, relaying signals to it only while it runs.

    SIGTERM (e.g. `kill <runner>`) reaches only the runner, so it is always
    relayed. A terminal Ctrl-C is delivered by the tty to the whole foreground
    process group, which the child shares with the runner, so the child already
    has it: relaying would deliver it twice. SIGINT is therefore relayed only to
    a child in another process group, and otherwise ignored here — the runner
    keeps waiting and exits with the child's code. A signal that lands before
    the child exists is held and then handled by the same rule.
    """
    child: subprocess.Popen[bytes] | None = None
    pending: list[int] = []

    def forward(signum: int, _frame: FrameType | None) -> None:
        if child is None:
            pending.append(signum)
        elif _should_relay(signum, child.pid):
            child.send_signal(signum)

    previous = {signum: signal.signal(signum, forward) for signum in FORWARDED_SIGNALS}
    try:
        child = subprocess.Popen(command)
        for signum in pending:
            if _should_relay(signum, child.pid):
                child.send_signal(signum)
        exit_code = child.wait()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return SIGNAL_EXIT_BASE - exit_code if exit_code < 0 else exit_code


def format_failure_block(
    label: str,
    exit_code: int,
    tokens: int,
    budget: int,
    capacity_file: Path,
    queued_seconds: float,
    others_at_start: tuple[str, ...],
    in_use_at_start: int,
    decision: str,
) -> list[str]:
    """The capacity a failed run ran under, so a capacity artifact identifies itself."""
    others = f" ({', '.join(others_at_start)})" if others_at_start else ""
    at_ceiling = in_use_at_start + tokens >= budget
    lines = [
        f"{MESSAGE_PREFIX}{label} exited {exit_code} — resolved capacity for this run:",
        f"  tokens (n):     {tokens} of budget {budget} ({BUDGET_KEY}, {capacity_file})",
        f"  queued:         {queued_seconds:.1f}s; other holders at start: "
        f"{in_use_at_start} tokens{others}",
        f"  at ceiling:     {'yes' if at_ceiling else 'no'}  "
        "(tokens in use incl. this run == budget)",
        f"  decision:       {decision or UNKNOWN}",
    ]
    if at_ceiling:
        lines.append(f"  hint:           {CEILING_HINT}")
    return lines


# --- CLI ---------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="token_budget.py",
        description="Hold host test tokens (U4I_N_MAX) around a command.",
    )
    subcommands = parser.add_subparsers(dest="subcommand", required=True)
    run_parser = subcommands.add_parser(
        "run", help="queue for --tokens slots, then run the command after --"
    )
    run_parser.add_argument("--capacity-file", type=Path, required=True)
    run_parser.add_argument("--lock-dir", type=Path, required=True)
    # Validated by hand (not type=int) so a bad count exits 1 with our prefix.
    run_parser.add_argument("--tokens", required=True)
    run_parser.add_argument(
        "--min-tokens",
        help="fewest workers an elastic run accepts (default --tokens: exact); "
        f"below --tokens the command must contain {TOKENS_PLACEHOLDER}",
    )
    run_parser.add_argument("--label", required=True)
    run_parser.add_argument(
        "--max-wait",
        type=float,
        help="give up (exit 1) after this many seconds queued; default waits forever",
    )
    run_parser.add_argument(
        "--memory-wait",
        type=float,
        default=MEMORY_WAIT_SECONDS,
        help="give up (exit 1) after this many seconds waiting for memory while no "
        "other run holds tokens",
    )
    run_parser.add_argument(
        "--settle-seconds",
        type=float,
        default=SETTLE_SECONDS,
        help="keep starts serialised this long after the child starts (validated "
        "only until the settle window lands)",
    )
    run_parser.add_argument(
        "--hub-project",
        help="read the Docker VM's memory through this hub's db container when "
        "--meminfo is unreadable (macOS/Colima)",
    )
    run_parser.add_argument(
        "--meminfo",
        type=Path,
        default=DEFAULT_MEMINFO_PATH,
        help="host meminfo file (tests)",
    )
    run_parser.add_argument(
        "--cgroup",
        type=Path,
        default=DEFAULT_CGROUP_PATH,
        help="cgroup memory.max file (tests)",
    )
    run_parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    command: list[str] = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    capacity_file: Path = args.capacity_file
    try:
        budget_file = read_budget(capacity_file)
        budget = budget_file.budget
        tokens = _parse_tokens(args.tokens, "--tokens")
        if tokens > budget:
            raise BudgetError(
                f"this run needs {tokens} tokens but the host budget is {budget} "
                f"({BUDGET_KEY} in {capacity_file}); lower n= or raise it with "
                "'make capacity' in the primary clone"
            )
        if not command:
            raise BudgetError("no command given after --")
        min_tokens = (
            _parse_tokens(args.min_tokens, "--min-tokens")
            if args.min_tokens is not None
            else tokens
        )
        if min_tokens > tokens:
            raise BudgetError(
                f"--min-tokens must be between 1 and --tokens ({tokens}), "
                f"got {min_tokens}"
            )
        if min_tokens < tokens and not any(
            TOKENS_PLACEHOLDER in element for element in command
        ):
            raise BudgetError(
                "an elastic run (--min-tokens < --tokens) needs "
                f"{TOKENS_PLACEHOLDER} in the command"
            )
        max_wait: float | None = args.max_wait
        _validate_seconds(max_wait, "--max-wait")
        _validate_seconds(args.memory_wait, "--memory-wait")
        _validate_seconds(args.settle_seconds, "--settle-seconds")
        ensure_lock_dir(args.lock_dir)
        acquired = acquire(
            args.lock_dir,
            tokens,
            min_tokens,
            budget_file,
            args.label,
            os.environ.get(SLUG_ENV_VAR) or UNKNOWN,
            max_wait,
            args.memory_wait,
            time.monotonic,
            time.sleep,
            _live_memory_reader(args.meminfo, args.cgroup, args.hub_project),
            sys.stderr,
        )
    except BudgetError as refusal:
        print(f"{MESSAGE_PREFIX}{refusal}", file=sys.stderr)
        return 1
    except OSError as lock_error:
        print(f"{MESSAGE_PREFIX}{lock_error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(f"{MESSAGE_PREFIX}interrupted while queued", file=sys.stderr)
        return EXIT_INTERRUPTED
    # Everything after acquire() is covered, so the slots are released even if a
    # Ctrl-C lands outside _run_child's handlers (just before or after them).
    try:
        command = [
            element.replace(TOKENS_PLACEHOLDER, str(acquired.granted))
            for element in command
        ]
        try:
            exit_code = _run_child(command)
        except OSError as spawn_error:
            print(
                f"{MESSAGE_PREFIX}cannot run {command[0]}: {spawn_error}",
                file=sys.stderr,
            )
            return EXIT_CANNOT_RUN
        if exit_code not in (0, EXIT_INTERRUPTED):
            for line in format_failure_block(
                label=args.label,
                exit_code=exit_code,
                tokens=tokens,
                budget=budget,
                capacity_file=capacity_file,
                queued_seconds=acquired.queued_seconds,
                others_at_start=acquired.others_at_start,
                in_use_at_start=acquired.in_use_at_start,
                decision=budget_file.decision,
            ):
                print(line, file=sys.stderr)
        return exit_code
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    finally:
        _release(acquired.fds)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
