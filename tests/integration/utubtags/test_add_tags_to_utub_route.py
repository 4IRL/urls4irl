from flask import url_for
from flask_login import current_user
import pytest

from src.models.utub_tags import Utub_Tags
from src.models.utubs import Utubs
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.all_routes import ROUTES
from src.utils.constants import TAG_CONSTANTS
from src.utils.strings.form_strs import TAG_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS

pytestmark = pytest.mark.tags


def test_add_tag_to_utub(every_user_in_every_utub, login_first_user_without_register):
    """
    GIVEN UTubs with members in every UTub, but no tags
    WHEN a tag is added to a UTub
    THEN verify that a new UtubTag item exists, the server responds with a 200 HTTP status code,
        and the proper JSON response is given

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_ADDED_TO_UTUB,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                MODEL_STRS.UTUB_TAG_ID: Integer representing ID of tag newly added,
                TAG_FORM.TAG_STRING: String representing the tag just added
            }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register
    NEW_TAG = "Funny!"

    with app.app_context():
        utub_to_add_tag_to: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        num_of_tag_in_utub = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_to_add_tag_to.id, Utub_Tags.tag_string == NEW_TAG
        ).count()
        num_of_utub_tags = Utub_Tags.query.count()

    new_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token, TAG_FORM.TAG_STRING: NEW_TAG}

    add_tag_response = client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_to_add_tag_to.id),
        data=new_tag_form,
    )

    assert add_tag_response.status_code == 200
    add_tag_response_json = add_tag_response.json

    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_ADDED_TO_UTUB
    assert (
        add_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODEL_STRS.TAG_STRING] == NEW_TAG
    )

    with app.app_context():
        new_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_to_add_tag_to.id, Utub_Tags.tag_string == NEW_TAG
        ).first()
        assert (
            new_tag.id
            == add_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODEL_STRS.UTUB_TAG_ID]
        )

        assert (
            Utub_Tags.query.filter(
                Utub_Tags.utub_id == utub_to_add_tag_to.id,
                Utub_Tags.tag_string == NEW_TAG,
            ).count()
            == num_of_tag_in_utub + 1
        )
        assert Utub_Tags.query.count() == num_of_utub_tags + 1


def test_add_same_tag_to_multiple_utubs(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN UTubs with members in every UTub, but no tags
    WHEN the same tag is added to every UTub
    THEN verify that a new UtubTag item exists, the server responds with a 200 HTTP status code,
        and the proper JSON response is given

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_ADDED_TO_UTUB,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                MODEL_STRS.UTUB_TAG_ID: Integer representing ID of tag newly added,
                TAG_FORM.TAG_STRING: String representing the tag just added
            }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register
    NEW_TAG = "Funny!"

    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.all()
        utub_tag_count: int = Utub_Tags.query.count()

    for utub in all_utubs:
        utub_id = utub.id
        with app.app_context():
            num_of_tag_in_utub = Utub_Tags.query.filter(
                Utub_Tags.utub_id == utub_id, Utub_Tags.tag_string == NEW_TAG
            ).count()

        new_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token, TAG_FORM.TAG_STRING: NEW_TAG}

        add_tag_response = client.post(
            url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_id),
            data=new_tag_form,
        )

        assert add_tag_response.status_code == 200
        add_tag_response_json = add_tag_response.json

        assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert add_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_ADDED_TO_UTUB
        assert (
            add_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODEL_STRS.TAG_STRING]
            == NEW_TAG
        )

        with app.app_context():
            new_tag: Utub_Tags = Utub_Tags.query.filter(
                Utub_Tags.utub_id == utub_id, Utub_Tags.tag_string == NEW_TAG
            ).first()
            assert (
                new_tag.id
                == add_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODEL_STRS.UTUB_TAG_ID]
            )

            assert (
                Utub_Tags.query.filter(
                    Utub_Tags.utub_id == utub_id, Utub_Tags.tag_string == NEW_TAG
                ).count()
                == num_of_tag_in_utub + 1
            )
            assert Utub_Tags.query.count() == utub_tag_count + 1

        utub_tag_count += 1


def test_add_duplicate_tag_to_utub(
    add_one_tag_to_each_utub_after_all_users_added, login_first_user_without_register
):
    """
    GIVEN UTubs already containing a tag and users
    WHEN a user wants to add a tag to a UTub that already exists
    THEN verify that the server responds with a 400 HTTP status code, and responds with the appropriate JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.TAG_ALREADY_IN_UTUB,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        tag_already_added: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_of_user.id
        ).first()
        tag_string_already_added = tag_already_added.tag_string

    new_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_string_already_added,
    }

    add_tag_response = client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_of_user.id),
        data=new_tag_form,
    )

    assert add_tag_response.status_code == 400
    add_tag_response_json = add_tag_response.json

    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_tag_response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.TAG_ALREADY_IN_UTUB


