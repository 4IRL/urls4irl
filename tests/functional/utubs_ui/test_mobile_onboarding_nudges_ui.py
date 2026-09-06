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

from typing import Tuple

from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from playwright.sync_api import Page, expect

from backend.cli.mock_constants import MOCK_URL_STRINGS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_mock_urls,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.playwright_utils import (
    Decks,
    click_on_navbar,
    login_user_to_home_page,
    select_utub_by_id_mobile,
    wait_then_click_element,
    wait_until_hidden,
)
from tests.functional.tags_ui.playwright_utils import (
    wait_until_tag_sheet_collapsed,
    wait_until_tag_sheet_open,
)
from tests.functional.utubs_ui.playwright_utils import create_utub

pytestmark = pytest.mark.mobile_ui

USER_ID_FOR_TEST = 1

# All tips before the one under test seeded as already seen, via a ONE-TIME
# evaluate (not add_init_script) so the value is not re-applied on later
# navigations. addMember is seeded seen for the addTag test so the mobile
# priority inversion (Summary decision 5) cannot let addMember show first and
# block addTag with the single-active-tip guard.
_SEED_CREATE_UTUB_ADD_URL_ADD_MEMBER_SEEN = (
    "localStorage.setItem('u4i:onboardingSeen',"
    " JSON.stringify({createUtub: true, addUrl: true, addMember: true}))"
)
_SEED_CREATE_UTUB_ADD_URL_ADD_TAG_SEEN = (
    "localStorage.setItem('u4i:onboardingSeen',"
    " JSON.stringify({createUtub: true, addUrl: true, addTag: true}))"
)


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


def test_add_tag_nudge_shows_when_tag_sheet_opened_and_dismisses_on_close_mobile(
    page_mobile_portrait: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a mobile user whose one UTub holds a URL but no tags (createUtub, addUrl,
          addMember tips already seen) with the tag bottom sheet collapsed
    WHEN they open the tag sheet
    THEN the addTag nudge shows anchored to #utubTagBtnCreate inside the open
         sheet; AND
    WHEN they tap the handle to close the sheet (an ordinary tap-away)
    THEN the nudge dismisses and is marked seen — it does not re-show on re-opening
         the sheet.

    This is the decision-3 ``TAG_SHEET_TOGGLED`` hook's end-to-end proof: on mobile
    #utubTagBtnCreate lives inside the sheet and is visibility:hidden while
    collapsed, so the addTag tip is correctly withheld until the sheet opens (the
    strengthened ``isAnchorVisible`` rejects the visibility:hidden ancestor), then
    shown once the sheet's open transition resolves the anchor visible (the bounded
    retry the ``TAG_SHEET_TOGGLED {active:true}`` handler runs after emit).
    """
    page = page_mobile_portrait
    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    page.evaluate(_SEED_CREATE_UTUB_ADD_URL_ADD_MEMBER_SEEN)

    # Select the UTub (switches to the URL panel). The tag deck is relocated into
    # the collapsed bottom sheet, so #utubTagBtnCreate is visibility:hidden and the
    # addTag tip must NOT show yet.
    select_utub_by_id_mobile(page=page, utub_id=utub_user_created.id)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)
    wait_until_tag_sheet_collapsed(page=page)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )

    # Open the sheet -> TAG_SHEET_TOGGLED{active:true} -> deferred re-eval -> the now
    # visible #utubTagBtnCreate anchor lets the addTag tip show inside the sheet.
    wait_then_click_element(page=page, css_selector=HPL.TAG_SHEET_HANDLE)
    wait_until_tag_sheet_open(page=page)

    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_ADD_TAG_TIP_TITLE
    )
    expect(page.locator(HPL.ONBOARDING_NUDGE_BODY)).to_have_text(
        UTS.ONBOARDING_ADD_TAG_TIP_BODY
    )

    # Tapping the handle to close is an ordinary tap-away: the shipped document
    # click handler dismisses the active tip with markSeen:true.
    wait_then_click_element(page=page, css_selector=HPL.TAG_SHEET_HANDLE)
    wait_until_tag_sheet_collapsed(page=page)
    wait_until_hidden(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)

    # Re-opening the sheet does NOT re-show the tip — it was marked seen and the
    # still-empty tag deck does not re-arm it.
    wait_then_click_element(page=page, css_selector=HPL.TAG_SHEET_HANDLE)
    wait_until_tag_sheet_open(page=page)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )


def test_add_member_nudge_shows_on_member_deck_and_tears_down_on_switch_mobile(
    page_mobile_portrait: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a mobile lone owner of a UTub (prior createUtub/addUrl/addTag tips seen)
    WHEN they switch to the member deck (MOBILE_DECK_SWITCHED)
    THEN the addMember nudge shows on the member panel (its #memberBtnCreate anchor
         is hidden on the URL panel, so it only becomes eligible once the member
         deck is current); AND
    WHEN they switch away to another deck
    THEN the nudge tears down.
    """
    page = page_mobile_portrait
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    page.evaluate(_SEED_CREATE_UTUB_ADD_URL_ADD_TAG_SEEN)

    # Select the UTub -> URL panel. #memberBtnCreate lives on the (hidden) member
    # panel, so the addMember tip must NOT show here.
    select_utub_by_id_mobile(page=page, utub_id=utub_user_created.id)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )

    # Switch to the member deck -> MOBILE_DECK_SWITCHED re-eval -> #memberBtnCreate
    # is now visible -> the addMember tip shows on the member panel.
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.MEMBERS)

    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_ADD_MEMBER_TIP_TITLE
    )
    expect(page.locator(HPL.ONBOARDING_NUDGE_BODY)).to_have_text(
        UTS.ONBOARDING_ADD_MEMBER_TIP_BODY
    )

    # Switch away to the URL deck -> MOBILE_DECK_SWITCHED tears the active tip down.
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_URLS_DECK)
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)
    wait_until_hidden(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
