"""End-to-end (Playwright) coverage for the addTag onboarding nudge (desktop).

Mirrors the shipped Create-UTub / Add-URL nudge flows
(``utubs_ui/test_onboarding_nudges_ui.py``) for the addTag tip: it proves the
bubble renders on ``#utubTagBtnCreate`` with its bridged copy once a UTub holds a
URL but no tags, that tapping the anchor (the "act" path) opens the create-tag
form and dismisses/persists the tip, and that the ``TAG_DECK_CHANGED`` re-arm
re-shows it after the last tag is deleted.

addTag eligibility (``nudges.ts`` registry): active UTub with
``urls.length > 0 && tags.length === 0``; ``hasContent`` = ``tags.length > 0``.
The createUtub + addUrl tips are seeded as seen so the curated sequence has
already advanced to addTag.
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
    assert_visible_css_selector,
)
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    select_utub_by_id,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.tags_ui

USER_ID_FOR_TEST = 1

# The createUtub + addUrl tips seeded as already seen so the curated sequence has
# advanced to addTag; a ONE-TIME evaluate (not add_init_script) so the value is
# not re-applied on later navigations that would mask a re-arm.
_SEED_CREATE_UTUB_AND_ADD_URL_SEEN = (
    "localStorage.setItem('u4i:onboardingSeen',"
    " JSON.stringify({createUtub: true, addUrl: true}))"
)
_SEED_CREATE_UTUB_ADD_URL_ADD_TAG_SEEN = (
    "localStorage.setItem('u4i:onboardingSeen',"
    " JSON.stringify({createUtub: true, addUrl: true, addTag: true}))"
)
# Reads the persisted addTag seen flag from localStorage.
_READ_ADD_TAG_SEEN = (
    "() => { const raw = localStorage.getItem('u4i:onboardingSeen');"
    " return raw ? JSON.parse(raw).addTag === true : false; }"
)


def test_add_tag_nudge_shows_with_bridged_copy(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a user whose one UTub holds a URL but no tags (createUtub + addUrl tips
          already seen)
    WHEN they select that UTub and the onboarding system re-evaluates
    THEN the addTag nudge bubble is visible on #utubTagBtnCreate with the bridged
         title/body copy read via APP_CONFIG.strings.*
    """
    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    page.evaluate(_SEED_CREATE_UTUB_AND_ADD_URL_SEEN)

    select_utub_by_id(page=page, utub_id=utub_user_created.id)

    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_ADD_TAG_TIP_TITLE
    )
    expect(page.locator(HPL.ONBOARDING_NUDGE_BODY)).to_have_text(
        UTS.ONBOARDING_ADD_TAG_TIP_BODY
    )


def test_add_tag_nudge_act_dismiss_opens_form_and_persists(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN the addTag nudge is showing on its anchor (#utubTagBtnCreate)
    WHEN the user taps the anchor itself (the "act" path)
    THEN the nudge dismisses AND the create-tag form opens; re-selecting the UTub
         after a reload shows no tip (the seen flag was persisted and the still-
         empty tag deck does not re-arm it).
    """
    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub_user_created.id

    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    page.evaluate(_SEED_CREATE_UTUB_AND_ADD_URL_SEEN)

    select_utub_by_id(page=page, utub_id=utub_id)
    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)

    # Act path: tapping the anchor dismisses the tip (mark seen) and, because the
    # dismiss handler never preventDefaults, the anchor's own click handler still
    # opens the create-tag form.
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_CREATE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)

    # Seen flag persisted -> re-selecting the UTub after a fresh load shows no tip
    # (the tag deck is still empty, so the addTag tip is not re-armed).
    page.reload()
    select_utub_by_id(page=page, utub_id=utub_id)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )


def test_add_tag_nudge_rearms_after_adding_first_tag_via_form(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a returning user (addTag tip already seen) whose one UTub holds a URL but
          no tags — the tag deck holds no content
    WHEN they add the first tag through the real create-UTub-tag form
    THEN the ``TAG_DECK_CHANGED`` event emitted by the create success path re-arms
         the addTag tip LIVE — its persisted seen flag is cleared the moment the
         deck gains content, with no reload — so the tip becomes eligible again if
         the user later re-empties the tag deck.

    This isolates the ``tags/create.ts`` emit site (the analog of the addUrl
    create-form re-arm test). The re-arm is asserted via the localStorage seen
    flag rather than a re-shown bubble: the ONLY path that empties the tag deck
    (UTub-tag deletion) runs inside the tag deck's "manage tags" mode, which hides
    ``#utubTagBtnCreate`` (inside ``#utubTagStandardBtns``) at the exact instant
    ``TAG_DECK_CHANGED`` fires, so the engine correctly withholds a bubble over the
    hidden anchor — making an E2E delete-re-show impossible by design. The
    delete-driven re-show is covered at the Vitest unit level (Step 4). The seen
    flag is seeded with a ONE-TIME ``page.evaluate`` (NOT ``add_init_script``) so
    it is not re-applied on any later navigation.
    """
    _, cli_runner = runner
    app = provide_app
    add_mock_urls(cli_runner, [MOCK_URL_STRINGS[0]])
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub_user_created.id

    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    # Seed all three prior tips as seen via a ONE-TIME evaluate (persisted to
    # localStorage, not re-applied on later navigations).
    page.evaluate(_SEED_CREATE_UTUB_ADD_URL_ADD_TAG_SEEN)

    # Select the empty-of-tags UTub: UTUB_SELECTED with tags.length === 0 -> no
    # re-arm (empty deck) and the already-seen addTag tip stays hidden.
    select_utub_by_id(page=page, utub_id=utub_id)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )
    # Precondition: the addTag seen flag is still set going into the create.
    assert page.evaluate(_READ_ADD_TAG_SEEN) is True

    # Add the first tag through the real create-UTub-tag form. On success
    # tags/create.ts emits TAG_DECK_CHANGED (emit-after-setState), whose live
    # re-eval clears (re-arms) the addTag seen flag now that the deck holds content.
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_CREATE)
    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    page.keyboard.type(UTS.TEST_TAG_NAME_1)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)

    # The addTag seen flag was cleared LIVE by the create's TAG_DECK_CHANGED — no
    # reload, no re-selection — proving the create emit site drives the re-arm.
    assert page.evaluate(_READ_ADD_TAG_SEEN) is False
