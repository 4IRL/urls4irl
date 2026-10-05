#!/usr/bin/env bash
# worktree.sh - create a urls4irl worktree (the logic behind `make worktree-new`).
#
#   worktree.sh new <name> [<branch>] [<from>]   validate, check admission, `git worktree add`, `worktree-init`
#   worktree.sh slug <name>                      print the sanitized slug (pure; no side effects)
#
# `worktree-rm` is deliberately NOT here: it is direct Makefile recipe lines (see the Makefile).
# `new` never starts a stack: it prints `make up d=1` for the user to run inside the new worktree.
# It never reads or writes .worktree.env: the INIT=1 bootstrap writes one with a wrong-prefix
# PROJECT=urls4irl-... (the project is u4i-<slug>), and it is ignored by design.
#
# Order of `new`: (1) validate inputs (read-only), (2) collision checks (read-only), (3) spoke admission,
# (4) git worktree add, (5) worktree-init, (6) hint. A refusal before (4) leaves no trace.
set -euo pipefail

err() { printf 'worktree-new: %s\n' "$*" >&2; }
warn() { printf 'worktree-new: warning: %s\n' "$*" >&2; }
die() {
  err "$*"
  exit 1
}

# slug <raw>: lowercase, non [a-z0-9-] -> '-', strip leading '-', cut 40, strip trailing '-'. Identical to the
# Makefile's U4I_HOST_SLUG (Makefile:75-76), pinned by tests/unit/test_worktree_script.py. Prints no newline.
slug() {
  local raw="$1" cleaned
  cleaned="$(printf '%s' "$raw" | LC_ALL=C tr '[:upper:]' '[:lower:]' | LC_ALL=C tr -c 'a-z0-9-' '-')"
  while [ "${cleaned#-}" != "$cleaned" ]; do cleaned="${cleaned#-}"; done
  cleaned="${cleaned:0:40}"
  while [ "${cleaned%-}" != "$cleaned" ]; do cleaned="${cleaned%-}"; done
  if [ -z "$cleaned" ]; then
    err "'$raw' sanitizes to an empty name; use letters or digits"
    return 1
  fi
  printf '%s' "$cleaned"
}

# resolve_primary_root: the exported PRIMARY_ROOT when set, else derived from git exactly as Makefile:72 does.
resolve_primary_root() {
  local common
  if [ -n "${PRIMARY_ROOT:-}" ]; then
    printf '%s' "$PRIMARY_ROOT"
    return 0
  fi
  common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" ||
    die "not inside a git checkout (git rev-parse --git-common-dir failed)"
  printf '%s' "${common%/.git}"
}

# default_base <primary>: origin/<default branch>, from origin/HEAD with an origin/main fallback.
default_base() {
  local ref
  ref="$(git -C "$1" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null)" || ref=""
  ref="${ref#origin/}"
  printf 'origin/%s' "${ref:-main}"
}

# Run make for a child checkout without the invoking checkout's identity or make state leaking in (a leaked
# U4I_PRIMARY=1 would make worktree-init link nothing while worktree-new reports success).
scrubbed_make() {
  env -u U4I_SLUG -u U4I_PRIMARY -u U4I_PROJECT -u U4I_DEV_DB -u U4I_HOST_SLUG -u U4I_WEB_HOST -u U4I_VITE_HOST \
    -u PRIMARY_ROOT -u MAKEFLAGS -u MFLAGS -u MAKEOVERRIDES make "$@"
}

# check_leftover_dev_db <slug>: with the hub db running, refuse when u4i_dev_<slug> is still in the cluster.
# A hub that is not running is skipped silently (worktree-rm already warned the DB would persist); an
# unverifiable lookup (psql failure) refuses rather than being ignored.
check_leftover_dev_db() {
  local slug_name="$1" hub_project hub_id dev_db found drop_cmd
  hub_project="u4i-hub-$(id -u)"
  hub_id="$(docker ps --filter "label=com.docker.compose.project=$hub_project" --filter label=com.docker.compose.service=db --filter status=running -q 2>/dev/null)" || hub_id=""
  if [ -z "$hub_id" ]; then
    return 0
  fi
  case "$hub_id" in
    *[!0-9a-f]*) die "unexpected hub db container id '$hub_id'" ;;
  esac
  dev_db="u4i_dev_${slug_name//-/_}"
  if ! found="$(docker exec "$hub_id" sh -c "psql -U \"\$POSTGRES_USER\" -d postgres -v ON_ERROR_STOP=1 -tAc \"SELECT 1 FROM pg_database WHERE datname = '$dev_db'\"" 2>&1)"; then
    die "could not check the hub for an existing dev DB $dev_db: $found"
  fi
  if [ -n "$found" ]; then
    drop_cmd="docker exec $hub_id sh -c 'psql -U \"\$POSTGRES_USER\" -d postgres -v ON_ERROR_STOP=1 -c \"DROP DATABASE IF EXISTS \\\"$dev_db\\\" WITH (FORCE)\"'"
    err "dev DB $dev_db already exists in the hub (left by an earlier worktree of this name whose hub was down at worktree-rm)"
    printf 'worktree-new: drop it first: %s\n' "$drop_cmd" >&2
    printf 'worktree-new: then retry\n' >&2
    exit 1
  fi
}

