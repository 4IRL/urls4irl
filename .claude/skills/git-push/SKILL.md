---
name: git-push
description: Review all unpushed code on the current branch using 7 parallel subagents (Safety & Security, Correctness, Simplicity & Conciseness, Test Coverage, Completeness & Cleanup, Consistency & Style, Integration Risk). Classifies findings as mechanical (auto-fixed via /run-review) or design_decision (presented via AskUserQuestion). Auto-fixes mechanical issues, presents design decisions for user input, re-reviews, then pushes when clean. Creates or updates a GitHub PR after push. Use when asked to push, push code, git push, review-and-push, or create a PR.
---

# Git Push with Multi-Agent Review

Review all code not yet on the remote branch, then push if approved or output findings.

## Branch Guard

Before starting, check the current branch:
1. If on `main` or `master`:
   - Run `gmas` to ensure main is up to date
   - Suggest a branch name based on the task context (e.g., `refactor/splash-validation`, `fix/login-error`)
   - Ask the user: "You're on main. Want me to create and switch to `<suggested-branch>`?"
   - Do NOT proceed until the user confirms and you've switched branches
2. If already on a feature branch: proceed normally

## Workflow

### 0. Squash-Merge Staleness Guard (MANDATORY)

**This check is REQUIRED before any other step. Never skip it.**

Launch a **subagent** to detect if the branch contains commits already squash-merged into main. The subagent reads its full prompt from `.claude/skills/git-push/references/staleness-guard-prompt.md`.

Subagent prompt:

```
Read .claude/skills/git-push/references/staleness-guard-prompt.md for your full instructions.
Write your result to <tmp-dir>/staleness-check.md.
```

- Uses `model: sonnet` for speed

After the subagent returns, read `<tmp-dir>/staleness-check.md`:

- **`CLEAN`**: Delete `<tmp-dir>/staleness-check.md` and proceed to Step 1.
- **`STALE`**: **STOP.** Do not proceed to Step 1 or any other step.
  1. Inform the user: *"Found N commits on this branch that are already in main (likely squash-merged via a prior PR). This branch must be rebased before pushing, otherwise the PR will contain duplicate/stale changes."*
  2. List the stale commits from the subagent output.
  3. Use `AskUserQuestion` to offer the fix:
     - question: "This branch has N commits already squash-merged into main. Rebase onto main to remove them? This requires a force-push."
     - header: "Stale branch"
     - options: `[{"label": "Rebase and force-push", "description": "Create backup branch, rebase onto main, force-push to update the PR"}, {"label": "Abort push", "description": "Stop here — I'll handle the rebase manually"}]`
  4. If the user selects "Rebase and force-push":
     - Create a backup branch: `git branch backup/<branch-name>`
     - Create a new branch from main, apply the net diff (`git diff origin/main <branch> | git apply`), commit, and force-push
  5. **Only proceed to Step 1 after a re-run of the subagent returns `CLEAN`.**

### 1. Gather the Diff

Determine what code exists locally but not on the remote:

```bash
# Get branch name and remote tracking info
BRANCH=$(git branch --show-current)

# Check if remote branch exists
if git rev-parse --verify origin/$BRANCH >/dev/null 2>&1; then
  # Diff against remote branch
  git diff origin/$BRANCH...HEAD
  git diff origin/$BRANCH...HEAD --stat
  git log origin/$BRANCH..HEAD --oneline
else
  # New branch — diff against main
  git diff origin/main...HEAD
  git diff origin/main...HEAD --stat
  git log origin/main..HEAD --oneline
fi

# Also include uncommitted staged/unstaged changes
git diff HEAD
git status --short
```

If the diff is empty (nothing to push), inform the user and stop.

### 2. Resolve Plan Folder

Launch a **subagent** to pick the `plans/<folder>/` directory where this branch's push review belongs. The subagent enumerates existing plan folders, scores each against the branch name, and writes a structured result. The orchestrator never holds the scoring rules — they live in the reference file.

Subagent prompt:

```
Read .claude/skills/git-push/references/plan-folder-resolver-prompt.md for your full instructions.
Branch name: <BRANCH>
Write your result to $TMPDIR/plan-folder.md.
```

