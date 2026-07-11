---
name: master-plan-orchestrator
description: Creates a master plan for a multi-phase initiative meant to be executed end-to-end, autonomously, by a single long-running orchestrator agent (e.g. Claude Fable 5) on ONE branch with ONE PR at the end — not one branch/PR per phase reviewed by a human between phases. Also generates a companion orchestrator execution prompt (memory file, per-phase Sonnet-subagent delegation, verification-before-advancing, CI-watch-to-green loop, ask-only-on-genuine-forks judgment) ready to hand to an Agent call. If a design doc (see /design-doc) already exists under plans/<topic>/, this skill detects and reads it as the primary source for problem framing and resolved design decisions rather than re-deriving them. Use when the user asks for an "orchestrator plan", "autonomous multi-phase plan", a "single-agent migration plan", a plan meant to run "end-to-end" or "unattended" by Fable 5, or explicitly says phases should NOT be split into separate branches/PRs. For a multi-PR initiative with a human-reviewed gate between phases, use /master-plan-creator instead. If the feature's shape (not just its phasing) is still undecided, run /design-doc first.
---

## Relationship to `/design-doc`, `/master-plan-creator`, and `/plan-creator`

`/design-doc` answers **what and why** and is optional upstream input — run it first only when
the feature's shape is still undecided. This skill answers **how** (phasing, branch, execution
contract) and always checks for a design doc's existence (Step 2a) before treating Summary/
Research Findings as something it must derive from scratch.

This skill **reuses** shared machinery by reference — do not duplicate:

- **Branch Guard** → `.claude/skills/plan-creator/SKILL.md` § Branch Guard (governs the branch you're on while *writing the plan file* — not the initiative's execution branch, which is decided in Step 5 and created later by the orchestrator itself)
- **Topic Folder determination** → `.claude/skills/plan-creator/SKILL.md` § Step 1
- **Research subagent harness + master-scope prompts** → `.claude/skills/master-plan-creator/SKILL.md` § Step 3 and `.claude/skills/master-plan-creator/references/research-prompts-master.md` (same breadth-focused research — reused verbatim, no separate copy)

What this skill **diverges on**, vs `/master-plan-creator`:

- **ONE `**Branch:**` for the whole initiative** (top-level, under the title) — not one per phase. There is no per-phase branch or PR.
- **Phases are elaborated in place by the orchestrator during execution** — never split into `/plan-creator` sub-plans. The to-do bullets stay coarse on purpose; the orchestrator (not a human, not a separate skill invocation) turns them into concrete steps when it reaches each phase.
- **One GitHub issue**, not an umbrella + sub-issue tree — there are no child phase issues to attach, since everything closes with a single PR.
- **A second artifact**: a companion *orchestrator execution prompt* file that encodes the Fable-5-specific execution contract (memory, delegation, verification gating, CI watch loop, judgment policy).

## Step 1: Branch Guard

Follow `.claude/skills/plan-creator/SKILL.md` § Branch Guard verbatim.

## Step 2: Determine Parent Topic Folder

Follow `.claude/skills/plan-creator/SKILL.md` § Step 1 verbatim. Store as `<topic>`.

## Step 2a: Check for an Existing Design Doc

Glob `plans/<topic>/*-design.md`. If one exists (or the user names it directly), read it in
full and treat its **Problem / Why / Outcome / Design Decisions** sections as settled — do not
re-derive them from scratch in Step 3 or re-ask the user anything it already resolved. Carry it
forward as `<design-doc-path>` for later steps.

If none exists, proceed with Step 3 exactly as before, deriving Summary/Research Findings
entirely from subagent research and the user's request. Do not require a design doc — this
skill remains fully usable for initiatives where the feature's shape is already fully specified.

## Step 3: Deep Research — Master Scope

Follow `.claude/skills/master-plan-creator/SKILL.md` § Step 3 verbatim: same subagent harness pattern, same research prompts (`.claude/skills/master-plan-creator/references/research-prompts-master.md`).

One difference in how you use Subagent 4's (Branch Naming Conventions) findings: pick **one** branch name for the entire initiative, not a name per phase.

If a design doc was found in Step 2a, still run this research — it covers scope/phase-boundary/
ordering/branch-naming concerns the design doc doesn't address (the design doc answers *what
and why*, not phasing or file-level scope). Fold its Codebase Context bullets into your findings
instead of re-researching what it already covered.

## Step 4: Propose Phases & the Single Branch

Draft the phase list using the same criteria as `/master-plan-creator` § Step 4 (cohesive groupings, respects ordering dependencies) with one change: phases are **not** sized to "ships as a single PR" — they're sized to a reviewable unit of *sequential orchestrator work* (a commit range within the one PR), since every phase lands in the same PR at the end.

Propose exactly **one** branch name for the whole initiative, following the repo's observed conventions (from Subagent 4).

Present the proposed phases and the single branch to the user via `AskUserQuestion`:
- **Accept as proposed** — proceed to Step 5
- **Modify** — user provides adjustments; redraft and re-present
- **Cancel** — abort skill

Do not write any file until the user accepts.

## Step 5: Write the Master Plan

Write to `plans/<topic>/<name>-master.md` (kebab-case filename ending in `-master`).

Use exactly this structure:

