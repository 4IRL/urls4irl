import threading
from unittest import mock

import ada_url
import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask_login import current_user
from werkzeug.test import TestResponse

from backend import db
from backend.extensions.url_validation.url_validator import (
    InvalidURLError,
)
from backend.metrics.events import EventName
from backend.models.urls import Urls
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.urls import UtubUrlDetailSchema
from backend.urls.constants import URLErrorCodes
from backend.urls.data_models import ValidatedUrl
from backend.urls.services.create_urls import validate_new_url_for_utub
from backend.utils.all_routes import ROUTES
from backend.utils.constants import TAG_CONSTANTS
from backend.utils.strings.form_strs import URL_FORM
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import (
    FAILURE_GENERAL,
    FIELD_REQUIRED_STR,
)
from backend.utils.strings.json_strs import (
    STD_JSON_RESPONSE as STD_JSON,
)
from backend.utils.strings.model_strs import MODELS as MODEL_STRS
from backend.utils.strings.model_strs import TAG_COUNTS_MODIFIED
from backend.utils.strings.tag_strs import TAGS_FAILURE
from backend.utils.strings.url_strs import URL_FAILURE, URL_NO_CHANGE, URL_SUCCESS
from backend.utils.strings.utub_strs import UTUB_FAILURE
from tests.integration.system.metrics_helpers import (
    STRIPPED_DIM_KEY,
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
)
from tests.unit.test_url_validation import (
    FLATTENED_NORMALIZED_AND_INPUT_VALID_URLS,
    FLATTENED_TRACKING_PARAM_URLS,
    FLATTENED_URLS_WITH_DIFFERENT_PATH,
    INVALID_URLS_TO_VALIDATE,
)
from tests.utils_for_test import (
    is_string_in_logs,
    is_string_in_logs_regex,
    trash_utub_url,
)

pytestmark = pytest.mark.urls


@pytest.mark.parametrize(
    "validated_url,input_url",
    [
        (validated_url, input_url)
        for (validated_url, input_url) in FLATTENED_NORMALIZED_AND_INPUT_VALID_URLS
    ],
)
def test_update_valid_url_with_fresh_valid_url(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    validated_url,
    input_url,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL not already in the database via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify that the new URL is stored in the database with same title, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    NORMALIZED_URL = ada_url.URL(validated_url).href
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: input_url},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        == url_in_this_utub.id
    )
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == NORMALIZED_URL
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs
    assert json_response[URL_SUCCESS.UTUB_NAME] == utub_creator_of.name
    UtubUrlDetailSchema.model_validate(json_response[URL_SUCCESS.URL])

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub.id,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == current_url_id,
            ).count()
            == 0
        )

        # Assert newest entity exist
        new_url_object: Urls = Urls.query.filter(
            Urls.url_string == NORMALIZED_URL
        ).first()
        new_url_id = int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == new_url_id,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == new_url_object.id,
            ).count()
            == 1
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == new_url_id,
        ).count() == len(associated_tags)


def test_update_url_in_locked_utub_is_rejected(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has a single URL, where the UTub is LOCKED
    WHEN the creator attempts to modify the URL string via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:utub_url_id>" with a fresh valid URL
    THEN the write-guard rejects the update: the server responds 403 with the locked-UTub
        JSON error (error code URLErrorCodes.UTUB_IS_LOCKED, message UTUB_FAILURE.UTUB_IS_LOCKED)
        and the URL string is left unchanged in the database.
    """
    NEW_URL_STRING = "https://www.example-locked-update.com"
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        utub_id_to_update = utub_creator_of.id
        utub_url_id_to_update = url_in_this_utub.id
        original_url_string = url_in_this_utub.standalone_url.url_string

        # Lock the UTub
        utub_creator_of.is_locked = True
        db.session.commit()

        # Assert-before-state: the URL string differs from the attempted new value
        assert original_url_string != NEW_URL_STRING

    update_url_response = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id_to_update,
            utub_url_id=utub_url_id_to_update,
        ),
        json={URL_FORM.URL_STRING: NEW_URL_STRING},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_response.status_code == 403
    update_url_response_json = update_url_response.json
    assert update_url_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert update_url_response_json[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert (
        int(update_url_response_json[STD_JSON.ERROR_CODE])
        == URLErrorCodes.UTUB_IS_LOCKED
    )

    with app.app_context():
        # The URL string is unchanged in the locked UTub
        unchanged_url_in_utub: Utub_Urls = Utub_Urls.query.get(utub_url_id_to_update)
        assert unchanged_url_in_utub.standalone_url.url_string == original_url_string


def test_update_url_string_records_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a logged-in creator of a UTub with a URL and metrics enabled
    WHEN they PATCH "/utubs/<utub_id>/urls/<utub_url_id>" with a different
        valid URL string (change-detected branch)
    THEN the request returns HTTP 200 AND exactly one URL_STRING_UPDATED
        counter key is written to the metrics Redis DB.
    """
    fresh_url_input, _expected_normalized = FLATTENED_NORMALIZED_AND_INPUT_VALID_URLS[0]
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        utub_id = utub_creator_of.id
        utub_url_id = url_in_this_utub.id

    # Before-state: no URL_STRING_UPDATED counter exists yet
    assert count_counter_keys(provide_metrics_redis, EventName.URL_STRING_UPDATED) == 0

    update_response = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        ),
        json={URL_FORM.URL_STRING: fresh_url_input},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_response.status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.URL_STRING_UPDATED) == 1


@pytest.mark.parametrize(
    "lowercase_url,valid_url",
    [
        (lowercase_url, valid_url)
        for (lowercase_url, valid_url) in FLATTENED_URLS_WITH_DIFFERENT_PATH
    ],
)
def test_update_valid_url_with_fresh_valid_url_with_diff_paths(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    lowercase_url,
    valid_url,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL not already in the database via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify that the new URL is stored in the database with same title, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    NORMALIZED_URL = ada_url.URL(valid_url).href
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: valid_url},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        == url_in_this_utub.id
    )
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == NORMALIZED_URL
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] != lowercase_url
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs
    assert json_response[URL_SUCCESS.UTUB_NAME] == utub_creator_of.name
    UtubUrlDetailSchema.model_validate(json_response[URL_SUCCESS.URL])

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub.id,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == current_url_id,
            ).count()
            == 0
        )

        # Assert newest entity exist
        new_url_object: Urls = Urls.query.filter(
            Urls.url_string == NORMALIZED_URL
        ).first()
        new_url_id = int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == new_url_id,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == new_url_object.id,
            ).count()
            == 1
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == new_url_id,
        ).count() == len(associated_tags)


def test_update_valid_url_with_another_fresh_valid_url_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL not already in the database via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify that the new URL is stored in the database with same title, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    URL_FOR_TEST = "https://yahoo.com"
    NORMALIZED_URL = ada_url.URL(URL_FOR_TEST).href
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Verify URL to modify to is not already in database
        assert Urls.query.filter(Urls.url_string == NORMALIZED_URL).first() is None

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: "yahoo.com"},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        == url_in_this_utub.id
    )
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == NORMALIZED_URL
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs
    assert json_response[URL_SUCCESS.UTUB_NAME] == utub_creator_of.name
    UtubUrlDetailSchema.model_validate(json_response[URL_SUCCESS.URL])

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub.id,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == current_url_id,
            ).count()
            == 0
        )

        # Assert newest entity exist
        new_url_object: Urls = Urls.query.filter(
            Urls.url_string == NORMALIZED_URL
        ).first()
        new_url_id = int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == new_url_id,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == new_url_object.id,
            ).count()
            == 1
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == new_url_id,
        ).count() == len(associated_tags)


def test_update_valid_url_with_another_fresh_valid_url_as_url_member(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, URLs added by each member, and tags associated with each URL
    WHEN the member attempts to modify the URL with a URL not already in the database, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the new URL is stored in the database with same title, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    URL_FOR_TEST = "https://yahoo.com"
    NORMALIZED_URL = ada_url.URL(URL_FOR_TEST).href
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_RAW_URL = "yahoo.com"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Verify URL to modify to is not already in database
        assert Urls.query.filter(Urls.url_string == NORMALIZED_URL).first() is None

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.user_id == current_user.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_member_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: NEW_RAW_URL},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        == url_in_this_utub.id
    )
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == NORMALIZED_URL
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub.id,
                Utub_Urls.utub_id == utub_member_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == current_url_id,
            ).first()
            is None
        )

        # Assert newest entity exist
        new_url_object: Urls = Urls.query.filter(
            Urls.url_string == NORMALIZED_URL
        ).first()
        new_url_id = int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == new_url_id,
                Utub_Urls.utub_id == utub_member_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == new_url_object.id,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == new_url_id,
        ).count() == len(associated_tags)


