---
name: run-review
description: Execute all pending TODO items from a review file autonomously in a loop. Delegates each item to a subagent running /next-step-taker in review mode. The main agent is purely an orchestrator — it reads the review, spawns subagents, and loops. Only stops on blockers (test failures, unresolved findings requiring user input) or when all items are done. Use when asked to "run the review", "fix all review items", "work through the review", or "apply all review feedback". Argument is the review name (e.g., "/run-review push-review-refactor-foo") or omit to auto-detect from current branch.
argument-hint: review-name (optional — auto-detects push review from current branch)
---

# Run Review Skill

Autonomously execute all pending TODO items from a review file. The **main agent is an orchestrator only** — it reads the review, delegates each item to a subagent running `/next-step-taker` in review mode, and loops. It never directly edits implementation files, runs tests, or runs build/make commands.

## Branch Guard

1. If on `main`/`master`: warn the user — review fixes should be on a feature branch. Ask before proceeding.
2. If on a feature branch: proceed.

## Sandbox Rules

- **Git commands** (`git add`, `git commit`, `git status`, `git diff`, etc.): run in **default sandbox** — never use `dangerouslyDisableSandbox`
- **Docker/make commands**: use `dangerouslyDisableSandbox: true` (Docker socket requires it)
- Subagent prompts must include these rules so subagents follow them too

## Workflow

### Step 1: Locate and Read the Review

#### If $ARGUMENTS is provided:
- Search for a review file under `plans/` matching **$ARGUMENTS** contextually
- Try `plans/**/<arg>.md`, `plans/**/<arg>-review.md`, `plans/*/reviews/push-review-<arg>.md`

#### If $ARGUMENTS is omitted:
- Get the current branch: `git branch --show-current`
- Look for `plans/*/reviews/push-review-<branch>.md`

#### Read the review:
- Read the full review file — review files accumulate multiple revision passes and the **latest revision is at the bottom**
- Paginate with `offset` + `limit` if needed to reach the end
- Find the latest revision section (highest `## Review N` for push reviews, latest date/pass for plan reviews)
- Count all unchecked items (`- [ ]`) in the **"To-Do: Required Changes"** section of the latest revision
- Report to user: "Found N pending items in Review M. Starting from item 1."

If all items are already checked (`- [x]`), report that the review is fully applied and stop.

### Step 2: Execution Loop

For each pending unchecked item, the main agent orchestrates:

#### 2a. Spawn Execution Subagent

Launch a subagent via the Agent tool with this prompt pattern:

```
Run /next-step-taker in review mode for "<review-name>".

The next unchecked item to apply is item N of M.

Important overrides for this run:
- Do NOT pause at the end to ask the user — complete the full workflow (apply change, validate, review, fix, cross off item) and return your final report.
- Commit the changes using /git-commit before returning. Follow all CLAUDE.md guidelines for commits.
- Follow all CLAUDE.md guidelines.
- CRITICAL: Every Bash call that runs `make` or `docker` MUST set dangerouslyDisableSandbox: true. Never for git commands.
  Example: Bash(command: "make test-marker-parallel m=urls > \"/tmp/claude/test-results.txt\" 2>&1", dangerouslyDisableSandbox: true)
- CRITICAL: Never dismiss a test failure as "pre-existing" or "flaky" because the test file wasn't modified on this branch. Current changes can break tests indirectly (shared fixtures, CSS/selector changes, templates, timing, imports). For every failure: (1) read the traceback, (2) check if branch changes could affect the failing path, (3) fix if related, (4) if confirmed unrelated, rerun in isolation 2-3 times and report findings.
```

The subagent handles the entire workflow internally:
1. Read the review file and find the next unchecked item
2. Apply the change to the codebase
3. Validate (build, tests via its own sub-subagents)
4. Review pipeline (3 parallel review subagents + fix subagent)
5. Cross off the item in the review file (`- [ ]` -> `- [x]`)
6. Commit all changes (implementation + review file update) using `/git-commit`
7. Return its final report (what changed, validation results, review findings)

#### 2b. Evaluate Subagent Result

The main agent reads the subagent's report and decides:

**Auto-continue** when ALL of these are true:
- Validation passed (build clean, tests green)
- Review pipeline returned all PASS or all findings were fixed
- Commit succeeded
- No unresolved items requiring user decisions

