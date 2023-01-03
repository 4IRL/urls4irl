import pytest
from flask_login import current_user

from urls4irl import db
from urls4irl.models import URLS, Utub_Urls, Utub, Utub_Users, User
from models_for_test import valid_url_strings

def test_remove_url_as_utub_creator_no_tags(add_one_url_to_each_utub_no_tags, login_first_user_without_register):
    """
    GIVEN a logged-in creator of a UTub who has added a valid URL to their UTub, with no tags
    WHEN the creator wishes to remove the URL from the UTub by making a POST to "/url/remove/<int: utub_id>/<int: url_id>"
    THEN the server responds with a 200 HTTP status code, the UTub-User-URL association is removed from the database,
        and the server sends back the correct JSON reponse

    Proper JSON response is as follows:
    {
        "Status" : "Success",
        "Message": "URL removed from this UTub",
        "URL" : Serialized information of the URL that was removed, as follows:
        {
            "id": Integer representing ID of the URL,
            "url": String representing the URL itself,
            "tags": Array containing the tag ID's associated with this URL in this UTub, that were removed
                Empty array if not tags were associated with the URL in this UTub
        
        }
        "UTub_ID" : Integer representing the UTub ID where the URL was removed from,
        "UTub_name" : String representing the name of the UTub removed"
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    # Get UTub of current user
    with app.app_context():
        current_user_utub = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure current user is the creator
        assert current_user_utub.created_by == current_user

        # Assert there is a URL in the UTub
        assert len(current_user_utub.utub_urls) == 1

        url_utub_user_association = current_user_utub.utub_urls[0]
        url_to_remove_serialized = url_utub_user_association.url_in_utub.serialized_url
        url_id_to_remove = url_utub_user_association.url_id

        # Assert the single UTUB-URL-USER association exists
        assert len(Utub_Urls.query.filter(Utub_Urls.url_id == url_id_to_remove, 
                                        Utub_Urls.user_id == current_user.id,
                                        Utub_Urls.utub_id == current_user_utub.id).all()) == 1

    # Remove URL from UTub as UTub creator
    remove_url_response = client.post(f"/url/remove/{current_user_utub.id}/{url_id_to_remove}", data={"csrf_token": csrf_token_string})

    # Ensure 200 HTTP status code response
    assert remove_url_response.status_code == 200

    # Ensure JSON response is correct
    remove_url_response_json = remove_url_response.json
    assert remove_url_response_json["Status"] == "Success"
    assert remove_url_response_json["Message"] == "URL removed from this UTub"
    assert remove_url_response_json["URL"] == url_to_remove_serialized
    assert int(remove_url_response_json["UTub_ID"]) == current_user_utub.id
    assert remove_url_response_json["UTub_name"] == current_user_utub.name

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert URLS.query.get(url_id_to_remove) is not None
        assert URLS.query.get(url_id_to_remove).serialized_url == url_to_remove_serialized

        # Assert the URL-USER-UTUB association is deleted
        assert len(Utub_Urls.query.filter(Utub_Urls.url_id == url_id_to_remove, 
                                        Utub_Urls.user_id == current_user.id,
                                        Utub_Urls.utub_id == current_user_utub.id).all()) == 0

        # Ensure UTub has no URLs left
        current_user_utub = Utub.query.get(current_user_utub.id)
        assert len(current_user_utub.utub_urls) == 0

def test_remove_url_as_utub_member_no_tags(add_one_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register):
    """
    GIVEN a logged-in member of a UTub who has added a valid URL to their UTub, with no tags
    WHEN the creator wishes to remove the URL from the UTub by making a POST to "/url/remove/<int: utub_id>/<int: url_id>"
    THEN the server responds with a 200 HTTP status code, the UTub-User-URL association is removed from the database,
        and the server sends back the correct JSON reponse

    Proper JSON response is as follows:
    {
        "Status" : "Success",
        "Message": "URL removed from this UTub",
        "URL" : Serialized information of the URL that was removed, as follows:
        {
            "id": Integer representing ID of the URL,
            "url": String representing the URL itself,
            "tags": Array containing the tag ID's associated with this URL in this UTub, that were removed
                Empty array if not tags were associated with the URL in this UTub
        
        }
        "UTub_ID" : Integer representing the UTub ID where the URL was removed from,
        "UTub_name" : String representing the name of the UTub removed"
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        # Get first UTub where current logged in user is not the creator
        current_user_utub = Utub.query.filter(Utub.utub_creator != current_user.id).first()

        # Ensure current user is not the creator
        assert current_user_utub.created_by != current_user

        # Assert there is a URL in the UTub
        assert len(current_user_utub.utub_urls) == 1
        current_url_in_utub = current_user_utub.utub_urls[0]

        # Assert current user did not add this URL
        assert len(Utub_Urls.query.filter(Utub_Urls.utub_id == current_user_utub.id, 
                                        Utub_Urls.url_id == current_url_in_utub.url_id,
                                        Utub_Urls.user_id == current_user.id).all()) == 0

        # Find a URL that the current user did not add
        missing_url_association = Utub_Urls.query.filter(Utub_Urls.user_id != current_user.id,
                                                Utub_Urls.utub_id != current_user_utub.id).first()

        missing_url = missing_url_association.url_in_utub
        missing_url_serialized = missing_url.serialized_url

        # Have current user add the missing URL to the current UTub
        new_utub_url_user_association = Utub_Urls()
        new_utub_url_user_association.url_id = missing_url.id
        new_utub_url_user_association.url_in_utub = missing_url
        new_utub_url_user_association.utub_id = current_user_utub.id
        new_utub_url_user_association.utub = current_user_utub
        new_utub_url_user_association.user_id = current_user.id
        new_utub_url_user_association.user_that_added_url = current_user

        db.session.add(new_utub_url_user_association)
        db.session.commit()

        # Assert this URL was added
        current_user_utub = Utub.query.get(current_user_utub.id)
        assert len(current_user_utub.utub_urls) == 2

        assert len(Utub_Urls.query.filter(Utub_Urls.url_id == missing_url.id,
                                        Utub_Urls.utub_id == current_user_utub.id,
                                        Utub_Urls.user_id == current_user.id).all()) == 1

    # Remove URL from UTub as UTub member
    remove_url_response = client.post(f"/url/remove/{current_user_utub.id}/{missing_url.id}", data={"csrf_token": csrf_token_string})

    # Ensure 200 HTTP status code response
    assert remove_url_response.status_code == 200

    # Ensure JSON response is correct
    remove_url_response_json = remove_url_response.json
    assert remove_url_response_json["Status"] == "Success"
    assert remove_url_response_json["Message"] == "URL removed from this UTub"
    assert remove_url_response_json["URL"] == missing_url_serialized
    assert int(remove_url_response_json["UTub_ID"]) == current_user_utub.id
    assert remove_url_response_json["UTub_name"] == current_user_utub.name

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert URLS.query.get(missing_url.id) is not None
        assert URLS.query.get(missing_url.id).serialized_url == missing_url_serialized

        # Assert the URL-USER-UTUB association is deleted
        assert len(Utub_Urls.query.filter(Utub_Urls.url_id == missing_url.id, 
                                        Utub_Urls.user_id == current_user.id,
                                        Utub_Urls.utub_id == current_user_utub.id).all()) == 0

        # Ensure UTub has one left
        current_user_utub = Utub.query.get(current_user_utub.id)
        assert len(current_user_utub.utub_urls) == 1



#TODO: Remove URL as creator of UTub, with tags
#TODO: Remove URL as user who added URL to UTub, with tags
#TODO: Remove URL as not member of UTub
#TODO: Remove nonexistent URL as creator of UTub
#TODO: Remove nonexistent URL as member of UTub