def test_update_valid_url_with_previously_added_url_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL already in the database, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in database and is not in this UTub
        url_not_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id
        ).first()

        url_string_of_url_not_in_utub = url_not_in_utub.standalone_url.url_string

        url_id_of_url_not_in_utub = url_not_in_utub.id

        # Grab URL that already exists in this UTub
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_in_utub.id
        id_of_url_object_in_utub = url_in_utub.url_id
        current_title = url_in_utub.url_title

        # Find associated tags with this url already in UTub
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_in_utub.id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        json={URL_FORM.URL_STRING: url_string_of_url_not_in_utub},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID]) == id_of_url_in_utub
    )
    assert (
        json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING]
        == url_string_of_url_not_in_utub
    )
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == id_of_url_object_in_utub,
            ).first()
            is None
        )

        # Assert newest entity exist
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == url_id_of_url_not_in_utub,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).count() == len(associated_tags)


def test_update_valid_url_with_previously_added_url_as_url_adder(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with a URL already in the database, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_member_of_not_created_utub: Utub_Members = Utub_Members.query.filter(
            Utub_Members.member_role != Member_Role.CREATOR
        ).first()
        utub_id = utub_member_of_not_created_utub.utub_id
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.user_id == current_user.id, Utub_Urls.utub_id == utub_id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id
        url_in_this_utub_id = url_in_this_utub.id

        # Get a URL that isn't in this UTub
        url_not_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.url_id != current_url_id, Utub_Urls.utub_id != utub_id
        ).first()
        url_string_of_url_not_in_utub: str = url_not_in_utub.standalone_url.url_string

        url_id_of_url_not_in_utub = url_not_in_utub.url_id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: url_string_of_url_not_in_utub},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        == url_in_this_utub_id
    )
    assert (
        json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING]
        == url_string_of_url_not_in_utub
    )
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub_id,
                Utub_Urls.utub_id == utub_id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is None
        )

        # Assert newest entity exist
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub_id,
                Utub_Urls.utub_id == utub_id,
                Utub_Urls.url_id == url_id_of_url_not_in_utub,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).count() == len(associated_tags)


def test_update_valid_url_with_same_url_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with the same URL already in the database, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.NO_CHANGE,
        STD_JSON.MESSAGE: URL_NO_CHANGE.URL_NOT_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        url_in_utub_string: str = url_already_in_utub.standalone_url.url_string
        current_title = url_already_in_utub.url_title
        url_object_id = url_already_in_utub.url_id

        # Find associated tags with this url already in UTub
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        json={URL_FORM.URL_STRING: url_in_utub_string},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_NOT_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID]) == id_of_url_in_utub
    )
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == url_in_utub_string
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_id == url_object_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).count() == len(associated_tags)


def test_update_valid_url_with_same_url_as_url_adder(
    add_two_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with the same URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.NO_CHANGE,
        STD_JSON.MESSAGE: URL_NO_CHANGE.URL_NOT_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Deterministically select a URL the current user added inside a UTub where
        # they are a NON-creator member. Selecting the URL first (ordered by id)
        # guarantees the row exists; picking an arbitrary non-creator UTub first could
        # land on one where the current user added no URL, making ``.first()`` return
        # None non-deterministically under pytest-randomly row ordering.
        non_creator_utub_ids = Utub_Members.query.with_entities(
            Utub_Members.utub_id
        ).filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role != Member_Role.CREATOR,
        )
        url_in_this_utub: Utub_Urls = (
            Utub_Urls.query.filter(
                Utub_Urls.user_id == current_user.id,
                Utub_Urls.utub_id.in_(non_creator_utub_ids),
            )
            .order_by(Utub_Urls.id)
            .first()
        )
        utub_id = url_in_this_utub.utub_id
        current_title = url_in_this_utub.url_title
        current_url_string = url_in_this_utub.standalone_url.url_string
        current_url_id = url_in_this_utub.url_id
        url_in_this_utub_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=url_in_this_utub_id,
        ),
        json={URL_FORM.URL_STRING: current_url_string},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_NOT_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        == url_in_this_utub_id
    )
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == current_url_string
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub_id,
                Utub_Urls.utub_id == utub_id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).count() == len(associated_tags)


@pytest.mark.parametrize(
    "invalid_url",
    [invalid_url for invalid_url in INVALID_URLS_TO_VALIDATE if "@" not in invalid_url],
)
def test_update_valid_url_with_invalid_url_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    invalid_url,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are not modified, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_VALIDATE_URL,
        STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_URL_ERROR
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        current_title = url_already_in_utub.url_title
        current_url_id = url_already_in_utub.url_id

        # Find associated tags with this url already in UTub
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        json={URL_FORM.URL_STRING: str(invalid_url)},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == URLErrorCodes.INVALID_URL_ERROR

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).count() == len(associated_tags)


@pytest.mark.parametrize(
    "invalid_url",
    [invalid_url for invalid_url in INVALID_URLS_TO_VALIDATE if "@" not in invalid_url],
)
def test_update_valid_url_with_invalid_url_as_url_adder(
    add_two_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
    invalid_url,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are not modified, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_VALIDATE_URL,
        STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_URL_ERROR
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Deterministically select a URL the current user added inside a UTub where
        # they are a NON-creator member. Selecting the URL first (ordered by id)
        # guarantees the row exists; picking an arbitrary non-creator UTub first could
        # land on one where the current user added no URL, making ``.first()`` return
        # None non-deterministically under pytest-randomly row ordering.
        non_creator_utub_ids = Utub_Members.query.with_entities(
            Utub_Members.utub_id
        ).filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role != Member_Role.CREATOR,
        )
        url_in_this_utub: Utub_Urls = (
            Utub_Urls.query.filter(
                Utub_Urls.user_id == current_user.id,
                Utub_Urls.utub_id.in_(non_creator_utub_ids),
            )
            .order_by(Utub_Urls.id)
            .first()
        )
        utub_id = url_in_this_utub.utub_id
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id
        url_in_this_utub_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=url_in_this_utub_id,
        ),
        json={URL_FORM.URL_STRING: str(invalid_url)},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == URLErrorCodes.INVALID_URL_ERROR

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub_id,
                Utub_Urls.utub_id == utub_id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).count() == len(associated_tags)


def test_update_valid_url_with_credentials_url_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are not modified, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_VALIDATE_URL,
        STD_JSON.ERROR_CODE: URLErrorCodes.URL_WITH_CREDENTIALS_ERROR
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        current_title = url_already_in_utub.url_title
        current_url_id = url_already_in_utub.url_id

        # Find associated tags with this url already in UTub
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    url_with_credentials = "https://user:password@example.com"
    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        json={URL_FORM.URL_STRING: url_with_credentials},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        json_response[STD_JSON.MESSAGE] == URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION
    )
    assert (
        int(json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.URL_WITH_CREDENTIALS_ERROR
    )

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).count() == len(associated_tags)


def test_update_valid_url_with_url_with_credentials_as_url_adder(
    add_two_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are not modified, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_VALIDATE_URL,
        STD_JSON.ERROR_CODE: URLErrorCodes.URL_WITH_CREDENTIALS_ERROR
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Deterministically select a URL the current user added inside a UTub where
        # they are a NON-creator member. Selecting the URL first (ordered by id)
        # guarantees the row exists; picking an arbitrary non-creator UTub first could
        # land on one where the current user added no URL, making ``.first()`` return
        # None non-deterministically under pytest-randomly row ordering.
        non_creator_utub_ids = Utub_Members.query.with_entities(
            Utub_Members.utub_id
        ).filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role != Member_Role.CREATOR,
        )
        url_in_this_utub: Utub_Urls = (
            Utub_Urls.query.filter(
                Utub_Urls.user_id == current_user.id,
                Utub_Urls.utub_id.in_(non_creator_utub_ids),
            )
            .order_by(Utub_Urls.id)
            .first()
        )
        utub_id = url_in_this_utub.utub_id
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id
        url_in_this_utub_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    url_with_credentials = "https://user:password@example.com"
    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=url_in_this_utub_id,
        ),
        json={URL_FORM.URL_STRING: url_with_credentials},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        json_response[STD_JSON.MESSAGE] == URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION
    )
    assert (
        int(json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.URL_WITH_CREDENTIALS_ERROR
    )

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub_id,
                Utub_Urls.utub_id == utub_id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).count() == len(associated_tags)


def test_update_valid_url_with_empty_url_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an empty URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are unmodified, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
        STD_JSON.ERROR_CODE : URLErrorCodes.INVALID_FORM_INPUT
        "Errors" : Object representing the errors found in the form, with the following fields
        {
            URL_FORM.URL_STRING: Array of errors associated with the url_string field,
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_URL = ""
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        current_title = url_already_in_utub.url_title
        current_url_id = url_already_in_utub.url_id

        # Find associated tags with this url already in UTub
        associated_tags: int = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_already_in_utub.id,
        ).count()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        json={URL_FORM.URL_STRING: NEW_URL},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert int(json_response[STD_JSON.ERROR_CODE]) == URLErrorCodes.INVALID_FORM_INPUT
    assert json_response[STD_JSON.ERRORS][URL_FORM.URL_STRING] == [FIELD_REQUIRED_STR]

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_creator_of.id,
                Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
            ).count()
            == associated_tags
        )


