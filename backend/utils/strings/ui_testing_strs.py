# Internal libraries
from backend.cli.mock_constants import (
    USERNAME_BASE,
    MOCK_UTUB_NAME_BASE,
    EMAIL_SUFFIX,
    MOCK_URL_STRINGS,
)
from backend.utils.strings.admin_metrics_strs import ADMIN_METRICS_STRINGS
from backend.utils.strings.search_strs import CROSS_SEARCH_NO_RESULTS
from backend.utils.strings.tag_strs import TAG_FILTER_NO_RESULTS
from backend.utils.strings.url_strs import (
    ADD_URL_BUTTON,
    URL_SEARCH_NO_RESULTS,
    UTUB_NO_URLS,
)
from backend.utils.strings.user_settings_strs import USER_SETTINGS_STRINGS
from backend.utils.strings.user_strs import COOKIE_BANNER_SEEN
from backend.utils.strings.utub_strs import UTUB_SEARCH_NO_RESULTS


class UI_TEST_STRINGS:
    BASE_URL = "http://127.0.0.1:"
    DOCKER_BASE_URL = "http://web:"

    TEST_USERNAME_1 = USERNAME_BASE + "1"
    # Using password as email
    TEST_PASSWORD_1 = TEST_USERNAME_1 + EMAIL_SUFFIX

    TEST_USERNAME_UNLISTED = USERNAME_BASE + "_UNLISTED"
    TEST_PASSWORD_UNLISTED = TEST_USERNAME_UNLISTED + EMAIL_SUFFIX

    # Register
    PASSWORD_EQUALITY_FAILED = "Passwords are not identical."
    EMAIL_EQUALITY_FAILED = "Emails do not match."

    # UTubs
    TEST_UTUB_NAME_1 = MOCK_UTUB_NAME_BASE + "1"
    TEST_UTUB_NAME_2 = MOCK_UTUB_NAME_BASE + "2"

    # URLDeck header/subheader length-responsive font sizes (px). These mirror
    # the TypeScript constants in frontend/home/utubs/header-fit.ts — they are a
    # cross-language pairing and MUST be kept in sync when changing a font value
    # in either file.
    TITLE_MAX_FONT_PX: int = 32  # mirrors TITLE_MAX_FONT_PX in header-fit.ts
    TITLE_MIN_FONT_PX: int = 16  # mirrors TITLE_MIN_FONT_PX in header-fit.ts
    DESC_MAX_FONT_PX: int = 20  # mirrors DESC_MAX_FONT_PX in header-fit.ts
    DESC_MIN_FONT_PX: int = 14  # mirrors DESC_MIN_FONT_PX in header-fit.ts

    # A 30-char title (the UTub name cap) and a ~240-char description that
    # overflow a single line, forcing the fit logic down to its minimum font and
    # the text to wrap across multiple lines. Used by the URLDeck header-font
    # Selenium tests. The description stays under the MAX_DESCRIPTION_LENGTH (250)
    # column limit while still being long enough — with spaces so word-break wraps
    # at word boundaries — to clamp the description to its minimum font and span
    # several lines in the narrow URLDeck panel.
    SHORT_FIT_UTUB_NAME = "ShortName"
    SHORT_FIT_UTUB_DESCRIPTION = "A short description."
    LONG_FIT_UTUB_NAME = "Wxyz" * 6 + "QrstUv"  # exactly 30 chars, no spaces
    LONG_FIT_UTUB_DESCRIPTION = (
        "This UTub description is intentionally long enough that even at the "
        "smallest font size it cannot fit on one line and must wrap across "
        "several lines while staying fully visible and never truncated, "
        "which is the responsive font-fitting behaviour."
    )  # 244 chars; stays under the 250-char column limit yet still forces min-font wrapping

    # Tags
    TEST_TAG_NAME_1 = "Terrible"

    TEST_URL_STRING_CREATE = MOCK_URL_STRINGS[0]
    TEST_URL_TITLE_1 = "This is " + MOCK_URL_STRINGS[0] + "."
    TEST_URL_TITLE_UPDATE = "MS Support"

    UTUB_SEARCH_NAMES = (
        "A1",
        "B1",
        "C1",
        "D1",
    )

    URL_SEARCH_UTUB_NAME = "URL Search Test UTub"

    URL_SEARCH_TITLES = (
        "Alpha News",
        "Beta Blog",
        "Charlie Docs",
        "Delta Forum",
    )

    URL_SEARCH_STRINGS = (
        "https://alpha-news.com",
        "https://beta-blog.org",
        "https://charlie-docs.io",
        "https://delta-forum.net",
    )

    # Cross-UTub search — shared query term appears in BOTH the title and the
    # url_string of one URL per UTub, so a match surfaces regardless of which
    # field(s) are selected. Two member UTubs (user is creator) each get one
    # matching URL plus a non-matching URL, so search yields >=2 groups.
    CROSS_SEARCH_QUERY_TERM = "orbit"
    CROSS_SEARCH_NO_MATCH_TERM = "zzqxnomatch"
    CROSS_SEARCH_UTUB_NAMES = (
        "Cross Search UTub One",
        "Cross Search UTub Two",
    )
    CROSS_SEARCH_MATCHING_TITLES = (
        "Orbit Mechanics One",
        "Orbit Dynamics Two",
    )
    CROSS_SEARCH_MATCHING_URLS = (
        "https://orbit-one.example.com",
        "https://orbit-two.example.org",
    )
    CROSS_SEARCH_FILLER_TITLES = (
        "Unrelated Page One",
        "Unrelated Page Two",
    )
    CROSS_SEARCH_FILLER_URLS = (
        "https://filler-one.example.com",
        "https://filler-two.example.org",
    )
    # Asserted rendered no-results text — locked to the backend source constant.
    CROSS_SEARCH_NO_RESULTS_TEXT = CROSS_SEARCH_NO_RESULTS

    TAG_FILTER_NO_URLS = TAG_FILTER_NO_RESULTS
    URL_SEARCH_NO_URLS = URL_SEARCH_NO_RESULTS
    UTUB_SEARCH_NO_UTUBS = UTUB_SEARCH_NO_RESULTS
    UTUB_NO_URLS = UTUB_NO_URLS
    ADD_URL_BUTTON = ADD_URL_BUTTON

    COOKIE_NAME, COOKIE_VALUE = COOKIE_BANNER_SEEN.split("=")

    # Admin metrics dashboard — re-export backend constants so test
    # assertions stay locked to the user-facing strings.
    METRICS_DASHBOARD_TITLE = ADMIN_METRICS_STRINGS.METRICS_DASHBOARD_TITLE
    METRICS_TAB_API = ADMIN_METRICS_STRINGS.METRICS_TAB_API
    METRICS_TAB_UI = ADMIN_METRICS_STRINGS.METRICS_TAB_UI
    METRICS_TAB_DOMAIN = ADMIN_METRICS_STRINGS.METRICS_TAB_DOMAIN
    METRICS_TAB_PIPELINE_HEALTH = ADMIN_METRICS_STRINGS.METRICS_TAB_PIPELINE_HEALTH
    METRICS_TAB_FLOWS = ADMIN_METRICS_STRINGS.METRICS_TAB_FLOWS
    METRICS_TAB_GAUGES = ADMIN_METRICS_STRINGS.METRICS_TAB_GAUGES
    METRICS_FLOW_EMPTY = ADMIN_METRICS_STRINGS.METRICS_FLOW_EMPTY
    METRICS_REFRESH_BUTTON_LABEL = ADMIN_METRICS_STRINGS.METRICS_REFRESH_BUTTON_LABEL
    METRICS_TOP_DEVICE_ALL = ADMIN_METRICS_STRINGS.METRICS_TOP_DEVICE_ALL
    METRICS_TOP_DEVICE_MOBILE = ADMIN_METRICS_STRINGS.METRICS_TOP_DEVICE_MOBILE
    METRICS_TOP_DEVICE_DESKTOP = ADMIN_METRICS_STRINGS.METRICS_TOP_DEVICE_DESKTOP
    METRICS_PIPELINE_HEALTH_TITLE = ADMIN_METRICS_STRINGS.METRICS_PIPELINE_HEALTH_TITLE
    METRICS_PIPELINE_HEALTH_EMPTY_STATE = (
        ADMIN_METRICS_STRINGS.METRICS_PIPELINE_HEALTH_EMPTY_STATE
    )
    METRICS_PIPELINE_HEALTH_AXIS_LABEL = (
        ADMIN_METRICS_STRINGS.METRICS_PIPELINE_HEALTH_AXIS_LABEL
    )
    METRICS_PIPELINE_HEALTH_LEGEND_FETCH_DESKTOP = (
        ADMIN_METRICS_STRINGS.METRICS_PIPELINE_HEALTH_LEGEND_FETCH_DESKTOP
    )
    METRICS_PIPELINE_HEALTH_LEGEND_FETCH_MOBILE = (
        ADMIN_METRICS_STRINGS.METRICS_PIPELINE_HEALTH_LEGEND_FETCH_MOBILE
    )
    METRICS_PIPELINE_HEALTH_LEGEND_BEACON_DESKTOP = (
        ADMIN_METRICS_STRINGS.METRICS_PIPELINE_HEALTH_LEGEND_BEACON_DESKTOP
    )
    METRICS_PIPELINE_HEALTH_LEGEND_BEACON_MOBILE = (
        ADMIN_METRICS_STRINGS.METRICS_PIPELINE_HEALTH_LEGEND_BEACON_MOBILE
    )
    METRICS_PIPELINE_HEALTH_CHART_DESC = (
        ADMIN_METRICS_STRINGS.METRICS_PIPELINE_HEALTH_CHART_DESC
    )

    # User settings page — re-export backend constants so test
    # assertions stay locked to the user-facing strings.
    SETTINGS_PAGE_TITLE = USER_SETTINGS_STRINGS.PAGE_TITLE
    SETTINGS_TAB_ACCOUNT = USER_SETTINGS_STRINGS.TAB_ACCOUNT
    SETTINGS_TAB_STATS = USER_SETTINGS_STRINGS.TAB_STATS
    SETTINGS_TAB_PRIVACY_DATA = USER_SETTINGS_STRINGS.TAB_PRIVACY_DATA
    SETTINGS_TAB_UI_SETTINGS = USER_SETTINGS_STRINGS.TAB_UI_SETTINGS
    SETTINGS_PLACEHOLDER = USER_SETTINGS_STRINGS.PLACEHOLDER
