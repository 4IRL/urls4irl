---
name: pr-review-fixer
description: Read all review comments on the current branch's GitHub PR, extract memory-worthy patterns, group comments by root cause, fix all issues with parallel subagents, commit, and push. Also monitors CI/CD workflow runs, summarizes failures, and investigates fixes. Loops the push review until it passes or user intervention is needed. Use when asked to address PR review comments, fix PR feedback, handle review comments, or resolve PR change requests.
---

# PR Review Fixer

Read PR review comments, fix all issues, commit, and push — looping until the push review passes. After the push, monitor CI/CD for failures via `/loop`.

## Workflow

### 1. Identify the PR

```bash
BRANCH=$(git branch --show-current)
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr view --json number,title,url
```

Extract the PR number. If no PR exists, inform the user and stop.

**Do NOT launch a CI monitor here.** The pre-fix CI run is invalidated the moment we push fixes, so monitoring it is pointless. CI monitoring runs in Step 7, after the push, against the post-fix commit.

### 2. Fetch and Analyze Review Comments (Comment Analyzer Subagent)

Launch a **foreground subagent** to fetch, filter, analyze, and group PR review comments. The orchestrator does NOT fetch or process comments directly — it delegates entirely to this subagent and acts on its structured output.

#### Subagent prompt template:

```
You are a PR comment analyzer for PR #<PR_NUMBER> on repo 4IRL/urls4irl (branch: <BRANCH>).

Your job: fetch all review comments, filter out resolved ones, extract memory-worthy patterns, and group unresolved comments by root cause.

## Step 1: Fetch unresolved review threads via GraphQL

Use the GraphQL API to get review threads with resolution status. The REST API does NOT expose resolution — GraphQL is required.

Use `dangerouslyDisableSandbox: true` for all gh commands. Always use the `GH_TOKEN=$(...)` inline prefix — it is exempted from the command substitution hook.

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh api graphql -f query='
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
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr view <PR_NUMBER> --json reviews
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

### 7. Monitor Post-Push CI via /loop

After the push in Step 6 completes successfully, monitor the new GitHub Actions run for the just-pushed commit. **Never use a background `Agent` subagent for this** — general-purpose subagents don't execute synchronous sleep loops; they exit immediately with "Monitor armed" without iterating. Use `/loop` in dynamic (self-paced) mode instead, where the runtime drives the cadence via `ScheduleWakeup`.

#### 7a. Resolve the post-push run ID

Right after the push, find the new run for the just-pushed `HEAD`:

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh run list --branch $BRANCH --limit 1 --json databaseId,status,conclusion,headSha,createdAt
```

If the most recent run's `headSha` does NOT match the just-pushed commit, GitHub hasn't picked up the push yet. Sleep 30 seconds (one `sleep 30` Bash call), retry once, and only proceed once the latest run is associated with the new commit. If still missing after the retry, stop and inform the user — there is no run to monitor.

Capture `RUN_ID` for use in the loop prompt below.

#### 7b. Invoke /loop in dynamic mode

Invoke the `loop` skill via the Skill tool. Pass NO interval (dynamic / self-paced). The prompt is a self-contained polling instruction that:

1. Checks the run via `gh run view <RUN_ID> --json status,conclusion`.
2. **If `status == "completed"` and `conclusion == "success"`** → report success and DO NOT call `ScheduleWakeup` (this ends the loop).
3. **If `status == "completed"` and `conclusion` is `failure` / `cancelled` / `timed_out`** → launch the CI Log Reader subagent (Step 7c) as a foreground subagent inside this loop tick, then DO NOT call `ScheduleWakeup` (this ends the loop).
4. **Otherwise (`queued`, `in_progress`, `waiting`)** → call `ScheduleWakeup(delaySeconds: 90, prompt: <same loop prompt>, reason: "polling CI run <RUN_ID>, currently <status>")` to fire again in 90 seconds.

90 seconds keeps the prompt cache warm (under the 5-minute TTL).

Skill invocation example payload:

```
/loop <self-contained polling prompt that references RUN_ID, the failures-file path, and the Log Reader subagent prompt template below>
```

The polling prompt must be fully self-contained — each `/loop` firing is a fresh prompt and does not have access to earlier turn context.

#### 7c. CI Log Reader subagent (launched on failure)

The /loop tick that detects a terminal failure launches the Log Reader as a regular foreground `Agent` subagent (`subagent_type: "general-purpose"`, `model: "sonnet"`).

