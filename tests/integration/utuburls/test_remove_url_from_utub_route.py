from unittest.mock import patch

import pytest
from flask import url_for
from flask_login import current_user

from backend import db
from backend.metrics.events import EventName
from backend.models.urls import Urls
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.urls import UtubUrlDeleteSchema
from backend.urls.constants import URLErrorCodes
from backend.urls.services.delete_urls import delete_url_in_utub, trash_live_utub_url
from backend.utils.all_routes import ROUTES
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import (
    FAILURE_GENERAL,
)
from backend.utils.strings.json_strs import (
    STD_JSON_RESPONSE as STD_JSON,
)
from backend.utils.strings.model_strs import TAG_COUNTS_MODIFIED
from backend.utils.strings.url_strs import URL_SUCCESS
from backend.utils.strings.utub_strs import UTUB_FAILURE
from tests.integration.system.metrics_helpers import count_counter_keys
from tests.utils_for_test import is_string_in_logs, set_member_role, trash_utub_url

pytestmark = pytest.mark.urls

FIRST_UTUB_ID = 1


def _live_url_count_in_utub(utub_id: int) -> int:
    """Counts the UTub's URL rows that are not trashed (call inside an app context)."""
    return Utub_Urls.query.filter(
        Utub_Urls.utub_id == utub_id, Utub_Urls.deleted_at.is_(None)
    ).count()


def test_delete_others_url_as_co_creator_no_tags(
    add_all_urls_and_users_to_each_utub_no_tags, login_second_user_without_register
):
    """
    GIVEN a co-creator (user 2, NOT the literal utub.utub_creator) of a UTub holding a
        URL added by a DIFFERENT member
    WHEN the co-creator removes that URL via DELETE to
        "/utubs/<int:utub_id>/urls/<int:utub_url_id>"
    THEN the server responds 200 and the URL-UTub association is trashed (the row survives
        flagged with the co-creator as deleted_by) — a co-owner (co-creator) is a manager
        and may delete any URL in the UTub (DD-1). This guards the already-co-creator-inclusive
        single-URL delete path against regression.
    """
    client, csrf_token_string, _, app = login_second_user_without_register

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator != current_user.id).first()
        utub_id = utub.id
        current_user_id = current_user.id
        others_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id,
            Utub_Urls.user_id != current_user_id,
        ).first()
        others_url_id = others_url.id
        initial_count = _live_url_count_in_utub(utub_id)
        initial_raw_count = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).count()

    set_member_role(app, utub_id, current_user_id, Member_Role.CO_CREATOR)

    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_id,
            utub_url_id=others_url_id,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert delete_url_response.status_code == 200
    assert delete_url_response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS

    with app.app_context():
        trashed_row: Utub_Urls = Utub_Urls.query.get(others_url_id)
        assert trashed_row is not None
        assert trashed_row.is_trashed
        assert trashed_row.deleted_by == current_user_id
        assert (
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).count()
            == initial_raw_count
        )
        assert _live_url_count_in_utub(utub_id) == initial_count - 1


def test_delete_url_as_utub_creator_no_tags(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub who has added a valid URL to their UTub, with no tags
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code, the UTub-User-URL association is removed from the database,
        and the server sends back the correct JSON reponse

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
        URL_SUCCESS.UTUB_ID : Integer representing the UTub ID where the URL was removed from,
        URL_SUCCESS.URL : Serialized information of the URL that was removed, as follows:
        {
            "utubUrlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAG_IDS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
            still exists in the UTub
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Get UTub of current user
    with app.app_context():
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        url_utub_user_association: Utub_Urls = current_user_utub.utub_urls[0]
        url_id_to_remove = url_utub_user_association.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()
        initial_live_utub_urls = _live_url_count_in_utub(current_user_utub.id)
        url_object: Urls = url_utub_user_association.standalone_url
        acting_user_id = current_user.id

    # Remove URL from UTub as UTub creator
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=current_user_utub.id,
            utub_url_id=url_id_to_remove,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 200

    # Ensure JSON response is correct
    delete_url_response_json = delete_url_response.json
    assert delete_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert delete_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert int(delete_url_response_json[URL_SUCCESS.UTUB_ID]) == current_user_utub.id
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.UTUB_URL_ID]
        == url_id_to_remove
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == url_object.url_string
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == url_utub_user_association.url_title
    )
    UtubUrlDeleteSchema.model_validate(delete_url_response_json[URL_SUCCESS.URL])

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_object.id) is not None

        # Assert the URL-USER-UTUB association is trashed, not removed
        trashed_row: Utub_Urls = Utub_Urls.query.get(url_id_to_remove)
        assert trashed_row is not None
        assert trashed_row.is_trashed
        assert trashed_row.deleted_by == acting_user_id

        # Ensure the live URL count dropped by exactly one
        assert _live_url_count_in_utub(current_user_utub.id) == (
            initial_live_utub_urls - 1
        )

        assert Utub_Urls.query.count() == initial_utub_urls


