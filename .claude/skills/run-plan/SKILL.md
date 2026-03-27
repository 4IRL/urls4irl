---
name: run-plan
description: Execute all remaining steps of a plan autonomously in a loop, without pausing between steps. Delegates each step to a subagent that runs the /next-step-taker workflow (execute, validate, review, update tracking). The main agent is purely an orchestrator — it reads the plan, spawns subagents, commits, and moves to the next step. Only stops on blockers (test failures, unresolved review findings, design decisions requiring user input) or when the plan is finished. Use when asked to "run the plan", "execute all steps", "finish the plan", "auto-run", or "keep going until done". Argument is the plan name (e.g., "/run-plan splash-modal-prerender").
argument-hint: plan-name
---

# Run Plan Skill

Autonomously execute all remaining steps of a plan. The **main agent is an orchestrator only** — it reads the plan, delegates each step to a subagent running `/next-step-taker`, commits, and loops. It never directly edits implementation files or runs tests.

## Branch Guard

1. If on `main`/`master`: run `gmas`, suggest a feature branch, ask user to confirm before proceeding
2. If on a feature branch: proceed

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
- Use dangerouslyDisableSandbox: true for all Docker commands.
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

#### 2c. Commit (via subagent)

Launch a separate subagent to commit the step's changes using `/git-commit`. The commit subagent handles staging, message generation, and pre-commit hook failures autonomously.

#### 2d. Progress Report

Print a brief progress line:
```
[Step X/N] Step Name — COMPLETE
```

Then re-read the plan to check for any modifications the subagent made, and loop to the next incomplete step.

### Step 3: Completion

When all steps are done or the plan is marked finished:

1. Run the full test suite via subagent (`make test-integration-parallel` then `make test-ui-parallel-built` — sequentially, never simultaneously)
2. Report final summary:

```
Plan "<name>" — COMPLETE

Steps completed this run: X
Total steps: Y
Test results: integration PASS/FAIL, UI PASS/FAIL

All changes committed. Ready for /git-push when you are.
```

If the final test suite reveals failures, report them and stop for user guidance.

## Key Differences from next-step-taker

| Behavior | next-step-taker | run-plan |
|---|---|---|
| Pause after each step | Always | Only on blockers |
| Auto-commit | No | Yes, after each step |
| Final test suite | No | Yes, runs all tests at end |
| Scope | Single step | All remaining steps |
| Main agent edits code | Never | Never — delegates to subagent |

## Important Notes

- **Main agent is orchestrator only** — never directly edit implementation files, run tests, or make code changes. Delegate everything to subagents running `/next-step-taker`.
- **Main agent CAN**: read the plan, run `git diff --name-only`, spawn subagents (execution + commit), re-read the plan between steps, and report progress.
- **Each subagent runs the full /next-step-taker workflow** — including its own validation and review sub-subagents. The main agent does not duplicate that work.
- **Commits are delegated to `/git-commit` subagents** — never commit directly from the main agent.
- If a step modifies the plan itself (e.g., adds sub-steps), the main agent re-reads the plan before continuing.
- When stopping on a blocker, report: which step failed, what was tried, what needs user input.