def test_update_url_string_with_fresh_valid_url_as_another_current_utub_member(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, URLs, and tags associated with each URL
    WHEN the member attempts to modify the URL and did not add the URL, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the backend denies the user, the url-utub-user associations and url-tag are not modified,
        all other URL associations are kept consistent, the server sends back a 403 HTTP status code,
        and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
        STD_JSON.ERROR_CODE : 1
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_FRESH_URL = "https://www.yahoo.com"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.user_id != current_user.id
        ).first()
        current_title = url_in_this_utub.url_title
        url_in_this_utub_id = url_in_this_utub.id
        url_in_utub_serialized_originally = UtubUrlDetailSchema.from_orm_url(
            url_in_this_utub
        ).model_dump(by_alias=True)
        original_url_id = url_in_this_utub.url_id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_member_of.id,
            utub_url_id=url_in_this_utub_id,
        ),
        json={URL_FORM.URL_STRING: NEW_FRESH_URL},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL

    with app.app_context():
        # Assert database is consistent after not modifying URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        utub_url_object: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_in_this_utub_id,
            Utub_Urls.utub_id == utub_member_of.id,
            Utub_Urls.url_id == original_url_id,
            Utub_Urls.url_title == current_title,
        ).first()

        # Verify original entry still exists
        assert utub_url_object is not None

        # Verify original serialization still exists
        assert (
            UtubUrlDetailSchema.from_orm_url(utub_url_object).model_dump(by_alias=True)
            == url_in_utub_serialized_originally
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).count() == len(associated_tags)


def test_update_url_with_fresh_valid_url_as_other_utub_member(
    add_first_user_to_second_utub_and_add_tags_remove_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of another UTub that has members, URLs, and tags associated with each URL
    WHEN the member attempts to modify the URL in a UTub they are not a member of, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the backend denies the user, the url-utub-user associations and url-tag are not modified,
        all other URL associations are kept consistent, the server sends back a 403 HTTP status code,
        and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
        STD_JSON.ERROR_CODE : 1
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_FRESH_URL = "https://www.yahoo.com"
    with app.app_context():
        # Get UTub this user is not a member of
        utub_user_not_member_of: Utubs = Utubs.query.get(3)

        # Verify URL to modify to is not already in database
        assert Urls.query.filter(Urls.url_string == NEW_FRESH_URL).first() is None

        # Get the URL not in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).first()
        url_in_utub_serialized_originally = UtubUrlDetailSchema.from_orm_url(
            url_in_this_utub
        ).model_dump(by_alias=True)
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.id

        # Get number of URLs in this UTub
        num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).count()

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_user_not_member_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: NEW_FRESH_URL},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 404

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_user_not_member_of.id
            ).count()
            == num_of_urls_in_utub
        )

        # Assert url-utub association hasn't changed
        assert (
            UtubUrlDetailSchema.from_orm_url(
                Utub_Urls.query.filter(
                    Utub_Urls.id == url_in_this_utub.id,
                    Utub_Urls.utub_id == utub_user_not_member_of.id,
                    Utub_Urls.url_id == original_url_id,
                    Utub_Urls.user_id == original_user_id,
                ).first()
            ).model_dump(by_alias=True)
            == url_in_utub_serialized_originally
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).count() == len(associated_tags)


def test_update_nonexistent_url_as_utub_creator(
    add_two_users_and_all_urls_to_each_utub_with_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with each URL
    WHEN the creator attempts to modify a nonexistent URL via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the server responds with a 404 status code, the url-utub-user associations and url-tag are not modified,
        all other URL associations are kept consistent
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_FRESH_URL = "https://www.yahoo.com"
    nonexistent_utub_url_id = 9999
    with app.app_context():
        # Get UTub this user is not a member of
        utub_member_user_not_member_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != current_user.id
        ).first()
        utub_user_not_member_of: Utubs = utub_member_user_not_member_of.to_utub

        # Use URL not already in database
        assert Urls.query.filter(Urls.url_string == NEW_FRESH_URL).first() is None

        # Get the URL not in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        url_in_utub_serialized_originally = UtubUrlDetailSchema.from_orm_url(
            url_in_this_utub
        ).model_dump(by_alias=True)
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.url_id

        # Get number of URLs in this UTub
        num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).count()

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_response = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_user_not_member_of.id,
            utub_url_id=nonexistent_utub_url_id,
        ),
        json={URL_FORM.URL_STRING: NEW_FRESH_URL},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_response.status_code == 404
    json_response = update_url_string_response.get_json()
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_user_not_member_of.id
            ).count()
            == num_of_urls_in_utub
        )

        utub_url_object: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_in_this_utub.id,
            Utub_Urls.utub_id == utub_user_not_member_of.id,
            Utub_Urls.url_id == original_url_id,
            Utub_Urls.user_id == original_user_id,
            Utub_Urls.url_title == current_title,
        ).first()

        # Assert url-utub association hasn't changed
        assert utub_url_object is not None

        assert (
            UtubUrlDetailSchema.from_orm_url(utub_url_object).model_dump(by_alias=True)
            == url_in_utub_serialized_originally
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).count() == len(associated_tags)


def test_update_url_with_fresh_valid_url_as_other_utub_creator(
    add_two_users_and_all_urls_to_each_utub_with_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with each URL
    WHEN the member attempts to modify the URL title and change the URL for a URL of another UTub, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the backend denies the user, the url-utub-user associations and url-tag are not modified,
        all other URL associations are kept consistent, the server sends back a 403 HTTP status code,
        and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
        STD_JSON.ERROR_CODE : 1
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_FRESH_URL = "https://www.yahoo.com"
    with app.app_context():
        # Get UTub this user is not a member of
        utub_member_user_not_member_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != current_user.id
        ).first()
        utub_user_not_member_of: Utubs = utub_member_user_not_member_of.to_utub

        # Use URL not already in database
        assert Urls.query.filter(Urls.url_string == NEW_FRESH_URL).first() is None

        # Get the URL not in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        url_in_utub_serialized_originally = UtubUrlDetailSchema.from_orm_url(
            url_in_this_utub
        ).model_dump(by_alias=True)
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.url_id

        # Get number of URLs in this UTub
        num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).count()

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_user_not_member_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: NEW_FRESH_URL},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 404

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_user_not_member_of.id
            ).count()
            == num_of_urls_in_utub
        )

        utub_url_object: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_in_this_utub.id,
            Utub_Urls.utub_id == utub_user_not_member_of.id,
            Utub_Urls.url_id == original_url_id,
            Utub_Urls.user_id == original_user_id,
            Utub_Urls.url_title == current_title,
        ).first()

        # Assert url-utub association hasn't changed
        assert utub_url_object is not None

        assert (
            UtubUrlDetailSchema.from_orm_url(utub_url_object).model_dump(by_alias=True)
            == url_in_utub_serialized_originally
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).count() == len(associated_tags)


def test_update_valid_url_with_missing_url_field_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a missing URL field, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
    THEN verify that the url-utub-user associations and url-tag are unmodified, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
        STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_FORM_INPUT,
        STD_JSON.ERRORS : Object representing the errors found in the form, with the following fields
        {
            URL_FORM.URL_STRING: Array of errors associated with the url_string field,
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        original_url_id = url_already_in_utub.url_id
        current_title = url_already_in_utub.url_title

        # Find associated tags with this url already in UTub
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_already_in_utub.id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_already_in_utub.id,
        ),
        json={},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert int(json_response[STD_JSON.ERROR_CODE]) == URLErrorCodes.INVALID_FORM_INPUT
    assert json_response[STD_JSON.ERRORS][URL_FORM.URL_STRING] == [FIELD_REQUIRED_STR]

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_already_in_utub.id,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_id == original_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).count() == len(associated_tags)


