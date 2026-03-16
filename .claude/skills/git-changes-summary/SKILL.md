---
name: git-changes-summary
description: Summarize all git changes on the current branch compared to main, including staged/unstaged changes, committed changes, and commit history. Use when asked to "summarize my changes", "what has been changed", "what are the current changes", "what's on this branch", or when returning to the codebase after a break and needing an overview of all branch work.
---

# Git Changes Summary

This skill analyzes ALL changes on the current branch (vs `main`) plus any uncommitted changes, and generates a comprehensive markdown report.

## Workflow

1. **Determine branch context**
   ```bash
   git branch --show-current
   git log main..HEAD --oneline
   ```

2. **Gather all changes**
   ```bash
   # All commits on this branch vs main
   git log main..HEAD --oneline

   # Full diff of everything on this branch vs main (includes uncommitted)
   git diff main...HEAD --stat
   git diff main...HEAD

   # Any uncommitted changes on top of that
   git status --short
   git diff HEAD --stat
   git diff HEAD
   ```

3. **Analyze the changes** by examining:
   - Files added (A), modified (M), deleted (D), renamed (R)
   - Line changes per file
   - Code patterns (imports, functions, classes, tests, configs)
   - Affected areas (frontend/, backend/, tests/, docs/, configs/)

4. **Detect patterns** to categorize the work:
   - **New Feature**: New files, new functions/classes, new tests
   - **Bug Fix**: Changes to existing logic with test updates
   - **Refactoring**: Code reorganization without behavior changes
   - **Testing**: Primarily test file changes
   - **Configuration**: Build configs, dependencies, env vars
   - **Mixed**: Multiple types of changes

5. **Identify affected areas**:
   - Frontend (JS/HTML/CSS files)
   - Backend (Python/Flask files)
   - Tests (test files)
   - Build/Config (docker, package.json, requirements.txt, etc.)

6. **Generate markdown report** and save to `/Users/ggpropersi/code/urls4irl/tmp/git-changes-summary-{timestamp}.md`

## Report Format

```markdown
# Git Changes Summary — {branch-name}
Generated: {timestamp}

## Overview
- **Branch**: {branch-name} ({N} commits ahead of main)
- **Files changed**: X modified, Y added, Z deleted
- **Total changes**: +XXX lines, -YYY lines
- **Change type**: {Primary pattern detected}
- **Affected areas**: {List of areas}

## Commits on This Branch
- `{sha}` {commit message}
- `{sha}` {commit message}
...

## Files Changed (vs main)

### Added
- path/to/file1.js (+XX lines)

### Modified
- path/to/file3.js (+XX -YY lines)
  - Brief description of changes

### Deleted
- path/to/old_file.js

## Uncommitted Changes
{Either "None" or a brief summary of staged/unstaged work}

## Change Analysis

### Pattern Detection
{Description of what type of work this represents}

### Affected Areas
- **Frontend**: {Brief summary or N/A}
- **Backend**: {Brief summary or N/A}
- **Tests**: {Brief summary or N/A}
- **Config**: {Brief summary or N/A}

### Key Changes
- {Most significant change 1}
- {Most significant change 2}
- {Most significant change 3}

## GitHub PR Summary

### Problem
{2–4 sentences. Describe the specific gap, bug, or limitation that motivated this branch. Include:
- What was missing or broken before this change
- Why it matters (user impact, technical debt, correctness, etc.)
- Any relevant context (e.g., prior refactor that made this possible, external requirement, etc.)}

### Solution
{2–4 sentences. Describe the approach taken and why it was chosen. Include:
- The core mechanism or pattern introduced (e.g., "replaced WTForms with Pydantic schemas for request validation")
- Key design decisions and trade-offs considered
- How the solution addresses each aspect of the problem above}

### Key Changes
- {Most impactful change, e.g., "Added `parse_request.py` to centralize Pydantic-based request parsing across all blueprints"}
- {Second change}
- {Third change, etc.}

### Tests
All relevant test suites were run locally and passed:
- {e.g., `make test-marker-parallel m=unit`}
- {e.g., `make test-marker-parallel m=utubs`}
- {e.g., `make test-marker-parallel m=urls`}
- {Add all markers tested, or note "Full integration suite: `make test-integration-parallel`"}

---
*Covers all changes on {branch-name} vs main, as of {timestamp}*
```

## Important Notes

- Always diff against `main` (use `git diff main...HEAD`) to capture the full branch scope
- Include both committed and uncommitted changes in the report
- Focus on WHAT changed and WHY it matters, not line-by-line details
- Save the report to `/Users/ggpropersi/code/urls4irl/tmp/` with timestamp
- After generating the report, inform the user of the file location