def test_remove_url_from_locked_utub_is_rejected(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub who has a valid URL in their UTub, where the UTub is LOCKED
    WHEN the creator tries to remove the URL from the locked UTub by making a DELETE to
        "/utubs/<int:utub_id>/urls/<int:utub_url_id>"
    THEN the write-guard rejects the delete: the server responds 403 with the locked-UTub
        JSON error (error code URLErrorCodes.UTUB_IS_LOCKED, message UTUB_FAILURE.UTUB_IS_LOCKED)
        and the Utub_Urls association is left intact in the database.
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        url_utub_user_association: Utub_Urls = current_user_utub.utub_urls[0]
        url_id_to_remove = url_utub_user_association.id
        utub_id_to_remove_from = current_user_utub.id

        # Lock the UTub
        current_user_utub.is_locked = True
        db.session.commit()

        # Assert-before-state: the URL association exists prior to the blocked action
        assert Utub_Urls.query.get(url_id_to_remove) is not None
        initial_utub_urls = Utub_Urls.query.count()

    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_id_to_remove_from,
            utub_url_id=url_id_to_remove,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert delete_url_response.status_code == 403
    delete_url_response_json = delete_url_response.json
    assert delete_url_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert delete_url_response_json[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert (
        int(delete_url_response_json[STD_JSON.ERROR_CODE])
        == URLErrorCodes.UTUB_IS_LOCKED
    )

    with app.app_context():
        # The URL association still exists in the locked UTub
        assert Utub_Urls.query.get(url_id_to_remove) is not None
        assert Utub_Urls.query.count() == initial_utub_urls


def test_delete_url_records_url_removed_from_utub_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_one_url_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a logged-in creator of a UTub with a URL (no tags) and metrics enabled
    WHEN the creator DELETEs "/utubs/<utub_id>/urls/<utub_url_id>"
    THEN the request returns HTTP 200 AND exactly one URL_REMOVED_FROM_UTUB
        counter key is written to the metrics Redis DB.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id = utub_user_is_creator_of.id
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).first()
        utub_url_id = utub_url.id

    # Before-state: no URL_REMOVED_FROM_UTUB counter exists yet
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_REMOVED_FROM_UTUB) == 0
    )

    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        ),
        headers={"X-CSRFToken": csrf_token},
    )

    assert delete_url_response.status_code == 200
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_REMOVED_FROM_UTUB) == 1
    )


