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

The review runs as a loop with up to 3 passes. Each pass executes Steps 2-8 below. Between passes, the user answers design decisions via `AskUserQuestion`. The loop exits early if:

- **A pass produces 0 critical + 0 major findings** → plan is clean, stop reviewing
- **Pass 3 completes** → hard cap reached; any remaining issues are tagged "resolve during implementation" in the review document

After the final pass (whether early exit or Pass 3), proceed to Step 9 (post-loop coherence check), then Steps 10-11 (root cause analysis and skill improvement) if prior reviews exist.

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

### Step 1c: Detect Master Plan (if any)

Some plans are sub-plans of a multi-PR master plan — the master encodes cross-phase contracts that reviewers cannot reconstruct from the sub-plan alone (e.g., "Phase 3 typed AppState.utubs as unknown[] specifically for Phase 6 to narrow"). Detect the master with a two-tier check:

1. **Primary signal (explicit link)** — Read the first ~40 lines of the plan. If a `**Master plan:**` field exists, extract its path.
2. **Fallback signal (auto-discovery)** — Glob `plans/*/*-master.md`. For each match, grep for either:
   - The current plan's filename (without extension), OR
   - The current branch name (from `git branch --show-current`)
   If any master references the current plan/branch, use that master path.

If a master plan is found, store `<master-plan-path>` for Step 2. If no master exists, record `<master-plan-path>` as null and proceed.

If the plan appears to be a sub-plan (lives in a folder referenced by `**Sub-plan:**` from any master) but no master plan is detected by either signal, flag this to the user as a skill setup warning — the reviewers will miss cross-phase context.

### Step 2: Launch 6 Parallel Review Subagents

Launch **all 6 subagents in parallel** using the Agent tool with **minimal prompts**. Each subagent reads its own instructions from individual reference files — the orchestrator does NOT inline the full checklist or response format.

**Subagent prompt template** (send this to each, filling in the blanks):

> You are Subagent #N (<Role Name>) reviewing the plan at `plans/<topic>/<plan-name>.md`.
>
> 1. Read `.claude/skills/plan-reviewer/references/common-response-format.md` for the response format and rules, then read `.claude/skills/plan-reviewer/references/<sa-file>` for your specific review checklist. Follow those instructions exactly.
> 2. <If master plan detected:> Read the master plan at `<master-plan-path>` FIRST to understand cross-phase context — which phases precede/follow this one, and what shared invariants (types, contracts, data shapes) are staged across phases. Every finding about a "type that's too wide" or "shared module change" must be evaluated against the master's staging plan before being classified as a regression vs. intentional.
> 3. Read the plan in full, then read the source files relevant to your review area.
> 4. Write your complete JSON response to `plans/<topic>/tmp/<role>.md` **using the `Write` tool** — NEVER `cat <<EOF`, `python3 << 'EOF'`, `cat >`, `tee`, `printf >`, `echo >`, or any Bash heredoc/redirect (any heredoc or inline script with `{` + quotes trips the brace+quote security prompt).
> 5. Return only: `Written to <path>`.
>
> **Do not defer any dimension to a follow-up pass.** Every checklist item must be evaluated.
> <Pass 2+ only: "This is Pass N. Do not re-flag issues already fixed. Prior fixes: [concise bullet list of fix titles from earlier passes]">

**Key rules:**
- Each subagent reads source files independently — the main agent does NOT pre-read files
- All 6 launches must be in a **single message** for true parallelism
- Use `model: sonnet` for all review subagents
- NEVER use `subagent_type: "Explore"` — Explore agents cannot use the Write tool. Omit `subagent_type` (defaults to general-purpose)

Subagents (all launched in a single message):

| # | Name | SA reference file | Output filename |
|---|---|---|---|
| 1 | Correctness & Accuracy | `sa1-correctness.md` | `correctness.md` |
| 2 | Full-Stack Trace | `sa2-full-stack-trace.md` | `full-stack-trace.md` |
| 3 | Ordering, Dependencies & Cleanup | `sa3-ordering.md` | `ordering.md` |
| 4 | Codebase Integration & Conventions | `sa4-integration.md` | `integration.md` |
| 5 | Verification & Test Coverage | `sa5-verification.md` | `verification.md` |
| 6 | Completeness, Risk & Specificity | `sa6-completeness.md` | `completeness.md` |

### Step 2a: Prior-Fix Verifier (Pass 2+ only)

On Pass 2 and Pass 3, launch a 7th subagent **in the same single message** as the 6 reviewers. This subagent reads the review file's prior passes, extracts every `[x]` item (mechanical fixes and `**Chosen:**` DD resolutions), and re-verifies each is actually present in the current plan text and resolves the originally-flagged root cause.

Prompt template:

> You are the Prior-Fix Verifier for a Pass N review.
>
> 1. Read the review file at `plans/<topic>/reviews/<plan-name>-review.md`.
> 2. Extract every `[x]` item from prior passes' Mechanical Fixes checklists AND every filled `**Chosen:**` field from prior DDs.
> 3. For each item, re-read the current plan (`plans/<topic>/<plan-name>.md`) and confirm the fix is present and correctly addresses the root cause described in the original finding.
> 4. Write a JSON response to `plans/<topic>/tmp/prior-fix-regressions.md` listing ANY regressions as critical findings. Each regression has: `{ id, prior_pass, fix_type (mechanical|dd), title, expected, actual, severity: "critical" }`. Empty array if none.
>
> Use the Write tool — NEVER cat <<EOF, python3 << 'EOF', cat >, tee, printf >, echo >, or any Bash heredoc/redirect.
> Return only: `Written to <path>`

### Step 3: Collect and Validate Results

After all 6 subagents return their one-line confirmations, verify each `plans/<topic>/tmp/<role>.md` file exists. The role filenames are: `correctness.md`, `full-stack-trace.md`, `ordering.md`, `integration.md`, `verification.md`, `completeness.md`.

**Use the Glob tool** (`Glob(pattern: "plans/<topic>/tmp/*.md")`) to check for the files — **never use Bash `ls` with brace expansion** (`{a,b,c}`) as it triggers sandbox security prompts.

For each file:
- If a file is missing or contains invalid JSON, note it — the coordinator (Step 3b) will treat that reviewer as FAIL with a parse error finding

### Step 3b: Launch Coordinator Subagent

After confirming all 6 files are present, launch a **single coordinator subagent** to deduplicate, conflict-detect, and produce two output files.

The coordinator subagent prompt:

> Read `.claude/skills/plan-reviewer/references/coordinator.md` for the full coordinator instructions. The 6 reviewer files are at `plans/<topic>/tmp/` — specifically: `correctness.md`, `full-stack-trace.md`, `ordering.md`, `integration.md`, `verification.md`, `completeness.md`. Follow the coordinator workflow, then write TWO files:
>
> 1. **`plans/<topic>/tmp/coordinator.md`** — the full JSON output (verdicts, summaries, files_read, findings) as specified in the reference file.
> 2. **`plans/<topic>/tmp/coordinator-summary.md`** — a short summary for the orchestrator containing ONLY:
>    - `verdicts`: one-line per reviewer (`correctness: PASS/FAIL`, etc.)
>    - `counts`: `{critical: N, major: N, minor: N}` (deduplicated totals)
>    - `mechanical_count`: number of findings with `fix_type: "mechanical"`
>    - `design_decision_count`: number of findings with `fix_type: "design_decision"`
>    - `design_decision_titles`: list of DD finding titles (one line each) — the orchestrator needs these for AskUserQuestion prompts
>    - `design_decision_options`: **REQUIRED** — map of DD title → array of option strings (e.g., `{"DD title 1": ["Option A: description", "Option B: description"]}`). The orchestrator uses this to present DDs without reading the full coordinator file.
>
> **On Pass 2+:** Also read `plans/<topic>/tmp/prior-fix-regressions.md` (if it exists). Merge each regression listed there into the `findings` array as a critical finding with `sources: ["Prior-Fix Verifier"]` and `fix_type: "mechanical"`. If the file does not exist (Pass 1 or verifier failed), skip this merge silently.
>
> Return only: `Written to plans/<topic>/tmp/coordinator.md and coordinator-summary.md`

- Uses `model: sonnet` for speed
- The orchestrator reads ONLY `coordinator-summary.md` — never `coordinator.md` directly. The full findings file is consumed by the fixing subagents (Step 4) and the writer subagent (Step 7).

### Step 4: Auto-Apply Mechanical Fixes

Read `plans/<topic>/tmp/coordinator-summary.md` to get the count and titles of mechanical findings. Then launch **one or more fixing subagents** in parallel. Each fixing subagent reads `plans/<topic>/tmp/coordinator.md` directly to get its assigned findings.

**Batching strategy:** Group mechanical findings into batches of ~5-8 per subagent (rather than one subagent per finding) to reduce subagent overhead. Each batch subagent:

1. Reads `plans/<topic>/tmp/coordinator.md` to extract its assigned findings (by title or index range)
2. Reads the plan file
3. Applies each mechanical fix (edits to plan text only — never source files)
4. After each edit, verifies surrounding plan text is coherent
5. Returns a JSON summary of applied/skipped fixes

**All fixing subagents launch in a single message** for true parallelism. After all return, collect results into `applied` and `skipped` lists.

**Skipped items**: If a fixing subagent discovers that its "mechanical" fix actually requires a design choice, it MUST skip it and explain why. Skipped items are promoted to design decisions.

