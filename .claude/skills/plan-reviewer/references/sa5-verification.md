# Subagent 5: Verification & Test Coverage

**Role:** Ensure each step has sufficient, layer-appropriate verification.

**What to read:** The plan's verification commands, test files referenced in the plan, `pytest.ini` / `Makefile` for available markers and targets, and — when the plan defines any explicit header dict, login fixture, or test-client helper for test code — the definition of the test client class and login fixtures to verify the plan's setup is not redundant with what the fixture already provides automatically (e.g., `AjaxFlaskLoginClient` auto-injects `X-Requested-With: XMLHttpRequest`).

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
- **vi.hoisted mock factory shape verification (required for any plan test block using vi.mock + vi.hoisted):** When a plan's test code block uses `vi.hoisted(() => ({ ... }))` to produce a factory for `vi.mock`, verify that calling the factory function returns an object whose keys match the mocked module's exported names. A bare `vi.fn()` stored as the factory and then called as `vi.mock('path', () => mockFn())` returns `undefined` — not a module-shape object — making every import from the mock `undefined` and silently voiding all assertions on those imports. The correct pattern is `vi.hoisted(async () => await import('../../__tests__/helpers/mock-metrics-client.js'))` or an inline object factory `vi.hoisted(() => ({ emit: vi.fn() }))`. Flag any bare `vi.fn()` used as a `vi.mock` factory as **Major**.

- **Named test helper/fixture existence requires a file read (required):** Any claim that a named test helper, fixture, or utility function exists or is absent in a test file MUST be backed by an actual Read or Grep of that file. Never assert existence or absence from plan prose, from another reviewer's claim, or from memory. If the plan names a helper (e.g., `wait_then_get_at_least_n_elements`), grep for it in the specified file before writing any finding or conditional fallback that depends on its presence or absence.

- **Red-phase test count consistency (required):** When a step's Red sub-phase has a verification command of the form "confirm N tests fail" (or matching Green-phase form "confirm N tests pass"), count the test-case specifications defined in that same Red block and verify the count equals N. If they differ, flag as **Critical**. When a prior review pass added a new test case to a Red block, the "confirm N tests fail/pass" number must have been updated atomically across both Red and Green phases — if it was not, the count is stale regardless of which pass introduced the test case.

- **Final test suite phase (required)**: The last phase must include `make test-integration-parallel` and `make test-ui-parallel-built`. Flag as **Critical** if either is missing.

- **Verification sufficiency**: Are the verification steps actually sufficient to catch regressions?

- **Deferred verification gaps**: When a step's verification depends on a file that can only be deployed manually (e.g., CI workflow files), flag the gap and require a local verification alternative.

- **Failure path guidance**: Every verification command in the plan — including intermediate checks AND final test suites — must have at least one concrete failure-mode hint (likely error message + resolution). Flag any verification step that lacks this.

- **Test assertion falsifiability (required):** For each negative test assertion (e.g., `assert key not in dict`), verify that the assertion targets the exact dict/field that the implementation would populate — not a parent container. An assertion on a parent dict passes trivially if the key is only ever inserted at a child level. Flag as **Major** if a negative assertion would pass even if the implementation is broken.
