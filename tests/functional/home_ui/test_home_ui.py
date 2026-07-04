from __future__ import annotations

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.cli.mock_constants import USERNAME_BASE
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import (
    assert_login,
    assert_no_utub_selected,
    assert_not_visible_css_selector,
    assert_utub_icon,
    assert_utub_selected,
)
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    click_on_navbar,
    current_base_url,
    login_user_to_home_page,
    select_utub_by_id,
    wait_for_modal_ready,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_utub_name_appears,
)

pytestmark = pytest.mark.home_ui


def test_logout(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a user's ability to logout.

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the navbar hamburger dropdown and clicks logout
    THEN ensure the U4I Splash page is displayed
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    click_on_navbar(page=page)
    logout_btn = wait_then_get_element(page=page, css_selector=HPL.BUTTON_LOGOUT)
    logout_btn.click()

    expect(page.locator(SPL.WELCOME_TEXT).first).to_have_text(IDENTIFIERS.SPLASH_PAGE)

    login_btn = page.locator(SPL.NAVBAR_LOGIN).first
    expect(login_btn).to_be_visible()


def test_navbar_hamburger_desktop_regular_member(
    page: Page, create_test_users, provide_app: Flask
):
    """
    Tests the desktop navbar hamburger dropdown for a non-admin member.

    GIVEN a logged-in non-admin user on the desktop home page
    WHEN they open the always-visible navbar hamburger dropdown
    THEN the username is shown inline on the bar, the dropdown contains
        Logout, and no Admin · Metrics entry is present
    """
    app = provide_app
    # User 1 is seeded as the admin; user 2 is a regular member.
    user_id = 2
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    # Username sits inline on the desktop bar (not in the dropdown).
    inline_username = wait_then_get_element(
        page=page, css_selector=HPL.LOGGED_IN_USERNAME_DESKTOP
    )
    expect(inline_username).to_have_text("Logged in as " + USERNAME_BASE + "2")

    click_on_navbar(page=page)

    # The dropdown-copy username is suppressed on desktop by the
    # #NavbarDropdownsHome .nav-item.user { display:none } rule at >=992px.
    assert_not_visible_css_selector(page=page, css_selector=HPL.LOGGED_IN_USERNAME_READ)

    wait_then_get_element(page=page, css_selector=HPL.NAVBAR_LOGOUT)

    # On desktop the dropdown is a compact panel anchored under the hamburger,
    # not a full-width overlay (the full-bleed layout is mobile-only). Guard the
    # >=992px width constraint so a regression to full-width is caught.
    dropdown = page.locator(HPL.NAVBAR_DROPDOWN).first
    expect(dropdown).to_be_visible()
    dropdown_box = dropdown.bounding_box()
    assert dropdown_box is not None
    viewport_width = page.evaluate("() => window.innerWidth")
    assert dropdown_box["width"] < viewport_width / 2

    # A non-admin never renders the Admin · Metrics entry.
    assert page.locator(HPL.NAVBAR_ADMIN_METRICS).count() == 0


def test_navbar_hamburger_desktop_admin_member(
    page: Page, create_test_users, provide_app: Flask
):
    """
    Tests the desktop navbar hamburger dropdown for an admin member.

    GIVEN a logged-in ADMIN user on the desktop home page
    WHEN they open the always-visible navbar hamburger dropdown
    THEN the dropdown contains both Admin · Metrics and Logout
    """
    app = provide_app
    # User 1 is seeded with the ADMIN role.
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    click_on_navbar(page=page)

    wait_then_get_element(page=page, css_selector=HPL.NAVBAR_ADMIN_METRICS)
    wait_then_get_element(page=page, css_selector=HPL.NAVBAR_LOGOUT)


def _navbar_item_border_top_width(page: Page, locator: str) -> str:
    element = wait_then_get_element(page=page, css_selector=locator)
    return element.evaluate(
        "element => window.getComputedStyle(element).borderTopWidth"
    )


def test_navbar_dropdown_dividers_non_admin(
    page: Page, create_test_users, provide_app: Flask
):
    """
    Guards the desktop dropdown dividers for a non-admin member (issue #634).

    GIVEN a logged-in non-admin user on the desktop home page
    WHEN they open the navbar hamburger dropdown
    THEN Settings shows no top border (no stray line under the green accent)
        and Logout shows a top divider between Settings and Logout
    """
    app = provide_app
    # User 1 is seeded as the admin; user 2 is a regular member.
    user_id = 2
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    click_on_navbar(page=page)

    assert _navbar_item_border_top_width(page, HPL.NAVBAR_USER_SETTINGS) == "0px"
    assert _navbar_item_border_top_width(page, HPL.NAVBAR_LOGOUT) == "1px"


def test_navbar_dropdown_dividers_admin(
    page: Page, create_test_users, provide_app: Flask
):
    """
    Guards the desktop dropdown dividers for an admin member (issue #634).

    GIVEN a logged-in ADMIN user on the desktop home page
    WHEN they open the navbar hamburger dropdown
    THEN Admin · Metrics (the first item) shows no top border, while Settings
        and Logout each show a top divider so all three read as separate items
    """
    app = provide_app
    # User 1 is seeded with the ADMIN role.
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    click_on_navbar(page=page)

    assert _navbar_item_border_top_width(page, HPL.NAVBAR_ADMIN_METRICS) == "0px"
    assert _navbar_item_border_top_width(page, HPL.NAVBAR_USER_SETTINGS) == "1px"
    assert _navbar_item_border_top_width(page, HPL.NAVBAR_LOGOUT) == "1px"


def test_refresh_logo(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests a user's ability to refresh the U4I Home page by clicking the upper LHS logo.

    GIVEN a fresh load of the U4I Home page, and any item selected
    WHEN user clicks upper LHS logo
    THEN ensure the Home page is re-displayed with nothing selected
    """
    app = provide_app
    user_id = 1
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=UTS.TEST_UTUB_NAME_1
    )

    wait_then_click_element(page=page, css_selector=HPL.U4I_LOGO)

    assert_login(page=page)

    assert page.locator(HPL.SELECTOR_SELECTED_UTUB).count() == 0


def test_back_and_forward_history(page: Page, create_test_tags, provide_app: Flask):
    """
    GIVEN a set of UTubs with URLs, member, and tags within that UTub
    WHEN the user selects each UTub 1 by 1, then uses browser back and then forward history
    THEN verify that each UTub is shown in the order it was clicked
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    with app.app_context():
        utub_members_with_user: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == user_id
        ).all()
        utub_ids: list[int] = [
            utub_member.utub_id for utub_member in utub_members_with_user
        ]

    for utub_id in utub_ids:
        select_utub_by_id(page=page, utub_id=utub_id)

    # Go backwards
    for idx in range(len(utub_ids)):
        utub_idx = len(utub_ids) - idx - 1
        utub_id = utub_ids[utub_idx]

        assert_utub_selected(page=page, app=app, utub_id=utub_id)
        assert_utub_icon(page=page, app=app, user_id=user_id, utub_id=utub_id)

        page.go_back()

    assert_no_utub_selected(page=page)

    # Go forwards
    for utub_id in utub_ids:
        page.go_forward()

        assert_utub_selected(page=page, app=app, utub_id=utub_id)
        assert_utub_icon(page=page, app=app, user_id=user_id, utub_id=utub_id)


def test_back_and_forward_history_with_one_utub_deleted(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a set of UTubs with URLs, member, and tags within that UTub
    WHEN the user selects each UTub 1 by 1, then deletes a UTub, then uses the browser back and forward history
    THEN verify that each UTub is shown in the order it was clicked, and the deleted
        UTub shows no UTub selected
    """
    app = provide_app
    user_id = 3
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    with app.app_context():
        utub_members_with_user: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == user_id
        ).all()
        utub_ids: list[int] = [
            utub_member.utub_id for utub_member in utub_members_with_user
        ]
        utub_user_created: Utubs = Utubs.query.filter(
            Utubs.utub_creator == user_id
        ).first()
        utub_id_to_delete = utub_user_created.id

    # Sort the UTubIDs so the 3rd UTub (the one this user created) is right in the middle
    utub_ids.sort()
    for utub_id in utub_ids:
        select_utub_by_id(page=page, utub_id=utub_id)

    select_utub_by_id(page=page, utub_id=utub_id_to_delete)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # Wait for DELETE request
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    css_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_id_to_delete}"]'
    wait_for_selector_to_be_removed(page=page, css_selector=css_selector)

    assert_no_utub_selected(page=page)

    # Start at the end of the selected UTubs again
    utub_ids.append(utub_id_to_delete)

    # Go backwards
    for idx in range(len(utub_ids)):
        page.go_back()
        utub_idx = -1 - idx
        utub_id = utub_ids[utub_idx]

        if utub_id == utub_id_to_delete:
            assert_no_utub_selected(page=page)
            continue

        with app.app_context():
            utub: Utubs = Utubs.query.get(utub_id)
            wait_until_utub_name_appears(page=page, utub_name=utub.name)

        assert_utub_selected(page=page, app=app, utub_id=utub_id)
        assert_utub_icon(page=page, app=app, user_id=user_id, utub_id=utub_id)

    # Go back to the home page when no UTubs were selected
    page.go_back()
    assert_no_utub_selected(page=page)

    # Go forwards
    for utub_id in utub_ids:
        page.go_forward()

        if utub_id == utub_id_to_delete:
            assert_no_utub_selected(page=page)
            continue

        assert_utub_selected(page=page, app=app, utub_id=utub_id)
        assert_utub_icon(page=page, app=app, user_id=user_id, utub_id=utub_id)


def test_back_and_forward_history_with_leaving_one_utub(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a set of UTubs with URLs, member, and tags within that UTub
    WHEN the user selects each UTub 1 by 1, then removes themself from UTub, then uses the browser back and forward history
    THEN verify that each UTub is shown in the order it was clicked, and the UTub they left shows no UTub selected
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    with app.app_context():
        utub_members_with_user: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == user_id
        ).all()
        utub_ids: list[int] = [
            utub_member.utub_id for utub_member in utub_members_with_user
        ]
    utub_id_to_delete = 3
    assert utub_id_to_delete in utub_ids

    # Sort the UTubIDs so the 3rd UTub (the one this user is a member of) is right in the middle
    utub_ids.sort()
    for utub_id in utub_ids:
        select_utub_by_id(page=page, utub_id=utub_id)

    select_utub_by_id(page=page, utub_id=utub_id_to_delete)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    expect(page.locator(HPL.BODY_MODAL)).to_be_visible()

    utub_css_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id_to_delete}']"

    # Wait for DELETE request
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_selector_to_be_removed(page=page, css_selector=utub_css_selector)

    assert_no_utub_selected(page=page)

    # Start at the end of the selected UTubs again
    utub_ids.append(utub_id_to_delete)

    # Go backwards
    for idx in range(len(utub_ids)):
        page.go_back()
        utub_idx = -1 - idx
        utub_id = utub_ids[utub_idx]

        if utub_id == utub_id_to_delete:
            assert_no_utub_selected(page=page)
            continue

        with app.app_context():
            utub: Utubs = Utubs.query.get(utub_id)
            wait_until_utub_name_appears(page=page, utub_name=utub.name)

        assert_utub_selected(page=page, app=app, utub_id=utub_id)
        assert_utub_icon(page=page, app=app, user_id=user_id, utub_id=utub_id)

    # Go back to the home page when no UTubs were selected
    page.go_back()
    assert_no_utub_selected(page=page)

    # Go forwards
    for utub_id in utub_ids:
        page.go_forward()

        if utub_id == utub_id_to_delete:
            assert_no_utub_selected(page=page)
            continue

        assert_utub_selected(page=page, app=app, utub_id=utub_id)
        assert_utub_icon(page=page, app=app, user_id=user_id, utub_id=utub_id)


def test_access_utub_id_via_url_logged_in(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a set of UTubs with URLs, member, and tags within that UTub, and the user has previously logged in
        and therefore has a session cookie
    WHEN the user accesses the URL with the given query parameter UTubID=X, where X is a given UTubID
    THEN verify that the UTub with the given UTubID is selected when the browser is shown
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    with app.app_context():
        utub_not_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != user_id
        ).first()
        utub_id_to_select = utub_not_creator_of.id
        utub_name_to_select = utub_not_creator_of.name

    utub_url = f"{page.url}?UTubID={utub_id_to_select}"
    page.goto(utub_url)
    wait_until_utub_name_appears(page=page, utub_name=utub_name_to_select)
    assert_utub_selected(page=page, app=app, utub_id=utub_id_to_select)


def test_access_utub_id_via_url_logged_out(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a set of UTubs with URLs, member, and tags within that UTub, and the user has no session cookie
    WHEN the user accesses the URL with the given query parameter UTubID=X, where X is a given UTubID
    THEN verify that the UTub with the given UTubID is selected when the browser is shown after logging in
    """
    app = provide_app
    user_id = 1
    with app.app_context():
        utub_not_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != user_id
        ).first()
        utub_id_to_select = utub_not_creator_of.id
        utub_name_to_select = utub_not_creator_of.name

    base_url = current_base_url(page=page)
    utub_url = f"{base_url}/home?UTubID={utub_id_to_select}"
    page.goto(utub_url)

    # Log in via the UI form (no session cookie was pre-set)
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_LOGIN)
    wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)
    username_input = wait_then_get_element(
        page=page, css_selector=SPL.LOGIN_INPUT_USERNAME
    )
    clear_then_send_keys(locator=username_input, input_text=UTS.TEST_USERNAME_1)
    password_input = wait_then_get_element(
        page=page, css_selector=SPL.LOGIN_INPUT_PASSWORD
    )
    clear_then_send_keys(locator=password_input, input_text=UTS.TEST_PASSWORD_1)
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_SUBMIT)

    wait_until_utub_name_appears(page=page, utub_name=utub_name_to_select)
    assert_utub_selected(page=page, app=app, utub_id=utub_id_to_select)


# TODO: test async addition of component by 2nd test user in a shared UTub, then confirm 1st test user can see the update upon refresh