def test_update_valid_url_with_valid_url_missing_csrf(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a missing CSRF token, and a valid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.URL_STRING: String of URL to add
    THEN the UTub-user-URL associations are consistent across the change, all URLs/URL titles titles are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate HTML element
        indicating the CSRF token is missing
    """
    client, _, _, app = login_first_user_without_register

    NEW_URL = "yahoo.com"
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        original_url_id = url_already_in_utub.url_id
        current_title = url_already_in_utub.url_title

        # Find associated tags with this url already in UTub
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_already_in_utub.id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_response = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_already_in_utub.id,
        ),
        json={URL_FORM.URL_STRING: NEW_URL},
    )

    # Ensure valid reponse
    assert update_url_string_response.status_code == 403
    assert update_url_string_response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in update_url_string_response.data

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_id == original_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).count() == len(associated_tags)


def test_update_valid_url_updates_utub_last_updated(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL already in the database, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify the server sends back a 200 HTTP status code, and the UTub's last updated is updated

    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_creator_of.last_updated

        # Grab URL that already exists in database and is not in this UTub
        url_not_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id
        ).first()
        url_string_of_url_not_in_utub: str = url_not_in_utub.standalone_url.url_string

        # Grab URL that already exists in this UTub
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_utub.id,
        ),
        json={URL_FORM.URL_STRING: url_string_of_url_not_in_utub},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200

    with app.app_context():
        # Assert database is consistent after newly modified URL
        current_utub: Utubs = Utubs.query.get(utub_creator_of.id)
        assert (current_utub.last_updated - initial_last_updated).total_seconds() > 0


@mock.patch("backend.extensions.notifications.notifications.threading.Thread")
@mock.patch("backend.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_invalid_url_does_not_update_utub_last_updated(
    mock_validate_url,
    mock_thread,
    add_two_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN the server sends back a 400 HTTP status code, and the UTub last updated field is not modified
    """
    mock_thread_response = mock.MagicMock()
    mock_thread_response.start.return_value = None
    mock_thread.return_value = mock_thread_response

    mock_validate_url.side_effect = InvalidURLError
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Deterministically select a URL the current user added inside a UTub where
        # they are a NON-creator member. Selecting the URL first (ordered by id)
        # guarantees the row exists; picking an arbitrary non-creator UTub first could
        # land on one where the current user added no URL, making ``.first()`` return
        # None non-deterministically under pytest-randomly row ordering.
        non_creator_utub_ids = Utub_Members.query.with_entities(
            Utub_Members.utub_id
        ).filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role != Member_Role.CREATOR,
        )
        url_in_this_utub: Utub_Urls = (
            Utub_Urls.query.filter(
                Utub_Urls.user_id == current_user.id,
                Utub_Urls.utub_id.in_(non_creator_utub_ids),
            )
            .order_by(Utub_Urls.id)
            .first()
        )
        utub_id = url_in_this_utub.utub_id
        utub_member_of: Utubs = Utubs.query.get(utub_id)

        initial_last_updated = utub_member_of.last_updated

    mock_validate_url.side_effect = InvalidURLError
    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: "aaa"},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 400

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(utub_id)
        assert current_utub.last_updated == initial_last_updated


def test_update_utub_url_with_url_already_in_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, URLs added by each member, and tags associated with each URL
    WHEN the member attempts to modify the URL with a URL already in the UTub, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the server responds with a 409 HTTP status code, the URL is not modified in the UTub, and the proper JSON response
        is given

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.URL_IN_UTUB,
        STD_JSON.ERROR_CODE: URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get UTub this user is member of
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Find URL already in UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id
        ).first()
        current_url_id = url_in_this_utub.url_id
        current_url_string = url_in_this_utub.standalone_url.url_string

        # Find another URL in this UTub that doesn't match given URL
        other_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.url_id != current_url_id
        ).first()
        other_utub_url_id_to_update = other_url_in_utub.id
        other_url_id = other_url_in_utub.url_id

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_member_of.id,
            utub_url_id=other_utub_url_id_to_update,
        ),
        json={URL_FORM.URL_STRING: current_url_string},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 409

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.URL_IN_UTUB
    assert json_response[STD_JSON.ERROR_CODE] == URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR
    assert json_response[MODEL_STRS.URL_STRING] == current_url_string

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.url_id == other_url_id
            ).first()
            is not None
        )


def _first_utub_row_info(app: Flask, url_id: int) -> tuple[int, str]:
    """Returns (utub_url_id, url_string) of the given URL's row in UTub 1."""
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == 1, Utub_Urls.url_id == url_id
        ).one()
        return utub_url.id, utub_url.standalone_url.url_string


def _patch_url_string(
    client: FlaskClient, csrf_token: str, utub_url_id: int, url_string: str
) -> TestResponse:
    """PATCHes the URL string of the given row in UTub 1."""
    return client.patch(
        url_for(ROUTES.URLS.UPDATE_URL, utub_id=1, utub_url_id=utub_url_id),
        json={URL_FORM.URL_STRING: url_string},
        headers={"X-CSRFToken": csrf_token},
    )


