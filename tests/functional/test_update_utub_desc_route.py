import pytest
from flask_login import current_user

from urls4irl.models import Utub, Utub_Urls, Utub_Users, Url_Tags

def test_update_valid_utub_description_as_creator(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with
    WHEN the creator attempts to modify the UTub description to a new description, via a POST to
        "/utub/edit_description/<utub_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "utub_description": New utub description to add
    THEN verify that the new UTub description is stored in the database, the utub-user associations are
        consistent across the change, all other UTub descriptions are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status": "Success",
        "UTub_ID": Integer representing the UTub ID for the changed description
        "UTub_name": String representing the name of the UTub whose description was changed
        "UTub_description": String representing the current UTub's new description
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    UPDATE_TEXT = "This is my new UTub description. 123456"
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_description = utub_of_user.utub_description

        # Ensure the new description is not the current description
        assert UPDATE_TEXT != current_utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        "csrf_token": csrf_token_string,
        "utub_description": UPDATE_TEXT
    }

    edit_utub_desc_response = client.post(f"/utub/edit_description/{current_utub_id}", data=utub_desc_form)

    # Ensure valid reponse
    assert edit_utub_desc_response.status_code == 200

    # Ensure JSON response is correct
    edit_utub_desc_json_response = edit_utub_desc_response.json

    assert edit_utub_desc_json_response["Status"] == "Success"
    assert int(edit_utub_desc_json_response["UTub_ID"]) == current_utub_id
    assert edit_utub_desc_json_response["UTub_description"] == UPDATE_TEXT
    assert edit_utub_desc_json_response["UTub_name"] == current_utub_name
    
    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == UPDATE_TEXT

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            if utub_name == current_utub_name:
                assert final_utub_names_and_descriptions[utub_name] != all_utub_names_and_descriptions[utub_name]
            else:
                assert final_utub_names_and_descriptions[utub_name] == all_utub_names_and_descriptions[utub_name]

def test_update_valid_empty_utub_description_as_creator(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with
    WHEN the creator attempts to modify the UTub description to an empty description, via a POST to
        "/utub/edit_description/<utub_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "utub_description": New utub description to add
    THEN verify that the new UTub description is stored in the database, the utub-user associations are
        consistent across the change, all other UTub descriptions are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status": "Success",
        "UTub_ID": Integer representing the UTub ID for the changed description
        "UTub_name": String representing the name of the UTub whose description was changed
        "UTub_description": String representing the current UTub's new description
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    UPDATE_TEXT = ""
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_description = utub_of_user.utub_description

        # Ensure the new description is not the current description
        assert UPDATE_TEXT != current_utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        "csrf_token": csrf_token_string,
        "utub_description": UPDATE_TEXT
    }

    edit_utub_desc_response = client.post(f"/utub/edit_description/{current_utub_id}", data=utub_desc_form)

    # Ensure valid reponse
    assert edit_utub_desc_response.status_code == 200

    # Ensure JSON response is correct
    edit_utub_desc_json_response = edit_utub_desc_response.json

    assert edit_utub_desc_json_response["Status"] == "Success"
    assert int(edit_utub_desc_json_response["UTub_ID"]) == current_utub_id
    assert edit_utub_desc_json_response["UTub_description"] == UPDATE_TEXT
    assert edit_utub_desc_json_response["UTub_name"] == current_utub_name
    
    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == UPDATE_TEXT

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            if utub_name == current_utub_name:
                assert final_utub_names_and_descriptions[utub_name] != all_utub_names_and_descriptions[utub_name]
            else:
                assert final_utub_names_and_descriptions[utub_name] == all_utub_names_and_descriptions[utub_name]

