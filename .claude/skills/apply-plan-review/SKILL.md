---
name: apply-plan-review
description: Apply all pending review changes from a review file to its corresponding plan file, one item at a time, with a staff-engineer quality check after each change. Use when asked to apply a review to a plan, update a plan from its review, or work through review feedback on a plan. The plan name is inferred from the argument (e.g., "/apply-plan-review pydantic-integration"). Plan files live at plans/<name>.md; review files live at reviews/<name>-review.md.
---

# Apply Plan Review

Apply every unchecked item from a review's "To-Do" section to the corresponding plan, one change at a time, with a distinguished staff-engineer critique after each edit.

## Workflow

### Step 1: Locate and Read Files

- Plan: `plans/<name>.md`
- Review: `reviews/<name>-review.md`

Both paths are **relative to the project root**, not nested under each other. `reviews/` is a sibling of `plans/`, not `plans/reviews/`.

Read both files in full before making any changes.

### Step 2: Identify Pending Items

Find every unchecked item (`- [ ]`) in the **"To-Do: Required Changes"** section of the review file. These are the only items to act on. Ignore findings, verification gaps, and the verdict — only the To-Do checklist drives changes.

If all items are already checked (`- [x]`), report that the review is fully applied and stop.

### Step 3: Apply Each Item in Sequence

For each unchecked item, in order:

#### 3a. Apply the Change

Read the review item carefully. If anything about the required change is ambiguous or requires a decision that the review item does not resolve — such as which of several valid approaches to take, what exact wording to use, or whether a change conflicts with existing plan content — **ask the user before editing**. Do not guess; a wrong assumption here propagates into the plan.

Once intent is clear, determine the minimal, faithful edit to the plan that fulfills it. Apply it using the Edit tool. Do not make additional changes beyond what the review item specifies.

#### 3b. Staff-Engineer Critique

Immediately after applying the edit, adopt the role of a **distinguished staff engineer** and answer these questions concisely:

1. **Faithful?** Does the edit fully implement what the review item asked for — no more, no less?
2. **Correct?** Is the change accurate given the actual codebase (file paths, APIs, model shapes)?
3. **Coherent?** Does the updated plan text read clearly and consistently with surrounding steps?
4. **Risk?** Does the edit introduce any new ambiguity, contradiction, or gap?

If any answer is "no" or raises a concern: explain the issue, propose a correction, and **wait for user confirmation before continuing**.

If all answers are satisfactory: proceed immediately to 3c.

#### 3c. Cross Off the Review Item

Mark the item as complete in the review file: `- [ ]` → `- [x]`.

### Step 4: Report Completion

After all items are processed, output a brief summary:
- How many items were applied
- Any items that required user input or were skipped
- Reminder to re-run relevant tests per the plan's Verification section
