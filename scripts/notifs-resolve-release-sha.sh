#!/usr/bin/env bash
# Pick the commit whose .notifs/manifest.json the exchange workflow applies. Prints the 40-hex
# sha on stdout; any unresolved or unexpected input exits non-zero with nothing on stdout
# (fail closed, never a fallback to main).
#
# Inputs (env): EVENT_NAME, RUN_HEAD_SHA, INPUT_SHA, and for the release lookup GH_TOKEN + GH_REPO.
#   workflow_run                      -> RUN_HEAD_SHA, only if reachable from main (via gh api compare)
#   workflow_dispatch, INPUT_SHA set  -> INPUT_SHA, only if reachable from main (via gh api compare)
#   workflow_dispatch, INPUT_SHA ""   -> commit of the latest published release tag (via gh api)
set -euo pipefail

fail() {
  echo "notifs-resolve-release-sha: $*" >&2
  exit 1
}

release_commit() {
  local tag ref ref_type ref_sha tag_obj tag_type tag_sha
  tag="$(gh release view --json tagName --jq .tagName)" || fail "no published release found"
  [ -n "${tag}" ] || fail "latest release has no tag"
  ref="$(gh api "repos/${GH_REPO}/git/ref/tags/${tag}" --jq '.object.type + " " + .object.sha')" || fail "tag ref for ${tag} not found"
  read -r ref_type ref_sha <<<"${ref}"
  case "${ref_type}" in
    commit)
      echo "${ref_sha}"
      ;;
    tag)
      tag_obj="$(gh api "repos/${GH_REPO}/git/tags/${ref_sha}" --jq '.object.type + " " + .object.sha')" || fail "annotated tag ${tag} not readable"
      read -r tag_type tag_sha <<<"${tag_obj}"
      [ "${tag_type}" = "commit" ] || fail "annotated tag ${tag} does not point at a commit (${tag_type})"
      echo "${tag_sha}"
      ;;
    *)
      fail "tag ${tag} has unexpected object type '${ref_type}'"
      ;;
  esac
}

# A dispatched or deploy-run sha must already be on main (identical to, or an ancestor of, its head);
# otherwise a run bound to main could apply the manifest of an unmerged commit. Fails closed on any lookup error.
require_on_main() {
  local sha="$1" status
  [[ "${sha}" =~ ^[0-9a-f]{40}$ ]] || fail "dispatch sha is not 40 lowercase hex characters"
  [ -n "${GH_REPO:-}" ] || fail "GH_REPO is required to verify the dispatch sha"
  status="$(gh api "repos/${GH_REPO}/compare/main...${sha}" --jq .status)" || fail "cannot compare ${sha} with main"
  case "${status}" in
    identical | behind) ;;
    *) fail "dispatch sha ${sha} is not reachable from main (compare status '${status}')" ;;
  esac
}

selected=""
case "${EVENT_NAME:-}" in
  workflow_run)
    require_on_main "${RUN_HEAD_SHA:-}"
    selected="${RUN_HEAD_SHA}"
    ;;
  workflow_dispatch)
    if [ -n "${INPUT_SHA:-}" ]; then
      require_on_main "${INPUT_SHA}"
      selected="${INPUT_SHA}"
    else
      [ -n "${GH_REPO:-}" ] || fail "GH_REPO is required for the release lookup"
      selected="$(release_commit)" || exit 1
    fi
    ;;
  *)
    fail "unsupported event '${EVENT_NAME:-}'"
    ;;
esac

if ! [[ "${selected}" =~ ^[0-9a-f]{40}$ ]]; then
  fail "selected sha is not 40 lowercase hex characters"
fi
echo "${selected}"
