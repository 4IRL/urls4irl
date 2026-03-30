---
name: ui-test-runner
description: When asked to run UI tests for URLS4IRL, this skill will be used.
argument-hint: Marker Name
---

UI tests are run against pre-built Vite assets using make targets.

1. Find all UI test markers listed in @pytest.ini. Any UI test set will have a marker ending in *_ui.
2. If the user passes a specific marker to run, then run this marker: **$0**_ui.
3. Run UI tests using the built make target. Replace MARKER with the actual marker:

  ```bash
  make test-marker-parallel-built m=MARKER
  ```

  This runs `start-built` (tears down stack, rebuilds with pre-built Vite assets) then runs the tests. Always use built targets for UI tests — never the dev server.

4. Verify the tests run.
5. Check for any failures.
6. Report any test failures to the user with relevant error lines from the test.
7. Investigate the test failures and hypothesize why they are occurring.

### NOTE - You MUST run one of the markers ending in _ui.
