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
```

```bash
# Call 1: generate token
/Users/ggpropersi/.claude/generate-gh-token.sh
# Call 2: use token
GH_TOKEN=<token> gh pr view --json number,title,url
```

Extract the PR number. If no PR exists, inform the user and stop.

**Immediately after identifying the PR**, launch the CI Monitor subagent (Step 1a) in the background. It runs independently alongside the rest of the workflow.

#### 1a. CI Monitor Subagent (background)

Launch a background subagent that polls CI/CD status for up to 10 minutes. This subagent:

1. Fetches the latest workflow run for this branch (two sequential calls):
   ```bash
   # Call 1: generate token
   /Users/ggpropersi/.claude/generate-gh-token.sh
   # Call 2: use token
   GH_TOKEN=<token> gh run list --branch $BRANCH --limit 1 --json databaseId,status,conclusion
   ```
2. Polls every 60 seconds for up to 10 minutes (10 iterations max)
3. On each poll, checks the run status:
   - **`completed` + `success`**: Report success and stop polling
   - **`completed` + `failure`**: Write the run ID and failed job names to `plans/<topic>/reviews/ci-failures-<branch>.md` (see format below), then stop polling
   - **`in_progress`** or **`queued`**: Sleep 60 seconds, poll again
4. If still in progress after 10 minutes, write a timeout note to the CI failures file and stop

When a failure is detected, also fetch failed job details (two sequential calls):
```bash
# Call 1: generate token
/Users/ggpropersi/.claude/generate-gh-token.sh
# Call 2: use token
GH_TOKEN=<token> gh run view <RUN_ID> --json jobs --jq '.jobs[] | select(.conclusion == "failure") | {name, conclusion}'
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

1. For each failed job, fetch the failed step logs (two sequential calls):
   ```bash
   # Call 1: generate token
   /Users/ggpropersi/.claude/generate-gh-token.sh
   # Call 2: use token
   GH_TOKEN=<token> gh run view <RUN_ID> --log-failed
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
3. **Never dismiss a failure as "pre-existing" or "flaky"** because the test file wasn't modified on this branch. Current changes can break tests indirectly (shared fixtures, CSS/selector changes, templates, timing, imports). For every failure: read the traceback, check if branch changes could affect the failing path, and either fix or confirm unrelated by rerunning in isolation 2-3 times.
4. If the fix is straightforward (typo, import error, missing constant, test assertion update):
   - Apply the fix directly
   - Report what was changed
5. If the fix requires behavioral or design decisions:
   - **Do NOT make changes**
   - Document the issue and recommended approach in the CI failures file
   - Flag it for user intervention

**Important**: The CI subagent chain (1a → 1b → 1c) runs independently of the PR comment workflow (Steps 2-6). If the CI fix investigator makes code changes, those changes will be picked up by the next `/git-commit` invocation.

All `gh` commands in CI subagents must:
- Use two sequential Bash calls: first `/Users/ggpropersi/.claude/generate-gh-token.sh` to get the token, then `GH_TOKEN=<token> gh ...` to run the command
- Use `dangerouslyDisableSandbox: true`
- Never use `$(...)` inline or inline raw tokens

### 2. Fetch and Analyze Review Comments (Comment Analyzer Subagent)

Launch a **foreground subagent** to fetch, filter, analyze, and group PR review comments. The orchestrator does NOT fetch or process comments directly — it delegates entirely to this subagent and acts on its structured output.

#### Subagent prompt template:

```
You are a PR comment analyzer for PR #<PR_NUMBER> on repo 4IRL/urls4irl (branch: <BRANCH>).

Your job: fetch all review comments, filter out resolved ones, extract memory-worthy patterns, and group unresolved comments by root cause.

## Step 1: Fetch unresolved review threads via GraphQL

Use the GraphQL API to get review threads with resolution status. The REST API does NOT expose resolution — GraphQL is required.

All gh commands require two sequential Bash calls (never use $(...) inline). Use `dangerouslyDisableSandbox: true` for all gh commands.

```bash
# Call 1: generate token
/Users/ggpropersi/.claude/generate-gh-token.sh
# Call 2: use token
GH_TOKEN=<token> gh api graphql -f query='
{
  repository(owner: "4IRL", name: "urls4irl") {
    pullRequest(number: <PR_NUMBER>) {
      reviewThreads(first: 100) {
        nodes {
          isResolved
          isOutdated
          path
          line
          startLine
          comments(first: 10) {
            nodes {
              body
              author { login }
              url
              createdAt
              diffHunk
            }
          }
        }
      }
    }
  }
}'
```

Also fetch top-level review bodies:
```bash
# Call 1: generate token
/Users/ggpropersi/.claude/generate-gh-token.sh
# Call 2: use token
GH_TOKEN=<token> gh pr view <PR_NUMBER> --json reviews
```

## Step 2: Filter to unresolved comments only

From the GraphQL response, keep ONLY threads where `isResolved == false`. Discard all resolved threads entirely — they have already been addressed and acknowledged by the reviewer.

