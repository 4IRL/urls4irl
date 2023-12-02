from flask import url_for
from flask_login import current_user

from src.models import Utub, URLS, Utub_Urls
from tests.models_for_test import valid_url_strings
from src.utils import strings as U4I_STRINGS

URL_FORM = U4I_STRINGS.URL_FORM
URL_SUCCESS = U4I_STRINGS.URL_SUCCESS
STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
MODEL_STRS = U4I_STRINGS.MODELS
URL_FAILURE = U4I_STRINGS.URL_FAILURE


def test_add_valid_url_as_utub_member(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a (previously generated) URL to a UTub they are a part of
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Url_UTub-User association exists where it didn't before

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : URL_SUCCESS.URL_ADDED,
        MODEL_STRS.URL : {
            "url_string": String representing the URL ,
            "url_ID" : Integer representing the URL ID
        },
        URL_SUCCESS.UTUB_ID : Integer representing the ID of the UTub added to,
        URL_SUCCESS.UTUB_NAME : String representing the name of the UTub added to,
        URL_SUCCESS.ADDED_BY : Integer representing the ID of current user who added this URL to this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        assert current_user in [user.to_user for user in current_utub_member_of.members]

        # Ensure no URLs in this UTub
        assert len(current_utub_member_of.utub_urls) == 0
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == current_utub_member_of.id
                ).all()
            )
            == 0
        )

        # Grab a URL to add
        url_to_add = URLS.query.first()
        number_of_urls_in_db = len(URLS.query.all())
        url_id_to_add = url_to_add.id
        url_string_to_add = url_to_add.url_string
        url_description_to_add = f"This is {url_string_to_add}"
        utub_id_to_add_to = current_utub_member_of.id
        utub_name_to_add = current_utub_member_of.name

        # Ensure Url-Utub-User association does not exist
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id_to_add_to,
                    Utub_Urls.url_id == url_id_to_add,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 0
        )

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_DESCRIPTION: url_description_to_add,
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 200

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_ADDED
    assert int(add_url_json_response[URL_SUCCESS.UTUB_ID]) == utub_id_to_add_to
    assert add_url_json_response[URL_SUCCESS.UTUB_NAME] == utub_name_to_add
    assert int(add_url_json_response[URL_SUCCESS.ADDED_BY]) == current_user.id
    assert (
        add_url_json_response[MODEL_STRS.URL][URL_FORM.URL_STRING] == url_string_to_add
    )
    assert (
        int(add_url_json_response[MODEL_STRS.URL][URL_SUCCESS.URL_ID]) == url_id_to_add
    )

    with app.app_context():
        # Ensure no new URL created
        assert len(URLS.query.all()) == number_of_urls_in_db

        # Get the UTub again
        current_utub_member_of = Utub.query.get(utub_id_to_add_to)

        # Ensure URL now in UTub
        assert len(current_utub_member_of.utub_urls) > 0
        assert url_id_to_add in [url.url_id for url in current_utub_member_of.utub_urls]

        # Ensure Url-Utub-User association exists
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id_to_add_to,
                    Utub_Urls.url_id == url_id_to_add,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 1
        )

        assert len(Utub_Urls.query.all()) == initial_utub_urls + 1


