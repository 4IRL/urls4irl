---
name: run-all-integration-tests
description: Run ALL non-UI tests (integration and unit tests) for URLS4IRL in parallel. Use when asked to run all integration tests, run the full test suite excluding UI tests, or verify all backend/unit tests pass. Records failures to tmp/ with timestamped files; cleans up on full success.
---

# Run All Integration Tests

Run all non-UI tests in parallel using `make test-integration-parallel`, recording failures and cleaning up on success.

## Procedure

### 1. Setup

```bash
mkdir -p tmp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="tmp/INTEGRATION_${TIMESTAMP}_output.txt"
FAILURE_FILE="tmp/INTEGRATION_${TIMESTAMP}_failures.txt"
```

### 2. Run All Tests in Parallel (preferred)

Capture all output to the raw output file:
```bash
make test-integration-parallel 2>&1 | tee "$OUTPUT_FILE"
```

This runs all non-UI markers (`unit`, `splash`, `utubs`, `members`, `urls`, `tags`, `account_and_support`, `cli`) in parallel within a single pytest invocation. Default `-n 4` workers.

**Fallback (sequential):** Only use if the parallel run produces unexplained errors unrelated to test logic (e.g., port conflicts, DB corruption). Run each marker one at a time, appending to the output file:

Markers in order: `unit`, `splash`, `utubs`, `members`, `urls`, `tags`, `account_and_support`, `cli`

```bash
docker compose --project-directory . -f docker/compose.local.yaml exec web bash -c "source /code/venv/bin/activate && python -m pytest -m 'MARKER'" 2>&1 | tee -a "$OUTPUT_FILE"
```

- Wait for each suite to complete before starting the next
- Continue to the next marker regardless of pass/fail

### 3. On Completion

Read `$OUTPUT_FILE` to check for failures.

**If any failures occurred:**
- Extract the failure summaries and stack traces from `$OUTPUT_FILE` and write them to `$FAILURE_FILE`
- Report which tests failed with a stack trace snippet showing the root cause
- Reference `$FAILURE_FILE` for the full failure details

**Always** delete the raw output file when done:
```bash
rm -f "$OUTPUT_FILE"
```
