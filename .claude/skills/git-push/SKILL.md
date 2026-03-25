---
name: git-push
description: Review all unpushed code on the current branch using 7 parallel subagents (Safety & Security, Correctness, Simplicity & Conciseness, Test Coverage, Completeness & Cleanup, Consistency & Style, Integration Risk), then push if all approve or write findings to reviews/push-review-<branch>.md if any reject. After a successful push, create or update a GitHub PR using the GitHub App token. Use when asked to push, push code, git push, review-and-push, or create a PR.
---

# Git Push with Multi-Agent Review

Review all code not yet on the remote branch, then push if approved or output findings.

## Branch Guard

Before starting, check the current branch:
1. If on `main` or `master`:
   - Run `gmas` to ensure main is up to date
   - Suggest a branch name based on the task context (e.g., `refactor/splash-validation`, `fix/login-error`)
   - Ask the user: "You're on main. Want me to create and switch to `<suggested-branch>`?"
   - Do NOT proceed until the user confirms and you've switched branches
2. If already on a feature branch: proceed normally

## Workflow

### 1. Gather the Diff

Determine what code exists locally but not on the remote:

```bash
# Get branch name and remote tracking info
BRANCH=$(git branch --show-current)
git fetch origin

# Check if remote branch exists
if git rev-parse --verify origin/$BRANCH >/dev/null 2>&1; then
  # Diff against remote branch
  git diff origin/$BRANCH...HEAD
  git diff origin/$BRANCH...HEAD --stat
  git log origin/$BRANCH..HEAD --oneline
else
  # New branch — diff against main
  git diff origin/main...HEAD
  git diff origin/main...HEAD --stat
  git log origin/main..HEAD --oneline
fi

# Also include uncommitted staged/unstaged changes
git diff HEAD
git status --short
```

If the diff is empty (nothing to push), inform the user and stop.

### 2. Launch 7 Parallel Review Subagents

Read `references/subagent-prompts.md` for the full prompt definitions and expected response format.

Launch **all 7 subagents in parallel** using the Agent tool. Each subagent:
- Receives the full diff output from Step 1
- Receives its specific review focus area from the reference file
- Must return a structured JSON response with `verdict`, `findings`, and `summary`
- Uses `model: sonnet` for speed

Subagents (all launched in a single message):

| # | Name | Focus |
|---|---|---|
| 1 | Safety & Security | XSS, injection, secrets, OWASP, destructive ops |
| 2 | Correctness | Logic errors, edge cases, type issues, wrong APIs |
| 3 | Simplicity & Conciseness | Over-engineering, dead code, verbose patterns |
| 4 | Test Coverage | Missing tests, untested new behavior, coverage gaps |
| 5 | Completeness & Cleanup | Debug artifacts, TODOs, commented code, stubs |
| 6 | Consistency & Style | Project conventions, naming, patterns, imports |
| 7 | Integration Risk | Breaking changes, missing migrations, cross-module impact |

### 3. Evaluate Results

Collect all 7 subagent responses. Parse each verdict:

- **ALL PASS, no findings at all**: Proceed to Step 4 (push).
- **ALL PASS, but minor findings exist**: Write findings (Step 5), then push (Step 4). Minor findings should not block the push but must be recorded so `/next-step-taker` can address them.
- **ANY FAIL**: Proceed to Step 5 (write findings). Do NOT push.

### 4. Push

Push using the GitHub App token over HTTPS so the push is attributed to the bot, not your personal account. This is required for branch protection rules that block self-approval from the last pusher. The repo remote uses SSH, so we must push to an explicit HTTPS URL with the token embedded.

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh)
git push "https://x-access-token:$GH_TOKEN@github.com/4IRL/urls4irl.git" $BRANCH
```

After pushing, proceed to Step 6 (PR creation).

If a review file was written (minor findings), include its path and note that `/next-step-taker push-review-<branch>` can address them.

### 5. Write Findings

The review file is `reviews/push-review-<branch>.md` (one file per branch, no timestamp in filename).

#### File and Review Numbering

1. Check if `reviews/push-review-<branch>.md` already exists
2. **If it exists**: read the file, find the highest `## Review N` number, and append a new section numbered N+1
3. **If it does not exist**: create the file with a header and start with `## Review 1`

The file header (written only on first creation):
```markdown
# Push Review: <branch>
```