- Uses `model: sonnet` for speed.
- Output goes to `$TMPDIR` initially because `<plan-dir>` (and therefore `<tmp-dir>`) is not yet known.

After the subagent returns, read `$TMPDIR/plan-folder.md` and parse the JSON (schema is defined in the reference file). Branch on `decision`:

- **`match`**: Set `<plan-dir>` to the returned `plan_dir`. Skip to "Set tmp directory" below.
- **`ambiguous`** or **`no_match`**: Present `AskUserQuestion` with:
  - One option per entry in `candidates` (label = bare folder name, description = `summary` from the entry, falling back to `"(no plan file)"` if `summary` is null).
  - One option labeled `"Create plans/<suggested_new_folder>/"` with description `"New folder for this branch"`.
  - The user may also pick "Other" to type a custom folder name.
  - `multiSelect: false`. `header: "Plan folder"`.
  After the user answers: if they chose "Create …", `mkdir -p plans/<suggested_new_folder>/tmp/` and set `<plan-dir>` to `plans/<suggested_new_folder>`. Otherwise set `<plan-dir>` to the chosen folder path.

**Set tmp directory:**
- Set `<tmp-dir>` to `<plan-dir>/tmp/` and `mkdir -p` it.
- Move `$TMPDIR/plan-folder.md` to `<tmp-dir>/plan-folder.md` (or delete it — the orchestrator no longer needs it).

**CRITICAL: `plans/tmp/` must never be used as the final storage location for plans, reviews, or any persistent document.** `<tmp-dir>` (`<plan-dir>/tmp/`) is for transient subagent output only — files are deleted after evaluation. Final documents (push reviews, plans) always go under `<plan-dir>/`.

Store `<plan-dir>` and `<tmp-dir>` for use in all subagent prompts below.

### 3. Launch 7 Parallel Review Subagents

Read `.claude/skills/git-push/references/subagent-prompts.md` for the full prompt definitions and expected response format.

Launch **all 7 subagents in parallel** using the Agent tool with **no `subagent_type`** (defaults to general-purpose — NEVER use `subagent_type: "Explore"`, which cannot use the Write tool). Each subagent:
- Receives the full diff output from Step 1
- Receives its specific review focus area from the reference file
- Receives `<tmp-dir>` and its assigned output filename (see table below)
- Writes its JSON response to `<tmp-dir>/<role>.md` and returns only: `Written to <path>`
- Uses `model: sonnet` for speed

Subagents (all launched in a single message):

| # | Name | Focus | Output file |
|---|---|---|---|
| 1 | Safety & Security | XSS, injection, secrets, OWASP, destructive ops | `<tmp-dir>/safety-security.md` |
| 2 | Correctness | Logic errors, edge cases, type issues, wrong APIs | `<tmp-dir>/correctness.md` |
| 3 | Simplicity & Conciseness | Over-engineering, dead code, verbose patterns | `<tmp-dir>/simplicity.md` |
| 4 | Test Coverage | Missing tests, untested new behavior, coverage gaps | `<tmp-dir>/test-coverage.md` |
| 5 | Completeness & Cleanup | Debug artifacts, TODOs, commented code, stubs | `<tmp-dir>/completeness.md` |
| 6 | Consistency & Style | Project conventions, naming, patterns, imports | `<tmp-dir>/consistency.md` |
| 7 | Integration Risk | Breaking changes, missing migrations, cross-module impact | `<tmp-dir>/integration-risk.md` |

### 4a. Launch Coordinator Subagent

After all 7 subagent files are written, launch a **single coordinator subagent** to deduplicate and conflict-detect across all findings before writing the push review.

Read `.claude/skills/git-push/references/subagent-prompts.md` for the full coordinator prompt definition.

The coordinator subagent:
- Receives the paths to all 7 `<tmp-dir>/<role>.md` files and the full diff from Step 1
- Groups findings by file + proximity, classifies each group as `unique`, `duplicate`, or `conflict`
- Escalates any `conflict` to `fix_type: "design_decision"` regardless of original `fix_type`
- Writes consolidated output to `<tmp-dir>/coordinator.md`
- Returns only: `Written to <tmp-dir>/coordinator.md`
- Uses `model: sonnet` for speed

