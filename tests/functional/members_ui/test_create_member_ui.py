import re

from flask import Flask
from playwright.sync_api import Page, expect
import pytest

from backend.cli.mock_constants import USERNAME_BASE
from backend.models.users import Users
from backend.utils.strings.user_strs import (
    MEMBER_ADD_SHARES_COUNT_ONE,
    MEMBER_ADD_SUMMARY_ADDED_ONE,
    MEMBER_ADD_SUMMARY_FAILED_ONE,
    MEMBER_FAILURE,
    USER_FAILURE,
)
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    add_existing_user_as_member_of_utub,
    click_add_member_submit,
    close_add_member_combobox,
    get_all_member_usernames,
    get_staged_chip,
    hold_member_add_response,
    member_badge_by_username,
    open_add_member_combobox,
    seed_co_members_for_owner,
    stage_co_member_suggestion,
    stage_outsider_username,
    type_in_member_combobox,
)
from tests.functional.playwright_assert_utils import (
    assert_login_with_username,
    assert_on_429_page,
    assert_panel_visibility_mobile,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    add_forced_rate_limit_header,
    click_on_navbar,
    invalidate_csrf_token_on_page,
    select_utub_by_name,
    wait_for_class_to_be_removed,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.members_ui

# Two existing users made co-members of user 1 (they share a seeded OTHER UTub
# with user 1 but are NOT in the target UTub), so they surface as candidates.
CO_MEMBER_A = USERNAME_BASE + "2"
CO_MEMBER_B = USERNAME_BASE + "3"
# An existing user who shares NO UTub with user 1 and is not a member -> not a
# co-member candidate, so typing it falls through to the amber outsider row.
OUTSIDER_USER = USERNAME_BASE + "4"
# A username no user owns -> the outsider add resolves to USER_NOT_EXIST.
NONEXISTENT_USER = USERNAME_BASE + "999A"

_DUAL_LOADING_RING_RE = re.compile(r"(^|\s)dual-loading-ring(\s|$)")
_CHIP_FAILED_RE = re.compile(r"(^|\s)memberAddStagedChipFailed(\s|$)")
# The per-chip failure marker is an inline warning SVG rendered into the chip's
# decorative status slot (bi-exclamation-triangle-fill — this project ships no
# icon font, so every `bi` icon is inline SVG).
_STATUS_WARNING_ICON = (
    f"{HPL.MEMBER_COMBOBOX_STAGED_CHIP_STATUS} svg.bi-exclamation-triangle-fill"
)


def _login_owner_with_co_members(
    *, app: Flask, page: Page, co_member_usernames: list[str]
) -> None:
    """Log user 1 into their created UTub after seeding co-member candidates.

    The target UTub is captured BEFORE seeding the shared UTub so a later
    unordered `get_utub_this_user_created` cannot return the seeded one; the
    target is always the original mock UTub.
    """
    target_utub = get_utub_this_user_created(app, 1)
    seed_co_members_for_owner(
        app=app, owner_id=1, co_member_usernames=co_member_usernames
    )
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=1, utub_name=target_utub.name
    )


def test_open_add_member_combobox(page: Page, create_test_utubs, provide_app: Flask):
    """
    GIVEN a UTub owner with the UTub selected
    WHEN the owner clicks the add-member opener
    THEN the combobox mounts with a visible, focused input and the opener has
         transformed in place into a Cancel affordance.
    """
    app = provide_app
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    combobox_input = open_add_member_combobox(page=page)
    expect(combobox_input).to_be_visible()
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.MEMBER_COMBOBOX_CANCEL_BTN
    )
    # The member list is hidden while the combobox owns the deck's input row.
    wait_until_hidden(page=page, css_selector=HPL.DISPLAY_MEMBER_WRAP)