def test_update_url_to_trashed_url_in_utub_revives_trashed_row_and_trashes_edited(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN UTub 1 where URL 3 (added by user 3, shared tag) is trashed and live URL 1 (added by
        user 1, shared + solo tags) is the one being edited
    WHEN the UTub creator (a manager, not URL 3's adder) edits URL 1's string to URL 3's string
    THEN the trashed row is revived in place (same utubUrlID) and takes over the edited card's
        title, adder and added_at, the edited row is trashed like a normal delete with its tag
        snapshot, the tags are unioned on the revived row, and the response reports
        revivedFromTrash, replacedUtubUrlID, appliedTags with live counts and the new counts for
        the edited row's tags
    """
    client, csrf_token, _, app = login_first_user_without_register
    edited_utub_url_id, _ = _first_utub_row_info(app, url_id=1)
    trashed_utub_url_id, trashed_url_string = _first_utub_row_info(app, url_id=3)

    with app.app_context():
        edited_row: Utub_Urls = Utub_Urls.query.get(edited_utub_url_id)
        edited_title = edited_row.url_title
        edited_added_at = edited_row.added_at
        edited_tag_ids = edited_row.associated_tag_ids
        trashed_tag_ids = Utub_Urls.query.get(trashed_utub_url_id).associated_tag_ids
        initial_row_count = Utub_Urls.query.count()
        initial_url_count = Urls.query.count()
        initial_utub_last_updated = Utubs.query.get(1).last_updated
    shared_tag_id, solo_tag_id = edited_tag_ids
    assert trashed_tag_ids == [shared_tag_id]

    trash_utub_url(app, trashed_utub_url_id, deleted_by=3)

    response = _patch_url_string(
        client, csrf_token, edited_utub_url_id, trashed_url_string
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert response_json[MODEL_STRS.REVIVED_FROM_TRASH] is True
    assert response_json[MODEL_STRS.LOST_TAG_COUNT] == 0
    assert response_json[MODEL_STRS.REPLACED_UTUB_URL_ID] == edited_utub_url_id

    url_json = response_json[MODEL_STRS.URL]
    assert url_json[MODEL_STRS.UTUB_URL_ID] == trashed_utub_url_id
    assert url_json[MODEL_STRS.URL_STRING] == trashed_url_string
    assert url_json[MODEL_STRS.URL_TITLE] == edited_title
    assert sorted(
        url_tag[MODEL_STRS.UTUB_TAG_ID] for url_tag in url_json[MODEL_STRS.URL_TAGS]
    ) == [shared_tag_id, solo_tag_id]

    # Live counts: URL 1 is now trashed, so the shared tag is on URL 2 + the revived row
    # and the solo tag only on the revived row
    applied_tag_counts = {
        applied_tag[MODEL_STRS.ID]: applied_tag[MODEL_STRS.TAG_APPLIED]
        for applied_tag in response_json[MODEL_STRS.APPLIED_TAGS]
    }
    assert applied_tag_counts == {shared_tag_id: 2, solo_tag_id: 1}
    assert {
        int(tag_id): count
        for tag_id, count in response_json[TAG_COUNTS_MODIFIED].items()
    } == {shared_tag_id: 2, solo_tag_id: 1}

    with app.app_context():
        revived_row: Utub_Urls = Utub_Urls.query.get(trashed_utub_url_id)
        assert revived_row.deleted_at is None
        assert revived_row.deleted_by is None
        assert revived_row.trashed_tag_ids is None
        assert revived_row.user_id == 1
        assert revived_row.url_title == edited_title
        assert revived_row.added_at == edited_added_at
        assert revived_row.associated_tag_ids == [shared_tag_id, solo_tag_id]

        trashed_edited_row: Utub_Urls = Utub_Urls.query.get(edited_utub_url_id)
        assert trashed_edited_row.is_trashed
        assert trashed_edited_row.deleted_by == 1
        assert trashed_edited_row.trashed_tag_ids == edited_tag_ids

        live_utub_url_ids = {
            live_row.id
            for live_row in Utub_Urls.query.filter(
                Utub_Urls.utub_id == 1, Utub_Urls.deleted_at.is_(None)
            ).all()
        }
        assert edited_utub_url_id not in live_utub_url_ids
        assert trashed_utub_url_id in live_utub_url_ids

        # No row or URL was created or hard-deleted
        assert Utub_Urls.query.count() == initial_row_count
        assert Urls.query.count() == initial_url_count
        assert Utubs.query.get(1).last_updated > initial_utub_last_updated


def test_update_url_to_trashed_url_unions_tags_of_both_rows(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN UTub 1 where URL 1 (shared + solo tags) is trashed and live URL 3 (shared tag) is edited
    WHEN the UTub creator edits URL 3's string to URL 1's string
    THEN the revived row keeps its own tags and gains the edited row's, with no duplicate
        association for the tag both rows carried
    """
    client, csrf_token, _, app = login_first_user_without_register
    edited_utub_url_id, _ = _first_utub_row_info(app, url_id=3)
    trashed_utub_url_id, trashed_url_string = _first_utub_row_info(app, url_id=1)

    with app.app_context():
        shared_tag_id, solo_tag_id = Utub_Urls.query.get(
            trashed_utub_url_id
        ).associated_tag_ids
        assert Utub_Urls.query.get(edited_utub_url_id).associated_tag_ids == [
            shared_tag_id
        ]
        # An extra tag only on the edited row
        extra_tag = Utub_Tags(utub_id=1, tag_string="editedonlytag", created_by=1)
        db.session.add(extra_tag)
        db.session.flush()
        extra_tag_id = extra_tag.id
        db.session.add(
            Utub_Url_Tags(
                utub_id=1,
                utub_url_id=edited_utub_url_id,
                utub_tag_id=extra_tag_id,
                user_id=1,
            )
        )
        db.session.commit()

    trash_utub_url(app, trashed_utub_url_id, deleted_by=1)

    response = _patch_url_string(
        client, csrf_token, edited_utub_url_id, trashed_url_string
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json[MODEL_STRS.REVIVED_FROM_TRASH] is True
    assert response_json[MODEL_STRS.LOST_TAG_COUNT] == 0
    expected_tag_ids = sorted([shared_tag_id, solo_tag_id, extra_tag_id])
    assert (
        sorted(
            applied_tag[MODEL_STRS.ID]
            for applied_tag in response_json[MODEL_STRS.APPLIED_TAGS]
        )
        == expected_tag_ids
    )

    with app.app_context():
        assert Utub_Urls.query.get(trashed_utub_url_id).associated_tag_ids == (
            expected_tag_ids
        )
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_url_id == trashed_utub_url_id,
                Utub_Url_Tags.utub_tag_id == shared_tag_id,
            ).count()
            == 1
        )


def test_update_url_to_trashed_url_reports_lost_tags(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN UTub 1 where URL 1 (shared + solo tags) is trashed and then its solo tag is deleted
        from the UTub, and live URL 2 (shared tag) is edited
    WHEN the UTub creator edits URL 2's string to URL 1's string
    THEN lostTagCount is 1 and only the surviving shared tag is on the revived row
    """
    client, csrf_token, _, app = login_first_user_without_register
    edited_utub_url_id, _ = _first_utub_row_info(app, url_id=2)
    trashed_utub_url_id, trashed_url_string = _first_utub_row_info(app, url_id=1)

    with app.app_context():
        shared_tag_id, solo_tag_id = Utub_Urls.query.get(
            trashed_utub_url_id
        ).associated_tag_ids

    trash_utub_url(app, trashed_utub_url_id, deleted_by=1)

    with app.app_context():
        db.session.delete(Utub_Tags.query.get(solo_tag_id))
        db.session.commit()

    response = _patch_url_string(
        client, csrf_token, edited_utub_url_id, trashed_url_string
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json[MODEL_STRS.REVIVED_FROM_TRASH] is True
    assert response_json[MODEL_STRS.LOST_TAG_COUNT] == 1
    assert [
        applied_tag[MODEL_STRS.ID]
        for applied_tag in response_json[MODEL_STRS.APPLIED_TAGS]
    ] == [shared_tag_id]
    # The edited row's only tag is the shared one, now on URL 3 + the revived row
    assert {
        int(tag_id): count
        for tag_id, count in response_json[TAG_COUNTS_MODIFIED].items()
    } == {shared_tag_id: 2}

    with app.app_context():
        revived_row: Utub_Urls = Utub_Urls.query.get(trashed_utub_url_id)
        assert revived_row.deleted_at is None
        assert revived_row.associated_tag_ids == [shared_tag_id]


def test_update_url_to_trashed_url_as_non_adder_member_drops_trashed_tags(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register,
):
    """
    GIVEN UTub 1 where URL 1 (added by user 1, shared + solo tags) is trashed and live URL 2
        (added by user 2, shared tag) is edited
    WHEN plain member user 2 (neither URL 1's adder nor a manager) edits URL 2's string to URL 1's
    THEN the revived row does not keep URL 1's old tags: only the edited row's tags remain, the solo
        tag association is gone, lostTagCount is 0 and the row now belongs to user 2
    """
    client, csrf_token, _, app = login_second_user_without_register
    edited_utub_url_id, _ = _first_utub_row_info(app, url_id=2)
    trashed_utub_url_id, trashed_url_string = _first_utub_row_info(app, url_id=1)

    with app.app_context():
        shared_tag_id, solo_tag_id = Utub_Urls.query.get(
            trashed_utub_url_id
        ).associated_tag_ids

    trash_utub_url(app, trashed_utub_url_id, deleted_by=1)

    response = _patch_url_string(
        client, csrf_token, edited_utub_url_id, trashed_url_string
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json[MODEL_STRS.REVIVED_FROM_TRASH] is True
    assert response_json[MODEL_STRS.LOST_TAG_COUNT] == 0
    assert [
        applied_tag[MODEL_STRS.ID]
        for applied_tag in response_json[MODEL_STRS.APPLIED_TAGS]
    ] == [shared_tag_id]
    # The edited row's only tag is the shared one, now on URL 3 + the revived row
    assert {
        int(tag_id): count
        for tag_id, count in response_json[TAG_COUNTS_MODIFIED].items()
    } == {shared_tag_id: 2}

    with app.app_context():
        revived_row: Utub_Urls = Utub_Urls.query.get(trashed_utub_url_id)
        assert revived_row.deleted_at is None
        assert revived_row.trashed_tag_ids is None
        assert revived_row.user_id == 2
        assert revived_row.associated_tag_ids == [shared_tag_id]
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_url_id == trashed_utub_url_id,
                Utub_Url_Tags.utub_tag_id == solo_tag_id,
            ).count()
            == 0
        )
        assert Utub_Urls.query.get(edited_utub_url_id).is_trashed


def test_update_url_to_trashed_url_over_tag_limit_is_400_and_changes_nothing(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN UTub 1 where trashed URL 1 holds MAX_URL_TAGS - 1 tags and live URL 3 carries two tags
        URL 1 lacks (so the union exceeds the per-URL limit)
    WHEN the UTub creator edits URL 3's string to URL 1's string
    THEN the response is the at-tag-limit 400 and nothing changed: URL 1 is still trashed with its
        snapshot, URL 3 is still live with its tags, and no tag or association row was written
    """
    client, csrf_token, _, app = login_first_user_without_register
    edited_utub_url_id, _ = _first_utub_row_info(app, url_id=3)
    trashed_utub_url_id, trashed_url_string = _first_utub_row_info(app, url_id=1)

    with app.app_context():
        for tag_index in range(TAG_CONSTANTS.MAX_URL_TAGS - 3):
            filler_tag = Utub_Tags(
                utub_id=1, tag_string=f"fillertag{tag_index}", created_by=1
            )
            db.session.add(filler_tag)
            db.session.flush()
            db.session.add(
                Utub_Url_Tags(
                    utub_id=1,
                    utub_url_id=trashed_utub_url_id,
                    utub_tag_id=filler_tag.id,
                    user_id=1,
                )
            )
        for tag_index in range(2):
            edited_only_tag = Utub_Tags(
                utub_id=1, tag_string=f"editedonly{tag_index}", created_by=1
            )
            db.session.add(edited_only_tag)
            db.session.flush()
            db.session.add(
                Utub_Url_Tags(
                    utub_id=1,
                    utub_url_id=edited_utub_url_id,
                    utub_tag_id=edited_only_tag.id,
                    user_id=1,
                )
            )
        db.session.commit()
        trashed_snapshot_tag_ids = Utub_Urls.query.get(
            trashed_utub_url_id
        ).associated_tag_ids
        edited_tag_ids = Utub_Urls.query.get(edited_utub_url_id).associated_tag_ids
    assert len(trashed_snapshot_tag_ids) == TAG_CONSTANTS.MAX_URL_TAGS - 1

    trash_utub_url(app, trashed_utub_url_id, deleted_by=1)

    with app.app_context():
        initial_tag_vocab_count = Utub_Tags.query.count()
        initial_url_tag_count = Utub_Url_Tags.query.count()
        trashed_at = Utub_Urls.query.get(trashed_utub_url_id).deleted_at
        edited_title = Utub_Urls.query.get(edited_utub_url_id).url_title
        initial_utub_last_updated = Utubs.query.get(1).last_updated

    response = _patch_url_string(
        client, csrf_token, edited_utub_url_id, trashed_url_string
    )

    assert response.status_code == 400
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.MAX_URL_TAGS_REACHED.format(
        max_tags=TAG_CONSTANTS.MAX_URL_TAGS
    )

    with app.app_context():
        still_trashed_row: Utub_Urls = Utub_Urls.query.get(trashed_utub_url_id)
        assert still_trashed_row.is_trashed
        assert still_trashed_row.deleted_at == trashed_at
        assert still_trashed_row.trashed_tag_ids == trashed_snapshot_tag_ids
        assert still_trashed_row.associated_tag_ids == trashed_snapshot_tag_ids

        still_live_row: Utub_Urls = Utub_Urls.query.get(edited_utub_url_id)
        assert not still_live_row.is_trashed
        assert still_live_row.trashed_tag_ids is None
        assert still_live_row.url_title == edited_title
        assert still_live_row.associated_tag_ids == edited_tag_ids

        assert Utub_Tags.query.count() == initial_tag_vocab_count
        assert Utub_Url_Tags.query.count() == initial_url_tag_count
        assert Utubs.query.get(1).last_updated == initial_utub_last_updated


def test_update_url_to_concurrently_revived_url_is_live_conflict_409(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN UTub 1 where URL 3 is trashed when the edit of URL 1 to URL 3's string is validated
    WHEN another request revives URL 3 before the edit takes its row locks
    THEN the edit falls back to the live-conflict 409 (URL_IN_UTUB, with the urlString echoed),
        and neither row is changed by the edit
    """
    client, csrf_token, _, app = login_first_user_without_register
    edited_utub_url_id, _ = _first_utub_row_info(app, url_id=1)
    trashed_utub_url_id, trashed_url_string = _first_utub_row_info(app, url_id=3)

    with app.app_context():
        edited_row: Utub_Urls = Utub_Urls.query.get(edited_utub_url_id)
        edited_title = edited_row.url_title
        edited_tag_ids = edited_row.associated_tag_ids
        trashed_title = Utub_Urls.query.get(trashed_utub_url_id).url_title
        initial_url_tag_count = Utub_Url_Tags.query.count()

    trash_utub_url(app, trashed_utub_url_id, deleted_by=3)

    def validate_then_revive_concurrently(
        url_string: str, utub_id: int
    ) -> ValidatedUrl:
        validated_new_url = validate_new_url_for_utub(url_string, utub_id)
        with app.app_context():
            concurrent_row: Utub_Urls = Utub_Urls.query.get(trashed_utub_url_id)
            concurrent_row.deleted_at = None
            concurrent_row.deleted_by = None
            concurrent_row.trashed_tag_ids = None
            db.session.commit()
        return validated_new_url

    with mock.patch(
        "backend.urls.services.update_urls.validate_new_url_for_utub",
        side_effect=validate_then_revive_concurrently,
    ):
        response = _patch_url_string(
            client, csrf_token, edited_utub_url_id, trashed_url_string
        )

    assert response.status_code == 409
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == URL_FAILURE.URL_IN_UTUB
    assert (
        int(response_json[STD_JSON.ERROR_CODE])
        == URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR
    )
    assert response_json[MODEL_STRS.URL_STRING] == trashed_url_string

    with app.app_context():
        unchanged_edited_row: Utub_Urls = Utub_Urls.query.get(edited_utub_url_id)
        assert not unchanged_edited_row.is_trashed
        assert unchanged_edited_row.url_title == edited_title
        assert unchanged_edited_row.associated_tag_ids == edited_tag_ids
        concurrently_revived_row: Utub_Urls = Utub_Urls.query.get(trashed_utub_url_id)
        assert not concurrently_revived_row.is_trashed
        assert concurrently_revived_row.url_title == trashed_title
        assert Utub_Url_Tags.query.count() == initial_url_tag_count


def test_update_url_to_trashed_url_when_edited_row_concurrently_trashed_is_404(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
) -> None:
    """
    GIVEN UTub 1 where URL 3 is trashed when the edit of URL 1 to URL 3's string is validated
    WHEN another request trashes the edited row (URL 1) before the edit takes its row locks
    THEN the edit aborts with 404 NOT_FOUND, the trashed target row is still trashed with
        its original deleted_at and trashed_tag_ids, and no Utub_Url_Tags rows are added
        or removed
    """
    client, csrf_token, _, app = login_first_user_without_register
    edited_utub_url_id, _ = _first_utub_row_info(app, url_id=1)
    trashed_utub_url_id, trashed_url_string = _first_utub_row_info(app, url_id=3)

    trash_utub_url(app, trashed_utub_url_id, deleted_by=3)

    with app.app_context():
        target_row: Utub_Urls = Utub_Urls.query.get(trashed_utub_url_id)
        original_deleted_at = target_row.deleted_at
        original_trashed_tag_ids = list(target_row.trashed_tag_ids)
        initial_url_tag_count = Utub_Url_Tags.query.count()

    def validate_then_trash_edited_row_concurrently(
        url_string: str, utub_id: int
    ) -> ValidatedUrl:
        validated_new_url = validate_new_url_for_utub(url_string, utub_id)
        trash_utub_url(app, edited_utub_url_id, deleted_by=2)
        return validated_new_url

    with mock.patch(
        "backend.urls.services.update_urls.validate_new_url_for_utub",
        side_effect=validate_then_trash_edited_row_concurrently,
    ):
        response = _patch_url_string(
            client, csrf_token, edited_utub_url_id, trashed_url_string
        )

    assert response.status_code == 404
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND

    with app.app_context():
        still_trashed_target: Utub_Urls = Utub_Urls.query.get(trashed_utub_url_id)
        assert still_trashed_target.is_trashed
        assert still_trashed_target.deleted_at == original_deleted_at
        assert still_trashed_target.trashed_tag_ids == original_trashed_tag_ids
        assert Utub_Urls.query.get(edited_utub_url_id).is_trashed
        assert Utub_Url_Tags.query.count() == initial_url_tag_count


def test_update_url_to_trashed_url_with_tracking_params_strips_and_revives(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN UTub 1 where URL 3 (shared tag) is trashed and metrics are enabled
    WHEN the UTub creator edits URL 1 (shared + solo tags) to URL 3's string with tracking params appended
    THEN the tracking params are stripped so the trashed row is matched and revived (not stored
        with the tracking params), and the same metrics events as a normal edit are recorded:
        one URL_STRING_UPDATED, one URL_TRACKING_PARAMS_STRIPPED with stripped "true", and one
        TAG_APPLIED per tag newly applied to the revived row, with no add/remove-from-UTub events
    """
    client, csrf_token, _, app = login_first_user_without_register
    edited_utub_url_id, _ = _first_utub_row_info(app, url_id=1)
    trashed_utub_url_id, trashed_url_string = _first_utub_row_info(app, url_id=3)

    trash_utub_url(app, trashed_utub_url_id, deleted_by=3)

    response = _patch_url_string(
        client,
        csrf_token,
        edited_utub_url_id,
        trashed_url_string + "?utm_source=x&gclid=y",
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json[MODEL_STRS.REVIVED_FROM_TRASH] is True
    assert response_json[MODEL_STRS.URL][MODEL_STRS.UTUB_URL_ID] == trashed_utub_url_id
    assert response_json[MODEL_STRS.URL][MODEL_STRS.URL_STRING] == trashed_url_string

    with app.app_context():
        assert Utub_Urls.query.get(trashed_utub_url_id).deleted_at is None
        assert (
            Utub_Urls.query.get(trashed_utub_url_id).standalone_url.url_string
            == trashed_url_string
        )
        assert Utub_Urls.query.get(edited_utub_url_id).is_trashed

    assert sum_counter_values(provide_metrics_redis, EventName.URL_STRING_UPDATED) == 1
    stripped_keys = find_counter_keys(
        provide_metrics_redis, EventName.URL_TRACKING_PARAMS_STRIPPED
    )
    assert len(stripped_keys) == 1
    assert parse_dims(stripped_keys[0])[STRIPPED_DIM_KEY] == "true"
    # Only the solo tag was new to the revived row (the shared tag was already on it)
    assert sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.URL_ADDED_TO_UTUB) == 0
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_REMOVED_FROM_UTUB) == 0
    )


def test_update_url_to_trashed_url_in_locked_utub_is_rejected(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a LOCKED UTub 1 where URL 3 is trashed
    WHEN the UTub creator edits URL 1's string to URL 3's string
    THEN the write-guard rejects it with the locked-UTub 403 and neither row is changed
    """
    client, csrf_token, _, app = login_first_user_without_register
    edited_utub_url_id, _ = _first_utub_row_info(app, url_id=1)
    trashed_utub_url_id, trashed_url_string = _first_utub_row_info(app, url_id=3)

    trash_utub_url(app, trashed_utub_url_id, deleted_by=3)

    with app.app_context():
        locked_utub: Utubs = Utubs.query.get(1)
        locked_utub.is_locked = True
        db.session.commit()

    response = _patch_url_string(
        client, csrf_token, edited_utub_url_id, trashed_url_string
    )

    assert response.status_code == 403
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert int(response_json[STD_JSON.ERROR_CODE]) == URLErrorCodes.UTUB_IS_LOCKED

    with app.app_context():
        assert Utub_Urls.query.get(trashed_utub_url_id).is_trashed
        assert not Utub_Urls.query.get(edited_utub_url_id).is_trashed


def test_update_url_to_fresh_url_response_has_revive_defaults(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a live URL in UTub 1 and a fresh valid URL string not in the UTub
    WHEN the UTub creator edits the URL to the fresh string
    THEN the response is the ordinary edit success with the revive fields at their defaults
    """
    client, csrf_token, _, app = login_first_user_without_register
    edited_utub_url_id, _ = _first_utub_row_info(app, url_id=1)

    response = _patch_url_string(
        client, csrf_token, edited_utub_url_id, "https://www.example-fresh-edit.com"
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json[MODEL_STRS.REVIVED_FROM_TRASH] is False
    assert response_json[MODEL_STRS.LOST_TAG_COUNT] == 0
    assert response_json.get(MODEL_STRS.REPLACED_UTUB_URL_ID) is None
    assert response_json[MODEL_STRS.APPLIED_TAGS] == []
    assert response_json[TAG_COUNTS_MODIFIED] == {}


def test_update_valid_url_with_fresh_valid_url_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL not already in the database via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 200 HTTP status code, and the logs are valid
    """
    URL_FOR_TEST = "https://yahoo.com"
    UPDATED_URL = ada_url.URL(URL_FOR_TEST).href
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Verify URL to modify to is not already in database
        assert Urls.query.filter(Urls.url_string == UPDATED_URL).first() is None

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: "yahoo.com"},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200
    assert is_string_in_logs(
        "Finished checks for url_string='yahoo.com'", caplog.records
    )
    assert is_string_in_logs_regex(r"(.*)Took (\d).(\d+) ms(.*)", caplog.records)

    with app.app_context():
        new_url = Urls.query.filter(Urls.url_string == UPDATED_URL).first()

    assert is_string_in_logs(f"Added new URL, URL.id={new_url.id}", caplog.records)
    assert is_string_in_logs("Added URL to UTub", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_creator_of.id}", caplog.records)
    assert is_string_in_logs(f"URL.id={new_url.id}", caplog.records)


def test_update_valid_url_with_existing_url_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL already in the database via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 200 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        url_not_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id
        ).first()
        url_string = url_not_in_this_utub.standalone_url.url_string
        url_id = url_not_in_this_utub.url_id

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: url_string},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200
    assert is_string_in_logs(
        f"Finished checks for url_string='{url_string}'", caplog.records
    )
    assert is_string_in_logs_regex(r"(.*)Took (\d).(\d+) ms(.*)", caplog.records)

    assert is_string_in_logs(
        f"URL already exists in U4I, URL.id={url_id}", caplog.records
    )
    assert is_string_in_logs("Added URL to UTub", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_creator_of.id}", caplog.records)
    assert is_string_in_logs(f"URL.id={url_id}", caplog.records)


def test_update_valid_url_with_same_url_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with the same URL (with the scheme
        omitted from the input, which normalizes back to the stored URL) via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 200 HTTP status code (no-change, since the
        validated input is equivalent to the stored URL), and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        url_string = url_in_this_utub.standalone_url.url_string
        utub_url_id = url_in_this_utub.id

    url_to_change_to = url_string.replace("https://", "")
    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: url_to_change_to},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_NOT_MODIFIED

    assert is_string_in_logs(
        f"Finished checks for url_string='{url_to_change_to}'", caplog.records
    )
    assert is_string_in_logs_regex(r"(.*)Took (\d).(\d+) ms(.*)", caplog.records)

    assert is_string_in_logs(
        f"User={user.id} tried changing UTubURL.id={utub_url_id} to the same URL",
        caplog.records,
    )


def test_update_valid_url_with_same_url_before_normalization_url_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL not in database but after
        normalization is equivalent to the stored URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 200 HTTP status code (no-change, since the
        validated input is equivalent to the stored URL), and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        url_string = url_in_this_utub.standalone_url.url_string
        utub_url_id = url_in_this_utub.id
        url_string_before_normalize = url_string.replace("https://", "")

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: url_string_before_normalize},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_NOT_MODIFIED

    assert is_string_in_logs(
        f"Finished checks for url_string='{url_string_before_normalize}'",
        caplog.records,
    )
    assert is_string_in_logs_regex(r"(.*)Took (\d).(\d+) ms(.*)", caplog.records)

    assert is_string_in_logs(
        f"User={user.id} tried changing UTubURL.id={utub_url_id} to the same URL",
        caplog.records,
    )


@mock.patch("backend.extensions.notifications.notifications.threading.Thread")
@mock.patch("backend.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_to_invalid_url_log(
    mock_validate_url,
    mock_thread,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 400 HTTP status code, and the logs are valid
    """
    mock_thread_response = mock.MagicMock()
    mock_thread_response.start.return_value = None
    mock_thread.return_value = mock_thread_response

    client, csrf_token_string, user, app = login_first_user_without_register
    mock_validate_url.side_effect = InvalidURLError("Invalid URL error")

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        url_string = url_in_this_utub.standalone_url.url_string.replace("https://", "")

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: url_string},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 400
    assert is_string_in_logs(
        f"Unable to validate the URL given by User={user.id}", caplog.records
    )
    assert is_string_in_logs_regex(
        r"(.*)[\s](.*)Took (\d).(\d+) ms to fail validation[\s](.*)[\s](.*)",
        caplog.records,
    )
    assert is_string_in_logs(f"url_string={url_string}", caplog.records)
    assert is_string_in_logs("Exception=Invalid URL error", caplog.records)


def test_update_to_same_url_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 200 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        url_string = url_in_this_utub.standalone_url.url_string

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        json={URL_FORM.URL_STRING: url_string},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200
    assert is_string_in_logs(
        f"User={user.id} tried changing UTubURL.id={url_in_this_utub.id} to the same URL",
        caplog.records,
    )


def test_update_url_user_not_allowed_to_log(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN a member attempts to modify URL they did not add with URL via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 403 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        url_in_this_utub_did_not_add: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != user.id,
            Utub_Urls.user_id != user.id,
        ).first()
        utub_id = url_in_this_utub_did_not_add.utub_id
        utub_url_id = url_in_this_utub_did_not_add.id
        url_string = url_in_this_utub_did_not_add.standalone_url.url_string

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        ),
        json={URL_FORM.URL_STRING: url_string},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 403
    assert is_string_in_logs(
        f"User={user.id} not URL adder or UTub manager: UTubURL.id={utub_url_id} in UTub.id={utub_id}",
        caplog.records,
    )


def test_update_url_with_only_spaces_log(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN a member attempts to modify URL but gives URL string with only spaces in body via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 400 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == user.id,
            Utub_Urls.user_id == user.id,
        ).first()
        utub_id = url_in_this_utub.utub_id
        utub_url_id = url_in_this_utub.id

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        ),
        json={URL_FORM.URL_STRING: "  "},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 400
    assert is_string_in_logs(
        f"User={user.id} tried changing UTubURL.id={utub_url_id} to a URL with only spaces",
        caplog.records,
    )


def test_update_url_with_invalid_form_log(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN a member attempts to modify URL but gives no JSON body via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN verify the server sends back a 400 HTTP status code and @api_route logs the missing body
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == user.id,
            Utub_Urls.user_id == user.id,
        ).first()
        utub_id = url_in_this_utub.utub_id
        utub_url_id = url_in_this_utub.id

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        ),
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 400
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert is_string_in_logs(f"User={user.id}", caplog.records)
    assert is_string_in_logs("Missing JSON body", caplog.records)


