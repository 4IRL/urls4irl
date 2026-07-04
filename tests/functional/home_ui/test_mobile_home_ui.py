from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.models.utubs import Utubs
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    click_on_navbar,
    login_user_to_home_page,
    wait_for_class_to_be_removed,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.mobile_ui


def test_navbar_on_utub_panel_utub_unselected_mobile(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user on home page on mobile

    GIVEN a user logs in or registers
    WHEN the user clicks on the navbar dropdown
    THEN ensure the correct navbar options are shown
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    click_on_navbar(page=page)

    assert_visible_css_selector(page=page, css_selector=HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_LOGOUT)

    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_URLS_DECK)
    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)
    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_TAGS_DECK)


def test_navbar_after_utub_deleted_mobile(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user deletes UTub

    GIVEN a user logs in or registers
    WHEN the user deletes a UTub
    THEN ensure the correct navbar options are shown
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )

    # Travel back to UTub panel from URLs panel
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)

    # Delete the UTub
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    expect(page.locator(HPL.SELECTOR_SELECTED_UTUB).first).to_be_attached()

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_for_selector_to_be_removed(page=page, css_selector=HPL.SELECTOR_SELECTED_UTUB)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(page=page)
    assert_visible_css_selector(page=page, css_selector=HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_LOGOUT)

    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_URLS_DECK)
    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)
    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_TAGS_DECK)


def test_navbar_after_select_utub_mobile(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user selects UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to URLs deck by selecting a UTub
    THEN ensure the correct navbar options are shown
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )

    # Click on navbar and verify proper menus are shown
    click_on_navbar(page=page)
    assert_visible_css_selector(page=page, css_selector=HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_LOGOUT)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_TAGS_DECK)

    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_URLS_DECK)


def test_navbar_after_reselect_utub_mobile(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user re-selects UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to URLs deck by selecting a UTub that was already selected
    THEN ensure the correct navbar options are shown
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )

    # Travel to utubs
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)

    wait_then_click_element(page=page, css_selector=HPL.SELECTOR_SELECTED_UTUB)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(page=page)
    assert_visible_css_selector(page=page, css_selector=HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_LOGOUT)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_TAGS_DECK)

    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_URLS_DECK)


def test_navbar_after_open_tag_deck_mobile(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user opens Tags deck after selecting UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to tags deck via navbar navigation
    THEN ensure the correct navbar options are shown
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )

    # Open the tag sheet via the navbar Tags button. #toTags collapses the
    # hamburger (so its Bootstrap state stays clean while the sheet traps focus).
    # The re-open click below is ignored by Bootstrap if the hide transition is
    # still running, so gate on the hide FULLY completing: `show` is removed at
    # the start of the transition and `collapsing` at its end. Waiting for
    # `collapsing` alone can return before it is even added (mid-hide); waiting
    # for `show` first guarantees `collapsing` is present, then waiting for
    # `collapsing` to clear confirms the collapse settled — deterministic, not a
    # padded timeout.
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_TAGS_DECK)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="show"
    )
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )

    # The sheet overlays the URL deck — both are visible simultaneously
    wait_until_visible_css_selector(page=page, css_selector=HPL.TAG_SHEET)
    assert_visible_css_selector(page=page, css_selector=HPL.TAG_SHEET)
    assert_visible_css_selector(page=page, css_selector=HPL.URL_DECK)

    # Click on navbar and verify proper menus are still shown (URL-showing state).
    # The tag sheet overlays the URL deck without changing the underlying deck
    # state, so the navbar stays in its URL-deck configuration: the "go to URLs"
    # button stays hidden (you are already on URLs), matching the navbar state set
    # by setMobileUIWhenUTubSelectedOrURLNavSelected().
    click_on_navbar(page=page)
    assert_visible_css_selector(page=page, css_selector=HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_LOGOUT)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_TAGS_DECK)

    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_URLS_DECK)


def test_nav_on_url_panel_after_open_member_deck_mobile(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user opens Members deck after selecting UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to member deck via navbar navigation
    THEN ensure the correct navbar options are shown
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )

    # Travel to members
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.MEMBERS)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(page=page)
    assert_visible_css_selector(page=page, css_selector=HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_LOGOUT)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_TAGS_DECK)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_URLS_DECK)

    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)


def test_nav_on_url_panel_after_selected_utub_on_utub_deck_mobile(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    Tests visibility of navbar when user returns to UTub deck after selecting UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user returns to UTub deck via navbar navigation
    THEN ensure the correct navbar options are shown
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )

    # Travel to utub deck
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(page=page)
    assert_visible_css_selector(page=page, css_selector=HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_LOGOUT)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_URLS_DECK)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_TAGS_DECK)

    assert_not_visible_css_selector(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)


