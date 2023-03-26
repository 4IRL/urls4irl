import pytest
from flask_login import current_user

from urls4irl.models import Utub, Utub_Urls, Utub_Users, Url_Tags, URLS
from urls4irl.url_validation import check_request_head

def test_update_valid_url_with_another_fresh_valid_url_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL not already in the database, with no description change, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the new URL is stored in the database with same description, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Success",
        "Message": "URL and/or URL Description modified",
        "URL" : Object representing a Utub_Urls, with the following fields 
        {
            "url_id": ID of URL that was modified to,
            "url_string": The URL that was newly modified to,
            "url_tags": An array of tag ID's associated with this URL
            "added_by": Id of the user who added this, should be the user modifying it
            "notes": String representing the URL description in this UTub
        }
        "UTub_ID" : UTub ID where this URL exists,
        "UTub_name" : Name of UTub where this
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_FRESH_URL = "github.com"
    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = check_request_head(NEW_FRESH_URL)
        assert URLS.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL in this UTub
        url_in_this_utub = Utub_Urls.query.filter_by(utub_id=utub_creator_of.id).first()
        current_desc = url_in_this_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_in_this_utub.url_id).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": validated_new_fresh_url,
        "url_description": current_desc
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_creator_of.id}/{url_in_this_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Success"
    assert json_response["Message"] == "URL and/or URL Description modified"
    assert int(json_response["URL"]["added_by"]) == current_user.id
    assert json_response["URL"]["notes"] == current_desc
    assert int(json_response["URL"]["url_id"]) != url_in_this_utub.url_id
    assert json_response["URL"]["url_string"] == validated_new_fresh_url
    assert json_response["URL"]["url_tags"] == associated_tag_ids
    assert int(json_response["UTub_ID"]) == utub_creator_of.id
    assert json_response["UTub_name"] == utub_creator_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all()) == 0

        # Assert newest entity exist
        new_url_id = int(json_response["URL"]["url_id"]) 
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=new_url_id, url_notes=current_desc).all()) == 1 

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=new_url_id).all()) == len(associated_tags)

def test_update_valid_url_with_another_fresh_valid_url_as_url_member(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid member of a UTub that has members, URLs added by each member, and tags associated with each URL
    WHEN the member attempts to modify the URL with a URL not already in the database, with no description change, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the new URL is stored in the database with same description, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Success",
        "Message": "URL and/or URL Description modified",
        "URL" : Object representing a Utub_Urls, with the following fields 
        {
            "url_id": ID of URL that was modified to,
            "url_string": The URL that was newly modified to,
            "url_tags": An array of tag ID's associated with this URL
            "added_by": Id of the user who added this, should be the user modifying it
            "notes": String representing the URL description in this UTub
        }
        "UTub_ID" : UTub ID where this URL exists,
        "UTub_name" : Name of UTub where this
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_FRESH_URL = "github.com"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of = Utub.query.filter(Utub.utub_creator != current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_member_of.utub_creator != current_user.id

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = check_request_head(NEW_FRESH_URL)
        assert URLS.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL in this UTub
        url_in_this_utub = Utub_Urls.query.filter_by(utub_id=utub_member_of.id, user_id=current_user.id).first()
        current_desc = url_in_this_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": validated_new_fresh_url,
        "url_description": current_desc
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_member_of.id}/{url_in_this_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Success"
    assert json_response["Message"] == "URL and/or URL Description modified"
    assert int(json_response["URL"]["added_by"]) == current_user.id
    assert json_response["URL"]["notes"] == current_desc
    assert int(json_response["URL"]["url_id"]) != url_in_this_utub.url_id
    assert json_response["URL"]["url_string"] == validated_new_fresh_url
    assert json_response["URL"]["url_tags"] == associated_tag_ids
    assert int(json_response["UTub_ID"]) == utub_member_of.id
    assert json_response["UTub_name"] == utub_member_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all()) == 0

        # Assert newest entity exist
        new_url_id = int(json_response["URL"]["url_id"]) 
        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=new_url_id, url_notes=current_desc).all()) == 1 

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=new_url_id).all()) == len(associated_tags)

