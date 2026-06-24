"""Pure decision helpers for the workflow container's backup pipeline.

The bash backup scripts (``daily-docker.sh`` orchestrating ``backup-database.sh``,
``backup-logs.sh``, ``remote-object-storage.sh``) cannot unit-test their own
decisions. This module is the single source of truth for the two genuinely
decidable concerns:

  - ``verify_dump`` — is a gzipped backup actually a valid, non-truncated stream
    whose decompressed payload is at least ``min_size_bytes`` (proof the dump is
    restorable, not merely that ``pg_dump`` exited 0)?
  - log-prune selection (``select_files_to_prune`` + ``scan_log_entries`` +
    ``prune_logs``) — which dated log files are over the retention cap and should
    be removed, oldest-first, in a single run?

Mirrors the ``(exit_code, message)`` return-type shape of
``scripts/check_flush_liveness.py:check_liveness``. Reads **no** environment
variables (every input arrives as a CLI argument), so the workflow env-allowlist
drift-guard test does not apply. Stdlib-only so the ``redis``+``psycopg2``-only
``/opt/metrics-venv`` (or any system ``python3``) can run it.
"""

from __future__ import annotations

import argparse
import gzip
import os
import sys
from pathlib import Path

DEFAULT_MIN_DUMP_BYTES: int = 1024
EXIT_OK: int = 0
EXIT_FAILURE: int = 1

_READ_CHUNK_BYTES: int = 64 * 1024


def verify_dump(*, path: str, min_size_bytes: int) -> tuple[int, str]:
    """Validate that ``path`` is a readable gzip whose payload meets a size floor.

    Streams the decompressed bytes in chunks (never loads the whole dump into
    memory) so a multi-GB nightly dump stays flat on RAM. A missing file, a
    corrupt/truncated gzip stream, or a payload below ``min_size_bytes`` each
    yields ``EXIT_FAILURE`` with a descriptive message; a healthy dump yields
    ``EXIT_OK``.

    Examples:
        >>> verify_dump(path="/nope.sql.gz", min_size_bytes=1024)
        (1, 'backup missing: /nope.sql.gz')
        >>> # a valid gzip whose payload decompresses to 2048 bytes
        >>> verify_dump(path="/ok.sql.gz", min_size_bytes=1024)
        (0, 'backup ok: 2048b: /ok.sql.gz')
        >>> # a valid gzip whose payload decompresses to only 10 bytes
        >>> verify_dump(path="/tiny.sql.gz", min_size_bytes=1024)
        (1, 'backup too small: 10b < 1024b: /tiny.sql.gz')
    """
    if not Path(path).exists():
        return (EXIT_FAILURE, f"backup missing: {path}")

    decompressed_bytes = 0
    try:
        with gzip.open(path, "rb") as gzip_file:
            while True:
                chunk = gzip_file.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                decompressed_bytes += len(chunk)
    except (gzip.BadGzipFile, EOFError, OSError):
        return (EXIT_FAILURE, f"backup corrupt: {path}")

    if decompressed_bytes < min_size_bytes:
        return (
            EXIT_FAILURE,
            f"backup too small: {decompressed_bytes}b < {min_size_bytes}b: {path}",
        )
    return (EXIT_OK, f"backup ok: {decompressed_bytes}b: {path}")


def select_files_to_prune(
    *, entries: list[tuple[float, str]], max_files: int
) -> list[str]:
    """Choose which files to prune so only the newest ``max_files`` survive.

    ``entries`` is a list of ``(mtime_epoch, path)`` pairs. The list is sorted
    ascending by mtime; if there are at most ``max_files`` entries nothing is
    pruned. Otherwise every file beyond the newest ``max_files`` is selected —
    all over-cap files in a single run, returned **oldest-first** (ascending
    mtime).

    A ``max_files`` below 1 is rejected (``ValueError``) rather than silently
    selecting every file for deletion — a retention cap of zero would prune the
    entire directory, which is never the intent of a backup-retention policy and
    would be a destructive foot-gun if a caller passed ``--max-files 0``.

    Examples:
        >>> select_files_to_prune(entries=[(2.0, "b"), (1.0, "a")], max_files=5)
        []
        >>> select_files_to_prune(
        ...     entries=[(30.0, "c"), (10.0, "a"), (20.0, "b")], max_files=1
        ... )
        ['a', 'b']
    """
    if max_files < 1:
        raise ValueError(f"max_files must be >= 1, got {max_files}")
    sorted_entries = sorted(entries, key=lambda entry: entry[0])
    if len(sorted_entries) <= max_files:
        return []
    over_cap = sorted_entries[: len(sorted_entries) - max_files]
    return [path for _, path in over_cap]


