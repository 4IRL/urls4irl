import re

from flask import Flask
from playwright.sync_api import Page, expect
import pytest

from backend.models.users import Users
from backend.utils.strings.user_strs import TRANSFER_OWNER_SUCCESS
from tests.functional.db_utils import (
    get_other_member_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    force_transfer_400_response,
    open_transfer_ownership_picker,
    pick_new_owner,
    seed_co_creator_in_utub,
)
from tests.functional.playwright_assert_utils import (
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    force_next_patch_ajax_failure_no_navigate,
    get_selected_utub_id,
    invalidate_csrf_token_on_page,
    wait_then_click_element,
    wait_until_css_property,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.members_ui

# A message distinct enough that asserting it in the live region proves the
# server text (not a generic fallback) surfaced. Fulfilled by
# force_transfer_400_response, standing in for the server-side TARGET_ALREADY_OWNER
# guard (the picker excludes the current owner, so the UI cannot reach it directly).
_ALREADY_OWNER_MESSAGE = "That member is already the owner of this UTub."


def _username_for_user_id(*, app: Flask, user_id: int) -> str:
    with app.app_context():
        return Users.query.get(user_id).username


def _submit_confirm_modal(*, page: Page) -> None:
    """Gate on the modal fade-in settling (opacity==1) before clicking submit.

    Clicking while Bootstrap's show-transition is still running causes the
    subsequent modal("hide") to be dropped as an overlapping transition, leaving
    the modal visible and racing wait_until_hidden (mirrors the delete/role tests).
    """
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)


# --------------------------------------------------------------------------- #
# Gating
# --------------------------------------------------------------------------- #


def test_owner_with_members_sees_transfer_button(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub that has at least one other member
    WHEN they view the members panel
    THEN the standalone "Transfer ownership" trigger is shown
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    expect(page.locator(HPL.MEMBER_BTN_TRANSFER_OWNER)).to_be_visible()


def test_co_owner_viewer_sees_no_transfer_button(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user is a CO_CREATOR (co-owner) of a UTub they did not create
    WHEN they view the members panel
    THEN the "Transfer ownership" trigger is NOT shown (owner-only affordance)
    """
    app = provide_app

    user_id = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    viewer_username = _username_for_user_id(app=app, user_id=user_id)
    seed_co_creator_in_utub(
        app=app, utub_id=utub_user_member_of.id, username=viewer_username
    )
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_member_of.name
    )

    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_ROW_ROLE_ICON)
    expect(page.locator(HPL.MEMBER_BTN_TRANSFER_OWNER)).to_be_hidden()


def test_plain_member_viewer_sees_no_transfer_button(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user is a plain member of a UTub they did not create
    WHEN they view the members panel
    THEN the "Transfer ownership" trigger is NOT shown
    """
    app = provide_app

    user_id = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_member_of.name
    )

    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_ROW_ROLE_ICON)
    expect(page.locator(HPL.MEMBER_BTN_TRANSFER_OWNER)).to_be_hidden()


def test_sole_owner_utub_sees_no_transfer_button(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with no other members (sole owner)
    WHEN they view the members panel
    THEN the "Transfer ownership" trigger is NOT shown (no eligible target)
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    # The owner badge renders even with no other members — wait on it so the
    # members deck is fully built before asserting the trigger stays hidden.
    expect(page.locator(HPL.BADGE_OWNER)).to_be_visible()
    expect(page.locator(HPL.MEMBER_BTN_TRANSFER_OWNER)).to_be_hidden()


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #


def test_transfer_ownership_happy_path(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with at least one other member
    WHEN they open the transfer picker, filter, pick a member, confirm, and submit
    THEN the submit button disables (double-submit guard), the chosen member becomes
        owner (diamond-fill), the acting user is demoted to co-owner (diamond-half)
        in the member list AND on the left UTub-deck selector (which stays .active),
        and the owner-only affordances give way to the Leave button
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)
    with app.app_context():
        new_owner_id = other_member.id
        new_owner_username = other_member.username

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    utub_id = get_selected_utub_id(page=page)

    open_transfer_ownership_picker(page=page)

    # Filter the picker to the target member, then pick + confirm to open the modal.
    page.locator(HPL.TRANSFER_PICKER_FILTER_INPUT).fill(new_owner_username)
    pick_new_owner(page=page, member_id=new_owner_id)

    _submit_confirm_modal(page=page)

    # DD-11 parity: submit disables immediately after click (double-submit guard).
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_disabled()

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    # Chosen member is now the owner (diamond-fill). Re-query rather than reusing a
    # captured Locator — the full refetch rebuilds the member deck.
    expect(
        page.locator(
            f'{HPL.BADGES_MEMBERS}[memberid="{new_owner_id}"] svg.bi-diamond-fill'
        )
    ).to_be_visible()

    # The acting user is demoted to co-owner (diamond-half) in the member list.
    expect(
        page.locator(f'{HPL.BADGES_MEMBERS}[memberid="{user_id}"] svg.bi-diamond-half')
    ).to_be_visible()

    # The left UTub-deck selector's role icon for this UTub flips to co-owner too
    # (the one reconciliation point the state-level refetch alone doesn't prove at
    # the rendered-DOM level), and the row keeps its .active class (DD-9 re-add).
    utub_selector = page.locator(f'{HPL.SELECTORS_UTUB}[utubid="{utub_id}"]')
    expect(utub_selector.locator("svg.bi-diamond-half")).to_be_visible()
    expect(utub_selector).to_have_class(re.compile(r"\bactive\b"))

    # Owner-only affordances are gone; the Leave button appears for the co-owner.
    expect(page.locator(HPL.MEMBER_BTN_TRANSFER_OWNER)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_UTUB_DELETE)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_UTUB_LEAVE)).to_be_visible()

    # The success announcement names the new owner in the reused live region.
    expect(page.locator("#MemberRowActionAnnouncement")).to_have_text(
        TRANSFER_OWNER_SUCCESS.replace("{{ username }}", new_owner_username)
    )