def test_update_url_description_with_fresh_valid_url_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL description and change the URL to one not already in the database, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of new description
    THEN verify that the new URL and description is stored in the database, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Success",
        "Message": "URL and/or URL Description modified",
        "URL" : Object representing a Utub_Urls, with the following fields 
        {
            "url_id": ID of URL that was modified to,
            "url_string": The URL that was newly modified to,
            "url_tags": An array of tag ID's associated with this URL
            "added_by": Id of the user who added this, should be the user modifying it
            "notes": String representing the URL description in this UTub
        }
        "UTub_ID" : UTub ID where this URL exists,
        "UTub_name" : Name of UTub where this
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_FRESH_URL = "github.com"
    NEW_DESCRIPTION = "This is my newest github.com!"
    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = check_request_head(NEW_FRESH_URL)
        assert URLS.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL in this UTub
        url_in_this_utub = Utub_Urls.query.filter_by(utub_id=utub_creator_of.id).first()
        current_desc = url_in_this_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_in_this_utub.url_id).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": validated_new_fresh_url,
        "url_description": NEW_DESCRIPTION
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_creator_of.id}/{url_in_this_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Success"
    assert json_response["Message"] == "URL and/or URL Description modified"
    assert int(json_response["URL"]["added_by"]) == current_user.id
    assert json_response["URL"]["notes"] == NEW_DESCRIPTION
    assert int(json_response["URL"]["url_id"]) != url_in_this_utub.url_id
    assert json_response["URL"]["url_string"] == validated_new_fresh_url
    assert json_response["URL"]["url_tags"] == associated_tag_ids
    assert int(json_response["UTub_ID"]) == utub_creator_of.id
    assert json_response["UTub_name"] == utub_creator_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all()) == 0

        # Assert newest entity exist
        new_url_id = int(json_response["URL"]["url_id"]) 
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=new_url_id, url_notes=NEW_DESCRIPTION).all()) == 1 

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=new_url_id).all()) == len(associated_tags)

def test_update_url_description_with_fresh_valid_url_as_url_adder(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid member of a UTub that has members, URL added by the member, and tags associated with each URL
    WHEN the member attempts to modify the URL description and change the URL to one not already in the database, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of new description
    THEN verify that the new URL and description is stored in the database, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Success",
        "Message": "URL and/or URL Description modified",
        "URL" : Object representing a Utub_Urls, with the following fields 
        {
            "url_id": ID of URL that was modified to,
            "url_string": The URL that was newly modified to,
            "url_tags": An array of tag ID's associated with this URL
            "added_by": Id of the user who added this, should be the user modifying it
            "notes": String representing the URL description in this UTub
        }
        "UTub_ID" : UTub ID where this URL exists,
        "UTub_name" : Name of UTub where this
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_FRESH_URL = "github.com"
    NEW_DESCRIPTION = "This is my newest github.com!"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of = Utub.query.filter(Utub.utub_creator != current_user.id).first()

        # Verify logged in user is not creator of this UTub
        assert utub_member_of.utub_creator != current_user.id

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = check_request_head(NEW_FRESH_URL)
        assert URLS.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL in this UTub
        url_in_this_utub = Utub_Urls.query.filter_by(utub_id=utub_member_of.id, user_id=current_user.id).first()
        current_desc = url_in_this_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": validated_new_fresh_url,
        "url_description": NEW_DESCRIPTION
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_member_of.id}/{url_in_this_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Success"
    assert json_response["Message"] == "URL and/or URL Description modified"
    assert int(json_response["URL"]["added_by"]) == current_user.id
    assert json_response["URL"]["notes"] == NEW_DESCRIPTION
    assert int(json_response["URL"]["url_id"]) != url_in_this_utub.url_id
    assert json_response["URL"]["url_string"] == validated_new_fresh_url
    assert json_response["URL"]["url_tags"] == associated_tag_ids
    assert int(json_response["UTub_ID"]) == utub_member_of.id
    assert json_response["UTub_name"] == utub_member_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id, url_notes=NEW_DESCRIPTION).all()) == 0

        # Assert newest entity exist
        new_url_id = int(json_response["URL"]["url_id"]) 
        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=new_url_id, url_notes=NEW_DESCRIPTION).all()) == 1 

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=new_url_id).all()) == len(associated_tags)

