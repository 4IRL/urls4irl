import re
from typing import NamedTuple
from urllib.parse import urlsplit

import pytest
from flask import Flask
from playwright.sync_api import Page, Response, expect

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.invite_links_ui.db_utils import (
    mint_invite_link_in_db,
    set_email_validated_in_db,
    set_utub_description_in_db,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import InvitePageLocators as IPL
from tests.functional.playwright_utils import (
    current_base_url,
    get_selected_utub_id,
    login_user_to_home_page,
)

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


def test_unvalidated_email_state_five_has_no_clickable_way_out(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a logged-in user whose email is no longer validated
    WHEN the user opens a live invite link
    THEN the page shows the confirm-email status and nothing clickable in the body,
         no splash link, and a non-link brand
    """
    scenario = _seed_invite(app=provide_app, page=page)
    login_user_to_home_page(app=provide_app, page=page, user_id=VISITOR_ID)
    set_email_validated_in_db(app=provide_app, user_id=VISITOR_ID, validated=False)

    response = page.goto(scenario.url)

    assert response is not None
    assert response.status == 200
    expect(page.locator(IPL.HEADING)).to_have_text(UTS.INVITE_UNVALIDATED_HEADING)
    expect(page.locator(IPL.MESSAGE)).to_be_visible()
    expect(page.locator(IPL.MESSAGE)).to_have_attribute("role", "status")
    expect(
        page.locator(f"{IPL.MAIN} button, {IPL.MAIN} a, {IPL.MAIN} form")
    ).to_have_count(0)
    expect(page.locator(IPL.BACK_SPLASH_BTN)).to_have_count(0)
    expect(page.locator(IPL.ANY_ROOT_LINK)).to_have_count(0)
    expect(page.locator(IPL.NAVBAR_BRAND_SPAN)).to_have_count(1)


def test_unvalidated_email_state_five_phone_width_has_no_overflow(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a logged-in user whose email is no longer validated on a 390px viewport
    WHEN the user opens a live invite link
    THEN the confirm-email message shows and nothing overflows horizontally
    """
    scenario = _seed_invite(app=provide_app, page=page)
    login_user_to_home_page(app=provide_app, page=page, user_id=VISITOR_ID)
    set_email_validated_in_db(app=provide_app, user_id=VISITOR_ID, validated=False)
    _use_mobile_viewport(page=page)

    page.goto(scenario.url)

    expect(page.locator(IPL.MESSAGE)).to_be_visible()
    expect(page.locator(IPL.ANY_ROOT_LINK)).to_have_count(0)
    _assert_no_horizontal_overflow(page=page)


def test_unvalidated_email_viewer_dead_page_has_no_go_to_app_link(
    page: Page,
    create_test_users,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a logged-in user whose email is no longer validated
    WHEN the user opens a revoked invite link
    THEN the dead page omits the Go to URLS4IRL link and has no root link at all
    """
    scenario = _seed_invite(app=provide_app, page=page, revoked=True)
    login_user_to_home_page(app=provide_app, page=page, user_id=VISITOR_ID)
    set_email_validated_in_db(app=provide_app, user_id=VISITOR_ID, validated=False)

    page.goto(scenario.url)

    expect(page.locator(IPL.HEADING)).to_have_text(UTS.INVITE_DEAD_HEADING)
    expect(page.locator(IPL.LINK_GO_TO_APP)).to_have_count(0)
    expect(page.locator(IPL.ANY_ROOT_LINK)).to_have_count(0)
