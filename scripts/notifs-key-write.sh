#!/usr/bin/env bash
# Host-side writer for the notifs hub key directory (run as the deploy user).
#
#   notifs-key-write.sh --check <dir>   preflight only
#   notifs-key-write.sh --write <dir>   preflight, then read key, Access client id and
#                                       Access client secret (three lines) from stdin
#
# The key and token never travel through argv or env. Output never contains them; on a
# successful write it prints the sha256 of the installed delivery_key (hash only).
set -euo pipefail

# Test-harness override only; no workflow sets it, so production always expects gid 1001.
EXPECTED_GID="${NOTIFS_KEY_EXPECTED_GID:-1001}"
EXPECTED_MODE="2750"
KEY_PATTERN='^dak_[A-Za-z0-9_-]{43}$'

TEMPS=()

cleanup() {
  local temp
  for temp in "${TEMPS[@]}"; do
    rm -f -- "$temp"
  done
}
trap cleanup EXIT

fail() {
  echo "notifs-key-write: $1" >&2
  exit 1
}

usage() {
  echo "usage: notifs-key-write.sh --check|--write <dir>" >&2
  exit 2
}

preflight() {
  local dir="$1"
  [ -e "$dir" ] || fail "directory does not exist: $dir"
  [ -d "$dir" ] || fail "not a directory: $dir"
  [ "$(stat -c %g -- "$dir")" = "$EXPECTED_GID" ] || fail "directory group is not $EXPECTED_GID: $dir"
  [ "$(stat -c %a -- "$dir")" = "$EXPECTED_MODE" ] || fail "directory mode is not $EXPECTED_MODE: $dir"
  { [ -w "$dir" ] && [ -x "$dir" ]; } || fail "directory is not writable by the caller: $dir"
}

write_keys() {
  local dir="$1"
  local key client_id client_secret extra
  IFS= read -r key || fail "stdin is missing the key line"
  IFS= read -r client_id || fail "stdin is missing the Access client id line"
  IFS= read -r client_secret || fail "stdin is missing the Access client secret line"
  if IFS= read -r extra; then
    fail "stdin has more than three lines (extra line of ${#extra} chars)"
  fi

  [[ $key =~ $KEY_PATTERN ]] || fail "key does not match the expected format"
  [ -n "$client_id" ] || fail "Access client id is empty"
  [ -n "$client_secret" ] || fail "Access client secret is empty"

  local names=(access_client_id access_client_secret delivery_key)
  local values=("$client_id" "$client_secret" "$key")
  local index temp
  umask 027
  for index in "${!names[@]}"; do
    temp="$dir/.${names[$index]}.tmp.$$"
    TEMPS+=("$temp")
    printf '%s\n' "${values[$index]}" >"$temp" || fail "could not write a temporary file in $dir"
    chmod 640 -- "$temp" || fail "could not set the mode of a temporary file in $dir"
  done

  for index in "${!names[@]}"; do
    temp="$dir/.${names[$index]}.tmp.$$"
    [ "$(cat -- "$temp")" = "${values[$index]}" ] || fail "temporary file for ${names[$index]} did not verify"
  done

  # The key moves last: the previous delivery_key is replaced only once both token files moved.
  for index in "${!names[@]}"; do
    mv -f -- "$dir/.${names[$index]}.tmp.$$" "$dir/${names[$index]}" || fail "could not install ${names[$index]}"
  done

  sha256sum -- "$dir/delivery_key" | cut -d' ' -f1
}

[ "$#" -eq 2 ] || usage
mode="$1"
dir="$2"

case "$mode" in
  --check)
    preflight "$dir"
    ;;
  --write)
    preflight "$dir"
    write_keys "$dir"
    ;;
  *)
    usage
    ;;
esac
