---
name: test-failure-logger
description: Automatically log test failures to timestamped files in tmp/ directory. Use this skill EVERY TIME a test failure is encountered during development, testing, or CI/CD workflows. Captures test name, timestamp, likely cause analysis, and stack trace snippets. Critical for tracking test failures across feature development and debugging sessions.
---

# Test Failure Logger

Automatically capture and log test failure information whenever tests fail.

## When to Use

**CRITICAL**: Use this skill EVERY TIME you encounter a test failure, regardless of other tasks. Test failure tracking is essential to feature development and debugging.

Triggers include:
- pytest failures
- UI/functional test failures (Selenium, Playwright)
- Integration test failures
- Any test suite execution that encounters failures

## Workflow

When a test fails:

1. **Extract failure information**:
   - Test name/path (e.g., `tests/functional/splash_ui/test_reset_password_ui.py::test_reset_password_success`)
   - Likely cause (brief analysis: "Missing element on page", "API returned 500", "Database connection timeout")
   - Stack trace snippet (the relevant error lines, not the full trace)

2. **Log the failure**:
   ```python
   python .claude/skills/test-failure-logger/scripts/log_test_failure.py \
     "test_name" \
     "likely_cause" \
     "stack_trace_snippet"
   ```

3. **Continue with your task** - The failure is now logged for future reference

## Output

Creates timestamped JSON files in `tmp/` directory:
- Filename pattern: `test_failure_YYYYMMDD_HHMMSS_<sanitized_test_name>.json`
- Contains: test name, ISO timestamp, likely cause, stack trace, optional context

## Example

```bash
python .claude/skills/test-failure-logger/scripts/log_test_failure.py \
  "tests/functional/splash_ui/test_login.py::test_login_invalid_credentials" \
  "Assertion failed - expected error message not displayed" \
  "AssertionError: assert False where False = <element>.is_displayed()"
```

## Integration with Workflows

- **During active development**: Log failures immediately when encountered
- **After test runs**: Log all failures from the test output
- **CI/CD failures**: Log the specific test that caused the build to fail
- **Debugging sessions**: Log failures as you investigate them

## Cleanup

Logged failures in `tmp/` are temporary and can be cleared when:
- The issue is resolved and verified
- Starting a fresh development cycle
- The information is no longer relevant

Run `rm tmp/test_failure_*.json` to clear all logged failures.
