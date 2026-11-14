#!/usr/bin/env bash
# Delete the primary clone's host venv/ when its Python major.minor differs from the pinned interpreter.
#
#   host_venv_check.sh <primary-root> <expected-python-command...>
#
# <expected-python-command...> is the command that creates the venv (`mise exec python -- python`); it
# runs from <primary-root>, so the venv follows that clone's .mise.toml pin. The caller recreates venv/.
#
# Exit codes: 0 = nothing to do (no venv, or it matches), 3 = venv/ was deleted (caller rebuilds it and
# reinstalls what it needs), 1 = failed closed (bad usage, or the expected python could not be resolved):
# venv/ is left untouched and the caller must abort.
set -uo pipefail

REBUILT_EXIT=3
VERSION_SNIPPET='import sys; print("%d.%d" % sys.version_info[:2])'
VERSION_PATTERN='^[0-9]+\.[0-9]+$'

fail() {
  echo "host_venv_check: $1" >&2
  exit 1
}

[ "$#" -ge 2 ] || fail "usage: host_venv_check.sh <primary-root> <expected-python-command...>"
root="$1"
shift
[ -d "$root" ] || fail "primary root '$root' is not a directory"

expected="$(cd "$root" && "$@" -c "$VERSION_SNIPPET" 2>/dev/null)" || fail "expected-python command failed: $*"
[[ "$expected" =~ $VERSION_PATTERN ]] || fail "expected-python command printed no major.minor (got '$expected')"

venv_python="$root/venv/bin/python"
# -L catches a dangling symlink (the interpreter it pointed at was uninstalled): -e alone is false for it.
if [ ! -e "$venv_python" ] && [ ! -L "$venv_python" ]; then
  exit 0
fi

current="$("$venv_python" -c "$VERSION_SNIPPET" 2>/dev/null)" || current="broken"
if [ "$current" = "$expected" ]; then
  exit 0
fi

echo "host_venv_check: venv python $current != pinned $expected; deleting $root/venv so it is rebuilt"
rm -rf -- "$root/venv" || fail "could not delete $root/venv"
exit "$REBUILT_EXIT"
