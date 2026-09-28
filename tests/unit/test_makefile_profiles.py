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
        _successful_dry_run("restart", "c=vite"), " restart "
    )
    assert f"{ALL_PROFILES_FLAG} restart vite" in restart_line


@pytest.mark.parametrize("hub_service", ["db", "playwright"])
def test_restart_rejects_hub_services(hub_service: str) -> None:
    result = _dry_run("restart", f"c={hub_service}")
    assert result.returncode != 0
    assert f"make hub-restart c={hub_service}" in result.stderr


def test_hub_restart_targets_the_hub_project() -> None:
    restart_line = _single_line_containing(
        _successful_dry_run("hub-restart", "c=playwright"), " restart "
    )
    assert f"-p u4i-hub-{os.getuid()} " in restart_line
    assert restart_line.endswith("compose.hub.yaml restart playwright")


@pytest.mark.parametrize(
    ("make_args", "expected_message"),
    [
        pytest.param(("hub-restart",), "c=<service> is required", id="missing"),
        pytest.param(("hub-restart", "c=web"), "c must be one of", id="spoke-service"),
    ],
)
def test_hub_restart_rejects_non_hub_services(
    make_args: tuple[str, ...], expected_message: str
) -> None:
    result = _dry_run(*make_args)
    assert result.returncode != 0
    assert expected_message in result.stderr


def test_logs_requires_a_service() -> None:
    result = _dry_run("logs")
    assert result.returncode != 0
    assert "c=<service> is required" in result.stderr


def test_logs_targets_the_spoke_project() -> None:
    logs_line = _single_line_containing(
        _successful_dry_run("logs", "c=cloudflared", "U4I_SLUG=wt-a"), " logs "
    )
    assert "-p u4i-wt-a " in logs_line
    assert "compose.hub.yaml" not in logs_line
    assert logs_line.endswith(f"{ALL_PROFILES_FLAG} logs cloudflared")


@pytest.mark.parametrize("hub_service", ["db", "playwright"])
def test_logs_rejects_hub_services(hub_service: str) -> None:
    result = _dry_run("logs", f"c={hub_service}")
    assert result.returncode != 0
    assert "is a hub service" in result.stderr


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


@pytest.mark.parametrize("linked_path", [".env", "secrets"])
def test_worktree_init_reports_each_link_it_creates(linked_path: str) -> None:
    output = _successful_dry_run("worktree-init", "U4I_PRIMARY=")
    link_line = _single_line_containing(output, f'/{linked_path}" {linked_path}')
    link_message = re.search(
        rf'echo "worktree-init: linked {re.escape(linked_path)} -> (\S+)"', link_line
    )
    assert link_message is not None, link_line
    assert link_message.group(1).endswith(f"/{linked_path}"), link_line
    assert f'ln -s "{link_message.group(1)}" {linked_path} && echo' in link_line


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
    ui_up_line = _single_line_containing(output, "--profile ui up -d --wait web vite")
    assert resolve_index < lines.index(ui_up_line)


def test_ui_up_starts_hub_playwright_first() -> None:
    output = _successful_dry_run("test-functional")
    lines = output.splitlines()
    playwright_up_line = _hub_playwright_up_line(output)
    ui_up_line = _single_line_containing(output, "--profile ui up -d --wait web vite")
    assert lines.index(playwright_up_line) < lines.index(ui_up_line)
    assert "playwright" not in ui_up_line


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


HUB_FILE_MARKER: str = "compose.hub.yaml"


def _hub_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if HUB_FILE_MARKER in line]


def _hub_db_up_line(output: str) -> str:
    return _single_line_containing(output, " up -d --wait --no-recreate db")


def _hub_playwright_up_line(output: str) -> str:
    return _single_line_containing(output, " up -d --wait --no-recreate playwright")