def test_update_valid_url_with_previously_added_url_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL already in the database, with no description change, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Success",
        "Message": "URL and/or URL Description modified",
        "URL" : Object representing a Utub_Urls, with the following fields 
        {
            "url_id": ID of URL that was modified to,
            "url_string": The URL that was newly modified to,
            "url_tags": An array of tag ID's associated with this URL
            "added_by": Id of the user who added this, should be the user modifying it
            "notes": String representing the URL description in this UTub
        }
        "UTub_ID" : UTub ID where this URL exists,
        "UTub_name" : Name of UTub where this
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Grab URL that already exists in database and is not in this UTub
        url_not_in_utub = Utub_Urls.query.filter(Utub_Urls.utub_id != utub_creator_of.id).first()
        assert Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_not_in_utub.url_id).first() is None
        url_string_of_url_not_in_utub = url_not_in_utub.url_in_utub.url_string
        url_id_of_url_not_in_utub = url_not_in_utub.url_id

        # Grab URL that already exists in this UTub
        url_in_utub = Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, user_id=current_user.id).first()
        id_of_url_in_utub = url_in_utub.url_id
        current_desc = url_in_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_in_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url already in UTub
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_in_utub.url_id).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": url_string_of_url_not_in_utub,
        "url_description": current_desc
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_creator_of.id}/{url_in_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Success"
    assert json_response["Message"] == "URL and/or URL Description modified"
    assert int(json_response["URL"]["added_by"]) == current_user.id
    assert json_response["URL"]["notes"] == current_desc
    assert int(json_response["URL"]["url_id"]) != id_of_url_in_utub
    assert int(json_response["URL"]["url_id"]) == url_id_of_url_not_in_utub
    assert json_response["URL"]["url_string"] == url_string_of_url_not_in_utub
    assert json_response["URL"]["url_tags"] == associated_tag_ids
    assert int(json_response["UTub_ID"]) == utub_creator_of.id
    assert json_response["UTub_name"] == utub_creator_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub, url_notes=current_desc).all()) == 0

        # Assert newest entity exist
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_id_of_url_not_in_utub, url_notes=current_desc).all()) == 1 

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_id_of_url_not_in_utub).all()) == len(associated_tags)

def test_update_valid_url_with_previously_added_url_as_url_adder(add_two_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with a URL already in the database, with no description change, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Success",
        "Message": "URL and/or URL Description modified",
        "URL" : Object representing a Utub_Urls, with the following fields 
        {
            "url_id": ID of URL that was modified to,
            "url_string": The URL that was newly modified to,
            "url_tags": An array of tag ID's associated with this URL
            "added_by": Id of the user who added this, should be the user modifying it
            "notes": String representing the URL description in this UTub
        }
        "UTub_ID" : UTub ID where this URL exists,
        "UTub_name" : Name of UTub where this
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        all_utubs_urls = Utub_Urls.query.all()
        for utub_urls in all_utubs_urls:
            utub = utub_urls.utub
            utub_members = [member.user_id for member in utub.members]

            user_in_utub = current_user.id in utub_members
            user_added_url = current_user.id == utub_urls.user_id
            user_not_creator = current_user.id != utub.utub_creator

            if user_in_utub and user_added_url and user_not_creator:
                utub_member_of = utub
                url_in_this_utub = utub_urls
                url_id_of_url_in_this_utub = url_in_this_utub.url_id
                current_desc = url_in_this_utub.url_notes
                break

        # Get a URL that isn't in this UTub
        url_not_in_utub = Utub_Urls.query.filter(Utub_Urls.user_id != current_user.id, Utub_Urls.utub_id != utub_member_of.id).first()
        url_string_of_url_not_in_utub = url_not_in_utub.url_in_utub.url_string
        url_id_of_url_not_in_utub = url_not_in_utub.url_id

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())


    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": url_string_of_url_not_in_utub,
        "url_description": current_desc
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_member_of.id}/{url_in_this_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Success"
    assert json_response["Message"] == "URL and/or URL Description modified"
    assert int(json_response["URL"]["added_by"]) == current_user.id
    assert json_response["URL"]["notes"] == current_desc
    assert int(json_response["URL"]["url_id"]) != url_id_of_url_in_this_utub
    assert int(json_response["URL"]["url_id"]) == url_id_of_url_not_in_utub
    assert json_response["URL"]["url_string"] == url_string_of_url_not_in_utub
    assert json_response["URL"]["url_tags"] == associated_tag_ids
    assert int(json_response["UTub_ID"]) == utub_member_of.id
    assert json_response["UTub_name"] == utub_member_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_id_of_url_in_this_utub, url_notes=current_desc).all()) == 0

        # Assert newest entity exist
        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_id_of_url_not_in_utub, url_notes=current_desc).all()) == 1 

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_id_of_url_not_in_utub).all()) == len(associated_tags)

