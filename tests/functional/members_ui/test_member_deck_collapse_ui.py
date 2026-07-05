import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from tests.functional.db_utils import get_utub_this_user_did_not_create
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    wait_then_click_element,
    wait_then_get_element,
)

pytestmark = pytest.mark.members_ui


def _wait_member_deck_collapsed(page: Page, collapsed: bool) -> None:
    if collapsed:
        expect(page.locator(HPL.MEMBER_DECK)).to_have_class(
            re.compile(r"(^|\s)collapsed(\s|$)")
        )
    else:
        expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(
            re.compile(r"(^|\s)collapsed(\s|$)")
        )


def test_add_member_button_stays_hidden_for_non_owner_after_deck_collapse(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a non-owner member of a UTub has it selected
    WHEN they collapse and then re-expand the Member deck
    THEN the add-member button must remain hidden (only the owner may add members)
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    # Before-state: non-owner sees the leave button, never the add-member button
    leave_btn = wait_then_get_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    expect(leave_btn).to_be_visible()
    expect(page.locator(HPL.BUTTON_MEMBER_CREATE)).to_be_hidden()

    # Collapse then re-expand the Member deck
    wait_then_click_element(page=page, css_selector=HPL.HEADER_AND_CARET_MEMBER_DECK)
    _wait_member_deck_collapsed(page, collapsed=True)
    wait_then_click_element(page=page, css_selector=HPL.HEADER_AND_CARET_MEMBER_DECK)
    _wait_member_deck_collapsed(page, collapsed=False)

    # The add-member button must still be hidden for the non-owner
    expect(page.locator(HPL.BUTTON_MEMBER_CREATE)).to_be_hidden()
