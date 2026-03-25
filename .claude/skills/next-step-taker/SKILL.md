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
- Search for an existing plan in the `/Users/ggpropersi/code/urls4irl/plans/` directory that matches **$ARGUMENTS** contextually
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
  - Task: "Run UI tests for marker MARKER_NAME using `make test-marker-parallel m=MARKER_NAME`. Report pass/fail count. On failure, include test name and assertion/error for each failure."
  - For a specific test file: "Run `make test-marker-parallel m=MARKER` or the specific pytest command in Docker. Report pass/fail with failure details."
- Common UI test markers: `splash_ui`, `home_ui`, `utubs_ui`, `members_ui`, `urls_ui`, `tags_ui`, `mobile_ui`

#### For Unit/Integration Tests:
Delegate to a subagent:
- Task: "Run tests for marker MARKER using `make test-marker-parallel m=MARKER`. Report pass/fail count. On failure, include test name and assertion/error for each failure."
- For a specific test file: "Run pytest for `tests/path/test_file.py` in the Docker web container. Report pass/fail with failure details."

#### Subagent Guidelines:
- Use the Agent tool with a clear, self-contained prompt
- The subagent must use `dangerouslyDisableSandbox: true` for all Docker commands
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

### Step 5: Staff Engineer Review
**CRITICAL: Always perform this review before reporting to the user.**

Adopt the perspective of a staff engineer reviewing the implementation. Evaluate:

1. **Codebase fit** - Does the implementation follow existing patterns, naming conventions, and architecture? Does it belong where it was placed?
2. **Technical correctness** - Are there logic errors, incorrect assumptions, or fragile implementations? Does the code do what it claims?
3. **Edge cases** - Are failure modes handled? What happens with empty input, missing data, concurrent access, or unexpected states?
4. **Test coverage** - Were tests added for the new behavior? Do existing tests still pass? Are happy and sad paths covered?
5. **Security and quality** - Are there OWASP concerns (XSS, injection, CSRF)? Is debug code removed? Are typehints present on Python code?
6. **Over-engineering** - Is the implementation more complex than needed? Are abstractions premature?

After the review, immediately fix any issues found before proceeding. Re-run validation after fixes.

### Step 6: Report and Pause
- Provide a concise summary of what was completed
- Show validation results (build output, test results, etc.)
- Confirm the plan document was updated
- Include a brief summary of the staff engineer review and any fixes applied
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

Staff Engineer Review:
✅ Follows existing data-route pattern used in other nav components
✅ Edge cases handled: missing route attribute falls back to window.location
⚠️  Fixed: removed a stale console.log left in navbar.js

Plan updated:
✅ Marked Phase 4 as complete in plan document

Ready for Phase 5 (Contact Form Migration)?
```

---

## Review Mode Workflow

### Step 1: Locate and Read Files
- Plan: `plans/<name>.md` where `<name>` matches **$ARGUMENTS** contextually
- Review: `reviews/<name>-review.md` (for plan reviews) OR `reviews/push-review-<branch>.md` (for push reviews)

Both paths are **relative to the project root**. `reviews/` is a sibling of `plans/`, not nested under it.

**For push reviews**: derive the exact filename from the current git branch (`git branch --show-current`), then construct `reviews/push-review-<branch>.md`. Do NOT glob or fuzzy-match — use the exact branch name to avoid collisions with similarly-named files.

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

#### 3c. Staff-Engineer Critique
After applying, evaluate:
1. **Faithful?** Does the edit fully implement what the review item asked for — no more, no less?
2. **Correct?** Is the change accurate given the actual codebase?
3. **Coherent?** Does the change integrate cleanly with surrounding code?
4. **Risk?** Does the edit introduce any new issues?

If any concern: explain, propose correction, and **wait for user confirmation**.

#### 3d. Cross Off the Review Item
Mark complete in the review file: `- [ ]` → `- [x]`

### Step 4: Report and Pause
- Summarize what was applied
- Show validation results
- Include staff engineer review findings and any fixes
- **REQUIRED:** Ask the user if they want to continue to the next review item
- Do NOT automatically proceed

---

## Important Notes

- **Always validate**: Build verification is mandatory for JavaScript changes
- **Always review**: Staff engineer review is mandatory before reporting to the user
- **Always update tracking**: Mark progress after every step/item completion
- **Always pause**: Never auto-continue to next step without user confirmation
- **Use dangerouslyDisableSandbox: true** for all Docker commands
- **Follow existing patterns**: Read code before making changes
- **Clean up**: Remove debug code, console.logs, window globals per CLAUDE.md
