# Subagent 5: Verification & Test Coverage

**Role:** Ensure each step has sufficient, layer-appropriate verification.

**What to read:** The plan's verification commands, test files referenced in the plan, and `pytest.ini` / `Makefile` for available markers and targets.

**Review checklist:**

- **Verification exists**: Does each step have a clear way to verify success (a command to run, a behavior to observe)? Note any steps that lack verification and suggest what to add.

- **Type-check-only verification for rename steps (required):** When a step's only verification is `make vite-build` + `npm run typecheck` and the step renames a file from `.js` to `.ts`, flag as **Minor** if `make test-js` is not also included. Type-checking alone cannot catch runtime errors (e.g., missed export, bad cast that throws at runtime) that vitest would catch. If the plan defers all `make test-js` runs to a later step, note the step attribution gap: a runtime regression introduced in an earlier step will be undetectable until the later `test-js` run.

- **Layer-match check (required)**: For each verification step, confirm the test type exercises the layer the change affects. Common mismatches to flag as **Major**:
  - Template/HTML changes verified only by integration tests (`client.post()`/`client.get()`) — these bypass the browser; need UI tests or Playwright
  - JS behavior changes verified only by integration tests — need JS unit tests (vitest) or UI/Selenium tests
  - Backend-only changes verified only by UI tests — integration tests are faster and more precise
  If a step changes templates or JS and the only verification is `make test-marker-parallel`, flag it and recommend adding `make test-js` and/or the relevant `_ui` marker test.

- **Test coverage**: Happy path, sad path, and edge case tests exist for every changed endpoint? Missing edge case coverage?

- **Route path verification in tests (required):** When a test example names a specific route path (e.g., `spec['paths']['/utubs/{utub_id}/urls/{utub_url_id}']`), read the corresponding route file and confirm (a) the path is registered, and (b) all HTTP methods registered at that path are known. A path claimed to be GET-only that also has PATCH/DELETE will cause assertions like 'x-key absent on this path' to fail. Flag as **Major** if the test example path has methods the plan doesn't account for.

- **Final test suite phase (required)**: The last phase must include `make test-integration-parallel` and `make test-ui-parallel-built`. Flag as **Critical** if either is missing.

- **Verification sufficiency**: Are the verification steps actually sufficient to catch regressions?

- **Deferred verification gaps**: When a step's verification depends on a file that can only be deployed manually (e.g., CI workflow files), flag the gap and require a local verification alternative.

- **Failure path guidance**: Every verification command in the plan — including intermediate checks AND final test suites — must have at least one concrete failure-mode hint (likely error message + resolution). Flag any verification step that lacks this.

- **Test assertion falsifiability (required):** For each negative test assertion (e.g., `assert key not in dict`), verify that the assertion targets the exact dict/field that the implementation would populate — not a parent container. An assertion on a parent dict passes trivially if the key is only ever inserted at a child level. Flag as **Major** if a negative assertion would pass even if the implementation is broken.