### 4b. Evaluate and Classify Results

Read `<tmp-dir>/coordinator.md` written by the coordinator in Step 4a.

Parse:
- `reviewer_verdicts` — per-reviewer PASS/FAIL map (used for Step 7c re-review targeting)
- `findings` — deduplicated, conflict-annotated finding list

Evaluate:

- **ALL PASS, no findings at all**: Proceed to Step 8 (push).
- **ALL PASS, only minor findings**: Write findings (Step 5), classify. If any findings exist (mechanical or design), proceed to Step 6. Otherwise proceed to Step 8 (push).
- **ANY FAIL**: Write findings (Step 5), classify, proceed to Step 6.

Partition all findings into two lists:
- `mechanical_fixes[]` — all findings with `fix_type: "mechanical"`
- `design_decisions[]` — all findings with `fix_type: "design_decision"` (includes escalated conflicts)

Track which reviewers returned FAIL from `reviewer_verdicts` (needed for re-review in Step 7c).

Track `fix_round = 1` (used in Step 7c to cap fix-review loops).

Capture `PRE_FIX_SHA = $(git rev-parse HEAD)` — the commit hash before any fix rounds begin. This anchor is captured **once** and reused across all re-review passes in Step 7c to scope the fix diff.

### 5. Write Findings

Push review file lives at `<plan-dir>/reviews/push-review-<branch>.md`, where `<plan-dir>` was resolved in Step 2. `mkdir -p <plan-dir>/reviews/` if it does not exist. `plans/tmp/` must never contain final review documents.

#### File and Review Numbering

1. Check if `<plan-dir>/reviews/push-review-<branch>.md` already exists
2. **If it exists**: read the file, find the highest `## Review N` number, and append a new section numbered N+1
3. **If it does not exist**: create the file with a header and start with `## Review 1`

The file header (written only on first creation):
```markdown
# Push Review: <branch>
```

Each review section appended to the file:
```markdown
## Review <N>
Generated: <YYYY-MM-DD HH:MM>
Comparison: <base>...HEAD
Verdict: **BLOCKED** or **PUSHED WITH MINOR FINDINGS**

### Results by Reviewer

#### 1. Safety & Security — <PASS/FAIL>
<summary + findings bullet list>

#### 2. Correctness — <PASS/FAIL>
...

#### 3. Simplicity & Conciseness — <PASS/FAIL>
...

#### 4. Test Coverage — <PASS/FAIL>
...

#### 5. Completeness & Cleanup — <PASS/FAIL>
...

#### 6. Consistency & Style — <PASS/FAIL>
...

#### 7. Integration Risk — <PASS/FAIL>
...

### To-Do: Mechanical Fixes

- [ ] **<Imperative action>** — <file(s) to change> — <what to do specifically>
- [ ] ...

### To-Do: Design Decisions

#### DD-1: <Decision title>
**Context:** <Why this needs a decision — what the review found and why it can't be fixed mechanically.>

| # | Option | Trade-off |
|---|---|---|
| 1 | <Option A> | <Pro/con> |
| 2 | <Option B> | <Pro/con> |

**Chosen:** _(pending)_
```

Omit `### To-Do: Mechanical Fixes` if there are no mechanical findings. Omit `### To-Do: Design Decisions` if there are no design decisions. Each DD must have at least 2 options with trade-offs.

#### Verdict Labels

| Verdict | Meaning |
|---|---|
| **PUSHED** | All PASS, no findings |
| **PUSHED WITH MINOR FINDINGS** | All PASS, minor findings recorded but no fixes needed |
| **RESOLVED — PUSHED** | Had FAILs, all fixed (mechanical + DDs), re-review passed, pushed |
| **BLOCKED** | FAILs remain after 2 fix rounds, or re-review still fails |

#### TO-DO Item Guidelines

Each mechanical fix TO-DO item must be:
- **Self-contained**: Include the file path(s), what to change, and why. The implementer should not need to read the reviewer results above.
- **Imperative**: Start with a verb (Add, Update, Extract, Fix, Remove, Replace).
- **Concrete**: Name the exact file, function, variable, or line to change. Avoid vague items like "fix style issues."
- **One logical change**: Each item should be implementable and verifiable independently.