@mock.patch("backend.extensions.notifications.notifications.requests.post")
@mock.patch("backend.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_url_unknown_exception_sends_notification(
    mock_validate_url,
    mock_request_post,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add that contains an invalid URL
    THEN verify that server sends back a 400 HTTP status code and a notification is sent
    """
    notification_sent = threading.Event()

    def mock_post_with_event(*args, **kwargs):
        mock_response = type("MockResponse", (), {"status_code": 200})()
        notification_sent.set()  # Signal that the request was made
        return mock_response

    mock_request_post.side_effect = mock_post_with_event
    mock_validate_url.side_effect = Exception
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        json={URL_FORM.URL_STRING: "AAAAA"},
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Wait for notification to be sent (with timeout)
    assert notification_sent.wait(timeout=5.0), (
        "Notification was not sent within timeout"
    )

    assert update_url_string_form.status_code == 400

    mock_request_post.assert_called_once()


@pytest.mark.parametrize(
    "expected_stripped,input_url",
    FLATTENED_TRACKING_PARAM_URLS,
)
def test_update_url_strips_tracking_params(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    expected_stripped,
    input_url,
):
    """
    GIVEN a valid creator of a UTub that has a single URL with tags
    WHEN the creator updates that URL to a fresh, tracking-laden URL via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN verify the stored URL row and echoed response both contain the stripped
        canonical form (tracking params removed).
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        utub_url_id = url_in_this_utub.id

        # Assert before-state: stripped URL not yet present
        assert Urls.query.filter(Urls.url_string == expected_stripped).count() == 0

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=utub_url_id,
        ),
        json={URL_FORM.URL_STRING: input_url},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200

    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == expected_stripped

    with app.app_context():
        assert Urls.query.filter(Urls.url_string == expected_stripped).count() == 1


