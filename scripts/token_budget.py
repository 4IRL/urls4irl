"""Host-wide test token budget, run on the host around every budgeted test target.

The Makefile's `BUDGETED` macro wraps the pytest line of every pytest-in-`web`
target (`test-integration[-parallel]`, `test-functional[-built]`,
`test-ui-parallel[-built]`, `test-marker[-built|-parallel|-parallel-built]`,
`test-last-failed`, `test-file[-parallel|-parallel-built]`) and the harness-run
line of `test-backup-pipeline`, `test-db-provision` and
`test-playwright-lifecycle`:

    token_budget.py run --capacity-file <primary file> --lock-dir <dir> \
        --tokens <k> --label <target> -- <command…>

A run at `-n k` holds `k` tokens (a sequential run holds 1) out of the budget
`U4I_N_MAX` read from the primary clone's capacity file. Tokens are `flock`ed
slot files in a per-user lock dir, so the kernel releases them when the runner
dies — there is no ledger to go stale. A run that doesn't fit queues (and says
so) instead of oversubscribing the host; a failing run prints the capacity it
ran under. Stdlib only: it runs on the host under bare mise python.
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


class BudgetError(ValueError):
    """A refusal: printed as `token budget: <message>`, exit 1."""


@dataclass(frozen=True)
class Acquired:
    """The slot fds a run holds, plus what it waited for and shared the host with."""

    fds: tuple[int, ...]
    queued_seconds: float
    others_at_start: tuple[str, ...]
    in_use_at_start: int


@dataclass(frozen=True)
class _Holder:
    name: str  # "<slug>/<label>"
    slots: int


# --- capacity file -----------------------------------------------------------


def read_budget(path: Path) -> tuple[int, str]:
    """Return (U4I_N_MAX, the `# decision:` line's text) from the capacity file."""
    invalid = BudgetError(
        f"{path} missing or has no valid {BUDGET_KEY} — run 'make capacity'"
    )
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError) as read_error:
        raise invalid from read_error
    budget: int | None = None
    decision = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(DECISION_PREFIX):
            decision = stripped.removeprefix(DECISION_PREFIX)
            continue
        key, separator, value = stripped.partition("=")
        if separator and key == BUDGET_KEY:
            budget = int(value) if _is_ascii_digits(value) else None
    if budget is None or budget < 1:
        raise invalid
    return budget, decision


def _is_ascii_digits(text: str) -> bool:
    # str.isdigit alone accepts e.g. "²", which int() rejects.
    return text.isascii() and text.isdigit()


def _parse_tokens(raw: str) -> int:
    if not _is_ascii_digits(raw) or int(raw) < 1:
        raise BudgetError(f"--tokens must be a positive integer, got {raw!r}")
    return int(raw)


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


# --- slots ---------------------------------------------------------------------


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


def acquire(
    lock_dir: Path,
    tokens: int,
    budget: int,
    label: str,
    slug: str,
    max_wait: float | None,
    clock: Callable[[], float],
    out: TextIO,
) -> Acquired:
    """Lock `tokens` of the `budget` slot files, polling — never a blocking flock.

    Only the turnstile holder accumulates slots, and it keeps the turnstile until
    it has all of them, so runs never hold-and-wait on each other and a large
    request can't be starved by smaller ones arriving after it. Default SIGINT
    handling stays in place: Ctrl-C unwinds this loop (KeyboardInterrupt) and
    every fd taken so far is closed on the way out.
    """
    started = clock()
    deadline = None if max_wait is None else started + max_wait
    turnstile: int | None = None
    held: dict[int, int] = {}
    announced_at: float | None = None
    try:
        while True:
            if turnstile is None:
                turnstile = _try_lock(lock_dir / TURNSTILE_NAME)
            if turnstile is not None:
                for index in range(budget):
                    if len(held) == tokens:
                        break
                    if index in held:
                        continue
                    descriptor = _try_lock(_slot_path(lock_dir, index))
                    if descriptor is not None:
                        held[index] = descriptor
                        _write_slot(descriptor, slug, label, tokens)
                if len(held) == tokens:
                    break
            now = clock()
            waiting = f"{tokens} of {budget} tokens"
            if announced_at is None or now - announced_at >= HEARTBEAT_SECONDS:
                holders = _describe(
                    _holders(lock_dir, budget, set(held), turnstile is not None)
                )
                if announced_at is None:
                    print(
                        f"{MESSAGE_PREFIX}waiting for {waiting} — held by: {holders}",
                        file=out,
                        flush=True,
                    )
                else:
                    print(
                        f"{MESSAGE_PREFIX}still waiting for {waiting} "
                        f"({now - started:.0f}s) — held by: {holders}",
                        file=out,
                        flush=True,
                    )
                announced_at = now
            if deadline is not None and now >= deadline:
                raise BudgetError(
                    f"gave up after {now - started:.1f}s waiting for {waiting} "
                    "(--max-wait)"
                )
            time.sleep(POLL_SECONDS)
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
    )


# --- the child -------------------------------------------------------------------


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


# --- CLI ---------------------------------------------------------------------------


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
    run_parser.add_argument("--label", required=True)
    run_parser.add_argument(
        "--max-wait",
        type=float,
        help="give up (exit 1) after this many seconds queued; default waits forever",
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
        budget, decision = read_budget(capacity_file)
        tokens = _parse_tokens(args.tokens)
        if tokens > budget:
            raise BudgetError(
                f"this run needs {tokens} tokens but the host budget is {budget} "
                f"({BUDGET_KEY} in {capacity_file}); lower n= or raise it with "
                "'make capacity' in the primary clone"
            )
        if not command:
            raise BudgetError("no command given after --")
        max_wait: float | None = args.max_wait
        if max_wait is not None and (not math.isfinite(max_wait) or max_wait < 0):
            raise BudgetError(
                f"--max-wait must be a finite number of seconds >= 0, got {max_wait}"
            )
        ensure_lock_dir(args.lock_dir)
        acquired = acquire(
            args.lock_dir,
            tokens,
            budget,
            args.label,
            os.environ.get(SLUG_ENV_VAR) or UNKNOWN,
            max_wait,
            time.monotonic,
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
                decision=decision,
            ):
                print(line, file=sys.stderr)
        return exit_code
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    finally:
        _release(acquired.fds)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
