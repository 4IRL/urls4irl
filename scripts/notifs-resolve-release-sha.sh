#!/usr/bin/env bash
# Pick the commit whose .notifs/manifest.json the exchange workflow applies. Prints the 40-hex
# sha on stdout; any unresolved or unexpected input exits non-zero with nothing on stdout
# (fail closed, never a fallback to main).
#
# Inputs (env): EVENT_NAME, RUN_HEAD_SHA, INPUT_SHA, and for the release lookup GH_TOKEN + GH_REPO.
#   workflow_run                      -> RUN_HEAD_SHA
#   workflow_dispatch, INPUT_SHA set  -> INPUT_SHA
#   workflow_dispatch, INPUT_SHA ""   -> commit of the latest published release tag (via gh api)
set -euo pipefail

fail() {
  echo "notifs-resolve-release-sha: $*" >&2
  exit 1
}

release_commit() {
  local tag ref_type ref_sha tag_type
  tag="$(gh release view --json tagName --jq .tagName)" || fail "no published release found"
  [ -n "${tag}" ] || fail "latest release has no tag"
  ref_type="$(gh api "repos/${GH_REPO}/git/ref/tags/${tag}" --jq .object.type)" || fail "tag ref for ${tag} not found"
  ref_sha="$(gh api "repos/${GH_REPO}/git/ref/tags/${tag}" --jq .object.sha)" || fail "tag ref for ${tag} not found"
  case "${ref_type}" in
    commit)
      echo "${ref_sha}"
      ;;
    tag)
      tag_type="$(gh api "repos/${GH_REPO}/git/tags/${ref_sha}" --jq .object.type)" || fail "annotated tag ${tag} not readable"
      [ "${tag_type}" = "commit" ] || fail "annotated tag ${tag} does not point at a commit (${tag_type})"
      gh api "repos/${GH_REPO}/git/tags/${ref_sha}" --jq .object.sha || fail "annotated tag ${tag} not readable"
      ;;
    *)
      fail "tag ${tag} has unexpected object type '${ref_type}'"
      ;;
  esac
}

selected=""
case "${EVENT_NAME:-}" in
  workflow_run)
    selected="${RUN_HEAD_SHA:-}"
    ;;
  workflow_dispatch)
    if [ -n "${INPUT_SHA:-}" ]; then
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
