---
name: pr-review-fixer
description: Read all review comments on the current branch's GitHub PR, extract memory-worthy patterns, group comments by root cause, fix all issues with parallel subagents, commit, and push. Also monitors CI/CD workflow runs, summarizes failures, and investigates fixes. Loops the push review until it passes or user intervention is needed. Use when asked to address PR review comments, fix PR feedback, handle review comments, or resolve PR change requests.
---

# PR Review Fixer

Read PR review comments, fix all issues, commit, and push — looping until the push review passes. Simultaneously monitors CI/CD for failures.

## Workflow

### 1. Identify the PR and Launch CI Monitor

```bash
BRANCH=$(git branch --show-current)
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr view --json number,title,url
```

Extract the PR number. If no PR exists, inform the user and stop.

**Immediately after identifying the PR**, launch the CI Monitor subagent (Step 1a) in the background. It runs independently alongside the rest of the workflow.

#### 1a. CI Monitor Subagent (background)

Launch a background subagent that polls CI/CD status for up to 10 minutes. This subagent:

1. Fetches the latest workflow run for this branch:
   ```bash
   GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh run list --branch $BRANCH --limit 1 --json databaseId,status,conclusion
   ```
2. Polls every 60 seconds for up to 10 minutes (10 iterations max)
3. On each poll, checks the run status:
   - **`completed` + `success`**: Report success and stop polling
   - **`completed` + `failure`**: Write the run ID and failed job names to `plans/<topic>/reviews/ci-failures-<branch>.md` (see format below), then stop polling
   - **`in_progress`** or **`queued`**: Sleep 60 seconds, poll again
4. If still in progress after 10 minutes, write a timeout note to the CI failures file and stop

When a failure is detected, also fetch failed job details:
```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh run view <RUN_ID> --json jobs --jq '.jobs[] | select(.conclusion == "failure") | {name, conclusion}'
```

**CI Failures File Format** (`plans/<topic>/reviews/ci-failures-<branch>.md`):

Infer `<topic>` from the branch name by splitting on `/` and `-` and matching against known topics (e.g., `api-route`, `urls`, `openapi`). If the topic cannot be inferred, fall back to `plans/tmp/ci-failures-<branch>.md`.

```markdown
# CI Failures: <branch>

## Run <RUN_ID> — <YYYY-MM-DD HH:MM>
Status: **FAILED**

### Failed Jobs
- <job name 1>
- <job name 2>

### Failure Logs
<!-- Populated by the CI Log Reader subagent -->
```

#### 1b. CI Log Reader Subagent (triggered by 1a)

When the CI Monitor writes a failure file, it must then launch a second subagent to read the actual failure logs:

1. For each failed job, fetch the failed step logs:
   ```bash
   GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh run view <RUN_ID> --log-failed
   ```
2. Parse the log output to extract:
   - Test names that failed (if test jobs)
   - Error messages and stack traces
   - Build errors (if build jobs)
3. Append a summarized, structured analysis to `plans/<topic>/reviews/ci-failures-<branch>.md` under `### Failure Logs`:
   ```markdown
   ### Failure Logs

   #### <Job Name>
   **Root cause**: <brief description>
   **Failed tests**:
   - `test_name_1` — <assertion/error summary>
   - `test_name_2` — <assertion/error summary>

   **Stack trace** (key excerpt):
   ```
   <relevant lines only, not full log>
   ```
   ```

#### 1c. CI Fix Investigator Subagent (triggered by 1b)

After the CI Log Reader finishes writing the failure analysis, it must launch a third subagent to investigate fixes:

1. Read `plans/<topic>/reviews/ci-failures-<branch>.md` to understand the failures
2. For each failure, investigate the root cause in the codebase:
   - Read the failing test files to understand what they expect
   - Read the source files referenced in stack traces
   - Determine if the failure is caused by changes on this branch
3. If the fix is straightforward (typo, import error, missing constant, test assertion update):
   - Apply the fix directly
   - Report what was changed
4. If the fix requires behavioral or design decisions:
   - **Do NOT make changes**
   - Document the issue and recommended approach in the CI failures file
   - Flag it for user intervention

**Important**: The CI subagent chain (1a → 1b → 1c) runs independently of the PR comment workflow (Steps 2-8). If the CI fix investigator makes code changes, those changes will be picked up by the next `/git-commit` invocation.

All `gh` commands in CI subagents must:
- Be prefixed with `GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh)`
- Use `dangerouslyDisableSandbox: true`

### 2. Fetch All Review Comments

Fetch both inline code comments and top-level review bodies:

```bash
# Inline review comments (code-level)
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh api repos/4IRL/urls4irl/pulls/<PR_NUMBER>/comments

# Top-level review bodies
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr view <PR_NUMBER> --json reviews
```

All `gh` commands must:
- Be prefixed with `GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh)`
- Use `dangerouslyDisableSandbox: true`

Parse comments extracting: `body`, `path`, `line`, `diff_hunk`, `user.login`, `created_at`.

If no comments exist, inform the user and stop.

### 3. Extract Memory-Worthy Patterns

