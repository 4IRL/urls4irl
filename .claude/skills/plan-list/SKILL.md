---
name: plan-list
description: List every plan document under plans/ — master plans AND sub-plans — with each plan's current completion status (finished/open), grouped by topic. Use when asked to "list plans", "/plan-list", "show all plans", "what plans do we have", "plan status", "which plans are done", or for an at-a-glance overview of planning docs and their progress.
---

# Plan List

Prints every plan under `plans/` (masters and sub-plans), grouped by topic, each tagged finished `[x]` or open `[ ]` and annotated with its related GitHub issue (`#N`, or `(no issue)` for plans that predate the issue-linking convention), with a summary count.

## Why a script (do not hand-roll this)

The lookup is delegated to `.claude/scripts/plan-list.sh` so the model never reads full plan files — that keeps the command both **token-cheap** and **accurate**:

- Status is read from the first `finished:` line *after* a plan's `## Status` heading. Plan bodies frequently quote a sub-plan's `` `finished: true` `` in prose; a naive `grep finished: true` reports those as completed plans. The script's heading-anchored, line-start match ignores them.
- A plan counts as a **master** iff its filename ends in `-master.md` (the only reliable signal in this repo).
- The related GitHub issue is read from the `github_issue: <N>` line in the plan's YAML frontmatter (written by `/plan-creator` and `/master-plan-creator`). Plans created before that convention show `(no issue)` — a useful signal that the link is missing, not an error.
- Coverage is `plans/<topic>/<name>.md` and `plans/<name>.md`; `reviews/`, `research/`, `compliance/`, and `tmp/` subfolders are excluded.

## Workflow

1. Run the scanner (a `make` target, so it never triggers a sandbox/permission prompt):

   ```
   make plan-list
   ```

   (Equivalent direct call: `.claude/scripts/plan-list.sh`.)

2. Relay the script's output to the user **verbatim** — it is already grouped, formatted, and summarized. Do **not** re-read individual plan files or re-derive any status; the script is the source of truth.

3. If any plan shows `[?]`, point out that that file is missing a `## Status` / `finished:` line and may be malformed — otherwise add nothing beyond at most a one-line summary.

Keep the response to the script output plus an optional single-line summary. Never expand into per-plan detail unless the user explicitly asks.