def test_add_empty_tag_to_utub(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN UTubs with every user in them
    WHEN a user tries to add a tag with an empty tag string
    THEN verify that the server responds with a 400 HTTP status code, and responds with the appropriate JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

    new_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token, TAG_FORM.TAG_STRING: ""}

    add_tag_response = client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_of_user.id),
        data=new_tag_form,
    )

    assert add_tag_response.status_code == 400
    add_tag_response_json = add_tag_response.json

    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_tag_response_json[STD_JSON.MESSAGE]
        == TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB
    )
    assert STD_JSON.ERRORS in add_tag_response_json

    assert (
        add_tag_response_json[STD_JSON.ERRORS][MODEL_STRS.TAG_STRING]
        == TAGS_FAILURE.FIELD_REQUIRED
    )


def test_add_fully_sanitized_tag_to_utub(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN UTubs with every user in them
    WHEN a user tries to add a tag with a tag that is sanitized by the backend
    THEN verify that the server responds with a 400 HTTP status code, and responds with the appropriate JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.INVALID_INPUT,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

    new_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: '<img src="evl.jpg">',
    }

    add_tag_response = client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_of_user.id),
        data=new_tag_form,
    )

    assert add_tag_response.status_code == 400
    add_tag_response_json = add_tag_response.json

    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_tag_response_json[STD_JSON.MESSAGE]
        == TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB
    )
    assert STD_JSON.ERRORS in add_tag_response_json

    assert add_tag_response_json[STD_JSON.ERRORS][MODEL_STRS.TAG_STRING] == [
        TAGS_FAILURE.INVALID_INPUT
    ]


def test_add_partially_sanitized_tag_to_utub(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN UTubs with every user in them
    WHEN a user tries to add a tag with a tag that is sanitized by the backend
    THEN verify that the server responds with a 400 HTTP status code, and responds with the appropriate JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.INVALID_INPUT,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

    for tag_string in (
        "<<HELLO>>",
        "<h1>Hello</h1>",
    ):
        new_tag_form = {
            TAG_FORM.CSRF_TOKEN: csrf_token,
            TAG_FORM.TAG_STRING: tag_string,
        }

        add_tag_response = client.post(
            url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_of_user.id),
            data=new_tag_form,
        )

        assert add_tag_response.status_code == 400
        add_tag_response_json = add_tag_response.json

        assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert (
            add_tag_response_json[STD_JSON.MESSAGE]
            == TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB
        )
        assert STD_JSON.ERRORS in add_tag_response_json

        assert add_tag_response_json[STD_JSON.ERRORS][MODEL_STRS.TAG_STRING] == [
            TAGS_FAILURE.INVALID_INPUT
        ]


def test_add_long_tag_to_utub(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN UTubs with every user in them
    WHEN a user tries to add a tag with an empty tag string
    THEN verify that the server responds with a 400 HTTP status code, and responds with the appropriate JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

    new_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: "a" * (TAG_CONSTANTS.MAX_TAG_LENGTH + 1),
    }

    add_tag_response = client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_of_user.id),
        data=new_tag_form,
    )

    assert add_tag_response.status_code == 400
    add_tag_response_json = add_tag_response.json

    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_tag_response_json[STD_JSON.MESSAGE]
        == TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB
    )
    assert STD_JSON.ERRORS in add_tag_response_json

    for limit in (
        TAG_CONSTANTS.MAX_TAG_LENGTH,
        TAG_CONSTANTS.MIN_TAG_LENGTH,
    ):
        assert (
            str(limit)
            in add_tag_response_json[STD_JSON.ERRORS][MODEL_STRS.TAG_STRING][0]
        )


