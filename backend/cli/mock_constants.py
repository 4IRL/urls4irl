from typing import NamedTuple

TEST_USER_COUNT = 5
USERNAME_BASE = "u4i_test"
EMAIL_SUFFIX = "@urls4irl.app"

MOCK_UTUB_NAME_BASE = "MockUTub_"

# Dedicated full-participant admin mock user, seeded ONLY by the opt-in
# `flask addmock admin` command — never by the default `addmock`/`addmock all`
# seed, so the shared test seed (which the UI suite relies on) is unchanged.
MOCK_ADMIN_USERNAME = "u4i_admin1"
MOCK_ADMIN_UTUB_NAME = f"{MOCK_UTUB_NAME_BASE}admin1"
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

MOCK_TEST_URL_STRINGS = [f"https://www.u4i.test/{idx}" for idx in range(8)]

MOCK_URL_WITH_TRACKING_PARAMS = "https://www.example.com/p?utm_source=google&gclid=abc123"  # fmt: skip
MOCK_URL_TRACKING_STRIPPED = "https://www.example.com/p"

# Tuples of (tracking_url, expected_stripped) seeded ONLY for the migration
# test and the collapse/UI tests — kept out of the default clean seed sets so
# unrelated suites are unperturbed. The first two collapse to the same stripped
# URL, exercising the migration's row-merge path.
MOCK_TRACKING_SEED_URL_PAIRS: tuple[tuple[str, str], ...] = (
    (
        "https://www.example.com/page?utm_source=a&gclid=x",
        "https://www.example.com/page",
    ),
    ("https://www.example.com/page?fbclid=y", "https://www.example.com/page"),
    ("https://www.other.com/page?utm_medium=b", "https://www.other.com/page"),
)

# Raw tracking-seed URL strings, as stored before stripping. Used to exclude
# these intentionally single-tagged URLs from the general mock-tag re-tagging
# pass, so repeated `addmock all` runs stay idempotent.
MOCK_TRACKING_SEED_URL_STRINGS: frozenset[str] = frozenset(
    raw_url for raw_url, _stripped_url in MOCK_TRACKING_SEED_URL_PAIRS
)


class MockInviteLinkState(NamedTuple):
    """One example invite link seeded by `addmock all`, on its own UTub."""

    label: str
    max_uses: int | None
    use_count: int
    expired: bool
    revoked: bool


# One per UTub (the one-active index allows a single unrevoked link per UTub),
# so this must stay <= TEST_USER_COUNT.
MOCK_INVITE_LINK_STATES: tuple[MockInviteLinkState, ...] = (
    MockInviteLinkState("live_unlimited", None, 0, False, False),
    MockInviteLinkState("live_limited", 5, 2, False, False),
    MockInviteLinkState("expired", None, 0, True, False),
    MockInviteLinkState("used_up", 1, 1, False, False),
    MockInviteLinkState("revoked", None, 0, False, True),
)

# Sample custom metric flows seeded by `addmock all` (wire shape, validated by
# validate_flow_payload at seeding time). `device_type:1` is DeviceType.MOBILE.
MOCK_METRIC_FLOW_PAYLOADS: tuple[dict[str, object], ...] = (
    {
        "display_name": "Create UTub on mobile",
        "steps": [
            {
                "stream": "ui",
                "label": "Open create UTub",
                "event_name": "ui_utub_create_open",
                "dim_filter": ["device_type:1"],
            },
            {
                "stream": "ui",
                "label": "Submit form",
                "event_name": "ui_form_submit",
                "dim_filter": ["form:utub_create"],
            },
            {
                "stream": "domain",
                "label": "UTub created",
                "event_name": "utub_created",
            },
        ],
    },
    {
        "display_name": "Login then add URL",
        "steps": [
            {
                "stream": "ui",
                "label": "Submit login",
                "event_name": "ui_login_submit",
            },
            {
                "stream": "domain",
                "label": "Login success",
                "event_name": "login_success",
            },
            {
                "stream": "api",
                "label": "Create URL call",
                "api_endpoint": "urls.create_url",
                "api_method": "POST",
                "dim_filter": ["status_code:200"],
            },
            {
                "stream": "domain",
                "label": "URL added",
                "event_name": "url_added_to_utub",
                "drop_breakdown": {
                    "event_name": "url_create_rejected",
                    "group_by": "reason",
                },
            },
        ],
    },
)

MOCK_TAGS = (
    "Great",
    "Funny",
    "Helpful",
    "Smart",
    "REH",
    "Tech",
    "News",
    "Recipe",
    "Travel",
    "Music",
    "Video",
    "Reference",
    "Tutorial",
    "Shopping",
    "Finance",
    "Health",
    "Sports",
    "Art",
    "Science",
    "Tool",
)
