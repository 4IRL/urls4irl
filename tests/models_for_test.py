from datetime import datetime

"""
Users used for testing logging in correctly
Models follow what is on a valid registration form
"""
valid_user_1 = {
    "id": 1,
    "csrf_token": None,
    "username": "FakeUserName1234",
    "email": "FakeUserName123@email.com",
    "confirm_email": "FakeUserName123@email.com",
    "password": "FakePassword1234",
    "confirm_password": "FakePassword1234"
}

valid_user_2 = {
    "id": 2,
    "csrf_token": None,
    "username": "CenturyUser1234",
    "email": "CenturyUser@email.com",
    "confirm_email": "CenturyUser@email.com",
    "password": "CenturyPassword1234",
    "confirm_password": "CenturyPassword1234"
}

valid_user_3 = {
    "id": 3,
    "csrf_token": None,
    "username": "PersonalEntry1234",
    "email": "PersonalEntry@email.com",
    "confirm_email": "PersonalEntry@email.com",
    "password": "PersonalPassword1234",
    "confirm_password": "PersonalPassword1234"
}

valid_users = (valid_user_1, valid_user_2, valid_user_3,)

"""
User who will never be added to the database
"""
invalid_user_1= {
    "csrf_token": None,
    "username": "NeverFindMe1234",
    "email": "NeverFindMe1234@email.com",
    "confirm_email": "NeverFindMe1234@email.com",
    "password": "NeverPassByMe1234",
    "confirm_password": "NeverPassByMe1234"
}

"""
Valid tags used for testing 
"""
valid_tag_1 = {
    'id': 1,
    'tag_string': 'Exciting!'
}

valid_tag_2 = {
    'id': 2,
    'tag_string': 'Funny'
}

valid_tag_3 = {
    'id': 3,
    'tag_string': 'Ugh'
}
valid_tag_ids = [tag["id"] for tag in (valid_tag_1, valid_tag_2, valid_tag_3)]
all_tags = (valid_tag_1, valid_tag_2, valid_tag_3,)

"""
Valid URLs used for testing, without tags    
"""
valid_url_without_tag_1 = {
    "id": 1,
    "url": 'https://www.google.com/',
    "tags": []
}

valid_url_without_tag_2 = {
    "id": 2,
    "url": 'https://www.facebook.com/',
    "tags": []
}

valid_url_without_tag_3 = {
    "id": 3,
    "url": 'https://www.microsoft.com/',
    "tags": []
}

all_urls_no_tags = (valid_url_without_tag_1, valid_url_without_tag_2, valid_url_without_tag_3,)

valid_url_strings = [url["url"] for url in (valid_url_without_tag_1, valid_url_without_tag_2, valid_url_without_tag_3)]

"""
Valid URLs used for testing, with tags    
"""
valid_url_with_tag_1 = {
    "url_id": 1,
    "url_string": 'https://www.google.com/',
    "url_tags": valid_tag_ids,
    "added_by": 1,
    "notes": ""
}

valid_url_with_tag_2 = {
    "url_id": 2,
    "url_string": 'https://www.facebook.com/',
    "url_tags": valid_tag_ids,
    "added_by": 2,
    "notes": ""
}

valid_url_with_tag_3 = {
    "url_id": 3,
    "url_string": 'https://www.microsoft.com/',
    "url_tags": valid_tag_ids,
    "added_by": 3,
    "notes": ""
}

"""
Valid UTubs for testing, empty    
"""
valid_empty_utub_1 = {
    "id": 1,
    "name": "Test UTub 1",
    "utub_description": "First Test UTub"
}

valid_empty_utub_2 = {
    "id": 2,
    "name": "Test UTub 2",
    "utub_description": "Second Test UTub"
}

valid_empty_utub_3 = {
    "id": 3,
    "name": "Test UTub 3",
    "utub_description": "Third Test UTub"
}

all_empty_utubs = (valid_empty_utub_1, valid_empty_utub_2, valid_empty_utub_3,)

"""
UTub serialized data for testing
"""
# UTub serialized data with only creator
valid_utub_serializations_with_only_creator = []
for utub, user in zip(all_empty_utubs, valid_users):
    valid_utub_serializations_with_only_creator.append({
        'id': utub["id"],
        'name': utub["name"],
        'created_by': utub["id"],
        'created_at': None,
        'description': utub["utub_description"],
        'members': [{
            "id": user["id"],
            "username": user["username"]}],
        'urls': [],
        'tags': []
    })

# UTub serialized data with only creator and all members
valid_utub_serializations_with_members = []
for utub, user in zip(all_empty_utubs, valid_users):
    valid_utub_serializations_with_members.append({
        'id': utub["id"],
        'name': utub["name"],
        'created_by': utub["id"],
        'created_at': None,
        'description': utub["utub_description"],
        'members': [{
            "id": all_user["id"],
            "username": all_user["username"]} for all_user in valid_users],
        'urls': [],
        'tags': []
    })

# UTub serialized data with all members and one URL - URL ID == UTub ID, Url added by ID == UTub ID
valid_utub_serializations_with_members_and_url = []
for utub, user, url in zip(all_empty_utubs, valid_users, all_urls_no_tags):
    valid_utub_serializations_with_members_and_url.append({
        'id': utub["id"],
        'name': utub["name"],
        'created_by': utub["id"],
        'created_at': None,
        'description': utub["utub_description"],
        'members': [{
            "id": all_user["id"],
            "username": all_user["username"]} for all_user in valid_users],
        'urls': [{
            "url_id": url["id"],
            "url_string": url["url"],
            "url_tags": [],
            "added_by": user["id"], 
            "notes": f"This is {url['url']}"}],
        'tags': []
        })

# UTub serialized data with all members, URLs, and all tags applied to each URL
# URL added by same ID as URL
valid_utub_serializations_with_members_and_url_and_tags = []
for utub in all_empty_utubs:
    valid_utub_serializations_with_members_and_url_and_tags.append({
        'id': utub["id"],
        'name': utub["name"],
        'created_by': utub["id"],
        'created_at': None,
        'description': utub["utub_description"],
        'members': [{
            "id": all_user["id"],
            "username": all_user["username"]} for all_user in valid_users],
        'urls': [{
            "url_id": url["id"],
            "url_string": url["url"],
            "url_tags": [tag["id"] for tag in all_tags],
            "added_by": url["id"], 
            "notes": f"This is {url['url']}"} for url in all_urls_no_tags],
        'tags': [tag for tag in all_tags]
        })
