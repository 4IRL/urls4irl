---
name: git-commit
description: Stage and commit changes to git in one workflow with automatic pre-commit hook handling. Use when the user asks to commit changes, create a commit, save work to git, or similar git commit requests. Automatically generates commit messages and handles pre-commit failures by fixing linting/formatting errors.
---

# Git Add and Commit

Streamline git commits by staging files, generating commit messages, and handling pre-commit hook failures automatically.

## Workflow

### 1. Stage Files

**Default**: Stage all changes
```bash
git add .
```

**Specific files**: If user specifies files or folders to exclude, stage only the desired files:
```bash
git add <specific-files>
```

### 2. Analyze Changes and Generate Commit Message

Before committing, run these commands in parallel to understand the changes:

```bash
git status
git diff --staged
git log -3 --oneline  # See recent commit message style
```

Analyze the staged changes to craft a concise commit message (1-2 sentences) that:
- Summarizes the nature of changes (feature, fix, refactor, docs, test, etc.)
- Focuses on "why" rather than "what"
- Follows the repository's existing commit message style
- Uses appropriate prefix (add/update/fix/refactor/etc.) based on actual changes

### 3. Create Commit

Use a HEREDOC for proper formatting:

```bash
git commit -m "$(cat <<'EOF'
Your commit message here.
EOF
)"
```

- Do NOT include any kind of attribution or `Co-Authored-By` statements in the git commit message.
- Keep the git commit to a single line

### 4. Handle Pre-Commit Failures

If the commit fails due to pre-commit hooks:

1. **Identify the errors** - Read the pre-commit output to understand what failed (linting, formatting, etc.)

2. **Fix menial errors** - Automatically fix:
   - Code formatting issues (black, prettier, etc.)
   - Linting errors (flake8, eslint, etc.)
   - Import sorting
   - Trailing whitespace
   - Other style/formatting issues

3. **Do NOT fix** if changes would:
   - Alter business logic
   - Break functionality
   - Require architectural decisions
   - Need user input to resolve correctly

4. **Re-stage and commit** - After fixing errors:
   ```bash
   git add .
   git commit -m "$(cat <<'EOF'
   Your original commit message here.
   EOF
   )"
   ```

5. **Report to user** - Summarize what was fixed and complete the commit

## Important Notes

- Never use `--no-verify` to bypass pre-commit hooks unless explicitly requested
- If pre-commit failures require non-menial changes, report to user and ask for guidance
- Verify commit success with `git status` after completion