def test_delete_url_does_not_inflate_tag_removed_counter(
    metrics_enabled_app,
    provide_metrics_redis,
    login_first_user_with_register,
):
    """
    GIVEN a UTub with a URL that has multiple Utub_Url_Tags associations,
        seeded via raw ORM (bypassing the service layer so no TAG_APPLIED
        is emitted during setup), and metrics enabled
    WHEN the creator DELETEs "/utubs/<utub_id>/urls/<utub_url_id>"
    THEN the request returns HTTP 200 AND NO TAG_REMOVED counter key is
        written — proving that trashing the URL (which retains its
        Utub_Url_Tags rows) does NOT re-enter `delete_url_tag` and
        inflate the counter.
    """
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    with app.app_context():
        seeded_utub = Utubs(
            name="Bypass-Cascade UTub",
            utub_creator=user_id,
            utub_description="",
        )
        db.session.add(seeded_utub)
        db.session.commit()
        utub_id = seeded_utub.id

        creator_membership = Utub_Members()
        creator_membership.utub_id = utub_id
        creator_membership.user_id = user_id
        creator_membership.member_role = Member_Role.CREATOR
        db.session.add(creator_membership)
        db.session.commit()

        url_row = Urls(
            normalized_url="https://www.bypass-cascade-example.com",
            current_user_id=user_id,
        )
        db.session.add(url_row)
        db.session.commit()

        utub_url = Utub_Urls()
        utub_url.utub_id = utub_id
        utub_url.url_id = url_row.id
        utub_url.user_id = user_id
        utub_url.url_title = "Bypass URL"
        db.session.add(utub_url)
        db.session.commit()
        utub_url_id = utub_url.id

        # Seed two Utub_Tags + two Utub_Url_Tags directly so TAG_APPLIED
        # is NOT emitted during setup.
        for tag_idx in range(2):
            tag_row = Utub_Tags(
                utub_id=utub_id,
                tag_string=f"bypass-tag-{tag_idx}",
                created_by=user_id,
            )
            db.session.add(tag_row)
            db.session.commit()

            url_tag = Utub_Url_Tags()
            url_tag.utub_id = utub_id
            url_tag.utub_url_id = utub_url_id
            url_tag.utub_tag_id = tag_row.id
            db.session.add(url_tag)
            db.session.commit()

    # Before-state: no TAG_REMOVED counter exists yet
    assert count_counter_keys(provide_metrics_redis, EventName.TAG_REMOVED) == 0

    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        ),
        headers={"X-CSRFToken": csrf_token},
    )

    assert delete_url_response.status_code == 200

    # The trash path never calls `delete_url_tag`, so TAG_REMOVED must
    # remain at 0, and the 2 Utub_Url_Tags rows are retained on the trashed row.
    assert count_counter_keys(provide_metrics_redis, EventName.TAG_REMOVED) == 0
    with app.app_context():
        assert (
            Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_url_id == utub_url_id).count()
            == 2
        )


def test_delete_url_as_utub_member_no_tags(
    add_all_urls_and_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in member of a UTub who has added a valid URL to their UTub, with no tags
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code, the UTub-User-URL association is removed from the database,
        and the server sends back the correct JSON reponse

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
        URL_SUCCESS.UTUB_ID : Integer representing the UTub ID where the URL was removed from,
        URL_SUCCESS.URL : Serialized information of the URL that was removed, as follows:
        {
            "utubUrlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAG_IDS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
            still exists in the UTub
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get URL that this user did not add to a UTub
        current_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.user_id == current_user.id
        ).first()

        current_user_utub_id = current_url_in_utub.utub_id
        current_num_urls_in_utub = _live_url_count_in_utub(current_user_utub_id)

        url_object: Urls = current_url_in_utub.standalone_url
        url_object_id = url_object.id
        current_url_string = url_object.url_string
        current_url_title = current_url_in_utub.url_title
        acting_user_id = current_user.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Remove URL from UTub as UTub member
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=current_user_utub_id,
            utub_url_id=current_url_in_utub.id,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 200

    # Ensure JSON response is correct
    delete_url_response_json = delete_url_response.json

    assert delete_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert delete_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert int(delete_url_response_json[URL_SUCCESS.UTUB_ID]) == current_user_utub_id
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.UTUB_URL_ID]
        == current_url_in_utub.id
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == current_url_string
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == current_url_title
    )
    UtubUrlDeleteSchema.model_validate(delete_url_response_json[URL_SUCCESS.URL])

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_object_id) is not None

        # Assert the URL-UTUB association is trashed, not removed
        trashed_row: Utub_Urls = Utub_Urls.query.get(current_url_in_utub.id)
        assert trashed_row is not None
        assert trashed_row.is_trashed
        assert trashed_row.deleted_by == acting_user_id

        # Ensure UTub has one fewer live URL
        assert _live_url_count_in_utub(current_user_utub_id) == (
            current_num_urls_in_utub - 1
        )

        assert Utub_Urls.query.count() == initial_utub_urls


