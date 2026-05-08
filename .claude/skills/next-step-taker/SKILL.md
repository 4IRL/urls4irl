---
name: next-step-taker
description: Execute the next step in a plan or apply the next item from a review. Use when asked to take the next step, continue a plan, or implement review feedback. The argument is a plan or review name (e.g., "/next-step-taker my-feature"). By default executes plan steps; when the user explicitly asks to implement review changes, applies review items instead.
argument-hint: Plan-or-review-name
---

# Next Step Taker Skill

This skill executes the next incomplete step from a plan OR applies the next pending item from a review file. It validates changes, updates tracking, and pauses for user confirmation before continuing.

## Branch Guard

Before starting, check the current branch:
1. If on `main` or `master`:
   - Run `gmas` to ensure main is up to date
   - Suggest a branch name based on the task context (e.g., `refactor/splash-validation`, `fix/login-error`)
   - Ask the user: "You're on main. Want me to create and switch to `<suggested-branch>`?"
   - Do NOT proceed until the user confirms and you've switched branches
2. If already on a feature branch: proceed normally

## Mode Selection

Determine the mode based on user intent:

- **Plan mode** (default): Execute the next incomplete phase/step from a plan document. Use this unless the user explicitly asks to implement review feedback.
- **Review mode**: Apply the next unchecked item from a review file. Use when the user says things like "implement the review changes", "apply the review", "work through the review feedback", or "next review item".

---

## Plan Mode Workflow

### Step 1: Locate the Plan
- Search for an existing plan by globbing `plans/**` relative to the project root, matching **$ARGUMENTS** contextually (e.g., `plans/**/<name>.md`). Derive the `<topic>` from the plan file's parent directory name.
- Read the plan document to understand the full context
- Identify the next incomplete step or phase (look for unchecked checkboxes: `- [ ]`)

### Step 2: Execute the Step
- Read all files mentioned in the current step before making changes
- Implement all changes specified in the step following existing code patterns
- Make edits, create files, or delete files as specified in the plan
- Follow CLAUDE.md guidelines (no window globals, clean up debug code, use typehints, etc.)

### Step 3: Validate the Changes
**CRITICAL: Always validate after execution.** Choose appropriate validation method(s).

**CRITICAL: All test suites MUST be run via a subagent** (using the Agent tool) to avoid context window bloat. The subagent runs the tests, captures output, and returns only a concise pass/fail summary with failure details. Never run test commands directly in the main context.

#### For JavaScript/Frontend Changes:
Run the Vite build via subagent:
- Task: "Run `make vite-build` and report pass/fail. On failure, include the full error output."
- Verify: No import errors, no missing exports, clean build output

#### For Template/Flask Changes:
- Verify Flask container starts without errors
- Check application logs for issues

#### For UI Changes (Selenium/Playwright Tests):
- If the plan specifies manual verification steps, list them for the user
- If specific UI tests are mentioned, delegate to a subagent:
  - Task: "Run UI tests for marker MARKER_NAME using `make test-marker-parallel-built m=MARKER_NAME`. Report pass/fail count. On failure, include test name and assertion/error for each failure."
  - For a specific test file: "Run `make test-marker-parallel-built m=MARKER` or the specific pytest command in Docker. Report pass/fail with failure details."
- **Always use built targets** (`test-marker-parallel-built`, `test-ui-parallel-built`) for UI tests — they run against pre-built Vite assets, not the dev server.
- Common UI test markers: `splash_ui`, `home_ui`, `utubs_ui`, `members_ui`, `urls_ui`, `tags_ui`, `mobile_ui`

#### For Unit/Integration Tests:
Delegate to a subagent:
- Task: "Run tests for marker MARKER using `make test-marker-parallel m=MARKER`. Report pass/fail count. On failure, include test name and assertion/error for each failure."
- For a specific test file: "Run pytest for `tests/path/test_file.py` in the Docker web container. Report pass/fail with failure details."

