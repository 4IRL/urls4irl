from __future__ import annotations

import gzip
import os
from unittest import mock

import pytest

import scripts.backup_maintenance
from scripts.backup_maintenance import (
    DEFAULT_MIN_DUMP_BYTES,
    EXIT_FAILURE,
    EXIT_OK,
    main,
    prune_logs,
    scan_log_entries,
    select_files_to_prune,
    verify_dump,
)

pytestmark = pytest.mark.unit


def test_verify_dump_valid_gzip_at_or_above_min_returns_ok(tmp_path):
    """
    GIVEN a valid gzip whose decompressed size (2048 bytes) is >= the minimum
    WHEN verify_dump is invoked with min_size_bytes=1024
    THEN it returns (EXIT_OK, "backup ok: ...").
    """
    dump_path = tmp_path / "backup.sql.gz"
    with gzip.open(dump_path, "wb") as gzip_file:
        gzip_file.write(b"x" * 2048)

    exit_code, message = verify_dump(path=str(dump_path), min_size_bytes=1024)

    assert exit_code == EXIT_OK
    assert "backup ok" in message
    assert "2048b" in message


def test_verify_dump_decompressed_below_min_returns_too_small(tmp_path):
    """
    GIVEN a valid gzip whose decompressed size (10 bytes) is below the minimum
    WHEN verify_dump is invoked with min_size_bytes=1024
    THEN it returns (EXIT_FAILURE, "backup too small: ...").
    """
    dump_path = tmp_path / "small.sql.gz"
    with gzip.open(dump_path, "wb") as gzip_file:
        gzip_file.write(b"0123456789")

    exit_code, message = verify_dump(path=str(dump_path), min_size_bytes=1024)

    assert exit_code == EXIT_FAILURE
    assert "too small" in message


def test_verify_dump_corrupt_non_gzip_bytes_returns_corrupt(tmp_path):
    """
    GIVEN a .gz file holding raw non-gzip bytes (bad magic number)
    WHEN verify_dump is invoked
    THEN it returns (EXIT_FAILURE, "backup corrupt: ...") via the BadGzipFile branch.
    """
    dump_path = tmp_path / "corrupt.sql.gz"
    with open(dump_path, "wb") as raw_file:
        raw_file.write(b"this is not a gzip stream at all")

    exit_code, message = verify_dump(path=str(dump_path), min_size_bytes=1024)

    assert exit_code == EXIT_FAILURE
    assert "corrupt" in message


