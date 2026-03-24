---
name: review-plan
description: Review a plan file as a staff engineer, checking for inconsistencies, edge cases, technicalities, and integration with the existing codebase. Use when asked to review, critique, or audit a plan. The plan name is inferred from the argument (e.g., "/review-plan selenium-to-js-unit-tests"). Creates or updates a review document in the plans/reviews/ directory. Presents findings and a to-do list, then waits for user confirmation before making any changes.
argument-hint: Plan-name
---

# Plan Review Skill

Adopt the role of a **staff engineer** performing a thorough code review of a planning document. Be critical, specific, and actionable.

## Workflow

### Step 1: Locate the Plan

- Search `plans/` for a file matching **$0** (fuzzy match on filename)
- Read the full plan document
- Note: plan files live at `plans/<name>.md`

### Step 2: Read Relevant Source Files

Before reviewing, read every source file the plan references (file paths in to-do items, modified/deleted file lists, etc.). This grounds the review in reality — catch issues that only appear when the plan meets actual code.

**Use sub-agents for file reads:** Launch Explore sub-agents to read and summarize source files referenced in the plan. Group files by concern (e.g., "backend routes and services," "frontend JS files," "test fixtures and configs," "templates"). Each sub-agent should report only plan-relevant details: imports, function signatures, conditional guards, decorator stacks, AJAX data formats, error handler dispatch, and template field IDs. Do not bring back full file contents — only findings that could contradict or confirm the plan's claims. Run sub-agents in parallel where possible to maximize efficiency.

**Verify plan assertions (required):** Plans often state preconditions as fact (e.g., "CSRF is already handled," "the token is available globally," "this import exists"). For every such assertion, trace the claim to its source file and verify it holds for all relevant contexts (user states, test clients, intermediate migration steps). A plan assertion that was true before migration may become false after the plan's own changes. Do not accept any "already handled" claim without reading the code that handles it.

**Transitive reads (required):** When a plan modifies a function or template, also read what that code calls. One level of callees is usually enough — if function A is being changed and it calls helper B, read B. Plans frequently miss helper signatures, conditional guards, and indirect dependencies that only appear when you follow the call chain.

**Read ALL frontend files for the module, not just the ones explicitly named:** If a plan touches any route or endpoint in a module (e.g., `splash`), read every JS file in the corresponding frontend directory (e.g., `frontend/splash/*.js`). Individual steps often name only the file they change, but the request-serialization format, failure-handler status codes, and field IDs in *other* files in the same module are equally affected. Do not stop at the files the plan explicitly lists.

**Conditional guards:** When reading templates, config files, or middleware, look for `if` conditions that gate availability of values (auth state, feature flags, session state, user roles). Trace whether the condition is satisfied in all contexts the plan assumes — especially test contexts (unauthenticated clients, unvalidated users, etc.).

**Linting / CI config (required when the plan defers cleanup to a later step):** If the plan stages cleanup — unused imports, dead helpers, orphaned exports — across multiple steps (e.g., "remove in Step 7"), read the linting config (`tox.ini`, `.flake8`, `pyproject.toml`, `.eslintrc`, etc.) before concluding that intermediate commits are safe. Rules like F401 (unused imports) are often active but not obvious from the plan alone. A plan that defers removing an import until Step 7 will block every commit from Step 2 onward if F401 is enforced.

### Step 3: Review the Plan as a Staff Engineer

**Do not defer any dimension to a follow-up pass.** Every category below must be evaluated before writing findings. A review that defers error-handling patterns, detail specificity, or intermediate state to a "follow-up pass" is incomplete. If you run out of findings in one dimension, continue to the next — do not stop after the first dimension that yields issues.

Evaluate across these dimensions. Be specific — cite step numbers and file names.

#### Correctness
- Do the proposed changes match the actual API/interface of the code they touch?
- Are import paths, function signatures, and data shapes accurate?
- Does the plan delete or modify things that other modules depend on?
- **Verify proposed fixes before writing them down.** If you are about to write "the fix is X," read the file X touches first. A fix stated from memory or reasoning alone, without reading the code, can introduce a new error worse than the original. This is how prior-review fixes slip through into new critical findings.

