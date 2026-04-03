---
name: refine-plan
description: Iteratively refine a plan by repeatedly applying the plan-reviewer and apply-plan-review cycle for a given number of iterations. Uses per-pass subagents so source file reads don't accumulate in the main context window — the main agent only receives structured JSON summaries (finding counts, items applied, design questions). Stops early when a review pass returns 0 critical AND 0 major findings. Collects design questions deferred during apply phases and surfaces them at the end. Use when asked to iteratively refine, polish, or auto-apply review feedback on a plan in a loop (e.g., "/refine-plan my-feature 3" or "/refine-plan auth-redesign").
argument-hint: <plan-name> [max-iterations=5]
---

# Refine Plan

Orchestrate the plan-reviewer → apply-plan-review loop using per-pass subagents to keep the main context lean. File reads happen inside subagents; the main agent tracks state and prints a summary table.

## Args

- `$1` — plan name (fuzzy-matched against `plans/**/<name>*.md` recursively)
- `$2` — max iterations (default: 5, hard cap: 5)

## Step 1: Initialize

1. Confirm a plan file matching `$1` exists by globbing `plans/**/<name>*.md`. If no match, report and stop. Derive `<topic>` from the parent directory of the matched file (e.g., `plans/auth/<name>.md` → `<topic>=auth`).
2. Set `MAX_ITER = min($2 ?? 5, 5)`.
3. Create (or clear) `plans/<topic>/tmp/design-questions-<plan-name>.md` with header: `# Design Questions: <plan-name>\n`
4. **Ask for confirmation before proceeding**: "Start the refinement loop for `<plan-name>` — up to `<MAX_ITER>` iterations? (yes/no)"
5. Wait for user confirmation. If not confirmed, stop.

## Step 2: Iterate

For each iteration `i` from 1 to MAX_ITER:

### 2a. Review Phase — subagent

Spawn a subagent using the Agent tool with these instructions:

> Follow ALL steps of the plan-reviewer skill (Steps 1–4): locate the plan at `plans/<topic>/<plan-name>.md`, read all relevant source files, review the plan as a staff engineer across every dimension (correctness, per-endpoint trace, ordering, edge cases, codebase integration, verification steps, implementation specificity, risk), and write/append your findings to `plans/<topic>/reviews/<plan-name>-review.md`.
>
> **Count accuracy rule**: The JSON counts you report MUST exactly equal the number of NEW unchecked `- [ ]` items you wrote in this pass's "To-Do: Required Changes" section. Do NOT count findings from prior passes — even if they are still `[ ]` in an older section. If a prior finding was already applied to the plan (the plan now contains the fix), do NOT re-report it or create a new `- [ ]` item for it. Only genuinely new issues that are not already addressed in the current plan text produce `- [ ]` items and increment counts.
>
> Skip Step 5 (do not wait for user confirmation).
>
> When done, output ONLY a JSON block — no other text:
> ```json
> {"critical": <N>, "major": <N>, "minor": <N>, "new_todo_items": <N>, "converged": <true if critical==0 AND major==0>}
> ```
> `new_todo_items` must equal the number of `- [ ]` lines you wrote in THIS pass's To-Do section.

The subagent performs all file I/O independently. The main agent receives only the JSON summary.

### 2b. Verify Reported Counts

**The main agent must verify the review subagent's reported counts before proceeding.** Read the last 60 lines of `plans/<topic>/reviews/<plan-name>-review.md` and:

