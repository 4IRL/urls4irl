---
name: run-all-ui-tests
description: Run ALL UI tests for URLS4IRL in parallel against the built assets. Use when asked to run all UI tests, run the full UI test suite, or verify all functional/Selenium tests pass. Records failures to /tmp/claude/ with timestamped files; cleans up on full success.
---

# Run All UI Tests

Run all UI tests in parallel against built assets using `make test-ui-parallel-built`, recording failures and cleaning up on success.

## Procedure

### 1. Setup

```bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="/tmp/claude/UI_${TIMESTAMP}_output.txt"
FAILURE_FILE="/tmp/claude/UI_${TIMESTAMP}_failures.txt"
```

### 2. Run All Tests in Parallel (preferred)

Capture all output to the raw output file:
```bash
make test-ui-parallel-built > "$OUTPUT_FILE" 2>&1
```

`test-ui-parallel-built` calls `start-built` which stops any running stack and brings up the built stack before running tests. It runs all UI markers (`splash_ui`, `home_ui`, `utubs_ui`, `members_ui`, `urls_ui`, `create_urls_ui`, `update_urls_ui`, `tags_ui`, `mobile_ui`) in parallel within a single pytest invocation. Default `-n 12` workers.

**Fallback (sequential):** Only use if the parallel run produces unexplained errors unrelated to test logic (e.g., Selenium session conflicts, container instability). Run each marker one at a time, appending to the output file:

Markers in order: `splash_ui`, `home_ui`, `utubs_ui`, `members_ui`, `urls_ui`, `create_urls_ui`, `update_urls_ui`, `tags_ui`, `mobile_ui`

```bash
docker exec u4i-local-web /bin/bash -c "source /code/venv/bin/activate && pytest -m 'MARKER'" >> "$OUTPUT_FILE" 2>&1
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