**Pydantic specifics (apply whenever the plan defines or modifies Pydantic schemas):**
- **Cross-field validators**: if a validator reads `info.data.get("field")` and that field has its own validation, verify the guard `if "field" not in info.data: return value` is present. Pydantic v2 omits failed fields from `info.data`, so without the guard `value != None` is always `True` for any typed string — a spurious second error fires even when the user entered matching values that were simply invalid.
- **`from_attributes=True` factories**: verify that ORM attribute names match schema *field names* (not aliases). If they differ, `model_validate(orm_obj)` will raise `AttributeError`; the factory must use explicit construction: `cls(field=obj.attr, ...)`.
- **Alias completeness**: if any field in a schema uses `Field(alias=...)`, ALL fields in that schema must have explicit alias declarations. Partial alias specs cause silent `model_validate` failures on any field without a matching alias key in the input dict.
- **Error-handling pattern**: `try/except ValidationError → log` swallows schema drift and makes integration tests pass when they should fail. Schema validation calls must be bare (no try/except) so `ValidationError` propagates as a 500 and tests catch drift immediately.

#### Per-Endpoint Full-Stack Trace (required for any plan touching routes or AJAX calls)

For **every endpoint** the plan modifies, trace the complete request/response cycle by reading the actual code. Do this as an explicit loop — enumerate each endpoint, then check each link in sequence. Do not infer; read the files.

**Request path — check each link:**

1. **JS serialization**: What `data:` format does the current JS send (`serialize()`, `JSON.stringify`, etc.)? What does the plan change it to? Does that change land in the **same step** as the backend format change? If the backend switches to JSON-only in Step N but the JS change is in Step M (M > N), the endpoint silently returns 400 with no field errors in the browser for all steps between N and M — integration tests won't catch this because they send the new format directly. Flag as **Major**.

2. **CSRF token delivery (full trace required)**: After the migration, how is the CSRF token sent? Is it covered by a global `$.ajaxSetup` hook, or was it previously embedded in the form body via `hidden_tag()`? If the form body is being replaced with JSON, perform a **complete CSRF delivery trace** — do not stop at "the global hook exists":
   - **Source**: Read the template that renders the token (e.g., a `<meta>` tag, a hidden input, a cookie). Check for conditional guards (`{% if auth %}`, feature flags, user state). Verify the condition is **True** for every user state that hits this endpoint (unauthenticated, authenticated-not-validated, authenticated-validated, test clients).
   - **Reader**: Read the JS that extracts the token. Confirm the DOM element or cookie it reads actually exists in the rendered page for all user states identified above. If the reader runs once at page load (e.g., `setupCSRF()` captures the value in a closure), verify the value is not `undefined` at that point.
   - **Transport**: Confirm the token reaches the server — header, body field, or cookie — and that Flask-WTF (or equivalent) checks that location.
   - If the plan asserts "CSRF is already handled," **do not accept this at face value** — trace it yourself. Plans that change the request format (form-encoded → JSON) can silently break CSRF even when the CSRF mechanism itself is unchanged.

3. **Route method + decorators**: What HTTP method(s) does the route accept after the split? What decorators wrap it (auth, `@parse_json_body`, etc.) and in what order? Does the plan's decorator placement match the required stack (innermost = closest to function)?

4. **Service function + all private helpers (one level deep)**: What private helpers does the service function call? For every helper, if the public function's signature changes (e.g., `public_fn(form)` → `public_fn(value: str)`), does the plan also update that helper's signature and all internal uses of the old parameter? A plan that changes the public function but forgets a private helper that calls `form.get_field()` will fail with `AttributeError` at runtime. Flag any missed helper as **Major**.

**Response path — check each link:**

5. **Status codes after migration**: List every status code this endpoint can return after migration. Compare to what it returned before.

6. **JS failure handler status code dispatch**: For each status code, does the JS failure handler branch correctly? If the backend changed from returning 401 → 400 for validation errors, did the `if (xhr.status === ...)` check in the handler change in the **same step**? A handler still checking 401 after the backend returns 400 falls to the `else` branch and silently discards field errors. Flag as **Major**.

