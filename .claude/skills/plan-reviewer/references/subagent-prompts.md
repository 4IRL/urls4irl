# Plan Review Subagent Prompts

Each subagent receives the plan file path and must independently read the plan and relevant source files. All subagents return a structured JSON response.

## Response Format (all subagents)

> **File delivery:** Write your complete JSON response to the file path provided in your prompt (`plans/<topic>/tmp/<role>.md`), then return only this one-line confirmation: `Written to <path>`. The orchestrator will read the file. The JSON structure below is unchanged.

```json
{
  "verdict": "PASS" | "FAIL",
  "findings": [
    {
      "severity": "critical" | "major" | "minor",
      "step": "Step N",
      "file": "path/to/file (if applicable)",
      "title": "Short finding title",
      "description": "What's wrong, why it matters, and what the plan should say instead",
      "category": "correctness | full-stack-trace | ordering | integration | verification | completeness",
      "fix_type": "mechanical | design_decision",
      "fix_description": "Exact edit to make (for mechanical) or description of the decision needed (for design_decision)",
      "design_options": ["option A", "option B"]
    }
  ],
  "files_read": ["list of files actually read during review"],
  "summary": "One-line summary of the review"
}
```

### fix_type Classification Rules

Every finding MUST include a `fix_type`. Use these rules to classify:

