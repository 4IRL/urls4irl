---
name: plan-reviewer
description: Review a plan file using up to 3 iterative passes of 6 parallel subagents with specialized expertise (Correctness, Full-Stack Trace, Ordering/Dependencies, Codebase Integration, Verification/Test Coverage, Completeness/Risk). Each pass auto-applies mechanical fixes, presents design decisions as interactive questions via AskUserQuestion, applies user choices, then loops into the next pass. Exits early if a pass finds 0 critical + 0 major. After Pass 3, remaining issues are tagged "resolve during implementation." The plan name is inferred from the argument (e.g., "/plan-reviewer selenium-to-js-unit-tests"). Creates or updates a review document in reviews/.
argument-hint: Plan-name
---

# Plan Review with Parallel Subagents (Up to 3 Passes)

Review a plan using 6 specialized subagents running in parallel, then merge their findings into a single review document. Automatically loops up to 3 passes, pausing between each pass for the user to answer design decisions via interactive `AskUserQuestion` prompts.

## Branch Guard

Before starting, check the current branch:
1. If on `main` or `master`:
   - Run `gmas` to ensure main is up to date
   - Suggest a branch name based on the task context
   - Ask the user: "You're on main. Want me to create and switch to `<suggested-branch>`?"
   - Do NOT proceed until the user confirms and you've switched branches
2. If already on a feature branch: proceed normally

## Review Loop (Up to 3 Passes)

The review runs as a loop with up to 3 passes. Each pass executes Steps 2-5 below. Between passes, the user answers design decisions via `AskUserQuestion`. The loop exits early if:

- **A pass produces 0 critical + 0 major findings** → plan is clean, stop reviewing
- **Pass 3 completes** → hard cap reached; any remaining issues are tagged "resolve during implementation" in the review document

After the final pass (whether early exit or Pass 3), proceed to Steps 6-7 (root cause analysis and skill improvement) if prior reviews exist.

### Pass tracking

Track the current pass number (1, 2, or 3). When writing to the review document:
- Pass 1: `## Review — <YYYY-MM-DD>`
- Pass 2+: `## Review — <YYYY-MM-DD> (Pass N)`

## Workflow

### Step 1: Locate the Plan (once, before the loop)

- Search `plans/` for a file matching **$0** (fuzzy match on filename)
- Read the full plan document
- Note: plan files live at `plans/<name>.md`

### Step 2: Launch 6 Parallel Review Subagents

Read `references/subagent-prompts.md` for the full prompt definitions and expected response format.

Launch **all 6 subagents in parallel** using the Agent tool. Each subagent:
- Receives the plan file path from Step 1
- Receives its specific review focus area from the reference file
- Must independently read the plan AND relevant source files (no pre-fetching by the main agent)
- Must return a structured JSON response with `verdict`, `findings`, `files_read`, and `summary`

