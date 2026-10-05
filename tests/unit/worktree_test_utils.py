"""Shared fixtures for the host-static `worktree-new` / `worktree-rm` tests.

Builds a throwaway "primary" git repo (with a fake `origin/main`) and stub `docker` / `make` / `mise` executables
that record what they were called with, so `scripts/worktree.sh` and the Makefile's `worktree-rm` recipe can run for
real without touching Docker, mise or the checkout under test. Used by `test_worktree_script.py` and
`test_makefile_profiles.py`; stdlib only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
MAKEFILE: Path = REPO_ROOT / "Makefile"
SCRIPT: Path = REPO_ROOT / "scripts" / "worktree.sh"

# Names the Makefile / script derive identity from; a test run must never inherit the suite's own values.
EXTRA_DROPPED_ENV: frozenset[str] = frozenset(
    {
        "PRIMARY_ROOT",
        "U4I_PROJECT",
        "U4I_DEV_DB",
        "U4I_HOST_SLUG",
        "U4I_WEB_HOST",
        "U4I_VITE_HOST",
        "U4I_UID",
        "U4I_HUB_PROJECT",
        "U4I_SHARED_NET",
    }
)
# The identity / make-state variables the script must scrub before its child makes (DD-1).
SCRUBBED_CHILD_VARIABLES: tuple[str, ...] = (
    "U4I_SLUG",
    "U4I_PRIMARY",
    "U4I_PROJECT",
    "U4I_DEV_DB",
    "U4I_HOST_SLUG",
    "U4I_WEB_HOST",
    "U4I_VITE_HOST",
    "PRIMARY_ROOT",
    "MAKEFLAGS",
    "MFLAGS",
    "MAKEOVERRIDES",
)

STUB_DOCKER: str = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$STUB_LOG_DIR/docker.log"
case "$1" in
  info) exit "${STUB_DOCKER_INFO_RC:-0}" ;;
  compose)
    case " $* " in
      *" ls "*) printf '%s' "${STUB_COMPOSE_LS:-[]}"; exit 0 ;;
      *" down "*) exit "${STUB_COMPOSE_DOWN_RC:-0}" ;;
    esac
    exit 0 ;;
  ps)
    case "$*" in
      *"com.docker.compose.project=u4i-hub-$(id -u)"*"com.docker.compose.service=db"*"status=running"*)
        [ -n "${STUB_HUB_ID:-}" ] && printf '%s\n' "$STUB_HUB_ID"
        exit "${STUB_HUB_RC:-0}" ;;
    esac
    [ -n "${STUB_PS_ALL_OUT:-}" ] && printf '%s\n' "$STUB_PS_ALL_OUT"
    exit "${STUB_PS_ALL_RC:-0}" ;;
  volume)
    [ -n "${STUB_VOLUME_OUT:-}" ] && printf '%s\n' "$STUB_VOLUME_OUT"
    exit "${STUB_VOLUME_RC:-0}" ;;
  image)
    [ -n "${STUB_IMAGE_OUT:-}" ] && printf '%s\n' "$STUB_IMAGE_OUT"
    exit "${STUB_IMAGE_RC:-0}" ;;
  exec)
    if [ "${STUB_EXEC_RC:-0}" != 0 ]; then
      printf '%s\n' "${STUB_EXEC_ERR:-psql: stub failure}" >&2
      exit "$STUB_EXEC_RC"
    fi
    case "$*" in
      *"SELECT 1 FROM pg_database"*)
        if [ -n "${STUB_DB_EXISTING:-}" ]; then
          case "$*" in *"$STUB_DB_EXISTING"*) printf '1\n' ;; esac
        fi ;;
    esac
    exit 0 ;;
esac
exit 0
"""

STUB_MAKE: str = r"""#!/usr/bin/env bash
dir="$STUB_LOG_DIR/make-calls"
mkdir -p "$dir"
n=0
while ! mkdir "$dir/call-$n" 2>/dev/null; do n=$((n + 1)); done
{
  echo '--ARGV--'
  printf '%s\n' "$@"
  echo '--PROBE--'
  if [ -n "${STUB_PROBE_PATH:-}" ] && [ -e "$STUB_PROBE_PATH" ]; then echo yes; else echo no; fi
  echo '--ENV--'
  env
} > "$dir/call-$n/record.txt"
case " $* " in
  *" _admit-spoke "*)
    if [ "${STUB_ADMIT_RC:-0}" != 0 ]; then
      echo "spoke admission: refusing spoke (stub)" >&2
      exit "$STUB_ADMIT_RC"
    fi
    exit 0 ;;
  *" worktree-init "*)
    if [ -z "${STUB_REAL_MAKE:-}" ]; then
      if [ "${STUB_INIT_RC:-0}" != 0 ]; then
        echo "worktree-init: stub failure" >&2
        exit "$STUB_INIT_RC"
      fi
      exit 0
    fi ;;
esac
if [ -n "${STUB_REAL_MAKE:-}" ]; then exec "$STUB_REAL_MAKE" "$@"; fi
exit 0
"""

