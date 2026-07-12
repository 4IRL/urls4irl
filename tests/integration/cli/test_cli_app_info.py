import pytest

from backend.cli.utils import (
    APP_INFO_ENV_LABEL,
    APP_INFO_NAME_LABEL,
)
from backend.utils.strings.config_strs import CONFIG_ENVS

pytestmark = pytest.mark.cli


def test_app_info_prints_name_and_env(runner):
    """
    GIVEN a running Flask app
    WHEN the developer runs `flask utils app-info`
    THEN verify the command exits with code 0 and prints the app name and
        environment labels
    """
    app, cli_runner = runner
    result = cli_runner.invoke(args=["utils", "app-info"])

    assert result.exit_code == 0
    assert app.name in result.output
    assert APP_INFO_NAME_LABEL in result.output
    assert APP_INFO_ENV_LABEL in result.output


def test_app_info_reports_testing_environment(runner):
    """
    GIVEN a running Flask app under ConfigTest (TESTING=True, PRODUCTION and
        DEV_SERVER False)
    WHEN the developer runs `flask utils app-info`
    THEN verify the environment line reports "testing"
    """
    app, cli_runner = runner
    result = cli_runner.invoke(args=["utils", "app-info"])

    assert result.exit_code == 0
    assert "testing" in result.output


def test_app_info_reports_production_environment(runner):
    """
    GIVEN a running Flask app with the PRODUCTION flag set
    WHEN the developer runs `flask utils app-info`
    THEN verify the environment line reports "production"
    """
    app, cli_runner = runner

    with app.app_context():
        app.config[CONFIG_ENVS.PRODUCTION] = True

    try:
        result = cli_runner.invoke(args=["utils", "app-info"])

        assert result.exit_code == 0
        assert "production" in result.output
    finally:
        with app.app_context():
            app.config[CONFIG_ENVS.PRODUCTION] = False


def test_app_info_reports_dev_server_environment(runner):
    """
    GIVEN a running Flask app with the DEV_SERVER flag set
    WHEN the developer runs `flask utils app-info`
    THEN verify the environment line reports "dev_server"
    """
    app, cli_runner = runner

    with app.app_context():
        app.config[CONFIG_ENVS.DEV_SERVER] = True

    try:
        result = cli_runner.invoke(args=["utils", "app-info"])

        assert result.exit_code == 0
        assert "dev_server" in result.output
    finally:
        with app.app_context():
            app.config[CONFIG_ENVS.DEV_SERVER] = False


def test_app_info_reports_local_environment(runner):
    """
    GIVEN a running Flask app with PRODUCTION, DEV_SERVER, and TESTING all off
    WHEN the developer runs `flask utils app-info`
    THEN verify the environment line reports "local"
    """
    app, cli_runner = runner

    with app.app_context():
        app.config[CONFIG_ENVS.PRODUCTION] = False
        app.config[CONFIG_ENVS.DEV_SERVER] = False
        app.config["TESTING"] = False

    try:
        result = cli_runner.invoke(args=["utils", "app-info"])

        assert result.exit_code == 0
        assert "local" in result.output
    finally:
        with app.app_context():
            app.config[CONFIG_ENVS.PRODUCTION] = False
            app.config[CONFIG_ENVS.DEV_SERVER] = False
            app.config["TESTING"] = True