def test_update_valid_url_with_same_url_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with the same URL already in the database, with no description change, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "No change",
        "Message": "URL and URL description were not modified",
        "URL" : Object representing a Utub_Urls, with the following fields 
        {
            "url_id": ID of URL that was modified to,
            "url_string": The URL that was newly modified to,
            "url_tags": An array of tag ID's associated with this URL
            "added_by": Id of the user who added this, should be the user modifying it
            "notes": String representing the URL description in this UTub
        }
        "UTub_ID" : UTub ID where this URL exists,
        "UTub_name" : Name of UTub where this
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Grab URL that already exists in this UTub
        url_already_in_utub = Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, user_id=current_user.id).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        url_in_utub_string = url_already_in_utub.url_in_utub.url_string
        current_desc = url_already_in_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url already in UTub
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": url_in_utub_string,
        "url_description": current_desc
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_creator_of.id}/{url_already_in_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "No change"
    assert json_response["Message"] == "URL and URL description were not modified"
    assert int(json_response["URL"]["added_by"]) == current_user.id
    assert json_response["URL"]["notes"] == current_desc
    assert int(json_response["URL"]["url_id"]) == id_of_url_in_utub
    assert json_response["URL"]["url_string"] == url_in_utub_string 
    assert json_response["URL"]["url_tags"] == associated_tag_ids
    assert int(json_response["UTub_ID"]) == utub_creator_of.id
    assert json_response["UTub_name"] == utub_creator_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub, url_notes=current_desc).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub).all()) == len(associated_tags)

def test_update_valid_url_with_same_url_as_url_adder(add_two_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with the same URL, with no description change, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "No change",
        "Message": "URL and URL description were not modified",
        "URL" : Object representing a Utub_Urls, with the following fields 
        {
            "url_id": ID of URL that was modified to,
            "url_string": The URL that was newly modified to,
            "url_tags": An array of tag ID's associated with this URL
            "added_by": Id of the user who added this, should be the user modifying it
            "notes": String representing the URL description in this UTub
        }
        "UTub_ID" : UTub ID where this URL exists,
        "UTub_name" : Name of UTub where this
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        all_utubs_urls = Utub_Urls.query.all()
        for utub_urls in all_utubs_urls:
            utub = utub_urls.utub
            utub_members = [member.user_id for member in utub.members]

            user_in_utub = current_user.id in utub_members
            user_added_url = current_user.id == utub_urls.user_id
            user_not_creator = current_user.id != utub.utub_creator

            if user_in_utub and user_added_url and user_not_creator:
                utub_member_of = utub
                url_in_this_utub = utub_urls
                url_id_of_url_in_this_utub = url_in_this_utub.url_id
                current_desc = url_in_this_utub.url_notes
                url_string_of_url_in_utub = url_in_this_utub.url_in_utub.url_string
                break

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": url_string_of_url_in_utub,
        "url_description": current_desc
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_member_of.id}/{url_id_of_url_in_this_utub}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "No change"
    assert json_response["Message"] == "URL and URL description were not modified"
    assert int(json_response["URL"]["added_by"]) == current_user.id
    assert json_response["URL"]["notes"] == current_desc
    assert int(json_response["URL"]["url_id"]) == url_id_of_url_in_this_utub
    assert json_response["URL"]["url_string"] == url_string_of_url_in_utub
    assert json_response["URL"]["url_tags"] == associated_tag_ids
    assert int(json_response["UTub_ID"]) == utub_member_of.id
    assert json_response["UTub_name"] == utub_member_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_id_of_url_in_this_utub, url_notes=current_desc).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_id_of_url_in_this_utub).all()) == len(associated_tags)

def test_update_valid_url_with_same_url_and_new_desc_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with the same URL already in the database, and a description change, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Success",
        "Message": "URL description was modified",
        "URL" : Object representing a Utub_Urls, with the following fields 
        {
            "url_id": ID of URL that was modified to,
            "url_string": The URL that was newly modified to,
            "url_tags": An array of tag ID's associated with this URL
            "added_by": Id of the user who added this, should be the user modifying it
            "notes": String representing the URL description in this UTub
        }
        "UTub_ID" : UTub ID where this URL exists,
        "UTub_name" : Name of UTub where this
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_DESCRIPTION = "THIS IS THE NEW DESCRIPTION."
    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Grab URL that already exists in this UTub
        url_already_in_utub = Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, user_id=current_user.id).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        url_in_utub_string = url_already_in_utub.url_in_utub.url_string
        current_desc = url_already_in_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url already in UTub
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": url_in_utub_string,
        "url_description": NEW_DESCRIPTION 
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_creator_of.id}/{url_already_in_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Success"
    assert json_response["Message"] == "URL description was modified"
    assert int(json_response["URL"]["added_by"]) == current_user.id
    assert json_response["URL"]["notes"] == NEW_DESCRIPTION
    assert int(json_response["URL"]["url_id"]) == id_of_url_in_utub
    assert json_response["URL"]["url_string"] == url_in_utub_string 
    assert json_response["URL"]["url_tags"] == associated_tag_ids
    assert int(json_response["UTub_ID"]) == utub_creator_of.id
    assert json_response["UTub_name"] == utub_creator_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub, url_notes=current_desc).all()) == 0

        # Assert new entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub, url_notes=NEW_DESCRIPTION).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub).all()) == len(associated_tags)

