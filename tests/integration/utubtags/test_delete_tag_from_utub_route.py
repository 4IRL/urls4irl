from flask import url_for
from flask_login import current_user
import pytest

from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import TAG_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.tag_strs import TAGS_SUCCESS
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.tags


def test_delete_tag_from_utub_with_no_url_associations(
    every_user_in_every_utub,
    add_one_tag_to_each_utub_after_one_url_added,
    login_first_user_without_register,
):
    """
    GIVEN utubs with associated utub tags and no tags associated with URLs
    WHEN a member of those utubs decides to delete a utub tag
    THEN verify that the tag gets deleted, the server responds with a 200 HTTP status code,
        and the server responds with the appropriate JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_REMOVED_FROM_UTUB,
        TAGS_SUCCESS.TAG : Serialization representing the deleted tag object:
            {
                MODELS.UTUB_TAG_ID: Integer representing ID of deleted tag,
                TAG_FORM.TAG_STRING: String representing the tag just deleted
            }
        TAGS_SUCCESS.UTUB_URL_IDS : Array of integers representing URLs that has this tag removed,
        TAGS_SUCCESS.TAG_COUNTS_MODIFIED : Should be 0.
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this user is member of
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == current_user.id).first()

        # Find tag in this UTub
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub.id
        ).first()
        utub_tag_id = utub_tag.id
        utub_tag_string = utub_tag.tag_string

        num_of_utub_tags: int = Utub_Tags.query.count()
        num_of_utub_url_tags: int = Utub_Url_Tags.query.count()

    delete_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token}

    delete_tag_response = client.delete(
        url_for(
            ROUTES.UTUB_TAGS.DELETE_UTUB_TAG,
            utub_id=utub.id,
            utub_tag_id=utub_tag_id,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 200
    delete_tag_response_json = delete_tag_response.json

    assert delete_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        delete_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_UTUB
    )
    assert (
        delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][TAG_FORM.TAG_STRING]
        == utub_tag_string
    )
    assert (
        delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODEL_STRS.UTUB_TAG_ID]
        == utub_tag_id
    )
    assert delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_IDS] == []

    with app.app_context():
        assert Utub_Tags.query.count() == num_of_utub_tags - 1
        assert Utub_Tags.query.get(utub_tag_id) is None
        assert Utub_Url_Tags.query.count() == num_of_utub_url_tags


def test_delete_tag_from_utub_with_url_associations(
    every_user_in_every_utub,
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN utubs with associated utub tags and those tags associated with URLs
    WHEN a member of those utubs decides to delete a utub tag
    THEN verify that the tag gets deleted, the utub-url-tag associations get deleted,
        the server responds with a 200 HTTP status code, and the server responds with the appropriate JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_REMOVED_FROM_UTUB,
        TAGS_SUCCESS.TAG : Serialization representing the deleted tag object:
            {
                MODELS.UTUB_TAG_ID: Integer representing ID of deleted tag,
                TAG_FORM.TAG_STRING: String representing the tag just deleted
            }
        TAGS_SUCCESS.UTUB_URL_IDS : Array of integers representing URLs that has this tag removed,
        TAGS_SUCCESS.TAG_COUNTS_MODIFIED : Should be 0.
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this user is member of
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == current_user.id).first()

        # Find tag in this UTub
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub.id
        ).first()
        utub_tag_id = utub_tag.id
        utub_tag_string = utub_tag.tag_string

        num_of_utub_tags: int = Utub_Tags.query.count()
        utub_url_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub.id, Utub_Url_Tags.utub_tag_id == utub_tag_id
        ).all()
        utub_url_tag_ids: list[int] = [url.utub_url_id for url in utub_url_tags]
        num_of_utub_url_tags: int = len(utub_url_tags)
        total_utub_url_tags: int = Utub_Url_Tags.query.count()

    delete_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token}

    delete_tag_response = client.delete(
        url_for(
            ROUTES.UTUB_TAGS.DELETE_UTUB_TAG,
            utub_id=utub.id,
            utub_tag_id=utub_tag_id,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 200
    delete_tag_response_json = delete_tag_response.json

    assert delete_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        delete_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_UTUB
    )
    assert (
        delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][TAG_FORM.TAG_STRING]
        == utub_tag_string
    )
    assert (
        delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODEL_STRS.UTUB_TAG_ID]
        == utub_tag_id
    )
    assert sorted(delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_IDS]) == sorted(
        utub_url_tag_ids
    )

    with app.app_context():
        assert Utub_Tags.query.count() == num_of_utub_tags - 1
        assert Utub_Tags.query.get(utub_tag_id) is None
        assert Utub_Url_Tags.query.count() == total_utub_url_tags - num_of_utub_url_tags


def test_delete_tag_from_utub_not_member_of(
    add_one_url_to_each_utub_one_tag_to_each_url_all_tags_in_utub,
    login_first_user_without_register,
):
    """
    GIVEN utubs with associated utub tags and those tags associated with URLs
    WHEN a member of those utubs decides to delete a utub tag from a UTub they aren't a member of
    THEN verify that the tag does not get deleted, the server responds with a 403 HTTP status code,
        and the server responds with the appropriate JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.ONLY_UTUB_MEMBERS_DELETE_TAGS,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this user is member of
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator != current_user.id).first()

        # Find tag in this UTub
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub.id
        ).first()

        num_of_utub_tags: int = Utub_Tags.query.count()
        num_of_utub_url_tags: int = Utub_Url_Tags.query.count()

    delete_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token}

    delete_tag_response = client.delete(
        url_for(
            ROUTES.UTUB_TAGS.DELETE_UTUB_TAG,
            utub_id=utub.id,
            utub_tag_id=utub_tag.id,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 404

    with app.app_context():
        assert Utub_Tags.query.count() == num_of_utub_tags
        assert Utub_Url_Tags.query.count() == num_of_utub_url_tags


def test_delete_nonexistent_tag_from_utub(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN utubs with associated utub tags and no tags associated with URLs
    WHEN a member of those utubs decides to delete a nonexistent UTub Tag
    THEN verify the server responds with a 404 HTTP status code, database content is the same,
        and the server responds with the appropriate HTML response
    """
    client, csrf_token, _, app = login_first_user_without_register

    NONEXISTENT_TAG_ID = 999

    with app.app_context():
        # Find UTub this user is member of
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == current_user.id).first()

        num_of_utub_tags: int = Utub_Tags.query.count()
        num_of_utub_url_tags: int = Utub_Url_Tags.query.count()

    delete_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token}

    delete_tag_response = client.delete(
        url_for(
            ROUTES.UTUB_TAGS.DELETE_UTUB_TAG,
            utub_id=utub.id,
            utub_tag_id=NONEXISTENT_TAG_ID,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 404
    assert IDENTIFIERS.HTML_404.encode() in delete_tag_response.data

    with app.app_context():
        assert Utub_Tags.query.count() == num_of_utub_tags
        assert Utub_Url_Tags.query.count() == num_of_utub_url_tags


def test_delete_tag_from_nonexistent_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN utubs with associated utub tags and no tags associated with URLs
    WHEN a member of those utubs decides to delete a tag from a nonexistent UTub
    THEN verify the server responds with a 404 HTTP status code, database content is the same,
        and the server responds with the appropriate HTML response
    """
    client, csrf_token, _, app = login_first_user_without_register

    NONEXISTENT_UTUB_ID = 999

    with app.app_context():
        # Find UTub this user is member of
        utub_tag = Utub_Tags.query.first()

        num_of_utub_tags: int = Utub_Tags.query.count()
        num_of_utub_url_tags: int = Utub_Url_Tags.query.count()

    delete_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token}

    delete_tag_response = client.delete(
        url_for(
            ROUTES.UTUB_TAGS.DELETE_UTUB_TAG,
            utub_id=NONEXISTENT_UTUB_ID,
            utub_tag_id=utub_tag.id,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 404
    assert IDENTIFIERS.HTML_404.encode() in delete_tag_response.data

    with app.app_context():
        assert Utub_Tags.query.count() == num_of_utub_tags
        assert Utub_Url_Tags.query.count() == num_of_utub_url_tags


def test_delete_tag_from_utub_no_csrf_token(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN utubs with associated utub tags and no tags associated with URLs
    WHEN a member of those utubs decides to delete a UTub Tag but is missing the CSRF token
    THEN verify the server responds with a 400 HTTP status code, database content is the same,
        and the server responds with the appropriate HTML response
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this user is member of
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == current_user.id).first()

        # Find tag in this UTub
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub.id
        ).first()
        utub_tag_id = utub_tag.id
        utub_tag_string = utub_tag.tag_string

        num_of_utub_tags: int = Utub_Tags.query.count()
        num_of_utub_url_tags: int = Utub_Url_Tags.query.count()

    delete_tag_form = {}

    delete_tag_response = client.delete(
        url_for(
            ROUTES.UTUB_TAGS.DELETE_UTUB_TAG,
            utub_id=utub.id,
            utub_tag_id=utub_tag_id,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 403
    assert delete_tag_response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in delete_tag_response.data

    with app.app_context():
        assert Utub_Tags.query.count() == num_of_utub_tags
        assert Utub_Url_Tags.query.count() == num_of_utub_url_tags
        assert (
            Utub_Tags.query.filter(
                Utub_Tags.utub_id == utub.id, Utub_Tags.tag_string == utub_tag_string
            ).first()
            is not None
        )


def test_delete_utub_tag_updates_utub_last_updated(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN utubs with associated utub tags and no tags associated with URLs
    WHEN a member of those utubs decides to delete a utub tag
    THEN verify that the tag gets deleted, the server responds with a 200 HTTP status code,
        and the last_updated field of the UTub is updated appropriately
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this user is member of
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == current_user.id).first()
        utub_id: int = utub.id
        initial_last_updated = utub.last_updated

        # Find tag in this UTub
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_id
        ).first()
        utub_tag_id = utub_tag.id

    delete_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token}

    delete_tag_response = client.delete(
        url_for(
            ROUTES.UTUB_TAGS.DELETE_UTUB_TAG,
            utub_id=utub_id,
            utub_tag_id=utub_tag_id,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 200

    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        assert (utub.last_updated - initial_last_updated).total_seconds() > 0


def test_delete_tag_from_utub_log(
    every_user_in_every_utub,
    add_one_tag_to_each_utub_after_one_url_added,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN utubs with associated utub tags and no tags associated with URLs
    WHEN a member of those utubs decides to delete a utub tag
    THEN verify that the tag gets deleted, the server responds with a 200 HTTP status code
        and the logs are valid
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this user is member of
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == current_user.id).first()

        # Find tag in this UTub
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub.id
        ).first()
        utub_tag_id = utub_tag.id
        utub_tag_string = utub_tag.tag_string

    delete_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token}

    delete_tag_response = client.delete(
        url_for(
            ROUTES.UTUB_TAGS.DELETE_UTUB_TAG,
            utub_id=utub.id,
            utub_tag_id=utub_tag_id,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 200
    assert is_string_in_logs("Deleted UTubTag", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub.id}", caplog.records)
    assert is_string_in_logs(f"UTubTag.id={utub_tag_id}", caplog.records)
    assert is_string_in_logs(f"UTubTag.tag_string={utub_tag_string}", caplog.records)