7. **`handleImproperFormErrors` field key alignment**: For any endpoint returning field-level errors, do the keys in the service's `errors` dict match the `case` labels in `handleImproperFormErrors`'s switch? Those keys must match the `id` attributes on the corresponding `<input>` elements (camelCase). A mismatch silently discards the error — the field is never highlighted.

#### Ordering & Dependencies
- Are steps sequenced so each prerequisite is done before its consumer?
- Would executing steps out of order cause failures?
- **Intermediate state (required check):** For every step in the plan, verify the application is in a fully working state after that step completes — not just at the end of the plan. Any gap where an endpoint is silently broken between steps is a **Major** finding, even if all integration tests pass.
- **Deferred cleanup commit gate (required check):** For any symbol (import, function, export, variable) that becomes unused partway through the plan but is only removed in a later cleanup step, verify the linting config does not enforce a rule that would block the intermediate commit. Read `tox.ini` / `.flake8` / `pyproject.toml` / `.eslintrc` to confirm. Common blockers: F401 (unused Python import), `no-unused-vars` (JS). If a rule is active, the cleanup must move into the same step that makes the symbol unused — not deferred.
- **Dead import analysis (required for every deletion):** When a step deletes a function, class, or helper — or changes a return expression (e.g., `render_template(...)` → `APIResponse(...)`) — perform a **full transitive import scan** of the affected file. For every symbol the deleted/changed code used (standard library types, framework functions, project utilities, string constants, model classes), grep the file for remaining usages *excluding* the deleted code. If no other usage exists, that import is dead and must be removed in the **same step** — not deferred. This is a single-pass mechanical check; do not split it across review rounds. Common misses: `typing` imports (`Sequence`, `cast`) used only in deleted helpers; `render_template` whose sole call site was the deleted success response; utility functions (`build_form_errors`) called only by deleted form-error handlers; string constants (`EMAILS`) referenced only in deleted conditional branches; `request` whose sole usage was a `request.method` check removed by a GET/POST split.

#### Edge Cases & Completeness
- What scenarios are not covered? (empty state, error paths, boundary conditions)
- Are there race conditions, async timing issues, or state management gaps?
- Does the plan handle cleanup (temp files, test fixtures, orphaned imports)?

#### Codebase Integration
- Does the plan follow established project patterns (test structure, naming, module conventions)?
- Are new files placed in the right directories per the project architecture?
- Does it respect CLAUDE.md rules (no window globals, typehints, cleanup of debug code)?
- Are test markers correct per `pytest.ini`? Are new markers needed?

#### Package Additions
If the plan introduces new Python packages, flag any that:
- Use a version range (`>=`, `~=`, `<`) instead of an exact pin (`==`)
- Are missing transitive dependency pins (new deps not already in any requirements file)
- Are placed in the wrong requirements file — runtime deps belong in `requirements-prod.txt`, test-only deps in `requirements-test.txt`, dev/tooling-only deps in `requirements-dev.txt`

#### Verification Steps
- Does each step have a clear way to verify success (a command to run, a behavior to observe)?
- Are the verification steps in the plan actually sufficient to catch regressions?
- Note any steps that lack verification and suggest what to add.
- **Layer-match check (required):** For each verification step, confirm the test type exercises the layer the change affects. Common mismatches to flag as **Major**:
  - Template/HTML changes (meta tags, conditional blocks, field IDs, hidden inputs) verified only by integration tests (`client.post()`/`client.get()`) — these bypass the browser; need UI tests or Playwright verification to confirm the rendered DOM is correct for all user states.
  - JS behavior changes (AJAX serialization, failure handler branches, DOM reads) verified only by integration tests — need either JS unit tests (vitest) or UI/Selenium tests.
  - Backend-only changes (service logic, DB queries, status codes) verified only by UI tests — integration tests are faster and more precise; UI tests should supplement, not replace.
  If a step changes templates or JS and the only verification is `make test-marker-parallel`, flag it and recommend adding `make test-js` and/or the relevant `_ui` marker test.
