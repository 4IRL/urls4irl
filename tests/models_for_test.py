from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.splash_form_strs import REGISTER_FORM

"""
Users used for testing logging in correctly
Models follow what is on a valid registration form
"""
valid_user_1: dict[str, str | None] = {
    MODEL_STRS.ID: 1,
    REGISTER_FORM.CSRF_TOKEN: None,
    REGISTER_FORM.USERNAME: "FakeUserName1234",
    REGISTER_FORM.EMAIL: "FakeUserName123@email.com",
    REGISTER_FORM.CONFIRM_EMAIL: "FakeUserName123@email.com",
    REGISTER_FORM.PASSWORD: "FakePassword1234",
    REGISTER_FORM.CONFIRM_PASSWORD: "FakePassword1234",
}

valid_user_2: dict[str, str | None] = {
    MODEL_STRS.ID: 2,
    REGISTER_FORM.CSRF_TOKEN: None,
    REGISTER_FORM.USERNAME: "CenturyUser1234",
    REGISTER_FORM.EMAIL: "CenturyUser@email.com",
    REGISTER_FORM.CONFIRM_EMAIL: "CenturyUser@email.com",
    REGISTER_FORM.PASSWORD: "CenturyPassword1234",
    REGISTER_FORM.CONFIRM_PASSWORD: "CenturyPassword1234",
}

valid_user_3: dict[str, str | None] = {
    MODEL_STRS.ID: 3,
    REGISTER_FORM.CSRF_TOKEN: None,
    REGISTER_FORM.USERNAME: "PersonalEntry1234",
    REGISTER_FORM.EMAIL: "PersonalEntry@email.com",
    REGISTER_FORM.CONFIRM_EMAIL: "PersonalEntry@email.com",
    REGISTER_FORM.PASSWORD: "PersonalPassword1234",
    REGISTER_FORM.CONFIRM_PASSWORD: "PersonalPassword1234",
}

valid_users: tuple[dict[str, str | None]] = (
    valid_user_1,
    valid_user_2,
    valid_user_3,
)

"""
User who will never be added to the database
"""
invalid_user_1 = {
    REGISTER_FORM.CSRF_TOKEN: None,
    REGISTER_FORM.USERNAME: "NeverFindMe1234",
    REGISTER_FORM.EMAIL: "NeverFindMe1234@email.com",
    REGISTER_FORM.CONFIRM_EMAIL: "NeverFindMe1234@email.com",
    REGISTER_FORM.PASSWORD: "NeverPassByMe1234",
    REGISTER_FORM.CONFIRM_PASSWORD: "NeverPassByMe1234",
}

"""
Valid tags used for testing
"""
valid_tag_1 = {MODEL_STRS.ID: 1, MODEL_STRS.TAG_STRING: "Exciting!"}

valid_tag_2 = {MODEL_STRS.ID: 2, MODEL_STRS.TAG_STRING: "Funny"}

valid_tag_3 = {MODEL_STRS.ID: 3, MODEL_STRS.TAG_STRING: "Ugh"}

all_tags = (
    valid_tag_1,
    valid_tag_2,
    valid_tag_3,
)
valid_tag_ids = [tag[MODEL_STRS.ID] for tag in all_tags]
all_tag_strings = [tag[MODEL_STRS.TAG_STRING] for tag in all_tags]

"""
Valid URLs used for testing, without tags
"""
valid_url_without_tag_1 = {
    MODEL_STRS.UTUB_URL_ID: 1,
    MODEL_STRS.URL_STRING: "https://www.google.com/",
    MODEL_STRS.URL_TAGS: [],
    MODEL_STRS.URL_TITLE: "",
    MODEL_STRS.CAN_DELETE: True,
}

valid_url_without_tag_2 = {
    MODEL_STRS.UTUB_URL_ID: 2,
    MODEL_STRS.URL_STRING: "https://github.com/",
    MODEL_STRS.URL_TAGS: [],
    MODEL_STRS.URL_TITLE: "",
    MODEL_STRS.CAN_DELETE: True,
}