def test_cancel_combobox_via_cancel_button(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN the add-member combobox is open
    WHEN the owner clicks the in-place Cancel button
    THEN the combobox tears down and the member list is restored.
    """
    app = provide_app
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    open_add_member_combobox(page=page)
    wait_then_click_element(page=page, css_selector=HPL.MEMBER_COMBOBOX_CANCEL_BTN)

    wait_until_hidden(page=page, css_selector=HPL.MEMBER_COMBOBOX_WRAP)
    wait_until_visible_css_selector(page=page, css_selector=HPL.DISPLAY_MEMBER_WRAP)


def test_cancel_combobox_via_two_stage_escape(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN the add-member combobox is open with the dropdown showing suggestions
    WHEN the owner presses Escape twice
    THEN the first Escape closes only the dropdown and the second cancels the
         combobox, returning focus to the (restored) opener button.
    """
    app = provide_app
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    combobox_input = open_add_member_combobox(page=page)
    type_in_member_combobox(page=page, text=CO_MEMBER_A)
    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_COMBOBOX_OPTION)

    # First Escape closes just the dropdown; the combobox input stays mounted.
    combobox_input.press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.MEMBER_COMBOBOX_LISTBOX)
    expect(page.locator(HPL.MEMBER_COMBOBOX_INPUT)).to_be_visible()

    # Second Escape cancels the combobox and returns focus to the opener.
    combobox_input.press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.MEMBER_COMBOBOX_WRAP)
    wait_until_in_focus(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)