def _primary_root() -> str:
    assert GIT_BINARY is not None
    common_dir = subprocess.run(
        [GIT_BINARY, "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return str(Path(common_dir).parent)


def test_spoke_compose_passes_the_project_name() -> None:
    up_line = _compose_up_line(_successful_dry_run("up", "U4I_SLUG=wt-a"))
    assert "-p u4i-wt-a " in up_line
    assert HUB_FILE_MARKER not in up_line


@pytest.mark.skipif(GIT_BINARY is None, reason="needs `git`")
def test_up_ensures_the_hub_first() -> None:
    output = _successful_dry_run("up")
    lines = output.splitlines()
    hub_db_line = _hub_db_up_line(output)
    assert f"-f {_primary_root()}/docker/{HUB_FILE_MARKER}" in hub_db_line
    assert "--build" not in hub_db_line
    # --no-deps: `run` must never recreate a diverged db that `--no-recreate db` just left alone.
    cluster_init_line = _single_line_containing(
        output, " run --rm --no-deps cluster-init"
    )
    up_index = lines.index(_compose_up_line(output))
    assert lines.index(hub_db_line) < lines.index(cluster_init_line) < up_index
    assert not [line for line in _hub_lines(output) if "--build" in line]


def test_up_with_a_profile_starts_hub_playwright() -> None:
    output = _successful_dry_run("up", "p=ui")
    lines = output.splitlines()
    playwright_up_line = _hub_playwright_up_line(output)
    assert HUB_FILE_MARKER in playwright_up_line
    assert lines.index(playwright_up_line) < lines.index(_compose_up_line(output))


def test_bare_up_leaves_hub_playwright_alone() -> None:
    output = _successful_dry_run("up")
    assert not [line for line in _hub_lines(output) if "playwright" in line]


@pytest.mark.parametrize("make_target", ["up-built", "start-built"])
def test_built_stack_starts_hub_playwright(make_target: str) -> None:
    output = _successful_dry_run(make_target)
    lines = output.splitlines()
    first_spoke_compose_index = next(
        index
        for index, line in enumerate(lines)
        if "docker compose" in line and HUB_FILE_MARKER not in line
    )
    assert lines.index(_hub_playwright_up_line(output)) < first_spoke_compose_index


def test_tunnel_needs_no_hub_playwright() -> None:
    output = _successful_dry_run("tunnel")
    _hub_db_up_line(output)
    assert not [line for line in _hub_lines(output) if "playwright" in line]
    assert _single_line_containing(output, " rm -sf ").endswith("rm -sf workflow")


@pytest.mark.parametrize("make_target", ["up", "up-built", "start-built", "tunnel"])
def test_stack_start_targets_run_worktree_init_first(make_target: str) -> None:
    # make -n is safe here: none of these targets or their prerequisites recurse via $(MAKE).
    lines = _successful_dry_run(make_target, "U4I_PRIMARY=1").splitlines()
    init_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "worktree-init: primary clone, nothing to link" in line
        ),
        None,
    )
    assert init_index is not None, lines
    first_compose_index = next(
        index for index, line in enumerate(lines) if "docker compose" in line
    )
    assert init_index < first_compose_index


def test_down_leaves_the_hub_alone() -> None:
    assert _hub_lines(_successful_dry_run("down")) == []


def test_hub_down_is_its_own_target() -> None:
    lines = _successful_dry_run("hub-down").splitlines()
    hub_down_line = _single_line_containing(
        "\n".join(lines), f"{ALL_PROFILES_FLAG} down"
    )
    assert HUB_FILE_MARKER in hub_down_line
    assert f"-p u4i-hub-{os.getuid()} " in hub_down_line
    attachment_check_index = next(
        index
        for index, line in enumerate(lines)
        if f"docker ps -a --filter network=u4i-shared-{os.getuid()} " in line
        and "spokes still attached" in line
    )
    assert attachment_check_index < lines.index(hub_down_line)
    network_rm_line = _single_line_containing(
        "\n".join(lines), f"docker network rm u4i-shared-{os.getuid()}"
    )
    assert lines.index(hub_down_line) < lines.index(network_rm_line)


@pytest.mark.skipif(GIT_BINARY is None, reason="needs `git`")
def test_hub_compose_uses_the_primary_clones_files() -> None:
    primary_root = _primary_root()
    hub_db_line = _hub_db_up_line(_successful_dry_run("hub-up"))
    assert f"--project-directory {primary_root} " in hub_db_line
    assert f"--env-file {primary_root}/.env " in hub_db_line
    assert f"-p u4i-hub-{os.getuid()} " in hub_db_line


def test_hub_up_creates_the_shared_network_first() -> None:
    lines = _successful_dry_run("hub-up").splitlines()
    network_line = _single_line_containing(
        "\n".join(lines), f"docker network create u4i-shared-{os.getuid()}"
    )
    assert lines.index(network_line) < lines.index(_hub_db_up_line("\n".join(lines)))


@pytest.mark.parametrize(
    "make_target",
    ["metrics-rows", "metrics-clear-rows", "gauge-rows", "gauge-clear-rows"],
)
def test_metrics_rows_queries_the_hub_db(make_target: str) -> None:
    exec_line = _single_line_containing(
        _successful_dry_run(make_target, "U4I_SLUG=wt-a"), " exec db "
    )
    assert HUB_FILE_MARKER in exec_line
    assert '-d "u4i_dev_wt_a"' in exec_line