valid_url_without_tag_3 = {
    MODEL_STRS.UTUB_URL_ID: 3,
    MODEL_STRS.URL_STRING: "https://www.microsoft.com/",
    MODEL_STRS.URL_TAGS: [],
    MODEL_STRS.URL_TITLE: "",
    MODEL_STRS.CAN_DELETE: True,
}

all_urls_no_tags = (
    valid_url_without_tag_1,
    valid_url_without_tag_2,
    valid_url_without_tag_3,
)

valid_url_strings = [
    url[MODEL_STRS.URL_STRING]
    for url in (
        valid_url_without_tag_1,
        valid_url_without_tag_2,
        valid_url_without_tag_3,
    )
]

"""
Valid URLs used for testing, with tags
"""
valid_url_with_tag_1 = {
    MODEL_STRS.UTUB_URL_ID: 1,
    MODEL_STRS.URL_STRING: "https://www.google.com/",
    MODEL_STRS.URL_TAGS: valid_tag_ids,
    MODEL_STRS.URL_TITLE: "",
    MODEL_STRS.CAN_DELETE: True,
}

valid_url_with_tag_2 = {
    MODEL_STRS.UTUB_URL_ID: 2,
    MODEL_STRS.URL_STRING: "https://github.com/",
    MODEL_STRS.URL_TAGS: valid_tag_ids,
    MODEL_STRS.URL_TITLE: "",
    MODEL_STRS.CAN_DELETE: True,
}

valid_url_with_tag_3 = {
    MODEL_STRS.UTUB_URL_ID: 3,
    MODEL_STRS.URL_STRING: "https://www.microsoft.com/",
    MODEL_STRS.URL_TAGS: valid_tag_ids,
    MODEL_STRS.URL_TITLE: "",
    MODEL_STRS.CAN_DELETE: True,
}

"""
Valid UTubs for testing, empty
"""
valid_empty_utub_1 = {
    MODEL_STRS.ID: 1,
    MODEL_STRS.NAME: "Test UTub 1",
    MODEL_STRS.UTUB_DESCRIPTION: "First Test UTub",
}

valid_empty_utub_2 = {
    MODEL_STRS.ID: 2,
    MODEL_STRS.NAME: "Test UTub 2",
    MODEL_STRS.UTUB_DESCRIPTION: "Second Test UTub",
}

valid_empty_utub_3 = {
    MODEL_STRS.ID: 3,
    MODEL_STRS.NAME: "Test UTub 3",
    MODEL_STRS.UTUB_DESCRIPTION: "Third Test UTub",
}

all_empty_utubs = (
    valid_empty_utub_1,
    valid_empty_utub_2,
    valid_empty_utub_3,
)

"""
UTub serialized data for testing
"""
# UTub serialized data with only creator
valid_utub_serializations_with_only_creator = []
for utub, user in zip(all_empty_utubs, valid_users):
    valid_utub_serializations_with_only_creator.append(
        {
            MODEL_STRS.ID: utub[MODEL_STRS.ID],
            MODEL_STRS.NAME: utub[MODEL_STRS.NAME],
            MODEL_STRS.CREATED_BY: utub[MODEL_STRS.ID],
            MODEL_STRS.CREATED_AT: None,
            MODEL_STRS.DESCRIPTION: utub[MODEL_STRS.UTUB_DESCRIPTION],
            MODEL_STRS.MEMBERS: [
                {
                    MODEL_STRS.ID: user[MODEL_STRS.ID],
                    REGISTER_FORM.USERNAME: user[REGISTER_FORM.USERNAME],
                }
            ],
            MODEL_STRS.URLS: [],
            MODEL_STRS.TAGS: [],
        }
    )