def test_add_valid_url_as_utub_creator(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a (previously generated) URL to a UTub they are a creator of
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Url_UTub-User association exists where it didn't before

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : URL_SUCCESS.URL_ADDED,
        MODEL_STRS.URL : {
            URL_FORM.URL_STRING: String representing the URL ,
            URL_SUCCESS.URL_ID : Integer representing the URL ID
        },
        URL_SUCCESS.UTUB_ID : Integer representing the ID of the UTub added to,
        URL_SUCCESS.UTUB_NAME : String representing the name of the UTub added to,
        URL_SUCCESS.ADDED_BY : Integer representing the ID of current user who added this URL to this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a creator of
        current_utub_member_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        assert current_user in [user.to_user for user in current_utub_member_of.members]

        # Ensure no URLs in this UTub
        assert len(current_utub_member_of.utub_urls) == 0
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == current_utub_member_of.id
                ).all()
            )
            == 0
        )

        # Grab a URL to add
        url_to_add = URLS.query.first()
        number_of_urls_in_db = len(URLS.query.all())
        url_id_to_add = url_to_add.id
        url_string_to_add = url_to_add.url_string
        url_description_to_add = f"This is {url_string_to_add}"
        utub_id_to_add_to = current_utub_member_of.id
        utub_name_to_add = current_utub_member_of.name

        # Ensure Url-Utub-User association does not exist
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id_to_add_to,
                    Utub_Urls.url_id == url_id_to_add,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 0
        )

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_DESCRIPTION: url_description_to_add,
    }
    add_url_response = client.post(
        url_for("urls.add_url", utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 200

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_ADDED
    assert int(add_url_json_response[URL_SUCCESS.UTUB_ID]) == utub_id_to_add_to
    assert add_url_json_response[URL_SUCCESS.UTUB_NAME] == utub_name_to_add
    assert int(add_url_json_response[URL_SUCCESS.ADDED_BY]) == current_user.id
    assert (
        add_url_json_response[MODEL_STRS.URL][URL_FORM.URL_STRING] == url_string_to_add
    )
    assert (
        int(add_url_json_response[MODEL_STRS.URL][URL_SUCCESS.URL_ID]) == url_id_to_add
    )

    with app.app_context():
        # Ensure no new URL created
        assert len(URLS.query.all()) == number_of_urls_in_db

        # Get the UTub again
        current_utub_member_of = Utub.query.get(utub_id_to_add_to)

        # Ensure URL now in UTub
        assert len(current_utub_member_of.utub_urls) > 0
        assert url_id_to_add in [url.url_id for url in current_utub_member_of.utub_urls]

        # Ensure Url-Utub-User association exists
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id_to_add_to,
                    Utub_Urls.url_id == url_id_to_add,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 1
        )

        assert len(Utub_Urls.query.all()) == initial_utub_urls + 1


def test_add_invalid_url_as_utub_member(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a nonexistant URL to a UTub they are a part of
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response
        is sent by the server, and that no new new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : "Failure",
        STD_JSON.MESSAGE : "Unable to add this URL",
        "Error_code": 2
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        assert current_user in [user.to_user for user in current_utub_member_of.members]

        # Ensure no URLs in this UTub
        assert len(current_utub_member_of.utub_urls) == 0
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == current_utub_member_of.id
                ).all()
            )
            == 0
        )

        # Get current number of URLs
        number_of_urls_in_db = len(URLS.query.all())

        utub_id_to_add_to = current_utub_member_of.id

        # Ensure Url-Utub-User association does not exist
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id_to_add_to,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 0
        )

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Try to add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: "AAAA",
        URL_FORM.URL_DESCRIPTION: "This is AAAA",
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_ADD_URL
    assert int(add_url_json_response[STD_JSON.ERROR_CODE]) == 2

    with app.app_context():
        # Ensure no new URL created
        assert len(URLS.query.all()) == number_of_urls_in_db

        # Get the UTub again
        current_utub_member_of = Utub.query.get(utub_id_to_add_to)

        # Ensure no URL now in UTub
        assert len(current_utub_member_of.utub_urls) == 0

        # Ensure Url-Utub-User association does not exist
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id_to_add_to,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 0
        )

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_add_invalid_url_as_utub_creator(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a nonexistant URL to a UTub they are a creator of
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response
        is sent by the server, and that no new new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.UNABLE_TO_ADD_URL,
        "Error_code": 2
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a creator of
        current_utub_member_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        assert current_user in [user.to_user for user in current_utub_member_of.members]

        # Ensure no URLs in this UTub
        assert len(current_utub_member_of.utub_urls) == 0
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == current_utub_member_of.id
                ).all()
            )
            == 0
        )

        # Get current number of URLs
        number_of_urls_in_db = len(URLS.query.all())

        utub_id_to_add_to = current_utub_member_of.id

        # Ensure Url-Utub-User association does not exist
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id_to_add_to,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 0
        )

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Try to add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: "AAAA",
        URL_FORM.URL_DESCRIPTION: "This is AAAA",
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_ADD_URL
    assert int(add_url_json_response[STD_JSON.ERROR_CODE]) == 2

    with app.app_context():
        # Ensure no new URL created
        assert len(URLS.query.all()) == number_of_urls_in_db

        # Get the UTub again
        current_utub_member_of = Utub.query.get(utub_id_to_add_to)

        # Ensure no URL now in UTub
        assert len(current_utub_member_of.utub_urls) == 0

        # Ensure Url-Utub-User association does not exist
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id_to_add_to,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 0
        )

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_add_valid_url_to_nonexistent_utub(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a (previously generated) URL to a nonexistent UTub
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 404 HTTP status code
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        utub_id_to_add_to = 0
        utub_to_add_to = Utub.query.get(utub_id_to_add_to)
        while utub_to_add_to is not None and current_user in [
            user.to_user for user in utub_to_add_to.members
        ]:
            utub_id_to_add_to += 1

        # Get a valid URL
        valid_url_to_add = URLS.query.first()
        valid_url_string = valid_url_to_add.url_string
        valid_url_description = f"This is {valid_url_string}"

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: valid_url_string,
        URL_FORM.URL_DESCRIPTION: valid_url_description,
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 404

    with app.app_context():
        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_add_valid_url_to_utub_not_a_member_of(
    add_urls_to_database, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with only the creators in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a (previously generated) URL to a UTub the user is not a part of
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 403 HTTP status code, the server sends back the proper
        JSON response, and no new Url-UTub-User associations are added

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.UNABLE_TO_ADD_URL,
        STD_JSON.ERROR_CODE: 1
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is not a member of
        utub_not_member_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        assert current_user not in [user.to_user for user in utub_not_member_of.members]

        id_of_utub_not_member_of = utub_not_member_of.id

        # Get a valid URL
        valid_url_to_add = URLS.query.first()
        valid_url_string = valid_url_to_add.url_string
        valid_url_description = f"This is {valid_url_string}"

        # Ensure URL not in UTub currently
        assert len(utub_not_member_of.utub_urls) == 0
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_not_member_of
                ).all()
            )
            == 0
        )

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: valid_url_string,
        URL_FORM.URL_DESCRIPTION: valid_url_description,
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=id_of_utub_not_member_of), data=add_url_form
    )

    assert add_url_response.status_code == 403

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_ADD_URL
    assert int(add_url_json_response[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        utub_not_member_of = Utub.query.get(id_of_utub_not_member_of)

        # Ensure URL not in UTub currently
        assert len(utub_not_member_of.utub_urls) == 0
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_not_member_of
                ).all()
            )
            == 0
        )

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_add_fresh_url_to_utub(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and no URLs
        currently in the database or associated with the UTubs
    WHEN the user tries to add a fresh and valid URL to a UTub they are a creator of
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Url_UTub-User association exists, and that a new URL entity is created

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : "New URL created and added to UTub",
        MODEL_STRS.URL : {
            URL_FORM.URL_STRING: String representing the URL,
            URL_SUCCESS.URL_ID : Integer representing the URL ID
        },
        URL_SUCCESS.UTUB_ID : Integer representing the ID of the UTub added to,
        URL_SUCCESS.UTUB_NAME : String representing the name of the UTub added to,
        URL_SUCCESS.ADDED_BY : Integer representing the ID of current user who added this URL to this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register
    valid_url_to_add = valid_url_strings[0]

    with app.app_context():
        # Get this user's UTub
        utub_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        id_of_utub_that_is_creator_of = utub_creator_of.id
        name_of_utub_that_is_creator_of = utub_creator_of.name

        # Ensure URL not in UTub currently
        assert len(utub_creator_of.utub_urls) == 0
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_that_is_creator_of
                ).all()
            )
            == 0
        )

        # Ensure no URLs
        assert len(URLS.query.all()) == 0

        # Ensure no Url-Utub-User association exists
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 0
        )

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: valid_url_to_add,
        URL_FORM.URL_DESCRIPTION: f"This is {valid_url_to_add}",
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=id_of_utub_that_is_creator_of),
        data=add_url_form,
    )

    assert add_url_response.status_code == 200

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_CREATED_ADDED
    assert (
        int(add_url_json_response[URL_SUCCESS.UTUB_ID]) == id_of_utub_that_is_creator_of
    )
    assert (
        add_url_json_response[URL_SUCCESS.UTUB_NAME] == name_of_utub_that_is_creator_of
    )
    assert int(add_url_json_response[URL_SUCCESS.ADDED_BY]) == current_user.id

    url_id_added = int(add_url_json_response[MODEL_STRS.URL][URL_SUCCESS.URL_ID])

    with app.app_context():
        # Ensure new URL exists
        assert len(URLS.query.all()) == 1
        assert len(URLS.query.filter(URLS.url_string == valid_url_to_add).all()) == 1
        assert URLS.query.get(url_id_added).url_string == valid_url_to_add

        # Get the UTub again
        current_utub_creator_of = Utub.query.get(id_of_utub_that_is_creator_of)

        # Ensure URL now in UTub
        assert len(current_utub_creator_of.utub_urls) == 1

        # Ensure Url-Utub-User association exists
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 1
        )

        assert len(Utub_Urls.query.all()) == initial_utub_urls + 1