**Critical instruction for each subagent prompt:** Include the full text of the relevant subagent section from `references/subagent-prompts.md` (response format + the specific subagent's checklist). Also include:

> You are reviewing the plan at `plans/<plan-name>.md`. Read it in full, then read the source files relevant to your review area. Return ONLY a JSON block — no other text.
>
> **Do not defer any dimension to a follow-up pass.** Every item in your checklist must be evaluated before writing findings. If you run out of findings in one area, continue to the next.

Subagents (all launched in a single message):

| # | Name | Focus | Key files to read |
|---|---|---|---|
| 1 | Correctness & Accuracy | Plan assertions vs actual code, signatures, Pydantic | Source files the plan references, one level of callees |
| 2 | Full-Stack Trace | Per-endpoint request/response cycle | Route handlers, JS files (entire module dir), templates |
| 3 | Ordering, Dependencies & Cleanup | Step sequencing, intermediate state, dead imports | Plan + lint config (`tox.ini`, `.flake8`, `pyproject.toml`) |
| 4 | Codebase Integration & Conventions | Project patterns, CLAUDE.md rules, packages | CLAUDE.md, ARCHITECTURE.md, requirements files, sample module files |
| 5 | Verification & Test Coverage | Verification sufficiency, layer-match | Test files, `pytest.ini`, `Makefile` |
| 6 | Completeness, Risk & Specificity | Gaps, risks, underspecified steps | Schema defs, factory methods, template structures |

### Step 3: Collect and Validate Results

Collect all 6 subagent responses. For each:
- Parse the JSON response
- If a subagent fails to return valid JSON, treat as FAIL with a note about the parse error
- Tally findings by severity across all subagents

### Step 4: Merge Findings into Review Document

#### Deduplication

Before writing, deduplicate findings across subagents:
- If two subagents flag the same issue (same step + same file + same root cause), keep the more detailed finding and note which subagents identified it
- Findings about the same step but different aspects are NOT duplicates — keep both

#### Coverage Checklist

Build the coverage checklist from subagent results:

| Area | Primary subagent | What to verify |
|---|---|---|
| Imports (dead, missing, circular) | #3 Ordering | Dead imports after deletions, missing imports for new symbols |
| Type annotations | #1 Correctness | New/changed functions have correct type hints |
| Error handling (status codes, exceptions, user feedback) | #2 Full-Stack Trace | Status codes match JS handlers, exceptions propagate correctly |
| Test coverage (happy path, sad path, edge cases) | #5 Verification | Tests exist for every changed endpoint |
| Breaking changes (API contracts, shared state, DB schema) | #6 Completeness | Cross-module dependencies accounted for |
| Config consistency (env vars, requirements pins, lint rules) | #4 Integration | Env vars, lint rules, CI config aligned |
| Naming conventions (CLAUDE.md rules, project patterns) | #4 Integration | No single-letter vars, no quoted hints, no window globals |

Mark each area `[x]` if the primary subagent reported reading the relevant files (check `files_read`). Mark `[ ]` with explanation if the subagent could not verify.

#### File location

`reviews/<plan-name>-review.md` — create `reviews/` if it doesn't exist.

NOTE: `reviews/` MUST be at the project root, NOT inside `plans/`.

One file per plan. If a review file already exists, **append** a new dated review section; do not overwrite previous reviews.

**Re-verify prior review resolutions (required when appending):** When a review file already exists, read every `[x]` item from prior reviews. For each, re-read the actual source file the fix depends on and confirm the fix resolves the root cause. "The plan now says X" is not verification — the code/template/config must support X. If a prior resolution is incorrect, re-open it as a new Critical finding.

#### Review file structure

```markdown
# Review: <Plan Name>

## Review — <YYYY-MM-DD>

### Summary
<2-3 sentence overall assessment: ready to proceed / needs changes / blocked.>

### Subagent Results

| # | Subagent | Verdict | Findings |
|---|---|---|---|
| 1 | Correctness & Accuracy | PASS/FAIL | N critical, N major, N minor |
| 2 | Full-Stack Trace | PASS/FAIL | N critical, N major, N minor |
| 3 | Ordering & Cleanup | PASS/FAIL | N critical, N major, N minor |
| 4 | Integration & Conventions | PASS/FAIL | N critical, N major, N minor |
| 5 | Verification & Coverage | PASS/FAIL | N critical, N major, N minor |
| 6 | Completeness & Risk | PASS/FAIL | N critical, N major, N minor |

### Findings

#### Critical (must fix before proceeding)
- **[Step N] <Finding title>** _(Subagent #N)_: <Specific issue and why it matters.>

#### Major (should fix)
- **[Step N] <Finding title>** _(Subagent #N)_: <Specific issue and impact.>

#### Minor (nice to fix)
- **[Step N] <Finding title>** _(Subagent #N)_: <Suggestion.>

### Verification Gaps
Steps that lack sufficient verification:
- **Step N**: Suggest running `<command>` to verify `<behavior>`.

### To-Do: Mechanical Fixes (auto-applied)
- [x] <Fix description> _(applied by fixing subagent)_
- [ ] <Fix description> _(skipped: <reason> — needs user input)_

### Design Decisions (awaiting user input)

#### DD-1: [Step N] <Decision title>
**Context:** <Why this needs a decision — what the review found and why it can't be fixed mechanically.>

| # | Option | Trade-off |
|---|---|---|
| 1 | <Option A> | <Pro/con> |
| 2 | <Option B> | <Pro/con> |

**Chosen:** _(filled in after user decides)_

---

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
```

If there are no findings in a category, omit that section.

### Step 5: Report, Auto-Fix Mechanicals, and Present Design Decisions

#### 5a: Separate findings by fix_type

After deduplication, partition the to-do list into two groups:

**Mechanical fixes** (`fix_type: "mechanical"`):
- List each with its exact edit description
- These will be auto-applied without user confirmation

**Design decisions** (`fix_type: "design_decision"`):
- List each with the decision needed and the options
- These require user input before any changes

#### 5b: Auto-apply mechanical fixes

Launch **one fixing subagent per mechanical finding** in parallel. Each subagent receives:
- The plan file path
- A single mechanical finding (title, step, fix_description)

Each fixing subagent:
1. Reads the plan file
2. Applies its single mechanical fix (edits to plan text only — never source files)
3. After the edit, verifies the surrounding plan text is still coherent (no orphaned references, no broken step numbering)
4. Returns a JSON response:

```json
{
  "status": "applied" | "skipped",
  "title": "finding title",
  "step": "Step N",
  "edit_summary": "what was changed (if applied)",
  "skip_reason": "why it couldn't be applied mechanically (if skipped)"
}
```

**All fixing subagents launch in a single message** for true parallelism. After all return, collect results into `applied` and `skipped` lists.

**Skipped items**: If a fixing subagent discovers that its "mechanical" fix actually requires a design choice (e.g., the edit location is ambiguous, or applying it would contradict another part of the plan), it MUST skip it and explain why. Skipped items are promoted to design decisions and presented to the user.

#### 5c: Write design decisions into the review document

Before presenting to the user, write all design decisions into the review document's `### Design Decisions (awaiting user input)` section. Each decision gets:
- A sequential ID (`DD-1`, `DD-2`, etc.)
- The step reference and title
- Context explaining why this needs a decision
- A table of options with trade-offs
- An empty `**Chosen:**` field

This ensures design decisions persist in the review file and are visible in future review passes, even if the conversation ends before the user decides.

#### 5d: Present results to user

Present a concise summary:
- Current pass number (e.g., "Pass 1 of 3")
- Overall verdict
- Subagent results table (from the review document)
- Count of critical / major / minor findings (deduplicated total)
- **Mechanical fixes applied** (count + list with one-line summaries)
- **Mechanical fixes skipped** (if any, with reasons — these need user input now)
- Path to the review file

**Do NOT apply design decisions to the plan without explicit user confirmation.**
**Do NOT apply any changes to source files — only the plan document.**

#### 5e: Present design decisions via AskUserQuestion

Present each design decision as an interactive question using the `AskUserQuestion` tool. This gives the user scrollable options they can select, plus an "Other" option for custom input.

**Constraints:**
- `AskUserQuestion` supports max 4 questions per call, each with max 4 options
- If there are more than 4 DDs, batch them across multiple `AskUserQuestion` calls (4 at a time)
- If a DD has more than 4 options, include the top 3-4 most viable options; the user can always select "Other" for an unlisted alternative

**Mapping DDs to AskUserQuestion format:**
- `question`: `"DD-N: [Step M] <finding title>?"` — include enough context in the question text for the user to understand the decision without referencing the review file
- `header`: `"DD-N"` (max 12 chars)
- `options`: Each option from the DD table becomes an option:
  - `label`: Short option name (1-5 words), e.g., "Refactor initResetPasswordForm" or "Use .one() binding"
  - `description`: The trade-off text from the DD table
  - `preview` (optional): Use when the option involves a specific code pattern or API choice that benefits from visual comparison. Include a short code snippet or ASCII diagram showing the approach.
- `multiSelect`: `false` (DDs are mutually exclusive choices)

**Example mapping:**

A DD like:
```
#### DD-1: [Step 4] Missing initResetPasswordForm $modal refactor
| # | Option | Trade-off |
|---|---|---|
| 1 | Refactor initResetPasswordForm($modal) | Consistent with all other form inits; slightly more code touched |
| 2 | Keep old signatures via wrapper | Avoids touching reset-password-form.js; adds indirection |
```

Becomes:
```
AskUserQuestion({
  questions: [{
    question: "DD-1: [Step 4] handleImproperFormErrors and showSplashModalAlertBanner now require $modal after Step 2's refactor, but reset-password-form.js still calls them without it. How should we fix this?",
    header: "DD-1",
    options: [
      { label: "Refactor initResetPasswordForm($modal)", description: "Consistent with all other form inits; slightly more code touched" },
      { label: "Keep old signatures via wrapper", description: "Avoids touching reset-password-form.js; adds indirection and a second API surface" }
    ],
    multiSelect: false
  }]
})
```

**After the user answers all DDs (across one or more AskUserQuestion calls):**

#### 5f: Apply user's design decisions via subagent

**IMPORTANT:** Launch a single subagent to handle all DD resolution work. The main orchestrator agent must NOT read/edit plan files or review files directly for DD application — this pollutes the main context window with large file contents. Instead, the subagent receives:
- The plan file path and review file path
- All user answers (DD number → chosen option text and any user notes)
- Instructions to: (1) apply each chosen option to the plan, (2) update the `**Chosen:**` field in the review document, (3) if the user selected "Other" with custom text, apply that instead

The subagent reads the files, makes all edits, and returns a summary of what was changed. The orchestrator only needs the summary to continue.

#### 5g: Loop decision

After applying DD choices, evaluate:

1. **Early exit check**: Did this pass produce 0 critical + 0 major findings?
   - **Yes** → Skip remaining passes. Print: "Pass N clean (0 critical, 0 major). Plan is ready for implementation." Proceed to Steps 6-7 if prior reviews exist.
   - **No** → Continue to next pass.

2. **Hard cap check**: Is this Pass 3?
   - **Yes** → Stop reviewing. If any unresolved issues remain, append a `### Resolve During Implementation` section to the review document listing them. Print: "Pass 3 complete (hard cap). Remaining issues tagged for implementation." Proceed to Steps 6-7.
   - **No** → Print: "Pass N complete. Starting Pass N+1..." and loop back to **Step 2**.

### Step 6: Root-Cause Analysis of Missed Findings (when prior reviews exist)

**Skip if this is the first review for the plan.**

When appending a new review pass and the current pass found findings that prior passes missed, add a `### Missed-Finding Root Causes` section. For each new finding, answer:

1. **What was missed?** — One-line summary.
2. **Why was it missed?** — Classify:
   - **Trusted plan assertion**: Plan stated something as fact, reviewer accepted without tracing
   - **Incomplete file reads**: Issue lives in a file the plan never references but is on the critical path
   - **Fix verification stopped at plan text**: Prior round confirmed the plan "says X" but nobody re-read the source file
   - **Scoped too narrowly**: Review dimension applied only to plan-referenced files, not the broader system
   - **Other**: Describe
3. **Skill gap**: Does the miss reveal a gap in the plan-reviewer skill's instructions?

Format:

```markdown
### Missed-Finding Root Causes
| Finding | Root cause | Skill gap? |
|---|---|---|
| <finding> | <root cause + details> | <gap or "Instructions already cover this"> |
```

After writing, check if the same root cause recurs across reviews. If so, flag it for Step 7.

### Step 7: Skill Self-Improvement (when prior reviews exist)

**Skip if this is the first review for the plan or if Step 6 found zero missed findings.**

After mechanical fixes are applied and the root-cause table is written, launch a **single skill-improvement subagent** that cross-references the current review's findings with prior reviews to identify and fix gaps in the reviewer skill itself.

#### 7a: Launch the skill-improvement subagent

The subagent receives:
- The review file path (`reviews/<plan-name>-review.md`)
- The plan file path
- The `### Missed-Finding Root Causes` table from Step 6
- Paths to skill files: `.claude/skills/plan-reviewer/SKILL.md`, `.claude/skills/plan-reviewer/references/subagent-prompts.md`
- Path to project CLAUDE.md
- Path to memory index: `.claude/projects/-Users-ggpropersi-code-urls4irl/memory/MEMORY.md`

The subagent:

1. **Reads all inputs**: review file (all passes), skill files, CLAUDE.md, memory index + any referenced memory files
2. **For each missed finding from Step 6**, determines:
   - **Which subagent (1-6) should have caught it** — based on the finding's category and the subagent checklists
   - **Why that subagent missed it** — maps to one of:
     - `prompt_gap`: The subagent's checklist doesn't cover this class of issue
     - `prompt_ambiguity`: The checklist covers it but the wording is too vague to enforce
     - `missing_context`: The subagent lacks awareness of a project convention or pattern
     - `scope_limitation`: The subagent's "what to read" section doesn't include the relevant files
     - `no_skill_gap`: The subagent's instructions already cover this; it was an execution miss (no fix needed)
   - **Concrete improvement** — exactly what to change and where:
     - For `prompt_gap`: exact checklist item to add to the subagent's section in `references/subagent-prompts.md`
     - For `prompt_ambiguity`: exact rewrite of the ambiguous checklist item
     - For `missing_context`: either a CLAUDE.md addition or a new memory file
     - For `scope_limitation`: exact edit to the subagent's "What to read" section
     - For `no_skill_gap`: no change proposed

3. **Checks for recurring patterns**: If the same root cause (`prompt_gap`, `prompt_ambiguity`, etc.) appears 2+ times across the same subagent, proposes a **structural improvement** (new checklist section, expanded scope) rather than individual line additions.

4. **Returns a JSON response**:

```json
{
  "improvements": [
    {
      "finding_title": "The missed finding from Step 6",
      "responsible_subagent": 3,
      "gap_type": "prompt_gap | prompt_ambiguity | missing_context | scope_limitation | no_skill_gap",
      "explanation": "Why this subagent missed it and how the improvement prevents recurrence",
      "target_file": "path to file being modified",
      "change_type": "add_checklist_item | rewrite_checklist_item | add_to_what_to_read | add_claude_md_rule | add_memory | no_change",
      "old_text": "existing text to replace (null for additions)",
      "new_text": "new or replacement text",
      "location_hint": "section name or after which existing item to insert"
    }
  ],
  "recurring_patterns": [
    {
      "pattern": "Description of recurring gap",
      "affected_subagents": [2, 5],
      "structural_proposal": "Description of structural improvement"
    }
  ],
  "summary": "One-line summary of proposed improvements"
}
```

#### 7b: Present improvements for user approval

Present each proposed improvement concisely:

```
**Improvement 1** — Subagent #3 (Ordering & Cleanup)
Gap: prompt_gap — checklist doesn't verify X
Proposed: Add checklist item to references/subagent-prompts.md
> "- **New check**: <exact text>"
Apply? [y/n]
```

If recurring patterns were found, present structural proposals separately:

```
**Recurring pattern**: <description>
Affects: Subagents #2, #5
Structural proposal: <description>
Apply? [y/n]
```

**Do NOT apply any improvement without explicit user approval.** Each improvement is approved or rejected independently.

#### 7c: Apply approved improvements

For each approved improvement:
1. Apply the edit to the target file (`references/subagent-prompts.md`, `CLAUDE.md`, or a memory file)
2. If adding a memory file, also update the memory index at `MEMORY.md`
3. After all edits, verify the modified files are syntactically coherent (no broken markdown, no orphaned references)

#### 7d: Write improvements to review document

Append a `### Skill Improvements Applied` section to the current review pass:

```markdown
### Skill Improvements Applied
| # | Finding | Subagent | Gap type | Change | Status |
|---|---|---|---|---|---|
| 1 | <finding> | #N | prompt_gap | Added checklist item to subagent-prompts.md | Applied |
| 2 | <finding> | #N | no_skill_gap | — | Skipped (no gap) |
| 3 | <finding> | #N | prompt_ambiguity | Rewrote checklist item | Rejected by user |
```

## Important Notes

- Each subagent reads source files independently — the main agent does NOT pre-read files for them
- All 6 subagent launches must be in a single message for true parallelism
- If a subagent fails to return valid JSON, treat as FAIL with a parse error note
- Cite specific step numbers and file paths in every finding
- If the plan is solid, say so clearly — a clean review is a useful result
- Multiple reviews of the same plan accumulate in one file (append, don't overwrite)
- The `reviews/` directory is at the project root, NOT nested inside `plans/`
