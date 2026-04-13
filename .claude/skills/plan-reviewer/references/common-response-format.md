# Plan Review — Common Response Format & Rules

Each subagent receives the plan file path and must independently read the plan and relevant source files. All subagents return a structured JSON response.

## Response Format (all subagents)

> **File delivery:** Write your complete JSON response to the file path provided in your prompt (`plans/<topic>/tmp/<role>.md`) **using the `Write` tool** — NEVER `cat <<EOF`, `cat >`, `tee`, `printf >`, `echo >`, or any Bash heredoc/redirect. JSON content containing `{` and quotes triggers the brace+quote security prompt; the `Write` tool bypasses this. Return only this one-line confirmation: `Written to <path>`. The orchestrator will read the file. The JSON structure below is unchanged.

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
      "category": "correctness | full-stack-trace | ordering | integration | verification | completeness",
      "fix_type": "mechanical | design_decision",
      "fix_description": "Exact edit to make (for mechanical) or description of the decision needed (for design_decision)",
      "design_options": ["option A", "option B"]
    }
  ],
  "files_read": ["list of files actually read during review"],
  "summary": "One-line summary of the review"
}
```

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
- `FAIL` if any `critical` or `major` finding exists
- `PASS` if only `minor` findings or none
- Every finding must cite a specific step number and file path where applicable
- Do not fabricate findings — if the plan is clean for your area, return PASS with empty findings
- **Verify before writing.** If you are about to write "the fix is X," read the file X touches first. A fix stated from memory or reasoning alone can introduce a new error worse than the original.
- **Do not trust plan assertions — including explanatory prose.** For any plan assertion about the current state of a file, directory, or package manifest, the reviewing subagent MUST read the actual file/directory to confirm. Never accept state assertions from plan prose alone. This applies to: file/directory existence, package versions, config field values, and import paths. Plans also embed factual claims in rationale prose ("only X does Y," "no route uses Z"). For every such claim — whether it appears as a precondition or as justification for a design decision — trace it to the source file and verify it holds. A wrong prose claim will mislead implementers even if the code spec is correct.
- **Verify anchors in source files, not just plan text.** When confirming a mechanical fix has been applied, do not stop at verifying plan text. For any fix that references a specific anchor in a source or reference file (import block, function body, registry row, config section), read that file and verify the anchor exists before accepting the fix as resolved.

**Fix verification rule (all subagents, Pass 2+):** When confirming a prior-pass fix has been applied:
1. Read the plan file and confirm the specific *old text* the fix required removing is no longer present — not just that the new text is present. "The plan now says X" is not sufficient if the old contradictory text still appears elsewhere in the same section.
2. For any fix that references a runtime behavior (path resolution, volume mount, import lookup, env var), also read the source file or config that governs that behavior and verify the runtime claim is true. "The plan now says X" is not the same as "X is true."
3. If both old and new text appear in the same section (e.g., a partially-applied edit), mark the fix as **REGRESSION** and re-open with Critical severity.
4. **Placement verification (required for fixes that insert text):** When a fix inserted a new sentence, bullet, or block, verify that its *position* relative to surrounding content is logically correct — not just that it is present. A pre-condition note that must precede an action bullet is incorrectly applied if it appears after that bullet. If the placement is wrong, re-open as a new Minor finding with a concrete move instruction.
5. **Conditional clause accuracy (required for fixes that add instructions with qualifiers):** When a fix added an instruction containing a conditional qualifier (e.g., 'update X if present', 'remove Y if applicable'), read the target file and verify whether the condition is actually true. If the condition is demonstrably false, flag the dead clause as Minor and instruct its removal.

**Container execution context (all subagents):** When the plan runs any command inside a Docker container (npm script, pytest, shell command), read the compose file that defines that service and verify: (a) the container WORKDIR, (b) all bind-mount paths, (c) where the referenced file actually resolves given (a) and (b). Do not trust the plan's prose description of the container environment.
