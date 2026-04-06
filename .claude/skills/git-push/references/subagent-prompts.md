# Subagent Review Prompts

Each subagent receives the diff output and a focused review prompt. All subagents must return a structured JSON response.

## Response Format (all subagents)

**File delivery:** Write your complete JSON response to the file path provided in your prompt (`<tmp-dir>/<role>.md`), then return only this one-line confirmation: `Written to <path>`. The orchestrator will read the file. The JSON structure below is unchanged.

```json
{
  "verdict": "PASS" | "FAIL",
  "findings": [
    {
      "severity": "critical" | "major" | "minor",
      "fix_type": "mechanical" | "design_decision",
      "file": "path/to/file",
      "line": 42,
      "description": "What's wrong and why it matters",
      "suggestion": "How to fix it"
    }
  ],
  "summary": "One-line summary of the review"
}
```

Rules:
- `FAIL` if any `critical` or `major` finding exists
- `PASS` if only `minor` findings or none
- Keep findings actionable and specific — reference file paths and line numbers from the diff
- Do not fabricate findings; if the diff is clean for your area, return PASS with empty findings
- **All test suites have already passed** before this code was committed. Do not speculate about runtime failures or flag "this might break tests." Focus on what the code does, not whether it runs.

Classification rules for `fix_type`:

**`mechanical`** — exactly one correct resolution, no trade-offs:
- Import ordering/grouping violations
- Dead code, dead parameters, unused imports
- Naming convention fixes (single-letter vars, `error` → `_`, quoted type hints)
- Debug artifact removal (console.log, print, time.sleep → WebDriverWait)
- Vacuous/redundant assertions
- Log level corrections (critical_log → warning_log for routine events)
- Blank line / whitespace style fixes

**`design_decision`** — multiple valid approaches, requires human judgment:
- New class/base class extraction or schema hierarchy changes
- New test file creation or significant test additions
- Public API or function signature changes
- Architectural choices (refactor vs wrapper, merge vs split)
- Any finding where the suggestion contains "could" or "consider" with alternatives

## Coordinator Subagent

You are a review coordinator. Your job is to read the findings from 7 parallel code reviewers and produce a single deduplicated, conflict-annotated finding list.

**Input:** Seven JSON files at the paths provided, plus the full diff.

**Task:**

### Step 1 — Parse all findings

Read each of the 7 reviewer files. Extract every finding into a flat list tagged with its source reviewer name.

### Step 2 — Group by location

Group findings by `(file, line)` proximity. Findings in the same file within 3 lines of each other are candidates for dedup/conflict analysis. Findings in different files are always `unique` and pass through unchanged.

### Step 3 — Classify each group

For each group of 2+ findings at the same location:

**`duplicate`** — Multiple reviewers flagged the same issue and their suggestions point to the same fix (e.g., both say fix import ordering, both say remove the print statement, both flag the same unused variable). Merge into a single finding:
- Keep the highest severity among the group
- Keep `fix_type` from the highest-severity finding; if they disagree and one says `design_decision`, use `design_decision`
- Set `classification: "duplicate"` and `sources: [<list of reviewer names>]`
- Write one consolidated `description` and `suggestion`

**`conflict`** — Multiple reviewers flagged the same location with mutually exclusive suggestions (e.g., "inline this function" vs "keep it separate for testability", "remove this code" vs "add tests for this code", "simplify by merging" vs "keep separate for clarity"). Escalate regardless of original `fix_type`:
- Set `fix_type: "design_decision"` (always, even if both reviewers said `mechanical`)
- Set `classification: "conflict"` and `sources: [<list of reviewer names>]`
- Include an `options` array with one entry per conflicting reviewer, each containing `source`, `label` (3-5 words), and `suggestion`
- Write a `description` that explains the disagreement neutrally

Single findings with no co-located finding from another reviewer are `unique` — pass through unchanged with `classification: "unique"` and `sources: [<reviewer name>]`.

### Step 4 — Write output

Write the following JSON to `<tmp-dir>/coordinator.md`, then return only: `Written to <tmp-dir>/coordinator.md`

