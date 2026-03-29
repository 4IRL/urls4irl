---
name: run-plan
description: Execute all remaining steps of a plan autonomously in a loop, without pausing between steps. Delegates each step to a subagent that runs the /next-step-taker workflow (execute, validate, review, update tracking). The main agent is purely an orchestrator — it reads the plan, spawns subagents, commits, and loops. Only stops on blockers (test failures, unresolved review findings, design decisions requiring user input) or when the plan is finished. Use when asked to "run the plan", "execute all steps", "finish the plan", "auto-run", or "keep going until done". Argument is the plan name (e.g., "/run-plan splash-modal-prerender").
argument-hint: plan-name
---

# Run Plan Skill

Autonomously execute all remaining steps of a plan. The **main agent is an orchestrator only** — it reads the plan, delegates each step to a subagent running `/next-step-taker`, commits, and loops. It never directly edits implementation files, runs tests, or runs build/make commands.

## Branch Guard

1. If on `main`/`master`: run `gmas`, suggest a feature branch, ask user to confirm before proceeding
2. If on a feature branch: proceed

## Sandbox Rules

- **Git commands** (`git add`, `git commit`, `git status`, `git diff`, etc.): run in **default sandbox** — never use `dangerouslyDisableSandbox`
- **Docker/make commands**: use `dangerouslyDisableSandbox: true` (Docker socket requires it)
- Subagent prompts must include these rules so subagents follow them too

## Workflow

### Step 1: Locate and Read the Plan

- Find the plan in `plans/` matching **$ARGUMENTS**
- Read the full plan to understand scope and remaining work
- Count total steps and identify which are already complete (`[x]`) vs remaining (`[ ]`)
- Report to user: "Found N remaining steps out of M total. Starting from Phase/Step X."

### Step 2: Execution Loop

For each remaining incomplete step, the main agent orchestrates:

#### 2a. Spawn Execution Subagent

Launch a subagent via the Agent tool with this prompt pattern:

```
Run /next-step-taker for the plan "<plan-name>".

The next incomplete step is Step N: <step name>.

Important overrides for this run:
- Do NOT pause at the end to ask the user — complete the full workflow (execute, validate, review, fix, update tracking) and return your final report.
- Follow all CLAUDE.md guidelines.
- Use dangerouslyDisableSandbox: true for Docker/make commands only. Never for git commands.
```

The subagent handles the entire next-step-taker workflow internally:
1. Execute the step (read files, implement changes)
2. Validate (build, tests via its own sub-subagents)
3. Review pipeline (3 parallel review subagents + fix subagent)
4. Update plan tracking (checkmarks, dates)
5. Return its final report (what changed, validation results, review findings)

#### 2b. Evaluate Subagent Result

The main agent reads the subagent's report and decides:

**Auto-continue** when ALL of these are true:
- Validation passed (build clean, tests green)
- Review pipeline returned all PASS or all findings were fixed
- No unresolved items requiring user decisions

**Stop and ask** when ANY of these are true:
- Test failures that couldn't be auto-fixed
- Review has UNRESOLVED findings (require user decision)
- Fix subagent returned `VALIDATION: FAIL`
- The step's plan instructions were ambiguous
- The plan's `finished` flag was set to `true` (all steps done)

#### 2c. Smoke Test After UI-Affecting Steps

If the completed step changed frontend code (JS, templates, CSS) or test locators/selectors, spawn a **smoke test subagent** before committing to catch issues early:

```
Run a quick UI smoke test against built assets. Execute:
  make test-ui-parallel-built n=2
Write the full test output to $TMPDIR/smoke-test-step-N.txt.
Report: total passed, total failed. If failures, include test names and error summaries.
Use dangerouslyDisableSandbox: true for make commands.
```

If the smoke test fails, enter the **Test Fix Loop** (Section 2e) before committing. If it passes, proceed to commit.

#### 2d. Commit (via subagent)