**Stop and ask** when ANY of these are true:
- Test failures that couldn't be auto-fixed
- Review has UNRESOLVED findings (require user decision)
- Fix subagent returned `VALIDATION: FAIL`
- The review item was ambiguous or required a decision
- Commit failed (pre-commit hook issues that couldn't be resolved)

#### 2c. Smoke Test After UI-Affecting Items

If the completed item changed frontend code (JS, templates, CSS) or test locators/selectors, spawn a **smoke test subagent** before continuing:

```
Run a quick UI smoke test against built assets. Execute:
  make test-ui-parallel-built n=2
Write the full test output to /tmp/claude/smoke-test-review-item-N.txt.
Report: total passed, total failed. If failures, include test names and error summaries.

CRITICAL: Every Bash call that runs `make` or `docker` MUST set dangerouslyDisableSandbox: true.
Example:
  Bash(command: "make test-ui-parallel-built n=2 > \"/tmp/claude/smoke-test-review-item-N.txt\" 2>&1", dangerouslyDisableSandbox: true)
```

If the smoke test fails, enter the **Test Fix Loop** (Section 2e) before continuing.

#### 2d. Re-read the Review File

After each item, re-read the review file to:
- Confirm the item was crossed off
- Count remaining unchecked items
- Report progress: "Completed item N of M. X items remaining."

#### 2e. Test Fix Loop (when tests fail)

When any test run (smoke test or validation) reports failures:

1. **Test runner subagent** writes full output to a temp file (`/tmp/claude/<descriptive-name>.txt`)
2. **Main agent reads the temp file** to understand failure count and patterns
3. **Fix subagent** is spawned with:
   ```
   Fix the following test failures. The full test output is at:
     <path-to-temp-file>
   Read this file to understand all failures, then fix them.
   <include user decisions if any were provided>
   CRITICAL: Never dismiss a failure as "pre-existing" — check if branch changes could affect the failing path indirectly (shared fixtures, CSS, templates, timing, imports). If confirmed unrelated, rerun in isolation 2-3 times to verify flakiness.
   After fixing, run `make vite-build` and `make test-js` to verify JS changes (if applicable).
   Do NOT run the full test suite — just implement fixes.

   CRITICAL: Every Bash call that runs `make` or `docker` MUST set dangerouslyDisableSandbox: true.
   Example:
     Bash(command: "make vite-build > \"/tmp/claude/vite-build.txt\" 2>&1", dangerouslyDisableSandbox: true)
   ```
4. **Spawn a commit subagent** to commit the fixes using `/git-commit`
5. **Re-run test subagent** writes output to a new temp file
6. **Repeat** up to 3 iterations. If failures persist after 3 rounds, stop and report to user.
7. **Clean up temp files** — delete all temp test output files once tests pass or the loop exits.

### Step 3: Completion

When all items are done:

1. **Run the relevant test suite via subagents** — sequentially, never simultaneously:
   - Spawn integration test subagent: `make test-integration-parallel`. Write output to `/tmp/claude/final-integration-results.txt`.
   - After it completes, spawn UI test subagent: `make test-ui-parallel-built`. Write output to `/tmp/claude/final-ui-results.txt`.
   - **Always use `test-ui-parallel-built`** — UI tests must run against built Vite assets, never the dev server.
   - Main agent reads each result file to determine pass/fail.
   - **Investigate every failure** — never dismiss a failure as "pre-existing" or "flaky" because the test file wasn't modified on this branch. Current changes can break tests indirectly (shared fixtures, CSS/selector changes, templates, timing, imports). For each failure: read the traceback, check if branch changes could affect the failing path, and either fix it or confirm it's unrelated by rerunning in isolation 2-3 times.
2. If failures exist, enter the **Test Fix Loop** (Section 2e).
3. **Clean up** all temp test output files. Also delete all files in `plans/<topic>/tmp/` (the subagent communication directory for this review run). Derive `<topic>` from the review file's parent path (`plans/<topic>/reviews/`).
4. Report final summary:

```
Review "<name>" — COMPLETE

Items resolved this run: X
Total items: Y
Test results: integration PASS/FAIL, UI PASS/FAIL

All changes committed. Ready for /git-push when you are.
```

If failures persist after the fix loop, report them and stop for user guidance.

## Key Differences from Related Skills

| Behavior | next-step-taker | run-review | run-plan |
|---|---|---|---|
| Pause after each item | Always | Only on blockers | Only on blockers |
| Commits | No | Yes, inside execution subagent | Yes, via commit subagent |
| Final test suite | No | Yes | Yes |
| Scope | Single item | All pending review items | All remaining plan steps |
| Main agent edits code | Never | Never | Never |
| Input | Plan or review | Review file only | Plan file only |

## Important Notes

- **Main agent is orchestrator only** — never directly edit implementation files, run tests, run make commands, or make code changes. ALL execution (code changes, tests, builds, make targets) MUST be delegated to subagents.
- **Main agent CAN**: read the review file, read temp test output files, run `git diff --name-only`, spawn subagents, re-read the review between items, and report progress.
- **Commits happen inside the execution subagent** — the subagent runs `/git-commit` as part of its workflow. The main agent does not commit directly.
- **Each subagent runs the full /next-step-taker review mode workflow** — including its own validation and review sub-subagents. The main agent does not duplicate that work.
- **Test output goes to temp files** — test runner subagents write output to `/tmp/claude/<name>.txt`. The main agent or fix subagent reads from these files. Clean up temp files when no longer needed.
- **Tests run via synchronous Bash inside subagents** — the subagent invokes `make test-*` with the synchronous `Bash` tool (and `dangerouslyDisableSandbox: true`), blocks until make exits, and reports the result. The orchestrator waits for the subagent's Agent-tool reply — that reply IS the completion signal. Do not arm a Monitor on the result file, do not poll a running subagent, and do not reach into a container with a side-channel probe.
- **Sandbox discipline** — git commands use default sandbox; Docker/make commands use `dangerouslyDisableSandbox: true`. Include this rule in all subagent prompts.
- **Review item ordering** — process items in the order they appear in the review file. Do not reorder or parallelize, as later items may depend on earlier fixes.
- When stopping on a blocker, report: which item failed, what was tried, what needs user input.
- **Investigate every test failure** — never dismiss a failure as "pre-existing" or "flaky" because the test file wasn't modified on this branch. Current changes can break tests indirectly (shared fixtures, CSS/selector changes, templates, timing, imports). For each failure: read the traceback, check if branch changes could affect the failing path, and either fix it or confirm it's unrelated by rerunning in isolation 2-3 times. Include this rule in all subagent prompts that run or evaluate tests.
