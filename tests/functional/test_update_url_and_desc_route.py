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


# TODO: test update valid url with previously added url as url adder
# TODO: Try to update to same url as utub creator
# TODO: Try to udpate to same url as url added
# TODO: Test update only description as utub creator
# TODO: Test update only description as url adder
# TODO: Try to update with invalid URL, as utub creator
# TODO: Try to update with invalid URL, as url adder
# TODO: Try to update with empty description + url
# TODO: Try to update with empty URL + empty description
# TODO: Try to update with empty URL + description
# TODO: Try to update with valid URL + same description as current utub member
# TODO: Try to update with valid URL + same description as another utub member
# TODO: Try to update with valid URL + same description as another utub creator
# TODO: Try to update without url field
# TODO: Try to update without description field
# TODO: Try to update without csrf token
