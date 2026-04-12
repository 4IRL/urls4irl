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

- Search `plans/**/` recursively for a file matching **$0** (fuzzy match on filename)
- Read the full plan document
- Derive `<topic>` from the plan file's parent directory (e.g., if the plan is at `plans/auth/my-plan.md`, `<topic>` is `auth`)

### Step 1b: Prepare tmp directory

Before launching subagents, create `plans/<topic>/tmp/` if it does not already exist.

### Step 2: Launch 6 Parallel Review Subagents

Launch **all 6 subagents in parallel** using the Agent tool with **minimal prompts**. Each subagent reads its own instructions from individual reference files — the orchestrator does NOT inline the full checklist or response format.

**Subagent prompt template** (send this to each, filling in the blanks):

> You are Subagent #N (<Role Name>) reviewing the plan at `plans/<topic>/<plan-name>.md`.
>
> 1. Read `.claude/skills/plan-reviewer/references/common-response-format.md` for the response format and rules, then read `.claude/skills/plan-reviewer/references/<sa-file>` for your specific review checklist. Follow those instructions exactly.
> 2. Read the plan in full, then read the source files relevant to your review area.
> 3. Write your complete JSON response to `plans/<topic>/tmp/<role>.md`.
> 4. Return only: `Written to <path>`.
>
> **Do not defer any dimension to a follow-up pass.** Every checklist item must be evaluated.
> <Pass 2+ only: "This is Pass N. Do not re-flag issues already fixed. Prior fixes: [concise bullet list of fix titles from earlier passes]">

**Key rules:**
- Each subagent reads source files independently — the main agent does NOT pre-read files
- All 6 launches must be in a **single message** for true parallelism
- Use `model: sonnet` for all review subagents

Subagents (all launched in a single message):

| # | Name | SA reference file | Output filename |
|---|---|---|---|
| 1 | Correctness & Accuracy | `sa1-correctness.md` | `correctness.md` |
| 2 | Full-Stack Trace | `sa2-full-stack-trace.md` | `full-stack-trace.md` |
| 3 | Ordering, Dependencies & Cleanup | `sa3-ordering.md` | `ordering.md` |
| 4 | Codebase Integration & Conventions | `sa4-integration.md` | `integration.md` |
| 5 | Verification & Test Coverage | `sa5-verification.md` | `verification.md` |
| 6 | Completeness, Risk & Specificity | `sa6-completeness.md` | `completeness.md` |

### Step 3: Collect and Validate Results

After all 6 subagents return their one-line confirmations, verify each `plans/<topic>/tmp/<role>.md` file exists. The role filenames are: `correctness.md`, `full-stack-trace.md`, `ordering.md`, `integration.md`, `verification.md`, `completeness.md`.

For each file:
- If a file is missing or contains invalid JSON, note it — the coordinator (Step 3b) will treat that reviewer as FAIL with a parse error finding

### Step 3b: Launch Coordinator Subagent

After confirming all 6 files are present, launch a **single coordinator subagent** to deduplicate, conflict-detect, and produce two output files.

The coordinator subagent prompt:

> Read `.claude/skills/plan-reviewer/references/coordinator.md` for the full coordinator instructions. The 6 reviewer files are at `plans/<topic>/tmp/{correctness,full-stack-trace,ordering,integration,verification,completeness}.md`. Follow the coordinator workflow, then write TWO files:
>
> 1. **`plans/<topic>/tmp/coordinator.md`** — the full JSON output (verdicts, summaries, files_read, findings) as specified in the reference file.
> 2. **`plans/<topic>/tmp/coordinator-summary.md`** — a short summary for the orchestrator containing ONLY:
>    - `verdicts`: one-line per reviewer (`correctness: PASS/FAIL`, etc.)
>    - `counts`: `{critical: N, major: N, minor: N}` (deduplicated totals)
>    - `mechanical_count`: number of findings with `fix_type: "mechanical"`
>    - `design_decision_count`: number of findings with `fix_type: "design_decision"`
>    - `design_decision_titles`: list of DD finding titles (one line each) — the orchestrator needs these for AskUserQuestion prompts
>
> Return only: `Written to plans/<topic>/tmp/coordinator.md and coordinator-summary.md`

- Uses `model: sonnet` for speed
- The orchestrator reads ONLY `coordinator-summary.md` — never `coordinator.md` directly. The full findings file is consumed by the writer subagent (Step 4) and fixing subagents (Step 5b).

### Step 4: Write Review Document via Subagent

**The orchestrator does NOT read `coordinator.md` or write the review document directly.** Instead, launch a **writer subagent** that handles all review document construction.