def test_update_only_spaces_utub_description_as_creator(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with
    WHEN the creator attempts to modify the UTub description to a description containing only spaces, via a POST to
        "/utub/edit_description/<utub_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "utub_description": New utub description to add
    THEN verify that the new UTub description is stored in the database as an empty string, the utub-user 
        associations are consistent across the change, all other UTub descriptions are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status": "Success",
        "UTub_ID": Integer representing the UTub ID for the changed description
        "UTub_name": String representing the name of the UTub whose description was changed
        "UTub_description": String representing the current UTub's new description
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    UPDATE_TEXT = "   "
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_description = utub_of_user.utub_description

        # Ensure the new description is not the current description
        assert UPDATE_TEXT != current_utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        "csrf_token": csrf_token_string,
        "utub_description": UPDATE_TEXT
    }

    edit_utub_desc_response = client.post(f"/utub/edit_description/{current_utub_id}", data=utub_desc_form)

    # Ensure valid reponse
    assert edit_utub_desc_response.status_code == 200

    # Ensure JSON response is correct
    edit_utub_desc_json_response = edit_utub_desc_response.json

    assert edit_utub_desc_json_response["Status"] == "Success"
    assert int(edit_utub_desc_json_response["UTub_ID"]) == current_utub_id
    assert edit_utub_desc_json_response["UTub_description"] == ""
    assert edit_utub_desc_json_response["UTub_name"] == current_utub_name
    
    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == ""

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            if utub_name == current_utub_name:
                assert final_utub_names_and_descriptions[utub_name] != all_utub_names_and_descriptions[utub_name]
            else:
                assert final_utub_names_and_descriptions[utub_name] == all_utub_names_and_descriptions[utub_name]

def test_update_utub_description_with_same_description_as_creator(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with
    WHEN the creator attempts to modify the UTub description to the same description, via a POST to
        "/utub/edit_description/<utub_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "utub_description": New utub description to add
    THEN verify that the new UTub description is stored in the database, the UTub-user associations are
        consistent across the change, all other UTub descriptions are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status": "Success",
        "UTub_ID": Integer representing the UTub ID for the changed description
        "UTub_name": String representing the name of the UTub whose description was changed
        "UTub_description": String representing the current UTub's previous description
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    # Grab this creator's UTub
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_description = utub_of_user.utub_description
        UPDATE_TEXT = current_utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        "csrf_token": csrf_token_string,
        "utub_description": UPDATE_TEXT
    }

    edit_utub_desc_response = client.post(f"/utub/edit_description/{current_utub_id}", data=utub_desc_form)

    # Ensure valid reponse
    assert edit_utub_desc_response.status_code == 200

    # Ensure JSON response is correct
    edit_utub_desc_json_response = edit_utub_desc_response.json

    assert edit_utub_desc_json_response["Status"] == "Success"
    assert int(edit_utub_desc_json_response["UTub_ID"]) == current_utub_id
    assert edit_utub_desc_json_response["UTub_description"] == UPDATE_TEXT
    assert edit_utub_desc_json_response["UTub_name"] == current_utub_name
    
    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == UPDATE_TEXT

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert final_utub_names_and_descriptions[utub_name] == all_utub_names_and_descriptions[utub_name]

def test_update_utub_description_as_member(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid member of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions
    WHEN the member attempts to modify the UTub description to a new description, via a POST to
        "/utub/edit_description/<utub_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "utub_description": New utub description to add
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent, 
        the server sends back a 403 HTTP status code, and the server sends back the appropriate JSON response
        indicating the member is not authorized to edit the description

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "You do not have permission to edit this UTub's description",
        "Error_code": 1,
        "UTub_description": String representing the current UTub's description
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    UPDATE_TEXT = "This is my new UTub description. 123456"
    # Grab this member's UTub
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator != current_user.id).first()

        # Ensure this user is not the creator
        assert utub_of_user.created_by != current_user

        # Ensure this user is in the UTub
        assert current_user in [user.to_user for user in utub_of_user.members]

        current_utub_description = utub_of_user.utub_description

        # Ensure the new description is not the current description
        assert UPDATE_TEXT != current_utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        "csrf_token": csrf_token_string,
        "utub_description": UPDATE_TEXT
    }

    edit_utub_desc_response = client.post(f"/utub/edit_description/{current_utub_id}", data=utub_desc_form)

    # Ensure valid reponse
    assert edit_utub_desc_response.status_code == 403

    # Ensure JSON response is correct
    edit_utub_desc_json_response = edit_utub_desc_response.json

    assert edit_utub_desc_json_response["Status"] == "Failure"
    assert edit_utub_desc_json_response["UTub_description"] != UPDATE_TEXT
    assert edit_utub_desc_json_response["UTub_description"] == current_utub_description
    assert int(edit_utub_desc_json_response["Error_code"]) == 1
    assert edit_utub_desc_json_response["Message"] == "You do not have permission to edit this UTub's description"
    
    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description
        assert final_check_utub_of_user.utub_description != UPDATE_TEXT

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert final_utub_names_and_descriptions[utub_name] == all_utub_names_and_descriptions[utub_name]