#### Subagent Guidelines:
- Use the Agent tool with a clear, self-contained prompt
- CRITICAL: The subagent must set `dangerouslyDisableSandbox: true` on every Bash call that runs `make` or `docker`. Include an example in the subagent prompt: `Bash(command: "make test-marker-parallel m=urls > \"/tmp/claude/test-results.txt\" 2>&1", dangerouslyDisableSandbox: true)`
- The subagent must activate the virtualenv: `source /code/venv/bin/activate`
- The subagent should use `make` targets when available (preferred over raw docker commands)
- Never run two test suites simultaneously (they share a single test DB)
- On success: subagent returns pass count only
- On failure: subagent returns failed test names + error/assertion snippets + writes failures to `tmp/` using the test-failure-logger pattern

### Step 4: Update the Plan Document
**CRITICAL: Always update progress tracking.**

#### If Progress Tracking Section Exists:
- Change `- [ ] **Phase X: Name**` to `- [x] **Phase X: Name** - COMPLETE (YYYY-MM-DD)`
- Add checkmarks for completed sub-items: `- ✅ Item description`
- Example:
```markdown
- [x] **Phase 4: Navigation Button Migration** - COMPLETE (2026-02-14)
  - ✅ Updated back_home_btn.html - added data-route attribute
  - ✅ Updated logout_btn.html - added data-route attribute
  - ✅ Updated frontend/home/navbar.js - added handlers
  - ✅ Vite build verified - clean build
```

#### If No Progress Tracking Section Exists:
- Create a new "## Progress Tracking" section at the end of the document
- Add checkboxes for each phase/step mentioned in the plan
- Mark completed items with `[x]` and date

#### Update the Finished Flag:
- If all phases are complete, change `**finished**: false` to `**finished**: true`

### Step 5: Subagent Review & Fix
**CRITICAL: Always perform this review before reporting to the user.**

Use the **Subagent Review Pipeline** (defined below) to review and fix the implementation. Before launching:
1. Run `git diff --name-only` to collect the list of changed files
2. Prepare a brief description of what the step was supposed to implement (from the plan)
3. Launch all 3 review subagents in parallel, then the fix subagent if needed

### Step 6: Report and Pause
- Provide a concise summary of what was completed
- Show validation results (build output, test results, etc.)
- Confirm the plan document was updated
- Include a brief summary of subagent review findings and any fixes applied by the fix subagent
- **REQUIRED:** Ask the user if they want to continue to the next step
- Do NOT automatically proceed to the next step

## Example Output

```
✅ Phase 4: Navigation Button Migration - COMPLETE

Changes made:
- Updated back_home_btn.html (added data-route="home")
- Updated logout_btn.html (added data-route="logout")
- Updated frontend/home/navbar.js (added APP_CONFIG import and handlers)
- Updated frontend/splash/navbar.js (added APP_CONFIG import and handlers)

Validation:
✅ Vite build passed - no errors

Subagent Review:
- Correctness & Codebase Fit: PASS — follows existing data-route pattern
- Security & Edge Cases: PASS — no injection vectors, missing route falls back safely
- Quality & Completeness: 1 FINDING — stale console.log in navbar.js

Fix Subagent:
✅ Removed console.log from navbar.js
✅ Re-validated: Vite build clean

Plan updated:
✅ Marked Phase 4 as complete in plan document

Ready for Phase 5 (Contact Form Migration)?
```

---

## Review Mode Workflow

### Step 1: Locate and Read Files
- Plan: glob `plans/**/<name>.md` where `<name>` matches **$ARGUMENTS** contextually. Derive `<topic>` from the plan file's parent directory name.
- Review: `plans/<topic>/reviews/<name>-review.md` (for plan reviews) OR `plans/<topic>/reviews/push-review-<branch>.md` (for push reviews)

Review files live at `plans/<topic>/reviews/`. Derive `<topic>` from the plan file's parent directory, or infer from branch name for push reviews.