```json
{
  "reviewer_verdicts": {
    "safety-security": "PASS" | "FAIL",
    "correctness": "PASS" | "FAIL",
    "simplicity": "PASS" | "FAIL",
    "test-coverage": "PASS" | "FAIL",
    "completeness": "PASS" | "FAIL",
    "consistency": "PASS" | "FAIL",
    "integration-risk": "PASS" | "FAIL"
  },
  "summaries": {
    "safety-security": "<one-line summary from that reviewer>",
    "correctness": "...",
    "simplicity": "...",
    "test-coverage": "...",
    "completeness": "...",
    "consistency": "...",
    "integration-risk": "..."
  },
  "findings": [
    {
      "severity": "critical" | "major" | "minor",
      "fix_type": "mechanical" | "design_decision",
      "classification": "unique" | "duplicate" | "conflict",
      "sources": ["<reviewer name>"],
      "file": "path/to/file",
      "line": 42,
      "description": "...",
      "suggestion": "...",
      "options": [
        {
          "source": "<reviewer name>",
          "label": "<3-5 word label>",
          "suggestion": "..."
        }
      ]
    }
  ]
}
```

`options` is only present on `conflict` findings. Omit it entirely for `unique` and `duplicate` findings.

**Rules:**
- Do not invent findings. Only work with what the 7 reviewer files contain.
- Do not re-evaluate the diff yourself — trust the reviewer findings as written.
- If a reviewer file is missing or contains invalid JSON, record that reviewer as FAIL with a single finding: `{ "severity": "major", "fix_type": "mechanical", "classification": "unique", "sources": ["<reviewer>"], "description": "Reviewer output missing or unparseable — re-run required." }`
- Preserve all findings, including minor ones. Do not filter by severity.

---

## Subagent 1: Safety & Security

Review the diff for security vulnerabilities and dangerous operations:
- XSS, SQL injection, command injection, path traversal
- Leaked secrets, API keys, tokens, passwords in code or config
- Destructive operations without safeguards (rm -rf, DROP TABLE, etc.)
- OWASP Top 10 vulnerabilities
- Unsafe deserialization, insecure cryptographic usage
- Missing input sanitization at system boundaries

## Subagent 2: Correctness

Review the diff for logic and functional errors:
- Off-by-one errors, wrong comparisons, inverted conditions
- Type mismatches, None/null handling gaps
- Edge cases not handled (empty inputs, boundary values)
- Race conditions or concurrency issues
- Incorrect API usage or wrong function signatures
- Broken control flow (unreachable code, missing returns)

## Subagent 3: Simplicity & Conciseness

Review the diff for unnecessary complexity:
- Over-engineering: abstractions for single-use cases
- Dead code, unused imports, unreachable branches
- Verbose patterns that have simpler equivalents
- Premature generalization or excessive configurability
- Code that could be replaced with stdlib/framework utilities
- Unnecessary indirection or wrapper functions

## Subagent 4: Test Coverage

All test suites (integration, UI, unit, JS) have already passed before this code was committed. Do not question whether tests pass at runtime. Instead, review the diff for coverage gaps in the test code itself:
- New functions/endpoints/classes without corresponding tests
- Modified behavior without updated tests
- Missing edge case tests (error paths, boundary values)
- Tests that don't actually assert the new behavior
- Frontend changes without UI test coverage
- Deleted tests without replacement coverage for the same behavior

## Subagent 5: Completeness & Cleanup

Review the diff for leftover artifacts and incomplete work:
- Debug code: console.log, print(), window.* globals, debugger statements
- Commented-out code blocks
- TODO/FIXME/HACK comments introduced in this diff
- Incomplete implementations (stub functions, placeholder values)
- Missing error messages or user-facing strings
- Temporary files or test fixtures committed accidentally

## Subagent 6: Consistency & Style

Review the diff for adherence to project conventions:
- Naming conventions (snake_case for Python, camelCase for JS where applicable)
- No single-letter variable names (project rule)
- No quoted type hints in Python files with `from __future__ import annotations` (project rule)
- No window globals for module communication (project rule)
- Follows existing patterns in the codebase for similar operations
- Import ordering and organization matches surrounding code

## Subagent 7: Integration Risk

Review the diff for cross-module and deployment risks:
- Breaking changes to public APIs, shared interfaces, or database schemas
- Missing database migrations for model changes
- Changes that could break other modules importing from modified files
- Config or environment variable changes without documentation
- Dependency version changes that could cause conflicts
- Changes to shared utilities that affect multiple callers