def test_update_utub_description_as_creator_of_other_utub(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid member of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions, and this member is creator of another UTub
    WHEN the member attempts to modify the UTub description to a new description, via a POST to
        "/utub/edit_description/<utub_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "utub_description": New utub description to add
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent, 
        the server sends back a 403 HTTP status code, and the server sends back the appropriate JSON response
        indicating the member is not authorized to edit the description

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "You do not have permission to edit this UTub's description",
        "Error_code": 1,
        "UTub_description": String representing the current UTub's description
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    UPDATE_TEXT = "This is my new UTub description. 123456"
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator != current_user.id).first()

        # Ensure this user is the creator of another UTub
        utub_user_is_creator_of = Utub.query.filter(Utub.utub_creator == current_user.id).first()
        assert utub_user_is_creator_of is not None

        # Ensure this user is not the creator
        assert utub_of_user.created_by != current_user

        # Ensure this user is in the UTub
        assert current_user in [user.to_user for user in utub_of_user.members]

        current_utub_description = utub_of_user.utub_description

        # Ensure the new description is not the current description
        assert UPDATE_TEXT != current_utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        "csrf_token": csrf_token_string,
        "utub_description": UPDATE_TEXT
    }

    edit_utub_desc_response = client.post(f"/utub/edit_description/{current_utub_id}", data=utub_desc_form)

    # Ensure valid reponse
    assert edit_utub_desc_response.status_code == 403

    # Ensure JSON response is correct
    edit_utub_desc_json_response = edit_utub_desc_response.json

    assert edit_utub_desc_json_response["Status"] == "Failure"
    assert edit_utub_desc_json_response["UTub_description"] != UPDATE_TEXT
    assert edit_utub_desc_json_response["UTub_description"] == current_utub_description
    assert int(edit_utub_desc_json_response["Error_code"]) == 1
    assert edit_utub_desc_json_response["Message"] == "You do not have permission to edit this UTub's description"
    
    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description
        assert final_check_utub_of_user.utub_description != UPDATE_TEXT

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert final_utub_names_and_descriptions[utub_name] == all_utub_names_and_descriptions[utub_name]

def test_update_utub_description_of_invalid_utub(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid member of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions, and this member is creator of another UTub
    WHEN the member attempts to modify the UTub description of a nonexistent UTub, via a POST to
        "/utub/edit_description/<utub_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "utub_description": New utub description to add
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent, 
        the server sends back a 404 HTTP status code
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    UPDATE_TEXT = "This is my new UTub description. 123456"
    # Grab this creator's UTub
    with app.app_context():
        invalid_utub_id = 0
        valid_utub_ids = [utub.id for utub in Utub.query.all()]
        while invalid_utub_id in valid_utub_ids:
            invalid_utub_id += 1
        
        # Ensure no UTub exists with this ID
        assert Utub.query.get(invalid_utub_id) is None
        # Ensure this user is the creator of another UTub
        utub_user_is_creator_of = Utub.query.filter(Utub.utub_creator == current_user.id).first()
        assert utub_user_is_creator_of is not None

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        "csrf_token": csrf_token_string,
        "utub_description": UPDATE_TEXT
    }

    edit_utub_desc_response = client.post(f"/utub/edit_description/{invalid_utub_id}", data=utub_desc_form)

    # Ensure valid reponse
    assert edit_utub_desc_response.status_code == 404

    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert final_utub_names_and_descriptions[utub_name] == all_utub_names_and_descriptions[utub_name]

