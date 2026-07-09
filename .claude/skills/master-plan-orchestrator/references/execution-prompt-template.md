# Orchestrator Execution Prompt — Template

Used by `master-plan-orchestrator` Step 7. Fill in every `<bracketed>` placeholder from the
master plan just written (title, branch, topic, phase count, research findings) before writing
the result to `plans/<topic>/<name>-execution-prompt.md`.

The generated file has two parts:
- Everything **above** `## Prompt` — reference/resume scaffolding, never sent to the agent.
- The `## Prompt` section itself — handed **verbatim** to the top-level `Agent` call
  (`model: "fable"`, `subagent_type: "general-purpose"`). Do not paraphrase or summarize it when
  launching; pass its exact text.

This template is derived from a real run (`plans/playwright-migration/fable-execution-prompt.md`)
that completed a 10-phase Selenium→Playwright migration end-to-end with CI green on the first
attempt. Keep deviations from it deliberate, not accidental — every section below exists because
it prevented a specific failure mode (branch-per-phase drift, silent scope creep, unverified
progress claims, early stopping, premature Selenium/legacy removal, etc.).

**Effort parameter note:** Anthropic's Fable 5 guidance treats `effort` (`high`/`xhigh`) as the
primary intelligence/latency/cost control for this model. This repo launches Fable 5 through the
`Agent` tool, which does not expose an `effort` parameter — there is nothing to fill in for it
here. If a run is ever launched directly via the Messages API instead of the `Agent` tool, set
`effort: high` (or `xhigh` for a phase flagged as the hardest in Research Findings).

---

## Template

```markdown
# Fable 5 Execution Prompt — <Title>

Reference material for running <initiative one-liner> as one unattended Fable 5 effort, with
Sonnet 5 subagents doing the mechanical per-file work. This file is the actual prompt handed to
the top-level `Agent` call (`model: "fable"`, `subagent_type: "general-purpose"`) — kept here so
it can be reused/rerun without reconstructing it, and so a resumed run has a fixed reference point.

## Status
finished: false

## Prompt

**Task:** Execute <initiative description> described in `<master-plan-path>` — all <N> phases,
end-to-end, autonomously, in one continuous effort. <If any phase(s) already have a fully detailed
sub-plan, name them and their path(s) here — those are elaborated already. Every other phase is
only branch/title + high-level bullets in the master plan and must be elaborated by you, in
place, as you reach it.>

### Step 0 — orient and set up memory

- Confirm `main` is up to date (fetch/pull), then create a single branch `<branch-name>` from
  it. Do not use a worktree — work directly in this checkout. This one branch carries all <N>
  phases; there is no branch-per-phase.
- Read the master plan <and any existing sub-plan(s)> in full. Cross-check their assumptions
  (exact file/line references, current helper contents) against the actual repo state before
  acting on them.
- Create and continuously maintain a memory file at `plans/<topic>/<name>-progress.md`. This is
  your own persistent scratchpad for the entire run — if this run is interrupted and resumed,
  read this file first before re-deriving anything from git history. Structure it with:
  - A `## Status` section at the top: `finished: false`. This mirrors the master plan's own
    `## Status` block so `/plan-list` can track this file too — flip it to `true` only once the
    initiative reaches Definition of done, in the same edit that flips the master plan's.
  - A phase-by-phase status table (not-started / in-progress / done, commit range on
    `<branch-name>`, verification result).
  - A running decisions log — anywhere you deviated from a master-plan bullet and why.
  - A helper/pattern inventory — <domain-specific: e.g. every shared helper function added, so
    later phases reuse rather than duplicate>.
  - Known deferred/flagged items (e.g. anything needing a human to push, like
    `.github/workflows/` changes).
  Update this file after every phase and after any nontrivial decision.

### Per-phase execution

- For phases without a detailed sub-plan, elaborate the master plan's bullets into concrete
  steps yourself: read the actual current state of the target files/directories and adapt
  patterns already established in earlier phases rather than re-deriving from scratch. Do not
  produce a heavyweight sub-plan document per phase — scope inline as you go.
- **Single branch, not one per phase:** all <N> phases land on `<branch-name>` as sequential
  commits. This overrides the usual "each phase maps to its own branch/PR" convention — that
  convention assumes independent human-reviewed PRs merged one at a time; here the whole
  initiative is one continuous execution, so keep phase boundaries legible through clear,
  distinctly-labeled commits (e.g. a commit message prefix naming the phase, such as
  `<prefix>: <phase> — <what changed>`) rather than through separate branches.
- Delegate the bulk, mechanical work (<domain-specific: e.g. porting individual test files,
  marker-group by marker-group>) to Sonnet 5 subagents via your own `Agent` tool calls — pass
  `model: "sonnet"` explicitly on every nested call, never omit it. Keep for yourself: shared
  helper/pattern design, the highest-friction buckets called out in the master plan's research
  findings, and final phase-level verification.
- Don't consider a phase done, and don't advance to the next, until its to-do items are
  complete **and** its verification has actually run and passed (e.g.
  `<repo's per-phase verification command>`) — no progress claim without a command's real
  output backing it.
- **Independently verify each phase before advancing:** in addition to running the phase's
  verification command yourself, dispatch a fresh-context Sonnet 5 subagent (`model: "sonnet"`,
  no prior conversation state) to check the phase's diff against the master plan's bullets and
  this repo's conventions. A separate fresh-context verifier catches things self-critique
  misses. Only advance once both the command output and the verifier subagent agree the phase
  is correct.
