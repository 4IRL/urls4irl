import pytest
from flask import Flask
from playwright.sync_api import Page

from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_panel_visibility_mobile
from tests.functional.playwright_utils import (
    Decks,
    click_on_navbar,
    login_user_to_home_page,
    select_utub_by_id_mobile,
    wait_then_click_element,
    wait_until_css_property,
)
from tests.functional.utubs_ui.playwright_utils import wait_for_selection_bar_on_utub

pytestmark = pytest.mark.mobile_ui

USER_ID_FOR_TEST = 1


def test_bar_matches_active_row_after_returning_to_utub_list_mobile(
    page_mobile_portrait: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a mobile user who selected a UTub (the UTub deck is now display:none)
    WHEN the user returns to the UTub list through the navbar
    THEN the selection bar matches the active row's box (not stuck at y=0)
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)

    select_utub_by_id_mobile(page=page, utub_id=utub.id)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)

    wait_until_css_property(
        page=page,
        css_selector=HPL.UTUB_SELECTION_INDICATOR,
        css_property="opacity",
        expected_value="1",
    )
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)