**The orchestrator NEVER reads `coordinator.md` directly.** The full findings are consumed by the fixing subagents and, later, the writer subagent (Step 7).

**Do NOT apply any changes to source files — only the plan document.**

### Step 5: Present Design Decisions via AskUserQuestion

The orchestrator has the DD titles and options from `coordinator-summary.md` (`design_decision_titles` and `design_decision_options` — both REQUIRED fields). Use these to construct AskUserQuestion prompts without reading the full coordinator file.

Present each design decision using `AskUserQuestion`:

**Constraints:**
- Max 4 questions per call, each with max 4 options
- Batch across multiple calls if needed
- `multiSelect: false` (DDs are mutually exclusive)

**Mapping:**
- `question`: `"DD-N: [Step M] <finding title>?"` — include enough context for the user to decide
- `header`: `"DD-N"` (max 12 chars)
- `options`: label (1-5 words) + description (trade-off) + optional `preview` (code snippet)

**Do NOT apply design decisions to the plan without explicit user confirmation.**

### Step 6: Apply User's Design Decisions via Subagent

**IMPORTANT:** Launch a single subagent to handle all DD resolution work. The main orchestrator agent must NOT read/edit plan files or review files directly for DD application — this pollutes the main context window with large file contents. Instead, the subagent receives:
- The plan file path and review file path
- All user answers (DD number → chosen option text and any user notes)
- Instructions to: (1) apply each chosen option to the plan, (2) update the `**Chosen:**` field in the review document, (3) if the user selected "Other" with custom text, apply that instead

The subagent reads the files, makes all edits, and returns a summary of what was changed. The orchestrator only needs the summary to continue.

### Step 7: Write Review Document via Subagent

**The orchestrator does NOT read `coordinator.md` or write the review document directly.** Instead, launch a **writer subagent** that handles all review document construction. By this point, all mechanical fixes have been applied (Step 4) and all DDs have been resolved (Steps 5-6) — the writer has the full picture.

The writer subagent prompt:

> You are a review document writer. Read `plans/<topic>/tmp/coordinator.md` (the full coordinator output) and write the review section into `plans/<topic>/reviews/<plan-name>-review.md`.
>
> Create `plans/<topic>/reviews/` if it doesn't exist. If the review file already exists, **append** a new dated section — do not overwrite.
>
> **Pass info:** This is Pass N. Date: <YYYY-MM-DD>. Use heading `## Review — <YYYY-MM-DD>` (Pass 1) or `## Review — <YYYY-MM-DD> (Pass N)` (Pass 2+).
>
> **Applied mechanical fixes:** The following fixes were already applied to the plan before you ran: [list from Step 4 applied results]. Mark each corresponding item as `[x] _(applied)_` when writing the Mechanical Fixes checklist.
>
> **Resolved DDs:** The following DD choices were applied before you ran: [list from Step 6 summary]. Fill in the `**Chosen:**` field for each.
>
> **Document structure:** Use `classification` and `sources` from each finding for attribution: `duplicate` → append `*(flagged by: Subagent A, Subagent B)*`; `conflict` → render as a design decision naming disagreeing subagents.
>
> **Coverage checklist mapping:** Mark `[x]` if the primary subagent for that area reported reading relevant files (check `files_read`):
> - Imports → #3 Ordering | Type annotations → #1 Correctness | Error handling → #2 Full-Stack Trace
> - Test coverage → #5 Verification | Breaking changes → #6 Completeness | Config → #4 Integration | Naming → #4 Integration
>
> **DD numbering:** Design decisions use sequential IDs continuing from prior passes. Read the existing file to find the highest DD-N, then start from DD-(N+1). If no prior DDs exist, start at DD-1.
>
> **`### Resolve During Implementation` section:** Include ONLY items that are genuinely unresolved after Steps 4-6 (i.e., skipped mechanicals that could not be applied, or DDs where no option was chosen). If all mechanicals and DDs were resolved, omit this section entirely or write "None."
>
> Write the review section using this structure:
> ```
> ### Summary — 2-3 sentences
> ### Subagent Results — table with verdicts and finding counts
> ### Findings — grouped by Critical/Major/Minor (omit empty categories)
> ### Verification Gaps — steps lacking verification
> ### To-Do: Mechanical Fixes — checklist ([x] _(applied)_ for applied; [ ] with reason for skipped)
> ### Design Decisions — each with DD-N, context, options table, filled Chosen field
> ### Verdict — one of: Ready / Proceed after minor / Requires changes
> ### Coverage Checklist — 7-area table
> ```
>
> Return only: `Written to <review-file-path>`

- Uses `model: sonnet` for speed
- The orchestrator reads ONLY `coordinator-summary.md` (from Step 3b) — never the full coordinator output or the review file

### Step 8: Report and Loop Decision

#### 8a: Present results to user

