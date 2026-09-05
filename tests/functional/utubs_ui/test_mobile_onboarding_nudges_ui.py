"""Mobile (Playwright) coverage for the first-time onboarding nudge system.

Proves the Create-UTub nudge shows on the UTub (left) panel at a 420px mobile
viewport, and that switching decks (by creating the first UTub, which is the only
deck-switch reachable from the zero-UTub state) clears it and advances the
curated sequence to the Add-URL nudge on the now-current URL panel. This also
exercises main.ts's real init ordering: the Add-URL tip only appears if the
onboarding MOBILE_DECK_SWITCHED subscriber runs after the mobile-layout
subscriber that reveals #urlBtnCreate.

WebKit note: the shared browser fixture (build_page_browser) connects to /
launches Chromium only, so WebKit is not driveable from this test harness;
WebKit mobile rendering is covered by the manual/device verification step
(see the plan's Step 7 screenshot to-do and the WebKit memory note).
"""

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.playwright_utils import (
    Decks,
    login_user_to_home_page,
    wait_then_click_element,
    wait_until_hidden,
)
from tests.functional.utubs_ui.playwright_utils import create_utub

pytestmark = pytest.mark.mobile_ui


def test_create_utub_nudge_shows_on_utub_panel_and_sequences_on_deck_switch_mobile(
    page_mobile_portrait: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a first-time user with zero UTubs on a 420px mobile viewport
    WHEN the home page loads
    THEN the Create-UTub nudge shows on the UTub (left) panel; AND
    WHEN they create their first UTub (switching decks to the URL panel)
    THEN the Create-UTub tip clears and the Add-URL nudge shows on the URL panel.
    """
    page = page_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    # Mobile zero-UTub user lands on the UTub (left) panel; the Create-UTub nudge
    # shows there.
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)
    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_CREATE_UTUB_TIP_TITLE
    )

    # Creating the first UTub switches decks to the URL panel
    # (MOBILE_DECK_SWITCHED). NOTE: from the zero-UTub state the only reachable
    # deck switch is via creating a UTub, and `create_utub` taps #utubBtnCreate
    # (the Create-UTub tip's anchor) — so here the Create-UTub tip is dismissed
    # via the ACT path (markSeen: true), not the environment-teardown path. The
    # markSeen:false MOBILE_DECK_SWITCHED teardown is covered at the unit level
    # (Vitest nudges.test.ts). This test proves the deck switch re-evaluates and
    # advances the curated sequence on the now-current panel.
    utub_name = UTS.TEST_UTUB_NAME_1
    create_utub(page=page, utub_name=utub_name, utub_description="")
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    # The Add-URL nudge now shows on the URL panel (the Create-UTub tip is gone,
    # replaced by the next tip in the curated sequence — the single-active-tip
    # invariant means a distinct title/body here proves the Create tip cleared).
    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_ADD_URL_TIP_TITLE
    )
    expect(page.locator(HPL.ONBOARDING_NUDGE_BODY)).to_have_text(
        UTS.ONBOARDING_ADD_URL_TIP_BODY
    )
