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
