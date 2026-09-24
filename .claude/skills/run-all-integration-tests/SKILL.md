---
name: run-all-integration-tests
description: Run ALL non-UI tests (integration and unit tests) for URLS4IRL in parallel. Use when asked to run all integration tests, run the full test suite excluding UI tests, or verify all backend/unit tests pass. Records failures to /tmp/claude/ with timestamped files; cleans up on full success.
---

# Run All Integration Tests

Run all non-UI tests in parallel using `make test-integration-parallel`, recording failures and cleaning up on success.

## Procedure

### 1. Setup

```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="/tmp/claude/INTEGRATION_${TIMESTAMP}_output.txt"
FAILURE_FILE="/tmp/claude/INTEGRATION_${TIMESTAMP}_failures.txt"
```

### 2. Run All Tests in Parallel (preferred)

Capture all output to the raw output file:
```bash
make test-integration-parallel > "$OUTPUT_FILE" 2>&1
```

This runs every marker not excluded by the target's hardcoded `not <marker>_ui …` expression in the `Makefile`, in parallel within a single pytest invocation, using the target's default worker count. **Before running**, compare the `_ui` markers in `pytest.ini`'s `markers =` list against that exclusion list; if any is missing from the `Makefile`, report the mismatch to the user first (that UI marker would otherwise run here, against the dev stack).

**Fallback (sequential):** Only use if the parallel run produces unexplained errors unrelated to test logic (e.g., port conflicts, DB corruption). Run each marker one at a time, appending to the output file:

Markers: read the `markers =` list in `pytest.ini` at runtime and run every marker that does not end in `_ui`, in the order listed there. Do not rely on a remembered list; markers are added over time.

```bash
make test-marker-parallel m=MARKER >> "$OUTPUT_FILE" 2>&1
```

- Wait for each suite to complete before starting the next
- Continue to the next marker regardless of pass/fail

### 3. On Completion

Read `$OUTPUT_FILE` to check for failures.

**If any failures occurred:**
- Extract the failure summaries and stack traces from `$OUTPUT_FILE` and write them to `$FAILURE_FILE`
- **Investigate every failure** — never dismiss a failure as "pre-existing" or "flaky" because the test file wasn't modified on the current branch. Current changes can break tests indirectly (shared fixtures, CSS/selector changes, templates, timing, imports). For each failure: read the traceback, check if branch changes could affect the failing path, and report whether it's likely related or confirmed unrelated (rerun in isolation 2-3 times to verify)
- Report which tests failed with a stack trace snippet showing the root cause
- Reference `$FAILURE_FILE` for the full failure details

**Always** delete the raw output file when done:
```bash
rm -f "$OUTPUT_FILE"
```