**For push reviews**: derive the exact branch name (`git branch --show-current`), then infer `<topic>` from it:
- Split the branch name on `/` and `-`, match tokens against known topics: `api-route`, `urls`, `openapi`
- Examples: `refactor/url-permission-decorator` → `api-route`; `feature/openapi-schema` → `openapi`
- If topic cannot be inferred, fall back to `plans/tmp/` for review files
- Construct the path as `plans/<topic>/reviews/push-review-<branch>.md`. Do NOT glob or fuzzy-match — use the exact branch name to avoid collisions with similarly-named files.

When **$ARGUMENTS** matches a push review file (e.g., "push-review-refactor-splash"), there is no associated plan file — the review is standalone. Skip reading the plan.

Read the review file in full — review files accumulate multiple revision passes and the latest revision is at the bottom. Paginate with `offset` + `limit` if needed. For plan reviews, also read the plan file in full.

### Step 2: Find the Latest Revision's Pending Items

Review files contain multiple revision sections. **Only the latest revision is authoritative.**

For push review files (`push-review-*`), revisions are numbered: `## Review 1`, `## Review 2`, etc.
For plan review files (`*-review`), revisions use dates or pass labels: `## Review — 2026-03-15 (fifth pass)`.

1. Grep for all `## Review` headings to get line numbers and text
2. Determine the latest: by **number** for push reviews (highest N in `## Review N`), or by **pass label/date** for plan reviews
3. Read from that heading to the next `## Review` heading (or end of file)
4. Find every unchecked item (`- [ ]`) in the **"To-Do: Required Changes"** section of the latest revision only

If all items are already checked (`- [x]`), report that the review is fully applied and stop.

### Step 3: Apply the Next Unchecked Item

Take the **first** unchecked item only (one at a time):

#### 3a. Apply the Change
- Read all files referenced by the review item before making changes
- If the change is ambiguous or requires a decision the review doesn't resolve, **ask the user before editing**
- Implement the minimal, faithful change to the **codebase** (not just the plan) that fulfills the review item
- Follow CLAUDE.md guidelines

#### 3b. Validate the Changes
Use the same validation approach as Plan Mode Step 3 (build verification, tests via subagent, etc.)

#### 3c. Subagent Review & Fix
Use the **Subagent Review Pipeline** (defined below) to review and fix the applied change. Before launching:
1. Run `git diff --name-only` to collect the list of changed files
2. Prepare a brief description of what the review item asked for
3. Launch all 3 review subagents in parallel, then the fix subagent if needed

#### 3d. Cross Off the Review Item
Mark complete in the review file: `- [ ]` → `- [x]`

### Step 4: Report and Pause
- Summarize what was applied
- Show validation results
- Include subagent review findings and any fixes applied by the fix subagent
- **REQUIRED:** Ask the user if they want to continue to the next review item
- Do NOT automatically proceed

---

## Subagent Review Pipeline

This pipeline is used by both Plan Mode (Step 5) and Review Mode (Step 3c). It replaces inline reviews with parallel subagents to keep the main context window clean.

### Prerequisites

Before launching the review subagents, the main agent must:
1. Run `git diff --name-only` to collect the list of changed files
2. Prepare a one-line summary of **what was supposed to be implemented** (the intent)

### Phase 1: Three Parallel Review Subagents (Read-Only)

Launch all 3 subagents simultaneously using the Agent tool. Each receives:
- The list of changed files
- The implementation intent summary
- Their specific review focus (below)
- Instruction: **read-only — do NOT edit any files**
- Instruction: read only the changed files and their immediate context (imports, callers)

Each subagent returns a structured response:

```
VERDICT: PASS | FINDINGS
Items: (only if FINDINGS)
- severity: critical | major | minor
  file: <path>
  line: <number or range>
  issue: <one-line description>
  suggestion: <one-line fix suggestion>
```

#### Subagent 1: Correctness & Codebase Fit
- Does the implementation follow existing patterns, naming conventions, and architecture?
- Are there logic errors, incorrect assumptions, or fragile implementations?
- Does the code faithfully implement what the plan step / review item specified?
- Are imports ordered correctly (stdlib → third-party → project)?

#### Subagent 2: Security & Edge Cases
- OWASP concerns: XSS, injection, CSRF vulnerabilities?
- Failure modes: empty input, missing data, unexpected states?
- Leftover debug code: console.log, window globals, debug hacks?
- Sensitive data exposure or insecure defaults?