def test_delete_url_from_utub_not_member_of(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in member of a UTub, with two other UTub the user is not a part of that also contains URLs
    WHEN the user wishes to remove the URL from another UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 404 HTTP status code and the UTub-User-URL association is not removed from the database
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Find the first UTub the logged in user is not a creator of
    with app.app_context():
        utub_current_user_not_part_of = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        current_num_of_urls_in_utub = len(utub_current_user_not_part_of.utub_urls)

        # Get the URL to remove
        url_to_remove_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_current_user_not_part_of.id
        ).first()

        url_to_remove_id = url_to_remove_in_utub.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Remove the URL from the other user's UTub while logged in as member of another UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_current_user_not_part_of.id,
            utub_url_id=url_to_remove_id,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert delete_url_response.status_code == 404

    # Ensure database is not affected
    with app.app_context():
        utub_in_url: Utub_Urls = Utub_Urls.query.get(url_to_remove_id)
        assert (
            utub_in_url is not None
            and utub_in_url.utub_id == utub_current_user_not_part_of.id
        )
        assert Utub_Urls.query.count() == initial_utub_urls

        utub_current_user_not_part_of: Utubs = Utubs.query.get(
            utub_current_user_not_part_of.id
        )
        assert current_num_of_urls_in_utub == len(
            utub_current_user_not_part_of.utub_urls
        )