def test_update_url_same_target_with_tracking_params_is_no_change(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub with a single stored URL (no tracking params)
    WHEN the creator PATCHes that same URL with tracking params appended (which
        strip back to the stored value)
    THEN verify the response is the clean no-change response (URL_NOT_MODIFIED),
        NOT a 409 conflict.
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        url_in_utub_string: str = url_already_in_utub.standalone_url.url_string

        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    tracking_variant = url_in_utub_string + "?utm_source=x"

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        json={URL_FORM.URL_STRING: tracking_variant},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200

    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_NOT_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID]) == id_of_url_in_utub
    )

    with app.app_context():
        # No new rows created on a no-change update
        assert num_of_urls == Urls.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()


@pytest.mark.parametrize(
    "client_trimmed_url",
    [
        "https://example.com/p?ref=x",
        "https://example.com/p?sort=date",
        "https://example.com/p?page=2",
        "https://example.com/p?q=1&q=2",
        "https://example.com/search?q=hello%20world",
        "https://example.com/?continue=https://gogle.cm",
    ],
)
def test_update_url_stores_exactly_what_client_sent_for_non_blocklisted_params(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    client_trimmed_url,
):
    """
    GIVEN a valid creator of a UTub that has a single URL with tags
    WHEN the creator PATCHes that URL to a string whose query holds only
        non-blocklisted params (what the client-side trim control submits)
    THEN the response echoes, and the Urls row stores, exactly that string.
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        utub_url_id = url_in_this_utub.id

        assert Urls.query.filter(Urls.url_string == client_trimmed_url).count() == 0

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=utub_url_id,
        ),
        json={URL_FORM.URL_STRING: client_trimmed_url},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 200
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == client_trimmed_url

    with app.app_context():
        assert Urls.query.filter(Urls.url_string == client_trimmed_url).count() == 1


def test_update_url_trimmed_back_to_stored_value_is_no_change(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub whose URL was updated to a string with a
        non-blocklisted query ("...?ref=x")
    WHEN the creator PATCHes that URL with the exact stored string again (what
        the edit form submits after the user drops an extra param they had typed)
    THEN the response is 200 with status "No change" and the stored echo, never
        a 409, and no new Urls or Utub_Urls rows are created.
    """
    client, csrf_token_string, _, app = login_first_user_without_register
    stored_with_query = "https://example.com/p?ref=x"

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        utub_id = utub_creator_of.id
        utub_url_id = url_in_this_utub.id

    seed_response = client.patch(
        url_for(ROUTES.URLS.UPDATE_URL, utub_id=utub_id, utub_url_id=utub_url_id),
        json={URL_FORM.URL_STRING: stored_with_query},
        headers={"X-CSRFToken": csrf_token_string},
    )
    assert seed_response.status_code == 200

    with app.app_context():
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    trimmed_response = client.patch(
        url_for(ROUTES.URLS.UPDATE_URL, utub_id=utub_id, utub_url_id=utub_url_id),
        json={URL_FORM.URL_STRING: stored_with_query},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert trimmed_response.status_code == 200
    json_response = trimmed_response.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_NOT_MODIFIED
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == stored_with_query
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID]) == utub_url_id

    with app.app_context():
        assert Urls.query.count() == num_of_urls
        assert Utub_Urls.query.count() == num_of_url_utubs_assocs