**Include all findings in the TO-DO list regardless of severity** — minor findings must also be actionable items.

For findings with `classification: "duplicate"` (flagged by multiple reviewers), append a `*(flagged by: Reviewer A, Reviewer B)*` attribution after the item description — this explains why a minor finding appears without inflating its severity.

For findings with `classification: "conflict"` that were escalated to `design_decision`, the DD context must name the disagreeing reviewers and their positions explicitly.

Example:
```markdown
### To-Do: Mechanical Fixes

- [ ] **Fix import ordering in `test_api_route_decorator.py`** — line 13: move `ErrorResponse` import after `ContactResponseSchema` import to maintain alphabetical ordering *(flagged by: Correctness, Consistency)*
- [ ] **Remove dead `None` default from `getattr`** — `tests/unit/schemas/test_schema_descriptions.py` line 20: change `getattr(module, name, None)` to `getattr(module, name)` since `name` comes from `__all__` and is guaranteed to exist

### To-Do: Design Decisions

#### DD-1: Replace `HealthDbResponseSchema` with `StatusMessageResponseSchema`?
**Context:** `HealthDbResponseSchema` duplicates `StatusMessageResponseSchema` — identical status + message fields. But the health endpoint might diverge later.

| # | Option | Trade-off |
|---|---|---|
| 1 | Replace with `StatusMessageResponseSchema` | Eliminates duplication now; easy to split later if needed |
| 2 | Keep separate | Explicit coupling to health domain; minor duplication |

**Chosen:** _(pending)_

#### DD-2: Inline helper vs keep separate — reviewer conflict
**Context:** Simplicity and Test Coverage disagree on `backend/utils/health.py:67`. Simplicity flags the helper as single-use and suggests inlining. Test Coverage flags the same function as lacking test coverage and suggests keeping it separate so it can be unit-tested directly.

| # | Option | Trade-off |
|---|---|---|
| 1 | Inline the helper (Simplicity) | Removes indirection; function no longer independently testable |
| 2 | Keep separate and add unit test (Test Coverage) | Preserves testability; minor extra indirection |

**Chosen:** _(pending)_
```

After writing the review file, inform the user:
- Which reviewers failed and why (brief)
- Path to the full review file and review number (e.g., "Review 2 appended")
- Count of mechanical fixes and design decisions: `"Found N findings (M mechanical, K design decisions)."`
- Then proceed automatically to Step 6 — do NOT ask the user to run `/run-review` manually.

### 6. Auto-Fix Mechanical Findings via /run-review

If `mechanical_fixes[]` is empty, skip to Step 7.

Inform the user: `"Launching /run-review for M mechanical fixes..."`

Launch `/run-review` as a **subagent** (using the Agent tool) targeting the push review file. The subagent processes all unchecked mechanical fix items through the standard `/run-review` pipeline (each item gets `/next-step-taker` with validation, 3-subagent review, tests, and commit).

Subagent prompt:

```
Run /run-review for "push-review-<branch>".

Process ONLY the items under "### To-Do: Mechanical Fixes" — skip any items
under "### To-Do: Design Decisions".

Important overrides:
- Do NOT pause at the end to ask the user — complete the full workflow and return your final report.
- Follow all CLAUDE.md guidelines.
- CRITICAL: Every Bash call that runs `make` or `docker` MUST set dangerouslyDisableSandbox: true. Never for git commands.
```

After the subagent returns:
1. Read the review file to confirm mechanical items are crossed off
2. Report to user: `"Applied N of M mechanical fixes."`
3. If any mechanical items were NOT crossed off, report which ones and why
4. Proceed to Step 7

### 7. Present and Apply Design Decisions

If `design_decisions[]` is empty, proceed to Step 7c (re-review).

#### Step 7a: Present via AskUserQuestion

Present each design decision using the `AskUserQuestion` tool (max 4 questions per call, max 4 options each):

- `question`: `"DD-N: <finding title>?"` — include enough context for the user to decide without reading the review file
- `header`: `"DD-N"` (max 12 chars)
- `options`: Each option from the DD table
  - `label`: Short name (1-5 words)
  - `description`: Trade-off text