@pytest.mark.parametrize(
    "selected_navbar_option,visible_deck",
    [
        (HPL.NAVBAR_MEMBER_DECK, Decks.MEMBERS),
        (HPL.NAVBAR_UTUB_DECK, Decks.UTUBS),
    ],
)
def test_nav_from_url_deck_to_other_deck_mobile(
    page_mobile_portrait: Page,
    create_test_tags,
    provide_app: Flask,
    selected_navbar_option: str,
    visible_deck: Decks,
):
    """
    Tests visibility of navbar when user travels from url deck

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user navigates using navbar
    THEN ensure the correct navbar options are shown
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )

    # Travel to url deck
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=selected_navbar_option)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=visible_deck)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(page=page)
    for navbar_option in HPL.MOBILE_NAVBAR_OPTIONS:
        if navbar_option == selected_navbar_option:
            assert_not_visible_css_selector(page=page, css_selector=navbar_option)
        else:
            assert_visible_css_selector(page=page, css_selector=navbar_option)


@pytest.mark.parametrize(
    "selected_navbar_option,visible_deck",
    [
        (HPL.NAVBAR_MEMBER_DECK, Decks.MEMBERS),
        (HPL.NAVBAR_URLS_DECK, Decks.URLS),
    ],
)
def test_nav_from_utub_deck_to_other_deck_with_utub_selected_mobile(
    page_mobile_portrait: Page,
    create_test_tags,
    provide_app: Flask,
    selected_navbar_option: str,
    visible_deck: Decks,
):
    """
    Tests visibility of navbar when user travels after returning to UTub deck after selecting UTub

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user returns to UTub deck via navbar navigation
    THEN ensure the correct navbar options are shown
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )

    # Travel to utub deck
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)

    # Travel to other decks
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=selected_navbar_option)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=visible_deck)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(page=page)
    for navbar_option in HPL.MOBILE_NAVBAR_OPTIONS:
        if navbar_option == selected_navbar_option:
            assert_not_visible_css_selector(page=page, css_selector=navbar_option)
        else:
            assert_visible_css_selector(page=page, css_selector=navbar_option)


# The URL deck stays current while the tag sheet overlays it, so the navbar never
# offers a "go to URLs" option from this state — only #toUTubs and #toMembers are
# reachable. (NAVBAR_URLS_DECK is therefore intentionally excluded here.)
@pytest.mark.parametrize(
    "selected_navbar_option,visible_deck",
    [
        (HPL.NAVBAR_UTUB_DECK, Decks.UTUBS),
        (HPL.NAVBAR_MEMBER_DECK, Decks.MEMBERS),
    ],
)
def test_nav_from_tag_deck_to_other_deck_mobile(
    page_mobile_portrait: Page,
    create_test_tags,
    provide_app: Flask,
    selected_navbar_option: str,
    visible_deck: Decks,
):
    """
    Tests visibility of navbar when user travels from tag deck

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to tag deck and then navigates using navbar
    THEN ensure the correct navbar options are shown
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )

    # Open the tag sheet over the URL deck
    wait_then_click_element(page=page, css_selector=HPL.TAG_SHEET_HANDLE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.TAG_SHEET)

    # Travel to other decks
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=selected_navbar_option)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=visible_deck)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(page=page)
    for navbar_option in HPL.MOBILE_NAVBAR_OPTIONS:
        if navbar_option == selected_navbar_option:
            assert_not_visible_css_selector(page=page, css_selector=navbar_option)
        else:
            assert_visible_css_selector(page=page, css_selector=navbar_option)


@pytest.mark.parametrize(
    "selected_navbar_option,visible_deck",
    [
        (HPL.NAVBAR_UTUB_DECK, Decks.UTUBS),
        (HPL.NAVBAR_URLS_DECK, Decks.URLS),
    ],
)
def test_nav_from_member_deck_to_other_deck_mobile(
    page_mobile_portrait: Page,
    create_test_tags,
    provide_app: Flask,
    selected_navbar_option: str,
    visible_deck: Decks,
):
    """
    Tests visibility of navbar when user travels from members deck

    GIVEN a logged in user on URLs deck on mobile
    WHEN the user travels to tag deck and then navigates using navbar
    THEN ensure the correct navbar options are shown
    """
    page = page_mobile_portrait
    app = provide_app
    user_id = 1
    utub: Utubs = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id, utub_id=utub.id
    )

    # Travel to tags deck
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.MEMBERS)

    # Travel to other decks
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=selected_navbar_option)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=visible_deck)

    # Click on navbar and verify proper menus are shown
    click_on_navbar(page=page)
    for navbar_option in HPL.MOBILE_NAVBAR_OPTIONS:
        if navbar_option == selected_navbar_option:
            assert_not_visible_css_selector(page=page, css_selector=navbar_option)
        else:
            assert_visible_css_selector(page=page, css_selector=navbar_option)


# TODO: Test back button brings user to previous panel was focused on (hides all other)
