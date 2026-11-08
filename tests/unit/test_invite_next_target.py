import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.invite_links.next_target import (
    InviteNextTarget,
    invite_next_redirect_path,
    parse_invite_next,
)
from backend.invite_links.page_response import build_invite_splash_urls

pytestmark = pytest.mark.unit

TOKEN = "A" * 11 + "b_-" + "9" * 8
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_token_fixture_is_22_chars():
    assert len(TOKEN) == 22


@pytest.mark.parametrize(
    "value,hint",
    [(f"/invite/{TOKEN}", "login"), (f"/invite/{TOKEN}/register", "register")],
)
def test_accepts_both_shapes(value: str, hint: str):
    target = parse_invite_next(value)
    assert target == InviteNextTarget(token=TOKEN, hint=hint)
    assert invite_next_redirect_path(target) == f"/invite/{TOKEN}"


@pytest.mark.parametrize(
    "value",
    [
        f"/invite/{TOKEN[:21]}",
        f"/invite/{TOKEN}A",
        f"/invite/{TOKEN[:21]}.",
        f"/invite/{TOKEN[:21]}%",
        f"/invite/{TOKEN[:21]}+",
        f"/invite/{TOKEN[:21]} ",
        f"/invite/{TOKEN}\n",
        f"/invite/{TOKEN}/",
        f"/invite/{TOKEN}/register/",
        f"/invite/{TOKEN}/join",
        f"/invite/{TOKEN}/register/x",
        f"/invite/{TOKEN}?x=1",
        f"/invite/{TOKEN}#f",
        f"/invite/{TOKEN}/register?x=1",
        f"//evil.example/invite/{TOKEN}",
        f"https://evil.example/invite/{TOKEN}",
        f"/INVITE/{TOKEN}",
        "/invite/%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E%2E",
        f"/invite%2F{TOKEN}",
        "",
        None,
        5,
        [f"/invite/{TOKEN}"],
    ],
)
def test_rejects_everything_else(value: object):
    assert parse_invite_next(value) is None


def test_round_trip_with_splash_url_builder():
    login_url, register_url = build_invite_splash_urls(TOKEN)
    parsed = []
    for url in (login_url, register_url):
        next_value = parse_qs(urlsplit(url).query)["next"][0]
        parsed.append(parse_invite_next(next_value))
    assert parsed == [
        InviteNextTarget(token=TOKEN, hint="login"),
        InviteNextTarget(token=TOKEN, hint="register"),
    ]


_IMPORT_PROBE = (
    "import importlib, sys, types\n"
    "for name in ('backend', 'backend.invite_links'):\n"
    "    stub = types.ModuleType(name)\n"
    "    stub.__path__ = [ROOT + '/' + name.replace('.', '/')]\n"
    "    sys.modules[name] = stub\n"
    "importlib.import_module('backend.invite_links.next_target')\n"
    "loaded = [m for m in sys.modules if m.split('.')[0] == 'flask_login' "
    "or m == 'backend.models' or m.startswith('backend.models.') "
    "or m.startswith('backend.splash')]\n"
    "assert loaded == [], loaded\n"
)


def test_import_does_not_load_models_or_flask_login():
    # `backend/__init__.py` is the app factory, so stub the packages and import the
    # leaf module directly to prove its own import graph is clean.
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"ROOT = {str(PROJECT_ROOT)!r}\n" + _IMPORT_PROBE],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