- `multiSelect`: `false`

**All design decisions must be resolved before pushing.** Do not include a "skip" option. The user can always select "Other" to provide a custom approach.

If there are more than 4 DDs, batch across multiple `AskUserQuestion` calls (4 at a time).

#### Step 7b: Apply Design Decisions via /run-review

After the user answers all DDs:

1. Update the review file: fill in `**Chosen:** <user's choice>` for each DD
2. Rewrite each DD's chosen option as an actionable to-do item (imperative, self-contained, concrete) and add it as an unchecked `- [ ]` item under that DD's section in the review file
3. Launch `/run-review` as a **subagent** to process the newly-added DD items

Subagent prompt:

```
Run /run-review for "push-review-<branch>".

Process ONLY the unchecked items under "### To-Do: Design Decisions" —
the mechanical fixes are already complete.

For each design decision, the user has chosen a specific approach. The chosen
option is recorded in the **Chosen:** field above each item. Implement exactly
what the user chose.

Important overrides:
- Do NOT pause at the end to ask the user — complete the full workflow and return your final report.
- Follow all CLAUDE.md guidelines.
- CRITICAL: Every Bash call that runs `make` or `docker` MUST set dangerouslyDisableSandbox: true. Never for git commands.
```

After the subagent returns:
1. Read the review file to confirm DD items are crossed off
2. Report to user: `"Applied N of M design decisions."`

#### Step 7c: Re-Review (verification pass)

After all fixes (mechanical + design decisions) are applied and committed:

**Generate two diffs for re-review subagents:**

1. **Full branch diff** (`origin/main...HEAD`) — provides overall context of what the branch does
2. **Fix-only diff** (`<PRE_FIX_SHA>..HEAD`) — shows only the changes made during fix rounds

`PRE_FIX_SHA` was captured once in Step 4b before any fixes began. Because it is never updated, each re-review pass sees the cumulative fix diff (all prior fix rounds), which lets later passes verify that earlier fixes weren't regressed.

Save both diffs to `<tmp-dir>/` (e.g., `re-review-full.diff` and `re-review-fixes.diff`).

**Re-run only the subagents that originally returned FAIL** (not all 7). Use the same review focus areas from Step 3, but modify the prompt to include both diffs and the following instruction:

```
You are re-reviewing after fixes were applied. You receive two diffs:

1. Full branch diff (full-diff file): the complete branch vs main — use for context only.
2. Fix-only diff (fix-diff file): changes made since the original review — this is your PRIMARY review target.

Your job:
- Verify that the fixes in the fix-only diff correctly address the issues from the original review.
- Check for any NEW issues introduced by the fix commits themselves.
- Do NOT re-flag issues from the original branch code that are resolved in the fix diff.
  If the full branch diff shows problematic code but the fix diff changes that same code,
  the issue is resolved — do not flag it.

When in doubt, read the actual source file at the flagged location to confirm whether
the issue still exists in the current code.
```

Write results to the same `<tmp-dir>/<role>.md` files.

Evaluate re-review results:
- **All now PASS**: Update review file verdict to `**RESOLVED — PUSHED**`. Proceed to Step 8 (push).
- **Still FAIL with new findings**:
  - Increment `fix_round`
  - If `fix_round <= 2`: Write new findings to review file (append as next `## Review N+1` section), classify into mechanical/design, loop back to Step 6 for mechanical fixes / Step 7a for design decisions
  - If `fix_round > 2`: **BLOCK**. Update review file verdict to `**BLOCKED**`. Inform user with review file path. Do NOT push.

### 8. Push

**CRITICAL: Never use bare `git push`.** The repo remote uses SSH, which attributes the push to the user's personal account. This breaks branch protection rules that block self-approval from the last pusher.

**Always push via `.claude/scripts/gh-app-push.sh`.** The script:
- Generates a fresh GitHub App installation token on every invocation.
- Stores the token in a locally-scoped variable (not `GH_TOKEN`), avoiding any chance of a stale env-var PAT shadowing it at URL-expansion time.
- Refuses to push to `main`/`master` and refuses force-push flags.
- Sets upstream tracking after a successful push.