- Commit at logical checkpoints within a phase. Once all <N> phases are complete and verified,
  stage, commit, and push the branch, then open a single PR covering the whole initiative — use
  `.claude/scripts/gh-app-push.sh` (never a bare `git push`), and reference the master plan's
  linked issue (`Closes #<issue-number>`) in the PR body. The PR itself is the review
  mechanism — do not add a separate pre-push human gate.
- **After the PR is open, watch CI to green.** Poll `gh pr checks <PR#> --repo <owner/repo>`
  (or `--watch`) until every check completes. For any failing check, fetch its log via
  `.claude/scripts/gh-log-fetch.sh run view --job <job-id> --repo <owner/repo> --log-failed`,
  diagnose the actual root cause (never dismiss a CI failure as a pre-existing/flaky/unrelated
  issue without investigating it per this repo's failure-investigation rules — CI is running
  the exact same suites you verified locally, so a CI-only failure means a local/CI environment
  discrepancy, not a fluke), fix it, commit, push, and re-watch. Repeat until every check on the
  PR is green — this is part of the task, not a hand-off point.

### Judgment — default unattended, ask when it's a genuine fork

- Default to unattended, autonomous execution across all <N> phases — do not pause for a
  check-in between phases as a matter of routine.
- You have the `AskUserQuestion` tool available. Use it when you hit a genuine fork you cannot
  resolve yourself and that materially changes the diff or a downstream phase (e.g. a
  master-plan assumption has drifted enough that two reasonable paths exist with real
  tradeoffs). Don't use it as a routine checkpoint, and don't let being blocked turn into silent
  improvisation on something consequential — ask instead of guessing.
- You have ample context remaining. Do not stop, summarize, or suggest a new session on account
  of context limits. Continue the work.
- Before ending your turn, check your last paragraph. If it is a plan, an analysis, a question,
  a list of next steps, or a promise about work you have not done ("I'll…", "next I will…"), do
  that work now with tool calls instead. End your turn only when the task is complete or you are
  blocked on input only the user can provide.

### Boundaries

- Stay inside the initiative's scope: <domain-specific list, pulled from the master plan's
  Research Findings — directories, shared helpers/config, what's explicitly out of scope>.
  Don't touch unrelated application code.
- <Any hard ordering constraint from research, e.g. "Phase <N> (removing the legacy system)
  only happens after every other phase's tests are verified green on the replacement — never
  take that shortcut early.">
- No tidying or refactors beyond what each phase's plan literally calls for.
- Follow this repo's `CLAUDE.md` exactly: exact-pinned dependencies, absolute imports, no
  single-letter variables, `make`/`docker` calls need `dangerouslyDisableSandbox: true`, tests
  always run via synchronous Bash (never `run_in_background`, never backgrounded)<, any other
  domain-specific test convention pulled from CLAUDE.md that materially applies, e.g. "UI tests
  always via -built targets">.

### Definition of done

- All <N> phases' to-do items complete and verified.
- <Final full-suite verification command(s), matching this repo's "Final Verification Step"
  convention — e.g. the full UI + integration suite green with the legacy system fully removed.>
- `<master-plan-path>`'s `## Status` updated to `finished: true`.
- `plans/<topic>/<name>-progress.md` reflects the final state of every phase, and its own
  `## Status` is flipped to `finished: true` in the same pass.
- This execution-prompt file's own `## Status` (above `## Prompt`) is flipped to `finished: true`
  as well — all three files (`master`, `progress`, `execution-prompt`) move to `finished: true`
  together once the initiative is truly done, not just once the code merges.
- Everything lives on the single `<branch-name>` branch, pushed with a single PR covering the
  whole initiative — the PR is where review happens.
- Every CI check on that PR is green. The task isn't complete until CI passes — local
  verification alone doesn't satisfy this.

### Final summary

Whoever reads your final report did not watch this run happen — write it as their first look,
not a continuation of your working shorthand. Open with the outcome in one sentence (what
shipped, whether CI is green). Then supporting detail: phases completed, the PR link, anything
that deviated from the master plan and why, anything flagged for the user (e.g. a manual push
needed). Drop arrow-chain shorthand, invented labels, and terse fragments — spell out file names,
commits, and flags in plain sentences.

## Assumptions before running

- The push and PR happen as a single pass at the very end, not per-phase; the PR itself is the
  review mechanism, not a step gated behind a prior review.
- <Any other initiative-specific assumption worth recording — e.g. a pinned version choice, a
  known environment quirk discovered during research.>
```

## Fill-in checklist (do not skip any)

- [ ] `## Status` block (`finished: false`) is present above `## Prompt` — never omit it; it's how `/plan-list` tracks this file.
- [ ] `<Title>`, `<initiative one-liner>`, `<initiative description>`, `<master-plan-path>`, `<N>` — pulled directly from the master plan.
- [ ] `<branch-name>` — the single branch chosen in Step 4/5. Must match the master plan's `**Branch:**` line exactly.
- [ ] Pre-existing detailed sub-plan(s), if any — name and path. Most initiatives have none; some (like a foundational first phase) may already have one written by `/plan-creator` before this skill ran.
- [ ] Per-phase verification command and final full-suite verification command(s) — pull from this repo's actual `make` targets (see `CLAUDE.md` → Development Commands), not invented ones.
- [ ] `<owner/repo>` — this repo's GitHub slug.
- [ ] Domain-specific delegation buckets (what's mechanical/subagent-able vs what the orchestrator keeps for itself) — pull from the master plan's Research Findings, not assumed.
- [ ] Scope boundaries and any hard ordering constraint — pull verbatim from Research Findings; don't paraphrase away a real constraint (e.g. "don't remove the legacy system until everything else is green" is load-bearing, not decoration).
- [ ] `Closes #<issue-number>` — filled in only after Step 8 creates the issue; if Step 8 ran before Step 7, this is already known.