Present a concise summary using data from `coordinator-summary.md` and fix subagent results:
- Current pass number (e.g., "Pass 1 of 3")
- Per-reviewer verdicts
- Count of critical / major / minor findings
- **Mechanical fixes applied** (count)
- **Mechanical fixes skipped** (if any, with reasons)
- **DD choices applied** (count)
- Path to the review file

#### 8b: Loop decision

After the writer completes, evaluate:

1. **Early exit check**: Did this pass produce 0 critical + 0 major findings?
   - **Yes** → Skip remaining passes. Print: "Pass N clean (0 critical, 0 major). Plan is ready for implementation. Ready to run: `/run-plan <plan-filename>`" (where `<plan-filename>` is the plan file's basename without extension, e.g. `openapi-type-generation-pipeline`). Delete all files in `plans/<topic>/tmp/`. Proceed to Step 9.
   - **No** → Continue to next pass.

2. **Hard cap check**: Is this Pass 3?
   - **Yes** → Stop reviewing. Print: "Pass 3 complete (hard cap). Remaining issues tagged for implementation. Ready to run: `/run-plan <plan-filename>`" (where `<plan-filename>` is the plan file's basename without extension). Delete all files in `plans/<topic>/tmp/`. Proceed to Step 9.
   - **No** → Print: "Pass N complete. Starting Pass N+1..." and loop back to **Step 2**.

### Step 9: Post-Loop Coherence Check

After the loop exits (early exit OR Pass 3 hard cap), launch one final lightweight subagent to verify the review document is internally consistent with the plan:

Prompt template:

> You are the Post-Loop Coherence Verifier.
>
> 1. Read the review at `plans/<topic>/reviews/<plan-name>-review.md` (full file).
> 2. For every `**Chosen:**` field in every pass's Design Decisions section, identify what the chosen option says should change in the plan.
> 3. Read `plans/<topic>/<plan-name>.md` and verify each Chosen decision has a corresponding instruction in the plan text (fuzzy match on key phrases — exact wording not required).
> 4. Check the `### Resolve During Implementation` section (if present) does NOT list items that have a filled `**Chosen:**` field elsewhere in the review.
> 5. Report any inconsistencies as a bullet list. If all coherent, return exactly "Coherent".
>
> Return the bullet list or "Coherent" directly (this subagent does NOT write a file — it returns findings inline).

If the subagent returns "Coherent", proceed to Steps 10-11 / finish. If it returns inconsistencies, present them to the user with AskUserQuestion offering:
- **Auto-fix** — spawn a corrector subagent to reconcile plan vs. review
- **Accept as-is** — user will handle manually
- **Show details** — print the full list and re-ask

This check runs regardless of early exit vs. hard cap. It is cheap (one subagent, ~1 min) and catches the class of bugs where the writer ran before DDs were resolved.

### Steps 10-11: Root-Cause Analysis & Skill Self-Improvement (conditional)

**Skip if this is the first review for the plan.**

If prior reviews exist and the current pass found findings that prior passes missed, read `.claude/skills/plan-reviewer/references/self-improvement-workflow.md` and follow Steps 6 and 7 from that file.

## Important Notes

### Orchestrator Context Budget

**The orchestrator must stay lean.** It is a dispatcher, not a reviewer. Follow these rules strictly:

- **NEVER read `coordinator.md`** (the full findings JSON). Read only `coordinator-summary.md`.
- **NEVER read or write the review document** directly. Delegate to the writer subagent (Step 7).
- **NEVER inline the full subagent prompt text.** Send the minimal template (Step 2) — subagents read the reference file themselves.
- **NEVER read the plan file** in the orchestrator. Subagents read it independently.
- The orchestrator's job is: launch subagents → read summary → apply mechanicals (Step 4) → present DDs to user (Step 5) → apply DD choices (Step 6) → run writer (Step 7) → report + loop (Step 8) → coherence check (Step 9). That's it.

### General Rules

- Each subagent reads source files independently — the main agent does NOT pre-read files for them
- All 6 subagent launches must be in a single message for true parallelism
- If a subagent fails to return valid JSON, the coordinator (Step 3b) handles it as a FAIL with a parse error finding — do not attempt to handle it in the orchestrator
- Cite specific step numbers and file paths in every finding
- If the plan is solid, say so clearly — a clean review is a useful result
- Multiple reviews of the same plan accumulate in one file (append, don't overwrite — the writer subagent in Step 7 handles this)
- The review file lives at `plans/<topic>/reviews/<plan-name>-review.md`. Derive `<topic>` from the plan file's parent directory.
- **The coordinator subagent (Step 3b) guarantees non-contradictory mechanical fix items.** Any finding where two reviewers suggest incompatible plan edits to the same step is escalated to a design decision before the parallel fixing subagents run — so they never receive items that conflict with each other.