def test_remove_invalid_nonexistant_url_as_utub_creator(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub
    WHEN the user wishes to remove a nonexistant URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 404 HTTP status code, and the database has no changes
    """
    NONEXISTENT_URL_IN_UTUB_ID = 999

    client, csrf_token_string, _, app = login_first_user_without_register

    # Find the first UTub this logged in user is a creator of
    with app.app_context():
        utub_current_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub_current_user_creator_of = utub_current_user_creator_of.id

        # Ensure not in UTub and nonexistant
        assert Utub_Urls.query.get(NONEXISTENT_URL_IN_UTUB_ID) is None

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Attempt to remove nonexistant URL from UTub as creator of UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=id_of_utub_current_user_creator_of,
            utub_url_id=NONEXISTENT_URL_IN_UTUB_ID,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 404

    with app.app_context():
        # Ensure not in UTub and nonexistant
        assert Utub_Urls.query.get(NONEXISTENT_URL_IN_UTUB_ID) is None
        assert Utub_Urls.query.count() == initial_utub_urls


def test_remove_invalid_nonexistant_url_as_utub_member(
    add_one_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub
    WHEN the user wishes to remove a nonexistant URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 404 HTTP status code, and the database has no changes
    """
    NONEXISTENT_URL_IN_UTUB_ID = 999
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_current_user_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        id_of_utub_current_user_member_of = utub_current_user_member_of.id

        # Ensure not in UTub and nonexistant
        assert Utub_Urls.query.get(NONEXISTENT_URL_IN_UTUB_ID) is None

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Attempt to remove nonexistant URL from UTub as creator of UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=id_of_utub_current_user_member_of,
            utub_url_id=NONEXISTENT_URL_IN_UTUB_ID,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 404

    with app.app_context():
        # Ensure not in UTub and nonexistant
        assert Utub_Urls.query.get(NONEXISTENT_URL_IN_UTUB_ID) is None
        assert Utub_Urls.query.count() == initial_utub_urls


def test_delete_already_trashed_url_is_404(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub that holds a URL that is already in the trash
    WHEN the user makes a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>" for it
    THEN the server responds with a 404 and the row's original deleted_at and
        deleted_by are unchanged, so the retention clock is not reset
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id = utub_creator_of.id
        utub_url_id = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).first().id
        creator_user_id = current_user.id

    trash_utub_url(app, utub_url_id, deleted_by=creator_user_id)

    with app.app_context():
        trashed_row: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        assert trashed_row is not None
        assert trashed_row.is_trashed
        original_deleted_at = trashed_row.deleted_at
        original_deleted_by = trashed_row.deleted_by

    delete_url_response = client.delete(
        url_for(ROUTES.URLS.DELETE_URL, utub_id=utub_id, utub_url_id=utub_url_id),
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert delete_url_response.status_code == 404
    json_response = delete_url_response.get_json()
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND

    with app.app_context():
        row_after: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        assert row_after.deleted_at == original_deleted_at
        assert row_after.deleted_by == original_deleted_by


def test_delete_url_trashed_between_gate_and_service_is_404(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
) -> None:
    """
    GIVEN a live URL that passes the route's ownership decorator
    WHEN another request trashes the row after the decorator but before the delete
        service's conditional trash UPDATE runs
    THEN the delete responds 404 NOT_FOUND and the first request's deleted_at and
        deleted_by are not overwritten
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id: int = utub_creator_of.id
        utub_url_id: int = (
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).first().id
        )
        creator_user_id: int = current_user.id
        other_user_id: int = creator_user_id + 1

    def trash_concurrently_then_delete(**kwargs: object) -> object:
        trash_utub_url(app, utub_url_id, deleted_by=other_user_id)
        return delete_url_in_utub(**kwargs)

    with patch(
        "backend.urls.routes.delete_url_in_utub",
        side_effect=trash_concurrently_then_delete,
    ):
        delete_url_response = client.delete(
            url_for(ROUTES.URLS.DELETE_URL, utub_id=utub_id, utub_url_id=utub_url_id),
            headers={"X-CSRFToken": csrf_token_string},
        )

    assert delete_url_response.status_code == 404
    json_response = delete_url_response.get_json()
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND

    with app.app_context():
        row_after: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        assert row_after.is_trashed
        assert row_after.deleted_by == other_user_id


def test_trash_live_utub_url_returns_false_for_already_trashed_row(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
) -> None:
    """
    GIVEN a URL row that is already in the trash
    WHEN the conditional trash helper is called for it
    THEN it returns False and leaves deleted_at, deleted_by and trashed_tag_ids as the
        first trash wrote them
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id: int = utub_creator_of.id
        utub_url_id: int = (
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).first().id
        )
        creator_user_id: int = current_user.id

    trash_utub_url(app, utub_url_id, deleted_by=creator_user_id, trashed_tag_ids=[])

    with app.app_context():
        trashed_row: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        original_deleted_at = trashed_row.deleted_at
        original_deleted_by = trashed_row.deleted_by
        original_trashed_tag_ids = trashed_row.trashed_tag_ids

        was_trashed: bool = trash_live_utub_url(
            utub_id=utub_id, utub_url_id=utub_url_id, snapshot_tag_ids={999}
        )
        db.session.expire_all()

        assert was_trashed is False
        row_after: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        assert row_after.deleted_at == original_deleted_at
        assert row_after.deleted_by == original_deleted_by
        assert row_after.trashed_tag_ids == original_trashed_tag_ids


def test_delete_url_as_utub_creator_with_tag(
    add_all_urls_and_users_to_each_utub_with_one_tag, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub who has a valid URL in their UTub, with a single tag
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code, the UTub-User-URL association is trashed (flagged, not deleted)
        with a tag snapshot, the UTub-URL-Tag associations are retained, and the server sends back the correct JSON reponse

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
        URL_SUCCESS.UTUB_ID : Integer representing the UTub ID where the URL was removed from,
        URL_SUCCESS.URL : Serialized information of the URL that was removed, as follows:
        {
            "utubUrlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAG_IDS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
            still exists in the UTub
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Find current user's UTub
        current_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Find a URL with tags on it in this UTub
        current_utub_url_tags: list[Utub_Url_Tags] = current_utub.utub_url_tags
        current_url_in_utub_with_tags: Utub_Url_Tags = current_utub_url_tags[0]

        # Get the Utubs-URL association
        url_in_utub: Utub_Urls = Utub_Urls.query.get(
            current_url_in_utub_with_tags.utub_url_id
        )
        url_object: Urls = url_in_utub.standalone_url
        url_object_id = url_object.id
        url_string_to_remove = url_object.url_string

        url_id_to_remove = url_in_utub.id
        utub_id_to_delete_url_from = current_utub.id
        acting_user_id = current_user.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

        # Get initial number of Url-Tag associations
        initial_tag_urls = Utub_Url_Tags.query.count()

        # Get count of tags on this URL in this UTub
        tags_on_url_in_utub = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == current_utub.id,
            Utub_Url_Tags.utub_url_id == current_url_in_utub_with_tags.utub_url_id,
        ).count()
        tag_ids_before_delete = sorted(url_in_utub.associated_tag_ids)
        assert tags_on_url_in_utub >= 1

    # Attempt to remove URL that contains tag from UTub as creator of UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_id_to_delete_url_from,
            utub_url_id=url_id_to_remove,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert delete_url_response.status_code == 200

    # Ensure JSON response is correct
    delete_url_response_json = delete_url_response.json
    assert delete_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert delete_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert (
        int(delete_url_response_json[URL_SUCCESS.UTUB_ID]) == utub_id_to_delete_url_from
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.UTUB_URL_ID]
        == url_id_to_remove
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == url_string_to_remove
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == url_in_utub.url_title
    )
    UtubUrlDeleteSchema.model_validate(delete_url_response_json[URL_SUCCESS.URL])

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_object_id) is not None

        # Assert the URL-USER-UTUB association is trashed, with a tag snapshot
        trashed_row: Utub_Urls = Utub_Urls.query.get(url_id_to_remove)
        assert trashed_row is not None
        assert trashed_row.is_trashed
        assert trashed_row.deleted_by == acting_user_id
        assert trashed_row.trashed_tag_ids == tag_ids_before_delete

        # Assert the UTUB-URL-TAG associations survive the trash
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_to_delete_url_from,
                Utub_Url_Tags.utub_url_id == url_id_to_remove,
            ).count()
            == tags_on_url_in_utub
        )

        # Ensure counts of Url-Utubs-Tag associations are unchanged
        assert Utub_Urls.query.count() == initial_utub_urls
        assert Utub_Url_Tags.query.count() == initial_tag_urls


