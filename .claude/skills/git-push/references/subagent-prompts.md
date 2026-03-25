# Subagent Review Prompts

Each subagent receives the diff output and a focused review prompt. All subagents must return a structured JSON response.

## Response Format (all subagents)

```json
{
  "verdict": "PASS" | "FAIL",
  "findings": [
    {
      "severity": "critical" | "major" | "minor",
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
