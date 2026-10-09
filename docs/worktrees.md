# Worktrees

urls4irl supports running several checkouts side by side as git worktrees under
`.claude/worktrees/<slug>`. Each worktree is its own compose project (a "spoke", `u4i-<slug>`) with its
own host ports, volumes, session cookie and dev database, while every spoke shares one per-user hub
(Postgres cluster and Playwright browser server). The tooling is standalone (no stronghold needed):
`make worktree-new` and `make worktree-rm`.

## Primary clone first

Set up the primary clone (`urls4irl/`) first. It needs a real `.env`: copy `.env.example` and fill it.
`make worktree-init` (run by `make setup`, `up`, `up-built`, `start-built` and `tunnel`) links `.env` and
`secrets/` from the primary into every worktree and never overwrites a real file already there. The hub
always reads the primary's `.env` and capacity file, whichever checkout runs it.

## Create

Run from the primary clone:

```sh
make worktree-new name=<slug> [b=<branch>] [from=<ref>]
```

- `name` is the worktree directory slug (lowercased, non `[a-z0-9-]` characters become `-`, leading `-`
  stripped, cut at 40 characters, trailing `-` stripped). `b` defaults to the slug; when both are given
  they must normalize to the same slug.
- A new branch is cut from `origin/<default branch>` (resolved from `origin/HEAD`, falling back to
  `origin/main`) unless `from=<ref>` says otherwise. Use `from=<ref>` to cut from an unmerged branch:
  the default base does not contain commits that have not reached `origin/main`. Do not use `base=`:
  that is the affected-markers knob (`make test-affected`), not a worktree option. `from` must be a
  valid commit ref and must not start with `-`. If the branch already exists locally or at
  `origin/<branch>`, it is checked out instead and `from=` is ignored with a warning.
- It needs docker running and the primary's `.env`, and refuses early (creating nothing) without
  either. With the hub running, it also refuses a name whose dev DB `u4i_dev_<slug>` is still in the
  hub (see Naming rules).
- It runs the spoke admission check first (`capacity.py admit`) and refuses when live memory cannot
  hold one more idle spoke plus a minimum test run (see Parallelism limits).
- After `git worktree add` it runs `make worktree-init` in the new worktree. It does not start a stack:
  it prints the `make up d=1` hint. Start the stack yourself from inside the worktree.

If a step after the add fails, the worktree is left in place for recovery and the error prints the
exact commands:

```sh
make -C <path> worktree-rm                  # discard it (needs the .env link)
git -C <primary> worktree remove <path>     # non-force fallback when the .env link is missing
```

## Ports

The primary clone keeps the defaults: web `8659`, Vite `5173`. A worktree gets `base + crc32(slug) % 99
+ 1` for each, then `scripts/spoke_ports.py` skips any port another project or any host process holds
and caches the result in the gitignored `docker/.ports.generated.env`, so a spoke keeps its URL across
`down`/`up`. Run `make stack-info` in a checkout to see its project, URLs, and the hub state.

## What each worktree isolates

- Compose project `u4i-<slug>`: its own containers, spoke volumes and locally built images. The hub's
  `pgdata` is shared by design, so the isolation is of spoke volumes, not of the Postgres cluster.
- Session cookie `u4i-<slug>_session`, so logins in two spokes do not log each other out.
- Dev database `u4i_dev_<slug>` (the slug with `-` replaced by `_`), inside the shared hub cluster.
- Host ports (above) and the `web-<slug>` / `vite-<slug>` aliases on the shared network.

Always go through `make`: only the Makefile computes the project, network and database names. A raw
`docker compose` fails fast on the unset `U4I_PROJECT`.

## Remove

Run inside the worktree:

```sh
make worktree-rm
```

- It runs `down -v --rmi local --remove-orphans` for the worktree's compose project. A worktree whose
  project has no compose containers, volumes or images (a half-built one that never created anything)
  skips `down` with a notice. Build-only residue, such as an image left by `make build`,
  `make vite-build` or `make generate-types`, still triggers the `down`.
- It drops the worktree's dev DB `u4i_dev_<slug>` from the hub. A hub that is not running leaves the DB
  behind with a warning naming it; a failing drop aborts the removal before anything is deleted, so you
  can retry.
- Finally a non-force `git -C <primary> worktree remove`. A dirty tree is refused. The branch is always
  kept; delete it yourself with `git branch -D`.
- It refuses to run in the primary clone, outside `<primary>/.claude/worktrees/`, in a directory named
  like the primary, or when `U4I_SLUG` is set to anything other than the directory's own name. Never set
  `U4I_SLUG` for `worktree-rm`.
- It never reads `.worktree.env`. The stronghold's `INIT=1` bootstrap writes one with a wrong-prefix
  `PROJECT=`, which is ignored by design.

## Naming rules

- The slug is the directory basename under `.claude/worktrees/`, and the compose project is
  `u4i-<slug>`. Keep worktree folder names unique among checkouts on the host.
- The slug must not equal `urls4irl` (the primary's directory name), must not sanitize to empty, and
  must not make a project starting `u4i-hub-` (reserved for the hub).
- A slug that already exists under `.claude/worktrees/` is refused, as is one whose `u4i-<slug>`
  project already appears in `docker compose ls --all`.
- Two names that differ only after the 40-character cut collide on the same slug: the second is
  refused.
- When the hub is running, a name whose dev DB `u4i_dev_<slug>` is still in the hub (left behind by a
  `worktree-rm` run while the hub was down) is refused with the exact `docker exec ... DROP DATABASE`
  command to run first. With the hub down the check is skipped, so bring the hub up and drop a
  warned-about leftover before reusing the name.
- One worktree per branch (git enforces this).

## Parallelism limits (macOS/Colima and Linux)

- Do not lower `n=` by hand when two spokes test at once. Test runs queue on the host token budget
  (`U4I_N_MAX`): a run that does not fit prints `token budget: waiting for <k> of <N> tokens ...` and
  starts when tokens free up.
- Memory-short runs wait (`token budget: waiting for memory ...`), and a run with no `n=` shrinks to the
  workers that fit live memory. Neither is a hang. A memory wait with no other run holding tokens exits
  1 after `U4I_MEMORY_WAIT` (600 s).
- `worktree-new` runs the spoke admission check first and refuses when live memory cannot hold an idle
  spoke plus a minimum test run (`spoke admission: refusing spoke ...`). Free memory or `make down` a
  running spoke, then retry.

## Via the stronghold

From `~/code`, `make wt-new REPO=urls4irl BRANCH=<branch>` and `make wt-rm REPO=urls4irl BRANCH=<branch>`
detect the root Makefile's `worktree-new` / `worktree-rm` targets and delegate to them. A repo with no worktree support can bootstrap a plain worktree with
`make wt-new REPO=<repo> BRANCH=<branch> INIT=1` (no owned targets, ports or compose isolation).

## Worktrees cut before this change

Worktrees created before `worktree-new` / `worktree-rm` existed have no `worktree-rm` target, so
`wt-rm` and `make worktree-rm` fail in them with `No rule to make target`. Merge or rebase `main` into
them first, or remove them by hand with a non-force `git worktree remove`.

## Residual risk

The worktree policy is `full`, so nothing blocks the `tunnel`, deploy and `vps-*` targets. They act on
real resources from any worktree exactly as they do from the primary. Run them deliberately.

A worktree also blocks deletion of the branch checked out in it, and `git branch -D` does not override
that — `--force` governs merge status, not checkouts. Remove the worktree first, then delete the branch.
