import pytest
from flask_login import current_user

from urls4irl.models import Utub, Utub_Urls, Utub_Users, Url_Tags, URLS
from urls4irl.url_validation import check_request_head

def test_update_valid_url_with_another_fresh_valid_url_as_utub_creator(add_one_url_and_all_users_to_each_utub_with_all_tags, login_first_user_without_register):
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
    