```bash
.claude/scripts/gh-app-push.sh $BRANCH
```

**MANDATORY: Run with `dangerouslyDisableSandbox: true` every time.** The script writes to `.git/config` to persist upstream tracking, which the sandbox blocks. Without `dangerouslyDisableSandbox`, the push itself still succeeds but tracking won't stick — breaking `gmas` / `git cleanup` workflows that rely on `git fetch -p` to detect merged branches.

After a successful push, proceed to Step 9 (PR creation).

After a successful push, delete all files in `<tmp-dir>/` (i.e., `<plan-dir>/tmp/`).

### 9. Create or Update PR

After a successful push, create or update a PR targeting `main`.

#### Environment Requirements

All `gh` commands must:
1. Use the inline `GH_TOKEN=$(...)` prefix — this pattern is exempted from the command substitution hook
2. Use `dangerouslyDisableSandbox: true` — the sandbox blocks TLS connections to `api.github.com`

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr ...
```

**CRITICAL:** Never resolve the token in a separate call and inline the raw value — that leaks secrets into logs and is blocked by the raw token hook. Always use the `GH_TOKEN=$(...)` prefix form.

#### Check for Existing PR

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr view $BRANCH 2>&1
```

- **If a PR exists**: use `gh pr edit` to update title/body if the changes warrant it.
- **If no PR exists**: create one with `gh pr create`.

#### PR Title Format

```
[SUBJECT] Title content
```

Where `SUBJECT` is one of:
- `refactor` — code restructuring without behavior change
- `frontend` — UI/JS/CSS changes
- `backend` — Python/Flask/API changes
- `database` — migrations, model changes
- `tests` — test-only changes

Use the most dominant category. If changes span multiple areas, pick the primary one.

#### PR Body Format

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr create \
  --base main \
  --head "$BRANCH" \
  --title "[SUBJECT] Title" \
  --body "$(cat <<'EOF'
# Summary

Brief overview of what this PR does.

## Problem

What issue or need motivated this change.

## Solutions

What was done to address the problem. Reference key files/functions changed.

## Verification Steps

- Tests added/modified and their markers
- How to manually verify (if applicable)
- Build verification status
EOF
)"
```

#### Apply Labels

After creating or updating the PR, apply labels based on **all changes on the branch** (the full `origin/main...HEAD` diff, not just the latest push). Add **all labels that apply** — multiple labels are expected when changes span areas.

Available labels and when to apply:

| Label | Apply when the diff touches… |
|---|---|
| `backend` | Python code under `backend/` (routes, models, schemas, utils) |
| `frontend` | JavaScript, HTML templates, CSS, or Vite config |
| `database` | Migrations, model column changes, or `flask db` commands |
| `testing` | Test files (`tests/`) or test infrastructure |
| `Infrastructure` | Docker, CI/CD, Makefile, `.github/`, or deployment config |
| `desktop` | Desktop-specific UI code or desktop UI tests |
| `mobile` | Mobile-specific UI code or mobile UI tests |
| `bug` | The change fixes a bug (use commit message/PR context to determine) |
| `enhancement` | The change adds new functionality |
| `documentation` | README, CLAUDE.md, ARCHITECTURE.md, or doc-only changes |

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr edit <PR_NUMBER> --add-label "label1,label2,..."
```

#### Set Milestone

After applying labels, set the appropriate milestone based on the nature and motivation behind **all changes on the branch** (not just the latest push). Choose **one** milestone:

| Milestone | When to use |
|---|---|
| `Bugs` | The PR fixes a bug or corrects broken behavior |
| `Maintenance` | Bug fixes, dependency updates, CI/CD changes, minor cleanup — small fixes that keep things running |
| `MVP v2` | New features, enhancements, refactors, and architectural improvements (e.g., new functionality, migrating to Pydantic, restructuring code) |
| `REH-ch goals` | Stretch/reach goals beyond MVP v2 |

