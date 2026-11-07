import re

import pytest

from backend.cli.mock_constants import MOCK_INVITE_LINK_STATES, MOCK_UTUB_NAME_BASE
from backend.cli.mock_data.invite_links import get_mock_invite_token
from backend.db import db
from backend.invite_links.constants import INVITE_LINK_TOKEN_LENGTH
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utubs import Utubs
from backend.utils.strings.config_strs import CONFIG_ENVS

pytestmark = pytest.mark.cli

# The shared token pattern is anchored (^...\Z); this finds a token inside CLI output.
INVITE_PATH_REGEX = re.compile(rf"/invite/[A-Za-z0-9_-]{{{INVITE_LINK_TOKEN_LENGTH}}}")
ALL_LABELS = [state.label for state in MOCK_INVITE_LINK_STATES]


@pytest.fixture(autouse=True)
def local_dev_signal(runner, monkeypatch):
    """Turn on the positive local-dev signal the command requires."""
    app, _ = runner
    monkeypatch.setitem(app.config, CONFIG_ENVS.VITE_DEV_SERVER, True)


def _seeded_token(app, index: int) -> str:
    utub_name = f"{MOCK_UTUB_NAME_BASE}{index + 1}"
    with app.app_context():
        utub = Utubs.query.filter(Utubs.name == utub_name).order_by(Utubs.id).first()
        assert utub is not None
        link = (
            Utub_Invite_Links.query.filter_by(utub_id=utub.id)
            .order_by(Utub_Invite_Links.id.desc())
            .first()
        )
        assert link is not None
        return link.token


@pytest.mark.parametrize("label", ALL_LABELS)
def test_invite_token_prints_seeded_path_for_every_state(runner, label):
    """
    GIVEN a database seeded with `addmock all`
    WHEN `addmock invite-token <label>` runs for each MOCK_INVITE_LINK_STATES label
    THEN it exits 0 and prints exactly `/invite/<token>` for that state's seeded row
    """
    app, cli_runner = runner
    cli_runner.invoke(args=["addmock", "all"])

    result = cli_runner.invoke(args=["addmock", "invite-token", label])

    index = ALL_LABELS.index(label)
    assert result.exit_code == 0
    assert result.output.strip() == f"/invite/{_seeded_token(app, index)}"


def test_invite_token_unknown_label_exits_non_zero(runner):
    """
    GIVEN a seeded database
    WHEN `addmock invite-token` gets a label outside the closed set
    THEN click rejects it with a non-zero exit and no token is printed
    """
    _, cli_runner = runner
    cli_runner.invoke(args=["addmock", "all"])

    result = cli_runner.invoke(args=["addmock", "invite-token", "not_a_state"])

    assert result.exit_code == 2
    assert "Invalid value" in result.output
    assert INVITE_PATH_REGEX.search(result.output) is None


def test_invite_token_missing_row_exits_non_zero_with_message(runner):
    """
    GIVEN an unseeded database
    WHEN `addmock invite-token live_unlimited` runs
    THEN it exits non-zero with a message and prints no token
    """
    app, cli_runner = runner

    result = cli_runner.invoke(args=["addmock", "invite-token", ALL_LABELS[0]])

    assert result.exit_code != 0
    assert "No seeded invite link" in result.output
    assert INVITE_PATH_REGEX.search(result.output) is None
    with app.app_context():
        assert get_mock_invite_token(ALL_LABELS[0]) is None


@pytest.mark.parametrize("env_flag", [CONFIG_ENVS.PRODUCTION, CONFIG_ENVS.DEV_SERVER])
def test_invite_token_refuses_on_deployed_config(runner, monkeypatch, env_flag):
    """
    GIVEN a seeded database and PRODUCTION or DEV_SERVER config
    WHEN `addmock invite-token live_unlimited` runs
    THEN it exits 1 with the refusal message and prints no token
    """
    app, cli_runner = runner
    seed = cli_runner.invoke(args=["addmock", "all"])
    assert seed.exit_code == 0
    token = _seeded_token(app, 0)
    monkeypatch.setitem(app.config, env_flag, True)

    result = cli_runner.invoke(args=["addmock", "invite-token", ALL_LABELS[0]])

    assert result.exit_code == 1
    assert "Cannot print invite tokens" in result.output
    assert token not in result.output
    assert INVITE_PATH_REGEX.search(result.output) is None


def test_invite_token_refuses_without_local_dev_signal(runner, monkeypatch):
    """
    GIVEN a seeded database and neither PRODUCTION nor DEV_SERVER, but no local-dev signal
    WHEN `addmock invite-token live_unlimited` runs
    THEN it exits 1 with the refusal message and prints no token
    """
    app, cli_runner = runner
    seed = cli_runner.invoke(args=["addmock", "all"])
    assert seed.exit_code == 0
    token = _seeded_token(app, 0)
    monkeypatch.setitem(app.config, CONFIG_ENVS.PRODUCTION, False)
    monkeypatch.setitem(app.config, CONFIG_ENVS.DEV_SERVER, False)
    monkeypatch.setitem(app.config, CONFIG_ENVS.VITE_DEV_SERVER, False)

    result = cli_runner.invoke(args=["addmock", "invite-token", ALL_LABELS[0]])

    assert result.exit_code == 1
    assert "Cannot print invite tokens" in result.output
    assert token not in result.output
    assert INVITE_PATH_REGEX.search(result.output) is None


def test_invite_token_utub_without_invite_row_exits_non_zero(runner):
    """
    GIVEN a seeded database where a state's invite row was deleted
    WHEN `addmock invite-token <label>` runs for that state
    THEN it exits non-zero with the missing-seed message
    """
    app, cli_runner = runner
    cli_runner.invoke(args=["addmock", "all"])
    with app.app_context():
        Utub_Invite_Links.query.delete()
        db.session.commit()

    result = cli_runner.invoke(args=["addmock", "invite-token", ALL_LABELS[0]])

    assert result.exit_code == 1
    assert "No seeded invite link" in result.output


def test_addmock_all_output_never_contains_a_token(runner):
    """
    GIVEN an unseeded database
    WHEN `addmock all` runs (twice, so the already-added branch also prints)
    THEN neither output contains an invite token or any seeded token
    """
    app, cli_runner = runner

    first = cli_runner.invoke(args=["addmock", "all"])
    second = cli_runner.invoke(args=["addmock", "all"])

    tokens = [_seeded_token(app, index) for index in range(len(ALL_LABELS))]
    for output in (first.output, second.output):
        assert "/invite/" not in output
        for token in tokens:
            assert token not in output