The writer subagent prompt:

> You are a review document writer. Read `plans/<topic>/tmp/coordinator.md` (the full coordinator output) and write the review section into `plans/<topic>/reviews/<plan-name>-review.md`.
>
> Create `plans/<topic>/reviews/` if it doesn't exist. If the review file already exists, **append** a new dated section — do not overwrite.
>
> **Pass info:** This is Pass N. Date: <YYYY-MM-DD>. Use heading `## Review — <YYYY-MM-DD>` (Pass 1) or `## Review — <YYYY-MM-DD> (Pass N)` (Pass 2+).
>
> **Re-verify prior resolutions (required when appending):** When the file already exists, read every `[x]` item from prior reviews. For each, re-read the actual source file the fix depends on and confirm it resolves the root cause. If incorrect, re-open as a new Critical finding.
>
> **Document structure:** Use `classification` and `sources` from each finding for attribution: `duplicate` → append `*(flagged by: Subagent A, Subagent B)*`; `conflict` → render as a design decision naming disagreeing subagents.
>
> **Coverage checklist mapping:** Mark `[x]` if the primary subagent for that area reported reading relevant files (check `files_read`):
> - Imports → #3 Ordering | Type annotations → #1 Correctness | Error handling → #2 Full-Stack Trace
> - Test coverage → #5 Verification | Breaking changes → #6 Completeness | Config → #4 Integration | Naming → #4 Integration
>
> **DD numbering:** Design decisions use sequential IDs continuing from prior passes. Read the existing file to find the highest DD-N, then start from DD-(N+1). If no prior DDs exist, start at DD-1.
>
> Write the review section using this structure:
> ```
> ### Summary — 2-3 sentences
> ### Subagent Results — table with verdicts and finding counts
> ### Findings — grouped by Critical/Major/Minor (omit empty categories)
> ### Verification Gaps — steps lacking verification
> ### To-Do: Mechanical Fixes — checklist (all [ ] initially)
> ### Design Decisions — each with DD-N, context, options table, empty Chosen field
> ### Verdict — one of: Ready / Proceed after minor / Requires changes
> ### Coverage Checklist — 7-area table
> ```
>
> Return only: `Written to <review-file-path>`

- Uses `model: sonnet` for speed
- The orchestrator reads ONLY `coordinator-summary.md` (from Step 3b) — never the full coordinator output or the review file

### Step 5: Report, Auto-Fix Mechanicals, and Present Design Decisions

#### 5a: Read the summary (orchestrator reads ONLY the summary)

Read `plans/<topic>/tmp/coordinator-summary.md`. This gives the orchestrator:
- Per-reviewer verdicts (PASS/FAIL)
- Deduplicated finding counts (critical, major, minor)
- Mechanical fix count and design decision count
- Design decision titles (needed for AskUserQuestion prompts)

**The orchestrator NEVER reads `coordinator.md` directly.** The full findings are consumed by the fixing subagents (5b) and the writer subagent (Step 4).

#### 5b: Auto-apply mechanical fixes

Launch **one or more fixing subagents** in parallel. Each fixing subagent reads `plans/<topic>/tmp/coordinator.md` directly to get its assigned findings.

**Batching strategy:** Group mechanical findings into batches of ~5-8 per subagent (rather than one subagent per finding) to reduce subagent overhead. Each batch subagent:

1. Reads `plans/<topic>/tmp/coordinator.md` to extract its assigned findings (by title or index range)
2. Reads the plan file
3. Applies each mechanical fix (edits to plan text only — never source files)
4. After each edit, verifies surrounding plan text is coherent
5. Returns a JSON summary of applied/skipped fixes

**All fixing subagents launch in a single message** for true parallelism. After all return, collect results into `applied` and `skipped` lists.

**Skipped items**: If a fixing subagent discovers that its "mechanical" fix actually requires a design choice, it MUST skip it and explain why. Skipped items are promoted to design decisions.

#### 5c: Update review document with fix results

Launch a subagent to update the review document's mechanical fixes checklist:
- Mark each applied fix as `[x]` with `_(applied)_`
- Mark skipped items as `[ ]` with skip reason
- The subagent reads the review file and edits it directly — the orchestrator does not

#### 5d: Present results to user

Present a concise summary using data from `coordinator-summary.md` and fix subagent results:
- Current pass number (e.g., "Pass 1 of 3")
- Per-reviewer verdicts
- Count of critical / major / minor findings
- **Mechanical fixes applied** (count)
- **Mechanical fixes skipped** (if any, with reasons)
- Path to the review file