Each review section appended to the file:
```markdown
## Review <N>
Generated: <YYYY-MM-DD HH:MM>
Comparison: <base>...HEAD
Verdict: **BLOCKED** or **PUSHED WITH MINOR FINDINGS**

### Results by Reviewer

#### 1. Safety & Security — <PASS/FAIL>
<summary + findings bullet list>

#### 2. Correctness — <PASS/FAIL>
...

#### 3. Simplicity & Conciseness — <PASS/FAIL>
...

#### 4. Test Coverage — <PASS/FAIL>
...

#### 5. Completeness & Cleanup — <PASS/FAIL>
...

#### 6. Consistency & Style — <PASS/FAIL>
...

#### 7. Integration Risk — <PASS/FAIL>
...

### To-Do: Required Changes

- [ ] **<Imperative action>** — <file(s) to change> — <what to do specifically>
- [ ] ...
```

#### TO-DO Item Guidelines

Each TO-DO item must be:
- **Self-contained**: Include the file path(s), what to change, and why. The implementer should not need to read the reviewer results above.
- **Imperative**: Start with a verb (Add, Update, Extract, Fix, Remove, Replace).
- **Concrete**: Name the exact file, function, variable, or line to change. Avoid vague items like "fix style issues."
- **One logical change**: Each item should be implementable and verifiable independently.

Consolidate related findings from different reviewers into a single TO-DO item when they refer to the same fix. **Include all findings in the TO-DO list regardless of severity** — minor findings must also be actionable items so `/next-step-taker` can address them.

Example:
```markdown
### To-Do: Required Changes

- [ ] **Extract `_register_json` to shared helper** — `tests/integration/splash/test_email_validation.py`, `tests/integration/splash/test_register_user.py` — Move the duplicated `_register_json()` function to `tests/integration/splash/conftest.py` and import from there in both test files
- [ ] **Add `ForgotPasswordErrorCodes` enum** — `backend/splash/constants.py`, `backend/splash/routes.py` — Create `ForgotPasswordErrorCodes(IntEnum)` with `INVALID_FORM_INPUT = 1` and use it in the `@parse_json_body` decorator call for the forgot-password route instead of bare `error_code=1`
```

After writing, inform the user:
- Which reviewers failed and why (brief)
- Path to the full review file and review number (e.g., "Review 2 appended")
- That they can use `/next-step-taker push-review-<branch>` to implement items one by one
- Do NOT automatically push — the user must fix findings and re-invoke

### 6. Create or Update PR

After a successful push, create or update a PR targeting `main`.

#### Environment Requirements

All `gh` commands must:
1. Be prefixed with the GitHub App token: `GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh)`
2. Use `dangerouslyDisableSandbox: true` — the sandbox blocks TLS connections to `api.github.com`

```bash
# Example (always run with dangerouslyDisableSandbox: true)
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr ...
```

#### Check for Existing PR

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr view $BRANCH 2>&1
```

- **If a PR exists**: use `gh pr edit` to update title/body if the changes warrant it.
- **If no PR exists**: create one with `gh pr create`.

#### PR Title Format

```
[SUBJECT] Title content
```

Where `SUBJECT` is one of:
- `refactor` — code restructuring without behavior change
- `frontend` — UI/JS/CSS changes
- `backend` — Python/Flask/API changes
- `database` — migrations, model changes
- `tests` — test-only changes

Use the most dominant category. If changes span multiple areas, pick the primary one.

#### PR Body Format

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr create \
  --base main \
  --head "$BRANCH" \
  --title "[SUBJECT] Title" \
  --body "$(cat <<'EOF'
# Summary

Brief overview of what this PR does.

## Problem

What issue or need motivated this change.

## Solutions

What was done to address the problem. Reference key files/functions changed.

## Verification Steps

- Tests added/modified and their markers
- How to manually verify (if applicable)
- Build verification status
EOF
)"
```

#### Apply Labels

After creating or updating the PR, apply labels based on **all changes on the branch** (the full `origin/main...HEAD` diff, not just the latest push). Add **all labels that apply** — multiple labels are expected when changes span areas.

Available labels and when to apply:

| Label | Apply when the diff touches… |
|---|---|
| `backend` | Python code under `backend/` (routes, models, schemas, utils) |
| `frontend` | JavaScript, HTML templates, CSS, or Vite config |
| `database` | Migrations, model column changes, or `flask db` commands |
| `testing` | Test files (`tests/`) or test infrastructure |
| `Infrastructure` | Docker, CI/CD, Makefile, `.github/`, or deployment config |
| `desktop` | Desktop-specific UI code or desktop UI tests |
| `mobile` | Mobile-specific UI code or mobile UI tests |
| `bug` | The change fixes a bug (use commit message/PR context to determine) |
| `enhancement` | The change adds new functionality |
| `documentation` | README, CLAUDE.md, ARCHITECTURE.md, or doc-only changes |

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr edit <PR_NUMBER> --add-label "label1,label2,..."
```

#### Set Milestone

After applying labels, set the appropriate milestone based on the nature and motivation behind **all changes on the branch** (not just the latest push). Choose **one** milestone:

| Milestone | When to use |
|---|---|
| `Bugs` | The PR fixes a bug or corrects broken behavior |
| `Maintenance` | Bug fixes, dependency updates, CI/CD changes, minor cleanup — small fixes that keep things running |
| `MVP v2` | New features, enhancements, refactors, and architectural improvements (e.g., new functionality, migrating to Pydantic, restructuring code) |
| `REH-ch goals` | Stretch/reach goals beyond MVP v2 |

Use the commit messages, branch name, and PR context to determine the best fit. Refactors and code modernization efforts are `MVP v2`, not `Maintenance`.

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr edit <PR_NUMBER> --milestone "<milestone title>"
```

#### Add to Project

After setting the milestone, add the PR to the **"URLS4IRL -> Real Life"** org project (project ID: `PVT_kwDOCEIbTM4Ai9RV`).

First, get the PR's node ID:

```bash
PR_NODE_ID=$(GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh api graphql -f query='{ repository(owner: "4IRL", name: "urls4irl") { pullRequest(number: <PR_NUMBER>) { id } } }' --jq '.data.repository.pullRequest.id')
```

Then add it to the project and capture the item ID:

```bash
PROJECT_ITEM_ID=$(GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh api graphql -f query="mutation { addProjectV2ItemById(input: { projectId: \"PVT_kwDOCEIbTM4Ai9RV\", contentId: \"$PR_NODE_ID\" }) { item { id } } }" --jq '.data.addProjectV2ItemById.item.id')
```

Then set the **Status** field to **"In progress"** (field ID: `PVTSSF_lADOCEIbTM4Ai9RVzgbZQoU`, option ID: `42a2e094`):

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh api graphql -f query="mutation { updateProjectV2ItemFieldValue(input: { projectId: \"PVT_kwDOCEIbTM4Ai9RV\", itemId: \"$PROJECT_ITEM_ID\", fieldId: \"PVTSSF_lADOCEIbTM4Ai9RVzgbZQoU\", value: { singleSelectOptionId: \"42a2e094\" } }) { projectV2Item { id } } }"
```

This is idempotent — safe to run on PRs already in the project.

#### Assign and Request Review

After adding to the project, assign the GitHub App as assignee via GraphQL (bot accounts can't be assigned via `gh pr edit --add-assignee`), then request review from `GPropersi`.

Assign the bot (node ID: `BOT_kgDOCHBJTA`) using the PR node ID obtained earlier:

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh api graphql -f query='mutation { addAssigneesToAssignable(input: { assignableId: "'"$PR_NODE_ID"'", assigneeIds: ["BOT_kgDOCHBJTA"] }) { assignable { ... on PullRequest { number } } } }'
```

Then request review:

```bash
GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) gh pr edit <PR_NUMBER> --add-reviewer GPropersi
```

#### After PR Creation

Output:
- The PR URL
- Branch name and number of commits
- One-line summary from each review subagent

## Important Notes

- **All test suites have passed before commit** — code reaching this workflow has already passed all relevant test suites (integration, UI, unit, JS). Subagents should NOT flag "tests might fail" or "untested at runtime." The Test Coverage reviewer focuses on whether the diff includes sufficient test code for new/changed behavior, not whether existing tests pass.
- Never push to `main` or `master` — warn the user and abort
- Never force-push
- If there are uncommitted changes, warn the user and ask whether to include them (commit first) or push only committed code
- The `reviews/` directory is at the project root, NOT under `plans/`
- All subagent launches must be in a single message for true parallelism
- If a subagent fails to return valid JSON, treat it as FAIL with a note about the parse error
