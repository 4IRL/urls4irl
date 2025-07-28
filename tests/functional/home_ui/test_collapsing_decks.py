from flask import Flask
import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.assert_utils import (
    assert_login,
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.home_ui.selenium_utils import collapse_deck
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_to_home_page,
)
from tests.functional.selenium_utils import (
    Decks,
    wait_for_animation_to_end_check_height,
    wait_then_click_element,
    wait_then_get_element,
)

pytestmark = pytest.mark.home_ui


@pytest.mark.parametrize(
    "deck_title_selector, collapsed_deck_selector",
    [
        (HPL.HEADER_TAG_DECK, Decks.TAGS),
        (HPL.HEADER_MEMBER_DECK, Decks.MEMBERS),
        (HPL.HEADER_UTUB_DECK, Decks.UTUBS),
    ],
)
def test_single_collapsible_lhs_decks(
    browser: WebDriver,
    create_test_tags,
    provide_app: Flask,
    deck_title_selector,
    collapsed_deck_selector,
):
    """
    Tests a user's ability to collapse one LHS deck.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks any one of the deck headers
    THEN ensure the given deck is collapsed
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app, browser, user_id)
    assert_login(browser)

    deck_header_elem = wait_then_get_element(browser, deck_title_selector, time=3)
    assert deck_header_elem is not None

    wait_then_click_element(browser, deck_title_selector, time=3)

    wait_for_animation_to_end_check_height(browser, collapsed_deck_selector.value)
    assert_not_visible_css_selector(
        browser, f"{collapsed_deck_selector.value} .content"
    )

    for deck in (
        Decks.UTUBS,
        Decks.MEMBERS,
        Decks.TAGS,
    ):
        if deck == collapsed_deck_selector:
            continue
        assert_visible_css_selector(browser, f"{deck.value} .content")


@pytest.mark.parametrize(
    "first_collapsed_header_and_deck, second_collapsed_header_and_deck, open_deck",
    [
        (
            (HPL.HEADER_TAG_DECK, Decks.TAGS),
            (HPL.HEADER_MEMBER_DECK, Decks.MEMBERS),
            Decks.UTUBS,
        ),
        (
            (HPL.HEADER_TAG_DECK, Decks.TAGS),
            (HPL.HEADER_UTUB_DECK, Decks.UTUBS),
            Decks.MEMBERS,
        ),
        (
            (HPL.HEADER_MEMBER_DECK, Decks.MEMBERS),
            (HPL.HEADER_TAG_DECK, Decks.TAGS),
            Decks.UTUBS,
        ),
        (
            (HPL.HEADER_MEMBER_DECK, Decks.MEMBERS),
            (HPL.HEADER_UTUB_DECK, Decks.UTUBS),
            Decks.TAGS,
        ),
        (
            (HPL.HEADER_UTUB_DECK, Decks.UTUBS),
            (HPL.HEADER_MEMBER_DECK, Decks.MEMBERS),
            Decks.TAGS,
        ),
        (
            (HPL.HEADER_UTUB_DECK, Decks.UTUBS),
            (HPL.HEADER_TAG_DECK, Decks.TAGS),
            Decks.MEMBERS,
        ),
    ],
)
def test_double_collapsible_lhs_decks(
    browser: WebDriver,
    create_test_tags,
    provide_app: Flask,
    first_collapsed_header_and_deck,
    second_collapsed_header_and_deck,
    open_deck,
):
    """
    Tests a user's ability to collapse two LHS decks

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks any two of the deck headers
    THEN ensure the given decks are collapsed
    """
    first_collapsed_deck_header, first_collapsed_deck = first_collapsed_header_and_deck
    second_collapsed_deck_header, second_collapsed_deck = (
        second_collapsed_header_and_deck
    )

    app = provide_app
    user_id = 1
    login_user_to_home_page(app, browser, user_id)
    assert_login(browser)

    collapse_deck(browser, first_collapsed_deck_header, first_collapsed_deck)
    collapse_deck(browser, second_collapsed_deck_header, second_collapsed_deck)
    assert_visible_css_selector(browser, f"{open_deck.value} .content")


@pytest.mark.parametrize(
    "first_collapsed_header_and_deck, second_collapsed_header_and_deck, third_collapsed_header_and_deck",
    [
        (
            (HPL.HEADER_TAG_DECK, Decks.TAGS),
            (HPL.HEADER_MEMBER_DECK, Decks.MEMBERS),
            (HPL.HEADER_UTUB_DECK, Decks.UTUBS),
        ),
        (
            (HPL.HEADER_TAG_DECK, Decks.TAGS),
            (HPL.HEADER_UTUB_DECK, Decks.UTUBS),
            (HPL.HEADER_MEMBER_DECK, Decks.MEMBERS),
        ),
        (
            (HPL.HEADER_MEMBER_DECK, Decks.MEMBERS),
            (HPL.HEADER_TAG_DECK, Decks.TAGS),
            (HPL.HEADER_UTUB_DECK, Decks.UTUBS),
        ),
        (
            (HPL.HEADER_MEMBER_DECK, Decks.MEMBERS),
            (HPL.HEADER_UTUB_DECK, Decks.UTUBS),
            (HPL.HEADER_TAG_DECK, Decks.TAGS),
        ),
        (
            (HPL.HEADER_UTUB_DECK, Decks.UTUBS),
            (HPL.HEADER_MEMBER_DECK, Decks.MEMBERS),
            (HPL.HEADER_TAG_DECK, Decks.TAGS),
        ),
        (
            (HPL.HEADER_UTUB_DECK, Decks.UTUBS),
            (HPL.HEADER_TAG_DECK, Decks.TAGS),
            (HPL.HEADER_MEMBER_DECK, Decks.MEMBERS),
        ),
    ],
)
def test_previously_collapsed_deck_shows_after_two_collapsed(
    browser: WebDriver,
    create_test_tags,
    provide_app: Flask,
    first_collapsed_header_and_deck,
    second_collapsed_header_and_deck,
    third_collapsed_header_and_deck,
):
    """
    Tests a user's ability to collapse three LHS decks, but makes sure U4I shows max two decks collapsed.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks all three of the deck headers
    THEN ensure the second deck (previously selected deck) is shown
    """
    first_collapsed_deck_header, first_collapsed_deck = first_collapsed_header_and_deck
    second_collapsed_deck_header, second_collapsed_deck = (
        second_collapsed_header_and_deck
    )
    third_collapsed_deck_header, third_collapsed_deck = third_collapsed_header_and_deck

    app = provide_app
    user_id = 1
    login_user_to_home_page(app, browser, user_id)
    assert_login(browser)

    collapse_deck(browser, first_collapsed_deck_header, first_collapsed_deck)
    collapse_deck(browser, second_collapsed_deck_header, second_collapsed_deck)
    collapse_deck(browser, third_collapsed_deck_header, third_collapsed_deck)
    assert_visible_css_selector(browser, f"{second_collapsed_deck.value} .content")
