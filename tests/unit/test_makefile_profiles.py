"""Unit tests pinning the Makefile's Compose profile wiring via `make -n` dry runs.

A dry run prints each recipe line without executing it, so these tests need no
Docker, mise or running stack: they assert on the compose commands `up`,
`up-built`, `down`, `build` and `restart` would run, and on the parse-time
validation of `p=` / `c=`. The profile map itself is pinned by
`test_compose_profiles.py`.

The Makefile is not copied into the `web` image and the image has no `make`, so
these tests skip inside the container and run host-side (and in CI's unit job).
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
MAKEFILE: Path = REPO_ROOT / "Makefile"
MAKE_BINARY: str | None = shutil.which("make")
GIT_BINARY: str | None = shutil.which("git")

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        MAKE_BINARY is None or not MAKEFILE.is_file(),
        reason="needs `make` and the repo Makefile (absent inside the web container)",
    ),
]

# Inherited make state (e.g. pytest launched from a make recipe) must not leak an outer p/c/d, or an outer
# worktree identity / port choice, into the dry run.
INHERITED_MAKE_VARIABLES: frozenset[str] = frozenset(
    {
        "MAKEFLAGS",
        "MFLAGS",
        "MAKELEVEL",
        "MAKEOVERRIDES",
        "p",
        "c",
        "d",
        "U4I_SLUG",
        "U4I_PRIMARY",
        "U4I_WEB_PORT",
        "U4I_VITE_PORT",
    }
)
SLUGGED_NAME_PATTERN: re.Pattern[str] = re.compile(r"\b(?:web|vite|u4i)-[a-z0-9-]*")
ALL_PROFILES_FLAG: str = "--profile '*'"


def _dry_run(*make_args: str) -> subprocess.CompletedProcess[str]:
    assert MAKE_BINARY is not None
    clean_env = {
        name: value
        for name, value in os.environ.items()
        if name not in INHERITED_MAKE_VARIABLES
    }
    return subprocess.run(
        [MAKE_BINARY, "--no-print-directory", "-n", *make_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=clean_env,
        check=False,
    )


def _successful_dry_run(*make_args: str) -> str:
    result = _dry_run(*make_args)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _single_line_containing(output: str, marker: str) -> str:
    matching_lines = [line for line in output.splitlines() if marker in line]
    assert len(matching_lines) == 1, (
        f"expected one line containing {marker!r}, got: {matching_lines}"
    )
    return matching_lines[0]


def _compose_up_line(output: str) -> str:
    return _single_line_containing(output, " up --build ")


def _profile_narrow_config_line(output: str) -> str:
    return _single_line_containing(output, " config --services")


def test_up_with_ui_profile_passes_it_to_compose() -> None:
    up_line = _compose_up_line(_successful_dry_run("up", "p=ui"))
    assert "--profile ui " in up_line


def test_up_without_profile_starts_only_the_core() -> None:
    output = _successful_dry_run("up")
    assert "--profile" not in _compose_up_line(output)
    assert "--profile" not in _profile_narrow_config_line(output)


@pytest.mark.parametrize(
    ("make_args", "expected_profile"),
    [
        pytest.param(("up-built",), "ui", id="defaults-to-ui"),
        pytest.param(("up-built", "p=full"), "full", id="explicit-full"),
    ],
)
def test_up_built_narrows_and_starts_the_same_profile(
    make_args: tuple[str, ...], expected_profile: str
) -> None:
    output = _successful_dry_run(*make_args)
    expected_flag = f"--profile {expected_profile} "
    assert expected_flag in _profile_narrow_config_line(output)
    up_line = _compose_up_line(output)
    assert "-f docker/compose.built.yaml" in up_line
    assert expected_flag in up_line


@pytest.mark.parametrize(
    ("profile_value", "expected_message"),
    [
        pytest.param("bogus", "p must be one of", id="unknown-profile"),
        pytest.param("ui full", "p takes one profile", id="two-profiles"),
    ],
)
def test_up_rejects_invalid_profile(profile_value: str, expected_message: str) -> None:
    result = _dry_run("up", f"p={profile_value}")
    assert result.returncode != 0
    assert expected_message in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("make_target", "variable_name", "expected_message"),
    [
        pytest.param("up", "p", "p must not contain '$'", id="p"),
        pytest.param("restart", "c", "c must not contain '$'", id="c"),
        pytest.param(
            "up", "U4I_WEB_PORT", "U4I_WEB_PORT must not contain '$'", id="web-port"
        ),
        pytest.param(
            "up", "U4I_VITE_PORT", "U4I_VITE_PORT must not contain '$'", id="vite-port"
        ),
    ],
)
@pytest.mark.parametrize(
    "function_syntax",
    [
        pytest.param("$({call})", id="parens"),
        pytest.param("${{{call}}}", id="braces"),
    ],
)
def test_dollar_bearing_variable_is_rejected_before_expansion(
    tmp_path: Path,
    make_target: str,
    variable_name: str,
    expected_message: str,
    function_syntax: str,
) -> None:
    probe_file = tmp_path / "probe"
    payload = function_syntax.format(call=f"shell touch {probe_file}")
    result = _dry_run(make_target, f"{variable_name}=ui{payload}")
    assert result.returncode != 0
    assert expected_message in result.stderr
    assert not probe_file.exists(), "the embedded $(shell …) ran before the guard"


def test_restart_requires_a_service() -> None:
    result = _dry_run("restart")
    assert result.returncode != 0
    assert "c=<service> is required" in result.stderr


def test_restart_reaches_every_profile() -> None:
    restart_line = _single_line_containing(
        _successful_dry_run("restart", "c=playwright"), " restart "
    )
    assert f"{ALL_PROFILES_FLAG} restart playwright" in restart_line


@pytest.mark.parametrize("make_target", ["down", "build"])
def test_lifecycle_targets_reach_every_profile(make_target: str) -> None:
    lifecycle_line = _single_line_containing(
        _successful_dry_run(make_target), f" {make_target}"
    )
    assert lifecycle_line.endswith(f"{ALL_PROFILES_FLAG} {make_target}")


def test_stack_info_sanitizes_slug_for_project_and_aliases() -> None:
    output = _successful_dry_run("stack-info", "U4I_SLUG=Feature.X_y")
    for expected_name in ("u4i-feature-x-y", "web-feature-x-y", "vite-feature-x-y"):
        assert expected_name in output


def test_stack_info_strips_trailing_dashes_from_aliases() -> None:
    output = _successful_dry_run("stack-info", "U4I_SLUG=wt-a.")
    assert "web-wt-a" in output
    assert "vite-wt-a" in output
    slugged_names = SLUGGED_NAME_PATTERN.findall(output)
    assert slugged_names, output
    assert not [name for name in slugged_names if name.endswith("-")], slugged_names


def test_stack_info_names_the_per_user_hub() -> None:
    output = _successful_dry_run("stack-info")
    assert f"u4i-hub-{os.getuid()}" in output
    assert f"u4i-shared-{os.getuid()}" in output


def test_stack_info_truncates_slug_without_a_trailing_dash() -> None:
    # 39 kept chars + "-.-x": the 40-char cut lands on a dash, which must then be stripped.
    output = _successful_dry_run("stack-info", f"U4I_SLUG={'a' * 39}-.-x")
    assert re.search(rf"web-{'a' * 39}(?![a-z0-9-])", output), output


def test_slug_with_a_quote_is_sanitized() -> None:
    output = _successful_dry_run("stack-info", "U4I_SLUG=a'b")
    assert "u4i-a-b" in output


def test_slug_that_sanitizes_to_empty_is_rejected() -> None:
    result = _dry_run("stack-info", "U4I_SLUG=...")
    assert result.returncode != 0
    assert "U4I_SLUG" in result.stderr


def test_worktree_init_is_a_noop_in_the_primary_clone() -> None:
    output = _successful_dry_run("worktree-init", "U4I_PRIMARY=1")
    assert "worktree-init: primary clone, nothing to link" in output
    assert not [line for line in output.splitlines() if "ln " in line]


def test_worktree_init_links_env_and_secrets_from_the_primary() -> None:
    output = _successful_dry_run("worktree-init", "U4I_PRIMARY=")
    link_lines = [line for line in output.splitlines() if "ln -s" in line]
    assert any(".env" in line for line in link_lines), output
    assert any("secrets" in line for line in link_lines), output


def test_worktree_init_fails_on_missing_env_but_skips_missing_secrets() -> None:
    output = _successful_dry_run("worktree-init", "U4I_PRIMARY=")
    link_lines = [line for line in output.splitlines() if "ln -s" in line]
    assert len(link_lines) == 2, link_lines
    env_line, secrets_line = link_lines
    assert "/.env" in env_line and "exit 1" in env_line, env_line
    assert "/secrets" in secrets_line and "exit 1" not in secrets_line, secrets_line
    for link_line in link_lines:
        assert "leaving it" in link_line, link_line
        assert "broken symlink" in link_line, link_line


@pytest.mark.skipif(GIT_BINARY is None, reason="needs `git`")
@pytest.mark.parametrize("linked_path", [".env", "secrets"])
def test_worktree_init_links_are_gitignored(linked_path: str) -> None:
    # --no-index treats a nonexistent path as a plain file: exactly how git sees the symlink worktree-init creates.
    assert GIT_BINARY is not None
    result = subprocess.run(
        [GIT_BINARY, "check-ignore", "-q", "--no-index", linked_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"{linked_path} is not gitignored: {result.stderr}"


def _ports_resolve_line(output: str) -> str:
    return _single_line_containing(output, "spoke_ports.py resolve")


def test_up_resolves_ports_before_starting() -> None:
    output = _successful_dry_run("up", "U4I_SLUG=wt-a")
    lines = output.splitlines()
    resolve_line = _ports_resolve_line(output)
    assert "--project u4i-wt-a " in resolve_line
    assert lines.index(resolve_line) < lines.index(_compose_up_line(output))


def test_explicit_port_is_forwarded() -> None:
    resolve_line = _ports_resolve_line(_successful_dry_run("up", "U4I_WEB_PORT=9001"))
    assert "--web-port '9001' " in resolve_line
    assert "--vite-port" not in resolve_line


def test_ui_up_resolves_ports_before_starting_vite() -> None:
    # test-functional reaches _ui-up with no $(MAKE) recursion, so a dry run stays side-effect free.
    output = _successful_dry_run("test-functional")
    lines = output.splitlines()
    resolve_index = lines.index(_ports_resolve_line(output))
    ui_up_line = _single_line_containing(
        output, "--profile ui up -d --wait vite playwright"
    )
    assert resolve_index < lines.index(ui_up_line)


@pytest.mark.parametrize("make_target", ["up-built", "start-built", "tunnel"])
def test_other_stack_starts_resolve_ports(make_target: str) -> None:
    output = _successful_dry_run(make_target)
    lines = output.splitlines()
    resolve_index = lines.index(_ports_resolve_line(output))
    first_compose_index = next(
        index for index, line in enumerate(lines) if "docker compose" in line
    )
    assert resolve_index < first_compose_index


def test_stack_info_shows_the_resolved_ports() -> None:
    assert "spoke_ports.py show" in _successful_dry_run("stack-info")


def test_setup_runs_worktree_init_first() -> None:
    # Static text check, never `make -n setup`: its `$(MAKE)` recipe lines run for real even under -n.
    setup_lines = [
        line for line in MAKEFILE.read_text().splitlines() if line.startswith("setup:")
    ]
    assert len(setup_lines) == 1, setup_lines
    prerequisites = setup_lines[0].split(":", 1)[1].split("##", 1)[0].split()
    assert prerequisites and prerequisites[0] == "worktree-init", prerequisites