# --------------------------------------------------------------------------- #
# Keyboard operability
# --------------------------------------------------------------------------- #


def test_transfer_picker_keyboard_open_navigate_escape(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with at least one other member
    WHEN they focus the Transfer trigger, press Enter, ArrowDown, Enter, then Escape
    THEN Enter opens the picker, ArrowDown/Enter stages a member (confirm enabled),
        and Escape closes the picker and returns focus to the trigger
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    trigger = page.locator(HPL.MEMBER_BTN_TRANSFER_OWNER)
    expect(trigger).to_be_visible()
    trigger.focus()
    expect(trigger).to_be_focused()

    # Enter fires the trigger's click handler, opening the picker (first row focused).
    page.keyboard.press("Enter")
    wait_until_visible_css_selector(page=page, css_selector=HPL.TRANSFER_PICKER_LISTBOX)

    # ArrowDown roves, Enter (on keyup) stages the focused member — confirm enables.
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator(HPL.TRANSFER_PICKER_CONFIRM_BTN)).to_be_enabled()

    # Escape closes the picker and returns focus to the trigger.
    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.TRANSFER_PICKER_LISTBOX)
    expect(trigger).to_be_focused()


# --------------------------------------------------------------------------- #
# Sad paths
# --------------------------------------------------------------------------- #


def test_transfer_ownership_rate_limits(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner has staged a transfer and the confirm modal is open but they are
        rate limited
    WHEN they submit the confirm modal
    THEN the 429 error page is shown
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)
    with app.app_context():
        new_owner_id = other_member.id
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_transfer_ownership_picker(page=page)
    pick_new_owner(page=page, member_id=new_owner_id)

    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    assert_on_429_page(page=page)


def test_transfer_ownership_invalid_csrf_token(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner has staged a transfer and the confirm modal is open
    WHEN they submit with an invalid CSRF token
    THEN U4I responds with the 403 body-swap and reload
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)
    with app.app_context():
        new_owner_id = other_member.id
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_transfer_ownership_picker(page=page)
    pick_new_owner(page=page, member_id=new_owner_id)

    invalidate_csrf_token_on_page(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    assert_visited_403_on_invalid_csrf_and_reload(page=page)


def test_transfer_ownership_submit_button_reenables_on_server_error(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner has staged a transfer and the confirm modal is open
    WHEN the PATCH request fails with a 500 server error
    THEN the #modalSubmit button is re-enabled so the user can retry
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)
    with app.app_context():
        new_owner_id = other_member.id
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_transfer_ownership_picker(page=page)
    pick_new_owner(page=page, member_id=new_owner_id)

    force_next_patch_ajax_failure_no_navigate(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_enabled()


def test_transfer_ownership_target_already_owner_surfaces_message(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner has staged a transfer and the confirm modal is open
    WHEN the PATCH is rejected 400 (target-already-owner / already-transferred guard)
    THEN the panel surfaces the server message in the row-action live region and
        does NOT redirect away
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)
    with app.app_context():
        new_owner_id = other_member.id
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_transfer_ownership_picker(page=page)
    pick_new_owner(page=page, member_id=new_owner_id)

    force_transfer_400_response(page=page, message=_ALREADY_OWNER_MESSAGE)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # The server message is surfaced via the members-panel row-action live region,
    # not a redirect — the members deck stays put.
    expect(page.locator("#MemberRowActionAnnouncement")).to_have_text(
        _ALREADY_OWNER_MESSAGE
    )
    expect(page.locator(HPL.MEMBER_DECK)).to_be_visible()


# --------------------------------------------------------------------------- #
# Cross-surface suppression (DD-6 / DD-7 / DD-11)
# --------------------------------------------------------------------------- #


def test_transfer_picker_open_suppresses_member_row_kebab(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members and opens the transfer picker
    WHEN a background member row's kebab would be clicked
    THEN the #MemberDeck.transfer-picker-open CSS suppression makes the kebab inert
        (pointer-events: none) in a real browser — the gap Vitest's class-toggle
        assertions alone leave open
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_transfer_ownership_picker(page=page)

    # The background member-row kebabs are visually dimmed AND click-inert while the
    # picker is open — assert the computed pointer-events using the repo's idiom
    # (test_locked_utub_ui.py's pointer-events assertion helper).
    wait_until_css_property(
        page=page,
        css_selector=HPL.MEMBER_ROW_KEBAB,
        css_property="pointer-events",
        expected_value="none",
    )


def test_transfer_picker_cancel_closes_and_restores_focus(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with at least one other member and opens the picker
    WHEN they click the picker's Cancel button
    THEN the picker's listbox and mount close AND focus returns to the trigger
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_transfer_ownership_picker(page=page)
    expect(page.locator(HPL.TRANSFER_OWNER_PICKER_MOUNT)).to_be_visible()

    # Cancel closes the picker without staging any transfer.
    wait_then_click_element(page=page, css_selector=HPL.TRANSFER_PICKER_CANCEL_BTN)

    wait_until_hidden(page=page, css_selector=HPL.TRANSFER_PICKER_LISTBOX)
    expect(page.locator(HPL.TRANSFER_OWNER_PICKER_MOUNT)).to_be_hidden()

    # Focus returns to the owner-only trigger that opened the picker.
    expect(page.locator(HPL.MEMBER_BTN_TRANSFER_OWNER)).to_be_focused()
