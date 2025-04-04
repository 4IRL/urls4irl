from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from src.models.utubs import Utubs
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.utils_for_test import (
    Decks,
    assert_not_visible_css_selector,
    assert_visible_css_selector,
    click_on_navbar,
    get_utub_this_user_created,
    login_user_and_select_utub_by_utubid_mobile,
    login_user_to_home_page,
    verify_panel_visibility_mobile,
    wait_for_class_to_be_removed,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_until_visible_css_selector,
)


def test_navbar_on_utub_panel_utub_unselected_mobile(
    browser_mobile_portrait: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user on home page on mobile

    GIVEN a user logs in or registers
    WHEN the user clicks on the navbar dropdown
    THEN ensure the correct navbar options are shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    login_user_to_home_page(app, browser, USER_ID)

    click_on_navbar(browser)

    assert_visible_css_selector(browser, HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(browser, HPL.NAVBAR_LOGOUT)

    assert_not_visible_css_selector(browser, HPL.NAVBAR_UTUB_DECK)
    assert_not_visible_css_selector(browser, HPL.NAVBAR_URLS_DECK)
    assert_not_visible_css_selector(browser, HPL.NAVBAR_MEMBER_DECK)
    assert_not_visible_css_selector(browser, HPL.NAVBAR_TAGS_DECK)


def test_navbar_after_utub_deleted_mobile(
    browser_mobile_portrait: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user deletes UTub

    GIVEN a user logs in or registers
    WHEN the user deletes a UTub
    THEN ensure the correct navbar options are shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    utub: Utubs = get_utub_this_user_created(app, USER_ID)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=USER_ID
    )

    # Travel back to UTub panel from URLs panel
    click_on_navbar(browser)
    wait_then_click_element(browser, HPL.NAVBAR_UTUB_DECK, time=10)
    verify_panel_visibility_mobile(browser=browser, visible_deck=Decks.UTUBS)

    # Delete the UTub
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DELETE, time=10)
    wait_until_visible_css_selector(browser, HPL.BUTTON_MODAL_SUBMIT, timeout=10)
    utub_selector = browser.find_element(By.CSS_SELECTOR, HPL.SELECTOR_SELECTED_UTUB)
    assert utub_selector is not None

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT, time=10)
    wait_for_element_to_be_removed(browser, utub_selector, timeout=10)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(browser)
    assert_visible_css_selector(browser, HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(browser, HPL.NAVBAR_LOGOUT)

    assert_not_visible_css_selector(browser, HPL.NAVBAR_UTUB_DECK)
    assert_not_visible_css_selector(browser, HPL.NAVBAR_URLS_DECK)
    assert_not_visible_css_selector(browser, HPL.NAVBAR_MEMBER_DECK)
    assert_not_visible_css_selector(browser, HPL.NAVBAR_TAGS_DECK)


def test_navbar_after_select_utub_mobile(
    browser_mobile_portrait: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user selects UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to URLs deck by selecting a UTub
    THEN ensure the correct navbar options are shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    utub: Utubs = get_utub_this_user_created(app, USER_ID)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=USER_ID
    )

    # Click on navbar and verify proper menus are shown
    click_on_navbar(browser)
    assert_visible_css_selector(browser, HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(browser, HPL.NAVBAR_LOGOUT)
    assert_visible_css_selector(browser, HPL.NAVBAR_UTUB_DECK)
    assert_visible_css_selector(browser, HPL.NAVBAR_MEMBER_DECK)
    assert_visible_css_selector(browser, HPL.NAVBAR_TAGS_DECK)

    assert_not_visible_css_selector(browser, HPL.NAVBAR_URLS_DECK)


def test_navbar_after_reselect_utub_mobile(
    browser_mobile_portrait: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user re-selects UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to URLs deck by selecting a UTub that was already selected
    THEN ensure the correct navbar options are shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    utub: Utubs = get_utub_this_user_created(app, USER_ID)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=USER_ID
    )

    # Travel to utubs
    click_on_navbar(browser)
    wait_then_click_element(browser, HPL.NAVBAR_UTUB_DECK)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    verify_panel_visibility_mobile(browser, visible_deck=Decks.UTUBS)

    wait_then_click_element(browser, HPL.SELECTOR_SELECTED_UTUB)
    verify_panel_visibility_mobile(browser, visible_deck=Decks.URLS)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(browser)
    assert_visible_css_selector(browser, HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(browser, HPL.NAVBAR_LOGOUT)
    assert_visible_css_selector(browser, HPL.NAVBAR_UTUB_DECK)
    assert_visible_css_selector(browser, HPL.NAVBAR_MEMBER_DECK)
    assert_visible_css_selector(browser, HPL.NAVBAR_TAGS_DECK)

    assert_not_visible_css_selector(browser, HPL.NAVBAR_URLS_DECK)


def test_navbar_after_open_tag_deck_mobile(
    browser_mobile_portrait: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user opens Tags deck after selecting UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to tags deck via navbar navigation
    THEN ensure the correct navbar options are shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    utub: Utubs = get_utub_this_user_created(app, USER_ID)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=USER_ID
    )

    # Travel to tags
    click_on_navbar(browser)
    wait_then_click_element(browser, HPL.NAVBAR_TAGS_DECK)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    verify_panel_visibility_mobile(browser, visible_deck=Decks.TAGS)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(browser)
    assert_visible_css_selector(browser, HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(browser, HPL.NAVBAR_LOGOUT)
    assert_visible_css_selector(browser, HPL.NAVBAR_UTUB_DECK)
    assert_visible_css_selector(browser, HPL.NAVBAR_MEMBER_DECK)
    assert_visible_css_selector(browser, HPL.NAVBAR_URLS_DECK)

    assert_not_visible_css_selector(browser, HPL.NAVBAR_TAGS_DECK)


def test_nav_on_url_panel_after_open_member_deck_mobile(
    browser_mobile_portrait: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user opens Members deck after selecting UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to member deck via navbar navigation
    THEN ensure the correct navbar options are shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    utub: Utubs = get_utub_this_user_created(app, USER_ID)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=USER_ID
    )

    # Travel to members
    click_on_navbar(browser)
    wait_then_click_element(browser, HPL.NAVBAR_MEMBER_DECK)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    verify_panel_visibility_mobile(browser, visible_deck=Decks.MEMBERS)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(browser)
    assert_visible_css_selector(browser, HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(browser, HPL.NAVBAR_LOGOUT)
    assert_visible_css_selector(browser, HPL.NAVBAR_UTUB_DECK)
    assert_visible_css_selector(browser, HPL.NAVBAR_TAGS_DECK)
    assert_visible_css_selector(browser, HPL.NAVBAR_URLS_DECK)

    assert_not_visible_css_selector(browser, HPL.NAVBAR_MEMBER_DECK)


def test_nav_on_url_panel_after_selected_utub_on_utub_deck_mobile(
    browser_mobile_portrait: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user returns to UTub deck after selecting UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user returns to UTub deck via navbar navigation
    THEN ensure the correct navbar options are shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    utub: Utubs = get_utub_this_user_created(app, USER_ID)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=USER_ID
    )

    # Travel to utub deck
    click_on_navbar(browser)
    wait_then_click_element(browser, HPL.NAVBAR_UTUB_DECK)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    verify_panel_visibility_mobile(browser, visible_deck=Decks.UTUBS)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(browser)
    assert_visible_css_selector(browser, HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(browser, HPL.NAVBAR_LOGOUT)
    assert_visible_css_selector(browser, HPL.NAVBAR_URLS_DECK)
    assert_visible_css_selector(browser, HPL.NAVBAR_MEMBER_DECK)
    assert_visible_css_selector(browser, HPL.NAVBAR_TAGS_DECK)

    assert_not_visible_css_selector(browser, HPL.NAVBAR_UTUB_DECK)


@pytest.mark.parametrize(
    "selected_navbar_option,visible_deck",
    [
        (HPL.NAVBAR_TAGS_DECK, Decks.TAGS),
        (HPL.NAVBAR_MEMBER_DECK, Decks.MEMBERS),
        (HPL.NAVBAR_UTUB_DECK, Decks.UTUBS),
    ],
)
def test_nav_from_url_deck_to_other_deck_mobile(
    browser_mobile_portrait: WebDriver,
    create_test_tags,
    provide_app: Flask,
    selected_navbar_option,
    visible_deck,
):
    """
    Tests visibility of navbar when user travels from url deck

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user navigates using navbar
    THEN ensure the correct navbar options are shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    utub: Utubs = get_utub_this_user_created(app, USER_ID)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=USER_ID
    )

    # Travel to url deck
    click_on_navbar(browser)
    wait_then_click_element(browser, selected_navbar_option)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    verify_panel_visibility_mobile(browser, visible_deck=visible_deck)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(browser)
    for navbar_option in HPL.MOBILE_NAVBAR_OPTIONS:
        if navbar_option == selected_navbar_option:
            assert_not_visible_css_selector(browser, navbar_option)
        else:
            assert_visible_css_selector(browser, navbar_option)


@pytest.mark.parametrize(
    "selected_navbar_option,visible_deck",
    [
        (HPL.NAVBAR_TAGS_DECK, Decks.TAGS),
        (HPL.NAVBAR_MEMBER_DECK, Decks.MEMBERS),
        (HPL.NAVBAR_URLS_DECK, Decks.URLS),
    ],
)
def test_nav_from_utub_deck_to_other_deck_with_utub_selected_mobile(
    browser_mobile_portrait: WebDriver,
    create_test_tags,
    provide_app: Flask,
    selected_navbar_option,
    visible_deck,
):
    """
    Tests visibility of navbar when user travels after returning to UTub deck after selecting UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user returns to UTub deck via navbar navigation
    THEN ensure the correct navbar options are shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    utub: Utubs = get_utub_this_user_created(app, USER_ID)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=USER_ID
    )

    # Travel to utub deck
    click_on_navbar(browser)
    wait_then_click_element(browser, HPL.NAVBAR_UTUB_DECK)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    verify_panel_visibility_mobile(browser, visible_deck=Decks.UTUBS)

    # Travel to other decks
    click_on_navbar(browser)
    wait_then_click_element(browser, selected_navbar_option)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    verify_panel_visibility_mobile(browser, visible_deck=visible_deck)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(browser)
    for navbar_option in HPL.MOBILE_NAVBAR_OPTIONS:
        if navbar_option == selected_navbar_option:
            assert_not_visible_css_selector(browser, navbar_option)
        else:
            assert_visible_css_selector(browser, navbar_option)


@pytest.mark.parametrize(
    "selected_navbar_option,visible_deck",
    [
        (HPL.NAVBAR_UTUB_DECK, Decks.UTUBS),
        (HPL.NAVBAR_MEMBER_DECK, Decks.MEMBERS),
        (HPL.NAVBAR_URLS_DECK, Decks.URLS),
    ],
)
def test_nav_from_tag_deck_to_other_deck_mobile(
    browser_mobile_portrait: WebDriver,
    create_test_tags,
    provide_app: Flask,
    selected_navbar_option,
    visible_deck,
):
    """
    Tests visibility of navbar when user travels from tag deck

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to tag deck and then navigates using navbar
    THEN ensure the correct navbar options are shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    utub: Utubs = get_utub_this_user_created(app, USER_ID)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=USER_ID
    )

    # Travel to tags deck
    click_on_navbar(browser)
    wait_then_click_element(browser, HPL.NAVBAR_TAGS_DECK)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    verify_panel_visibility_mobile(browser, visible_deck=Decks.TAGS)

    # Travel to other decks
    click_on_navbar(browser)
    wait_then_click_element(browser, selected_navbar_option)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    verify_panel_visibility_mobile(browser, visible_deck=visible_deck)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(browser)
    for navbar_option in HPL.MOBILE_NAVBAR_OPTIONS:
        if navbar_option == selected_navbar_option:
            assert_not_visible_css_selector(browser, navbar_option)
        else:
            assert_visible_css_selector(browser, navbar_option)


@pytest.mark.parametrize(
    "selected_navbar_option,visible_deck",
    [
        (HPL.NAVBAR_UTUB_DECK, Decks.UTUBS),
        (HPL.NAVBAR_TAGS_DECK, Decks.TAGS),
        (HPL.NAVBAR_URLS_DECK, Decks.URLS),
    ],
)
def test_nav_from_member_deck_to_other_deck_mobile(
    browser_mobile_portrait: WebDriver,
    create_test_tags,
    provide_app: Flask,
    selected_navbar_option,
    visible_deck,
):
    """
    Tests visibility of navbar when user travels from members deck

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to tag deck and then navigates using navbar
    THEN ensure the correct navbar options are shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    USER_ID = 1
    utub: Utubs = get_utub_this_user_created(app, USER_ID)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=USER_ID
    )

    # Travel to tags deck
    click_on_navbar(browser)
    wait_then_click_element(browser, HPL.NAVBAR_MEMBER_DECK)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    verify_panel_visibility_mobile(browser, visible_deck=Decks.MEMBERS)

    # Travel to other decks
    click_on_navbar(browser)
    wait_then_click_element(browser, selected_navbar_option)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    verify_panel_visibility_mobile(browser, visible_deck=visible_deck)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(browser)
    for navbar_option in HPL.MOBILE_NAVBAR_OPTIONS:
        if navbar_option == selected_navbar_option:
            assert_not_visible_css_selector(browser, navbar_option)
        else:
            assert_visible_css_selector(browser, navbar_option)


# TODO: Test back button brings user to previous panel was focused on (hides all other)
