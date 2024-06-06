from typing import Generator, Tuple

from flask import Flask
from flask.testing import FlaskCliRunner
import pytest


@pytest.fixture
def runner(app) -> Generator[Tuple[Flask, FlaskCliRunner], None, None]:
    flask_app: Flask = app
    yield flask_app, flask_app.test_cli_runner()
