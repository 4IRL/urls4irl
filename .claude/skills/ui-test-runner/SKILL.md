---
name: ui-test-runner
description: When asked to run UI tests for URLS4IRL, this skill will be used.
argument-hint: Marker Name
---

UI tests are run through the u4i-local-web container.

1. Find all UI test markers listed in @pytest.ini.  Any UI test set will have a marker ending in *_ui.
2. If the user passes a specific marker to run, then run this marker: **$0**_ui. 
3. You can run UI tests with the following command. Just replace #MARKER with the actual marker.

  ```bash
  `docker exec u4i-local-web /bin/bash "source /code/venv/bin/activate; pytest -m '#MARKER' -x"`
  ```

4. Verify the tests run.
5. Check for any failures.
6. Report any test failures to the user with relevant error lines from the test
7. Investigate the test failures and hypothesize why they are occurring


### NOTE - You MUST run one of the markers ending in _ui.