def test_update_valid_url_with_same_url_new_description_as_url_adder(add_two_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with the same URL, with a description change, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Success",
        "Message": "URL description was modified",
        "URL" : Object representing a Utub_Urls, with the following fields 
        {
            "url_id": ID of URL that was modified to,
            "url_string": The URL that was newly modified to,
            "url_tags": An array of tag ID's associated with this URL
            "added_by": Id of the user who added this, should be the user modifying it
            "notes": String representing the URL description in this UTub
        }
        "UTub_ID" : UTub ID where this URL exists,
        "UTub_name" : Name of UTub where this
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_DESCRIPTION = "THIS IS MY NEW DESCRIPTION."
    with app.app_context():
        all_utubs_urls = Utub_Urls.query.all()
        for utub_urls in all_utubs_urls:
            utub = utub_urls.utub
            utub_members = [member.user_id for member in utub.members]

            user_in_utub = current_user.id in utub_members
            user_added_url = current_user.id == utub_urls.user_id
            user_not_creator = current_user.id != utub.utub_creator

            if user_in_utub and user_added_url and user_not_creator:
                utub_member_of = utub
                url_in_this_utub = utub_urls
                url_id_of_url_in_this_utub = url_in_this_utub.url_id
                current_desc = url_in_this_utub.url_notes
                url_string_of_url_in_utub = url_in_this_utub.url_in_utub.url_string
                break

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": url_string_of_url_in_utub,
        "url_description": NEW_DESCRIPTION
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_member_of.id}/{url_id_of_url_in_this_utub}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Success"
    assert json_response["Message"] == "URL description was modified"
    assert int(json_response["URL"]["added_by"]) == current_user.id
    assert json_response["URL"]["notes"] == NEW_DESCRIPTION
    assert int(json_response["URL"]["url_id"]) == url_id_of_url_in_this_utub
    assert json_response["URL"]["url_string"] == url_string_of_url_in_utub
    assert json_response["URL"]["url_tags"] == associated_tag_ids
    assert int(json_response["UTub_ID"]) == utub_member_of.id
    assert json_response["UTub_name"] == utub_member_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_id_of_url_in_this_utub, url_notes=current_desc).all()) == 0

        # Assert new entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_id_of_url_in_this_utub, url_notes=NEW_DESCRIPTION).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_id_of_url_in_this_utub).all()) == len(associated_tags)

def test_update_valid_url_with_invalid_url_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL, with no description change, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are not modified, all other URL associations are kept consistent, 
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "Unable to add this URL",
        "Error_code": 3
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Grab URL that already exists in this UTub
        url_already_in_utub = Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, user_id=current_user.id).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        current_desc = url_already_in_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url already in UTub
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": "AAAAA",
        "url_description": current_desc
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_creator_of.id}/{url_already_in_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Failure"
    assert json_response["Message"] == "Unable to add this URL"
    assert int(json_response["Error_code"]) == 3

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub, url_notes=current_desc).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub).all()) == len(associated_tags)

def test_update_valid_url_with_invalid_url_as_url_adder(add_two_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with an invalid URL, with no description change, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are not modified, all other URL associations are kept consistent, 
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "Unable to add this URL",
        "Error_code": 3
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        all_utubs_urls = Utub_Urls.query.all()
        for utub_urls in all_utubs_urls:
            utub = utub_urls.utub
            utub_members = [member.user_id for member in utub.members]

            user_in_utub = current_user.id in utub_members
            user_added_url = current_user.id == utub_urls.user_id
            user_not_creator = current_user.id != utub.utub_creator

            if user_in_utub and user_added_url and user_not_creator:
                utub_member_of = utub
                url_in_this_utub = utub_urls
                url_id_of_url_in_this_utub = url_in_this_utub.url_id
                current_desc = url_in_this_utub.url_notes
                url_string_of_url_in_utub = url_in_this_utub.url_in_utub.url_string
                break

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())


    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": "AAAAA",
        "url_description": current_desc
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_member_of.id}/{url_id_of_url_in_this_utub}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Failure"
    assert json_response["Message"] == "Unable to add this URL"
    assert int(json_response["Error_code"]) == 3

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_id_of_url_in_this_utub, url_notes=current_desc).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_id_of_url_in_this_utub).all()) == len(associated_tags)

