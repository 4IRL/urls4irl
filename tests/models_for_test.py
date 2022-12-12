"""
Users used for testing logging in correctly
Models follow what is on a valid registration form
"""

valid_user_1 = {
    "csrf_token": None,
    "username": "FakeUserName1234",
    "email": "FakeUserName123@email.com",
    "confirm_email": "FakeUserName123@email.com",
    "password": "FakePassword1234",
    "confirm_password": "FakePassword1234"
}

valid_user_2 = {
    "csrf_token": None,
    "username": "CenturyUser1234",
    "email": "CenturyUser@email.com",
    "confirm_email": "CenturyUser@email.com",
    "password": "CenturyPassword1234",
    "confirm_password": "CenturyPassword1234"
}

valid_user_3 = {
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

