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