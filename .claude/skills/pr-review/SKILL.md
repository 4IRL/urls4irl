---
name: pr-review
description: Review a GitHub PR against its plan using 8 parallel subagents (Plan Conformance, Correctness, Code Patterns, Simplicity & Readability, Test Coverage, Security & Safety, Consistency & Style, Documentation & Registry). Writes a distinctly-titled "PR Review for <plan> (PR #N)" record to plans/<topic>/reviews/, raises design decisions via AskUserQuestion, and does NOT post anything to GitHub. Use when asked to review a PR, audit a pull request against its plan, or produce a local PR review record. Argument is the PR number (e.g., "/pr-review 42") — omit to auto-detect from the current branch.
argument-hint: PR-number (optional — auto-detects from current branch)
---

# PR Review with Multi-Agent Review (Single Pass)

Review a GitHub PR against its corresponding plan using 8 parallel subagents. Produces a local review record only — does **not** post comments to GitHub. This is a single-pass review (no loop). For posting findings to the PR, use `/code-review --comment`; for review-and-push, use `/git-push`.

## Workflow

### Step 1: Resolve the PR

If `$ARGUMENTS` is a number, use it as `<PR>`. Otherwise auto-detect from the current branch:

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr view --json number,title,body,headRefName,baseRefName
```

Extract `<PR>`, `<branch>`, `<base>`, `<title>`, `<body>`. If no PR exists for the current branch and no arg was given, stop and inform the user.

All `gh` calls in this skill use the inline `GH_TOKEN=$(...)` prefix and run **in-sandbox** (the github.com hosts are allowlisted — never set `dangerouslyDisableSandbox` on `gh` calls).

### Step 2: Locate the Plan

Resolve `<plan-path>` (`plans/<topic>/<plan-name>.md`) for the PR:

1. **From PR body** — grep the body for any reference matching `plans/<topic>/<name>.md`. If exactly one match exists and the file is present, use it.
2. **From branch slug** — strip the branch's leading segment (`frontend/foo` → `foo`) and Glob `plans/**/*<slug>*.md`. If exactly one match, use it.
3. **Otherwise** — use `AskUserQuestion`:
   - `header`: `"Plan"` (max 12 chars)
   - `question`: `"Could not auto-detect a plan for PR #<PR>. Choose one or skip plan-conformance review."`
   - `options`: up to 3 plausible plan candidates (label = bare plan filename, description = parent topic folder) + a final `"Skip plan conformance"` option.
   - User-typed "Other" is allowed for a custom path.

If a plan was chosen, set `<topic>` = parent directory of the plan, `<plan-name>` = plan filename without `.md`. If the user selected "Skip plan conformance", set `<plan-path>` = null and ask a second question for where to file the review:
- `header`: `"Topic"` — options are the top 3 most recently-modified `plans/*/` folders + `"Create new"` + Other. Use the chosen folder as `<topic>` and set `<plan-name>` = `<branch>` for review-file naming.

`<plan-path>` may be null for the rest of the workflow — that only disables Plan Conformance findings, nothing else.

### Step 3: Fetch the Diff

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr diff <PR>
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr view <PR> --json files --jq '.files[] | "\(.path) (+\(.additions)/-\(.deletions))"'
```

Create `<tmp-dir>` = `plans/<topic>/tmp/` (`mkdir -p`). Write the diff to `<tmp-dir>/pr-diff.patch` using the Write tool — never heredoc/redirect. Capture the file-list output in memory for subagent prompts.

If the diff is empty, stop and inform the user.

### Step 4: Launch 8 Parallel Review Subagents

Read `.claude/skills/pr-review/references/subagent-prompts.md` for the full prompt definitions, response format, and `fix_type` classification rules. Each subagent receives the minimal prompt template below — they read their checklist from the reference file.

Subagent prompt template (send to each, filling blanks):

> You are Subagent #N (<Role Name>) reviewing PR #<PR> on branch `<branch>`.
>
> 1. Read `.claude/skills/pr-review/references/subagent-prompts.md` — find your role's section and the shared response format. Follow it exactly.
> 2. The diff is at `<tmp-dir>/pr-diff.patch`. The PR title is "<title>" and body is below. Files changed: <file-list>.
> 3. <If plan exists:> The plan this PR is composed against is at `<plan-path>`. Read it in full before reviewing.
> 4. Read the source files relevant to your review area.
> 5. Write your JSON response to `<tmp-dir>/<role>.md` using the `Write` tool — NEVER `cat <<EOF`, `python3 << 'EOF'`, `cat >`, `tee`, `printf >`, `echo >`, or any heredoc/redirect (brace+quote security prompt).
> 6. Return only: `Written to <path>`.
>
> PR body:
> <body>

Launch **all subagents in a single message** for true parallelism. Use `model: sonnet`. Do NOT use `subagent_type: "Explore"` — it cannot use the Write tool. Skip Subagent #1 (Plan Conformance) if `<plan-path>` is null.

| # | Name                       | Focus                                                                  | Output file                       |
|---|----------------------------|------------------------------------------------------------------------|-----------------------------------|
| 1 | Plan Conformance           | Implements plan steps; no skipped to-dos; no scope creep               | `<tmp-dir>/plan-conformance.md`   |
| 2 | Correctness                | Logic errors, race conditions, error-handling gaps, wrong API usage    | `<tmp-dir>/correctness.md`        |
| 3 | Code Patterns              | Matches existing idioms (event bus, ajaxCall, type-guard, Pydantic)    | `<tmp-dir>/code-patterns.md`      |
| 4 | Simplicity & Readability   | Over-engineering, dead code, unnecessary abstractions                  | `<tmp-dir>/simplicity.md`         |
| 5 | Test Coverage              | Happy + sad path tests, FE tests for FE changes, integration for BE    | `<tmp-dir>/test-coverage.md`      |
| 6 | Security & Safety          | OWASP, auth, input validation, SQL/XSS injection vectors               | `<tmp-dir>/security.md`           |
| 7 | Consistency & Style        | Top-level imports, no quoted hints, no single-letter vars, no console.*| `<tmp-dir>/consistency.md`        |
| 8 | Documentation & Registry   | `ENDPOINT_REGISTRY.md`, `ARCHITECTURE.md`, `CLAUDE.md` updates         | `<tmp-dir>/documentation.md`      |

### Step 5: Coordinator Subagent

After all subagent files are written, launch a **single coordinator subagent** to deduplicate findings and escalate conflicts to design decisions. Reuse the coordinator prompt from `.claude/skills/pr-review/references/subagent-prompts.md` (the "Coordinator Subagent" section).

The coordinator writes `<tmp-dir>/coordinator.md` (full findings) and `<tmp-dir>/coordinator-summary.md` (verdicts, counts, DD titles, DD options). The orchestrator reads **only** the summary — never the full coordinator file.

### Step 6: Present Design Decisions via AskUserQuestion

Read `<tmp-dir>/coordinator-summary.md`. For each finding with `fix_type: "design_decision"`, present it via `AskUserQuestion`:

- `question`: `"DD-N: <finding title>?"` — include enough context for the user to decide
- `header`: `"DD-N"` (max 12 chars)
- `options`: from `design_decision_options` in the summary
- `multiSelect: false`

Constraints: max 4 questions per call, max 4 options each. Batch across multiple calls if needed.

Capture each chosen option (and any free-text notes) for the review file.

### Step 7: Write the Review File via Writer Subagent

Launch a **writer subagent** to produce the review record. The orchestrator never reads `coordinator.md` or writes the review file directly.

Review file path:
- **With plan**: `plans/<topic>/reviews/<plan-name>-pr-review-<PR>.md`
- **Without plan**: `plans/<topic>/reviews/pr-review-<PR>-<branch>.md`

`mkdir -p plans/<topic>/reviews/` if needed. **Never** write the review under `plans/tmp/`.

Writer subagent prompt:

> You are the PR review writer for PR #<PR>. Read `<tmp-dir>/coordinator.md` for the full findings.
>
> Write the review section to `<review-file-path>` using the `Write` tool (no heredoc/redirect). If the file already exists, append a new dated section — do not overwrite.
>
> **Title (first creation only):** `# PR Review for <plan-name> (PR #<PR>)` (or `# PR Review for PR #<PR> — <branch>` if no plan was provided). This title is mandatory and distinguishes the record from plan reviews and push reviews.
>
> **Resolved DDs:** apply the following user choices to the corresponding DD-N entries (fill `**Chosen:**` and the user note if any): <list of {DD-N → choice, note}>.
>
> **Document structure** (single dated section per run):
>
> ```
> ## Review — <YYYY-MM-DD HH:MM>
> PR: #<PR> — <title>
> Branch: <branch> → <base>
> Plan: <plan-path or "none">
>
> ### Summary
> 2-3 sentences on overall verdict and shape of findings.
>
> ### Subagent Results
> | # | Reviewer | Verdict | One-line summary |
> |---|---|---|---|
> | 1 | Plan Conformance | PASS/FAIL/N-A | ... |
> | ... |
>
> ### Findings
> Grouped by Critical / Major / Minor / Nit (omit empty categories). Each finding includes file:line, description, suggestion. For `duplicate` classification, append `*(flagged by: Reviewer A, Reviewer B)*`.
>
> ### Design Decisions
> #### DD-N: <title>
> **Context:** ...
> | # | Option | Trade-off |
> |---|---|---|
> | 1 | ... | ... |
> **Chosen:** <user's choice> <optional note>
>
> ### Verdict
> One of: **Ready to merge** / **Minor concerns** / **Requires changes** / **Blocked**.
> ```
>
> Return only: `Written to <review-file-path>`

Use `model: sonnet`.

### Step 8: Final Summary

Report to the user:
- Per-reviewer verdicts (one line each)
- Counts: critical / major / minor / nit
- Number of design decisions resolved
- Final verdict
- Path to the review file

Then clean up: delete all files in `<tmp-dir>/`.

## Important Notes

- **Single pass.** This skill runs the review once. To re-review after fixes, invoke `/pr-review <PR>` again.
- **Does NOT post to GitHub.** This is a local review record. Use `/code-review --comment` to post findings as inline PR comments, or `/git-push` for the review-and-push workflow.
- **Does NOT modify code or apply fixes.** Auto-fixing is `/run-review`'s job; this skill records findings only.
- **All subagent launches in a single message** for true parallelism.
- **Writer + coordinator subagents only** touch `coordinator.md` and the review file. The orchestrator reads only `coordinator-summary.md`.
- **`<tmp-dir>` is `plans/<topic>/tmp/`** — transient subagent communication only. Final documents (the review file) always live under `plans/<topic>/reviews/`. Never store final review records in `plans/tmp/`.
- **All `gh` calls** use the inline `GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh)` prefix and run in-sandbox (github.com hosts are allowlisted — never set `dangerouslyDisableSandbox` on `gh`).
- **Use Write/Edit for all file content.** Never heredoc or redirect (`cat <<EOF`, `python3 << 'EOF'`, `cat >`, `tee`, `printf >`, `echo >`) — brace+quote content trips the security prompt.
- **If a subagent fails to return valid JSON** or its output file is missing, the coordinator treats it as FAIL with a parse error finding.
