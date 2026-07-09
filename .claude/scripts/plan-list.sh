#!/usr/bin/env bash
#
# plan-list.sh — enumerate every plan (master plans AND sub-plans) under plans/
# with its current completion status, grouped by topic.
#
# Accuracy: the `finished:` value is read from the first `^finished:` line that
# appears AFTER the `## Status` heading. Plan bodies routinely quote a sub-plan's
# `` `finished: true` `` in prose (a real false-positive source); anchoring on the
# Status heading + a line-start match ignores those.
#
# Master vs sub: a plan is a "master" iff its filename ends in `-master.md`
# (100% precise/recall across the repo; no plan encodes it any other way).
#
# Efficiency: one awk pass per file, no file contents leave the script — the
# caller (model) only sees the compact table below.
#
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [ ! -d plans ]; then
  echo "No plans/ directory found at $ROOT"
  exit 0
fi

total=0
done_n=0
open_n=0
unknown_n=0
linked_n=0
rows=""

# Plan files live at plans/<name>.md (depth 1) and plans/<topic>/<name>.md (depth 2).
# Capping maxdepth at 2 excludes reviews/, research/, compliance/, tmp/ (depth >= 3).
while IFS= read -r plan_file; do
  [ -n "$plan_file" ] || continue

  finished_value="$(awk '
    /^##[[:space:]]+Status/ { in_status = 1; next }
    in_status && /^finished:[[:space:]]*/ { print $2; exit }
  ' "$plan_file")"

  case "$finished_value" in
    true)
      box="x"
      done_n=$((done_n + 1))
      ;;
    false)
      box=" "
      open_n=$((open_n + 1))
      ;;
    *)
      box="?"
      unknown_n=$((unknown_n + 1))
      ;;
  esac

  case "$plan_file" in
    *-master.md)
      kind="master"
      kind_sort="0"
      ;;
    *)
      kind="sub"
      kind_sort="1"
      ;;
  esac

  # Related GitHub issue number from the YAML frontmatter (`github_issue: <N>`).
  issue="$(awk '/^github_issue:[[:space:]]*/ { print $2; exit }' "$plan_file")"
  [ -n "$issue" ] && linked_n=$((linked_n + 1))

  topic="$(basename "$(dirname "$plan_file")")"
  [ "$topic" = "plans" ] && topic="(root)"
  name="$(basename "$plan_file" .md)"
  total=$((total + 1))

  rows="${rows}${topic}\t${kind_sort}\t${kind}\t${box}\t${name}\t${issue}\n"
done < <(find plans -maxdepth 2 -name '*.md' | sort)

if [ "$total" -eq 0 ]; then
  echo "No plan files found under plans/."
  exit 0
fi

echo "# Plans"

# Sort by topic, then master-before-sub, then name; print grouped with a checkbox per plan.
printf "%b" "$rows" |
  sort -t"$(printf '\t')" -k1,1 -k2,2 -k5,5 |
  awk -F'\t' '
      { if ($1 != current_topic) { current_topic = $1; printf "\n## %s\n", $1 }
        master_tag = ($3 == "master" ? "  (master)" : "")
        issue_tag  = ($6 == "" ? "  (no issue)" : "  #" $6)
        printf "  - [%s] %s%s%s\n", $4, $5, master_tag, issue_tag }
    '

summary="Total: ${total} plans — ${done_n} done, ${open_n} open"
[ "$unknown_n" -gt 0 ] && summary="${summary}, ${unknown_n} unknown"
summary="${summary} · ${linked_n}/${total} linked to a GitHub issue"
echo
echo "$summary"
echo "Legend: [x] finished  [ ] open  [?] no \`## Status\`/\`finished:\` line  ·  #N = GitHub issue"

# Flat "Not Done" section (open + unknown) so every non-finished plan is visible
# without a separate filtered request. Topic is appended per-row since this list
# has no topic-grouping headings like the main list above.
not_done_n=$((open_n + unknown_n))
if [ "$not_done_n" -gt 0 ]; then
  echo
  echo "## Not Done (${not_done_n})"
  printf "%b" "$rows" |
    sort -t"$(printf '\t')" -k1,1 -k2,2 -k5,5 |
    awk -F'\t' '
        $4 != "x" {
          master_tag = ($3 == "master" ? "  (master)" : "")
          issue_tag  = ($6 == "" ? "  (no issue)" : "  #" $6)
          printf "  - [%s] %s%s%s  · %s\n", $4, $5, master_tag, issue_tag, $1
        }
      '
fi
