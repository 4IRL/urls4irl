---
name: plan-creator
description: Creates structured planning documents for new features or tasks in the @plans directory. Use when the user asks to create, write, or draft a plan for a feature, task, or implementation.
---

## Plan Creation

1. Create `@plans/<feature-name>.md` (create `@plans/` if missing).
2. Name the file after the feature/task (kebab-case).
3. Structure the plan as follows:

```markdown
# <Feature Name>

## Summary
<2-4 sentence description of what this feature does and why.>

## Steps

### 1. <Phase Title>
<One sentence describing what this phase accomplishes.>

**To-do:**
- [ ] <Specific, actionable sub-task>
- [ ] <Specific, actionable sub-task>

### 2. <Phase Title>
...

## Status
finished: false
```

**Rules:**
- Think like a staff engineer: anticipate edge cases, dependencies, and ordering constraints.
- Each phase must have at least one actionable to-do checkbox.
- To-do items must be detailed enough that a junior engineer can execute them without ambiguity — include file paths, function names, data shapes, or API contracts where relevant.
- The to-do list carries the detail; phase descriptions should be brief overviews.

## Package Pinning

Any plan step that adds a new Python package **must**:

1. Pin it to the **latest stable version** (check PyPI: `curl -s https://pypi.org/pypi/<package>/json | python3 -c "import sys,json,re; d=json.load(sys.stdin); vs=[v for v in d['releases'] if re.match(r'^\d+\.\d+\.\d+$',v)]; print(sorted(vs,key=lambda v:tuple(int(x) for x in v.split('.')))[-1])"`)
2. If stable is incompatible with the existing stack, use the latest working version instead — document why in the to-do item.
3. Pin **all transitive dependencies** introduced by the new package to exact versions as well. Run `pip install <package>==<version>` in the container, then `pip show <package>` and inspect the `Requires:` field. Add each unlisted dependency at its installed version.

**Always use `==` (not `>=`, `~=`, or ranges).** Add the package and its transitive deps to the appropriate requirements file based on usage:

| File | Use when |
|---|---|
| `requirements-prod.txt` | Needed at runtime in production |
| `requirements-test.txt` | Only needed for running tests (includes prod via `-r`) |
| `requirements-dev.txt` | Only needed for local dev tooling / pre-commit (includes test via `-r`) |

## TDD Enforcement

For any plan involving a **new feature or bug fix** (not pure refactoring or cleanup), the steps must follow a strict Red → Green → Refactor loop. Do not bulk-code then bulk-test.

## Final Verification Step

For **every plan that touches code or tests**, the last phase must be:

```markdown
### N. Verify All Tests Pass

Run the full test suites to confirm nothing is broken:

**To-do:**
- [ ] Run `make test-integration-parallel` and confirm all integration tests pass
- [ ] Run `make test-ui-parallel-built` and confirm all UI/functional tests pass
- [ ] Investigate and fix any failures before marking the plan finished
```

Do not omit this phase even if only one test file was touched.

## TDD Enforcement

For any plan involving a **new feature or bug fix** (not pure refactoring or cleanup), the steps must follow a strict Red → Green → Refactor loop. Do not bulk-code then bulk-test.

**The Loop (one requirement at a time):**
1. **Red** – Write a focused test for one specific requirement. Run it; confirm it fails with a relevant error.
2. **Green** – Write the minimum code to make that test pass. Run it; confirm it passes.
3. **Refactor** – Clean up for readability and project patterns. Confirm tests stay green.
4. Repeat until the feature is complete.

**Implementation standards:**
- **Backend (Flask):** Prioritize integration or unit tests. Match existing style and directory structure in `tests/`.
- **Frontend – logic/state:** Use Vitest with JSDOM (fast, isolated).
- **Frontend – navigation/critical flows:** Use Selenium (end-to-end verification).
- **Philosophy:** Tests are the contract; code is the fulfillment. Never write tests to fit existing feature code.