```markdown
# <Title>

**Branch:** `<branch-name>` (single branch — every phase lands here as sequential commits; one PR at the end)

## Summary
<2-4 sentences on what this initiative does and why. If a design doc exists (Step 2a), draw this directly from its Problem/Why/Outcome instead of re-deriving it. State explicitly that this is one continuous autonomous execution — not per-phase PRs — and that later phases are elaborated in place by the orchestrator, not pre-written as sub-plans.>

<If a design doc exists, include this line: **Design doc:** `<design-doc-path>` — see for full problem framing and resolved design decisions.>

## Research Findings
<3-6 bullets summarizing scope, phase boundaries, and notable constraints from subagent research. If a design doc exists, this section covers phasing/scope/ordering only — do not repeat its Design Decisions verbatim here, just reference it.>

## Steps

### 1. <Phase title>
<One sentence describing what this phase accomplishes.>

**To-do:**
- [ ] <Coarse bullet — the orchestrator elaborates this into concrete steps during execution, reading the target's actual current state; no separate sub-plan is written for this phase>
- [ ] <Coarse bullet>

---

### 2. <Phase title>
...

## Status
finished: false
```

**Rules:**
- Exactly **one** `**Branch:**` line, directly under the title — never per-step. This is the load-bearing difference from `/master-plan-creator`'s output; get it right.
- To-dos stay coarse (same rationale as `/master-plan-creator`: sub-plan-elaboration territory) but are understood to be elaborated by the orchestrator inline, not by a separate `/plan-creator` invocation.
- Do NOT include TDD Enforcement, Package Pinning, Dead Import Elimination, Function Signature Change, or Frontend/Backend Colocation sections — those protocols are already codified in this repo's `CLAUDE.md`, and the execution prompt (Step 7) tells the orchestrator to follow it exactly during each phase's inline elaboration.
- Do NOT include a per-phase or final test-verification phase in the master itself. Verification is a per-phase gate enforced by the execution prompt's "don't advance without a passing command" rule, not a master-plan phase.
- Separate steps with `---` horizontal rules for readability.

## Step 6: Validation

Before reporting success, verify:
1. Exactly one line matches `\*\*Branch:\*\* \`[^\`]+\`` (Grep the file — must be a single match, not one per step).
2. The `## Status` block is present with `finished: false`.

If any check fails, fix the plan file before proceeding.

## Step 7: Generate the Orchestrator Execution Prompt

This is the artifact that makes the master plan executable by a single autonomous agent instead of a sequence of human-reviewed PRs.

Read `references/execution-prompt-template.md` in full — it contains the template structure and fill-in guidance. Fill in every placeholder from the master plan you just wrote (title, branch name, topic, phase count, scope boundaries, verification commands, ordering constraints) and write the result to `plans/<topic>/<name>-execution-prompt.md`. Include the template's `## Status` block (`finished: false`) above `## Prompt` verbatim — do not drop it; it's what lets `/plan-list` track this file the same way it tracks the master plan.

If any phase touches user-visible UI, keep the template's Boundaries rule intact: new UI must fit
the app's existing color palette, component patterns, and interaction conventions — never stand
apart as its own look. Phases without a design doc or pre-existing mockup pinning down their UI
shape still owe a lightweight mock (real CSS/theme values, no invented styling) before the
orchestrator implements them. This is a hard constraint the orchestrator resolves itself by
grepping real theme/component values, not a check-in point — autonomous execution stays fully
unattended here; "match existing conventions" is always the right call, so there's nothing to ask
about.

The template's `## Prompt` section is what later gets handed to the orchestrator **verbatim**, via a separate `Agent` tool call with `model: "fable"`. Everything above `## Prompt` in the generated file is reference/resume scaffolding for whoever launches or re-launches the run — it is never itself sent to the agent.

## Step 8: Create GitHub Issue

Follow `.claude/skills/plan-creator/SKILL.md` § Step 4 (search existing issues, generate Problem/Why/Outcome body, infer labels, create, add to project board + bot assignee), with two simplifications since this initiative closes with a single PR:

- **Skip § 4d entirely** (native sub-issue attachment / umbrella detection) — there are no child phase issues that will ever exist to attach.
- The body's footer line reads `Master plan: \`plans/<topic>/<name>-master.md\`` (not `Plan:`).

If a design doc exists (Step 2a), reuse its Problem/Why/Outcome sections **verbatim** for the
issue body instead of re-deriving them from Research Findings — the design doc is the source of
truth for what/why; Research Findings only inform phasing, which isn't issue-body content.

Write `github_issue:` / `github_issue_url:` YAML frontmatter into `<name>-master.md` only (not the execution-prompt file — that file references the issue by number inline in its template, not via frontmatter).

## Step 9: Cleanup & Summary

1. Delete all `plans/<topic>/tmp/research-*-master.md` files.
2. Ask the user via `AskUserQuestion` whether to launch now:
   - **Launch the orchestrator now** — spawn `Agent` with `model: "fable"`, `subagent_type: "general-purpose"`, and `prompt` set to the exact contents of the execution-prompt file's `## Prompt` section (verbatim, no paraphrasing)
   - **Just create the files** — stop here; the user launches later by pointing at the execution-prompt file
3. Report to the user:
   - Master plan path and execution-prompt path
   - Number of phases
   - Issue: `#<N>` and URL (or a warning if Step 8 failed)
   - If launched: the spawned agent's id

Append a changelog entry per user-level CLAUDE.md rules (`master-plan-orchestrator: Created plans/<topic>/<name>-master.md + <name>-execution-prompt.md with N phases, issue #<N>`).
