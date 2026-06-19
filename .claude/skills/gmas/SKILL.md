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
git diff --name-only HEAD main          # in-sandbox — read-only; the CHECKOUT leg (HEAD → local main)
git diff --name-only main origin/main   # in-sandbox — read-only; the PULL leg (local main → origin/main)
git checkout main                       # in-sandbox by default; DDS only if protected-path hit (see below)
git pull origin main                    # in-sandbox by default; DDS only if protected-path hit (see below)
```

**Why the diff gate.** The sandbox writes git internals (`.git/objects`, `.git/refs`) fine — `git fetch` and `git pull` of ordinary code changes run in-sandbox with no prompt. The sandbox only denies a narrow set of **working-tree paths**: `.claude/settings.json`, `.claude/settings.local.json`, `.claude/hooks/**`, `.claude/skills/**`, `.mcp.json` (plus `.git/config`). A checkout/pull that rewrites one of those partially fails and **tears the working tree** (HEAD moves but blocked files keep old content → phantom "local changes" on every later git command). `dangerouslyDisableSandbox: true` swaps the tree atomically, but it forces a per-call confirmation that can't be allowlisted — so apply it **only when actually needed**.

**Check both legs separately — never the net `HEAD…origin/main` diff.** The two commands rewrite the working tree in two distinct hops, and the net endpoint diff can hide a protected-path write that the intermediate hop performs:
- `git checkout main` rewrites every file that differs between **HEAD and local `main`** → its risk is `git diff --name-only HEAD main`.
- `git pull origin main` (fast-forward) rewrites every file that differs between **local `main` and `origin/main`** → its risk is `git diff --name-only main origin/main`.

A single `HEAD…origin/main` diff compares only the endpoints, which **cancel out** in the common squash-merge case: you're on a just-merged feature branch whose tree already holds the new `.claude/**` content (you authored it there), local `main` is stale with the *old* content, and `origin/main` has the new content. Then `HEAD` and `origin/main` match (empty diff → guard says "in-sandbox"), but `checkout` still reverts the protected files HEAD(new) → main(old) — a blocked write that tears the tree. Checking the checkout leg (`HEAD vs main`) catches this; the endpoint diff does not.

**Decision rule** (after the two leg diffs):
- If **either** diff has any line matching `.claude/settings.json`, `.claude/settings.local.json`, `.claude/hooks/`, `.claude/skills/`, or `.mcp.json` → run **both** `git checkout main` and `git pull origin main` with `dangerouslyDisableSandbox: true` (a sandbox-protected path is rewritten by at least one leg; the one confirmation is warranted — a human should glance at a hooks/skills/settings change anyway).
- Otherwise → run both **in-sandbox** (no DDS). `git checkout` is allowlisted; `git pull origin main` is allowlisted via `Bash(git pull origin main:*)`, so neither prompts.

**Fallback.** If an in-sandbox `git checkout`/`git pull` unexpectedly fails with `Operation not permitted` (a protected path the glob list missed), retry that single command with `dangerouslyDisableSandbox: true`, then continue. **If the tree is already torn** — `git checkout` printed `unable to unlink old '<protected path>'` but still reported `Switched to branch 'main'`, so HEAD moved while the protected files kept old content — a plain retry won't recover: the protected files now read as phantom local changes and the follow-up `git pull` aborts with `Your local changes ... would be overwritten`. Since those changes are already merged into `origin/main`, recover by atomically resyncing: `git reset --hard origin/main` with `dangerouslyDisableSandbox: true`. This is lossless **only** when the working tree was clean at Step 1 (gmas guarantees this) and the only "modifications" are the merged protected files — verify with `git status --porcelain` showing nothing but those paths before resetting.

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
- `git checkout main` and `git pull origin main` (Step 2) run **in-sandbox by default** — git internals (`.git/objects`, `.git/refs`) are sandbox-writable. They escalate to `dangerouslyDisableSandbox: true` **only** when **either** leg diff — `git diff --name-only HEAD main` (checkout) or `git diff --name-only main origin/main` (pull) — shows a sandbox-protected working-tree path (`.claude/settings*.json`, `.claude/hooks/**`, `.claude/skills/**`, `.mcp.json`) being rewritten, which would otherwise tear the tree. **Do not use the net `HEAD…origin/main` diff** — it cancels out the protected-path write that the checkout leg performs when you're on a just-merged branch that carried `.claude/**` changes (the exact case that tears the tree). `git branch -D` (Step 5) may print a `could not write config file .git/config: Operation not permitted` warning under sandbox — the branch is still deleted, so it's harmless; no DDS needed. All other steps run in-sandbox.
- Branches with unique commits not on main are force-deleted via `-D` — acceptable because the user has explicitly opted in per branch.