def test_delete_url_as_utub_member_with_tags(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in member of a UTub who has added a valid URL to their UTub, with tags
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code, the UTub-User-URL association is trashed (flagged, not deleted)
        with a tag snapshot, the UTub-URL-Tag associations are retained, and the server sends back the correct JSON reponse

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
        URL_SUCCESS.UTUB_ID : Integer representing the UTub ID where the URL was removed from,
        URL_SUCCESS.URL : Serialized information of the URL that was removed, as follows:
        {
            "utubUrlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAG_IDS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
            still exists in the UTub
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get first UTub where current logged in user is not the creator
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Find a URL this user has added
        current_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == current_user_utub.id,
            Utub_Urls.user_id == current_user.id,
        ).first()

        utub_id_to_delete_url_from = current_user_utub.id
        url_id_to_remove = current_url_in_utub.id
        url_object: Urls = current_url_in_utub.standalone_url
        url_object_id = url_object.id
        url_string_to_remove = url_object.url_string
        url_title_to_remove = current_url_in_utub.url_title
        acting_user_id = current_user.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

        # Get initial number of Url-Tag associations
        initial_tag_urls = Utub_Url_Tags.query.count()

        # Get count of tags on this URL in this UTub
        tags_on_url_in_utub = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == current_user_utub.id,
            Utub_Url_Tags.utub_url_id == url_id_to_remove,
        ).count()
        tag_ids_before_delete = sorted(current_url_in_utub.associated_tag_ids)
        assert tags_on_url_in_utub >= 1

    # Remove URL from UTub as UTub member
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_id_to_delete_url_from,
            utub_url_id=url_id_to_remove,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 200

    # Ensure JSON response is correct
    delete_url_response_json = delete_url_response.json

    delete_url_response_json = delete_url_response.json
    assert delete_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert delete_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert (
        int(delete_url_response_json[URL_SUCCESS.UTUB_ID]) == utub_id_to_delete_url_from
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.UTUB_URL_ID]
        == url_id_to_remove
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == url_string_to_remove
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == url_title_to_remove
    )
    UtubUrlDeleteSchema.model_validate(delete_url_response_json[URL_SUCCESS.URL])

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_object_id) is not None

        # Assert the URL-USER-UTUB association is trashed, with a tag snapshot
        trashed_row: Utub_Urls = Utub_Urls.query.get(url_id_to_remove)
        assert trashed_row is not None
        assert trashed_row.is_trashed
        assert trashed_row.deleted_by == acting_user_id
        assert trashed_row.trashed_tag_ids == tag_ids_before_delete

        # Assert the UTUB-URL-TAG associations survive the trash
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_to_delete_url_from,
                Utub_Url_Tags.utub_url_id == url_id_to_remove,
            ).count()
            == tags_on_url_in_utub
        )

        # Ensure counts of Url-Utubs-Tag associations are unchanged
        assert Utub_Urls.query.count() == initial_utub_urls
        assert Utub_Url_Tags.query.count() == initial_tag_urls


