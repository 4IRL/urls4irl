from flask import Flask
import pytest
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from locators import HomePageLocators as HPL
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.login_utils import (
    login_user_and_select_utub_by_name,
    login_user_to_home_page,
)
from tests.functional.selenium_utils import (
    leave_utub_as_member,
    wait_then_click_element,
)
from tests.functional.utubs_ui.selenium_utils import delete_utub_as_creator

pytestmark = pytest.mark.home_ui


def _deck_minimized(browser: WebDriver, deck_selector: str) -> bool:
    return bool(
        browser.execute_script(
            "return document.querySelector(arguments[0])"
            ".classList.contains('collapsed');",
            deck_selector,
        )
    )


def _deck_locked(browser: WebDriver, deck_selector: str) -> bool:
    return bool(
        browser.execute_script(
            "return document.querySelector(arguments[0])"
            ".classList.contains('deck-locked');",
            deck_selector,
        )
    )


def test_member_and_tag_decks_minimized_when_no_utub_selected(
    browser: WebDriver,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a user loads the home page (desktop) with no UTub selected
    WHEN the page initializes
    THEN the Member and Tag decks are minimized while the UTub deck stays expanded
    """
    app = provide_app
    login_user_to_home_page(app, browser, user_id=1)

    WebDriverWait(browser, 10).until(
        lambda driver: _deck_minimized(driver, HPL.MEMBER_DECK)
    )
    assert _deck_minimized(browser, HPL.MEMBER_DECK)
    assert _deck_minimized(browser, HPL.TAG_DECK)
    assert not _deck_minimized(browser, HPL.UTUB_DECK)


def test_member_and_tag_decks_expand_when_utub_selected(
    browser: WebDriver,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the home page is loaded with no UTub selected (Member/Tag decks minimized)
    WHEN the user selects a UTub
    THEN the Member and Tag decks expand again
    """
    app = provide_app
    login_user_to_home_page(app, browser, user_id=1)

    # Before-state: Member/Tag decks are minimized while no UTub is selected
    WebDriverWait(browser, 10).until(
        lambda driver: _deck_minimized(driver, HPL.MEMBER_DECK)
    )

    wait_then_click_element(browser, HPL.SELECTORS_UTUB, time=3)

    WebDriverWait(browser, 10).until(
        lambda driver: not _deck_minimized(driver, HPL.MEMBER_DECK)
    )
    assert not _deck_minimized(browser, HPL.MEMBER_DECK)
    assert not _deck_minimized(browser, HPL.TAG_DECK)


def test_member_and_tag_decks_minimized_after_leaving_utub(
    browser: WebDriver,
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
        app, browser, user_id_for_test, utub_user_member_of.name
    )

    # With the UTub selected, the Member/Tag decks are expanded
    WebDriverWait(browser, 10).until(
        lambda driver: not _deck_minimized(driver, HPL.MEMBER_DECK)
    )

    leave_utub_as_member(browser, utub_user_member_of)

    # After leaving, no UTub is selected, so the decks minimize again
    WebDriverWait(browser, 10).until(
        lambda driver: _deck_minimized(driver, HPL.MEMBER_DECK)
    )
    assert _deck_minimized(browser, HPL.MEMBER_DECK)
    assert _deck_minimized(browser, HPL.TAG_DECK)


def _caret_hidden(browser: WebDriver, deck_selector: str) -> bool:
    return bool(
        browser.execute_script(
            "const caret = document.querySelector(arguments[0] + ' .title-caret');"
            "return getComputedStyle(caret).visibility === 'hidden';",
            deck_selector,
        )
    )


def _click_deck_header(browser: WebDriver, header_selector: str) -> None:
    # A real pointer click can't reach the header (pointer-events:none on the
    # locked state), so fire the click directly to prove the JS guard — not only
    # the CSS — keeps the deck collapsed when no UTub is selected.
    browser.execute_script(
        "document.querySelector(arguments[0]).click();", header_selector
    )


def test_member_and_tag_decks_locked_when_no_utub_selected(
    browser: WebDriver,
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
    login_user_to_home_page(app, browser, user_id=1)

    WebDriverWait(browser, 10).until(
        lambda driver: _deck_locked(driver, HPL.MEMBER_DECK)
    )
    assert _deck_locked(browser, HPL.MEMBER_DECK)
    assert _deck_locked(browser, HPL.TAG_DECK)
    assert _caret_hidden(browser, HPL.MEMBER_DECK)
    assert _caret_hidden(browser, HPL.TAG_DECK)


def test_member_and_tag_decks_not_expandable_when_no_utub_selected(
    browser: WebDriver,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the home page is loaded with no UTub selected (Member/Tag decks locked)
    WHEN the user attempts to expand a locked Member/Tag deck via its header
    THEN the deck stays minimized
    """
    app = provide_app
    login_user_to_home_page(app, browser, user_id=1)

    WebDriverWait(browser, 10).until(
        lambda driver: _deck_locked(driver, HPL.MEMBER_DECK)
    )

    _click_deck_header(browser, HPL.HEADER_AND_CARET_MEMBER_DECK)
    _click_deck_header(browser, HPL.HEADER_AND_CARET_TAG_DECK)

    assert _deck_minimized(browser, HPL.MEMBER_DECK)
    assert _deck_minimized(browser, HPL.TAG_DECK)


def test_member_and_tag_decks_unlocked_when_utub_selected(
    browser: WebDriver,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the home page is loaded with no UTub selected (Member/Tag decks locked)
    WHEN the user selects a UTub
    THEN the lock is removed so the decks become expandable again
    """
    app = provide_app
    login_user_to_home_page(app, browser, user_id=1)

    WebDriverWait(browser, 10).until(
        lambda driver: _deck_locked(driver, HPL.MEMBER_DECK)
    )

    wait_then_click_element(browser, HPL.SELECTORS_UTUB, time=3)

    WebDriverWait(browser, 10).until(
        lambda driver: not _deck_locked(driver, HPL.MEMBER_DECK)
    )
    assert not _deck_locked(browser, HPL.MEMBER_DECK)
    assert not _deck_locked(browser, HPL.TAG_DECK)


def test_member_and_tag_decks_minimized_after_deleting_utub(
    browser: WebDriver,
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
        app, browser, user_id_for_test, utub_user_created.name
    )

    # With the UTub selected, the Member/Tag decks are expanded
    WebDriverWait(browser, 10).until(
        lambda driver: not _deck_minimized(driver, HPL.MEMBER_DECK)
    )

    delete_utub_as_creator(browser, utub_user_created)

    # After deleting, no UTub is selected, so the decks minimize again
    WebDriverWait(browser, 10).until(
        lambda driver: _deck_minimized(driver, HPL.MEMBER_DECK)
    )
    assert _deck_minimized(browser, HPL.MEMBER_DECK)
    assert _deck_minimized(browser, HPL.TAG_DECK)