- **Final test suite phase (required for any plan touching code or tests):** The last phase must include `make test-integration-parallel` and `make test-ui-parallel-built`. Flag as **Critical** if either is missing.

#### Implementation Specificity

For every step that defines or modifies a class, function, schema, or template:
- Does the plan provide enough specific detail (exact field definitions, method bodies, variable extraction instructions, explicit code patterns) that an implementer can execute the step without additional research?
- Flag any step where a developer would need to "figure out" details the plan leaves unstated — e.g., factory method bodies, full alias declarations for all schema fields, explicit variable extraction before a validation call, or required refactors to existing call sites. These are **Major** findings.
- Partial specifications are not acceptable: if a schema has five fields and only one has `Field(alias=...)`, the other four are underspecified even if "derivable." Explicitness prevents implementer errors.

#### Risk & Reversibility
- Which steps are hard to undo (file deletions, DB migrations, API contract changes)?
- Are there steps that could break CI or affect shared infrastructure?

#### Coverage Checklist (required — fill out during review)

After completing all dimensions above, confirm each area was checked. Mark `[ ]` for any area you could not fully verify and explain why in the Notes column. This checklist is included in the review output.

| Area | What to verify |
|---|---|
| **Imports** | Dead imports after deletions, missing imports for new symbols, circular dependencies |
| **Type annotations** | New/changed functions have correct type hints per CLAUDE.md rules |
| **Error handling** | Status codes match JS handlers, exceptions propagate correctly, user gets feedback |
| **Test coverage** | Happy path, sad path, and edge case tests exist for every changed endpoint |
| **Breaking changes** | API contracts, shared state, DB schema, cross-module dependencies |
| **Config consistency** | Env vars, requirements pins, lint rules, CI config aligned with plan changes |
| **Naming conventions** | CLAUDE.md rules (no single-letter vars, no quoted hints, no window globals) |

### Step 4: Write or Update the Review Document

#### File location

In the project directory -
`reviews/<plan-name>-review.md` — create `reviews/` if it doesn't exist.

NOTE: This `reviews/` MUST be in the project directory, NOT in the same `plans/` folder as the plan being reviewed.

One file per plan. If a review file already exists, **append** a new dated review section; do not overwrite previous reviews.

**Re-verify prior review resolutions (required when appending):** When a review file already exists, read every to-do item from prior reviews that is marked `[x]` (resolved). For each one, re-read the **actual source file** the fix depends on — not just the plan text — and confirm the fix resolves the root cause in practice. "The plan now says X" is not verification; verification means the code/template/config file supports X. Prior reviewers can be wrong about whether a proposed fix works. A fix that changes the symptom without curing the disease (e.g., proposing `client.get("/")` to read a meta tag that is conditionally rendered and absent for the relevant user state) counts as unresolved. If a prior resolution is incorrect, re-open it as a new Critical finding with a reference to the prior review date.

#### Review file structure

```markdown
# Review: <Plan Name>

## Review — <YYYY-MM-DD>

### Summary
<2-3 sentence overall assessment: ready to proceed / needs changes / blocked.>

### Findings

#### Critical (must fix before proceeding)
- **[Step N] <Finding title>**: <Specific issue and why it matters.>

#### Major (should fix)
- **[Step N] <Finding title>**: <Specific issue and impact.>

#### Minor (nice to fix)
- **[Step N] <Finding title>**: <Suggestion.>

### Verification Gaps
Steps that lack sufficient verification:
- **Step N**: Suggest running `<command>` to verify `<behavior>`.

### To-Do: Required Changes
- [ ] <Specific, actionable fix — include file, function, line context>
- [ ] <Specific, actionable fix>

### Verdict
[ ] Ready to proceed as-is
[ ] Proceed after minor fixes
[x] Requires changes before proceeding

### Coverage Checklist
| Area | Checked? | Notes |
|---|---|---|
| Imports (dead, missing, circular) | [x] / [ ] | <files checked or why not verified> |
| Type annotations | [x] / [ ] | |
| Error handling (status codes, exceptions, user feedback) | [x] / [ ] | |
| Test coverage (happy path, sad path, edge cases) | [x] / [ ] | |
| Breaking changes (API contracts, shared state, DB schema) | [x] / [ ] | |
| Config consistency (env vars, requirements pins, lint rules) | [x] / [ ] | |
| Naming conventions (CLAUDE.md rules, project patterns) | [x] / [ ] | |

### Missed-Finding Root Causes (only when prior reviews exist)
| Finding | Root cause | Skill gap? |
|---|---|---|
| <finding> | <root cause category + details> | <skill gap or "Instructions already cover this"> |
```

