---
name: run-all-ui-tests
description: Run ALL UI tests for URLS4IRL sequentially. Use when asked to run all UI tests, run the full UI test suite, or verify all functional/Selenium tests pass. Records failures to tmp/ with timestamped files; cleans up on full success.
---

# Run All UI Tests

Execute all UI test markers sequentially, recording failures and cleaning up on success.

## UI Test Markers (from pytest.ini)

Run in this order:
1. splash_ui
2. home_ui
3. utubs_ui
4. members_ui
5. urls_ui
6. create_urls_ui
7. update_urls_ui
8. tags_ui
9. mobile_ui

## Procedure

### 1. Setup

Create tmp directory and set failure file path:
```bash
mkdir -p tmp
FAILURE_FILE="tmp/UI_$(date +%Y%m%d_%H%M%S)_failures.txt"
```

### 2. Run Each Marker Sequentially

For each marker above, run:
```bash
docker exec u4i-local-web /bin/bash -c "source /code/venv/bin/activate && pytest -m 'MARKER'"
```

- Wait for each test suite to complete before starting the next
- If tests fail, append marker name and failure summary to the failure file
- Continue to the next marker regardless of pass/fail

### 3. On Completion

**If any failures occurred:**
- Report which markers failed
- Reference the failure file: `tmp/UI_<timestamp>_failures.txt`
- MUST include a snippet of the stack trace indicating why the error occurred

**If ALL tests passed:**
- Remove all UI failure files:
```bash
rm -f tmp/UI_*
```
- Confirm success and cleanup
