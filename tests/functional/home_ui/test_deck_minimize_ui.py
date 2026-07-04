from __future__ import annotations

import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import leave_utub_as_member
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    wait_then_click_element,
)
from tests.functional.utubs_ui.playwright_utils import delete_utub_as_creator

pytestmark = pytest.mark.home_ui

_COLLAPSED_CLASS_RE = re.compile(r"(^|\s)collapsed(\s|$)")
_DECK_LOCKED_CLASS_RE = re.compile(r"(^|\s)deck-locked(\s|$)")


def _caret_hidden(page: Page, deck_selector: str) -> bool:
    return bool(
        page.evaluate(
            """(cssSelector) => {
                const caret = document.querySelector(cssSelector + ' .title-caret');
                if (!caret) return false;
                return getComputedStyle(caret).visibility === 'hidden';
            }""",
            deck_selector,
        )
    )


def _click_deck_header(page: Page, header_selector: str) -> None:
    # A real pointer click can't reach the header (pointer-events:none on the
    # locked state), so fire the click directly to prove the JS guard — not only
    # the CSS — keeps the deck collapsed when no UTub is selected.
    page.evaluate(
        "(cssSelector) => { document.querySelector(cssSelector).click(); }",
        header_selector,
    )


def test_member_and_tag_decks_minimized_when_no_utub_selected(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a user loads the home page (desktop) with no UTub selected
    WHEN the page initializes
    THEN the Member and Tag decks are minimized while the UTub deck stays expanded
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.UTUB_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)


def test_member_and_tag_decks_expand_when_utub_selected(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the home page is loaded with no UTub selected (Member/Tag decks minimized)
    WHEN the user selects a UTub
    THEN the Member and Tag decks expand again
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)

    # Before-state: Member/Tag decks are minimized while no UTub is selected
    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)

    wait_then_click_element(page=page, css_selector=HPL.SELECTORS_UTUB)

    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)


def test_member_and_tag_decks_minimized_after_leaving_utub(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a member has a UTub selected (Member/Tag decks expanded)
    WHEN they leave the UTub, after which no UTub is selected (others remain)
    THEN the Member and Tag decks are minimized again
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

    # With the UTub selected, the Member/Tag decks are expanded
    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)

    leave_utub_as_member(page=page, utub_to_leave=utub_user_member_of)

    # After leaving, no UTub is selected, so the decks minimize again
    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_COLLAPSED_CLASS_RE)


def test_member_and_tag_decks_locked_when_no_utub_selected(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a user loads the home page (desktop) with no UTub selected
    WHEN the page initializes
    THEN the Member and Tag decks are visibly marked non-expandable
        (deck-locked class applied, caret hidden)
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_DECK_LOCKED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_DECK_LOCKED_CLASS_RE)
    assert _caret_hidden(page, HPL.MEMBER_DECK)
    assert _caret_hidden(page, HPL.TAG_DECK)


def test_member_and_tag_decks_not_expandable_when_no_utub_selected(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the home page is loaded with no UTub selected (Member/Tag decks locked)
    WHEN the user attempts to expand a locked Member/Tag deck via its header
    THEN the deck stays minimized
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_DECK_LOCKED_CLASS_RE)

    _click_deck_header(page, HPL.HEADER_AND_CARET_MEMBER_DECK)
    _click_deck_header(page, HPL.HEADER_AND_CARET_TAG_DECK)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_COLLAPSED_CLASS_RE)


def test_member_and_tag_decks_unlocked_when_utub_selected(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the home page is loaded with no UTub selected (Member/Tag decks locked)
    WHEN the user selects a UTub
    THEN the lock is removed so the decks become expandable again
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_DECK_LOCKED_CLASS_RE)

    wait_then_click_element(page=page, css_selector=HPL.SELECTORS_UTUB)

    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_DECK_LOCKED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).not_to_have_class(_DECK_LOCKED_CLASS_RE)


def test_member_and_tag_decks_minimized_after_deleting_utub(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner has a UTub selected (Member/Tag decks expanded)
    WHEN they delete the UTub, after which no UTub is selected (others remain)
    THEN the Member and Tag decks are minimized again
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    # With the UTub selected, the Member/Tag decks are expanded
    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)

    delete_utub_as_creator(page=page, utub_to_delete=utub_user_created)

    # After deleting, no UTub is selected, so the decks minimize again
    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
