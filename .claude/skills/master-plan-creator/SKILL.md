---
name: master-plan-creator
description: Creates a high-level master plan that decomposes a multi-PR initiative into numbered phases, each with a **Branch:** field. Use when the user asks to create a "master plan", "migration plan", "multi-PR plan", "umbrella plan", or a plan that "spans multiple branches/PRs/phases". Not for single-PR plans — use /plan-creator for those.
---

## Relationship to `/plan-creator`

This skill **reuses** `/plan-creator`'s shared machinery by reference — do not duplicate.
Authoritative sources (read these verbatim when the step below says "reuse"):

- **Branch Guard** → `.claude/skills/plan-creator/SKILL.md` § Branch Guard
- **Topic Folder determination** → `.claude/skills/plan-creator/SKILL.md` § Step 1
- **Research subagent harness** → `.claude/skills/plan-creator/SKILL.md` § Step 2 (pattern; see `references/research-prompts-master.md` for master-level prompts, not plan-creator's)
- **Research cleanup** → `.claude/skills/plan-creator/SKILL.md` § Step 3 Cleanup

What this skill **adds** on top:
- A master-scope research prompt set (broader than plan-creator's deep-dive)
- A `**Branch:**` field required on every non-verification step
- Coarser to-do granularity (sub-plan territory, not detailed implementation)

## Step 1: Branch Guard

Follow `.claude/skills/plan-creator/SKILL.md` § Branch Guard verbatim.

## Step 2: Determine Parent Topic Folder

Follow `.claude/skills/plan-creator/SKILL.md` § Step 1 verbatim. Store as `<parent-topic>`.
This is the master plan's home (e.g. `openapi-typescript`). Sub-plan folders will be separate — do NOT nest sub-plans here.

## Step 3: Deep Research — Master Scope

Follow the subagent harness pattern in `.claude/skills/plan-creator/SKILL.md` § Step 2 (including: NEVER use `subagent_type: "Explore"` — Explore agents cannot use the Write tool; omit `subagent_type` to get general-purpose), with two differences:

1. Use master-level research prompts from `references/research-prompts-master.md` — NOT plan-creator's `references/research-prompts.md`. Master prompts focus on breadth (scope enumeration, phase boundaries, ordering, branch-naming conventions) rather than depth (signatures, data shapes).
2. Before launching, create `plans/<parent-topic>/tmp/` (same as plan-creator).

Subagents write their findings to `plans/<parent-topic>/tmp/research-<focus>-master.md` and return a one-line confirmation.

After subagents return, read each output file and compile findings for Step 4.

## Step 4: Propose Phases & Branches

Based on research findings, draft a numbered phase list where each phase:
- Represents a single PR / branch of work
- Has a suggested `**Branch:**` following the repo's observed naming conventions (from subagent 4)
- Respects ordering dependencies (from subagent 3)
- Is cohesive enough to review in a single PR

Present the proposed phases and branches to the user via `AskUserQuestion` with choices:
- **Accept as proposed** — proceed to Step 5
- **Modify** — user provides adjustments; redraft and re-present
- **Cancel** — abort skill

Do not write any plan file until the user accepts.

## Step 5: Write the Master Plan

Write to `plans/<parent-topic>/<name>-master.md` (kebab-case filename ending in `-master`).

Use exactly this structure:

```markdown
# <Title>

## Summary
<2-4 sentence description of what this initiative does and why. Mention that each phase maps to its own branch/PR with a detailed sub-plan.>

## Research Findings
<3-6 bullets summarizing scope, phase boundaries, and notable constraints from subagent research.>

## Steps

### 1. <Phase title>
<One sentence describing what this phase accomplishes.>

**Branch:** `<branch-name>`

**To-do:**
- [ ] <Coarse bullet — a sub-plan will elaborate this into detailed tasks>
- [ ] <Coarse bullet>

---

### 2. <Phase title>
...

---

### N. Verify All Tests Pass
Final umbrella verification after every phase merges.

**To-do:**
- [ ] Run `make test-js` and confirm all JS/TS unit tests pass
- [ ] Run `make test-integration-parallel` and confirm all integration tests pass
- [ ] Run `make test-ui-parallel-built` and confirm all UI/functional tests pass
- [ ] Investigate and fix any failures before marking the plan finished

## Status
finished: false
```

**Rules:**
- Every non-verification step MUST have a `**Branch:**` line with a backtick-quoted branch name.
- To-dos are intentionally coarse — they name the work, not every file. Sub-plans elaborate.
- Do NOT include TDD Enforcement, Package Pinning, Dead Import Elimination, Function Signature Change, or Frontend/Backend Colocation sections. Those belong in sub-plans (`/plan-creator` enforces them).
- Do NOT include a Final Verification inside each phase — only the umbrella one as the last step.
- Separate steps with `---` horizontal rules for readability.

## Step 6: Validation

Before reporting success, verify:
1. Every non-verification step has a `**Branch:**` line matching the pattern `\*\*Branch:\*\* \`[^\`]+\``. Use Grep on the master plan file.
2. The `## Status` block is present with `finished: false`.

If any check fails, fix the plan file. Do not proceed to Step 7 until both pass.

## Step 7: Cleanup & Summary

1. Delete all `plans/<parent-topic>/tmp/research-*-master.md` files.
2. Report to the user:
   - Master plan path
   - Number of phases created
   - Suggested next command: `/plan-creator "Step 1 of <master-plan-name>"`

Note: Sub-plan folders are created on-demand by `/plan-creator` when each phase's sub-plan is written.

Append a changelog entry per user-level CLAUDE.md rules (`master-plan-creator: Created plans/<parent-topic>/<name>-master.md with N phases`).