# UTub serialized data with only creator and all members
valid_utub_serializations_with_members = []
for utub, user in zip(all_empty_utubs, valid_users):
    valid_utub_serializations_with_members.append(
        {
            MODEL_STRS.ID: utub[MODEL_STRS.ID],
            MODEL_STRS.NAME: utub[MODEL_STRS.NAME],
            MODEL_STRS.CREATED_BY: utub[MODEL_STRS.ID],
            MODEL_STRS.CREATED_AT: None,
            MODEL_STRS.DESCRIPTION: utub[MODEL_STRS.UTUB_DESCRIPTION],
            MODEL_STRS.MEMBERS: [
                {
                    MODEL_STRS.ID: all_user[MODEL_STRS.ID],
                    REGISTER_FORM.USERNAME: all_user[REGISTER_FORM.USERNAME],
                }
                for all_user in valid_users
            ],
            MODEL_STRS.URLS: [],
            MODEL_STRS.TAGS: [],
        }
    )

# UTub serialized data with all members and one URL - URL ID == UTub ID, Url added by ID == UTub ID
valid_utub_serializations_with_members_and_url = []
for utub, user, url in zip(all_empty_utubs, valid_users, all_urls_no_tags):
    valid_utub_serializations_with_members_and_url.append(
        {
            MODEL_STRS.ID: utub[MODEL_STRS.ID],
            MODEL_STRS.NAME: utub[MODEL_STRS.NAME],
            MODEL_STRS.CREATED_BY: utub[MODEL_STRS.ID],
            MODEL_STRS.CREATED_AT: None,
            MODEL_STRS.DESCRIPTION: utub[MODEL_STRS.UTUB_DESCRIPTION],
            MODEL_STRS.MEMBERS: [
                {
                    MODEL_STRS.ID: all_user[MODEL_STRS.ID],
                    REGISTER_FORM.USERNAME: all_user[REGISTER_FORM.USERNAME],
                }
                for all_user in valid_users
            ],
            MODEL_STRS.URLS: [
                {
                    MODEL_STRS.UTUB_URL_ID: url[MODEL_STRS.UTUB_URL_ID],
                    MODEL_STRS.URL_STRING: url[MODEL_STRS.URL_STRING],
                    MODEL_STRS.URL_TAGS: [],
                    MODEL_STRS.URL_TITLE: f"This is {url[MODEL_STRS.URL_STRING]}",
                    MODEL_STRS.CAN_DELETE: False,
                }
            ],
            MODEL_STRS.TAGS: [],
        }
    )

# UTub serialized data with all members, URLs, and all tags applied to each URL
# URL added by same ID as URL
valid_utub_serializations_with_members_and_url_and_tags = []
for utub in all_empty_utubs:
    valid_utub_serializations_with_members_and_url_and_tags.append(
        {
            MODEL_STRS.ID: utub[MODEL_STRS.ID],
            MODEL_STRS.NAME: utub[MODEL_STRS.NAME],
            MODEL_STRS.CREATED_BY: utub[MODEL_STRS.ID],
            MODEL_STRS.CREATED_AT: None,
            MODEL_STRS.DESCRIPTION: utub[MODEL_STRS.UTUB_DESCRIPTION],
            MODEL_STRS.MEMBERS: [
                {
                    MODEL_STRS.ID: all_user[MODEL_STRS.ID],
                    REGISTER_FORM.USERNAME: all_user[REGISTER_FORM.USERNAME],
                }
                for all_user in valid_users
            ],
            MODEL_STRS.URLS: [
                {
                    MODEL_STRS.UTUB_URL_ID: url[MODEL_STRS.UTUB_URL_ID],
                    MODEL_STRS.URL_STRING: url[MODEL_STRS.URL_STRING],
                    MODEL_STRS.URL_TAGS: [tag[MODEL_STRS.ID] for tag in all_tags],
                    MODEL_STRS.URL_TITLE: f"This is {url[MODEL_STRS.URL_STRING]}",
                    MODEL_STRS.CAN_DELETE: True,
                }
                for url in all_urls_no_tags
            ],
            MODEL_STRS.TAGS: [tag for tag in all_tags],
            MODEL_STRS.IS_CREATOR: True,
        }
    )
