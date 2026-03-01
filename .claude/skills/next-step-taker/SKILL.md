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
**CRITICAL: Always validate after execution.** Choose appropriate validation method(s):

#### For JavaScript/Frontend Changes:
```bash
# ALWAYS run this after any JavaScript file changes
docker compose --project-directory /Users/ggpropersi/code/urls4irl -f /Users/ggpropersi/code/urls4irl/docker/compose.local.yaml exec vite npx vite build
```
- Must use `dangerouslyDisableSandbox: true` for Docker commands
- Verify: No import errors, no missing exports, clean build output

#### For Template/Flask Changes:
- Verify Flask container starts without errors
- Check application logs for issues

#### For UI Changes (Selenium/Playwright Tests):
- If the plan specifies manual verification steps, list them for the user
- If specific UI tests are mentioned, run them in the Docker container:
```bash
# For UI tests with specific marker (e.g., splash_ui, home_ui, etc.)
docker exec u4i-local-web /bin/bash -c "source /code/venv/bin/activate; pytest -m 'MARKER_NAME' -v"

# For specific test file
docker exec u4i-local-web /bin/bash -c "source /code/venv/bin/activate; pytest tests/functional/PATH/test_file.py -v"
```
- Must use `dangerouslyDisableSandbox: true` for Docker commands
- Common UI test markers: `splash_ui`, `home_ui`, `utubs_ui`, `members_ui`, `urls_ui`, `tags_ui`, `mobile_ui`

#### For Unit/Integration Tests:
- Run relevant tests in the Docker container:
```bash
# For unit tests
docker exec u4i-local-web /bin/bash -c "source /code/venv/bin/activate; pytest -m 'unit' tests/unit/test_file.py -v"

# For integration tests (splash, utubs, members, urls, tags, etc.)
docker exec u4i-local-web /bin/bash -c "source /code/venv/bin/activate; pytest -m 'MARKER' -v"

# For specific test file
docker exec u4i-local-web /bin/bash -c "source /code/venv/bin/activate; pytest tests/integration/PATH/test_file.py -v"
```
- Must use `dangerouslyDisableSandbox: true` for Docker commands

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