Scan all review comments for patterns the reviewer wants remembered — phrases like:
- "always...", "never...", "we should...", "from now on...", "remember to..."
- Comments that reference coding conventions, project rules, or recurring mistakes
- Comments that reinforce or correct existing CLAUDE.md rules

For each memory-worthy comment:
1. Determine the appropriate memory type (`feedback`, `project`, or `reference`)
2. Save to the memory system following the standard memory format
3. If the pattern should also be in CLAUDE.md, update CLAUDE.md

### 4. Group Comments by Root Cause

Analyze all comments and group them by identical or closely related root causes. Examples:
- Multiple comments about relative imports → one group: "Use absolute imports"
- Multiple comments about missing type hints → one group: "Add type hints"
- A single unique comment → its own group

For each group, record:
- **Cause**: The underlying issue
- **Comments**: List of all comments in the group (with file, line, body)
- **Fix description**: What needs to change

### 5. Fix All Groups in Parallel

Launch one subagent per group using the Agent tool. All subagents launch in a **single message** for true parallelism.

Each subagent receives:
- The group's cause and fix description
- The list of affected files, lines, and comment bodies
- The full diff hunks for context
- Instructions to read each affected file before editing
- Instructions to follow CLAUDE.md guidelines (absolute imports, no quoted type hints, no single-letter variables, typehints required)

Subagent prompt template:
```
Fix all PR review comments in this group.

Root cause: <cause>
Fix: <fix description>

Comments to address:
<for each comment>
- File: <path>, Line: <line>
  Comment: <body>
  Diff context: <diff_hunk>
</for each>

Instructions:
- Read each file before editing
- Follow CLAUDE.md guidelines
- Make minimal changes to address the comments
- Do NOT make unrelated changes
- Report what you changed
```

Use `model: sonnet` for subagents.

### 6. Review Subagent Results

Collect all subagent results. If any subagent reports issues requiring user input (behavioral or design changes), **stop and inform the user**:
- Explain which comment(s) need user guidance
- Explain why the fix cannot be automated
- Do NOT proceed until the user responds

### 6a. Run Related Tests Before Committing

**If any changes were made to code-containing files** (Python `.py`, JavaScript `.js`, HTML templates `.html`, CSS `.css`), you **must** run related tests locally before committing.

1. Identify which files were changed by the fix subagents (check `git diff --name-only`)
2. Determine the relevant test markers based on the changed files:
   - `backend/splash/` → `splash` (integration) + `splash_ui` (UI)
   - `backend/templates/components/splash/` → `splash_ui`
   - `frontend/splash/` → `splash_ui` + `test-js` (vitest)
   - `backend/urls/` or `frontend/urls/` → `urls` + `urls_ui`
   - `backend/tags/` or `frontend/tags/` → `tags` + `tags_ui`
   - `backend/utubs/` or `frontend/utubs/` → `utubs` + `utubs_ui`
   - `backend/members/` or `frontend/members/` → `members` + `members_ui`
   - For other paths, use best judgment to pick the right markers
3. Run integration tests first using `make test-marker-parallel m=<marker>`, then UI tests using `make test-marker-parallel m=<marker_ui>`. **Never run both simultaneously** — they share a single test DB.
4. If tests fail:
   - Investigate the failure and fix if straightforward
   - If the fix requires design decisions, stop and inform the user
   - Re-run tests after fixing to confirm they pass
5. Only proceed to commit (Step 7) after all related tests pass

**Skip this step** if the only changes are to non-code files (e.g., documentation, config, `.claude/` skill files).

### 7. Commit

Invoke the `/git-commit` skill via the Skill tool. This handles staging, message generation, and pre-commit hooks automatically.

### 8. Push and Review Loop

Invoke the `/git-push` skill via the Skill tool. This runs the 7-agent review and pushes if approved.

**If `/git-push` review blocks the push:**

1. Read the review file at `plans/<topic>/reviews/push-review-<branch>.md`
2. Find the latest `## Review N` section
3. Extract all unchecked to-do items
4. Launch a subagent to fix all findings:
   - The subagent receives the full to-do list and makes all necessary changes
   - Use `model: sonnet`
5. After fixes, invoke `/git-commit` again
6. Invoke `/git-push` again
7. Repeat until push succeeds or a finding requires user intervention

**User intervention triggers** — stop and inform the user if any finding:
- Requires a behavioral or design decision
- Conflicts with an existing CLAUDE.md rule
- Would change public API behavior
- Involves test logic changes beyond simple fixes
- Cannot be resolved without understanding business context

**Loop cap**: Maximum 3 iterations. If still blocked after 3 attempts, stop and present all remaining findings to the user.

## Important Notes

- All `gh` commands require `GH_TOKEN` prefix and `dangerouslyDisableSandbox: true`
- Never force-push or push to main/master
- CI failure files and push review files live at `plans/<topic>/reviews/`. Infer `<topic>` from the branch name.
- Follow existing commit message style (check `git log -3 --oneline`)
- All subagent launches in a single step must be in one message for parallelism
- If a subagent fails or returns unclear results, treat as needing user intervention
- The CI monitor chain (1a → 1b → 1c) is a sequential pipeline but runs in the background, independent of Steps 2-8
- CI fixes from subagent 1c will be included in the next commit cycle