1. Confirm a new pass section was appended (look for a new dated heading that wasn't there before).
2. Count the actual `- [ ]` (unchecked) items in the **latest** pass's "To-Do: Required Changes" section.
3. Compare with the subagent's reported `new_todo_items` count.

If the counts **mismatch** (e.g., subagent reports 3 findings but 0 new unchecked To-Do items exist):
- Override the JSON with the actual counts from the file.
- Log: "Count mismatch — subagent reported `<N>` new items but review file contains `<actual>` unchecked items. Using file as source of truth."

If the review file has **0 new unchecked To-Do items** regardless of what the subagent reported:
- Treat as converged (`converged = true`).

### 2c. Convergence Check

Parse the (possibly overridden) counts. If `converged == true` (critical == 0 AND major == 0, AND new unchecked To-Do items == 0):
- Append the final row to the summary table with "Yes" in the Converged column.
- Report: "Pass `i` complete — 0 critical, 0 major, `<minor>` minor. Converged early."
- Go to Step 3.

Otherwise report: "Pass `i` complete — `<critical>` critical, `<major>` major, `<minor>` minor. Applying changes..."

### 2d. Apply Phase — subagent

Spawn a subagent using the Agent tool with these instructions:

> Follow ALL steps of the apply-plan-review skill (Steps 1–3): locate `plans/<topic>/<plan-name>.md` and `plans/<topic>/reviews/<plan-name>-review.md`. Read the full review file to find the **latest revision** (highest pass ordinal, not highest line number). Find every unchecked item (`- [ ]`) in the latest revision's "To-Do: Required Changes" section only. Apply each one to the plan.
>
> For any item that is ambiguous or requires a decision the review item does not resolve: evaluate the options using ALL of the following criteria before choosing. Do not guess — reason through each criterion explicitly.
>
> **Decision criteria (apply in order; the chosen option must satisfy all):**
> 1. **Codebase pattern match** — Read the relevant files. What does the existing codebase already do in analogous situations? Prefer the approach that is already established over inventing something new.
> 2. **Simplest sufficient solution** — Choose the option that solves the problem with the least added complexity. If a simpler approach exists, the more complex one needs a strong justification.
> 3. **Cross-module consistency** — Does the decision align with how other modules/branches in the codebase handle the same concern? Inconsistency is a code smell; flag it if you can't reconcile.
> 4. **Testability** — Which option is easier to write a clear, isolated test for? Prefer the option where the happy path, sad path, and edge cases can be tested without heavy mocking or setup.
> 5. **Modifiability** — Could a future developer change this decision with a small, local edit? Prefer options that don't require cascading changes across many files if requirements shift.
> 6. **Defensibility** — Could you defend this choice to a distinguished staff engineer, a CTO focused on technical quality, and a CPO/CEO focused on shipping value? If the answer is "no" or "maybe," pick a different option or surface it as a design question instead.
>
> If after applying all criteria an option is clearly better, apply it and record it. If two options are genuinely tied or the criteria conflict, surface it as a design question instead of guessing.
>
> Record each resolved decision by appending to `plans/<topic>/tmp/design-questions-<plan-name>.md`:
> ```markdown
> ## Iteration <i> — <YYYY-MM-DD>
> ### Q<n>: <brief title>
> **Review item**: <paraphrase>
> **Options considered**: <list the options that were viable>
> **Decision made**: <what was chosen>
> **Reasoning**: <which criteria drove the choice and why — cite the codebase file/pattern if relevant>
> **Deferred?**: No (resolved) / Yes (criteria conflicted — user input needed)
> ```
>
> When done, output ONLY a JSON block — no other text:
> ```json
> {"items_applied": <N>, "design_questions": <count of questions recorded>}
> ```

### 2e. Apply-Phase Mismatch Guard

After the apply subagent returns, if `items_applied == 0` but the (verified) review counts showed findings:
- This means the review either re-reported already-resolved findings or wrote findings that didn't produce actionable To-Do items.
- Treat as converged: set `converged = true`, append the row with "Yes (no actionable items)" in the Converged column, and go to Step 3.

### 2f. Update Summary Table

After both subagents complete, record the row:

```
| <i> | <critical> | <major> | <minor> | <items_applied> | No |
```

If this was the final iteration without convergence, mark the last row "No (max reached)".

## Step 3: Surface Results

1. Print the completed summary table:

```
| Pass | Critical | Major | Minor | Items Applied | Converged? |
|------|----------|-------|-------|---------------|------------|
| ...  | ...      | ...   | ...   | ...           | ...        |
```

2. Report whether the loop converged early or hit the max iteration limit.
3. If `plans/<topic>/tmp/design-questions-<plan-name>.md` has entries beyond the header, display the full file contents and say: "The following design questions were deferred — please review and confirm or adjust each decision."
4. If no design questions: "No design questions were deferred — all review items were unambiguous."
5. Remind the user to run the plan's verification steps.

### Persist the Run Log

Write (or append) to `plans/<topic>/reviews/<plan-name>-refine-log.md`. If the file doesn't exist, create it with the header `# Refinement Log: <plan-name>\n`. Append a new dated section each run:

```markdown
## Run — <YYYY-MM-DD HH:MM>

### Summary Table

| Pass | Critical | Major | Minor | Items Applied | Converged? |
|------|----------|-------|-------|---------------|------------|
| ...  | ...      | ...   | ...   | ...           | ...        |

**Outcome**: Converged after pass N / Hit max iterations (N passes) with <critical> critical and <major> major findings remaining.

### Design Questions Deferred

<copy full contents of plans/<topic>/tmp/design-questions-<plan-name>.md if any questions were recorded, otherwise write "None.">
```

## Important Notes

- Review files live at `plans/<topic>/reviews/`. The project-root `reviews/` directory no longer exists.
- The main agent must NOT read plan or review files directly — EXCEPT during step 2b (verify reported counts), where it reads the tail of the review file to confirm actual unchecked item counts
- Each review subagent appends a new dated section; it does not overwrite prior reviews
- Subagents must follow the full plan-reviewer and apply-plan-review skill instructions, not abbreviated versions
- Best-effort decisions in the apply phase should favor the simplest, most conservative interpretation
- `plans/<topic>/tmp/` must exist before writing design questions — create it if needed
