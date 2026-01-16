from typing import Generator
from flask import Flask
import pytest


@pytest.fixture
def logged_out_app(app_with_server_name: Flask) -> Generator[Flask, None, None]:
    with app_with_server_name.app_context():
        yield app_with_server_name
