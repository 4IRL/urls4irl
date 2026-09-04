"""End-to-end (Playwright) coverage for the first-time onboarding nudge system.

Proves the nudge bubble actually renders (the existing tooltip custom-classes
ship with zero CSS, so the whole point of Step 3's stylesheet is that this bubble
is visible), that its copy comes through the APP_CONFIG strings bridge, that the
seen-once localStorage gate suppresses it for a returning user, that acting on
the anchor / tapping away both dismiss and persist the seen flag, and that the
Create-UTub tip sequences into the Add-URL tip once the first UTub exists.

Zero-UTub state = the ``create_test_users`` fixture alone with ``user_id = 1``
(no UTub-seeding fixture layered on), mirroring
``test_search_utub_ui.py::test_search_bar_hidden_when_no_utubs``.
"""

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_active_utub,
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    wait_then_click_element,
    wait_until_hidden,
)
from tests.functional.utubs_ui.playwright_utils import create_utub

pytestmark = pytest.mark.utubs_ui


def test_create_utub_nudge_shows_with_bridged_copy(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a first-time user with zero UTubs loads the home page
    WHEN the onboarding system initializes
    THEN the Create-UTub nudge bubble is visible and shows the bridged
         title/body copy read via APP_CONFIG.strings.*
    """
    app = provide_app
    user_id_for_test = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_CREATE_UTUB_TIP_TITLE
    )
    expect(page.locator(HPL.ONBOARDING_NUDGE_BODY)).to_have_text(
        UTS.ONBOARDING_CREATE_UTUB_TIP_BODY
    )


def test_onboarding_nudge_hidden_for_returning_user(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a returning user whose seen-once flag is already persisted
    WHEN they load the home page in the zero-UTub state
    THEN the nudge bubble never appears.

    The seen flag is seeded via ``page.context.add_init_script(...)`` — a
    standard Playwright technique (not otherwise used in tests/functional) that
    runs the script on every navigation registered AFTER it. Because the page
    fixture already navigated during setup, an explicit ``page.reload()`` is
    required so the seeded value is present when the onboarding init runs.
    """
    app = provide_app
    user_id_for_test = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    page.context.add_init_script(
        "localStorage.setItem('u4i:onboardingSeen',"
        " JSON.stringify({createUtub: true}))"
    )
    # $(document).ready fires on DOMContentLoaded, which precedes the 'load'
    # event that reload() awaits — so once reload() returns, the onboarding init
    # has already run against the seeded flag and the tip decision is final.
    page.reload()

    # Page is interactive (zero-UTub subheader server-rendered) and the tip was
    # gated off by the persisted flag.
    assert_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_UTUB_DECK)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )


def test_create_utub_nudge_act_dismiss_opens_form_and_persists(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN the Create-UTub nudge is showing on the anchor button
    WHEN the user taps the anchor (#utubBtnCreate) itself (the "act" path)
    THEN the nudge dismisses AND the create-UTub form opens, and reloading
         afterward shows no tip (the seen flag was persisted on dismissal).
    """
    app = provide_app
    user_id_for_test = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)

    # Act path: tapping the anchor dismisses the tip (mark seen) and, because the
    # handler never preventDefaults, the anchor's own click handler still opens
    # the create form.
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_CREATE)

    assert_visible_css_selector(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)

    # Seen flag persisted -> no tip after a fresh load.
    page.reload()
    assert_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_UTUB_DECK)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )


def test_create_utub_nudge_tap_away_dismisses_and_persists(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN the Create-UTub nudge is showing
    WHEN the user taps somewhere else on the page (the "tap-away" path)
    THEN the nudge dismisses, and reloading afterward shows no tip (the seen
         flag was persisted on dismissal).
    """
    app = provide_app
    user_id_for_test = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)

    # Tap-away path: a click on a neutral element away from the anchor (the URL
    # deck subheader on the opposite panel, which has no click handler while no
    # UTub is selected, so it never navigates) dismisses the tip.
    wait_then_click_element(page=page, css_selector=HPL.SUBHEADER_URL_DECK)
    wait_until_hidden(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)

    page.reload()
    assert_visible_css_selector(page=page, css_selector=HPL.SUBHEADER_UTUB_DECK)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )


def test_add_url_nudge_shows_after_creating_first_utub(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a first-time user dismisses the Create-UTub tip by creating their
          first UTub (which auto-selects it, emptied of URLs)
    WHEN the onboarding system re-evaluates on UTUB_SELECTED
    THEN the Create-UTub tip is gone and the Add-URL nudge shows next, with its
         own bridged copy — proving the contextual Create -> Add-URL sequence.
    """
    app = provide_app
    user_id_for_test = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_CREATE_UTUB_TIP_TITLE
    )

    # Creating the first UTub: the anchor tap (act path) dismisses the Create-UTub
    # tip; submitting auto-selects the new, empty UTub -> Add-URL tip becomes
    # eligible and shows.
    utub_name = UTS.TEST_UTUB_NAME_1
    create_utub(page=page, utub_name=utub_name, utub_description="")
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE)
    assert_active_utub(page=page, utub_name=utub_name)

    # The next tip in the curated sequence is the Add-URL nudge.
    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_ADD_URL_TIP_TITLE
    )
    expect(page.locator(HPL.ONBOARDING_NUDGE_BODY)).to_have_text(
        UTS.ONBOARDING_ADD_URL_TIP_BODY
    )
