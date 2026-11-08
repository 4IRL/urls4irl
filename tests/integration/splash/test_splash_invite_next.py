"""Splash ``next=/invite/<token>`` handoff: modal hint and authenticated redirect."""

from urllib.parse import quote, urlsplit

import pytest
from flask import Flask, url_for

from backend import db
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.splash_form_strs import REGISTER_FORM

pytestmark = pytest.mark.splash

TOKEN = "A" * 22
TOKEN_2 = "B" * 22
HINT_ATTRIBUTE = b"data-auth-modal-hint"
SPLASH_CONFIG_MARKER = b'id="splashConfig"'

REJECTED_NEXT_VALUES = [
    f"/invite/{TOKEN[:21]}",
    f"/invite/{TOKEN}A",
    f"/invite/{TOKEN}/",
    f"/invite/{TOKEN}/join",
    f"/invite/{TOKEN}?x=1",
    f"//evil.example/invite/{TOKEN}",
    f"https://evil.example/invite/{TOKEN}",
    f"/INVITE/{TOKEN}",
    "",
]


@pytest.mark.parametrize(
    "next_value,hint",
    [(f"/invite/{TOKEN}", "login"), (f"/invite/{TOKEN}/register", "register")],
)
def test_anonymous_valid_invite_next_renders_hint(
    app: Flask, next_value: str, hint: str
):
    """
    GIVEN an anonymous visitor
    WHEN they load / with a valid invite next
    THEN #splashConfig carries the matching modal hint
    """
    response = app.test_client().get(f"/?next={quote(next_value, safe='')}")

    assert response.status_code == 200
    assert f'data-auth-modal-hint="{hint}"'.encode() in response.data


@pytest.mark.parametrize("next_value", REJECTED_NEXT_VALUES)
def test_anonymous_rejected_next_renders_no_hint(app: Flask, next_value: str):
    """
    GIVEN an anonymous visitor
    WHEN they load / with a next that is not a valid invite path
    THEN the page renders with #splashConfig and no hint attribute
    """
    response = app.test_client().get(f"/?next={quote(next_value, safe='')}")

    assert response.status_code == 200
    assert SPLASH_CONFIG_MARKER in response.data
    assert HINT_ATTRIBUTE not in response.data


@pytest.mark.parametrize(
    "query",
    [
        f"next=/invite/{TOKEN}&x=1",
        f"next=/invite/{TOKEN}&next=/invite/{TOKEN_2}",
        f"next=/invite/{TOKEN}&email_change_status=confirmed",
        "email_change_status=confirmed",
        "",
    ],
)
def test_anonymous_sibling_duplicate_or_missing_next_renders_no_hint(
    app: Flask, query: str
):
    """
    GIVEN an anonymous visitor
    WHEN they load / with a sibling param, a repeated next, or no next
    THEN the page renders with #splashConfig and no hint attribute
    """
    response = app.test_client().get(f"/?{query}")

    assert response.status_code == 200
    assert SPLASH_CONFIG_MARKER in response.data
    assert HINT_ATTRIBUTE not in response.data


def test_expired_confirm_render_has_no_hint(
    app: Flask, register_first_user_without_email_validation, load_register_page
):
    """
    GIVEN an expired email validation token
    WHEN /validate/expired renders the splash page
    THEN it carries no modal hint
    """
    registered_user, _ = register_first_user_without_email_validation
    client, _ = load_register_page

    with app.app_context():
        user: Users = Users.query.filter(
            Users.email == registered_user[REGISTER_FORM.EMAIL].lower()
        ).first()
        expired_token = user.get_email_validation_token(expires_in=0)
        user.email_confirm = Email_Validations(validation_token=expired_token)
        db.session.commit()

    response = client.get(
        url_for(
            "splash.validate_email_expired",
            token=expired_token,
            next=f"/invite/{TOKEN}",
        )
    )

    assert response.status_code == 200
    assert HINT_ATTRIBUTE not in response.data


@pytest.mark.parametrize(
    "next_value", [f"/invite/{TOKEN}", f"/invite/{TOKEN}/register"]
)
def test_authenticated_valid_invite_next_redirects_to_bare_invite(
    register_first_user, login_first_user_without_register, next_value: str
):
    """
    GIVEN a confirmed, logged in user
    WHEN they load / with a valid invite next (live or not: no lookup)
    THEN they get a 302 to the bare /invite/<token>
    """
    client, _, _, _ = login_first_user_without_register

    response = client.get(f"/?next={quote(next_value, safe='')}")

    assert response.status_code == 302
    assert urlsplit(response.location).path == f"/invite/{TOKEN}"


@pytest.mark.parametrize(
    "query",
    [
        f"next=/invite/{TOKEN}&x=1",
        f"next=/invite/{TOKEN}&next=/invite/{TOKEN_2}",
        f"next=/invite/{TOKEN[:21]}",
        "next=%2F%2Fevil.example",
        "",
    ],
)
def test_authenticated_other_cases_redirect_home(
    register_first_user, login_first_user_without_register, query: str
):
    """
    GIVEN a confirmed, logged in user
    WHEN they load / with an invalid, sibling or repeated next, or none
    THEN they get a 302 to HOME, never the invite
    """
    client, _, _, _ = login_first_user_without_register

    response = client.get(f"/?{query}")

    assert response.status_code == 302
    assert urlsplit(response.location).path == url_for(ROUTES.UTUBS.HOME)