def test_verify_dump_truncated_gzip_returns_corrupt(tmp_path):
    """
    GIVEN a valid gzip file truncated mid-stream
    WHEN verify_dump is invoked
    THEN it returns (EXIT_FAILURE, "backup corrupt: ...") via the EOFError branch.
    """
    dump_path = tmp_path / "truncated.sql.gz"
    with gzip.open(dump_path, "wb") as gzip_file:
        gzip_file.write(b"y" * 4096)
    full_size = os.path.getsize(dump_path)
    os.truncate(dump_path, full_size // 2)

    exit_code, message = verify_dump(path=str(dump_path), min_size_bytes=1024)

    assert exit_code == EXIT_FAILURE
    assert "corrupt" in message


def test_verify_dump_min_size_zero_accepts_empty_payload(tmp_path):
    """
    GIVEN a valid gzip wrapping a zero-byte payload and min_size_bytes=0
    WHEN verify_dump is invoked
    THEN it returns (EXIT_OK, ...) — the accept-empty boundary the log-backup
        path relies on (logs verify with --min-size 0, where a quiet day
        legitimately yields a near-empty archive).
    """
    dump_path = tmp_path / "empty-payload.log.gz"
    with gzip.open(dump_path, "wb") as gzip_file:
        gzip_file.write(b"")

    exit_code, message = verify_dump(path=str(dump_path), min_size_bytes=0)

    assert exit_code == EXIT_OK
    assert "backup ok" in message
    assert "0b" in message


def test_verify_dump_zero_byte_file_at_default_min_returns_too_small(tmp_path):
    """
    GIVEN a zero-byte file (gzip.open treats an empty file as an empty stream,
        decompressing to 0 bytes without raising — it is not flagged corrupt)
    WHEN verify_dump is invoked with the default minimum (1024)
    THEN it returns (EXIT_FAILURE, "backup too small: ...") — the size floor,
        not gzip-integrity, is what rejects an empty dump on the DB-backup path.
    """
    dump_path = tmp_path / "empty-file.sql.gz"
    with open(dump_path, "wb") as raw_file:
        raw_file.write(b"")

    exit_code, message = verify_dump(
        path=str(dump_path), min_size_bytes=DEFAULT_MIN_DUMP_BYTES
    )

    assert exit_code == EXIT_FAILURE
    assert "too small" in message


def test_verify_dump_os_error_during_read_returns_corrupt(tmp_path):
    """
    GIVEN a file whose gzip stream cannot be opened (gzip.open raises OSError)
    WHEN verify_dump is invoked
    THEN it returns (EXIT_FAILURE, "backup corrupt: ...") via the OSError branch.
    """
    dump_path = tmp_path / "io-error.sql.gz"
    with gzip.open(dump_path, "wb") as gzip_file:
        gzip_file.write(b"x" * 2048)

    with mock.patch.object(
        scripts.backup_maintenance.gzip,
        "open",
        side_effect=OSError("io error"),
    ):
        exit_code, message = verify_dump(path=str(dump_path), min_size_bytes=1024)

    assert exit_code == EXIT_FAILURE
    assert "corrupt" in message
    assert str(dump_path) in message


def test_verify_dump_missing_path_returns_missing(tmp_path):
    """
    GIVEN a path that does not exist
    WHEN verify_dump is invoked
    THEN it returns (EXIT_FAILURE, "backup missing: ...").
    """
    missing_path = tmp_path / "does-not-exist.sql.gz"

    exit_code, message = verify_dump(path=str(missing_path), min_size_bytes=1024)

    assert exit_code == EXIT_FAILURE
    assert "missing" in message


def test_select_files_to_prune_below_cap_returns_empty():
    """
    GIVEN fewer entries than max_files
    WHEN select_files_to_prune is invoked
    THEN it returns [] — nothing to prune.
    """
    entries = [(1.0, "a"), (2.0, "b")]

    assert select_files_to_prune(entries=entries, max_files=5) == []


def test_select_files_to_prune_exactly_at_cap_returns_empty():
    """
    GIVEN exactly max_files entries
    WHEN select_files_to_prune is invoked
    THEN it returns [] — the cap is inclusive, nothing is pruned.
    """
    entries = [(1.0, "a"), (2.0, "b"), (3.0, "c")]

    assert select_files_to_prune(entries=entries, max_files=3) == []


def test_select_files_to_prune_over_cap_returns_oldest_first():
    """
    GIVEN max_files + 3 entries supplied out of mtime order
    WHEN select_files_to_prune is invoked with max_files=2
    THEN it returns exactly the 3 lowest-mtime paths in oldest-first order.
    """
    entries = [
        (50.0, "newest"),
        (10.0, "oldest"),
        (40.0, "fourth"),
        (20.0, "second"),
        (30.0, "third"),
    ]

    assert select_files_to_prune(entries=entries, max_files=2) == [
        "oldest",
        "second",
        "third",
    ]


def test_select_files_to_prune_rejects_zero_max_files():
    """
    GIVEN max_files of 0
    WHEN select_files_to_prune is invoked
    THEN it raises ValueError rather than silently selecting every file for
        deletion — guarding against a destructive --max-files 0 caller typo.
    """
    entries = [(1.0, "a"), (2.0, "b")]

    with pytest.raises(ValueError):
        select_files_to_prune(entries=entries, max_files=0)


def test_scan_log_entries_missing_directory_returns_empty(tmp_path):
    """
    GIVEN a directory that does not exist
    WHEN scan_log_entries is invoked
    THEN it returns [] without raising.
    """
    missing_dir = tmp_path / "nonexistent"

    assert scan_log_entries(directory=str(missing_dir), pattern="*.txt") == []


def test_scan_log_entries_returns_matching_files_with_mtimes(tmp_path):
    """
    GIVEN a directory with two matching dated files and one non-matching file
    WHEN scan_log_entries is invoked with the dated pattern
    THEN it returns one (mtime, path) tuple per matching file only.
    """
    (tmp_path / "2024-01-01-daily-workflow-logs.txt").write_text("a")
    (tmp_path / "2024-01-02-daily-workflow-logs.txt").write_text("b")
    (tmp_path / "cron.log").write_text("live")

    entries = scan_log_entries(
        directory=str(tmp_path), pattern="*-daily-workflow-logs.txt"
    )

    returned_paths = {path for _, path in entries}
    assert len(entries) == 2
    assert all(isinstance(mtime, float) for mtime, _ in entries)
    assert str(tmp_path / "cron.log") not in returned_paths


def test_scan_log_entries_skips_non_regular_file_matching_glob(tmp_path):
    """
    GIVEN a real file and a symlink both matching the glob in the directory
    WHEN scan_log_entries is invoked
    THEN only the real regular file entry is returned (the symlink is skipped).
    """
    real_file = tmp_path / "2024-01-01-daily-workflow-logs.txt"
    real_file.write_text("entry")
    symlink_path = tmp_path / "2024-01-02-daily-workflow-logs.txt"
    os.symlink(tmp_path, symlink_path)

    entries = scan_log_entries(
        directory=str(tmp_path), pattern="*-daily-workflow-logs.txt"
    )

    returned_paths = {path for _, path in entries}
    assert returned_paths == {str(real_file)}
    assert str(symlink_path) not in returned_paths


def test_prune_logs_skips_unremovable_file_and_warns(tmp_path, capsys):
    """
    GIVEN three over-cap dated logs where one deletion raises OSError
    WHEN prune_logs is invoked with max_files=1
    THEN removed_count reflects only the successful deletions, the unremovable
        path is absent from removed_paths, and a warning naming it is written to
        stderr while the function still completes the remaining deletions.
    """
    log_dir = tmp_path
    dated_files = []
    for day_index in range(3):
        dated_path = log_dir / f"2024-01-0{day_index + 1}-daily-workflow-logs.txt"
        dated_path.write_text("entry")
        os.utime(dated_path, (1_000 + day_index, 1_000 + day_index))
        dated_files.append(dated_path)

    assert all(dated.exists() for dated in dated_files)

    unremovable_path = str(dated_files[0])
    real_remove = os.remove

    def remove_with_one_failure(path: str) -> None:
        if path == unremovable_path:
            raise OSError("permission denied")
        real_remove(path)

    with mock.patch.object(
        scripts.backup_maintenance.os, "remove", side_effect=remove_with_one_failure
    ):
        removed_count, removed_paths = prune_logs(
            directory=str(log_dir),
            pattern="*-daily-workflow-logs.txt",
            max_files=1,
        )

    assert removed_count == 1
    assert unremovable_path not in removed_paths
    assert str(dated_files[1]) in removed_paths
    assert f"Warning: could not prune {unremovable_path}" in capsys.readouterr().err


def test_prune_logs_removes_oldest_over_cap_and_never_touches_live_log(tmp_path):
    """
    GIVEN max_files + 2 dated workflow logs plus a live cron.log
    WHEN prune_logs is invoked with max_files=1
    THEN the 2 oldest dated files are removed, cron.log is never removed and
        still exists, and the before-state had all files present.
    """
    log_dir = tmp_path
    dated_files = []
    for day_index in range(3):
        dated_path = log_dir / f"2024-01-0{day_index + 1}-daily-workflow-logs.txt"
        dated_path.write_text("entry")
        os.utime(dated_path, (1_000 + day_index, 1_000 + day_index))
        dated_files.append(dated_path)
    live_log = log_dir / "cron.log"
    live_log.write_text("live")

    assert all(dated.exists() for dated in dated_files)
    assert live_log.exists()

    removed_count, removed_paths = prune_logs(
        directory=str(log_dir),
        pattern="*-daily-workflow-logs.txt",
        max_files=1,
    )

    assert removed_count == 2
    assert str(live_log) not in removed_paths
    assert live_log.exists()
    assert not dated_files[0].exists()
    assert not dated_files[1].exists()
    assert dated_files[2].exists()


def test_main_verify_dump_valid_returns_ok(tmp_path):
    """
    GIVEN a valid gzip dump at or above the default minimum
    WHEN main runs the verify-dump subcommand
    THEN it returns EXIT_OK.
    """
    valid_gz = tmp_path / "valid.sql.gz"
    with gzip.open(valid_gz, "wb") as gzip_file:
        gzip_file.write(b"z" * 4096)

    assert main(["verify-dump", "--path", str(valid_gz)]) == EXIT_OK


def test_main_verify_dump_missing_returns_failure_and_prints(tmp_path, capsys):
    """
    GIVEN a missing dump path
    WHEN main runs the verify-dump subcommand
    THEN it returns EXIT_FAILURE and prints a "missing" message.
    """
    missing = tmp_path / "absent.sql.gz"

    exit_code = main(["verify-dump", "--path", str(missing)])

    assert exit_code == EXIT_FAILURE
    assert "missing" in capsys.readouterr().out


def test_main_prune_logs_removes_oldest_keeps_newest(tmp_path):
    """
    GIVEN two dated workflow logs with deterministic mtimes
    WHEN main runs the prune-logs subcommand with max-files=1
    THEN the older file is removed and the newer file remains.
    """
    older = tmp_path / "2024-01-01-daily-workflow-logs.txt"
    newer = tmp_path / "2024-01-02-daily-workflow-logs.txt"
    older.write_text("old")
    newer.write_text("new")
    os.utime(older, (1_000, 1_000))
    os.utime(newer, (2_000, 2_000))

    assert older.exists()
    assert newer.exists()

    exit_code = main(["prune-logs", "--directory", str(tmp_path), "--max-files", "1"])

    assert exit_code == EXIT_OK
    assert not older.exists()
    assert newer.exists()