def scan_log_entries(*, directory: str, pattern: str) -> list[tuple[float, str]]:
    """Return ``(mtime_epoch, path)`` for each regular file matching ``pattern``.

    Globs ``pattern`` within ``directory``, skipping anything that is not a
    regular file. A missing directory yields ``[]`` (the glob simply matches
    nothing), so callers never need to pre-check existence.

    Examples:
        >>> # directory holds "2024-01-01-daily-workflow-logs.txt" (mtime 1000.0)
        >>> scan_log_entries(
        ...     directory="/app/workflow_logs",
        ...     pattern="*-daily-workflow-logs.txt",
        ... )
        [(1000.0, '/app/workflow_logs/2024-01-01-daily-workflow-logs.txt')]
        >>> scan_log_entries(directory="/no/such/dir", pattern="*.txt")
        []
    """
    entries: list[tuple[float, str]] = []
    for entry in Path(directory).glob(pattern):
        if entry.is_file():
            entries.append((entry.stat().st_mtime, str(entry)))
    return entries


def prune_logs(
    *, directory: str, pattern: str, max_files: int
) -> tuple[int, list[str]]:
    """Remove over-cap files matching ``pattern`` in ``directory``, oldest-first.

    Composes ``scan_log_entries`` and ``select_files_to_prune``, then deletes the
    selected files. A failed deletion (``OSError``) is skipped — a warning naming
    the skipped file is written to ``stderr`` so the failure leaves a diagnostic
    trail — so one unremovable file never blocks the rest. Returns
    ``(removed_count, removed_paths)``.

    Examples:
        >>> # directory holds 3 dated logs, cap of 1 -> 2 oldest removed
        >>> prune_logs(
        ...     directory="/app/workflow_logs",
        ...     pattern="*-daily-workflow-logs.txt",
        ...     max_files=1,
        ... )
        (2, ['/app/workflow_logs/2024-01-01-daily-workflow-logs.txt',
             '/app/workflow_logs/2024-01-02-daily-workflow-logs.txt'])
    """
    paths_to_prune = select_files_to_prune(
        entries=scan_log_entries(directory=directory, pattern=pattern),
        max_files=max_files,
    )
    removed_paths: list[str] = []
    for path in paths_to_prune:
        try:
            os.remove(path)
        except OSError as remove_error:
            print(
                f"Warning: could not prune {path}: {remove_error}",
                file=sys.stderr,
            )
            continue
        removed_paths.append(path)
    return (len(removed_paths), removed_paths)


def main(argv: list[str]) -> int:
    """Dispatch the ``verify-dump`` / ``prune-logs`` subcommands from ``argv``.

    Examples:
        >>> main(["verify-dump", "--path", "/ok.sql.gz"])  # prints, returns 0
        0
        >>> main(["prune-logs", "--directory", "/logs", "--max-files", "90"])
        0
    """
    parser = argparse.ArgumentParser(prog="backup_maintenance")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify-dump")
    verify_parser.add_argument("--path", required=True)
    verify_parser.add_argument("--min-size", type=int, default=DEFAULT_MIN_DUMP_BYTES)

    prune_parser = subparsers.add_parser("prune-logs")
    prune_parser.add_argument("--directory", required=True)
    prune_parser.add_argument("--pattern", default="*-daily-workflow-logs.txt")
    prune_parser.add_argument("--max-files", type=int, required=True)

    args = parser.parse_args(argv)

    if args.command == "verify-dump":
        exit_code, message = verify_dump(path=args.path, min_size_bytes=args.min_size)
        print(message)
        return exit_code

    removed_count, removed_paths = prune_logs(
        directory=args.directory,
        pattern=args.pattern,
        max_files=args.max_files,
    )
    print(f"pruned {removed_count} file(s)")
    for removed_path in removed_paths:
        print(removed_path)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
