---
name: run-all-tests
description: Run ALL test suites for URLS4IRL — UI tests first, then integration and unit tests — in sequence. Use when asked to run all tests, run the full test suite, verify everything passes, or run all suites end to end. Stores raw output in /tmp/claude/, writes failure details to separate failure files, and cleans up raw output on full success.
---

# Run All Tests

Run both test suites in sequence: UI tests first, then integration/unit tests. Each suite is independent — both complete regardless of failures in the other.

**CRITICAL: Never run both suites simultaneously** — they share a single test DB and Redis instance. Concurrent `db.drop_all()` calls corrupt the DB.

## Procedure

### 1. Setup

```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
UI_OUTPUT="/tmp/claude/UI_${TIMESTAMP}_output.txt"
UI_FAILURES="/tmp/claude/UI_${TIMESTAMP}_failures.txt"
INT_OUTPUT="/tmp/claude/INTEGRATION_${TIMESTAMP}_output.txt"
INT_FAILURES="/tmp/claude/INTEGRATION_${TIMESTAMP}_failures.txt"
```

### 2. Run UI Tests (first)

```bash
make test-ui-parallel-built > "$UI_OUTPUT" 2>&1
```

`test-ui-parallel-built` calls `start-built`, which stops any running stack and brings up the built stack before running. Runs all UI markers (`splash_ui`, `home_ui`, `utubs_ui`, `members_ui`, `urls_ui`, `create_urls_ui`, `update_urls_ui`, `tags_ui`, `mobile_ui`) in parallel (default `-n 12` workers).

**Fallback (sequential):** Only if the parallel run produces unexplained errors unrelated to test logic. Run each marker in order, appending output:

```bash
docker exec u4i-local-web /bin/bash -c "source /code/venv/bin/activate && pytest -m 'MARKER'" >> "$UI_OUTPUT" 2>&1
```

Wait for each to complete before starting the next; continue regardless of pass/fail.

### 3. Run Integration + Unit Tests (second, after UI suite finishes)

```bash
make test-integration-parallel > "$INT_OUTPUT" 2>&1
```

Runs all non-UI markers (`unit`, `splash`, `utubs`, `members`, `urls`, `tags`, `account_and_support`, `cli`) in parallel (default `-n 4` workers).

**Fallback (sequential):** Only if parallel run produces unexplained errors unrelated to test logic. Run each marker in order, appending output:

```bash
docker compose --project-directory . -f docker/compose.local.yaml exec web bash -c "source /code/venv/bin/activate && python -m pytest -m 'MARKER'" >> "$INT_OUTPUT" 2>&1
```

Wait for each to complete before starting the next; continue regardless of pass/fail.

### 4. On Completion

Read both output files and check each for failures.

**For each suite with failures:**
- Extract failure summaries and stack traces and write them to the corresponding `_failures.txt` file
- Report which tests failed with a stack trace snippet showing the root cause
- Reference the failure file for full details

**Always** delete both raw output files when done:
```bash
rm -f "$UI_OUTPUT" "$INT_OUTPUT"
```

If a failure file was never written (no failures), do not create it.

### 5. Final Summary

Report a combined summary:
- UI suite: N passed, M failed (reference `$UI_FAILURES` if any)
- Integration suite: N passed, M failed (reference `$INT_FAILURES` if any)
