"""Unit tests pinning `scripts/worktree.sh` (the `new` and `slug` subcommands behind `make worktree-new`).

Each test runs the real script against a throwaway primary git repo with a fake `origin/main`, and stub `docker` /
`make` / `mise` executables on PATH that record their argv (and, for `make`, their environment). No Docker, mise or
real stack is involved. `worktree-rm` is Makefile recipe lines, so its pins live in `test_makefile_profiles.py`.

The Makefile is not copied into the `web` image (and the image has no `make`), so these tests skip inside the
container and run host-side. The skip deliberately does not look for the script itself: a missing script must fail the
tests, not skip them.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.test_makefile_profiles import INHERITED_MAKE_VARIABLES
from tests.unit.worktree_test_utils import (
    MAKEFILE,
    SCRIPT,
    SCRUBBED_CHILD_VARIABLES,
    TempPrimary,
    add_linked_worktree,
    build_temp_primary,
)

MAKE_BINARY: str | None = shutil.which("make")
BASH_BINARY: str | None = shutil.which("bash")

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        BASH_BINARY is None
        or shutil.which("git") is None
        or MAKE_BINARY is None
        or not MAKEFILE.is_file(),
        reason="needs bash, git, `make` and the repo Makefile (absent inside the web container)",
    ),
]

HUB_ID: str = "abc123def456"


def _run(
    primary: TempPrimary,
    *args: str,
    cwd: Path | None = None,
    extra_env: dict[str, str] | None = None,
    primary_root: bool = True,
) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), "scripts/worktree.sh is missing"
    assert BASH_BINARY is not None
    return subprocess.run(
        [BASH_BINARY, str(SCRIPT), *args],
        cwd=cwd or primary.root,
        env=primary.env(INHERITED_MAKE_VARIABLES, extra_env, primary_root=primary_root),
        capture_output=True,
        text=True,
        check=False,
    )


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return result.stdout + result.stderr


def _worktree_path(primary: TempPrimary, slug: str) -> Path:
    return primary.root / ".claude" / "worktrees" / slug


def _assert_refused_cleanly(
    primary: TempPrimary,
    result: subprocess.CompletedProcess[str],
    worktrees_before: str,
    slug: str | None = None,
) -> None:
    # A step-(1)/(2) refusal leaves no trace: admission never ran, nothing was added, no directory was made.
    assert result.returncode != 0, _output(result)
    assert result.stderr.strip(), "a refusal must print one clear message"
    assert primary.make_calls() == [], "admission/worktree-init must not run"
    assert primary.worktree_list() == worktrees_before
    if slug is not None:
        assert not _worktree_path(primary, slug).exists()


def _new(
    primary: TempPrimary,
    name: str,
    branch: str = "",
    base_ref: str = "",
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    return _run(primary, "new", name, branch, base_ref, **kwargs)  # type: ignore[arg-type]


@pytest.fixture
def primary(tmp_path: Path) -> TempPrimary:
    return build_temp_primary(tmp_path)


@pytest.mark.parametrize(
    ("name", "existing_dir", "extra_env"),
    [
        pytest.param("___", None, {}, id="sanitizes-empty"),
        pytest.param("urls4irl", None, {}, id="primary-basename"),
        pytest.param("hub-1", None, {}, id="hub-namespace"),
        pytest.param("taken", "taken", {}, id="existing-directory"),
        pytest.param(
            "busy",
            None,
            {"STUB_COMPOSE_LS": '[{"Name":"u4i-busy","Status":"running(1)"}]'},
            id="compose-project-exists",
        ),
    ],
)
def test_new_refuses_colliding_or_invalid_names(
    primary: TempPrimary,
    name: str,
    existing_dir: str | None,
    extra_env: dict[str, str],
) -> None:
    if existing_dir is not None:
        _worktree_path(primary, existing_dir).mkdir(parents=True)
    before = primary.worktree_list()

    result = _new(primary, name, extra_env=extra_env)

    _assert_refused_cleanly(primary, result, before)
    assert "No such file" not in result.stderr


def test_new_refuses_when_a_leftover_dev_db_exists(primary: TempPrimary) -> None:
    before = primary.worktree_list()

    result = _new(
        primary,
        "my-wt",
        extra_env={"STUB_HUB_ID": HUB_ID, "STUB_DB_EXISTING": "u4i_dev_my_wt"},
    )

    _assert_refused_cleanly(primary, result, before, "my-wt")
    message = _output(result)
    assert "u4i_dev_my_wt" in message
    marker = "drop it first: "
    assert marker in message
    command = message.split(marker, 1)[1].splitlines()[0]
    assert command.startswith(f"docker exec {HUB_ID} sh -c '")
    assert 'DROP DATABASE IF EXISTS \\"u4i_dev_my_wt\\" WITH (FORCE)' in command
    assert re.fullmatch(r"[0-9a-f]+", HUB_ID)
    assert re.findall(r"u4i_dev_\w+", command) == ["u4i_dev_my_wt"]
    assert subprocess.run(["bash", "-n", "-c", command], check=False).returncode == 0


def test_new_goes_on_to_admission_when_the_dev_db_is_absent(
    primary: TempPrimary,
) -> None:
    result = _new(
        primary,
        "my-wt",
        extra_env={"STUB_HUB_ID": HUB_ID, "STUB_DB_EXISTING": "u4i_dev_other"},
    )

    assert result.returncode == 0, _output(result)
    assert "already exists" not in _output(result)
    assert any("_admit-spoke" in call.argv for call in primary.make_calls())
    queries = [
        line for line in primary.docker_lines() if "SELECT 1 FROM pg_database" in line
    ]
    assert len(queries) == 1
    assert "u4i_dev_my_wt" in queries[0], (
        "the looked-up DB is u4i_dev_ + slug with - as _"
    )


def test_new_skips_the_dev_db_check_silently_when_the_hub_is_down(
    primary: TempPrimary,
) -> None:
    result = _new(primary, "my-wt")

    assert result.returncode == 0, _output(result)
    assert "u4i_dev_" not in _output(result)
    assert not [line for line in primary.docker_lines() if line.startswith("exec ")]


def test_new_refuses_when_the_dev_db_lookup_fails(primary: TempPrimary) -> None:
    before = primary.worktree_list()

    result = _new(
        primary,
        "my-wt",
        extra_env={
            "STUB_HUB_ID": HUB_ID,
            "STUB_EXEC_RC": "1",
            "STUB_EXEC_ERR": "psql: boom",
        },
    )

    _assert_refused_cleanly(primary, result, before, "my-wt")
    assert "psql: boom" in result.stderr


def test_dev_db_name_matches_the_makefile_derivation(primary: TempPrimary) -> None:
    # The script looks up u4i_dev_<slug with - as _>; `make -n worktree-rm` names the DB the Makefile derives.
    assert MAKE_BINARY is not None
    dry_run = subprocess.run(
        [MAKE_BINARY, "--no-print-directory", "-n", "worktree-rm", "U4I_SLUG=my-wt"],
        cwd=MAKEFILE.parent,
        env=primary.env(INHERITED_MAKE_VARIABLES, primary_root=False),
        capture_output=True,
        text=True,
        check=False,
    )
    assert dry_run.returncode == 0, dry_run.stderr
    assert "u4i_dev_my_wt" in dry_run.stdout


def test_new_refuses_without_a_primary_env_file(primary: TempPrimary) -> None:
    (primary.root / ".env").unlink()
    before = primary.worktree_list()

    result = _new(primary, "wt1")

    _assert_refused_cleanly(primary, result, before, "wt1")
    assert ".env.example" in result.stderr


def test_new_refuses_when_docker_is_unreachable(primary: TempPrimary) -> None:
    before = primary.worktree_list()

    result = _new(primary, "wt1", extra_env={"STUB_DOCKER_INFO_RC": "1"})

    _assert_refused_cleanly(primary, result, before, "wt1")
    assert "worktree-new needs docker for the admission check" in result.stderr


def test_new_refuses_when_name_and_branch_normalize_differently(
    primary: TempPrimary,
) -> None:
    before = primary.worktree_list()

    result = _new(primary, "Foo_Bar", "other")

    _assert_refused_cleanly(primary, result, before, "foo-bar")


def test_new_defaults_the_branch_to_the_slug(primary: TempPrimary) -> None:
    result = _new(primary, "Mixed_Case")

    assert result.returncode == 0, _output(result)
    path = _worktree_path(primary, "mixed-case")
    assert primary.git("branch", "--show-current", cwd=path).stdout.strip() == (
        "mixed-case"
    )


def test_new_accepts_a_branch_that_normalizes_to_the_slug(
    primary: TempPrimary,
) -> None:
    result = _new(primary, "Foo_Bar", "foo-bar")

    assert result.returncode == 0, _output(result)
    path = _worktree_path(primary, "foo-bar")
    assert primary.git("branch", "--show-current", cwd=path).stdout.strip() == (
        "foo-bar"
    )


@pytest.mark.parametrize(
    "branch",
    [
        pytest.param("bad..name", id="check-ref-format"),
        pytest.param("-foo", id="leading-dash"),
        pytest.param("foo bar", id="space"),
    ],
)
def test_new_rejects_an_invalid_branch(primary: TempPrimary, branch: str) -> None:
    before = primary.worktree_list()

    result = _new(primary, "foo", branch)

    _assert_refused_cleanly(primary, result, before, "foo")


@pytest.mark.parametrize(
    "base_ref",
    [
        pytest.param("-x", id="leading-dash"),
        pytest.param("no-such-ref", id="nonexistent"),
        pytest.param("tree-ref", id="not-a-commit"),
    ],
)
def test_new_validates_the_from_ref_before_admission(
    primary: TempPrimary, base_ref: str
) -> None:
    primary.git("tag", "tree-ref", "HEAD^{tree}")
    before = primary.worktree_list()

    result = _new(primary, "wt1", "", base_ref)

    _assert_refused_cleanly(primary, result, before, "wt1")


def test_new_validates_the_default_base_before_admission(primary: TempPrimary) -> None:
    primary.git("remote", "set-head", "origin", "--delete")
    primary.git("update-ref", "-d", "refs/remotes/origin/main")
    before = primary.worktree_list()

    result = _new(primary, "wt1")

    _assert_refused_cleanly(primary, result, before, "wt1")
    assert "origin/main" in result.stderr


def test_new_branches_from_the_default_base_without_from(primary: TempPrimary) -> None:
    result = _new(primary, "wt1")

    assert result.returncode == 0, _output(result)
    path = _worktree_path(primary, "wt1")
    assert primary.git("rev-parse", "HEAD", cwd=path).stdout.strip() == (
        primary.first_commit
    )
    assert primary.git("config", "--get", "branch.wt1.remote", check=False).stdout == ""


def test_new_branches_from_an_explicit_from_ref(primary: TempPrimary) -> None:
    result = _new(primary, "wt1", "", "main")

    assert result.returncode == 0, _output(result)
    path = _worktree_path(primary, "wt1")
    assert primary.git("rev-parse", "HEAD", cwd=path).stdout.strip() == (
        primary.second_commit
    )


def test_new_checks_out_an_existing_local_branch_and_ignores_from(
    primary: TempPrimary,
) -> None:
    primary.git("branch", "existing", primary.first_commit)

    result = _new(primary, "existing", "", "main")

    assert result.returncode == 0, _output(result)
    assert "ignored" in _output(result).lower()
    path = _worktree_path(primary, "existing")
    assert primary.git("branch", "--show-current", cwd=path).stdout.strip() == (
        "existing"
    )
    assert primary.git("rev-parse", "HEAD", cwd=path).stdout.strip() == (
        primary.first_commit
    )


def test_new_tracks_an_origin_only_branch(primary: TempPrimary) -> None:
    primary.git("push", "origin", "main:refs/heads/remote-only")
    primary.git("fetch", "origin")

    result = _new(primary, "remote-only")

    assert result.returncode == 0, _output(result)
    path = _worktree_path(primary, "remote-only")
    assert primary.git("branch", "--show-current", cwd=path).stdout.strip() == (
        "remote-only"
    )
    assert primary.git(
        "config", "branch.remote-only.remote", cwd=path
    ).stdout.strip() == ("origin")


def test_new_runs_admission_before_adding_the_worktree(primary: TempPrimary) -> None:
    slug = "wt-order"
    result = _new(
        primary,
        slug,
        extra_env={"STUB_PROBE_PATH": str(_worktree_path(primary, slug))},
    )

    assert result.returncode == 0, _output(result)
    admission = [call for call in primary.make_calls() if "_admit-spoke" in call.argv]
    assert len(admission) == 1
    assert admission[0].argv == [
        "-C",
        str(primary.root),
        "--no-print-directory",
        "_admit-spoke",
        f"U4I_SLUG={slug}",
    ]
    assert not admission[0].probe_exists, "admission ran after the worktree existed"


def test_new_leaves_nothing_when_admission_refuses(primary: TempPrimary) -> None:
    before = primary.worktree_list()

    result = _new(primary, "wt1", extra_env={"STUB_ADMIT_RC": "1"})

    assert result.returncode != 0
    assert "spoke admission" in result.stderr
    assert primary.worktree_list() == before
    assert not _worktree_path(primary, "wt1").exists()
    assert [call.argv[-2:] for call in primary.make_calls()] == [
        ["_admit-spoke", "U4I_SLUG=wt1"]
    ]


def test_new_initialises_the_worktree_and_never_starts_a_stack(
    primary: TempPrimary,
) -> None:
    result = _new(primary, "wt1")

    assert result.returncode == 0, _output(result)
    path = _worktree_path(primary, "wt1")
    calls = primary.make_calls()
    init_calls = [call for call in calls if "worktree-init" in call.argv]
    assert len(init_calls) == 1
    assert init_calls[0].argv[:2] == ["-C", str(path)]
    started = {"up", "up-built", "start-built", "tunnel"}
    assert not [call for call in calls if started & set(call.argv)]
    assert f"cd {path} && make up d=1" in result.stdout


def test_new_failure_after_the_add_prints_both_recovery_commands(
    primary: TempPrimary,
) -> None:
    result = _new(primary, "wt1", extra_env={"STUB_INIT_RC": "1"})

    path = _worktree_path(primary, "wt1")
    assert result.returncode != 0
    assert path.is_dir(), "the worktree is kept for the user to discard"
    message = _output(result)
    assert f"make -C {path} worktree-rm" in message
    assert f"git -C {primary.root} worktree remove {path}" in message


@pytest.mark.parametrize("variable", SCRUBBED_CHILD_VARIABLES)
def test_child_makes_run_without_the_invoking_identity(
    primary: TempPrimary, variable: str
) -> None:
    sentinels = {
        name: f"leak-{name}"
        for name in SCRUBBED_CHILD_VARIABLES
        if name != "PRIMARY_ROOT"
    }

    result = _new(primary, "wt1", extra_env=sentinels)

    assert result.returncode == 0, _output(result)
    calls = primary.make_calls()
    assert len(calls) == 2, [call.argv for call in calls]
    for call in calls:
        assert variable not in call.env, f"{variable} leaked into {call.argv}"
    admission = next(call for call in calls if "_admit-spoke" in call.argv)
    assert "U4I_SLUG=wt1" in admission.argv


def test_worktree_init_links_the_env_file_despite_a_primary_identity(
    tmp_path: Path,
) -> None:
    # Positive control with the real Makefile: without the scrub, an exported U4I_PRIMARY=1 makes the nested
    # worktree-init print "primary clone, nothing to link" and link nothing while worktree-new reports success.
    assert MAKE_BINARY is not None
    primary = build_temp_primary(tmp_path, with_makefile=True)

    result = _new(
        primary,
        "wt-real",
        extra_env={
            "U4I_PRIMARY": "1",
            "U4I_SLUG": primary.root.name,
            "STUB_REAL_MAKE": MAKE_BINARY,
        },
    )

    assert result.returncode == 0, _output(result)
    link = _worktree_path(primary, "wt-real") / ".env"
    assert link.is_symlink(), _output(result)
    assert link.resolve() == (primary.root / ".env").resolve()


def test_primary_root_env_wins_over_the_current_repo(tmp_path: Path) -> None:
    primary = build_temp_primary(tmp_path / "a")
    other = tmp_path / "b" / "other"
    other.mkdir(parents=True)
    primary.git("init", "-b", "main", cwd=other)

    result = _new(primary, "wt1", cwd=other)

    assert result.returncode == 0, _output(result)
    assert _worktree_path(primary, "wt1").is_dir()
    assert not (other / ".claude").exists()


def test_primary_root_is_derived_from_the_cwd_repo(primary: TempPrimary) -> None:
    result = _new(primary, "wt1", primary_root=False)

    assert result.returncode == 0, _output(result)
    assert _worktree_path(primary, "wt1").is_dir()


def test_primary_root_derived_from_a_linked_worktree_is_the_primary(
    primary: TempPrimary,
) -> None:
    seed = add_linked_worktree(primary, "seed")

    result = _new(primary, "wt2", cwd=seed, primary_root=False)

    assert result.returncode == 0, _output(result)
    assert _worktree_path(primary, "wt2").is_dir()
    assert not (seed / ".claude").exists()


def test_new_refuses_outside_any_git_repo(primary: TempPrimary, tmp_path: Path) -> None:
    elsewhere = tmp_path / "not-a-repo"
    elsewhere.mkdir()
    before = primary.worktree_list()

    result = _new(
        primary,
        "wt1",
        cwd=elsewhere,
        primary_root=False,
        extra_env={"GIT_CEILING_DIRECTORIES": str(tmp_path)},
    )

    _assert_refused_cleanly(primary, result, before, "wt1")


SLUG_PARITY_NAMES: list[str] = [
    "Mixed_Case.Name",
    "under_score",
    "dots.in.name",
    "-leading",
    "trailing-",
    "--both--",
    "abcdefghij" * 6,
    "a" * 39 + "-bbbbbbbb",
    "wt-1",
]
EMPTY_SLUG_NAMES: list[str] = ["___", "..."]


def _makefile_project(
    primary: TempPrimary, name: str
) -> subprocess.CompletedProcess[str]:
    assert MAKE_BINARY is not None
    return subprocess.run(
        [MAKE_BINARY, "--no-print-directory", "-n", "down", f"U4I_SLUG={name}"],
        cwd=MAKEFILE.parent,
        env=primary.env(INHERITED_MAKE_VARIABLES, primary_root=False),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("name", SLUG_PARITY_NAMES)
def test_slug_matches_the_makefile_sanitizer(primary: TempPrimary, name: str) -> None:
    script = _run(primary, "slug", name)
    dry_run = _makefile_project(primary, name)

    assert script.returncode == 0, _output(script)
    assert script.stdout == script.stdout.strip(), "slug prints the bare slug"
    assert dry_run.returncode == 0, dry_run.stderr
    projects = re.findall(r" -p (u4i-\S+)", dry_run.stdout)
    assert projects, dry_run.stdout
    assert projects[0] == f"u4i-{script.stdout.strip()}"


@pytest.mark.parametrize("name", EMPTY_SLUG_NAMES)
def test_slug_refuses_a_name_that_sanitizes_empty(
    primary: TempPrimary, name: str
) -> None:
    script = _run(primary, "slug", name)
    dry_run = _makefile_project(primary, name)

    assert script.returncode != 0
    assert script.stdout == ""
    assert dry_run.returncode != 0
    assert "sanitizes to an empty compose project name" in dry_run.stderr
    assert " -p u4i-" not in dry_run.stdout