**`mechanical`** — the fix is unambiguous and has exactly one correct resolution:
- Adding/keeping an import that is demonstrably used (grep confirms call sites exist)
- Removing an import that is demonstrably dead (grep confirms zero remaining usages)
- Fixing a plan self-contradiction (plan says "remove X" in one step and "use X" in another)
- Correcting a factual claim (plan says "function is at line 50" but it's at line 72)
- Cleaning up stream-of-consciousness / self-correcting notes into direct instructions
- Adding a missing file/function to a step when the plan already covers every other consumer of the same interface change
- Changing "optional" to "required" for cleanup of verified dead code
- Adding `make vite-build` or similar standard verification to a step that lacks any

For `mechanical` findings, `fix_description` must contain the exact edit: what text to find, what to replace it with, or what to add and where. `design_options` should be omitted or empty.

**`design_decision`** — multiple valid approaches exist and the choice affects behavior, architecture, or user experience:
- Choosing between refactoring a function vs. creating a wrapper/adapter
- Deciding whether to merge steps, reorder steps, or add a "commit together" note
- Choosing which modal/component should own an event handler
- Deciding whether to add new tests vs. relying on existing test coverage
- Choosing between keeping backward compatibility vs. clean break
- Any fix that changes control flow, event binding, or runtime behavior

For `design_decision` findings, `fix_description` must describe the decision needed. `design_options` must list at least 2 concrete options with enough detail to evaluate trade-offs.

**Default to `design_decision`** when uncertain. The cost of asking is low; the cost of a bad auto-applied fix is high.

**Bright-line rules (always `design_decision` regardless of how obvious the fix seems):**
- Any change to function signatures or parameter ordering
- Any change to event handler binding/unbinding
- Any change to step ordering or step merging
- Any change that adds or removes a test requirement
- Any change to error handling behavior or user-facing messaging

Rules:
- `FAIL` if any `critical` or `major` finding exists
- `PASS` if only `minor` findings or none
- Every finding must cite a specific step number and file path where applicable
- Do not fabricate findings — if the plan is clean for your area, return PASS with empty findings
- **Verify before writing.** If you are about to write "the fix is X," read the file X touches first. A fix stated from memory or reasoning alone can introduce a new error worse than the original.
- **Do not trust plan assertions.** Plans often state preconditions as fact ("CSRF is already handled," "this import exists"). For every such assertion in your review area, trace the claim to its source file and verify it holds.

---

## Subagent 1: Correctness & Accuracy

**Role:** Verify that the plan's claims match the actual codebase.

**What to read:** Every source file the plan references (file paths in to-do items, modified/deleted file lists). For each file, focus on imports, function signatures, class definitions, decorator stacks, and data shapes.

**Review checklist:**
- Do proposed changes match the actual API/interface of the code they touch?
- Are import paths, function signatures, and data shapes accurate as stated in the plan?
- Does the plan delete or modify things that other modules depend on? Grep for usages of any deleted/renamed symbol.
- Are type annotations correct per the codebase's actual types?

**Pydantic specifics (apply whenever the plan defines or modifies Pydantic schemas):**
- **Cross-field validators**: if a validator reads `info.data.get("field")` and that field has its own validation, verify the guard `if "field" not in info.data: return value` is present. Pydantic v2 omits failed fields from `info.data`, so without the guard a spurious second error fires.
- **`from_attributes=True` factories**: verify that ORM attribute names match schema *field names* (not aliases). If they differ, `model_validate(orm_obj)` raises `AttributeError`.
- **Alias completeness**: if any field in a schema uses `Field(alias=...)`, ALL fields must have explicit alias declarations. Partial alias specs cause silent `model_validate` failures.
- **Error-handling pattern**: `try/except ValidationError -> log` swallows schema drift. Schema validation calls must be bare (no try/except) so `ValidationError` propagates as a 500.

**Transitive reads (required):** When a plan modifies a function, also read what that code calls — one level of callees. Plans frequently miss helper signatures, conditional guards, and indirect dependencies.

---

## Subagent 2: Full-Stack Trace

**Role:** For every endpoint the plan modifies, trace the complete request/response cycle by reading actual code.

**What to read:** For each touched endpoint: the route handler, its decorators, the service function + private helpers (one level deep), the frontend JS that calls the endpoint (read ALL JS files in the module directory, not just ones the plan names), and the HTML template that renders the form/page.

**Review checklist — Request path (check each link):**

1. **JS serialization**: What `data:` format does the current JS send (`serialize()`, `JSON.stringify`, etc.)? What does the plan change it to? Does the format change land in the **same step** as the backend format change? A gap where the browser sends the old format to a new backend is a **Major** finding.

2. **CSRF token delivery (full trace required)**:
   - **Source**: Read the template that renders the token (meta tag, hidden input, cookie). Check for conditional guards (`{% if auth %}`, feature flags). Verify the condition is True for every user state hitting this endpoint (unauthenticated, authenticated-not-validated, authenticated-validated, test clients).
   - **Reader**: Read the JS that extracts the token. Confirm the DOM element or cookie it reads actually exists in the rendered page for all user states.
   - **Transport**: Confirm the token reaches the server (header, body, cookie) and that Flask-WTF checks that location.
   - If the plan asserts "CSRF is already handled," **do not accept this at face value** — trace it yourself.

3. **Route method + decorators**: What HTTP method(s) does the route accept? What decorators wrap it and in what order? Does the plan's decorator placement match the required stack?

4. **Service function + private helpers**: For every helper the service calls, if the public function's signature changes, does the plan also update the helper's signature and internal uses? Flag any missed helper as **Major**.

**Review checklist — Response path (check each link):**

5. **Status codes after migration**: List every status code the endpoint can return after migration. Compare to before.

6. **JS failure handler dispatch**: For each status code, does the JS failure handler branch correctly? A handler still checking an old status code after the backend changes falls to the `else` branch and silently discards errors. Flag as **Major**.

7. **`handleImproperFormErrors` field key alignment**: Do the keys in the service's `errors` dict match the `case` labels in the handler's switch? Those keys must match `id` attributes on `<input>` elements (camelCase). A mismatch silently discards the error.

---

## Subagent 3: Ordering, Dependencies & Cleanup

**Role:** Verify step sequencing, intermediate state safety, and cleanup correctness.

**What to read:** The plan in full, plus lint config files (`tox.ini`, `.flake8`, `pyproject.toml`, `.eslintrc`) and any files where the plan defers deletion or cleanup to a later step.

**Review checklist:**

- **Step sequencing**: Are steps ordered so each prerequisite is done before its consumer? Would executing steps out of order cause failures?

- **Intermediate state (required)**: For every step, verify the application is fully working after that step completes — not just at the end of the plan. Any gap where an endpoint is silently broken between steps is a **Major** finding, even if integration tests pass.

- **Deferred cleanup commit gate (required)**: For any symbol (import, function, export, variable) that becomes unused partway through but is only removed later, verify lint config does not enforce a rule blocking the intermediate commit. Common blockers: F401 (unused Python import), `no-unused-vars` (JS). If active, cleanup must move into the same step that makes the symbol unused.

- **Dead import analysis (required for every deletion)**: When a step deletes a function/class/helper or changes a return expression, perform a full transitive import scan:
  1. List every symbol the deleted code uses from imports
  2. Grep the file for remaining usages excluding the deleted code
  3. If no other usage exists, that import is dead and must be removed in the **same step**
  Common misses: `typing` imports used only in deleted helpers, `render_template` whose sole call is deleted, utility functions called only by deleted code, string constants referenced only in deleted branches, `request` whose sole usage was removed.

- **Forward references**: No to-do item should reference a function/class that doesn't exist yet and isn't created in the same or earlier step.

---

## Subagent 4: Codebase Integration & Conventions

**Role:** Verify the plan follows project patterns and CLAUDE.md rules.

**What to read:** CLAUDE.md, ARCHITECTURE.md (if referenced), and a sample of files in the same module as the plan's changes to confirm pattern alignment. Also read requirements files if the plan adds packages.

**Review checklist:**

- **Project patterns**: Does the plan follow established patterns (test structure, naming, module conventions)? Are new files placed in the right directories per project architecture?

- **CLAUDE.md rules**:
  - No window globals for module communication
  - Use typehints — no shortcuts
  - Never use quoted type hints (files use `from __future__ import annotations`)
  - Never use single-letter variable names — all variables must be descriptively named
  - No relative imports — always use absolute paths like `from backend.schemas.requests._sanitize import ...`

- **Import ordering**: Three groups (stdlib, third-party, project), each alphabetized internally, separated by blank lines.

- **Package additions** (if applicable):
  - Use exact pin (`==`) not ranges (`>=`, `~=`, `<`)
  - Pin transitive dependencies
  - Place in correct requirements file: runtime in `requirements-prod.txt`, test-only in `requirements-test.txt`, dev/tooling in `requirements-dev.txt`

- **Config consistency**: Env vars, lint rules, and CI config aligned with plan changes.

- **Test markers**: Are markers correct per `pytest.ini`? Are new markers needed?

---

## Subagent 5: Verification & Test Coverage

**Role:** Ensure each step has sufficient, layer-appropriate verification.

**What to read:** The plan's verification commands, test files referenced in the plan, and `pytest.ini` / `Makefile` for available markers and targets.

**Review checklist:**

- **Verification exists**: Does each step have a clear way to verify success (a command to run, a behavior to observe)? Note any steps that lack verification and suggest what to add.

- **Layer-match check (required)**: For each verification step, confirm the test type exercises the layer the change affects. Common mismatches to flag as **Major**:
  - Template/HTML changes verified only by integration tests (`client.post()`/`client.get()`) — these bypass the browser; need UI tests or Playwright
  - JS behavior changes verified only by integration tests — need JS unit tests (vitest) or UI/Selenium tests
  - Backend-only changes verified only by UI tests — integration tests are faster and more precise
  If a step changes templates or JS and the only verification is `make test-marker-parallel`, flag it and recommend adding `make test-js` and/or the relevant `_ui` marker test.

- **Test coverage**: Happy path, sad path, and edge case tests exist for every changed endpoint? Missing edge case coverage?

- **Final test suite phase (required)**: The last phase must include `make test-integration-parallel` and `make test-ui-parallel-built`. Flag as **Critical** if either is missing.

- **Verification sufficiency**: Are the verification steps actually sufficient to catch regressions?

---

## Subagent 6: Completeness, Risk & Specificity

**Role:** Identify gaps, risks, and underspecified steps.

**What to read:** The full plan, plus any files where the plan's specificity claims can be checked (schema definitions, factory methods, template structures).

**Review checklist:**

- **Edge cases & completeness**: What scenarios are not covered (empty state, error paths, boundary conditions)? Race conditions, async timing issues, or state management gaps?

- **Implementation specificity**: For every step that defines or modifies a class, function, schema, or template:
  - Does the plan provide enough detail (exact field definitions, method bodies, variable extraction instructions, explicit code patterns) for an implementer to execute without additional research?
  - Flag any step where a developer would need to "figure out" details the plan leaves unstated (factory method bodies, full alias declarations, explicit variable extraction, required refactors). These are **Major** findings.
  - Partial specifications are not acceptable: if a schema has five fields and only one has `Field(alias=...)`, the other four are underspecified even if "derivable."

- **Risk & reversibility**: Which steps are hard to undo (file deletions, DB migrations, API contract changes)? Steps that could break CI or affect shared infrastructure?

- **Cleanup**: Does the plan handle cleanup of temp files, test fixtures, orphaned imports?

- **Breaking changes**: API contracts, shared state, DB schema, cross-module dependencies — does the plan account for all consumers?