def test_update_user_trimmed_url_collision_returns_plain_in_utub_message(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub containing multiple distinct stored URLs
    WHEN the creator PATCHes one URL to the exact stored string of another URL
        in the UTub (the client-trimmed form of "<other>?ref=x")
    THEN the server responds 409 with URL_ALREADY_IN_UTUB_ERROR and the plain
        URL_IN_UTUB message, because it cannot tell a user trim happened. This is
        why the friendlier trim-conflict message is substituted client-side.
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        target_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id
        ).first()
        target_url_id = target_url_in_utub.url_id
        target_url_string: str = target_url_in_utub.standalone_url.url_string

        other_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id,
            Utub_Urls.url_id != target_url_id,
        ).first()
        other_utub_url_id_to_update = other_url_in_utub.id

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_member_of.id,
            utub_url_id=other_utub_url_id_to_update,
        ),
        json={URL_FORM.URL_STRING: target_url_string},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 409
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.URL_IN_UTUB
    assert (
        int(json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR
    )


def test_update_url_tracking_param_collision_returns_informative_message(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub containing multiple distinct stored URLs
    WHEN the creator PATCHes one URL to the tracking-laden variant of another URL
        already in the UTub (which strips back to that other URL's stored value)
    THEN verify the server responds with a 409 conflict and the informative
        tracking-params-stripped message.
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # The canonical target URL already in the UTub (stored, no tracking params)
        target_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id
        ).first()
        target_url_id = target_url_in_utub.url_id
        target_url_string: str = target_url_in_utub.standalone_url.url_string

        # A different URL in the same UTub that we will try to update
        other_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id,
            Utub_Urls.url_id != target_url_id,
        ).first()
        other_utub_url_id_to_update = other_url_in_utub.id

    tracking_variant = target_url_string + "?utm_source=x"

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_member_of.id,
            utub_url_id=other_utub_url_id_to_update,
        ),
        json={URL_FORM.URL_STRING: tracking_variant},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_url_string_form.status_code == 409

    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        json_response[STD_JSON.MESSAGE]
        == URL_FAILURE.URL_IN_UTUB_TRACKING_PARAMS_STRIPPED
    )
    assert json_response[STD_JSON.ERROR_CODE] == URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR


def test_update_url_string_records_tracking_params_stripped_true(
    metrics_enabled_app,
    provide_metrics_redis,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a logged-in creator of a UTub with a URL and metrics enabled
    WHEN they PATCH that URL to a fresh tracking-laden URL string
    THEN exactly one URL_TRACKING_PARAMS_STRIPPED counter is written with the
        stripped dimension set to "true", alongside exactly one
        URL_STRING_UPDATED event.
    """
    tracking_url = "https://example.com/page?utm_source=a&gclid=x"
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        utub_id = utub_creator_of.id
        utub_url_id = url_in_this_utub.id

    # Before-state: no tracking-params-stripped counter exists yet
    assert (
        count_counter_keys(
            provide_metrics_redis, EventName.URL_TRACKING_PARAMS_STRIPPED
        )
        == 0
    )

    update_response = client.patch(
        url_for(ROUTES.URLS.UPDATE_URL, utub_id=utub_id, utub_url_id=utub_url_id),
        json={URL_FORM.URL_STRING: tracking_url},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_response.status_code == 200
    stripped_keys = find_counter_keys(
        provide_metrics_redis, EventName.URL_TRACKING_PARAMS_STRIPPED
    )
    assert len(stripped_keys) == 1
    assert parse_dims(stripped_keys[0])[STRIPPED_DIM_KEY] == "true"
    assert count_counter_keys(provide_metrics_redis, EventName.URL_STRING_UPDATED) == 1


def test_update_url_string_records_tracking_params_stripped_false(
    metrics_enabled_app,
    provide_metrics_redis,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a logged-in creator of a UTub with a URL and metrics enabled
    WHEN they PATCH that URL to a fresh clean URL string (no tracking params)
    THEN exactly one URL_TRACKING_PARAMS_STRIPPED counter is written with the
        stripped dimension set to "false".
    """
    clean_url = "https://example.com/page?q=search&sort=date"
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        utub_id = utub_creator_of.id
        utub_url_id = url_in_this_utub.id

    # Before-state: no tracking-params-stripped counter exists yet
    assert (
        count_counter_keys(
            provide_metrics_redis, EventName.URL_TRACKING_PARAMS_STRIPPED
        )
        == 0
    )

    update_response = client.patch(
        url_for(ROUTES.URLS.UPDATE_URL, utub_id=utub_id, utub_url_id=utub_url_id),
        json={URL_FORM.URL_STRING: clean_url},
        headers={"X-CSRFToken": csrf_token_string},
    )

    assert update_response.status_code == 200
    stripped_keys = find_counter_keys(
        provide_metrics_redis, EventName.URL_TRACKING_PARAMS_STRIPPED
    )
    assert len(stripped_keys) == 1
    assert parse_dims(stripped_keys[0])[STRIPPED_DIM_KEY] == "false"