def test_update_utub_description_too_long(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions
    WHEN the creator attempts to modify the UTub description to a new description that is longer than 
        500 characters, via a POST to:
        "/utub/edit_description/<utub_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "utub_description": New utub description to add
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent, 
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response
        indicating the UTub description is too long

    Proper JSON is as follows:
    {
        "Status": "Failure",
        "Message": "UTub description is too long",
        "Error_code": 3,
        "Errors": Objects representing the incorrect field, and an array of errors associated with that field.
            For example, with the missing or empty utub_description field:
            {
                "utub_description": ['This field is required.']
            }
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    MAX_UTUB_DESC = 500

    UPDATE_TEXT = "".join(["a" for _ in range(MAX_UTUB_DESC + 1)])
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_description = utub_of_user.utub_description

        # Ensure the new description is not the current description
        assert UPDATE_TEXT != current_utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        "csrf_token": csrf_token_string,
        "utub_description": UPDATE_TEXT
    }

    edit_utub_desc_response = client.post(f"/utub/edit_description/{current_utub_id}", data=utub_desc_form)

    # Ensure valid reponse
    assert edit_utub_desc_response.status_code == 404

    # Ensure JSON response is correct
    edit_utub_desc_json_response = edit_utub_desc_response.json

    assert edit_utub_desc_json_response["Status"] == "Failure"
    assert edit_utub_desc_json_response["Message"] == "UTub description is too long"
    assert int(edit_utub_desc_json_response["Error_code"]) == 3
    assert edit_utub_desc_json_response["Errors"]["utub_description"] == ["Field cannot be longer than 500 characters."]
    
    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description
        assert final_check_utub_of_user.utub_description != UPDATE_TEXT

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert final_utub_names_and_descriptions[utub_name] == all_utub_names_and_descriptions[utub_name]

def test_update_utub_description_missing_description_field(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions
    WHEN the creator attempts to modify the UTub description, via a POST to:
        "/utub/edit_description/<utub_id: int>" with invalid form data that doens't contain
            the "utub_description" field, following this format:
            "csrf_token": String containing CSRF token for validation
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent, 
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response
        indicating the form is invalid

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "Invalid form",
        "Error_code": 2,
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    # Grab this creator's UTub
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_description = utub_of_user.utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        "csrf_token": csrf_token_string,
    }

    edit_utub_desc_response = client.post(f"/utub/edit_description/{current_utub_id}", data=utub_desc_form)

    # Ensure valid reponse
    assert edit_utub_desc_response.status_code == 404

    # Ensure JSON response is correct
    edit_utub_desc_json_response = edit_utub_desc_response.json

    assert edit_utub_desc_json_response["Status"] == "Failure"
    assert edit_utub_desc_json_response["Message"] == "Invalid form"
    assert int(edit_utub_desc_json_response["Error_code"]) == 2
    
    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert final_utub_names_and_descriptions[utub_name] == all_utub_names_and_descriptions[utub_name]

def test_update_utub_description_missing_csrf_token(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions
    WHEN the creator attempts to modify the UTub description, via a POST to:
        "/utub/edit_description/<utub_id: int>" with invalid form data that doens't contain
            the "csrf_token" field, following this format:
            "utub_description": New utub description to add
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent, 
        the server sends back a 400 HTTP status code, and the server sends back the appropriate HTML element
        indicating the CSRF token is missing
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    # Grab this creator's UTub
    UPDATE_TEXT = "This is my new UTub description. 123456"
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_description = utub_of_user.utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        "utub_description": UPDATE_TEXT,
    }

    edit_utub_desc_response = client.post(f"/utub/edit_description/{current_utub_id}", data=utub_desc_form)

    # Ensure valid reponse
    assert edit_utub_desc_response.status_code == 400
    assert b'<p>The CSRF token is missing.</p>' in edit_utub_desc_response.data
    
    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert final_utub_names_and_descriptions[utub_name] == all_utub_names_and_descriptions[utub_name]