If ALL threads are resolved and there are no actionable top-level review bodies, write the output file with `"status": "all_resolved"` and stop.

## Step 3: Extract memory-worthy patterns

Scan ALL comments (including resolved ones) for patterns the reviewer wants remembered:
- "always...", "never...", "we should...", "from now on...", "remember to..."
- Comments referencing coding conventions, project rules, or recurring mistakes
- Comments reinforcing or correcting existing CLAUDE.md rules

For each memory-worthy comment, save to the memory system following the standard memory format (determine type: feedback, project, or reference). If the pattern should also be in CLAUDE.md, update CLAUDE.md.

## Step 4: Group unresolved comments by root cause

Analyze unresolved comments and group by identical or closely related root causes. Examples:
- Multiple comments about relative imports → one group: "Use absolute imports"
- Multiple comments about missing type hints → one group: "Add type hints"
- A single unique comment → its own group

## Step 5: Write structured output

Write output to `<tmp-dir>/comment-analysis.md` **using the `Write` tool** — NEVER `cat <<EOF`, `python3 << 'EOF'`, `cat >`, `tee`, `printf >`, `echo >`, or any Bash heredoc/redirect (any heredoc or inline script with `{` + quotes trips the brace+quote security prompt). Write as JSON:

```json
{
  "status": "has_unresolved",
  "total_threads": <number>,
  "resolved_threads": <number>,
  "unresolved_threads": <number>,
  "memory_patterns_saved": <number>,
  "groups": [
    {
      "cause": "<root cause description>",
      "fix_description": "<what needs to change>",
      "comments": [
        {
          "path": "<file path>",
          "line": <line number>,
          "body": "<comment body>",
          "diff_hunk": "<diff context>",
          "author": "<login>",
          "url": "<comment URL>"
        }
      ]
    }
  ]
}
```

If no unresolved comments exist:
```json
{
  "status": "all_resolved",
  "total_threads": <number>,
  "resolved_threads": <number>,
  "unresolved_threads": 0,
  "memory_patterns_saved": <number>,
  "groups": []
}
```
```

Use `model: sonnet` for this subagent. Set `<tmp-dir>` to `plans/<topic>/tmp/` (infer topic from branch name) or `$TMPDIR` if topic cannot be inferred.

#### Orchestrator actions after subagent returns:

1. Read `<tmp-dir>/comment-analysis.md`
2. If `status` is `"all_resolved"`:
   - Inform the user: "All N review threads are resolved. No unresolved comments to address."
   - **Stop the comment workflow** (CI monitor may still be running independently)
3. If `status` is `"has_unresolved"`:
   - Report to user: "Found N unresolved threads (M resolved, skipped). Fixing N groups..."
   - Proceed to Step 3

### 3. Fix All Groups in Parallel

Using the `groups` array from the comment analysis output, launch **one subagent per group** in a **single message** for true parallelism.

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

### 4. Review Subagent Results

Collect all subagent results. If any subagent reports issues requiring user input (behavioral or design changes), **stop and inform the user**:
- Explain which comment(s) need user guidance
- Explain why the fix cannot be automated
- Do NOT proceed until the user responds

### 4a. Run Related Tests Before Committing

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
   - **Never dismiss a failure as "pre-existing" or "flaky"** — check if branch changes could affect the failing path indirectly (shared fixtures, CSS, templates, timing, imports). If confirmed unrelated, rerun in isolation 2-3 times to verify flakiness and report findings.
   - Investigate the failure and fix if straightforward
   - If the fix requires design decisions, stop and inform the user
   - Re-run tests after fixing to confirm they pass
5. Only proceed to commit (Step 5) after all related tests pass

**Skip this step** if the only changes are to non-code files (e.g., documentation, config, `.claude/` skill files).

### 5. Commit

Invoke the `/git-commit` skill via the Skill tool. This handles staging, message generation, and pre-commit hooks automatically.

### 6. Push and Review Loop

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

- All `gh` commands require two sequential Bash calls (generate token first, then `GH_TOKEN=<token> gh ...`) and `dangerouslyDisableSandbox: true`. Never use `$(...)` inline or inline raw tokens.
- Never force-push or push to main/master
- CI failure files and push review files live at `plans/<topic>/reviews/`. Infer `<topic>` from the branch name.
- Follow existing commit message style (check `git log -3 --oneline`)
- All subagent launches in a single step must be in one message for parallelism
- If a subagent fails or returns unclear results, treat as needing user intervention
- The CI monitor chain (1a → 1b → 1c) is a sequential pipeline but runs in the background, independent of Steps 2-6
- CI fixes from subagent 1c will be included in the next commit cycle
- **Comment resolution check is mandatory**: The Comment Analyzer subagent (Step 2) uses the GraphQL API to check `isResolved` on each review thread. The REST API does NOT expose resolution status — always use GraphQL. If all threads are resolved, the workflow stops early with no changes.
- The orchestrator never fetches or processes comments directly — it delegates to the Comment Analyzer subagent and acts on the structured JSON output
