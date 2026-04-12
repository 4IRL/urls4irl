# Steps 6-7: Root-Cause Analysis & Skill Self-Improvement

**These steps only execute when prior reviews exist AND the current pass found findings that prior passes missed.**

## Step 6: Root-Cause Analysis of Missed Findings

**Skip if this is the first review for the plan.**

When appending a new review pass and the current pass found findings that prior passes missed, add a `### Missed-Finding Root Causes` section. For each new finding, answer:

1. **What was missed?** — One-line summary.
2. **Why was it missed?** — Classify:
   - **Trusted plan assertion**: Plan stated something as fact, reviewer accepted without tracing
   - **Incomplete file reads**: Issue lives in a file the plan never references but is on the critical path
   - **Fix verification stopped at plan text**: Prior round confirmed the plan "says X" but nobody re-read the source file
   - **Scoped too narrowly**: Review dimension applied only to plan-referenced files, not the broader system
   - **Other**: Describe
3. **Skill gap**: Does the miss reveal a gap in the plan-reviewer skill's instructions?

Format:

```markdown
### Missed-Finding Root Causes
| Finding | Root cause | Skill gap? |
|---|---|---|
| <finding> | <root cause + details> | <gap or "Instructions already cover this"> |
```

After writing, check if the same root cause recurs across reviews. If so, flag it for Step 7.

## Step 7: Skill Self-Improvement

**Skip if this is the first review for the plan or if Step 6 found zero missed findings.**

After mechanical fixes are applied and the root-cause table is written, launch a **single skill-improvement subagent** that cross-references the current review's findings with prior reviews to identify and fix gaps in the reviewer skill itself.

### 7a: Launch the skill-improvement subagent

The subagent receives:
- The review file path (`plans/<topic>/reviews/<plan-name>-review.md`)
- The plan file path
- The `### Missed-Finding Root Causes` table from Step 6
- Paths to skill files: `.claude/skills/plan-reviewer/SKILL.md` and the individual subagent reference files in `.claude/skills/plan-reviewer/references/` (e.g., `sa1-correctness.md` through `sa6-completeness.md`)
- Path to project CLAUDE.md
- Path to memory index: `.claude/projects/-Users-ggpropersi-code-urls4irl/memory/MEMORY.md`

The subagent:

1. **Reads all inputs**: review file (all passes), skill files, CLAUDE.md, memory index + any referenced memory files
2. **For each missed finding from Step 6**, determines:
   - **Which subagent (1-6) should have caught it** — based on the finding's category and the subagent checklists
   - **Why that subagent missed it** — maps to one of:
     - `prompt_gap`: The subagent's checklist doesn't cover this class of issue
     - `prompt_ambiguity`: The checklist covers it but the wording is too vague to enforce
     - `missing_context`: The subagent lacks awareness of a project convention or pattern
     - `scope_limitation`: The subagent's "what to read" section doesn't include the relevant files
     - `no_skill_gap`: The subagent's instructions already cover this; it was an execution miss (no fix needed)
   - **Concrete improvement** — exactly what to change and where:
     - For `prompt_gap`: exact checklist item to add to the subagent's file (e.g., `.claude/skills/plan-reviewer/references/sa3-ordering.md`)
     - For `prompt_ambiguity`: exact rewrite of the ambiguous checklist item
     - For `missing_context`: either a CLAUDE.md addition or a new memory file
     - For `scope_limitation`: exact edit to the subagent's "What to read" section
     - For `no_skill_gap`: no change proposed

3. **Checks for recurring patterns**: If the same root cause (`prompt_gap`, `prompt_ambiguity`, etc.) appears 2+ times across the same subagent, proposes a **structural improvement** (new checklist section, expanded scope) rather than individual line additions.

4. **Returns a JSON response**:

```json
{
  "improvements": [
    {
      "finding_title": "The missed finding from Step 6",
      "responsible_subagent": 3,
      "gap_type": "prompt_gap | prompt_ambiguity | missing_context | scope_limitation | no_skill_gap",
      "explanation": "Why this subagent missed it and how the improvement prevents recurrence",
      "target_file": "path to file being modified",
      "change_type": "add_checklist_item | rewrite_checklist_item | add_to_what_to_read | add_claude_md_rule | add_memory | no_change",
      "old_text": "existing text to replace (null for additions)",
      "new_text": "new or replacement text",
      "location_hint": "section name or after which existing item to insert"
    }
  ],
  "recurring_patterns": [
    {
      "pattern": "Description of recurring gap",
      "affected_subagents": [2, 5],
      "structural_proposal": "Description of structural improvement"
    }
  ],
  "summary": "One-line summary of proposed improvements"
}
```

### 7b: Present improvements for user approval via AskUserQuestion

**Always use the `AskUserQuestion` tool — never plain-text y/n prompts.** Build a single multi-select question listing every proposed improvement as an option; the user selects the subset to apply. If recurring patterns are also proposed, include them as additional options in the same question (or a second question if you exceed the 4-option cap).

**Question construction:**
- `question`: `"Which skill improvements should be applied?"`
- `header`: `"Skill fix"` (≤12 chars)
- `multiSelect: true`
- One option per improvement:
  - `label` (1-5 words): e.g. `"SA#5 verify test-js"` — short tag for the improvement
  - `description` (trade-off): gap type + one-line summary of the change + target file
  - `preview` (optional): the exact `old_text → new_text` diff snippet for visual review

**Option cap handling:** If more than 4 improvements are proposed, batch them across multiple `AskUserQuestion` calls (max 4 options each). Present them in priority order: structural/recurring-pattern proposals first, then individual improvements.

**"Other" handling:** The tool adds an "Other" option automatically — if the user writes custom text there, treat it as a rejection of the listed options plus a custom instruction to apply instead. Read the user's note and pass it to the applier subagent (7c).

**Do NOT apply any improvement without explicit user approval.** Unselected options are treated as rejected for this pass.

### 7c: Apply approved improvements

For each approved improvement:
1. Apply the edit to the target file (the relevant `sa{N}-*.md` file, `CLAUDE.md`, or a memory file)
2. If adding a memory file, also update the memory index at `MEMORY.md`
3. After all edits, verify the modified files are syntactically coherent (no broken markdown, no orphaned references)

### 7d: Write improvements to review document

Append a `### Skill Improvements Applied` section to the current review pass:

```markdown
### Skill Improvements Applied
| # | Finding | Subagent | Gap type | Change | Status |
|---|---|---|---|---|---|
| 1 | <finding> | #N | prompt_gap | Added checklist item to sa{N}-*.md | Applied |
| 2 | <finding> | #N | no_skill_gap | — | Skipped (no gap) |
| 3 | <finding> | #N | prompt_ambiguity | Rewrote checklist item | Rejected by user |
```