def test_co_member_suggestions_appear_with_count_pill(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub owner with a seeded co-member (sharing exactly one other UTub)
    WHEN the owner opens the add UI and types the co-member's username
    THEN a suggestion row renders with the right-pinned "shares N UTubs" count
         pill.
    """
    app = provide_app
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    open_add_member_combobox(page=page)
    type_in_member_combobox(page=page, text=CO_MEMBER_A)

    suggestion = page.locator(HPL.MEMBER_COMBOBOX_OPTION).filter(
        has=page.locator(f"{HPL.MEMBER_COMBOBOX_OPTION_LABEL}:text-is('{CO_MEMBER_A}')")
    )
    expect(suggestion).to_be_visible()
    count_pill = suggestion.locator(HPL.MEMBER_COMBOBOX_OPTION_COUNT)
    expect(count_pill).to_be_visible()
    expect(count_pill).to_have_text(MEMBER_ADD_SHARES_COUNT_ONE)


def test_add_co_member_via_suggestion_shows_ring_then_badge(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a staged co-member chip (source=search_result)
    WHEN the owner clicks "Add 1" and the POST is briefly delayed
    THEN the chip shows the delayed loading ring in flight, then resolves: the
         new member badge appears in the deck and the staged chip is cleared.
    """
    app = provide_app
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    open_add_member_combobox(page=page)
    chip = stage_co_member_suggestion(page=page, username=CO_MEMBER_A)
    expect(chip).to_be_visible()

    # Hold the POST so the transient per-chip ring is reliably observable, then
    # release it once observed.
    release_add = hold_member_add_response(page=page)
    click_add_member_submit(page=page)

    ring = chip.locator(HPL.MEMBER_COMBOBOX_STAGED_CHIP_RING)
    expect(ring).to_have_class(_DUAL_LOADING_RING_RE)
    release_add()

    # After settle: the succeeded chip is removed and the badge is appended to
    # the (still-open-combobox-hidden) deck. Close the combobox to reveal it.
    badge = member_badge_by_username(page=page, username=CO_MEMBER_A)
    expect(badge).to_be_attached()
    expect(get_staged_chip(page=page, username=CO_MEMBER_A)).to_have_count(0)

    close_add_member_combobox(page=page)
    expect(badge).to_be_visible()
    assert CO_MEMBER_A in get_all_member_usernames(page=page)


def test_add_outsider_by_exact_username(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Regression for today's exact-username add path.

    GIVEN an owner with co-members seeded (so the combobox has a candidate list)
    WHEN they type a username that is NOT a co-member and stage the amber
         outsider row, then submit
    THEN the exact-username add succeeds and the member badge appears.
    """
    app = provide_app
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    open_add_member_combobox(page=page)
    chip = stage_outsider_username(page=page, username=OUTSIDER_USER)
    expect(chip).to_have_class(re.compile(r"memberAddStagedChipOutsider"))
    # Outsider chips carry a "NEW" marker (mock State 2).
    expect(chip.locator(HPL.MEMBER_COMBOBOX_STAGED_CHIP_NEW)).to_be_visible()

    click_add_member_submit(page=page)

    # Success clears the chip; the badge lands in the combobox-hidden deck.
    badge = member_badge_by_username(page=page, username=OUTSIDER_USER)
    expect(badge).to_be_attached()
    expect(get_staged_chip(page=page, username=OUTSIDER_USER)).to_have_count(0)

    close_add_member_combobox(page=page)
    expect(badge).to_be_visible()
    assert OUTSIDER_USER in get_all_member_usernames(page=page)


def test_outsider_nonexistent_user_shows_inline_error_and_ring_clears(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a staged outsider chip for a username no user owns
    WHEN the owner submits with the POST briefly delayed
    THEN the chip shows the ring in flight, then the ring clears and the chip is
         marked failed (red warning icon + USER_NOT_EXIST reason in its `title`
         tooltip) while staying staged, and a count-based failure summary renders
         under the strip (siblings unaffected).
    """
    app = provide_app
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    open_add_member_combobox(page=page)
    chip = stage_outsider_username(page=page, username=NONEXISTENT_USER)

    release_add = hold_member_add_response(page=page)
    click_add_member_submit(page=page)

    ring = chip.locator(HPL.MEMBER_COMBOBOX_STAGED_CHIP_RING)
    expect(ring).to_have_class(_DUAL_LOADING_RING_RE)
    release_add()

    # After settle: ring class cleared; chip marked failed with the red warning
    # icon + reason tooltip, retained; count-based summary shown under the strip.
    expect(chip).to_have_class(_CHIP_FAILED_RE)
    expect(chip.locator(_STATUS_WARNING_ICON)).to_be_visible()
    expect(chip).to_have_attribute("title", USER_FAILURE.USER_NOT_EXIST)
    expect(ring).not_to_have_class(_DUAL_LOADING_RING_RE)
    expect(get_staged_chip(page=page, username=NONEXISTENT_USER)).to_have_count(1)
    expect(page.locator(HPL.MEMBER_COMBOBOX_MESSAGE)).to_have_text(
        MEMBER_ADD_SUMMARY_FAILED_ONE
    )


def test_duplicate_member_shows_inline_error(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a co-member chip staged from the candidate list
    WHEN that user is added to the target UTub server-side before the batch POST
         fires (a stale-candidate race)
    THEN the per-chip POST resolves to MEMBER_ALREADY_IN_UTUB, marking the
         still-staged chip failed (red warning icon + reason in its `title`
         tooltip) with a count-based failure summary under the strip.
    """
    app = provide_app
    target_utub = get_utub_this_user_created(app, 1)
    seed_co_members_for_owner(app=app, owner_id=1, co_member_usernames=[CO_MEMBER_A])
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=1, utub_name=target_utub.name
    )

    open_add_member_combobox(page=page)
    chip = stage_co_member_suggestion(page=page, username=CO_MEMBER_A)

    # Make the staged co-member an actual member of the target AFTER the combobox
    # already staged it from the (now-stale) candidate list.
    add_existing_user_as_member_of_utub(
        app=app, utub_id=target_utub.id, username=CO_MEMBER_A
    )

    click_add_member_submit(page=page)

    expect(chip).to_have_class(_CHIP_FAILED_RE)
    expect(chip.locator(_STATUS_WARNING_ICON)).to_be_visible()
    expect(chip).to_have_attribute("title", MEMBER_FAILURE.MEMBER_ALREADY_IN_UTUB)
    expect(get_staged_chip(page=page, username=CO_MEMBER_A)).to_have_count(1)
    expect(page.locator(HPL.MEMBER_COMBOBOX_MESSAGE)).to_have_text(
        MEMBER_ADD_SUMMARY_FAILED_ONE
    )


def test_mixed_outcome_batch_add_resolves_each_chip_independently(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN two staged chips in one batch: a valid co-member and a nonexistent user
    WHEN the owner submits the batch once
    THEN each chip resolves independently — the valid one succeeds (badge
         appended, chip cleared) while the nonexistent one is marked failed
         (red warning icon + USER_NOT_EXIST reason in its `title` tooltip) and
         stays staged; the batched count-based summary recaps both outcomes.
    """
    app = provide_app
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    open_add_member_combobox(page=page)
    stage_co_member_suggestion(page=page, username=CO_MEMBER_A)
    bad_chip = stage_outsider_username(page=page, username=NONEXISTENT_USER)

    click_add_member_submit(page=page)

    # The good chip succeeds: its badge is appended and the chip is cleared.
    good_badge = member_badge_by_username(page=page, username=CO_MEMBER_A)
    expect(good_badge).to_be_attached()
    expect(get_staged_chip(page=page, username=CO_MEMBER_A)).to_have_count(0)

    # The bad chip fails independently: retained with the red warning icon +
    # reason tooltip, siblings unaffected.
    expect(bad_chip).to_have_class(_CHIP_FAILED_RE)
    expect(bad_chip.locator(_STATUS_WARNING_ICON)).to_be_visible()
    expect(bad_chip).to_have_attribute("title", USER_FAILURE.USER_NOT_EXIST)
    expect(get_staged_chip(page=page, username=NONEXISTENT_USER)).to_have_count(1)

    # Batched count-based summary recaps both outcomes: one added, one failed.
    expect(page.locator(HPL.MEMBER_COMBOBOX_MESSAGE)).to_have_text(
        f"{MEMBER_ADD_SUMMARY_ADDED_ONE}, {MEMBER_ADD_SUMMARY_FAILED_ONE}"
    )


def test_already_member_hint_suppresses_outsider_row(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub whose members already include the owner + others
    WHEN the owner types an exact current-member username
    THEN the dead-end outsider row is suppressed in favor of an
         "is already a member" hint row, and no chip can be staged.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_add_member_combobox(page=page)
    type_in_member_combobox(page=page, text=CO_MEMBER_A)

    # A hint row renders; the amber outsider row does not.
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.MEMBER_COMBOBOX_LISTBOX_HINT
    )
    expect(page.locator(HPL.MEMBER_COMBOBOX_LISTBOX_HINT)).to_contain_text(CO_MEMBER_A)
    expect(page.locator(HPL.MEMBER_COMBOBOX_OPTION_OUTSIDER)).to_have_count(0)


def test_keyboard_arrow_down_enter_stages_suggestion(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN the combobox open with a single co-member suggestion visible
    WHEN the owner presses ArrowDown then Enter
    THEN the active suggestion is staged as a chip.
    """
    app = provide_app
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    combobox_input = open_add_member_combobox(page=page)
    type_in_member_combobox(page=page, text=CO_MEMBER_A)
    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_COMBOBOX_OPTION)

    combobox_input.press("ArrowDown")
    combobox_input.press("Enter")

    expect(get_staged_chip(page=page, username=CO_MEMBER_A)).to_be_visible()


def test_backspace_on_empty_input_removes_last_chip(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN two staged chips and an empty input
    WHEN the owner presses Backspace
    THEN the most-recently staged chip is removed and the first remains.
    """
    app = provide_app
    _login_owner_with_co_members(
        app=app, page=page, co_member_usernames=[CO_MEMBER_A, CO_MEMBER_B]
    )

    combobox_input = open_add_member_combobox(page=page)
    stage_co_member_suggestion(page=page, username=CO_MEMBER_A)
    stage_co_member_suggestion(page=page, username=CO_MEMBER_B)

    combobox_input.press("Backspace")

    expect(get_staged_chip(page=page, username=CO_MEMBER_B)).to_have_count(0)
    expect(get_staged_chip(page=page, username=CO_MEMBER_A)).to_have_count(1)


def test_add_member_via_enter_key_with_staged_chip(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a single staged chip and an empty input
    WHEN the owner presses Enter (empty input + >=1 staged -> batch submit)
    THEN the batch add fires and the member badge appears.
    """
    app = provide_app
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    combobox_input = open_add_member_combobox(page=page)
    stage_co_member_suggestion(page=page, username=CO_MEMBER_A)

    combobox_input.press("Enter")

    badge = member_badge_by_username(page=page, username=CO_MEMBER_A)
    expect(badge).to_be_attached()
    close_add_member_combobox(page=page)
    expect(badge).to_be_visible()
    assert CO_MEMBER_A in get_all_member_usernames(page=page)


def test_add_member_rate_limited_shows_429_page(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a staged chip
    WHEN the add POST is forced to hit the per-IP rate limit
    THEN the 429 error page is shown (mirrors the old single-input 429 test).
    """
    app = provide_app
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    open_add_member_combobox(page=page)
    stage_outsider_username(page=page, username=OUTSIDER_USER)

    # Force the header AFTER the co-member GET (on open) so only the add POST 429s.
    add_forced_rate_limit_header(page=page)
    click_add_member_submit(page=page)
    assert_on_429_page(page=page)


def test_add_member_invalid_csrf_token(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a staged chip
    WHEN the add POST is submitted with an invalidated CSRF token
    THEN U4I returns 403, the page reloads to the login screen.
    """
    app = provide_app
    with app.app_context():
        username = Users.query.get(1).username
    _login_owner_with_co_members(app=app, page=page, co_member_usernames=[CO_MEMBER_A])

    open_add_member_combobox(page=page)
    stage_outsider_username(page=page, username=OUTSIDER_USER)

    invalidate_csrf_token_on_page(page=page)
    click_add_member_submit(page=page)
    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    wait_until_hidden(page=page, css_selector=HPL.MEMBER_COMBOBOX_WRAP)
    assert_login_with_username(page=page, username=username)


def test_non_owner_cannot_open_add_ui(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a user who is a member (not owner) of the selected UTub
    THEN the add-member opener is not shown to them (owner-only gate).
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    select_utub_by_name(page=page, utub_name=utub_user_member_of.name)
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)


def test_add_member_combobox_opens_on_mobile(
    page_mobile_portrait: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub owner on a mobile-portrait (coarse-pointer) viewport
    WHEN they navigate to the member deck and open the add-member combobox
    THEN the input opens visible + focused; option rows and the "Add N" submit
         meet the 44px touch-target minimum; and staged chips wrap rather than
         overflow the combobox width.
    """
    app = provide_app
    user_id = 1
    target_utub = get_utub_this_user_created(app, user_id)
    seed_co_members_for_owner(
        app=app, owner_id=user_id, co_member_usernames=[CO_MEMBER_A, CO_MEMBER_B]
    )
    login_user_and_select_utub_by_utubid_mobile(
        app=app,
        page=page_mobile_portrait,
        user_id=user_id,
        utub_id=target_utub.id,
    )

    click_on_navbar(page=page_mobile_portrait)
    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.NAVBAR_MEMBER_DECK
    )
    wait_for_class_to_be_removed(
        page=page_mobile_portrait,
        css_selector=HPL.NAVBAR_DROPDOWN,
        class_name="collapsing",
    )
    assert_panel_visibility_mobile(
        page=page_mobile_portrait, visible_deck=Decks.MEMBERS
    )

    # Combobox opens: input visible + focused.
    combobox_input = open_add_member_combobox(page=page_mobile_portrait)
    expect(combobox_input).to_be_visible()
    wait_until_in_focus(
        page=page_mobile_portrait, css_selector=HPL.MEMBER_COMBOBOX_INPUT
    )

    # Option rows meet the coarse-pointer 44px (2.75rem) touch target.
    type_in_member_combobox(page=page_mobile_portrait, text=CO_MEMBER_A)
    option = page_mobile_portrait.locator(HPL.MEMBER_COMBOBOX_OPTION).first
    expect(option).to_be_visible()
    option_box = option.bounding_box()
    assert option_box is not None and option_box["height"] >= 44

    # Stage two chips so the strip must wrap; the "Add N" submit is now visible.
    stage_co_member_suggestion(page=page_mobile_portrait, username=CO_MEMBER_A)
    stage_co_member_suggestion(page=page_mobile_portrait, username=CO_MEMBER_B)

    submit = page_mobile_portrait.locator(HPL.MEMBER_COMBOBOX_SUBMIT)
    expect(submit).to_be_visible()
    submit_box = submit.bounding_box()
    assert submit_box is not None and submit_box["height"] >= 44

    # Staged chips wrap (flex-wrap:wrap on the combobox row) rather than overflow.
    flex_wrap = page_mobile_portrait.locator(HPL.MEMBER_COMBOBOX).first.evaluate(
        "element => getComputedStyle(element).flexWrap"
    )
    assert flex_wrap == "wrap"
