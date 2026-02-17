---
name: git-changes-summary
description: Summarize all git changes (staged and unstaged) in the working directory with pattern detection, affected areas analysis, and commit message suggestions. Use when asked to "summarize my changes", "what has been changed", "what are the current changes", or when returning to the codebase after a break and needing an overview of uncommitted work.
---

# Git Changes Summary

This skill analyzes all uncommitted changes (both staged and unstaged) and generates a comprehensive markdown report.

## Workflow

1. **Gather git information**
   ```bash
   git status --short
   git diff HEAD --stat
   git diff HEAD
   ```

2. **Analyze the changes** by examining:
   - Files added (A), modified (M), deleted (D), renamed (R)
   - Line changes per file
   - Code patterns (imports, functions, classes, tests, configs)
   - Affected areas (frontend/, backend/, tests/, docs/, configs/)

3. **Detect patterns** to categorize the work:
   - **New Feature**: New files, new functions/classes, new tests
   - **Bug Fix**: Changes to existing logic with test updates
   - **Refactoring**: Code reorganization without behavior changes
   - **Testing**: Primarily test file changes
   - **Documentation**: README, docs, comments
   - **Configuration**: Build configs, dependencies, env vars
   - **Mixed**: Multiple types of changes

4. **Identify affected areas**:
   - Frontend (JS/HTML/CSS files)
   - Backend (Python/Flask files)
   - Tests (test files)
   - Build/Config (docker, package.json, requirements.txt, etc.)
   - Documentation (README, docs, comments)

5. **Suggest commit message** following conventional commits format:
   - Type: feat, fix, refactor, test, docs, chore, style
   - Scope: affected component/module
   - Description: concise summary in imperative mood
   - Example: `feat(frontend): add error handling for URL validation`

6. **Generate markdown report** and save to `/tmp/git-changes-summary-{timestamp}.md`

## Report Format

```markdown
# Git Changes Summary
Generated: {timestamp}

## Overview
- **Files changed**: X modified, Y added, Z deleted
- **Total changes**: +XXX lines, -YYY lines
- **Change type**: {Primary pattern detected}
- **Affected areas**: {List of areas}

## Files Changed

### Added
- path/to/file1.js (+XX lines)
- path/to/file2.py (+YY lines)

### Modified
- path/to/file3.js (+XX -YY lines)
  - Brief description of changes
- path/to/file4.py (+XX -YY lines)
  - Brief description of changes

### Deleted
- path/to/old_file.js

## Change Analysis

### Pattern Detection
{Description of what type of work this represents}

### Affected Areas
- **Frontend**: {Brief summary}
- **Backend**: {Brief summary}
- **Tests**: {Brief summary}
- **Config**: {Brief summary}

### Key Changes
- {Most significant change 1}
- {Most significant change 2}
- {Most significant change 3}

## Suggested Commit Message

```
{type}({scope}): {description}

{optional body with more details}
```

---
*This summary represents all uncommitted changes (staged + unstaged) as of {timestamp}*
```

## Important Notes

- Always combine staged AND unstaged changes using `git diff HEAD`
- Focus on WHAT changed and WHY it matters, not line-by-line details
- Keep the summary concise but informative
- Pattern detection should be based on actual code analysis, not just file counts
- Save the report to `/Users/ggpropersi/code/urls4irl/tmp/` with timestamp
- After generating the report, inform the user of the file location
