from flask import Flask
import pytest
from playwright.sync_api import Page

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_tag_to_single_url_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_utubid
from tests.functional.playwright_utils import (
    select_utub_by_id,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.tags_ui

EMPTY_STATE_TAG_STRING = "tagged-other-utub"


def test_zero_tags_utub_shows_empty_state(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user selects a UTub that has URLs but zero tags
    WHEN the tag deck renders
    THEN the empty state (#noTagsEmptyState) is shown with the expected text from
         UTS.TAG_DECK_NO_TAGS and the tag list (#listTags) holds no rows.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_id
    )

    assert_visible_css_selector(page=page, css_selector=HPL.TAG_DECK_EMPTY_STATE)
    empty_state_elem = page.locator(HPL.TAG_DECK_EMPTY_STATE).first
    assert empty_state_elem.inner_text() == UTS.TAG_DECK_NO_TAGS

    # The tag list holds no rows when the UTub has zero tags.
    tag_rows = page.locator(HPL.TAG_FILTERS).all()
    assert len(tag_rows) == 0


def test_selecting_utub_with_tags_hides_empty_state(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user starts on a zero-tag UTub (empty state shown)
    WHEN they switch to a UTub that has tags
    THEN the empty state (#noTagsEmptyState) is hidden and tag rows are present.
    """
    app = provide_app
    user_id_for_test = 1

    # The zero-tag UTub the user starts on.
    empty_utub = get_utub_this_user_created(app, user_id_for_test)
    empty_utub_id = empty_utub.id

    # A different UTub seeded with a tag.
    tagged_utub = get_utub_this_user_did_not_create(app, user_id_for_test)
    tagged_utub_id = tagged_utub.id
    add_tag_to_single_url_in_utub(
        app, tagged_utub_id, user_id_for_test, EMPTY_STATE_TAG_STRING
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=empty_utub_id
    )

    # Before switching: the empty state is shown on the zero-tag UTub.
    assert_visible_css_selector(page=page, css_selector=HPL.TAG_DECK_EMPTY_STATE)

    select_utub_by_id(page=page, utub_id=tagged_utub_id)

    # After switching: the empty state is hidden and the tagged UTub shows rows.
    wait_until_visible_css_selector(page=page, css_selector=HPL.TAG_FILTERS)
    assert_not_visible_css_selector(page=page, css_selector=HPL.TAG_DECK_EMPTY_STATE)
    tag_rows = page.locator(HPL.TAG_FILTERS).all()
    assert len(tag_rows) >= 1