Spawn a **commit subagent** to handle the entire commit workflow. The main agent must never load or execute `/git-commit` itself — doing so pulls staging, diff analysis, message drafting, and pre-commit hook fix loops into the main context window.

```
Commit the current changes using /git-commit.
Follow all CLAUDE.md guidelines.
Never use dangerouslyDisableSandbox for git commands.
```

**Why a subagent:** `/git-commit` involves reading diffs, generating messages, and potentially multiple pre-commit fix iterations — all of which pollute the orchestrator's context if run inline. The subagent absorbs this work and returns only a short summary.

#### 2e. Test Fix Loop (when tests fail)

When any test run (smoke test, final suite, or step validation) reports failures:

1. **Test runner subagent** writes full output to a temp file (`$TMPDIR/<descriptive-name>.txt`)
2. **Main agent reads the temp file** to understand failure count and patterns
3. **Fix subagent** is spawned with:
   ```
   Fix the following UI/integration test failures. The full test output is at:
     <path-to-temp-file>
   Read this file to understand all failures, then fix them.
   <include user decisions if any were provided>
   After fixing, run `make vite-build` and `make test-js` to verify JS changes.
   Do NOT run the full test suite — just implement fixes.
   Use dangerouslyDisableSandbox: true for Docker/make commands only.
   ```
4. **Re-run test subagent** writes output to a new temp file
5. **Repeat** up to 3 iterations. If failures persist after 3 rounds, stop and report to user.
6. **Clean up temp files** — delete all temp test output files once tests pass or the loop exits.

### Step 3: Completion

When all steps are done or the plan is marked finished:

1. **Run the full test suite via subagents** — sequentially, never simultaneously:
   - Spawn integration test subagent: `make test-integration-parallel`. Write output to `$TMPDIR/final-integration-results.txt`.
   - After it completes, spawn UI test subagent: `make test-ui-parallel-built`. Write output to `$TMPDIR/final-ui-results.txt`.
   - **Always use `test-ui-parallel-built`** — UI tests must run against built Vite assets, never the dev server.
   - Main agent reads each result file to determine pass/fail.
2. If failures exist, enter the **Test Fix Loop** (Section 2e).
3. **Clean up** all temp test output files.
5. Report final summary:

```
Plan "<name>" — COMPLETE

Steps completed this run: X
Total steps: Y
Test results: integration PASS/FAIL, UI PASS/FAIL

All changes committed. Ready for /git-push when you are.
```

If failures persist after the fix loop, report them and stop for user guidance.

## Key Differences from next-step-taker

| Behavior | next-step-taker | run-plan |
|---|---|---|
| Pause after each step | Always | Only on blockers |
| Auto-commit | No | Yes, via commit subagent |
| Final test suite | No | Yes, runs all tests at end |
| Scope | Single step | All remaining steps |
| Main agent edits code | Never | Never — delegates to subagent |

## Important Notes

- **Main agent is orchestrator only** — never directly edit implementation files, run tests, run make commands, or make code changes. ALL execution (code changes, tests, builds, make targets) MUST be delegated to subagents. This includes the final test suite in Step 3.
- **Main agent CAN**: read the plan, read temp test output files, run `git diff --name-only`, spawn subagents (including commit subagents), re-read the plan between steps, and report progress. **Main agent CANNOT** invoke `/git-commit` directly — it must always be delegated to a subagent.
- **Each subagent runs the full /next-step-taker workflow** — including its own validation and review sub-subagents. The main agent does not duplicate that work.
- **Test output goes to temp files** — test runner subagents write output to `$TMPDIR/<name>.txt`. The main agent or fix subagent reads from these files. Clean up temp files when no longer needed.
- **Sandbox discipline** — git commands use default sandbox; Docker/make commands use `dangerouslyDisableSandbox: true`. Include this rule in all subagent prompts.
- If a step modifies the plan itself (e.g., adds sub-steps), the main agent re-reads the plan before continuing.
- When stopping on a blocker, report: which step failed, what was tried, what needs user input.
