import pytest
from flask_login import current_user

from urls4irl import db
from urls4irl.models import Utub, URLS, Utub_Urls, Utub_Users, Tags, Url_Tags
from models_for_test import all_tag_strings

def test_update_valid_utub_description_as_creator(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with
    WHEN the creator attempts to modify the UTub description to something else

    Args:
        add_all_urls_and_users_to_each_utub_with_all_tags (_type_): _description_
        login_first_user_without_register (_type_): _description_
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    UPDATE_TEXT = "This is my new UTub description. 123456"
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_description = utub_of_user.utub_description
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

# TODO - Test updating to the same description
# TODO - Test member trying to update the UTub's description
# TODO - Test creator of a UTub trying to edit someone else's UTub description
# TODO - Test adding too long of a UTub description