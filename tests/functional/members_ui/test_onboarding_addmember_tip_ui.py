"""End-to-end (Playwright) coverage for the addMember onboarding nudge (desktop).

Mirrors the shipped Create-UTub / Add-URL nudge flows
(``utubs_ui/test_onboarding_nudges_ui.py``) for the addMember tip: it proves the
bubble renders on ``#memberBtnCreate`` with its bridged copy for a lone
owner/co-creator, that it is NOT shown to a plain member (the
``isCurrentUserOwner || isCoCreator`` gate), and that the ``MEMBER_DECK_CHANGED``
re-arm re-shows it after the last extra member is removed.

addMember eligibility (``nudges.ts`` registry):
``(isCurrentUserOwner || isCoCreator) && active UTub && members.length <= 1``
(the store's ``members`` counts the owner, so a lone owner ⇒ length 1);
``hasContent`` = ``members.length > 1``. The createUtub + addUrl + addTag tips are
seeded as seen so the curated sequence has already advanced to addMember.
"""

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.cli.mock_constants import USERNAME_BASE
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_user_as_plain_member_of_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    add_existing_user_as_member_of_utub,
    delete_member_active_utub,
)
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    select_utub_by_id,
    wait_then_click_element,
    wait_until_css_property,
    wait_until_hidden,
)

pytestmark = pytest.mark.members_ui

USER_ID_FOR_TEST = 1
# An existing mock user to add as the "last" extra member for the re-arm case.
OTHER_MEMBER_USERNAME = USERNAME_BASE + "2"

# All prior tips seeded as already seen so the curated sequence has advanced to
# addMember; a ONE-TIME evaluate (not add_init_script) so the value is not
# re-applied on later navigations that would mask a re-arm.
_SEED_PRIOR_TIPS_SEEN = (
    "localStorage.setItem('u4i:onboardingSeen',"
    " JSON.stringify({createUtub: true, addUrl: true, addTag: true}))"
)
_SEED_PRIOR_TIPS_AND_ADD_MEMBER_SEEN = (
    "localStorage.setItem('u4i:onboardingSeen',"
    " JSON.stringify({createUtub: true, addUrl: true, addTag: true,"
    " addMember: true}))"
)


def test_add_member_nudge_shows_with_bridged_copy(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a lone owner of a UTub (no other members; prior tips already seen)
    WHEN they select that UTub and the onboarding system re-evaluates
    THEN the addMember nudge bubble is visible on #memberBtnCreate with the bridged
         title/body copy read via APP_CONFIG.strings.*
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    page.evaluate(_SEED_PRIOR_TIPS_SEEN)

    select_utub_by_id(page=page, utub_id=utub_user_created.id)

    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_ADD_MEMBER_TIP_TITLE
    )
    expect(page.locator(HPL.ONBOARDING_NUDGE_BODY)).to_have_text(
        UTS.ONBOARDING_ADD_MEMBER_TIP_BODY
    )


def test_add_member_nudge_not_shown_for_plain_member(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user who is only a plain MEMBER (not owner/co-creator) of the selected
          UTub (prior tips already seen)
    WHEN they select that UTub
    THEN the addMember nudge never appears — the ``isCurrentUserOwner ||
         isCoCreator`` gate keeps a plain member from being nudged to add members.

    The plain-member row is inserted directly (add_user_as_plain_member_of_utub)
    rather than via create_test_utubmembers, so exactly one membership is scoped
    here: user 1 can select the UTub, yet stays a MEMBER so the negative gate is
    genuinely exercised.
    """
    app = provide_app
    utub_not_created_by_user = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST)
    add_user_as_plain_member_of_utub(app, USER_ID_FOR_TEST, utub_not_created_by_user.id)

    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    page.evaluate(_SEED_PRIOR_TIPS_SEEN)

    select_utub_by_id(page=page, utub_id=utub_not_created_by_user.id)

    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )


def test_add_member_nudge_rearms_after_removing_last_member(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a returning owner (addMember tip already seen) whose UTub currently holds
          one other member — i.e. the member deck holds content
    WHEN they remove that last extra member, returning to the lone-owner state
    THEN the addMember nudge RE-SHOWS IMMEDIATELY — no reload — proving the
         ``MEMBER_DECK_CHANGED`` event drives the re-arm/re-show live.

    Content-load-then-empty rhythm (mirrors the addUrl delete re-arm test):
      1. Content load: selecting the UTub while a second member is present emits
         ``UTUB_SELECTED`` with ``members.length > 1``, a re-eval that clears
         (re-arms) the seeded ``addMember`` seen flag. The tip is not eligible
         (deck has a second member) so it does NOT show yet.
      2. Empty: removing that member emits ``MEMBER_DECK_CHANGED`` (emit-after-
         setState). With the flag already cleared and only the owner left, the
         addMember tip is eligible again and re-shows.
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub_user_created.id
    add_existing_user_as_member_of_utub(
        app=app, utub_id=utub_id, username=OTHER_MEMBER_USERNAME
    )

    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    page.evaluate(_SEED_PRIOR_TIPS_AND_ADD_MEMBER_SEEN)

    # Content load: select the UTub while the second member is present ->
    # UTUB_SELECTED with members.length > 1 -> the addMember seen flag is cleared
    # (re-armed). The tip is not eligible (deck has a second member), so hidden.
    select_utub_by_id(page=page, utub_id=utub_id)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP
    )

    # Remove the last extra member via the real delete flow (open kebab -> Remove
    # member -> confirm modal -> submit).
    delete_member_active_utub(page=page, member_name=OTHER_MEMBER_USERNAME)
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    # removeMemberSuccess emitted MEMBER_DECK_CHANGED, re-evaluating the engine
    # LIVE. With the flag cleared during the content load and only the owner left,
    # the addMember tip is eligible again and re-shows with its bridged copy.
    assert_visible_css_selector(page=page, css_selector=HPL.ONBOARDING_NUDGE_TOOLTIP)
    expect(page.locator(HPL.ONBOARDING_NUDGE_TITLE)).to_have_text(
        UTS.ONBOARDING_ADD_MEMBER_TIP_TITLE
    )
    expect(page.locator(HPL.ONBOARDING_NUDGE_BODY)).to_have_text(
        UTS.ONBOARDING_ADD_MEMBER_TIP_BODY
    )