def test_add_duplicate_url_to_utub_as_same_user_who_added_url(
    add_all_urls_and_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        currently in the database, with all UTubs containing all URLs
    WHEN the user tries to add a URL to a UTub that they already added the URL to, as the creator of the UTub
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response
        is sent by the server, and that no new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : "URL already in UTub",
        STD_JSON.ERROR_CODE: 3
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub
        utub_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        id_of_utub_that_is_creator_of = utub_creator_of.id

        # Find the first URL in this UTub that this user added
        url_association_that_user_added = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first()

        url_that_user_added = url_association_that_user_added.url_in_utub
        url_id = url_that_user_added.id
        url_string_to_add = url_that_user_added.url_string
        url_description_to_add = url_association_that_user_added.url_notes

        number_of_urls_in_utub = len(
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == id_of_utub_that_is_creator_of
            ).all()
        )
        number_of_urls_in_db = len(URLS.query.all())

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_DESCRIPTION: url_description_to_add,
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=id_of_utub_that_is_creator_of),
        data=add_url_form,
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.URL_IN_UTUB
    assert int(add_url_json_response[STD_JSON.ERROR_CODE]) == 3

    with app.app_context():
        # Ensure same number of URLs in UTub as before
        utub_to_check = Utub.query.get(id_of_utub_that_is_creator_of)
        assert len(utub_to_check.utub_urls) == number_of_urls_in_utub

        # Ensure Url-UTub-UAser association still contains only the one associatisn
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
                    Utub_Urls.user_id == current_user.id,
                    Utub_Urls.url_id == url_id,
                ).all()
            )
            == 1
        )

        # Ensure same number of URLs as before
        assert len(URLS.query.all()) == number_of_urls_in_db

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_add_duplicate_url_to_utub_as_creator_of_utub_not_url_adder(
    add_all_urls_and_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        currently in the database, with all UTubs containing all URLs
    WHEN the user tries to add a URL to a UTub that someone else added, as the creator of the UTub
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response
        is sent by the server, and that no new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.URL_IN_UTUB,
        STD_JSON.ERROR_CODE: 3
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub
        utub_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        id_of_utub_that_is_creator_of = utub_creator_of.id

        # Find the first URL in this UTub that this user added
        url_association_that_user_did_not_add = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
            Utub_Urls.user_id != current_user.id,
        ).first()

        url_that_user_did_not_add = url_association_that_user_did_not_add.url_in_utub
        url_id = url_that_user_did_not_add.id
        url_string_to_add = url_that_user_did_not_add.url_string
        url_description_to_add = url_association_that_user_did_not_add.url_notes

        number_of_urls_in_utub = len(
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == id_of_utub_that_is_creator_of
            ).all()
        )
        number_of_urls_in_db = len(URLS.query.all())

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_DESCRIPTION: url_description_to_add,
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=id_of_utub_that_is_creator_of),
        data=add_url_form,
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.URL_IN_UTUB
    assert int(add_url_json_response[STD_JSON.ERROR_CODE]) == 3

    with app.app_context():
        # Ensure same number of URLs in UTub as before
        utub_to_check = Utub.query.get(id_of_utub_that_is_creator_of)
        assert len(utub_to_check.utub_urls) == number_of_urls_in_utub

        # Ensure Url-UTub-UAser association still contains only the one associatisn
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
                    Utub_Urls.url_id == url_id,
                ).all()
            )
            == 1
        )

        # Ensure same number of URLs as before
        assert len(URLS.query.all()) == number_of_urls_in_db

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_add_duplicate_url_to_utub_as_member_of_utub_not_url_adder(
    add_all_urls_and_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        currently in the database, with all UTubs containing all URLs
    WHEN the user tries to add a URL to a UTub that someone else added, as the member of the UTub
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response
        is sent by the server, and that no new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.URL_IN_UTUB,
        STD_JSON.ERROR_CODE: 3
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub
        utub_member_of = Utub.query.filter(Utub.utub_creator != current_user.id).first()
        id_of_utub_that_is_member_of = utub_member_of.id

        # Ensure user is member of this UTub
        assert current_user in [user.to_user for user in utub_member_of.members]

        # Find the first URL in this UTub that this user added
        url_association_that_user_did_not_add = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_member_of,
            Utub_Urls.user_id != current_user.id,
        ).first()

        url_that_user_did_not_add = url_association_that_user_did_not_add.url_in_utub
        url_id = url_that_user_did_not_add.id
        url_string_to_add = url_that_user_did_not_add.url_string
        url_description_to_add = url_association_that_user_did_not_add.url_notes

        number_of_urls_in_utub = len(
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == id_of_utub_that_is_member_of
            ).all()
        )
        number_of_urls_in_db = len(URLS.query.all())

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_DESCRIPTION: url_description_to_add,
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=id_of_utub_that_is_member_of), data=add_url_form
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.URL_IN_UTUB
    assert int(add_url_json_response[STD_JSON.ERROR_CODE]) == 3

    with app.app_context():
        # Ensure same number of URLs in UTub as before
        utub_to_check = Utub.query.get(id_of_utub_that_is_member_of)
        assert len(utub_to_check.utub_urls) == number_of_urls_in_utub

        # Ensure Url-UTub-UAser association still contains only the one associatisn
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_that_is_member_of,
                    Utub_Urls.url_id == url_id,
                ).all()
            )
            == 1
        )

        # Ensure same number of URLs as before
        assert len(URLS.query.all()) == number_of_urls_in_db

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_add_url_missing_url(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a URL with an empty 'url_string' field in the form
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 404 HTTP status code, and that the proper JSON response
        is sent by the server

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: "Unable to add this URL, please check inputs",
        STD_JSON.ERROR_CODE: 4,
        "Errors": {
            URL_FORM.URL_STRING: ["This field is required."]
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        assert current_user in [user.to_user for user in current_utub_member_of.members]

        # Ensure no URLs in this UTub
        assert len(current_utub_member_of.utub_urls) == 0
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == current_utub_member_of.id
                ).all()
            )
            == 0
        )

        # Grab a URL to add
        url_to_add = URLS.query.first()
        url_string_to_add = url_to_add.url_string
        url_description_to_add = f"This is {url_string_to_add}"
        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: "",
        URL_FORM.URL_DESCRIPTION: url_description_to_add,
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 404

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_ADD_URL_FORM
    assert int(add_url_json_response[STD_JSON.ERROR_CODE]) == 4
    assert (
        add_url_json_response[STD_JSON.ERRORS][URL_FORM.URL_STRING]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        assert (
            len(Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_to_add_to).all())
            == 0
        )

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_add_url_missing_url_description(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a URL with an empty 'url_description' field in the form
    THEN ensure that the server responds with a 404 HTTP status code, and that the proper JSON response
        is sent by the server

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL_FORM,
        STD_JSON.ERROR_CODE: 4,
        STD_JSON.ERRORS: {
            URL_FORM.URL_DESCRIPTION: ["This field is required."]
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        assert current_user in [user.to_user for user in current_utub_member_of.members]

        # Ensure no URLs in this UTub
        assert len(current_utub_member_of.utub_urls) == 0
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == current_utub_member_of.id
                ).all()
            )
            == 0
        )

        # Grab a URL to add
        url_to_add = URLS.query.first()
        url_string_to_add = url_to_add.url_string
        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_DESCRIPTION: "",
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 404

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_ADD_URL_FORM
    assert int(add_url_json_response[STD_JSON.ERROR_CODE]) == 4
    assert (
        add_url_json_response[STD_JSON.ERRORS][URL_FORM.URL_DESCRIPTION]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        assert (
            len(Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_to_add_to).all())
            == 0
        )

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_add_url_missing_csrf_token(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a URL with an empty 'url_description' field in the form
        - By POST to "/url/add/<url_id: int>" where "url_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 404 HTTP status code, and that the proper JSON response
        is sent by the server

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL_FORM,
        STD_JSON.ERROR_CODE: 4,
        STD_JSON.ERRORS: {
            URL_FORM.URL_DESCRIPTION: ["This field is required."]
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        assert current_user in [user.to_user for user in current_utub_member_of.members]

        # Ensure no URLs in this UTub
        assert len(current_utub_member_of.utub_urls) == 0
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == current_utub_member_of.id
                ).all()
            )
            == 0
        )

        # Grab a URL to add
        url_to_add = URLS.query.first()
        url_string_to_add = url_to_add.url_string
        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_DESCRIPTION: "",
    }

    add_url_response = client.post(
        url_for("urls.add_url", utub_id=utub_id_to_add_to), data=add_url_form
    )

    # Assert invalid response code
    assert add_url_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in add_url_response.data

    with app.app_context():
        assert (
            len(Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_to_add_to).all())
            == 0
        )

        assert len(Utub_Urls.query.all()) == initial_utub_urls