Subagent prompt:

```
You are the CI Log Reader for run <RUN_ID> on branch <BRANCH>. The CI Monitor detected a terminal failure.

Steps:
1. Get failed jobs:
   GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh run view <RUN_ID> --json jobs --jq '.jobs[] | select(.conclusion == "failure") | {name, conclusion}'
2. Get failed logs:
   GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh run view <RUN_ID> --log-failed
3. Get a timestamp: date '+%Y-%m-%d %H:%M' (separate Bash call).
4. WRITE the failures file at plans/<topic>/reviews/ci-failures-<branch>.md using the Write tool (NEVER heredoc / cat-redirect):

   # CI Failures: <branch>

   ## Run <RUN_ID> — <timestamp>
   Status: **FAILED** (conclusion: <conclusion>)

   ### Failed Jobs
   - <job 1>
   - <job 2>

   ### Failure Logs

   #### <Job Name>
   **Root cause**: <brief>
   **Failed tests**:
   - `test_x` — <assertion/error summary>
   **Stack trace** (key excerpt):
   ```
   <5-15 relevant lines, not the full log>
   ```

5. Launch the CI Fix Investigator subagent (Step 7d prompt below).
6. Report a one-paragraph summary and stop.

Rules: inline GH_TOKEN prefix and dangerouslyDisableSandbox on every gh call. Never commit, never push. Use Write/Edit for file content — never heredoc.
```

Infer `<topic>` from the branch name. Fall back to `plans/tmp/ci-failures-<branch>.md` if no topic match exists.

#### 7d. CI Fix Investigator subagent (launched by 7c)

```
You are the CI Fix Investigator. The failure analysis is at plans/<topic>/reviews/ci-failures-<branch>.md.

Steps:
1. Read the failures file.
2. For each failure: read the failing test, read source in the stack trace, decide if the just-pushed commit could plausibly have caused it (think indirectly: shared fixtures, CSS/templates, timing, imports). Never dismiss as "flaky" or "pre-existing" without that investigation.
3. If the fix is straightforward (typo, missing import, constant rename, simple assertion update) → apply via Edit and report what changed.
4. If the fix needs design judgment → append a `### Recommended Approach` section to the failures file describing the issue and what the user should decide.
5. Report a one-paragraph summary and stop.

Rules: inline GH_TOKEN prefix, dangerouslyDisableSandbox on gh/docker/make. Use Read/Grep/Glob to investigate; Edit to apply fixes. Never use Bash to write file content. Never commit, never push — the orchestrator handles commits on the next cycle.
```

Fixes applied by the Investigator will be picked up by the next `/git-commit` invocation.

## Important Notes

- All `gh` commands require `GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh)` prefix and `dangerouslyDisableSandbox: true`. Never resolve the token separately and inline a raw value.
- Never force-push or push to main/master
- CI failure files and push review files live at `plans/<topic>/reviews/`. Infer `<topic>` from the branch name.
- Follow existing commit message style (check `git log -3 --oneline`)
- All subagent launches in a single step must be in one message for parallelism
- If a subagent fails or returns unclear results, treat as needing user intervention
- **CI monitoring uses /loop dynamic mode, never a background subagent.** General-purpose `Agent` subagents do NOT execute synchronous `sleep` polling loops in the background — they interpret "poll for N minutes" as a setup task and exit immediately ("Monitor armed"). `/loop` (dynamic / self-paced) hands cadence to the runtime via `ScheduleWakeup`, and each fire re-enters the polling prompt with fresh state.
- **Test runs use synchronous Bash inside subagents** — test-runner subagents invoke `make test-*` synchronously (with `dangerouslyDisableSandbox: true`) and block until make exits. The orchestrator waits for the subagent's Agent-tool reply — that reply IS the completion signal. Do not arm a Monitor on a test result file, do not poll a running subagent, and never reach into a container with a side-channel probe. The CI monitor in Step 7 is a separate concern: it polls GitHub Actions via `gh` through `/loop`, not a local test run.
- Fixes from the CI Fix Investigator (Step 7d) are picked up by the next `/git-commit` invocation.
- **Comment resolution check is mandatory**: The Comment Analyzer subagent (Step 2) uses the GraphQL API to check `isResolved` on each review thread. The REST API does NOT expose resolution status — always use GraphQL. If all threads are resolved, the workflow stops early with no changes.
- The orchestrator never fetches or processes comments directly — it delegates to the Comment Analyzer subagent and acts on the structured JSON output
