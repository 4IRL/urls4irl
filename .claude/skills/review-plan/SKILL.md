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

Read in parallel where possible.

### Step 3: Review the Plan as a Staff Engineer

Evaluate across these dimensions. Be specific — cite step numbers and file names.

#### Correctness
- Do the proposed changes match the actual API/interface of the code they touch?
- Are import paths, function signatures, and data shapes accurate?
- Does the plan delete or modify things that other modules depend on?

#### Ordering & Dependencies
- Are steps sequenced so each prerequisite is done before its consumer?
- Would executing steps out of order cause failures?

#### Edge Cases & Completeness
- What scenarios are not covered? (empty state, error paths, boundary conditions)
- Are there race conditions, async timing issues, or state management gaps?
- Does the plan handle cleanup (temp files, test fixtures, orphaned imports)?

#### Codebase Integration
- Does the plan follow established project patterns (test structure, naming, module conventions)?
- Are new files placed in the right directories per the project architecture?
- Does it respect CLAUDE.md rules (no window globals, typehints, cleanup of debug code)?
- Are test markers correct per `pytest.ini`? Are new markers needed?

#### Verification Steps
- Does each step have a clear way to verify success (a command to run, a behavior to observe)?
- Are the verification steps in the plan actually sufficient to catch regressions?
- Note any steps that lack verification and suggest what to add.

#### Risk & Reversibility
- Which steps are hard to undo (file deletions, DB migrations, API contract changes)?
- Are there steps that could break CI or affect shared infrastructure?

### Step 4: Write or Update the Review Document

#### File location

In the project directory - 
`reviews/<plan-name>-review.md` — create `reviews/` if it doesn't exist.

NOTE: This `reviews/` MUST be in the project directory, NOT in the same `plans/` folder as the plan being reviewed.

One file per plan. If a review file already exists, **append** a new dated review section; do not overwrite previous reviews.

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

## Important Notes

- Read source files before concluding anything about correctness — don't assume
- Cite specific step numbers and file paths in every finding
- If the plan is already solid, say so clearly — a clean review is a useful result
- Multiple reviews of the same plan accumulate in one file (append, don't overwrite)
- The `plans/reviews/` directory may need to be created if this is the first review