def test_update_valid_url_with_same_url_and_empty_desc_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with the same URL already in the database, and a description change, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent, 
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Success",
        "Message": "URL description was modified",
        "URL" : Object representing a Utub_Urls, with the following fields 
        {
            "url_id": ID of URL that was modified to,
            "url_string": The URL that was newly modified to,
            "url_tags": An array of tag ID's associated with this URL
            "added_by": Id of the user who added this, should be the user modifying it
            "notes": String representing the URL description in this UTub
        }
        "UTub_ID" : UTub ID where this URL exists,
        "UTub_name" : Name of UTub where this
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_DESCRIPTION = ""
    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Grab URL that already exists in this UTub
        url_already_in_utub = Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, user_id=current_user.id).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        url_in_utub_string = url_already_in_utub.url_in_utub.url_string
        current_desc = url_already_in_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url already in UTub
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": url_in_utub_string,
        "url_description": NEW_DESCRIPTION 
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_creator_of.id}/{url_already_in_utub.url_id}", data=edit_url_string_desc_form)

    print(edit_url_string_desc_form.json)
    assert edit_url_string_desc_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Success"
    assert json_response["Message"] == "URL description was modified"
    assert int(json_response["URL"]["added_by"]) == current_user.id
    assert json_response["URL"]["notes"] == NEW_DESCRIPTION
    assert int(json_response["URL"]["url_id"]) == id_of_url_in_utub
    assert json_response["URL"]["url_string"] == url_in_utub_string 
    assert json_response["URL"]["url_tags"] == associated_tag_ids
    assert int(json_response["UTub_ID"]) == utub_creator_of.id
    assert json_response["UTub_name"] == utub_creator_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub, url_notes=current_desc).all()) == 0

        # Assert new entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub, url_notes=NEW_DESCRIPTION).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub).all()) == len(associated_tags)

def test_update_valid_url_with_empty_url_and_empty_desc_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an empty URL and url description, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are unmodified, all other URL associations are kept consistent, 
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "Unable to modify this URL, please check inputs",
        "Errors" : Object representing the errors found in the form, with the following fields 
        {
            "url_string": Array of errors associated with the url_string field,
            "url_description": Array of errors associated with the url_description field 
        }
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_DESCRIPTION = NEW_URL = ""
    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Grab URL that already exists in this UTub
        url_already_in_utub = Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, user_id=current_user.id).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        current_desc = url_already_in_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url already in UTub
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": NEW_URL,
        "url_description": NEW_DESCRIPTION 
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_creator_of.id}/{url_already_in_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 404 

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Failure"
    assert json_response["Message"] == "Unable to modify this URL, please check inputs"
    assert int(json_response["Error_code"]) == 5
    assert json_response["Errors"]["url_string"] == ["This field is required."]

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub, url_notes=current_desc).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub).all()) == len(associated_tags)

def test_update_valid_url_with_empty_url_and_valid_desc_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an empty URL and valid url description, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are unmodified, all other URL associations are kept consistent, 
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "Unable to modify this URL, please check inputs",
        "Errors" : Object representing the errors found in the form, with the following fields 
        {
            "url_string": Array of errors associated with the url_string field,
            "url_description": Array of errors associated with the url_description field 
        }
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_URL = ""
    NEW_DESCRIPTION = "My New Description."
    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Grab URL that already exists in this UTub
        url_already_in_utub = Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, user_id=current_user.id).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        url_in_utub_string = url_already_in_utub.url_in_utub.url_string
        current_desc = url_already_in_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url already in UTub
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": NEW_URL,
        "url_description": NEW_DESCRIPTION 
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_creator_of.id}/{url_already_in_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 404 

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Failure"
    assert json_response["Message"] == "Unable to modify this URL, please check inputs"
    assert int(json_response["Error_code"]) == 5
    assert json_response["Errors"]["url_string"] == ["This field is required."]

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub, url_notes=current_desc).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub).all()) == len(associated_tags)