If there are no findings in a category, omit that section.

### Step 5: Report and Wait for User Confirmation

Present a concise summary of findings to the user:
- Overall verdict
- Count of critical / major / minor findings
- The to-do list (if any)
- Path to the review file

**Then ask**: "Would you like me to apply any of these changes to the plan, or proceed as-is?"

**Do NOT apply changes to the plan or any source files without explicit user confirmation.**

### Step 6: Root-Cause Analysis of Missed Findings (when prior reviews exist)

**Skip this step if this is the first review for the plan.**

When appending a new review pass and the current pass found findings that prior passes missed, add a `### Missed-Finding Root Causes` section at the end of the review entry (after `### Verdict`). For each new finding, answer:

1. **What was missed?** — One-line summary of the finding.
2. **Why was it missed?** — Classify the root cause using one or more of these categories:
   - **Trusted plan assertion**: The plan stated something as fact (e.g., "CSRF is already handled") and the reviewer accepted it without independently tracing the claim through actual code.
   - **Incomplete file reads**: The reviewer only read files the plan explicitly names. The issue lives in a file the plan never references but that is on the critical path (e.g., a shared template, middleware, base config).
   - **Fix verification stopped at plan text**: A prior round proposed a fix, subsequent rounds confirmed the plan now "says X," but nobody re-read the actual source file to verify the fix's assumption holds in practice.
   - **Scoped too narrowly to plan-referenced code**: A review dimension (e.g., conditional guards, CSRF delivery, dead imports) was applied only to files/lines the plan explicitly touches, not to the broader system the plan depends on.
   - **Other**: Describe the root cause if none of the above fit.
3. **Skill gap**: Does the miss reveal a gap in the review-plan skill's instructions? If so, state what instruction is missing or insufficiently specific. If existing instructions already cover it (the reviewer just didn't follow them), say so — the fix is emphasis, not new rules.

**Format:**

```markdown
### Missed-Finding Root Causes

| Finding | Root cause | Skill gap? |
|---|---|---|
| CSRF meta tag gated behind auth | Trusted plan assertion ("CSRF is already handled") + Incomplete file reads (`meta.html` never read) | Existing CSRF section covers this but is disconnected from main Per-Endpoint trace; integrate into item 2 |
```

**How this feeds back:** After writing the root-cause table, check whether the skill gap column reveals a pattern. If the same root cause recurs across multiple reviews of different plans, propose a concrete addition or edit to the review-plan skill's instructions (in this SKILL.md) and present it to the user for approval. Do not self-modify the skill without user confirmation.

## Important Notes

- Read source files before concluding anything about correctness — don't assume
- Cite specific step numbers and file paths in every finding
- If the plan is already solid, say so clearly — a clean review is a useful result
- Multiple reviews of the same plan accumulate in one file (append, don't overwrite)
- The `plans/reviews/` directory may need to be created if this is the first review

## CSRF / Auth / Session specifics

When a plan touches authentication, form submission, or CSRF handling:
1. **Where is the token rendered?** Read the template. Check for conditional guards (`{% if ... %}`). Verify the condition is satisfied in all contexts: authenticated users, unauthenticated users, test clients.
2. **Where does the test get the token?** Read the fixture. Confirm the HTML response it parses actually contains the token in the form the fixture expects (hidden input vs. meta tag vs. cookie).
3. **Where does the frontend read the token?** Read the JS. Confirm the DOM element it targets exists in the rendered page for all user states.