#### Subagent 3: Quality & Completeness
- Over-engineering or premature abstractions?
- Test coverage: were tests added for new behavior? Happy + sad paths?
- CLAUDE.md compliance: typehints on Python code, no quoted annotations, descriptive variable names, no single-letter variables?
- Clean up: no unused imports, no dead code introduced?

### Phase 2: Aggregation

The main agent collects all 3 subagent responses:
- If all 3 return `PASS`: skip Phase 3, proceed to reporting
- If any return `FINDINGS`: aggregate all findings into a single list and proceed to Phase 3

### Phase 3: Fix Subagent

Launch a single fix subagent via the Agent tool. It receives:
- The aggregated findings list from Phase 2
- The list of changed files
- The implementation intent summary
- Instruction: fix all reported findings, then re-validate

The fix subagent must:
1. Read the relevant files
2. Apply fixes for each finding
3. Re-validate using the appropriate method (CRITICAL: every Bash call running `make` or `docker` MUST set `dangerouslyDisableSandbox: true`):
   - **JavaScript/Frontend changes**: Run `make vite-build` — example: `Bash(command: "make vite-build > \"/tmp/claude/vite-build.txt\" 2>&1", dangerouslyDisableSandbox: true)`
   - **Python changes**: Run the relevant test marker via `make test-marker-parallel m=<marker>` — example: `Bash(command: "make test-marker-parallel m=urls > \"/tmp/claude/test-results.txt\" 2>&1", dangerouslyDisableSandbox: true)`
   - **Template changes**: Verify Flask container starts without errors
4. Return a structured response:

```
FIXES APPLIED:
- file: <path>, line: <number>, change: <one-line description>
- ...

VALIDATION: PASS | FAIL
(if FAIL, include error output)

UNRESOLVED:
- (any findings that could not be fixed mechanically — require user decision)
```

If the fix subagent reports `VALIDATION: FAIL` or has `UNRESOLVED` items, the main agent must surface these to the user in the report step and ask for guidance before proceeding.

### Subagent Guidelines (applies to all 4 subagents)
- CRITICAL: Set `dangerouslyDisableSandbox: true` on every Bash call that runs `make` or `docker`. Example: `Bash(command: "make vite-build > \"/tmp/claude/vite-build.txt\" 2>&1", dangerouslyDisableSandbox: true)`
- Activate the virtualenv in Docker: `source /code/venv/bin/activate`
- Use `make` targets when available (preferred over raw docker commands)
- Never run two test suites simultaneously (they share a single test DB)
- Keep responses concise — structured format only, no prose

---

## Important Notes

- **Always validate**: Build verification is mandatory for JavaScript changes
- **Always review via subagents**: The Subagent Review Pipeline is mandatory before reporting to the user
- **Always update tracking**: Mark progress after every step/item completion
- **Always pause**: Never auto-continue to next step without user confirmation
- **CRITICAL: Set `dangerouslyDisableSandbox: true`** on every Bash call running `make` or `docker`
- **Test runs use synchronous Bash** — every `make test-*` invocation (integration, UI, single-marker, parallel, full suite) runs via the synchronous `Bash` tool with `dangerouslyDisableSandbox: true`. Never wrap test runs in a `Monitor`, never use `run_in_background`. Output goes to `/tmp/claude/<name>.txt`; this subagent blocks until make exits and reports the result in its Agent-tool reply.
- **Follow existing patterns**: Read code before making changes
- **Clean up**: Remove debug code, console.logs, window globals per CLAUDE.md
- **Investigate every test failure** — never dismiss a failure as "pre-existing" or "flaky" because the test file wasn't modified on this branch. Current changes can break tests indirectly (shared fixtures, CSS/selector changes, templates, timing, imports). For each failure: read the traceback, check if branch changes could affect the failing path, and either fix it or confirm it's unrelated by rerunning in isolation 2-3 times. Include this rule in all subagent prompts that run or evaluate tests.
