from typing import Tuple
from unittest.mock import MagicMock

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend.models.users import Users
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.trash_strs import TRASH_FAILURE
from backend.utubs.constants import TrashScope, UTubErrorCodes
from backend.utubs.services.empty_trash import empty_trash_for_user
from tests.integration.trash.trash_helpers import (
    FIRST_USER_ID,
    FIRST_UTUB_ID,
    count_url_tags_in_utub,
)
from tests.utils_for_test import trash_utub

pytestmark = pytest.mark.trash


def test_empty_trash_for_user_denies_an_unhandled_scope_and_deletes_nothing(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed UTub with url-tags and a scope value the service does not handle
        (standing in for a future TrashScope member)
    WHEN empty_trash_for_user is called with that scope
    THEN it fails closed with the 400 UNABLE_TO_EMPTY_TRASH response and deletes nothing
    """
    _, _, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    url_tags_before = count_url_tags_in_utub(app, FIRST_UTUB_ID)
    assert url_tags_before > 0
    unhandled_scope = MagicMock(spec=TrashScope)

    with app.test_request_context():
        response, status_code = empty_trash_for_user(
            scope=unhandled_scope, listed_at=utc_now(), current_user_id=FIRST_USER_ID
        )

        assert status_code == 400
        response_json = response.get_json()
        assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
        assert (
            response_json[STD_JSON_RESPONSE.MESSAGE]
            == TRASH_FAILURE.UNABLE_TO_EMPTY_TRASH
        )
        assert (
            response_json[STD_JSON_RESPONSE.ERROR_CODE]
            == UTubErrorCodes.UNABLE_TO_EMPTY_TRASH_ERROR
        )
    assert count_url_tags_in_utub(app, FIRST_UTUB_ID) == url_tags_before
