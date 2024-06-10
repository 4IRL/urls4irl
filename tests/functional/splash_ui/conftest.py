# Standard library

# External libraries
import pytest

# Internal libraries


@pytest.fixture
def add_test_user(runner):
    app, cli_runner = runner
    cli_runner.invoke(args=["addmock", "users"])