Use the commit messages, branch name, and PR context to determine the best fit. Refactors and code modernization efforts are `MVP v2`, not `Maintenance`.

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr edit <PR_NUMBER> --milestone "<milestone title>"
```

#### Add to Project

After setting the milestone, add the PR to the **"URLS4IRL -> Real Life"** org project (project ID: `PVT_kwDOCEIbTM4Ai9RV`).

First, get the PR's node ID (capture the output as `PR_NODE_ID` for later calls):

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh api graphql -f query='{ repository(owner: "4IRL", name: "urls4irl") { pullRequest(number: <PR_NUMBER>) { id } } }' --jq '.data.repository.pullRequest.id'
```

Then add it to the project (capture the output as `PROJECT_ITEM_ID` for later). Use the `PR_NODE_ID` value from the previous call's output:

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh api graphql -f query="mutation { addProjectV2ItemById(input: { projectId: \"PVT_kwDOCEIbTM4Ai9RV\", contentId: \"<PR_NODE_ID>\" }) { item { id } } }" --jq '.data.addProjectV2ItemById.item.id'
```

Then set the **Status** field to **"In progress"** (field ID: `PVTSSF_lADOCEIbTM4Ai9RVzgbZQoU`, option ID: `42a2e094`). Use the `PROJECT_ITEM_ID` value from the previous call's output:

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh api graphql -f query="mutation { updateProjectV2ItemFieldValue(input: { projectId: \"PVT_kwDOCEIbTM4Ai9RV\", itemId: \"<PROJECT_ITEM_ID>\", fieldId: \"PVTSSF_lADOCEIbTM4Ai9RVzgbZQoU\", value: { singleSelectOptionId: \"42a2e094\" } }) { projectV2Item { id } } }"
```

This is idempotent — safe to run on PRs already in the project.

#### Assign and Request Review

After adding to the project, assign the GitHub App as assignee via GraphQL (bot accounts can't be assigned via `gh pr edit --add-assignee`), then request review from `GPropersi`.

Assign the bot (node ID: `BOT_kgDOCHBJTA`) using the `PR_NODE_ID` value obtained earlier:

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh api graphql -f query='mutation { addAssigneesToAssignable(input: { assignableId: "<PR_NODE_ID>", assigneeIds: ["BOT_kgDOCHBJTA"] }) { assignable { ... on PullRequest { number } } } }'
```

Then request review:

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr edit <PR_NUMBER> --add-reviewer GPropersi
```

#### After PR Creation

Output:
- The PR URL
- Branch name and number of commits
- One-line summary from each review subagent

## Important Notes

- **All test suites have passed before commit** — code reaching this workflow has already passed all relevant test suites (integration, UI, unit, JS). Subagents should NOT flag "tests might fail" or "untested at runtime." The Test Coverage reviewer focuses on whether the diff includes sufficient test code for new/changed behavior, not whether existing tests pass.
- Never push to `main` or `master` — warn the user and abort
- Never force-push
- If there are uncommitted changes, warn the user and ask whether to include them (commit first) or push only committed code
- Push review file lives at `<plan-dir>/reviews/push-review-<branch>.md`, where `<plan-dir>` was resolved by the plan-folder-resolver subagent in Step 2. **Never store final documents (reviews, plans) in `plans/tmp/`.**
- All subagent launches must be in a single message for true parallelism
- If a subagent fails to return valid JSON (or its output file is missing/unreadable), treat it as FAIL with a note about the parse error
- **All design decisions must be resolved before pushing.** The skill blocks until the user has answered every DD via `AskUserQuestion`. There is no "skip" or "defer" option.
- **Max 2 fix-review rounds.** After fixes are applied (Step 6 + 7b), a re-review runs (Step 7c). If new issues appear, the cycle repeats up to 2 times total. After 2 rounds, the skill blocks.
- **`/run-review` is launched as a subagent** for both mechanical fixes (Step 6) and design decision fixes (Step 7b). It runs the full `/next-step-taker` pipeline per item (validate, review, test, commit). The main `/git-push` agent orchestrates but never directly edits source files.
- **The coordinator subagent (Step 4a) guarantees non-contradictory mechanical fix items.** Any finding where two reviewers suggest incompatible changes to the same code is escalated to a design decision before `/run-review` runs — so `/run-review` never receives items that would conflict with each other.