STUB_MISE: str = "#!/usr/bin/env bash\nexit 0\n"


@dataclass(frozen=True)
class MakeCall:
    argv: list[str]
    probe_exists: bool
    env: dict[str, str]


@dataclass(frozen=True)
class TempPrimary:
    root: Path
    origin: Path
    stub_dir: Path
    log_dir: Path
    first_commit: str
    second_commit: str

    def git(
        self, *args: str, cwd: Path | None = None, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        return _git(cwd or self.root, *args, check=check)

    def worktree_list(self) -> str:
        return self.git("worktree", "list", "--porcelain").stdout

    def docker_lines(self) -> list[str]:
        log = self.log_dir / "docker.log"
        return log.read_text().splitlines() if log.is_file() else []

    def make_calls(self) -> list[MakeCall]:
        calls_dir = self.log_dir / "make-calls"
        if not calls_dir.is_dir():
            return []
        calls: list[MakeCall] = []
        ordered = sorted(
            calls_dir.iterdir(), key=lambda path: int(path.name.split("-", 1)[1])
        )
        for call_dir in ordered:
            text = (call_dir / "record.txt").read_text()
            argv_part, rest = text.split("--PROBE--\n", 1)
            probe_part, env_part = rest.split("--ENV--\n", 1)
            env = {
                line.split("=", 1)[0]: line.split("=", 1)[1]
                for line in env_part.splitlines()
                if "=" in line
            }
            calls.append(
                MakeCall(
                    argv=argv_part.removeprefix("--ARGV--\n").splitlines(),
                    probe_exists=probe_part.strip() == "yes",
                    env=env,
                )
            )
        return calls

    def env(
        self,
        inherited: frozenset[str],
        extra: dict[str, str] | None = None,
        *,
        primary_root: bool = True,
    ) -> dict[str, str]:
        dropped = inherited | EXTRA_DROPPED_ENV
        env = {key: value for key, value in os.environ.items() if key not in dropped}
        env.update(
            {
                "PATH": f"{self.stub_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                "STUB_LOG_DIR": str(self.log_dir),
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
            }
        )
        if primary_root:
            env["PRIMARY_ROOT"] = str(self.root)
        env.update(extra or {})
        return env


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    git_binary = shutil.which("git")
    assert git_binary is not None
    return subprocess.run(
        [
            git_binary,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(cwd),
            *args,
        ],
        capture_output=True,
        text=True,
        check=check,
        env={
            **{
                key: value
                for key, value in os.environ.items()
                if not key.startswith("GIT_")
            },
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        },
    )


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(0o755)


def build_temp_primary(
    base: Path,
    *,
    name: str = "urls4irl",
    with_makefile: bool = False,
    with_env: bool = True,
) -> TempPrimary:
    """A primary clone with origin/main at the first commit and one more local-only commit on main."""
    root = base / name
    origin = base / "origin.git"
    stub_dir = base / "stubs"
    log_dir = base / "logs"
    for directory in (root, stub_dir, log_dir):
        directory.mkdir(parents=True)
    _write_executable(stub_dir / "docker", STUB_DOCKER)
    _write_executable(stub_dir / "make", STUB_MAKE)
    _write_executable(stub_dir / "mise", STUB_MISE)

    _git(base, "init", "--bare", "-b", "main", str(origin))
    _git(root, "init", "-b", "main")
    (root / "README.md").write_text("primary\n")
    (root / ".gitignore").write_text(".claude/worktrees/\n.env\nsecrets/\n")
    if with_makefile:
        shutil.copyfile(MAKEFILE, root / "Makefile")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "first")
    first_commit = _git(root, "rev-parse", "HEAD").stdout.strip()
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "origin", "main")
    _git(root, "fetch", "origin")
    _git(root, "remote", "set-head", "origin", "main")
    (root / "second.txt").write_text("local only\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "second")
    second_commit = _git(root, "rev-parse", "HEAD").stdout.strip()
    if with_env:
        (root / ".env").write_text("POSTGRES_USER=u\n")
    return TempPrimary(
        root=root.resolve(),
        origin=origin,
        stub_dir=stub_dir,
        log_dir=log_dir,
        first_commit=first_commit,
        second_commit=second_commit,
    )


def add_linked_worktree(primary: TempPrimary, slug: str) -> Path:
    """A hand-made linked worktree at <primary>/.claude/worktrees/<slug> (any name, unlike `worktree-new`)."""
    path = primary.root / ".claude" / "worktrees" / slug
    primary.git("worktree", "add", "-b", f"branch-{slug}", str(path), "main")
    return path
