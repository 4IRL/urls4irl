from src.utils.constants import URL_CONSTANTS


TEST_USER_COUNT = 5
USERNAME_BASE = "u4i_test"
EMAIL_SUFFIX = "@urls4irl.app"

MOCK_UTUB_NAME_BASE = "MockUTub_"
MOCK_UTUB_DESCRIPTION = "This is a description"

MOCK_URL_TITLES = (
    "This is https://www.abc.com/.",
    "This is https://www.bcd.com/.",
    "This is https://www.cde.com/.",
    "This is https://www.def.com/.",
    "This is https://efg.com/.",
)

MOCK_URL_STRINGS = (
    "https://www.abc.com/",
    "https://www.bcd.com/",
    "https://www.cde.com/",
    "https://www.def.com/",
    "https://efg.com/",
)

MOCK_TEST_URL_STRINGS = [
    f"https://www.u4i.test/{idx}"
    for idx in range(URL_CONSTANTS.MAX_NUM_OF_URLS_TO_ACCESS + 5)
]

MOCK_TAGS = (
    "Great",
    "Funny",
    "Helpful",
    "Smart",
    "REH",
)
