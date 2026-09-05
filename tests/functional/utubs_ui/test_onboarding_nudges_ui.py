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

from typing import Tuple

from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from playwright.sync_api import Page, expect

from backend.cli.mock_constants import MOCK_URL_STRINGS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM
from tests.functional.db_utils import (
    add_mock_urls,
    get_url_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_active_utub,
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.playwright_utils import (
    current_base_url,
    login_user_to_home_page,
    select_utub_by_id,
    select_utub_by_name,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_until_css_property,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.playwright_utils import (
    create_utub,
    delete_utub_as_creator,
)

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


def test_create_utub_nudge_rearms_after_deleting_last_utub(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a returning user (Create-UTub tip already marked seen) who currently
          has exactly one UTub — i.e. the Create deck holds content
    WHEN they delete that last UTub, returning to the zero-UTub empty state
    THEN the Create-UTub nudge RE-SHOWS, proving the re-arm mechanic.

    Re-arm mechanic (nudges.ts::rearmCompletedTips): on every re-evaluation the
    engine CLEARS a tip's persisted seen flag when that tip's deck holds content
    (createUtub: ``utubs.length > 0``) and it was previously seen. The clear only
    happens while content exists — so the content-load-then-empty rhythm this
    test drives is essential:

      1. Content load: the page loads with one UTub present. On that load the
         onboarding init re-evaluates while the Create deck has content, so the
         seeded ``createUtub`` seen flag is cleared (re-armed). Because content
         exists, the tip is not eligible and does NOT show yet.
      2. Empty: deleting the last UTub empties the deck. ``delete.ts`` sets
         ``{ utubs: [], activeUTubID: null, urls: [] }`` then emits
         ``UTUB_DELETED`` — a live re-eval (no page reload). With the flag already
         cleared and the deck now empty, the Create-UTub tip is eligible again and
         re-shows.

    ``add_init_script`` is safe here to seed the seen flag: there is NO further
    reload after the delete (``UTUB_DELETED`` drives the re-show on the live
    page), so the init script cannot re-seed the flag and mask the re-arm.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    # Seed the Create-UTub tip as already seen for this returning user. The reload
    # is required so the seeded value is present when the onboarding init runs (see
    # test_onboarding_nudge_hidden_for_returning_user for the reload rationale).
    page.context.add_init_script(
        "localStorage.setItem('u4i:onboardingSeen',"
        " JSON.stringify({createUtub: true}))"
    )
    page.reload()

    # A UTub exists, so the Create-UTub tip is not eligible (has content) and does
    # not show. The content-present load has ALSO already re-armed the flag (the
    # clear runs during any re-eval while the deck is non-empty). The UTub selector
    # being present is the readiness signal (the zero-UTub "Create a UTub"
    # subheader is correctly hidden while a UTub exists).
    assert_visible_css_selector(page=page, css_selector=HPL.SELECTORS_UTUB)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )

    # Select the UTub (the delete flow acts on the selected UTub). This is another
    # content-present re-eval (harmless — the flag is already cleared).
    select_utub_by_name(page=page, utub_name=utub_user_created.name)

    # Delete the last UTub -> zero-UTub empty state -> UTUB_DELETED re-eval fires
    # live and the re-armed Create-UTub tip re-shows.
    delete_utub_as_creator(page=page, utub_to_delete=utub_user_created)

    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_CREATE_UTUB_TIP_TITLE
    )


def test_add_url_nudge_rearms_after_deleting_last_url(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a returning user (Add-URL tip already marked seen) whose one UTub holds
          exactly one URL — i.e. the Add-URL deck holds content
    WHEN they delete that last URL and evaluation re-runs on the now-empty UTub
    THEN the Add-URL nudge RE-SHOWS, proving the re-arm mechanic for the Add-URL
         tip via the ``UTUB_SELECTED`` (cold-load pre-selection) path.

    Re-arm mechanic (nudges.ts::rearmCompletedTips): on every re-evaluation the
    engine CLEARS a tip's persisted seen flag when that tip's deck holds content
    (addUrl: active UTub ``urls.length > 0``) and it was previously seen. The
    clear only happens while content exists, so this test drives the
    content-load-then-empty rhythm:

      1. Content load: selecting the UTub while its URL is present emits
         ``UTUB_SELECTED`` with ``urls.length > 0``, a re-eval that clears
         (re-arms) the seeded ``addUrl`` seen flag. The tip is not eligible (deck
         has a URL) so it does NOT show yet.
      2. Empty: deleting the last URL empties the UTub. Re-selecting the same,
         already-active UTub does NOT re-emit ``UTUB_SELECTED``
         (selectors.ts::selectUTub short-circuits a re-selection), so evaluation
         is re-triggered by navigating to the pre-selected-UTub URL
         (``/home?<UTUB_ID_QUERY_PARAM>=<id>``). On that cold load the pageshow
         handler pre-selects the UTub and emits ``UTUB_SELECTED`` with
         ``urls: []`` — with the flag already cleared and the deck now empty, the
         Add-URL tip is eligible again and re-shows.

    The seen flag is seeded with a ONE-TIME ``page.evaluate`` (NOT
    ``add_init_script``): this test reloads after the re-arm, and an init script
    would re-seed ``addUrl: true`` on that reload and mask the fix.
    """
    _, cli_runner = runner
    app = provide_app
    user_id_for_test = 1

    # One UTub containing exactly one URL (mirrors test_delete_last_url's setup:
    # create_test_utubs gives user 1 a single owned UTub, then a single mock URL
    # is added to it).
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])

    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id=utub_id)
    url_id = url_in_utub.id

    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    # Seed BOTH tips as already seen via a ONE-TIME evaluate (persisted to
    # localStorage, not re-applied on later navigations).
    page.evaluate(
        "localStorage.setItem('u4i:onboardingSeen',"
        " JSON.stringify({addUrl: true, createUtub: true}))"
    )

    # Content load: select the UTub while its URL is present -> UTUB_SELECTED with
    # urls.length > 0 -> the addUrl seen flag is cleared (re-armed). The Add-URL
    # tip is not eligible (deck has a URL), so it must NOT be visible.
    select_utub_by_id(page=page, utub_id=utub_id)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )

    # Delete the last URL via the desktop delete-URL flow (mirrors
    # test_delete_url_ui.py rhythm): select the row, open the confirm modal, gate
    # the submit on the fade-in settling, submit, then wait for the row to go.
    url_row_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_id}']"
    wait_then_click_element(page=page, css_selector=url_row_selector)
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )
    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}"
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_selector_to_be_removed(page=page, css_selector=url_row_selector)

    # Re-trigger evaluation while the UTub is empty. Re-clicking the already-active
    # UTub would be a no-op (selectUTub short-circuits), so navigate to the
    # pre-selected-UTub URL: the cold-load pageshow handler pre-selects the UTub
    # and emits UTUB_SELECTED with urls: [], re-evaluating the onboarding engine.
    base_url = current_base_url(page=page)
    page.goto(f"{base_url}/home?{UTUB_ID_QUERY_PARAM}={utub_id}")

    # With the flag cleared during the content load and the deck now empty, the
    # Add-URL tip is eligible again and re-shows with its bridged copy.
    assert_active_utub(page=page, utub_name=utub_user_created.name)
    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_ADD_URL_TIP_TITLE
    )
    expect(page.locator(HPL.ONBOARDING_NUDGE_BODY)).to_have_text(
        UTS.ONBOARDING_ADD_URL_TIP_BODY
    )