def test_delete_url_tag_counts_are_live_only(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a UTub where a `shared` tag is on URLs 1, 2, 3 and a `solo` tag is on URL 1 only
    WHEN the creator DELETEs URL 1 (which trashes it and retains its Utub_Url_Tags rows)
    THEN tagCountsInUtub counts only live URLs: the shared tag is 2 (still on URLs 2, 3)
        and the solo tag is 0 (present, not omitted) — neither double-decremented nor
        counting the trashed row's retained tag rows.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        url_one: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == FIRST_UTUB_ID, Utub_Urls.url_id == 1
        ).first()
        url_two: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == FIRST_UTUB_ID, Utub_Urls.url_id == 2
        ).first()
        url_one_id = url_one.id
        shared_tag_id = sorted(url_two.associated_tag_ids)[0]
        solo_tag_id = next(
            tag_id for tag_id in url_one.associated_tag_ids if tag_id != shared_tag_id
        )

    response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=FIRST_UTUB_ID,
            utub_url_id=url_one_id,
        ),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    tag_counts = {
        int(tag_id): count
        for tag_id, count in response.json[TAG_COUNTS_MODIFIED].items()
    }
    assert tag_counts == {shared_tag_id: 2, solo_tag_id: 0}


def test_delete_url_not_in_utub_no_tags(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub who has added a valid URL to their UTub, with no tags
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 404 HTTP status code
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Get UTub of current user
    with app.app_context():
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        url_utub_user_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != current_user_utub.id
        ).first()
        url_id_to_remove = url_utub_user_association.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()
        url_object: Urls = url_utub_user_association.standalone_url

    # Remove URL from UTub as UTub creator
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=current_user_utub.id,
            utub_url_id=url_id_to_remove,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 404
    json_response = delete_url_response.get_json()
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_object.id) is not None

        # Ensure UTub has no URLs left
        assert Utub_Urls.query.count() == initial_utub_urls