def test_update_url_description_with_fresh_valid_url_as_another_current_utub_member(add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid member of a UTub that has members, URLs, and tags associated with each URL
    WHEN the member attempts to modify the URL description and change the URL and did not add the URL, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of new description
    THEN verify that the backend denies the user, the url-utub-user associations and url-tag are not modified,
        all other URL associations are kept consistent, the server sends back a 403 HTTP status code, 
        and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "Unable to modify this URL",
        "Error_code" : 1
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_FRESH_URL = "github.com"
    NEW_DESCRIPTION = "This is my newest github.com!"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of = Utub.query.filter(Utub.utub_creator != current_user.id).first()

        # Verify logged in user is not creator of this UTub
        assert utub_member_of.utub_creator != current_user.id

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = check_request_head(NEW_FRESH_URL)
        assert URLS.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL in this UTub
        url_in_this_utub = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.user_id != current_user.id).first()
        current_desc = url_in_this_utub.url_notes
        url_in_utub_serialized_originally = url_in_this_utub.serialized
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": validated_new_fresh_url,
        "url_description": NEW_DESCRIPTION
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_member_of.id}/{url_in_this_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Failure"
    assert json_response["Message"] == "Unable to modify this URL"
    assert int(json_response["Error_code"]) == 1 

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all()) == num_of_url_utub_associations

        assert Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=original_url_id, user_id=original_user_id).first().serialized == url_in_utub_serialized_originally

        # Assert previous entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id).all()) == len(associated_tags)

