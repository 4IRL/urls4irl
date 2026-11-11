"""Pin `.github/workflows/notifs-exchange.yml` and `.notifs/manifest.json` (host-static; YAML and JSON only).

The workflow is never run. Contracts pinned here: triggers, permissions, concurrency on the job, the job guard
(through a tiny `if:` evaluator that rejects anything it does not understand), the step order, the one-SHA rule
for the 4irl-notifs pins, the write/post-write `if:` strings that rely on `continue-on-error`, and the manifest
contents against the pinned job check names.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
WORKFLOWS: Path = REPO_ROOT / ".github" / "workflows"

# `.github/` and `.notifs/` are not mounted into the `web` image, so the module skips there and runs host-side.
# The skip looks at the workflows directory, never at the files under test: a missing file must fail.
pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        not WORKFLOWS.is_dir(),
        reason="needs the repo's .github/workflows (absent inside the web container)",
    ),
]

EXCHANGE: Path = WORKFLOWS / "notifs-exchange.yml"
PROD_BUILD_AND_DEPLOY: Path = WORKFLOWS / "prod-build-and-deploy.yml"
PROD_DEPLOY: Path = WORKFLOWS / "prod-deploy.yml"
MANIFEST: Path = REPO_ROOT / ".notifs" / "manifest.json"
FIXTURES: Path = Path(__file__).resolve().parent / "fixtures" / "notifs_exchange"

JOB_NAME: str = "exchange"
SETUP_NODE_SHA: str = "6044e13b5dc448c55e2357c09f80417699197238"
ACTION_USES = re.compile(
    r"^4IRL/4irl-notifs/\.github/actions/notifs-app@(?P<sha>[0-9a-f]{40})(?: #.*)?$"
)
CHECKOUT_PREFIX: str = "actions/checkout@"
KEY_PRESENT_IF: str = "steps.notifs.outputs.key != ''"
FINAL_IF: str = "always() && steps.notifs.outcome == 'failure'"
JOB_IF: str = (
    "github.ref == 'refs/heads/main' && (github.event_name == 'workflow_dispatch' "
    "|| github.event.workflow_run.conclusion == 'success')"
)
# check name -> the script (relative to scripts/) that pings it; daily_backup is a shell script
CHECK_SCRIPTS: dict[str, str] = {
    "daily_backup": "daily-docker.sh",
    "metrics_flush": "flush_metrics.py",
    "gauge_sample": "sample_gauges.py",
    "purge_audit_log": "purge_audit_log.py",
    "purge_trash": "purge_trash.py",
    "purge_short_links": "purge_short_links.py",
    "purge_invite_links": "purge_invite_links.py",
}
MIN_SECONDS: int = 60
_DURATION = re.compile(r"^(?P<count>\d+)(?P<unit>[smhd])$")
_UNIT_SECONDS: dict[str, int] = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_ENV_REFERENCE = "env"


def _workflow() -> dict[Any, Any]:
    return yaml.safe_load(EXCHANGE.read_text())


def _job() -> dict[str, Any]:
    return _workflow()["jobs"][JOB_NAME]


def _steps() -> list[dict[str, Any]]:
    return _job()["steps"]


def _index_where(predicate: Any) -> int:
    matches = [index for index, step in enumerate(_steps()) if predicate(step)]
    assert len(matches) == 1, matches
    return matches[0]


def _by_id(step_id: str) -> dict[str, Any]:
    return _steps()[_index_where(lambda step: step.get("id") == step_id)]


def _index_by_id(step_id: str) -> int:
    return _index_where(lambda step: step.get("id") == step_id)


def _is_checkout(step: dict[str, Any]) -> bool:
    return str(step.get("uses", "")).startswith(CHECKOUT_PREFIX)


def _checkouts() -> list[dict[str, Any]]:
    return [step for step in _steps() if _is_checkout(step)]


def _exchange_sha() -> str:
    match = ACTION_USES.match(_by_id("notifs")["uses"])
    assert match is not None
    return match.group("sha")


def _seconds(value: str) -> int:
    match = _DURATION.match(value)
    assert match is not None, value
    return int(match.group("count")) * _UNIT_SECONDS[match.group("unit")]


# ---------------------------------------------------------------------------
# A minimal `if:` evaluator: ==, &&, ||, parentheses, string literals, dotted lookups.
# ---------------------------------------------------------------------------

_TOKEN = re.compile(
    r"\s*(?:(?P<op>==|&&|\|\||\(|\))|'(?P<string>[^']*)'|(?P<name>[A-Za-z_][A-Za-z0-9_.-]*))"
)


def _tokenize(expression: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    position = 0
    while position < len(expression):
        if expression[position:].strip() == "":
            break
        match = _TOKEN.match(expression, position)
        if match is None or match.end() == position:
            raise ValueError(f"cannot parse expression at: {expression[position:]!r}")
        kind = match.lastgroup or ""
        tokens.append((kind, match.group(kind)))
        position = match.end()
    return tokens


def _lookup(path: str, context: dict[str, Any]) -> Any:
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def evaluate_condition(expression: str, context: dict[str, Any]) -> bool:
    """Evaluate a restricted GitHub `if:`; any construct outside the grammar raises ValueError."""
    tokens = _tokenize(expression)
    position = 0

    def peek() -> tuple[str, str] | None:
        return tokens[position] if position < len(tokens) else None

    def take() -> tuple[str, str]:
        nonlocal position
        token = peek()
        if token is None:
            raise ValueError("unexpected end of expression")
        position += 1
        return token

    def parse_or() -> Any:
        value = parse_and()
        while peek() == ("op", "||"):
            take()
            right = parse_and()
            value = bool(value) or bool(right)
        return value

    def parse_and() -> Any:
        value = parse_equality()
        while peek() == ("op", "&&"):
            take()
            right = parse_equality()
            value = bool(value) and bool(right)
        return value

    def parse_equality() -> Any:
        value = parse_atom()
        while peek() == ("op", "=="):
            take()
            right = parse_atom()
            value = value == right
        return value

    def parse_atom() -> Any:
        kind, text = take()
        if kind == "string":
            return text
        if kind == "name":
            return _lookup(text, context)
        if (kind, text) == ("op", "("):
            value = parse_or()
            if take() != ("op", ")"):
                raise ValueError("missing closing parenthesis")
            return value
        raise ValueError(f"unexpected token {text!r}")

    result = parse_or()
    if position != len(tokens):
        raise ValueError(f"trailing tokens: {tokens[position:]}")
    return bool(result)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


# ---------------------------------------------------------------------------
# Triggers, permissions, concurrency
# ---------------------------------------------------------------------------


def test_triggers_are_exactly_workflow_run_and_dispatch():
    """
    GIVEN the exchange workflow
    WHEN its triggers are read (YAML loads `on` as True)
    THEN they are the deploy workflow's completed event and a dispatch with one optional sha input.
    """
    triggers = _workflow()[True]
    deploy_name = yaml.safe_load(PROD_BUILD_AND_DEPLOY.read_text())["name"]

    assert set(triggers) == {"workflow_run", "workflow_dispatch"}
    assert triggers["workflow_run"] == {
        "workflows": [deploy_name],
        "types": ["completed"],
    }
    assert set(triggers["workflow_dispatch"]["inputs"]) == {"sha"}
    sha_input = triggers["workflow_dispatch"]["inputs"]["sha"]
    assert sha_input["type"] == "string"
    assert sha_input["default"] == ""
    assert not sha_input["required"]


def test_only_the_exchange_job_holds_id_token():
    """
    GIVEN the workflow and both deploy workflows
    WHEN permissions are read
    THEN top-level permissions are empty, only job exchange has id-token: write, the deploy files never mention it.
    """
    workflow = _workflow()

    assert workflow["permissions"] == {}
    assert list(workflow["jobs"]) == [JOB_NAME]
    assert _job()["permissions"] == {"contents": "read", "id-token": "write"}
    for deploy in (PROD_BUILD_AND_DEPLOY, PROD_DEPLOY):
        assert "id-token" not in deploy.read_text()


def test_no_environment_on_workflow_or_job():
    """
    GIVEN the workflow
    WHEN the job is read
    THEN it declares no environment (it would become part of the bound identity).
    """
    assert "environment" not in _job()
    assert "environment" not in _workflow()


def test_concurrency_is_on_the_job_and_never_cancels():
    """
    GIVEN the workflow
    WHEN concurrency is read
    THEN the fixed group with cancel-in-progress false is on the exchange job, not the workflow.
    """
    assert "concurrency" not in _workflow()
    assert _job()["concurrency"] == {
        "group": "notifs-exchange-urls4irl",
        "cancel-in-progress": False,
    }


# ---------------------------------------------------------------------------
# The job guard
# ---------------------------------------------------------------------------


def test_job_guard_is_exact():
    """
    GIVEN the exchange job
    WHEN its `if:` is read
    THEN it is exactly the documented guard.
    """
    assert _job()["if"] == JOB_IF


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("workflow_run_success_main.json", True),
        ("workflow_run_failure_main.json", False),
        ("dispatch_main.json", True),
        ("dispatch_other_ref.json", False),
    ],
)
def test_job_guard_against_event_fixtures(fixture: str, expected: bool):
    """
    GIVEN real-shaped event contexts
    WHEN the job guard is evaluated
    THEN a successful deploy on main and a dispatch from main run; a failed deploy and another ref do not.
    """
    assert evaluate_condition(_job()["if"], _fixture(fixture)) is expected


@pytest.mark.parametrize(
    "expression",
    [
        "success()",
        "github.ref != 'refs/heads/main'",
        "!github.ref",
        "contains(github.ref, 'main')",
        'github.ref == "refs/heads/main"',
        "github.ref == 'refs/heads/main' &&",
        "(github.ref == 'refs/heads/main'",
    ],
)
def test_evaluator_rejects_what_it_does_not_understand(expression: str):
    """
    GIVEN an expression outside the evaluator's grammar
    WHEN it is evaluated
    THEN it raises, so a guard edit breaks the test instead of passing.
    """
    with pytest.raises(ValueError):
        evaluate_condition(expression, _fixture("dispatch_main.json"))


# ---------------------------------------------------------------------------
# Step order and contents
# ---------------------------------------------------------------------------


def test_step_order_is_the_contract():
    """
    GIVEN the job steps
    WHEN their positions are compared
    THEN script checkout < resolve < manifest fetch < preflight < setup-node < lint < exchange < write
        < post-write < final.
    """
    script_checkout, notifs_checkout = _checkouts()
    steps = _steps()
    preflight = _index_where(
        lambda step: "--check /home/u4i/notifs-key" in step.get("run", "")
    )
    setup_node = _index_where(
        lambda step: str(step.get("uses", "")).startswith("actions/setup-node@")
    )
    post_write = _index_where(
        lambda step: (
            "docker exec" in step.get("run", "") and "sha256sum" in step.get("run", "")
        )
    )
    positions = [
        steps.index(script_checkout),
        _index_by_id("resolve"),
        _index_by_id("manifest"),
        preflight,
        steps.index(notifs_checkout),
        setup_node,
        _index_by_id("lint"),
        _index_by_id("notifs"),
        _index_by_id("write"),
        post_write,
        len(steps) - 1,
    ]

    assert positions == sorted(positions)
    assert len(set(positions)) == len(positions)
    assert steps[-1]["if"] == FINAL_IF
    assert steps.index(script_checkout) == 0


def test_script_checkout_is_sparse_pinned_and_credentialless():
    """
    GIVEN the first checkout
    WHEN its inputs are read
    THEN it is SHA-pinned, fetches only the resolve script (cone mode off) into its own path, with no credentials.
    """
    script_checkout = _checkouts()[0]
    inputs = script_checkout["with"]

    assert re.fullmatch(
        r"actions/checkout@[0-9a-f]{40}( #.*)?", script_checkout["uses"]
    )
    assert inputs["sparse-checkout"].strip() == "scripts/notifs-resolve-release-sha.sh"
    assert inputs["sparse-checkout-cone-mode"] is False
    assert inputs["persist-credentials"] is False
    assert "ref" not in inputs
    assert "repository" not in inputs


def test_resolve_step_passes_inputs_through_env_only():
    """
    GIVEN the resolve step
    WHEN its env and run text are read
    THEN env has the five inputs and the run text has no `${{` expression.
    """
    resolve = _by_id("resolve")

    assert {
        "GH_TOKEN",
        "GH_REPO",
        "EVENT_NAME",
        "RUN_HEAD_SHA",
        "INPUT_SHA",
    } <= set(resolve["env"])
    assert "${{" not in resolve["run"]
    assert "resolve-src/scripts/notifs-resolve-release-sha.sh" in resolve["run"]


def test_manifest_is_fetched_by_api_never_checked_out():
    """
    GIVEN the manifest step
    WHEN its inputs are read
    THEN it downloads only .notifs/manifest.json at the resolved sha through the contents API, and
        the ref is never checked out (only the resolve script and the pinned 4irl-notifs are).
    """
    manifest = _by_id("manifest")

    assert not _is_checkout(manifest)
    assert manifest["env"]["MANIFEST_SHA"] == "${{ steps.resolve.outputs.sha }}"
    assert "contents/.notifs/manifest.json?ref=${MANIFEST_SHA}" in manifest["run"]
    assert "> release/.notifs/manifest.json" in manifest["run"]
    for checkout in _checkouts():
        assert "steps.resolve.outputs.sha" not in str(checkout.get("with", {}))


def test_checkout_paths_are_distinct():
    """
    GIVEN the two checkouts and the manifest download directory
    WHEN their paths are read
    THEN every path is different.
    """
    script_checkout, notifs_checkout = _checkouts()

    paths = [
        script_checkout["with"]["path"],
        notifs_checkout["with"]["path"],
        "release",
    ]
    assert len(set(paths)) == 3


def test_manifest_paths_point_under_the_manifest_checkout():
    """
    GIVEN the lint step and the exchange step
    WHEN their manifest arguments are read
    THEN both point at .notifs/manifest.json under the manifest checkout's path.
    """
    manifest_path = "release"
    lint = _by_id("lint")
    notifs = _by_id("notifs")

    assert notifs["with"]["manifest"] == f"{manifest_path}/.notifs/manifest.json"
    assert lint["env"]["MANIFEST"] == (
        f"${{{{ github.workspace }}}}/{manifest_path}/.notifs/manifest.json"
    )
    assert '--manifest "$MANIFEST"' in lint["run"]
    assert "--target app" in lint["run"]
    notifs_path = _checkouts()[1]["with"]["path"]
    assert f"node {notifs_path}/scripts/onboard.mjs lint" in lint["run"]


def test_lint_checkout_sha_equals_the_exchange_action_sha():
    """
    GIVEN the 4irl-notifs checkout and the exchange action pin
    WHEN both SHAs are compared
    THEN they are the same 40-hex SHA, so a bump of one without the other fails.
    """
    notifs_checkout = _checkouts()[1]

    assert notifs_checkout["with"]["repository"] == "4IRL/4irl-notifs"
    assert notifs_checkout["with"]["ref"] == _exchange_sha()
    assert notifs_checkout["with"]["persist-credentials"] is False


def test_setup_node_is_pinned_and_precedes_lint():
    """
    GIVEN the setup-node step
    WHEN its pin and position are read
    THEN it is the action's own pinned SHA with node 24, unconditional, before the lint step.
    """
    index = _index_where(
        lambda step: str(step.get("uses", "")).startswith("actions/setup-node@")
    )
    step = _steps()[index]

    assert step["uses"].startswith(f"actions/setup-node@{SETUP_NODE_SHA}")
    assert step["with"]["node-version"] == "24"
    assert "if" not in step
    assert index < _index_by_id("lint")


def test_exchange_step_contract():
    """
    GIVEN the exchange step
    WHEN its fields are read
    THEN it is id notifs with continue-on-error, the right inputs and the manifest's env names.
    """
    step = _by_id("notifs")

    assert step["continue-on-error"] is True
    assert step["with"]["app_id"] == "urls4irl"
    assert step["with"]["delivery_url"] == "https://notifs-delivery.4irl.app"
    assert "if" not in step
    assert _index_by_id("lint") < _index_by_id("notifs")


def test_write_and_post_write_rely_on_implicit_success():
    """
    GIVEN the write and post-write steps
    WHEN their `if:` strings are read
    THEN each is exactly the key-present check (no status function), and the write step validates and exports host_hash.
    """
    write = _by_id("write")
    post_write = _steps()[
        _index_where(lambda step: "docker exec" in step.get("run", ""))
    ]

    assert write["if"] == KEY_PRESENT_IF
    assert post_write["if"] == KEY_PRESENT_IF
    assert "=~ ^[0-9a-f]{64}$" in write["run"]
    assert 'echo "host_hash=${host_hash}" >> "$GITHUB_OUTPUT"' in write["run"]


def test_write_step_keeps_secrets_out_of_command_text():
    """
    GIVEN the write step
    WHEN its run text and env are read
    THEN no `${{` expression is in the run text and key, client id and secret come from env.
    """
    write = _by_id("write")

    assert "${{" not in write["run"]
    assert write["env"]["NOTIFS_KEY"] == "${{ steps.notifs.outputs.key }}"
    assert write["env"]["NOTIFS_ACCESS_CLIENT_ID"] == (
        "${{ secrets.NOTIFS_ACCESS_CLIENT_ID }}"
    )
    assert write["env"]["NOTIFS_ACCESS_CLIENT_SECRET"] == (
        "${{ secrets.NOTIFS_ACCESS_CLIENT_SECRET }}"
    )
    assert "--write /home/u4i/notifs-key" in write["run"]
    assert "ssh " in write["run"]
    assert "$NOTIFS_KEY" in write["run"]


def test_post_write_reads_both_containers_as_the_shared_group():
    """
    GIVEN the post-write step
    WHEN its run text is read
    THEN it hashes the key inside the flask and workflow containers as uid 1001 and compares to the host hash.
    """
    post_write = _steps()[
        _index_where(lambda step: "docker exec" in step.get("run", ""))
    ]

    assert "docker exec -u 1001" in post_write["run"]
    assert "u4i-prod-flask" in post_write["run"]
    assert "u4i-prod-workflow" in post_write["run"]
    assert "/run/notifs/delivery_key" in post_write["run"]
    assert post_write["env"]["HOST_HASH"] == "${{ steps.write.outputs.host_hash }}"


def test_final_step_reports_the_action_outcome():
    """
    GIVEN the last step
    WHEN its `if:` and run text are read
    THEN it fires only on an exchange failure, prints the outcome and exits 1.
    """
    final = _steps()[-1]

    assert final["if"] == FINAL_IF
    assert "steps.notifs.outcome" in final["run"]
    assert "exit 1" in final["run"]


def test_cloudflared_is_pinned_and_checksum_verified():
    """
    GIVEN the Install Cloudflared step
    WHEN its env and run text are read
    THEN it downloads an exact version (never latest) and verifies a 64-hex sha256 before installing it.
    """
    step = _steps()[
        _index_where(lambda step: step.get("name") == "Install Cloudflared")
    ]
    run = step["run"]

    assert re.fullmatch(r"\d{4}\.\d{1,2}\.\d+", step["env"]["CLOUDFLARED_VERSION"])
    assert re.fullmatch(r"[0-9a-f]{64}", step["env"]["CLOUDFLARED_SHA256"])
    assert "latest" not in run
    assert "releases/download/${CLOUDFLARED_VERSION}/" in run
    assert run.index("sha256sum --check --strict") < run.index("install -m 0755")


def test_every_uses_is_pinned_by_full_sha():
    """
    GIVEN every `uses:` in the workflow
    WHEN the refs are read
    THEN each is a 40-hex SHA.
    """
    uses = [step["uses"] for step in _steps() if "uses" in step]

    assert uses
    for reference in uses:
        assert re.search(r"@[0-9a-f]{40}( #.*)?$", reference), reference


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text())


def _env_names(value: Any) -> set[str]:
    if isinstance(value, dict):
        names = {value[_ENV_REFERENCE]} if set(value) == {_ENV_REFERENCE} else set()
        for child in value.values():
            names |= _env_names(child)
        return names
    if isinstance(value, list):
        return set().union(*[_env_names(child) for child in value]) if value else set()
    return set()


def test_manifest_identity_and_destinations():
    """
    GIVEN the manifest
    WHEN it is parsed
    THEN the app id is urls4irl and every heartbeat destination is declared.
    """
    manifest = _manifest()
    declared = {destination["name"] for destination in manifest["destinations"]}

    assert manifest["app_id"] == "urls4irl"
    assert declared == {"urls4irl_ops"}
    for heartbeat in manifest["heartbeats"]:
        assert set(heartbeat["destinations"]) <= declared
    assert "routes" not in manifest


def test_manifest_env_references_are_supplied_by_the_exchange_step():
    """
    GIVEN the manifest's `{env: NAME}` references
    WHEN compared with the exchange step's env
    THEN every name is set there.
    """
    names = _env_names(_manifest())

    assert names == {"NOTIFICATION_URL"}
    assert names <= set(_by_id("notifs")["env"])


def test_manifest_heartbeats_match_the_pinged_checks():
    """
    GIVEN the manifest heartbeat names and the scripts that ping them
    WHEN compared
    THEN the sets are equal, names are unique, and each name appears in its script.
    """
    names = [heartbeat["name"] for heartbeat in _manifest()["heartbeats"]]

    assert len(names) == len(set(names))
    assert set(names) == set(CHECK_SCRIPTS)
    for name, script in CHECK_SCRIPTS.items():
        assert name in (REPO_ROOT / "scripts" / script).read_text(), (name, script)


def test_manifest_periods_and_graces_parse_and_meet_the_hub_minimum():
    """
    GIVEN each heartbeat's period and grace
    WHEN parsed
    THEN both are at least 60 seconds and match the planned values.
    """
    expected = {
        "daily_backup": ("24h", "3h"),
        "metrics_flush": ("1m", "5m"),
        "gauge_sample": ("1h", "30m"),
        "purge_audit_log": ("24h", "2h"),
        "purge_trash": ("24h", "2h"),
        "purge_short_links": ("24h", "2h"),
        "purge_invite_links": ("24h", "2h"),
    }

    for heartbeat in _manifest()["heartbeats"]:
        assert _seconds(heartbeat["period"]) >= MIN_SECONDS
        assert _seconds(heartbeat["grace"]) >= MIN_SECONDS
        assert (heartbeat["period"], heartbeat["grace"]) == expected[heartbeat["name"]]
