---
name: gmas
description: Run the `gmas` workflow — checkout main, pull, fetch -p, and interactively clean up stale local branches. Use when the user says "run gmas", "/gmas", "update main and clean branches", "clean up stale branches", or similar. Presents the candidate list as a multiSelect AskUserQuestion so the user picks which branches to delete (not all-or-nothing).
---

# gmas — Update main and clean orphaned local branches

Mirrors the user's `gmas` shell alias (`git checkout main; git pull origin main; git fetch -p; git cleanup`) but routes the cleanup confirmation through `AskUserQuestion` so the user picks individual branches to delete instead of a single blanket yes/no.

## Workflow

### 1. Pre-flight safety

Run `git status --porcelain`. If output is non-empty, stop and use `AskUserQuestion` to offer:

- Commit changes first (delegate to `/git-commit`)
- Stash changes (`git stash push -u -m "gmas pre-flight"`)
- Abort

Do NOT silently stash, reset, or force-checkout.

### 2. Refresh main

Run as separate Bash calls, in this order:

```
git fetch -p                            # in-sandbox — prunes + updates origin/main
git diff --name-only HEAD origin/main   # in-sandbox — read-only; lists the working-tree delta
git checkout main                       # in-sandbox by default; DDS only if protected-path hit (see below)
git pull origin main                    # in-sandbox by default; DDS only if protected-path hit (see below)
```

**Why the diff gate.** The sandbox writes git internals (`.git/objects`, `.git/refs`) fine — `git fetch` and `git pull` of ordinary code changes run in-sandbox with no prompt. The sandbox only denies a narrow set of **working-tree paths**: `.claude/settings.json`, `.claude/settings.local.json`, `.claude/hooks/**`, `.claude/skills/**`, `.mcp.json` (plus `.git/config`). A checkout/pull that rewrites one of those partially fails and **tears the working tree** (HEAD moves but blocked files keep old content → phantom "local changes" on every later git command). `dangerouslyDisableSandbox: true` swaps the tree atomically, but it forces a per-call confirmation that can't be allowlisted — so apply it **only when actually needed**.

**Decision rule** (after the `git diff --name-only HEAD origin/main`):
- If any line matches `.claude/settings.json`, `.claude/settings.local.json`, `.claude/hooks/`, `.claude/skills/`, or `.mcp.json` → run **both** `git checkout main` and `git pull origin main` with `dangerouslyDisableSandbox: true` (the incoming update touches a sandbox-protected path; the one confirmation is warranted — a human should glance at a hooks/skills/settings change anyway).
- Otherwise → run both **in-sandbox** (no DDS). `git checkout` is allowlisted; `git pull origin main` is allowlisted via `Bash(git pull origin main:*)`, so neither prompts.

The `git diff HEAD origin/main` captures the full delta from the current branch to the target, covering both the checkout and the fast-forward pull in one check.

**Fallback.** If an in-sandbox `git checkout`/`git pull` unexpectedly fails with `Operation not permitted` (a protected path the glob list missed), retry that single command with `dangerouslyDisableSandbox: true`, then continue.

If `git pull` reports a non-fast-forward, merge conflict, or other error, surface it verbatim and stop. Do not attempt to resolve automatically.

### 3. Preview cleanup candidates

Run:

```
echo n | git cleanup
```

This invokes the alias with `n` piped to its confirmation prompt, so the candidate list is printed but nothing is deleted. Parse the lines between `Will delete:` and `Proceed?` — each candidate is a single branch name indented by two spaces.

If the output is `No branches to clean up.`, report that and stop.

### 4. Let the user pick which branches to delete

Use **`AskUserQuestion` with `multiSelect: true`**. Each option's label is the branch name; the description is a short reason — e.g. `"no upstream + missing on origin"` (orphan) or `"upstream pruned (: gone])"` (classic gone branch). Determine each branch's reason by checking whether `git for-each-ref --format='%(upstream)' refs/heads/<branch>` returns an upstream — empty means orphan, non-empty means gone.

**Batching rules (AskUserQuestion caps: 4 options per question, 4 questions per call → 16 candidates per call):**

- **1–4 candidates:** one question, one option per branch.
- **5–16 candidates:** multiple questions in a single call (up to 4 questions × 4 options each). Group sensibly — e.g., one question per "reason" category if that makes the choice clearer.
- **17+ candidates:** sequential `AskUserQuestion` calls, 16 at a time.

For each question, phrase like `"Delete these stale branches?"` with multiSelect on. The user checks the ones to delete; unchecked branches stay.

### 5. Delete selected branches

Run a single in-sandbox Bash call:

```
git branch -D <selected1> <selected2> ...
```

Skip any branches the user did not check.

### 6. Report

One-line summary:

- `Deleted N branches: foo, bar, baz. Kept M: qux.`
- Or `No branches deleted.` if the user checked nothing.

## Notes

- The `git cleanup` alias lives in `~/.gitconfig` and excludes `main` by design.
- Never pipe `y` directly into `git cleanup` — always go through `AskUserQuestion`. The pipe is only for preview (`n`).
- `git checkout main` and `git pull origin main` (Step 2) run **in-sandbox by default** — git internals (`.git/objects`, `.git/refs`) are sandbox-writable. They escalate to `dangerouslyDisableSandbox: true` **only** when the `git diff --name-only HEAD origin/main` check shows the incoming update modifies a sandbox-protected working-tree path (`.claude/settings*.json`, `.claude/hooks/**`, `.claude/skills/**`, `.mcp.json`), which would otherwise tear the tree. `git branch -D` (Step 5) may print a `could not write config file .git/config: Operation not permitted` warning under sandbox — the branch is still deleted, so it's harmless; no DDS needed. All other steps run in-sandbox.
- Branches with unique commits not on main are force-deleted via `-D` — acceptable because the user has explicitly opted in per branch.