def test_update_url_description_with_fresh_valid_url_as_other_utub_member(add_first_user_to_second_utub_and_add_tags_remove_first_utub, login_first_user_without_register):
    """
    GIVEN a valid member of a UTub that has members, URLs, and tags associated with each URL
    WHEN the member attempts to modify the URL description and change the URL for a URL of another UTub, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of new description
    THEN verify that the backend denies the user, the url-utub-user associations and url-tag are not modified,
        all other URL associations are kept consistent, the server sends back a 403 HTTP status code, 
        and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "Unable to modify this URL",
        "Error_code" : 1
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_FRESH_URL = "github.com"
    NEW_DESCRIPTION = "This is my newest github.com!"
    with app.app_context():
        # Get UTub this user is not a member of
        utub_user_not_member_of = Utub.query.get(3)

        all_utubs = Utub.query.all()
        for utub in all_utubs:
            assert current_user.id != utub.utub_creator
        
        # Verify logged in user is not member of this UTub
        assert current_user.id not in [chosen_utub_member.user_id for chosen_utub_member in utub_user_not_member_of.members]  

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = check_request_head(NEW_FRESH_URL)
        assert URLS.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL not in this UTub
        url_in_this_utub = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_user_not_member_of.id).first()
        current_desc = url_in_this_utub.url_notes
        url_in_utub_serialized_originally = url_in_this_utub.serialized
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1

        # Get number of URLs in this UTub
        num_of_urls_in_utub = len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id).all())
        
        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": validated_new_fresh_url,
        "url_description": NEW_DESCRIPTION
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_user_not_member_of.id}/{url_in_this_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Failure"
    assert json_response["Message"] == "Unable to modify this URL"
    assert int(json_response["Error_code"]) == 1 

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        assert len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id).all()) == num_of_urls_in_utub

        # Assert url-utub association hasn't changed
        assert len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all()) == num_of_url_utub_associations
        assert Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=original_url_id, user_id=original_user_id).first().serialized == url_in_utub_serialized_originally

        # Assert previous entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id).all()) == len(associated_tags)

def test_update_url_description_with_fresh_valid_url_as_other_utub_creator(add_two_users_and_all_urls_to_each_utub_with_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with each URL
    WHEN the member attempts to modify the URL description and change the URL for a URL of another UTub, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
            "url_description": String of new description
    THEN verify that the backend denies the user, the url-utub-user associations and url-tag are not modified,
        all other URL associations are kept consistent, the server sends back a 403 HTTP status code, 
        and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "Unable to modify this URL",
        "Error_code" : 1
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_FRESH_URL = "github.com"
    NEW_DESCRIPTION = "This is my newest github.com!"
    with app.app_context():
        # Get UTub this user is not a member of
        all_utubs = Utub.query.all()
        i = 0
        while current_user.id in [utub_member.user_id for utub_member in all_utubs[i].members] and current_user.id == all_utubs[i].utub_creator:
            i += 1 

        utub_user_not_member_of = all_utubs[i]
        
        # Verify logged in user is not member of this UTub
        assert current_user.id not in [chosen_utub_member.user_id for chosen_utub_member in utub_user_not_member_of.members]  
        
        # Verify user is creator of a UTub
        i = 0
        while all_utubs[i].utub_creator != current_user.id:
            i += 1
        
        assert all_utubs[i].utub_creator == current_user.id

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = check_request_head(NEW_FRESH_URL)
        assert URLS.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL not in this UTub
        url_in_this_utub = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_user_not_member_of.id).first()
        current_desc = url_in_this_utub.url_notes
        url_in_utub_serialized_originally = url_in_this_utub.serialized
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1

        # Get number of URLs in this UTub
        num_of_urls_in_utub = len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id).all())
        
        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": validated_new_fresh_url,
        "url_description": NEW_DESCRIPTION
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_user_not_member_of.id}/{url_in_this_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Failure"
    assert json_response["Message"] == "Unable to modify this URL"
    assert int(json_response["Error_code"]) == 1 

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        assert len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id).all()) == num_of_urls_in_utub

        # Assert url-utub association hasn't changed
        assert len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all()) == num_of_url_utub_associations
        assert Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=original_url_id, user_id=original_user_id).first().serialized == url_in_utub_serialized_originally

        # Assert previous entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id, url_notes=current_desc).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id).all()) == len(associated_tags)

def test_update_valid_url_with_missing_url_field_and_valid_desc_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a missing URL vield and valid url description, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_description": String of current description, no change
    THEN verify that the url-utub-user associations and url-tag are unmodified, all other URL associations are kept consistent, 
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "Unable to modify this URL, please check inputs",
        "Errors" : Object representing the errors found in the form, with the following fields 
        {
            "url_string": Array of errors associated with the url_string field,
            "url_description": Array of errors associated with the url_description field 
        }
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_DESCRIPTION = "My New Description."
    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Grab URL that already exists in this UTub
        url_already_in_utub = Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, user_id=current_user.id).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        url_in_utub_string = url_already_in_utub.url_in_utub.url_string
        current_desc = url_already_in_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url already in UTub
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_description": NEW_DESCRIPTION 
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_creator_of.id}/{url_already_in_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 404 

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Failure"
    assert json_response["Message"] == "Unable to modify this URL, please check inputs"
    assert int(json_response["Error_code"]) == 5
    assert json_response["Errors"]["url_string"] == ["This field is required."]

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub, url_notes=current_desc).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub).all()) == len(associated_tags)

# TODO: Try to update without description field
def test_update_valid_url_with_valid_url_and_missing_valid_desc_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a missing URL vield and valid url description, via a POST to
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
    THEN verify that the url-utub-user associations and url-tag are unmodified, all other URL associations are kept consistent, 
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        "Status" : "Failure",
        "Message": "Unable to modify this URL, please check inputs",
        "Errors" : Object representing the errors found in the form, with the following fields 
        {
            "url_string": Array of errors associated with the url_string field,
            "url_description": Array of errors associated with the url_description field 
        }
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_URL = "github.com"
    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Grab URL that already exists in this UTub
        url_already_in_utub = Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, user_id=current_user.id).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        url_in_utub_string = url_already_in_utub.url_in_utub.url_string
        current_desc = url_already_in_utub.url_notes

        num_of_url_utub_associations = len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id, url_notes=current_desc).all())
        assert num_of_url_utub_associations == 1
        
        # Find associated tags with this url already in UTub
        associated_tags = Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_desc_form = {
        "csrf_token": csrf_token_string,
        "url_string": NEW_URL 
    }

    edit_url_string_desc_form = client.post(f"/url/edit/{utub_creator_of.id}/{url_already_in_utub.url_id}", data=edit_url_string_desc_form)

    assert edit_url_string_desc_form.status_code == 404 

    # Assert JSON response from server is valid
    json_response = edit_url_string_desc_form.json
    assert json_response["Status"] == "Failure"
    assert json_response["Message"] == "Unable to modify this URL, please check inputs"
    assert int(json_response["Error_code"]) == 4
    assert json_response["Errors"]["url_description"] == ["This field is required."]

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert len(Utub_Urls.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub, url_notes=current_desc).all()) == 1

        # Check associated tags
        assert len(Url_Tags.query.filter_by(utub_id=utub_creator_of.id, url_id=id_of_url_in_utub).all()) == len(associated_tags)
# TODO: Try to update without csrf token
