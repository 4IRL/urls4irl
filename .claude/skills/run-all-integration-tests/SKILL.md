---
name: run-all-integration-tests
description: Run ALL non-UI tests (integration and unit tests) for URLS4IRL sequentially. Use when asked to run all integration tests, run the full test suite excluding UI tests, or verify all backend/unit tests pass. Records failures to tmp/ with timestamped files; cleans up on full success.
---

# Run All Integration Tests

Execute all non-UI test markers sequentially, recording failures and cleaning up on success.

## Integration Test Markers (from pytest.ini)

Run in this order:
1. unit
2. splash
3. utubs
4. members
5. urls
6. tags
7. account_and_support
8. cli

## Procedure

### 1. Setup

Create tmp directory and set failure file path:
```bash
mkdir -p tmp
FAILURE_FILE="tmp/INTEGRATION_$(date +%Y%m%d_%H%M%S)_failures.txt"
```

### 2. Run Each Marker Sequentially

For each marker above, run:
```bash
docker compose --project-directory . -f docker/compose.local.yaml exec web bash -c "source /code/venv/bin/activate && python -m pytest -m 'MARKER'"
```

- Wait for each test suite to complete before starting the next
- If tests fail, append marker name and failure summary to the failure file
- Continue to the next marker regardless of pass/fail

### 3. On Completion

**If any failures occurred:**
- Report which markers failed
- Reference the failure file: `tmp/INTEGRATION_<timestamp>_failures.txt`
- MUST include a snippet of the stack trace indicating why the error occurred

**If ALL tests passed:**
- Remove all INTEGRATION failure files:
```bash
rm -f tmp/INTEGRATION_*
```
- Confirm success and cleanup
