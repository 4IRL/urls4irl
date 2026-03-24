---
name: next-step-taker
description: Execute the next step in the plan when asked.
argument-hint: Plan-name
---

# Next Step Taker Skill

This skill executes the next incomplete step or phase from an existing implementation plan, validates the changes, updates the plan document, and pauses for user confirmation before continuing.

## Workflow

### Step 1: Locate the Plan
- Search for an existing plan in the `/Users/ggpropersi/code/urls4irl/plans/` directory that matches **$0** contextually
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

## Important Notes

- **Always validate**: Build verification is mandatory for JavaScript changes
- **Always review**: Staff engineer review is mandatory before reporting to the user
- **Always update plan**: Mark progress after every step completion
- **Always pause**: Never auto-continue to next step without user confirmation
- **Use dangerouslyDisableSandbox: true** for all Docker commands
- **Follow existing patterns**: Read code before making changes
- **Clean up**: Remove debug code, console.logs, window globals per CLAUDE.md
