"""Unit coverage for the splash marketing strings module.

Asserts every public constant in `backend.utils.strings.splash_marketing_strs`
is a non-empty `str`. Does not assert literal contents (mirror-string
anti-pattern) — only the type/non-empty invariant that the Jinja templates and
the `STRINGS` bridge rely on.
"""

from __future__ import annotations

import pytest

from backend.utils.strings import splash_marketing_strs
from backend.utils.strings.splash_marketing_strs import (
    SPLASH_FEATURE_1_BODY,
    SPLASH_FEATURE_1_TITLE,
    SPLASH_FEATURE_2_BODY,
    SPLASH_FEATURE_2_TITLE,
    SPLASH_FEATURE_3_BODY,
    SPLASH_FEATURE_3_TITLE,
    SPLASH_FEATURES_HEADING,
    SPLASH_META_DESCRIPTION,
    SPLASH_MOCK_TAG_1,
    SPLASH_MOCK_TAG_2,
    SPLASH_MOCK_TAG_3,
    SPLASH_MOCK_URL_1_TITLE,
    SPLASH_MOCK_URL_1_URL,
    SPLASH_MOCK_URL_2_TITLE,
    SPLASH_MOCK_URL_2_URL,
    SPLASH_MOCK_URL_3_TITLE,
    SPLASH_MOCK_URL_3_URL,
    SPLASH_MOCK_UTUB_1_NAME,
    SPLASH_MOCK_UTUB_2_NAME,
    SPLASH_MOCK_UTUB_3_NAME,
    SPLASH_MOCK_UTUB_4_NAME,
    SPLASH_MOCK_UTUB_DESCRIPTION,
    SPLASH_PRODUCT_PREVIEW_CAPTION,
    SPLASH_PRODUCT_PREVIEW_HEADING,
    SPLASH_TAGLINE,
)

MARKETING_CONSTANTS_BY_NAME = {
    "SPLASH_FEATURE_1_BODY": SPLASH_FEATURE_1_BODY,
    "SPLASH_FEATURE_1_TITLE": SPLASH_FEATURE_1_TITLE,
    "SPLASH_FEATURE_2_BODY": SPLASH_FEATURE_2_BODY,
    "SPLASH_FEATURE_2_TITLE": SPLASH_FEATURE_2_TITLE,
    "SPLASH_FEATURE_3_BODY": SPLASH_FEATURE_3_BODY,
    "SPLASH_FEATURE_3_TITLE": SPLASH_FEATURE_3_TITLE,
    "SPLASH_FEATURES_HEADING": SPLASH_FEATURES_HEADING,
    "SPLASH_META_DESCRIPTION": SPLASH_META_DESCRIPTION,
    "SPLASH_MOCK_TAG_1": SPLASH_MOCK_TAG_1,
    "SPLASH_MOCK_TAG_2": SPLASH_MOCK_TAG_2,
    "SPLASH_MOCK_TAG_3": SPLASH_MOCK_TAG_3,
    "SPLASH_MOCK_URL_1_TITLE": SPLASH_MOCK_URL_1_TITLE,
    "SPLASH_MOCK_URL_1_URL": SPLASH_MOCK_URL_1_URL,
    "SPLASH_MOCK_URL_2_TITLE": SPLASH_MOCK_URL_2_TITLE,
    "SPLASH_MOCK_URL_2_URL": SPLASH_MOCK_URL_2_URL,
    "SPLASH_MOCK_URL_3_TITLE": SPLASH_MOCK_URL_3_TITLE,
    "SPLASH_MOCK_URL_3_URL": SPLASH_MOCK_URL_3_URL,
    "SPLASH_MOCK_UTUB_1_NAME": SPLASH_MOCK_UTUB_1_NAME,
    "SPLASH_MOCK_UTUB_2_NAME": SPLASH_MOCK_UTUB_2_NAME,
    "SPLASH_MOCK_UTUB_3_NAME": SPLASH_MOCK_UTUB_3_NAME,
    "SPLASH_MOCK_UTUB_4_NAME": SPLASH_MOCK_UTUB_4_NAME,
    "SPLASH_MOCK_UTUB_DESCRIPTION": SPLASH_MOCK_UTUB_DESCRIPTION,
    "SPLASH_PRODUCT_PREVIEW_CAPTION": SPLASH_PRODUCT_PREVIEW_CAPTION,
    "SPLASH_PRODUCT_PREVIEW_HEADING": SPLASH_PRODUCT_PREVIEW_HEADING,
    "SPLASH_TAGLINE": SPLASH_TAGLINE,
}


@pytest.mark.unit
@pytest.mark.parametrize(
    "marketing_string",
    MARKETING_CONSTANTS_BY_NAME.values(),
    ids=MARKETING_CONSTANTS_BY_NAME.keys(),
)
def test_marketing_constant_is_non_empty_str(marketing_string: str) -> None:
    assert isinstance(marketing_string, str)
    assert marketing_string.strip() != ""


@pytest.mark.unit
def test_every_public_module_constant_is_covered() -> None:
    public_constant_names = {
        name for name in dir(splash_marketing_strs) if name.startswith("SPLASH_")
    }
    uncovered = public_constant_names - set(MARKETING_CONSTANTS_BY_NAME)
    assert uncovered == set()