# add_worktree <primary> <mode> <branch> <path> <base>
add_worktree() {
  local primary="$1" mode="$2" branch="$3" path="$4" base="$5"
  case "$mode" in
    local) git -C "$primary" worktree add "$path" "$branch" ;;
    origin) git -C "$primary" worktree add --track -b "$branch" "$path" "origin/$branch" ;;
    *) git -C "$primary" worktree add --no-track -b "$branch" "$path" "$base" ;;
  esac
}

cmd_new() {
  local name="${1-}" branch="${2-}" from="${3-}"
  local primary_root new_slug mode base path compose_json

  # (1) validate inputs: read-only.
  primary_root="$(resolve_primary_root)" || exit 1
  new_slug="$(slug "$name")" || exit 1
  if [ "$new_slug" = urls4irl ] || [ "$new_slug" = "$(slug "$(basename "$primary_root")" 2>/dev/null || true)" ]; then
    die "name '$name' gives slug '$new_slug', which is the primary clone's own name; pick another"
  fi
  case "$new_slug" in
    hub-*) die "slug '$new_slug' would put the spoke project in the per-user hub's u4i-hub-* namespace; pick another name" ;;
  esac

  if [ -n "$branch" ]; then
    case "$branch" in
      -*) die "branch '$branch' must not start with '-'" ;;
      *'@{'*) die "'$branch' is not a valid branch name" ;;
    esac
    git -C "$primary_root" check-ref-format --branch "$branch" >/dev/null 2>&1 ||
      die "'$branch' is not a valid branch name"
    if [ "$(slug "$branch" 2>/dev/null || true)" != "$new_slug" ]; then
      die "name '$name' (slug '$new_slug') and branch '$branch' normalize to different slugs; the directory must match the branch"
    fi
  else
    branch="$new_slug"
  fi

  case "$from" in
    -*) die "from '$from' must not start with '-'" ;;
  esac
  if [ -n "$from" ] && ! git -C "$primary_root" rev-parse --verify --quiet "$from^{commit}" >/dev/null; then
    die "from '$from' is not a commit in this repository; run 'git fetch origin' or pass another ref"
  fi

  if git -C "$primary_root" show-ref --verify --quiet "refs/heads/$branch"; then
    mode=local
  elif git -C "$primary_root" show-ref --verify --quiet "refs/remotes/origin/$branch"; then
    mode=origin
  else
    mode=new
  fi
  base=""
  if [ "$mode" = new ]; then
    base="${from:-$(default_base "$primary_root")}"
    git -C "$primary_root" rev-parse --verify --quiet "$base^{commit}" >/dev/null ||
      die "base '$base' not found; run 'git fetch origin' or pass from=<ref>"
  elif [ -n "$from" ]; then
    warn "from '$from' ignored: branch '$branch' already exists ($mode)"
  fi

  if [ ! -e "$primary_root/.env" ]; then
    die "the primary clone has no .env ($primary_root/.env); copy .env.example to .env and fill it first"
  fi
  docker info >/dev/null 2>&1 || die "worktree-new needs docker for the admission check, but docker is unreachable"

  # (2) collision checks: read-only, before admission.
  path="$primary_root/.claude/worktrees/$new_slug"
  if [ -e "$path" ]; then
    die "$path already exists"
  fi
  compose_json="$(docker compose ls --all --format json 2>&1)" ||
    die "could not list compose projects: $compose_json"
  case "$compose_json" in
    *"\"Name\":\"u4i-$new_slug\""*) die "compose project u4i-$new_slug already exists; pick another name" ;;
  esac
  check_leftover_dev_db "$new_slug"

  # (3) spoke admission (runs _hub-capacity first), before anything is created.
  if ! scrubbed_make -C "$primary_root" --no-print-directory _admit-spoke "U4I_SLUG=$new_slug"; then
    die "admission refused; nothing was created"
  fi

  # (4) create the worktree, (5) link .env/secrets.
  mkdir -p "$primary_root/.claude/worktrees"
  add_worktree "$primary_root" "$mode" "$branch" "$path" "$base" || die "git worktree add failed; nothing was created"
  if ! scrubbed_make -C "$path" worktree-init; then
    err "worktree-init failed; the worktree was left in place at $path"
    printf 'discard it with: make -C %q worktree-rm\n' "$path" >&2
    printf 'or, if its .env link is missing: git -C %q worktree remove %q\n' "$primary_root" "$path" >&2
    exit 1
  fi

  # (6) hint: never start a stack here.
  printf 'created %s (branch %s)\n' "$path" "$branch"
  printf 'start it with: cd %q && make up d=1\n' "$path"
}

case "${1-}" in
  new) cmd_new "${2-}" "${3-}" "${4-}" ;;
  slug) slug "${2-}" ;;
  *)
    printf 'usage: worktree.sh new <name> [<branch>] [<from>] | slug <name>\n' >&2
    exit 2
    ;;
esac
