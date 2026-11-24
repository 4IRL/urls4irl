from typing import Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient
from markupsafe import escape

from backend.models.users import Users
from backend.utils.strings.invite_link_strs import INVITE_LINK_LEGAL

pytestmark = pytest.mark.splash

LEGAL_PAGES = [
    pytest.param("/terms", INVITE_LINK_LEGAL.TERMS_PREVIEW, id="terms"),
    pytest.param("/privacy-policy", INVITE_LINK_LEGAL.PRIVACY_PREVIEW, id="privacy"),
]


@pytest.mark.parametrize("path, sentence", LEGAL_PAGES)
def test_legal_page_shows_preview_sentence_logged_out(
    client: FlaskClient, path: str, sentence: str
) -> None:
    """
    GIVEN a visitor who is not logged in
    WHEN the Terms or the Privacy Policy is requested (GET)
    THEN the page returns 200 and renders the invite link preview sentence once
    """
    response = client.get(path)

    assert response.status_code == 200
    assert response.get_data(as_text=True).count(str(escape(sentence))) == 1


@pytest.mark.usefixtures("register_first_user")
@pytest.mark.parametrize("path, sentence", LEGAL_PAGES)
def test_legal_page_shows_preview_sentence_logged_in(
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    path: str,
    sentence: str,
) -> None:
    """
    GIVEN a logged-in user
    WHEN the Terms or the Privacy Policy is requested (GET)
    THEN the page returns 200 and renders the invite link preview sentence once
    """
    logged_in_client, _, _, _ = login_first_user_without_register

    response = logged_in_client.get(path)

    assert response.status_code == 200
    assert response.get_data(as_text=True).count(str(escape(sentence))) == 1
