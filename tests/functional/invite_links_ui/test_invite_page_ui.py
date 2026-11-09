import re
from typing import NamedTuple
from urllib.parse import quote, unquote, urlencode, urlsplit

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, Response, expect

from backend import db
from backend.cli.mock_constants import EMAIL_SUFFIX
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.invite_links_ui.db_utils import (
    mint_invite_link_in_db,
    set_email_validated_in_db,
    set_utub_description_in_db,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import InvitePageLocators as IPL
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import assert_login_with_username
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    add_cookie_banner_cookie as add_playwright_cookie_banner_cookie,
)
from tests.functional.playwright_utils import (
    current_base_url,
    get_selected_utub_id,
    input_login_fields,
    login_user_to_home_page,
    wait_for_modal_ready,
)
from tests.functional.splash_ui.playwright_utils import (
    fill_register_fields,
    register_user_ui,
)
from tests.functional.urls_ui.playwright_utils import ClipboardMockHelper

pytestmark = pytest.mark.invite_links_ui

MOBILE_VIEWPORT = {"width": 390, "height": 844}
LONG_UNBROKEN_DESCRIPTION = "a" * 200
CREATOR_ID = 1
VISITOR_ID = 2
TAB_PRESS_LIMIT = 20
WIDTH_TOLERANCE_PX = 1


class InviteScenario(NamedTuple):
    utub_id: int
    utub_name: str
    token: str
    url: str


def _seed_invite(
    *, app: Flask, page: Page, revoked: bool = False, description: str | None = None
) -> InviteScenario:
    """A UTub user 1 created plus an invite link for it. Requires
    ``create_test_users`` and ``create_test_utubs`` so user 2 is not a member."""
    utub = get_utub_this_user_created(app, CREATOR_ID)
    if description is not None:
        set_utub_description_in_db(app=app, utub_id=utub.id, description=description)
    token = mint_invite_link_in_db(
        app=app, utub_id=utub.id, created_by=CREATOR_ID, revoked=revoked
    )
    return InviteScenario(
        utub_id=utub.id,
        utub_name=utub.name,
        token=token,
        url=f"{current_base_url(page=page)}/invite/{token}",
    )


def _use_mobile_viewport(*, page: Page) -> None:
    page.set_viewport_size(MOBILE_VIEWPORT)


def _assert_no_horizontal_overflow(*, page: Page) -> None:
    layout = page.evaluate(
        """() => ({
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
        })"""
    )
    assert layout["scrollWidth"] <= layout["clientWidth"], layout


def _assert_description_inside_panel(*, page: Page) -> None:
    description = page.locator(IPL.DESCRIPTION).bounding_box()
    panel = page.locator(IPL.PANEL).bounding_box()
    assert description is not None and panel is not None
    assert description["x"] >= panel["x"] - WIDTH_TOLERANCE_PX
    assert (
        description["x"] + description["width"]
        <= panel["x"] + panel["width"] + WIDTH_TOLERANCE_PX
    )


def _assert_full_width(*, page: Page, css_selector: str) -> None:
    element = page.locator(css_selector).bounding_box()
    container = page.locator(IPL.CTA_ROW).bounding_box()
    assert element is not None and container is not None
    assert abs(element["width"] - container["width"]) <= WIDTH_TOLERANCE_PX


def _log_in_and_open_invite(
    *, app: Flask, page: Page, scenario: InviteScenario
) -> Response | None:
    login_user_to_home_page(app=app, page=page, user_id=VISITOR_ID)
    return page.goto(scenario.url)