def test_stack_info_lists_attached_spokes() -> None:
    output = _successful_dry_run("stack-info")
    assert f"docker network inspect u4i-shared-{os.getuid()}" in output
    assert "hub: not running" in output
    assert f"docker ps -a --filter network=u4i-shared-{os.getuid()} " in output
    assert (
        f"--filter label=com.docker.compose.project=u4i-hub-{os.getuid()} "
        "--filter label=com.docker.compose.service=db --filter status=running"
    ) in output


def test_attached_spokes_exclude_the_hub_by_project_label() -> None:
    hub_down_check_line = _single_line_containing(
        _successful_dry_run("hub-down"), "spokes still attached"
    )
    assert '{{.Label "com.docker.compose.project"}} {{.Names}}' in hub_down_check_line
    assert f"-v hub='u4i-hub-{os.getuid()}'" in hub_down_check_line
    assert "$1 != hub" in hub_down_check_line


@pytest.mark.skipif(GIT_BINARY is None, reason="needs `git`")
def test_hub_up_ensures_the_primary_capacity_file_before_the_hub_db() -> None:
    # A prerequisite, so HUB_COMPOSE's wildcard (expanded with hub-up's recipe) sees a file made on this run.
    output = _successful_dry_run("hub-up")
    lines = output.splitlines()
    ensure_line = _single_line_containing(
        output,
        f"capacity.py ensure --output {_primary_root()}/docker/.capacity.generated.env",
    )
    assert lines.index(ensure_line) < lines.index(_hub_db_up_line(output))


@pytest.mark.parametrize(
    "make_args",
    [
        pytest.param(("start-built",), id="start-built"),
        pytest.param(("tunnel",), id="tunnel"),
        pytest.param(("up-built", "d=1"), id="up-built-detached"),
        pytest.param(("up-built", "p=full", "d=1"), id="up-built-full-detached"),
    ],
)
def test_built_stack_waits_for_the_vite_build_before_web(
    make_args: tuple[str, ...],
) -> None:
    # `up --wait` fails once the unreferenced one-shot vite exits, so the build starts detached, the vite
    # barrier blocks on it, and only then does a waiting `up` target web.
    make_target = make_args[0]
    output = _successful_dry_run(*make_args)
    lines = output.splitlines()
    build_up_line = _compose_up_line(output)
    assert " --wait" not in build_up_line
    # The barrier is one make variable, so its backslash-continued shell prints as one line.
    barrier_line = _single_line_containing(output, "docker wait ")
    assert f"{make_target}: the vite asset build exited" in barrier_line
    assert '[ "$vite_exit" != 0 ]' in barrier_line
    assert barrier_line.endswith("exit 1; fi")
    web_wait_line = _single_line_containing(output, " up --wait web")
    assert (
        lines.index(build_up_line)
        < lines.index(barrier_line)
        < lines.index(web_wait_line)
    )


def test_attached_up_built_streams_without_a_barrier() -> None:
    # Without d=1 the `up` stays attached until Ctrl-C (which stops the stack), so there is no later point to wait at.
    output = _successful_dry_run("up-built")
    assert " -d" not in _compose_up_line(output)
    assert "docker wait " not in output
    assert " up --wait web" not in output


def test_hub_named_spoke_slug_is_rejected() -> None:
    result = _dry_run("stack-info", f"U4I_SLUG=hub-{os.getuid()}")
    assert result.returncode != 0
    assert "U4I_SLUG" in result.stderr


def test_hub_targets_require_the_primary_hub_file() -> None:
    result = _dry_run("hub-up", "PRIMARY_ROOT=/nonexistent-u4i-root")
    assert result.returncode != 0
    assert (
        "the primary clone (/nonexistent-u4i-root) must be a git checkout carrying "
        "docker/compose.hub.yaml"
    ) in result.stderr


@pytest.mark.parametrize(
    ("make_target", "service_value"),
    [
        pytest.param("restart", "web;id", id="shell-metachar"),
        pytest.param("logs", "web id", id="two-words"),
    ],
)
def test_service_name_must_be_one_compose_service(
    make_target: str, service_value: str
) -> None:
    result = _dry_run(make_target, f"c={service_value}")
    assert result.returncode != 0
    assert "c must be one compose service name ([a-z0-9_-])" in result.stderr


def test_restart_accepts_a_dashed_service_name() -> None:
    restart_line = _single_line_containing(
        _successful_dry_run("restart", "c=redis-metrics"), " restart "
    )
    assert restart_line.endswith("restart redis-metrics")