def test_add_tag_to_utub_not_member_of(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN UTubs with only a single member in every UTub, and no tags
    WHEN a user tries to add a tag to a UTub they aren't a member of
    THEN verify that no new UtubTag item exists, the server responds with a 403 HTTP status code,
        and the proper JSON response is given

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
        STD_JSON.ERROR_CODE : 1
    }
    """
    client, csrf_token, _, app = login_first_user_without_register
    NEW_TAG = "Funny!"

    with app.app_context():
        utub_to_add_tag_to: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        num_of_tag_in_utub = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_to_add_tag_to.id
        ).count()
        num_of_utub_tags = Utub_Tags.query.count()

    new_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token, TAG_FORM.TAG_STRING: NEW_TAG}

    add_tag_response = client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_to_add_tag_to.id),
        data=new_tag_form,
    )

    assert add_tag_response.status_code == 403
    add_tag_response_json = add_tag_response.json

    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_tag_response_json[STD_JSON.MESSAGE]
        == TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB
    )
    assert add_tag_response_json[STD_JSON.ERROR_CODE] == 1

    with app.app_context():
        assert num_of_utub_tags == Utub_Tags.query.count()
        assert (
            num_of_tag_in_utub
            == Utub_Tags.query.filter(
                Utub_Tags.utub_id == utub_to_add_tag_to.id
            ).count()
        )


def test_add_tag_to_nonexistent_utub(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN UTubs with every member in every UTub, and no tags
    WHEN a user tries to add a tag to a UTub that does not exist
    THEN verify that no new UtubTag item exists, the server responds with a 404 HTTP status code,
        and the proper HTML response is given
    """
    client, csrf_token, _, app = login_first_user_without_register
    NEW_TAG = "Funny!"
    NONEXISTENT_UTUB_ID = 999

    with app.app_context():
        num_of_utub_tags = Utub_Tags.query.count()

    new_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token, TAG_FORM.TAG_STRING: NEW_TAG}

    add_tag_response = client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=NONEXISTENT_UTUB_ID),
        data=new_tag_form,
    )

    assert add_tag_response.status_code == 404
    assert IDENTIFIERS.HTML_404.encode() in add_tag_response.data

    with app.app_context():
        assert num_of_utub_tags == Utub_Tags.query.count()


def test_add_tag_to_utub_missing_csrf_token(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN UTubs with members in every UTub, but no tags
    WHEN a tag is added to a UTub but the form is missing the CSRF token
    THEN verify that a new UtubTag item exists, the server responds with a 400 HTTP status code,
        and the proper HTML response is given
    """
    client, _, _, app = login_first_user_without_register
    NEW_TAG = "Funny!"

    with app.app_context():
        utub_to_add_tag_to: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        num_of_tag_in_utub = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_to_add_tag_to.id
        ).count()
        num_of_utub_tags = Utub_Tags.query.count()

    new_tag_form = {TAG_FORM.TAG_STRING: NEW_TAG}

    add_tag_response = client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_to_add_tag_to.id),
        data=new_tag_form,
    )

    assert add_tag_response.status_code == 400
    assert IDENTIFIERS.CSRF_MISSING.encode() in add_tag_response.data

    with app.app_context():
        assert num_of_utub_tags == Utub_Tags.query.count()
        assert (
            num_of_tag_in_utub
            == Utub_Tags.query.filter(
                Utub_Tags.utub_id == utub_to_add_tag_to.id
            ).count()
        )


def test_add_tag_to_utub_missing_tag_field(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN UTubs with members in every UTub, but no tags
    WHEN a tag is added to a UTub but the form is missing the CSRF token
    THEN verify that a new UtubTag item exists, the server responds with a 400 HTTP status code,
        and the proper JSON response is given

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
        STD_JSON.ERROR_CODE : 3,
        STD_JSON.ERRORS: {
            TAG_FORM.TAG_STRING: ["This field is required."]
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_to_add_tag_to: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        num_of_tag_in_utub = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_to_add_tag_to.id
        ).count()
        num_of_utub_tags = Utub_Tags.query.count()

    new_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    add_tag_response = client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_to_add_tag_to.id),
        data=new_tag_form,
    )

    assert add_tag_response.status_code == 400
    add_tag_response_json = add_tag_response.json

    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_tag_response_json[STD_JSON.MESSAGE]
        == TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB
    )
    assert add_tag_response_json[STD_JSON.ERROR_CODE] == 3
    assert STD_JSON.ERRORS in add_tag_response_json
    assert (
        add_tag_response_json[STD_JSON.ERRORS][TAG_FORM.TAG_STRING]
        == TAGS_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        assert num_of_utub_tags == Utub_Tags.query.count()
        assert (
            num_of_tag_in_utub
            == Utub_Tags.query.filter(
                Utub_Tags.utub_id == utub_to_add_tag_to.id
            ).count()
        )


def test_add_tag_updates_utub_last_updated(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN UTubs with members in every UTub, but no tags
    WHEN a tag is added to a UTub
    THEN ensure that the server responds with a 200 HTTP status code, and the UTub's last updated
        field is updated
    """
    client, csrf_token, _, app = login_first_user_without_register
    NEW_TAG = "Funny!"

    with app.app_context():
        utub_to_add_tag_to: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_to_add_tag_to.last_updated

    new_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token, TAG_FORM.TAG_STRING: NEW_TAG}

    add_tag_response = client.post(
        url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_to_add_tag_to.id),
        data=new_tag_form,
    )

    assert add_tag_response.status_code == 200

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(utub_to_add_tag_to.id)
        assert (current_utub.last_updated - initial_last_updated).total_seconds() > 0
