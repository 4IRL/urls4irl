from datetime import datetime

"""
Users used for testing logging in correctly
Models follow what is on a valid registration form
"""
valid_user_1 = {
    "id": 0,
    "csrf_token": None,
    "username": "FakeUserName1234",
    "email": "FakeUserName123@email.com",
    "confirm_email": "FakeUserName123@email.com",
    "password": "FakePassword1234",
    "confirm_password": "FakePassword1234"
}

valid_user_2 = {
    "id": 1,
    "csrf_token": None,
    "username": "CenturyUser1234",
    "email": "CenturyUser@email.com",
    "confirm_email": "CenturyUser@email.com",
    "password": "CenturyPassword1234",
    "confirm_password": "CenturyPassword1234"
}

valid_user_3 = {
    "id": 2,
    "csrf_token": None,
    "username": "PersonalEntry1234",
    "email": "PersonalEntry@email.com",
    "confirm_email": "PersonalEntry@email.com",
    "password": "PersonalPassword1234",
    "confirm_password": "PersonalPassword1234"
}

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
    'id': 0,
    'tag_string': 'Exciting!'
}

valid_tag_2 = {
    'id': 1,
    'tag_string': 'Funny'
}

valid_tag_3 = {
    'id': 2,
    'tag_string': 'Ugh'
}
valid_tag_ids = [tag["id"] for tag in (valid_tag_1, valid_tag_2, valid_tag_3)]

"""
Valid URLs used for testing, without tags    
"""
valid_url_without_tag_1 = {
    "id": 0,
    "url": 'https://www.google.com',
    "tags": []
}

valid_url_without_tag_2 = {
    "id": 1,
    "url": 'https://www.facebook.com',
    "tags": []
}

valid_url_without_tag_3 = {
    "id": 2,
    "url": 'https://www.microsoft.com',
    "tags": []
}

valid_url_strings = [url["url"] for url in (valid_url_without_tag_1, valid_url_without_tag_2, valid_url_without_tag_3)]

"""
Valid URLs used for testing, with tags    
"""
valid_url_with_tag_1 = {
    "id": 0,
    "url": 'https://www.google.com',
    "tags": valid_tag_ids
}

valid_url_with_tag_2 = {
    "id": 1,
    "url": 'https://www.facebook.com',
    "tags": valid_tag_ids
}

valid_url_with_tag_3 = {
    "id": 2,
    "url": 'https://www.microsoft.com',
    "tags": valid_tag_ids
}

"""
Valid UTubs for testing, empty    
"""
valid_empty_utub_1 = {
    "id": 0,
    "name": "Test UTub 1",
    "utub_description": "First Test UTub"
}

valid_empty_utub_2 = {
    "id": 1,
    "name": "Test UTub 2",
    "utub_description": "Second Test UTub"
}

valid_empty_utub_3 = {
    "id": 2,
    "name": "Test UTub 3",
    "utub_description": "Third Test UTub"
}

"""
UTub serialized data for testing
"""
valid_utub_serialization_empty = {
    'id': 0,
    'name': "Test UTub 1",
    'created_by': None,
    'created_at': datetime.utcnow(),
    'description': "",
    'members': [],
    'urls': [],
    'tags': []
}

valid_utub_serialization_with_only_creator = {
    'id': 0,
    'name': "Test UTub 1",
    'created_by': valid_user_1["id"],
    'created_at': datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S"),
    'description': "",
    'members': [{
        "id": user["id"],
        "username": user["username"]} for user in (valid_user_1,)],
    'urls': [],
    'tags': []
}

valid_utub_serialization_with_creator_and_member = {
    'id': 0,
    'name': "Test UTub 1",
    'created_by': valid_user_1["id"],
    'created_at': datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S"),
    'description': "",
    'members': [{
        "id": user["id"],
        "username": user["username"]} for user in (valid_user_1, valid_user_2)],
    'urls': [],
    'tags': []
}

valid_utub_serialization_with_members_urls_no_tags = {
    'id': 0,
    'name': "Test UTub 1",
    'created_by': valid_user_1["id"],
    'created_at': datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S"),
    'description': "",
    'members': [{
        "id": user["id"],
        "username": user["username"]} for user in (valid_user_1, valid_user_2)],
    'urls': [{
        "url_id": url["id"],
        "url_string": url["url"],
        "url_tags": [],
        "added_by": 1,  # second user added these for testing
        "notes": ""} for url in (valid_url_without_tag_1, valid_url_without_tag_2, valid_url_without_tag_3,)],
    'tags': []
}

valid_utub_serialization_with_members_urls_tags = {
    'id': 0,
    'name': "Test UTub 1",
    'created_by': valid_user_1["id"],
    'created_at': datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S"),
    'description': "",
    'members': [{
        "id": user["id"],
        "username": user["username"]} for user in (valid_user_1, valid_user_2)],
    'urls': [{
        "url_id": url["id"],
        "url_string": url["url"],
        "url_tags": [url["id"]],
        "added_by": 1,  # second user added these for testing
        "notes": ""} for url in (valid_url_without_tag_1, valid_url_without_tag_2, valid_url_without_tag_3,)],
    'tags': [{
        "id": tag["id"],
        "tag_string": tag["tag_string"]} for tag in (valid_tag_1, valid_tag_2, valid_tag_3)]
}