def test_delete_url_from_utub_no_csrf_token(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in member of a UTub, with two other UTub the user is not a part of that also contains URLs
    WHEN the user wishes to remove the URL from another UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>",
        where the DELETE does not contain a valid CSRF token
    THEN the server responds with a 400 HTTP status code, the UTub-User-URL association is not removed from the database,
        and the server sends back an HTML element indicating a missing CSRF token
    """
    client, _, _, app = login_first_user_without_register

    # Find the first UTub the logged in user is not a creator of
    with app.app_context():
        utub_current_user_not_part_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        current_num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_current_user_not_part_of.id
        ).count()

        # Get the URL to remove
        url_to_remove_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_current_user_not_part_of.id
        ).first()
        url_to_remove_id = url_to_remove_in_utub.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Remove the URL from the other user's UTub while logged in as member of another UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_current_user_not_part_of.id,
            utub_url_id=url_to_remove_id,
        ),
        data={},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 403
    assert delete_url_response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in delete_url_response.data

    # Ensure database is not affected
    with app.app_context():
        utub_current_user_not_part_of = Utubs.query.filter(
            Utubs.id == utub_current_user_not_part_of.id
        ).first()

        assert (
            len(utub_current_user_not_part_of.utub_urls) == current_num_of_urls_in_utub
        )
        current_utub_urls_id = [
            url.id for url in utub_current_user_not_part_of.utub_urls
        ]
        assert url_to_remove_id in current_utub_urls_id

        assert Utub_Urls.query.count() == initial_utub_urls


def test_delete_url_updates_utub_last_updated(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub who has added a valid URL to their UTub, with no tags
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code, and the UTub's last updated field is updated
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Get UTub of current user
    with app.app_context():
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = current_user_utub.last_updated

        url_utub_user_association: Utub_Urls = current_user_utub.utub_urls[0]
        url_id_to_remove = url_utub_user_association.id

    # Remove URL from UTub as UTub creator
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=current_user_utub.id,
            utub_url_id=url_id_to_remove,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 200

    # Ensure proper removal from database
    with app.app_context():
        current_user_utub = Utubs.query.get(current_user_utub.id)
        assert (
            current_user_utub.last_updated - initial_last_updated
        ).total_seconds() > 0


def test_remove_invalid_url_does_not_update_utub_last_updated(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub
    WHEN the user wishes to remove a nonexistant URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 404 HTTP status code, and the UTub's last updated field is not updated
    """

    client, csrf_token_string, _, app = login_first_user_without_register

    # Find the first UTub this logged in user is a creator of
    with app.app_context():
        utub_current_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_current_user_creator_of.last_updated
        id_of_utub_current_user_creator_of = utub_current_user_creator_of.id

        url_not_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != id_of_utub_current_user_creator_of,
        ).first()
        id_of_url_to_remove = url_not_in_utub.id

    # Attempt to remove nonexistant URL from UTub as creator of UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=id_of_utub_current_user_creator_of,
            utub_url_id=id_of_url_to_remove,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure 404 HTTP status code response
    assert delete_url_response.status_code == 404

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(id_of_utub_current_user_creator_of)
        assert current_utub.last_updated == initial_last_updated


def test_delete_url_logs(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register, caplog
):
    """
    GIVEN a logged-in creator of a UTub who has added a valid URL to their UTub, with no tags
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    # Get UTub of current user
    with app.app_context():
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        url_utub_user_association: Utub_Urls = current_user_utub.utub_urls[0]
        url_id = url_utub_user_association.standalone_url.id
        utub_url_id_to_remove = url_utub_user_association.id

    # Remove URL from UTub as UTub creator
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=current_user_utub.id,
            utub_url_id=utub_url_id_to_remove,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 200
    assert is_string_in_logs(f"User.id={current_user_utub.id}", caplog.records)
    assert is_string_in_logs(f"UTub.id={current_user_utub.id}", caplog.records)
    assert is_string_in_logs(f"UTubURL.id={utub_url_id_to_remove}", caplog.records)
    assert is_string_in_logs(f"URL.id={url_id}", caplog.records)


def test_delete_url_not_in_utub_logs(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register, caplog
):
    """
    GIVEN a logged-in creator of a UTub who has added a valid URL to their UTub, with no tags
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    # Get UTub of current user
    with app.app_context():
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        url_utub_user_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != current_user_utub.id
        ).first()
        utub_url_id_to_remove = url_utub_user_association.id

    # Remove URL from UTub as UTub creator
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=current_user_utub.id,
            utub_url_id=utub_url_id_to_remove,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 404
    assert is_string_in_logs(
        f"Invalid UTubURL.id={utub_url_id_to_remove} for UTub.id={current_user_utub.id} by UTubUser={current_user.id}",
        caplog.records,
    )


def test_delete_url_user_not_adder_or_creator_logs(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a logged-in member of a UTub
    WHEN the member tries to remove a URL from a UTub but they didn't add the URL or create the UTub by DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 403 HTTP status code and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    # Get UTub of current user
    with app.app_context():
        another_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator != user.id
        ).first()

        url_utub_user_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == another_user_utub.id,
            Utub_Urls.user_id == another_user_utub.utub_creator,
        ).first()
        utub_url_id_to_remove = url_utub_user_association.id

    # Remove URL from UTub as UTub creator
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=another_user_utub.id,
            utub_url_id=utub_url_id_to_remove,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 403
    assert is_string_in_logs(
        f"User={user.id} not URL adder or UTub manager: UTubURL.id={utub_url_id_to_remove} in UTub.id={another_user_utub.id}",
        caplog.records,
    )