def test_anonymous_visitor_sees_state_two_with_next_contract_links(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a live invite link and a visitor who is not logged in
    WHEN the visitor opens the invite page
    THEN it shows the UTub, the Log in and Create account links carrying the
         `next` contract, and the navbar splash item
    """
    scenario = _seed_invite(app=provide_app, page=page)

    response = page.goto(scenario.url)

    assert response is not None
    assert response.status == 200
    expect(page.locator(IPL.HEADING)).to_have_text(scenario.utub_name)
    expect(page.locator(IPL.LINK_LOG_IN)).to_have_attribute(
        "href", f"/?next=/invite/{scenario.token}"
    )
    expect(page.locator(IPL.LINK_CREATE_ACCOUNT)).to_have_attribute(
        "href", f"/?next=/invite/{scenario.token}/register"
    )
    expect(page.locator(IPL.BACK_SPLASH_BTN)).to_be_visible()
    expect(page.locator(IPL.BUTTON_JOIN)).to_have_count(0)


def test_anonymous_state_two_has_no_overflow_at_phone_width(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a live invite link and a logged-out visitor on a 390px viewport
    WHEN the invite page renders
    THEN nothing overflows horizontally and the actions fill the row
    """
    scenario = _seed_invite(app=provide_app, page=page)
    _use_mobile_viewport(page=page)

    page.goto(scenario.url)

    expect(page.locator(IPL.LINK_CREATE_ACCOUNT)).to_be_visible()
    _assert_no_horizontal_overflow(page=page)


def test_state_two_long_unbroken_description_stays_inside_panel_at_phone_width(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a UTub whose description is 200 characters without spaces
    WHEN a logged-out visitor opens its invite at 390px
    THEN the page does not scroll horizontally and the description stays in the panel
    """
    scenario = _seed_invite(
        app=provide_app, page=page, description=LONG_UNBROKEN_DESCRIPTION
    )
    _use_mobile_viewport(page=page)

    page.goto(scenario.url)

    expect(page.locator(IPL.DESCRIPTION)).to_have_text(LONG_UNBROKEN_DESCRIPTION)
    _assert_no_horizontal_overflow(page=page)
    _assert_description_inside_panel(page=page)


def test_state_one_long_unbroken_description_stays_inside_panel_at_phone_width(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a UTub whose description is 200 characters without spaces
    WHEN a logged-in non-member opens its invite at 390px
    THEN the page does not scroll horizontally and the description stays in the panel
    """
    scenario = _seed_invite(
        app=provide_app, page=page, description=LONG_UNBROKEN_DESCRIPTION
    )
    _use_mobile_viewport(page=page)

    _log_in_and_open_invite(app=provide_app, page=page, scenario=scenario)

    expect(page.locator(IPL.DESCRIPTION)).to_have_text(LONG_UNBROKEN_DESCRIPTION)
    _assert_no_horizontal_overflow(page=page)
    _assert_description_inside_panel(page=page)


def test_logged_in_visitor_sees_state_one_and_joins(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a live invite link and a logged-in user who is not a member
    WHEN the user opens the invite page and clicks Join
    THEN the page has Not now pointing home and no splash item, Join lands on the
         UTub, and Back from there lands on /home
    """
    scenario = _seed_invite(app=provide_app, page=page)

    response = _log_in_and_open_invite(app=provide_app, page=page, scenario=scenario)

    assert response is not None
    assert response.status == 200
    expect(page.locator(IPL.HEADING)).to_have_text(scenario.utub_name)
    expect(page.locator(IPL.BUTTON_JOIN)).to_have_text(UTS.INVITE_JOIN_LABEL)
    expect(page.locator(IPL.LINK_NOT_NOW)).to_have_text(UTS.INVITE_NOT_NOW_LABEL)
    expect(page.locator(IPL.LINK_NOT_NOW)).to_have_attribute("href", "/home")
    expect(page.locator(IPL.BACK_SPLASH_BTN)).to_have_count(0)

    page.locator(IPL.BUTTON_JOIN).click()

    page.wait_for_url(re.compile(r"/home\?UTubID=\d+$"))
    assert urlsplit(page.url).query == f"UTubID={scenario.utub_id}"
    assert get_selected_utub_id(page=page) == scenario.utub_id

    page.go_back()

    # The invite URL is now a member redirect: Back must not show the invite page.
    page.wait_for_url(re.compile(r"/home(\?.*)?$"))
    assert urlsplit(page.url).path == "/home"
    expect(page.locator(IPL.MAIN)).to_have_count(0)
    expect(page.locator(HPL.SELECTORS_UTUB).first).to_be_visible()


def test_state_one_phone_width_actions_are_full_width_without_overflow(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a logged-in non-member on a 390px viewport
    WHEN the invite page renders
    THEN Join and Not now both fill their row and nothing overflows horizontally
    """
    scenario = _seed_invite(app=provide_app, page=page)
    _use_mobile_viewport(page=page)

    _log_in_and_open_invite(app=provide_app, page=page, scenario=scenario)

    expect(page.locator(IPL.BUTTON_JOIN)).to_be_visible()
    _assert_full_width(page=page, css_selector=IPL.BUTTON_JOIN)
    _assert_full_width(page=page, css_selector=IPL.LINK_NOT_NOW)
    _assert_no_horizontal_overflow(page=page)


def test_join_busy_state_is_undone_by_pageshow(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a Join submit whose POST is still in flight
    WHEN a persisted `pageshow` event fires (as on a bfcache restore)
    THEN the button, form and status return to their normal state
    """
    scenario = _seed_invite(app=provide_app, page=page)
    _log_in_and_open_invite(app=provide_app, page=page, scenario=scenario)
    # A 204 answers the POST without committing a navigation, so the page stays in its
    # busy state and no request is left pending (a held request would block teardown).
    page.route("**/invite/*/join", lambda route: route.fulfill(status=204))

    page.locator(IPL.BUTTON_JOIN).click()

    expect(page.locator(IPL.JOIN_FORM)).to_have_attribute("aria-busy", "true")
    expect(page.locator(IPL.BUTTON_JOIN)).to_have_text(UTS.INVITE_JOINING_LABEL)
    expect(page.locator(IPL.BUTTON_JOIN)).to_have_attribute("aria-disabled", "true")
    expect(page.locator(IPL.JOIN_STATUS)).to_have_text(UTS.INVITE_JOINING_LABEL)

    page.evaluate(
        "() => window.dispatchEvent("
        "new PageTransitionEvent('pageshow', { persisted: true }))"
    )

    expect(page.locator(IPL.BUTTON_JOIN)).not_to_have_attribute("aria-disabled", "true")
    expect(page.locator(IPL.BUTTON_JOIN)).to_have_text(UTS.INVITE_JOIN_LABEL)
    expect(page.locator(IPL.JOIN_FORM)).not_to_have_attribute("aria-busy", "true")
    expect(page.locator(IPL.JOIN_STATUS)).to_have_text("")


def test_join_button_shows_focus_ring_under_keyboard_focus(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN the logged-in invite page
    WHEN the user tabs to Join
    THEN it matches `:focus-visible` and draws an outline
    """
    scenario = _seed_invite(app=provide_app, page=page)
    _log_in_and_open_invite(app=provide_app, page=page, scenario=scenario)

    for _ in range(TAB_PRESS_LIMIT):
        page.keyboard.press("Tab")
        if page.locator(IPL.BUTTON_JOIN).evaluate(
            "el => el === document.activeElement"
        ):
            break

    expect(page.locator(IPL.BUTTON_JOIN)).to_be_focused()
    outline = page.locator(IPL.BUTTON_JOIN).evaluate(
        """(el) => ({
            focusVisible: el.matches(':focus-visible'),
            style: getComputedStyle(el).outlineStyle,
            width: parseFloat(getComputedStyle(el).outlineWidth),
        })"""
    )
    assert outline["focusVisible"] is True
    assert outline["style"] != "none"
    assert outline["width"] > 0


def test_dead_invite_shows_dead_page_with_go_to_app_link(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a revoked invite link
    WHEN a logged-out visitor opens it
    THEN the uniform dead page shows with a Go to URLS4IRL link and no UTub details
    """
    scenario = _seed_invite(app=provide_app, page=page, revoked=True)

    response = page.goto(scenario.url)

    assert response is not None
    assert response.status == 404
    expect(page.locator(IPL.HEADING)).to_have_text(UTS.INVITE_DEAD_HEADING)
    expect(page.locator(IPL.LINK_GO_TO_APP)).to_have_text(UTS.INVITE_GO_TO_APP_LABEL)
    expect(page.locator(IPL.MAIN)).not_to_contain_text(scenario.utub_name)


def test_dead_invite_has_no_overflow_at_phone_width(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a revoked invite link on a 390px viewport
    WHEN a logged-out visitor opens it
    THEN the dead page does not overflow horizontally
    """
    scenario = _seed_invite(app=provide_app, page=page, revoked=True)
    _use_mobile_viewport(page=page)

    page.goto(scenario.url)

    expect(page.locator(IPL.HEADING)).to_have_text(UTS.INVITE_DEAD_HEADING)
    _assert_no_horizontal_overflow(page=page)


def test_unconfirmed_email_viewer_is_treated_as_anonymous_on_a_live_link(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a logged-in user whose email is no longer validated (so an anonymous viewer)
    WHEN the user opens a live invite link
    THEN it shows the anonymous page: Log in and Create account links carrying the
         `next` contract, the navbar splash item and no Join button
    """
    scenario = _seed_invite(app=provide_app, page=page)
    login_user_to_home_page(app=provide_app, page=page, user_id=VISITOR_ID)
    set_email_validated_in_db(app=provide_app, user_id=VISITOR_ID, validated=False)

    response = page.goto(scenario.url)

    assert response is not None
    assert response.status == 200
    expect(page.locator(IPL.HEADING)).to_have_text(scenario.utub_name)
    expect(page.locator(IPL.LINK_LOG_IN)).to_have_attribute(
        "href", f"/?next=/invite/{scenario.token}"
    )
    expect(page.locator(IPL.LINK_CREATE_ACCOUNT)).to_have_attribute(
        "href", f"/?next=/invite/{scenario.token}/register"
    )
    expect(page.locator(IPL.BACK_SPLASH_BTN)).to_be_visible()
    expect(page.locator(IPL.BUTTON_JOIN)).to_have_count(0)


def test_unconfirmed_email_viewer_is_treated_as_anonymous_on_a_dead_link(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a logged-in user whose email is no longer validated (so an anonymous viewer)
    WHEN the user opens a revoked invite link
    THEN the uniform dead page shows with the Go to URLS4IRL link and no UTub details
    """
    scenario = _seed_invite(app=provide_app, page=page, revoked=True)
    login_user_to_home_page(app=provide_app, page=page, user_id=VISITOR_ID)
    set_email_validated_in_db(app=provide_app, user_id=VISITOR_ID, validated=False)

    response = page.goto(scenario.url)

    assert response is not None
    assert response.status == 404
    expect(page.locator(IPL.HEADING)).to_have_text(UTS.INVITE_DEAD_HEADING)
    expect(page.locator(IPL.LINK_GO_TO_APP)).to_have_text(UTS.INVITE_GO_TO_APP_LABEL)
    expect(page.locator(IPL.MAIN)).not_to_contain_text(scenario.utub_name)


def _assert_oauth_hrefs_end_with(*, page: Page, next_value: str) -> None:
    suffix = f"?next={quote(next_value, safe='')}"
    for css_selector in (
        SPL.LOGIN_BUTTON_GOOGLE_OAUTH,
        SPL.LOGIN_BUTTON_GITHUB_OAUTH,
        SPL.REGISTER_BUTTON_GOOGLE_OAUTH,
        SPL.REGISTER_BUTTON_GITHUB_OAUTH,
    ):
        expect(page.locator(css_selector)).to_have_attribute(
            "href", re.compile(f"{re.escape(suffix)}$")
        )
        href = page.locator(css_selector).get_attribute("href")
        assert href is not None and href.count("next=") == 1, (css_selector, href)


def _assert_visitor_is_not_member(*, app: Flask, utub_id: int) -> None:
    with app.app_context():
        assert (
            Utub_Members.query.filter_by(utub_id=utub_id, user_id=VISITOR_ID).count()
            == 0
        )


def test_log_in_link_opens_login_modal_with_oauth_next(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a live invite link and an anonymous visitor on its page
    WHEN the visitor clicks Log in
    THEN the splash opens with the Login modal shown and every OAuth button
         carrying the invite as `next`
    """
    scenario = _seed_invite(app=provide_app, page=page)
    page.goto(scenario.url)

    page.locator(IPL.LINK_LOG_IN).click()

    page.wait_for_url(re.compile(r"/\?next="))
    assert unquote(urlsplit(page.url).query) == f"next=/invite/{scenario.token}"
    wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)
    _assert_oauth_hrefs_end_with(page=page, next_value=f"/invite/{scenario.token}")


def test_create_account_link_opens_register_modal_with_oauth_next(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a live invite link and an anonymous visitor on its page
    WHEN the visitor clicks Create account
    THEN the splash opens with the Register modal shown and every OAuth button
         carrying the register hint as `next`
    """
    scenario = _seed_invite(app=provide_app, page=page)
    page.goto(scenario.url)

    page.locator(IPL.LINK_CREATE_ACCOUNT).click()

    page.wait_for_url(re.compile(r"/\?next="))
    wait_for_modal_ready(page=page, modal_selector=SPL.REGISTER_MODAL)
    _assert_oauth_hrefs_end_with(
        page=page, next_value=f"/invite/{scenario.token}/register"
    )


def test_password_login_from_auto_opened_modal_lands_on_invite_join(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a live invite link and an anonymous visitor who clicked Log in
    WHEN the visitor logs in with a password from the auto-opened modal
    THEN the visitor lands on the bare invite page showing Join, and is not a
         member until Join is pressed
    """
    scenario = _seed_invite(app=provide_app, page=page)
    page.goto(scenario.url)
    page.locator(IPL.LINK_LOG_IN).click()
    wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)

    input_login_fields(
        page=page,
        username=UTS.TEST_USERNAME_2,
        password=UTS.TEST_USERNAME_2 + EMAIL_SUFFIX,
    )
    page.locator(SPL.LOGIN_BUTTON_SUBMIT).click()

    page.wait_for_url(scenario.url)
    expect(page.locator(IPL.BUTTON_JOIN)).to_have_text(UTS.INVITE_JOIN_LABEL)
    _assert_visitor_is_not_member(app=provide_app, utub_id=scenario.utub_id)


def test_panel_link_login_handoff_ends_in_utub_with_one_join_click(
    page: Page,
    build_page_browser: Browser,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
    clipboard_mock: ClipboardMockHelper,
):
    """
    GIVEN a link the owner created and copied in the panel
    WHEN a logged-out, validated non-member opens it, logs in and clicks Join once
    THEN the visitor lands in the UTub as a MEMBER and one use is counted, with no
         membership or use before the click
    """
    utub_id = get_utub_this_user_created(provide_app, CREATOR_ID).id
    login_user_and_select_utub_by_utubid(
        app=provide_app, page=page, user_id=CREATOR_ID, utub_id=utub_id
    )
    clipboard_mock.setup_clipboard_mock()
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).click()
    page.locator(HPL.INVITE_LINK_CREATE_BTN).click()
    expect(page.locator(HPL.INVITE_LINK_COPY_BTN)).to_be_visible()
    page.locator(HPL.INVITE_LINK_COPY_BTN).click()
    clipboard_mock.wait_for_write_count(count=1)
    invite_url = clipboard_mock.get_clipboard_content()
    token = invite_url.rsplit("/", 1)[1]
    base_url = current_base_url(page=page)
    assert invite_url == f"{base_url}/invite/{token}"

    visitor_context = build_page_browser.new_context()
    try:
        visitor_context.set_default_timeout(10_000)
        visitor_context.set_default_navigation_timeout(30_000)
        add_playwright_cookie_banner_cookie(context=visitor_context, base_url=base_url)
        visitor = visitor_context.new_page()
        visitor.goto(invite_url)
        expect(visitor.locator(IPL.LINK_LOG_IN)).to_be_visible()
        visitor.locator(IPL.LINK_LOG_IN).click()
        wait_for_modal_ready(page=visitor, modal_selector=SPL.LOGIN_MODAL)
        input_login_fields(
            page=visitor,
            username=UTS.TEST_USERNAME_2,
            password=UTS.TEST_USERNAME_2 + EMAIL_SUFFIX,
        )
        visitor.locator(SPL.LOGIN_BUTTON_SUBMIT).click()

        visitor.wait_for_url(invite_url)
        expect(visitor.locator(IPL.BUTTON_JOIN)).to_have_text(UTS.INVITE_JOIN_LABEL)
        _assert_visitor_is_not_member(app=provide_app, utub_id=utub_id)
        with provide_app.app_context():
            assert _use_count(token=token) == 0

        visitor.locator(IPL.BUTTON_JOIN).click()

        _assert_joined_as_member(
            app=provide_app,
            page=visitor,
            utub_id=utub_id,
            user_id=VISITOR_ID,
            token=token,
        )
    finally:
        visitor_context.close()


def test_non_invite_next_opens_no_modal_and_leaves_oauth_hrefs(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN an anonymous visitor on `/?next=/not-an-invite`
    WHEN the splash loads
    THEN no modal opens (no hint is rendered) and the OAuth hrefs carry only the
         page's own single `next`
    """
    page.goto(f"{current_base_url(page=page)}/?next=/not-an-invite")

    expect(page.locator(SPL.SPLASH_CONFIG_ANONYMOUS)).to_be_attached()
    expect(page.locator(SPL.SPLASH_CONFIG_ANONYMOUS)).not_to_have_attribute(
        "data-auth-modal-hint", re.compile(".+")
    )
    # Hrefs are rewritten in the same on-load tick as the hint check, so waiting
    # on them first proves the on-load code ran before asserting no modal opened.
    _assert_oauth_hrefs_end_with(page=page, next_value="/not-an-invite")
    expect(page.locator(".modal.show")).to_have_count(0)


def test_github_oauth_from_auto_opened_login_modal_lands_on_invite(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a live invite link and a returning GitHub-linked user who is not a member
    WHEN the visitor clicks Log in, then Sign in with GitHub
    THEN the OAuth callback returns the visitor to the bare invite page
    """
    with provide_app.app_context():
        user = Users(
            username=UTS.OAUTH_GITHUB_RETURNING_USER_USERNAME,
            email=UTS.OAUTH_GITHUB_RETURNING_USER_EMAIL,
            plaintext_password=None,
        )
        user.oauth_identities.append(
            UserOAuthIdentity(
                provider="github",
                provider_subject=UTS.OAUTH_GITHUB_RETURNING_USER_SUBJECT,
            )
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()

    scenario = _seed_invite(app=provide_app, page=page)
    page.goto(scenario.url)
    page.locator(IPL.LINK_LOG_IN).click()
    wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)

    # The auto-opened modal covers the navbar, so set the fake identity
    # directly instead of login_with_github_ui's navbar click.
    splash_url = page.url
    page.goto(
        f"{current_base_url(page=page)}/fake-oauth/set-identity?"
        + urlencode(
            {
                "subject": UTS.OAUTH_GITHUB_RETURNING_USER_SUBJECT,
                "email": UTS.OAUTH_GITHUB_RETURNING_USER_EMAIL,
                "login": UTS.OAUTH_GITHUB_RETURNING_USER_LOGIN,
            }
        )
    )
    page.goto(splash_url)
    wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)
    page.locator(SPL.LOGIN_BUTTON_GITHUB_OAUTH).click()

    page.wait_for_url(scenario.url)
    expect(page.locator(IPL.BUTTON_JOIN)).to_have_text(UTS.INVITE_JOIN_LABEL)


SIGNUP_USERNAME = "invitesignup"
SIGNUP_EMAIL = "invitesignup@urls4irl.app"
SIGNUP_PASSWORD = "InviteSignup1!"


def _use_count(*, token: str) -> int:
    """Must be called inside an app context."""
    return Utub_Invite_Links.query.filter_by(token=token).one().use_count


def _assert_joined_as_member(
    *, app: Flask, page: Page, utub_id: int, user_id: int, token: str
) -> None:
    """After the single Join click: on the UTub, a MEMBER row, one use counted."""
    page.wait_for_url(re.compile(r"/home\?UTubID=\d+$"))
    assert urlsplit(page.url).query == f"UTubID={utub_id}"
    assert get_selected_utub_id(page=page) == utub_id
    with app.app_context():
        membership = Utub_Members.query.filter_by(
            utub_id=utub_id, user_id=user_id
        ).one()
        assert membership.member_role == Member_Role.MEMBER
        assert _use_count(token=token) == 1


def _submit_signup_and_open_validation_link(*, app: Flask, page: Page) -> int:
    """Submit the filled Register form, wait for the confirmation modal, then open
    the new user's validation link. Returns the new user's id."""
    page.locator(SPL.REGISTER_BUTTON_SUBMIT).click()
    wait_for_modal_ready(page=page, modal_selector=SPL.REGISTER_CONFIRMATION_MODAL)

    with app.app_context():
        user = Users.query.filter(Users.username == SIGNUP_USERNAME).one()
        user_id = user.id
        token = user.email_confirm.validation_token

    page.goto(f"{current_base_url(page=page)}/validate/{token}")
    return user_id


def test_signup_from_invite_lands_on_invite_join_without_membership(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a live invite link and an anonymous visitor who clicked Create account
    WHEN the visitor registers, then opens the emailed validation link
    THEN the visitor is logged in on the invite page showing Join, and is not a
         member of the UTub
    """
    scenario = _seed_invite(app=provide_app, page=page)
    page.goto(scenario.url)
    page.locator(IPL.LINK_CREATE_ACCOUNT).click()
    wait_for_modal_ready(page=page, modal_selector=SPL.REGISTER_MODAL)

    fill_register_fields(
        page=page,
        username=SIGNUP_USERNAME,
        email=SIGNUP_EMAIL,
        password=SIGNUP_PASSWORD,
    )
    user_id = _submit_signup_and_open_validation_link(app=provide_app, page=page)

    page.wait_for_url(scenario.url)
    expect(page.locator(IPL.BUTTON_JOIN)).to_have_text(UTS.INVITE_JOIN_LABEL)
    with provide_app.app_context():
        assert (
            Utub_Members.query.filter_by(
                utub_id=scenario.utub_id, user_id=user_id
            ).count()
            == 0
        )
        assert _use_count(token=scenario.token) == 0

    page.locator(IPL.BUTTON_JOIN).click()

    _assert_joined_as_member(
        app=provide_app,
        page=page,
        utub_id=scenario.utub_id,
        user_id=user_id,
        token=scenario.token,
    )


def test_signup_from_plain_splash_lands_on_home(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN an anonymous visitor on the plain splash page
    WHEN the visitor registers, then opens the emailed validation link
    THEN the visitor lands on the home page
    """
    page.goto(current_base_url(page=page))
    register_user_ui(
        page=page,
        username=SIGNUP_USERNAME,
        email=SIGNUP_EMAIL,
        password=SIGNUP_PASSWORD,
    )
    _submit_signup_and_open_validation_link(app=provide_app, page=page)

    page.wait_for_url(re.compile(r"/home(\?|$)"))
    assert_login_with_username(page=page, username=SIGNUP_USERNAME)
