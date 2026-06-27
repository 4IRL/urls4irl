# Plan Review — Common Response Format & Rules

Each subagent receives the plan file path and must independently read the plan and relevant source files. All subagents return a structured JSON response.

## Response Format (all subagents)

> **File delivery:** Write your complete JSON response to the file path provided in your prompt (`plans/<topic>/tmp/<role>.md`) **using the `Write` tool** — NEVER `cat <<EOF`, `python3 << 'EOF'`, `cat >`, `tee`, `printf >`, `echo >`, or any Bash heredoc/redirect. Any heredoc or inline script containing `{` and quotes triggers the brace+quote security prompt; the `Write` tool bypasses this. Return only this one-line confirmation: `Written to <path>`. The orchestrator will read the file. The JSON structure below is unchanged.

```json
{
  "verdict": "PASS" | "FAIL",
  "findings": [
    {
      "severity": "critical" | "major" | "minor",
      "step": "Step N",
      "file": "path/to/file (if applicable)",
      "title": "Short finding title",
      "description": "What's wrong, why it matters, and what the plan should say instead",
      "category": "correctness | full-stack-trace | ordering | integration | verification | completeness | ux-accessibility",
      "fix_type": "mechanical | design_decision",
      "fix_description": "Exact edit to make (for mechanical) or description of the decision needed (for design_decision)",
      "design_options": ["option A", "option B"],
      "evidence": "<file>:<line> you actually read (absence claim: '<file> (grep:<pattern> → 0)'); REQUIRED for any finding referencing a named code entity — see Grounding Rule"
    }
  ],
  "files_read": ["list of files actually read during review"],
  "summary": "One-line summary of the review"
}
```

## Grounding Rule (all subagents — the single rule the per-area checklists apply)

A **named code entity** is any symbol, function, helper, fixture, constant, type/union member, class, attribute, route/endpoint, import binding, file path, directory, package version, config field, or established code pattern that a finding asserts something about — that it **exists, is absent, was preserved, was dropped, conflicts, or differs from a convention**.

1. **Read before claiming.** Before writing any finding that references a named code entity, Read or Grep the actual file. Never assert presence, absence, location, or behavior from plan prose (including rationale prose), another reviewer's claim, memory, or inference.
2. **Cite the evidence.** Every such finding MUST populate `evidence` with what you actually read: `"<file>:<line>"`, or for an absence claim the grep that returned zero — `"<file> (grep:<pattern> → 0)"`.
3. **Uncited = unverified.** A finding that references a named entity with no `evidence` may NOT be `mechanical`. Cap it at `minor`, set `fix_type: "design_decision"`, and the coordinator routes it as a conflict — never as an auto-applied fix.

The per-subagent checklists name the *specific triggers* for this rule in each area (function calls, replacement blocks, imports, test helpers, paths, single-instance sweeps, use-site traces). They are applications of this one rule — apply it to any named entity, not only the enumerated triggers.

### fix_type Classification Rules

Every finding MUST include a `fix_type`. Use these rules to classify:

**`mechanical`** — the fix is unambiguous and has exactly one correct resolution:
- Adding/keeping an import that is demonstrably used (grep confirms call sites exist)
- Removing an import that is demonstrably dead (grep confirms zero remaining usages)
- Fixing a plan self-contradiction (plan says "remove X" in one step and "use X" in another)
- Correcting a factual claim (plan says "function is at line 50" but it's at line 72)
- Cleaning up stream-of-consciousness / self-correcting notes into direct instructions
- Adding a missing file/function to a step when the plan already covers every other consumer of the same interface change
- Changing "optional" to "required" for cleanup of verified dead code
- Adding `make vite-build` or similar standard verification to a step that lacks any

For `mechanical` findings, `fix_description` must contain the exact edit: what text to find, what to replace it with, or what to add and where. `design_options` should be omitted or empty.

**`design_decision`** — multiple valid approaches exist and the choice affects behavior, architecture, or user experience:
- Choosing between refactoring a function vs. creating a wrapper/adapter
- Deciding whether to merge steps, reorder steps, or add a "commit together" note
- Choosing which modal/component should own an event handler
- Deciding whether to add new tests vs. relying on existing test coverage
- Choosing between keeping backward compatibility vs. clean break
- Any fix that changes control flow, event binding, or runtime behavior

For `design_decision` findings, `fix_description` must describe the decision needed. `design_options` must list at least 2 concrete options with enough detail to evaluate trade-offs.

**Default to `design_decision`** when uncertain. The cost of asking is low; the cost of a bad auto-applied fix is high.

**Bright-line rules (always `design_decision` regardless of how obvious the fix seems):**
- Any change to function signatures or parameter ordering
- Any change to event handler binding/unbinding
- Any change to step ordering or step merging
- Any change that adds or removes a test requirement
- Any change to error handling behavior or user-facing messaging

Rules:
- **Never write a bare absolute line number as a navigation anchor** in plan text or in a mechanical-fix correction. Always use a symbol anchor (search for `SymbolName`) as the primary locator. If a line number is included, mark it explicitly approximate (e.g., 'around line N') and pair it with a grep/search instruction. This prevents a prior-pass line-number correction from becoming the next-pass stale finding.
- `FAIL` if any `critical` or `major` finding exists
- `PASS` if only `minor` findings or none
- Every finding must cite a specific step number and file path where applicable
- Do not fabricate findings — if the plan is clean for your area, return PASS with empty findings
- **Grounding Rule applies to every state claim** (see above): file/directory existence, package versions, config field values, import paths, anchors in reference docs (import blocks, function bodies, registry rows, config sections), and rationale-prose claims ("only X does Y", "no route uses Z") all require reading the source file — cited in `evidence` — never accepted from plan prose. This holds both when raising a finding and when confirming a mechanical fix was applied (verify the anchor in the source file, not just that the plan text changed).

**Fix verification rule (all subagents, Pass 2+):** When confirming a prior-pass fix has been applied:
1. Read the plan file and confirm the specific *old text* the fix required removing is no longer present — not just that the new text is present. "The plan now says X" is not sufficient if the old contradictory text still appears elsewhere in the same section.
2. For any fix that references a runtime behavior (path resolution, volume mount, import lookup, env var), also read the source file or config that governs that behavior and verify the runtime claim is true. "The plan now says X" is not the same as "X is true."
3. If both old and new text appear in the same section (e.g., a partially-applied edit), mark the fix as **REGRESSION** and re-open with Critical severity.
4. **Placement verification (required for fixes that insert text):** When a fix inserted a new sentence, bullet, or block, verify that its *position* relative to surrounding content is logically correct — not just that it is present. A pre-condition note that must precede an action bullet is incorrectly applied if it appears after that bullet. If the placement is wrong, re-open as a new Minor finding with a concrete move instruction.
5. **Conditional clause accuracy (required for fixes that add instructions with qualifiers):** When a fix added an instruction containing a conditional qualifier (e.g., 'update X if present', 'remove Y if applicable'), read the target file and verify whether the condition is actually true. If the condition is demonstrably false, flag the dead clause as Minor and instruct its removal.

**Container execution context (all subagents):** When the plan runs any command inside a Docker container (npm script, pytest, shell command), read the compose file that defines that service and verify: (a) the container WORKDIR, (b) all bind-mount paths, (c) where the referenced file actually resolves given (a) and (b). Do not trust the plan's prose description of the container environment.
