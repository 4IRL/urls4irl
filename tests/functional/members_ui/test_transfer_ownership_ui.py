import re

from flask import Flask
from playwright.sync_api import Page, expect
import pytest

from backend.models.users import Users
from backend.utils.strings.user_strs import (
    TRANSFER_OWNER_CONFIRM_SUBMIT,
    TRANSFER_OWNER_CONFIRM_TITLE,
    TRANSFER_OWNER_CONFIRM_WARNING,
    TRANSFER_OWNER_SUCCESS,
)
from tests.functional.db_utils import (
    get_other_member_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    force_transfer_400_response,
    open_transfer_ownership_picker,
    seed_co_creator_in_utub,
    stage_transfer_confirm_view,
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
    WHEN they open the modal, filter, pick a member, Continue, and commit
    THEN the confirm view shows the warning + retitles + relabels Submit, the commit
        submit disables (double-submit guard), the chosen member becomes owner
        (diamond-fill), the acting user is demoted to co-owner (diamond-half) in the
        member list AND on the left UTub-deck selector (which stays .active), and the
        owner-only affordances give way to the Leave button
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

    # Filter the pick view to the target member, then pick + Continue to advance the
    # SAME modal to its confirm view (no commit yet).
    page.locator(HPL.TRANSFER_PICKER_FILTER_INPUT).fill(new_owner_username)
    stage_transfer_confirm_view(page=page, member_id=new_owner_id)

    # The confirm view shows the warning naming the new owner, the title flips to
    # the confirm prompt, and Submit is relabeled "Transfer to <username>".
    expect(page.locator(HPL.TRANSFER_OWNER_CONFIRM_VIEW)).to_have_text(
        TRANSFER_OWNER_CONFIRM_WARNING.replace("{{ username }}", new_owner_username)
    )
    expect(page.locator(HPL.TRANSFER_OWNER_MODAL_TITLE)).to_have_text(
        TRANSFER_OWNER_CONFIRM_TITLE
    )
    expect(page.locator(HPL.TRANSFER_OWNER_SUBMIT)).to_have_text(
        TRANSFER_OWNER_CONFIRM_SUBMIT.replace("{{ username }}", new_owner_username)
    )

    # Commit the transfer.
    page.locator(HPL.TRANSFER_OWNER_SUBMIT).click()

    # DD-11 parity: submit disables immediately after click (double-submit guard).
    expect(page.locator(HPL.TRANSFER_OWNER_SUBMIT)).to_be_disabled()

    wait_until_hidden(page=page, css_selector=HPL.TRANSFER_OWNER_MODAL)

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
    THEN Enter opens the modal, ArrowDown/Enter stages a member (Submit enabled),
        and Escape closes the modal (Bootstrap data-bs-keyboard) and returns focus
        to the trigger
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

    # Enter fires the trigger's click handler, opening the modal. Gate on the
    # fade-in settling (opacity==1) so the shown-focus handler has moved focus onto
    # the first row before roving.
    page.keyboard.press("Enter")
    wait_until_visible_css_selector(page=page, css_selector=HPL.TRANSFER_OWNER_MODAL)
    wait_until_css_property(
        page=page,
        css_selector=HPL.TRANSFER_OWNER_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.TRANSFER_PICKER_LISTBOX)

    # The modal's shown.bs.modal handler moves DOM focus onto the first option row;
    # wait for it before roving so the ArrowDown/Enter keydown/keyup actually reach
    # the pick-view listeners (pressing before focus lands is a lost-keys race).
    expect(page.locator(HPL.TRANSFER_PICKER_OPTION).first).to_be_focused()

    # ArrowDown roves, Enter (on keyup) stages the focused member — Submit enables.
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator(HPL.TRANSFER_OWNER_SUBMIT)).to_be_enabled()

    # Escape closes the modal and returns focus to the trigger.
    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.TRANSFER_OWNER_MODAL)
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
    GIVEN an owner has staged a transfer and the confirm view is shown but they are
        rate limited
    WHEN they commit the transfer
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
    stage_transfer_confirm_view(page=page, member_id=new_owner_id)

    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=HPL.TRANSFER_OWNER_SUBMIT)
    assert_on_429_page(page=page)


def test_transfer_ownership_invalid_csrf_token(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner has staged a transfer and the confirm view is shown
    WHEN they commit with an invalid CSRF token
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
    stage_transfer_confirm_view(page=page, member_id=new_owner_id)

    invalidate_csrf_token_on_page(page=page)
    wait_then_click_element(page=page, css_selector=HPL.TRANSFER_OWNER_SUBMIT)
    assert_visited_403_on_invalid_csrf_and_reload(page=page)


def test_transfer_ownership_submit_button_reenables_on_server_error(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner has staged a transfer and the confirm view is shown
    WHEN the PATCH request fails with a 500 server error
    THEN the #transferOwnerSubmit button is re-enabled so the user can retry
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
    stage_transfer_confirm_view(page=page, member_id=new_owner_id)

    force_next_patch_ajax_failure_no_navigate(page=page)
    wait_then_click_element(page=page, css_selector=HPL.TRANSFER_OWNER_SUBMIT)

    expect(page.locator(HPL.TRANSFER_OWNER_SUBMIT)).to_be_enabled()


def test_transfer_ownership_target_already_owner_surfaces_message(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner has staged a transfer and the confirm view is shown
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
    stage_transfer_confirm_view(page=page, member_id=new_owner_id)

    force_transfer_400_response(page=page, message=_ALREADY_OWNER_MESSAGE)
    wait_then_click_element(page=page, css_selector=HPL.TRANSFER_OWNER_SUBMIT)

    # The server message is surfaced via the members-panel row-action live region,
    # not a redirect — the members deck stays put.
    expect(page.locator("#MemberRowActionAnnouncement")).to_have_text(
        _ALREADY_OWNER_MESSAGE
    )
    expect(page.locator(HPL.MEMBER_DECK)).to_be_visible()


# --------------------------------------------------------------------------- #
# Modal-open coverage of the deck (replaces the DD-11 pointer-events kebab test)
# --------------------------------------------------------------------------- #


def test_transfer_modal_open_covers_deck_with_backdrop(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members and opens the transfer modal
    WHEN the modal is shown
    THEN #transferOwnerModal is visible AND a .modal-backdrop is present — the
        Bootstrap backdrop inherently blocks the deck behind it (the modal-based
        equivalent of the retired DD-11 cross-surface pointer-events suppression)
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_transfer_ownership_picker(page=page)

    expect(page.locator(HPL.TRANSFER_OWNER_MODAL)).to_be_visible()
    # The shared modal backdrop is appended to <body> on show and covers the deck.
    expect(page.locator(HPL.MODAL_BACKDROP).first).to_be_visible()


def test_transfer_modal_cancel_closes_and_restores_focus(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with at least one other member and opens the modal
    WHEN they click the footer Cancel button
    THEN the transfer modal hides AND focus returns to the trigger
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_transfer_ownership_picker(page=page)
    expect(page.locator(HPL.TRANSFER_OWNER_MODAL)).to_be_visible()

    # Cancel dismisses the modal without staging any transfer.
    wait_then_click_element(page=page, css_selector=HPL.TRANSFER_OWNER_CANCEL)

    wait_until_hidden(page=page, css_selector=HPL.TRANSFER_OWNER_MODAL)

    # Focus returns to the owner-only trigger that opened the modal.
    expect(page.locator(HPL.MEMBER_BTN_TRANSFER_OWNER)).to_be_focused()
