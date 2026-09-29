---
name: run-all-tests
description: Run ALL test suites for URLS4IRL — UI tests first, then integration and unit tests — in sequence. Use when asked to run all tests, run the full test suite, verify everything passes, or run all suites end to end. Stores raw output in /tmp/claude/, writes failure details to separate failure files, and cleans up raw output on full success.
---

# Run All Tests

Run both test suites in sequence: UI tests first, then integration/unit tests. Each suite is independent — both complete regardless of failures in the other.

**Concurrency is governed by the host token budget.** Concurrent runs are isolated (each gets its own `testrun_uid`-keyed databases and leased Redis indices), and every `make test-*` target that runs pytest in `web` (not `test-host-static`) holds tokens from a per-user, host-wide budget of `U4I_N_MAX` (a run at `-n k` holds `k`, a sequential run holds 1). A run that would oversubscribe the host queues instead: it prints `token budget: waiting for <k> of <budget> tokens — held by: …` once, then a `still waiting` heartbeat every 30s, and starts when tokens free up. That is not a hang, so don't kill it. If the heartbeat keeps naming the same holder with no progress, investigate that holder (its `<slug>/<label>`) rather than waiting indefinitely: the Makefile never passes `--max-wait`, so a queued run waits forever. A failing run prints a `resolved capacity for this run:` block; `at ceiling: yes` with timeouts means rerun with a lower `n=` before debugging product code. If an interrupted run leaked databases or leases (e.g. a `Redis lease pool '…' is exhausted` error), run `make reset-test-dbs` before retrying.

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

`test-ui-parallel-built` calls `start-built`, which stops any running stack and brings up the built stack before running. Runs the UI marker set hardcoded in the target's `-m` expression in the `Makefile`, in parallel, using the target's default worker count. **Before running**, compare the `_ui` markers in `pytest.ini`'s `markers =` list against that expression; if any is missing from the `Makefile`, report the mismatch to the user first (a missing `_ui` marker is silently skipped here and picked up by the integration target instead).

**Fallback (sequential):** Only if the parallel run produces unexplained errors unrelated to test logic. Read the `markers =` list in `pytest.ini` at runtime and run every marker ending in `_ui`, in the order listed there (do not rely on a remembered list; markers are added over time), appending output:

```bash
make test-marker-parallel m=MARKER >> "$UI_OUTPUT" 2>&1
```

This execs into the built stack that `test-ui-parallel-built` already started, so markers still run against built assets without a rebuild or `prune`.

Wait for each to complete before starting the next; continue regardless of pass/fail.

### 3. Run Integration + Unit Tests (second, after UI suite finishes)

```bash
make test-integration-parallel > "$INT_OUTPUT" 2>&1
```

Runs every marker not excluded by the target's hardcoded `not <marker>_ui …` expression in the `Makefile`, in parallel, using the target's default worker count (the `_ui` check in §2 covers this exclusion list too).

**Fallback (sequential):** Only if parallel run produces unexplained errors unrelated to test logic. Read the `markers =` list in `pytest.ini` at runtime and run every marker that does not end in `_ui`, in the order listed there, appending output:

```bash
make test-marker-parallel m=MARKER >> "$INT_OUTPUT" 2>&1
```

Wait for each to complete before starting the next; continue regardless of pass/fail.

### 4. On Completion

Read both output files and check each for failures.

**For each suite with failures:**
- Extract failure summaries and stack traces and write them to the corresponding `_failures.txt` file
- **Investigate every failure** — never dismiss a failure as "pre-existing" or "flaky" because the test file wasn't modified on the current branch. Current changes can break tests indirectly (shared fixtures, CSS/selector changes, templates, timing, imports). For each failure: read the traceback, check if branch changes could affect the failing path, and report whether it's likely related or confirmed unrelated (rerun in isolation 2-3 times to verify)
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