**Do NOT apply design decisions to the plan without explicit user confirmation.**
**Do NOT apply any changes to source files — only the plan document.**

#### 5e: Present design decisions via AskUserQuestion

The orchestrator has the DD titles from `coordinator-summary.md`. For each DD, it needs enough context to construct the AskUserQuestion — the title and a brief description are sufficient. If the summary lacks option details, the orchestrator may read ONLY the specific DD entries from `coordinator.md` (grep for the finding title, read ~10 lines of context) rather than reading the entire file.

Present each design decision using `AskUserQuestion`:

**Constraints:**
- Max 4 questions per call, each with max 4 options
- Batch across multiple calls if needed
- `multiSelect: false` (DDs are mutually exclusive)

**Mapping:**
- `question`: `"DD-N: [Step M] <finding title>?"` — include enough context for the user to decide
- `header`: `"DD-N"` (max 12 chars)
- `options`: label (1-5 words) + description (trade-off) + optional `preview` (code snippet)

**After the user answers all DDs:**

#### 5f: Apply user's design decisions via subagent

**IMPORTANT:** Launch a single subagent to handle all DD resolution work. The main orchestrator agent must NOT read/edit plan files or review files directly for DD application — this pollutes the main context window with large file contents. Instead, the subagent receives:
- The plan file path and review file path
- All user answers (DD number → chosen option text and any user notes)
- Instructions to: (1) apply each chosen option to the plan, (2) update the `**Chosen:**` field in the review document, (3) if the user selected "Other" with custom text, apply that instead

The subagent reads the files, makes all edits, and returns a summary of what was changed. The orchestrator only needs the summary to continue.

#### 5g: Loop decision

After applying DD choices, evaluate:

1. **Early exit check**: Did this pass produce 0 critical + 0 major findings?
   - **Yes** → Skip remaining passes. Print: "Pass N clean (0 critical, 0 major). Plan is ready for implementation. Ready to run: `/run-plan <plan-filename>`" (where `<plan-filename>` is the plan file's basename without extension, e.g. `openapi-type-generation-pipeline`). Delete all files in `plans/<topic>/tmp/`. Proceed to Steps 6-7 if prior reviews exist.
   - **No** → Continue to next pass.

2. **Hard cap check**: Is this Pass 3?
   - **Yes** → Stop reviewing. If any unresolved issues remain, append a `### Resolve During Implementation` section to the review document listing them. Print: "Pass 3 complete (hard cap). Remaining issues tagged for implementation. Ready to run: `/run-plan <plan-filename>`" (where `<plan-filename>` is the plan file's basename without extension). Delete all files in `plans/<topic>/tmp/`. Proceed to Steps 6-7.
   - **No** → Print: "Pass N complete. Starting Pass N+1..." and loop back to **Step 2**.

### Steps 6-7: Root-Cause Analysis & Skill Self-Improvement (conditional)

**Skip if this is the first review for the plan.**

If prior reviews exist and the current pass found findings that prior passes missed, read `.claude/skills/plan-reviewer/references/self-improvement-workflow.md` and follow Steps 6 and 7 from that file.

## Important Notes

### Orchestrator Context Budget

**The orchestrator must stay lean.** It is a dispatcher, not a reviewer. Follow these rules strictly:

- **NEVER read `coordinator.md`** (the full findings JSON). Read only `coordinator-summary.md`.
- **NEVER read or write the review document** directly. Delegate to the writer subagent (Step 4) and update subagent (Step 5c).
- **NEVER inline the full subagent prompt text.** Send the minimal template (Step 2) — subagents read the reference file themselves.
- **NEVER read the plan file** in the orchestrator. Subagents read it independently.
- The orchestrator's job is: launch subagents → read summary → present DDs to user → launch fix/DD subagents → evaluate loop condition. That's it.

### General Rules

- Each subagent reads source files independently — the main agent does NOT pre-read files for them
- All 6 subagent launches must be in a single message for true parallelism
- If a subagent fails to return valid JSON, the coordinator (Step 3b) handles it as a FAIL with a parse error finding — do not attempt to handle it in the orchestrator
- Cite specific step numbers and file paths in every finding
- If the plan is solid, say so clearly — a clean review is a useful result
- Multiple reviews of the same plan accumulate in one file (append, don't overwrite)
- The review file lives at `plans/<topic>/reviews/<plan-name>-review.md`. Derive `<topic>` from the plan file's parent directory.
- **The coordinator subagent (Step 3b) guarantees non-contradictory mechanical fix items.** Any finding where two reviewers suggest incompatible plan edits to the same step is escalated to a design decision before the parallel fixing subagents run — so they never receive items that conflict with each other.
