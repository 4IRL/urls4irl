from flask import Flask
from playwright.sync_api import Page, expect
import pytest

from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.utils.strings.user_strs import (
    MAKE_CO_OWNER_ACTION,
    REVOKE_CO_OWNER_ACTION,
)
from tests.functional.db_utils import (
    get_other_member_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    force_role_change_400_response,
    open_member_row_role_action,
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
    invalidate_csrf_token_on_page,
    wait_then_click_element,
    wait_until_css_property,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.members_ui

# A message distinct enough that asserting it in the live region proves the
# server text (not a generic fallback) surfaced. Fulfilled by
# force_role_change_400_response, standing in for the server-side
# CANNOT_MODIFY_OWNER_ROLE guard the UI cannot reach directly (the owner's own
# row has no kebab).
_OWNER_GUARD_MESSAGE = "You cannot change the owner's role."


def _username_for_user_id(*, app: Flask, user_id: int) -> str:
    with app.app_context():
        return Users.query.get(user_id).username


def _submit_confirm_modal(*, page: Page) -> None:
    """Gate on the modal fade-in settling (opacity==1) before clicking submit.

    Clicking while Bootstrap's show-transition is still running causes the
    subsequent modal("hide") to be dropped as an overlapping transition, leaving
    the modal visible and racing wait_until_hidden (mirrors the delete tests).
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


def test_owner_sees_kebab_on_non_owner_rows(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with members
    WHEN they hover a non-owner member row
    THEN the row's kebab is revealed (opacity 1) and the owner's own row has none
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    badge = page.locator(f'{HPL.BADGES_MEMBERS}[memberid="{other_member.id}"]')
    expect(badge).to_be_visible()
    badge.hover()
    # Hover-reveal: the kebab is opacity:0 until :hover on fine pointers, so assert
    # the computed opacity rather than a bare visibility check (Playwright treats
    # opacity:0 as visible).
    wait_until_css_property(
        page=page,
        css_selector=f'{HPL.BADGES_MEMBERS}[memberid="{other_member.id}"] '
        f"{HPL.MEMBER_ROW_KEBAB}",
        css_property="opacity",
        expected_value="1",
    )

    # The owner's own row (#UTubOwner) carries no kebab.
    assert page.locator(HPL.BADGE_OWNER).locator(HPL.MEMBER_ROW_KEBAB).count() == 0


def test_co_owner_viewer_sees_no_kebabs(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user is a CO_CREATOR (co-owner) of a UTub they did not create
    WHEN they view the members panel
    THEN no member row shows a kebab (owner-only affordance), yet role icons render
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
    assert page.locator(HPL.MEMBER_ROW_KEBAB).count() == 0
    assert page.locator(HPL.MEMBER_ROW_ROLE_ICON).count() > 0


def test_plain_member_viewer_sees_no_kebabs(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user is a plain member of a UTub they did not create
    WHEN they view the members panel
    THEN no member row shows a kebab, yet role icons render
    """
    app = provide_app

    user_id = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_member_of.name
    )

    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_ROW_ROLE_ICON)
    assert page.locator(HPL.MEMBER_ROW_KEBAB).count() == 0
    assert page.locator(HPL.MEMBER_ROW_ROLE_ICON).count() > 0


# --------------------------------------------------------------------------- #
# Grant / revoke happy paths
# --------------------------------------------------------------------------- #


def test_grant_co_owner_happy_path(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with a plain member
    WHEN they open the member's kebab, pick "Make co-owner", and submit
    THEN the submit button disables (double-submit guard), the row's icon becomes
        diamond-half, and the menu item now reads "Revoke co-owner"
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    open_member_row_role_action(page=page, member_id=other_member.id)

    role_item = page.locator(
        f'{HPL.BADGES_MEMBERS}[memberid="{other_member.id}"] {HPL.MEMBER_ROW_MENU_ROLE}'
    )
    # The plain member's item offers "Make co-owner" before the grant.
    expect(role_item).to_have_text(MAKE_CO_OWNER_ACTION)

    _submit_confirm_modal(page=page)

    # DD-11: submit is disabled immediately after click to prevent double-submit.
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_disabled()

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    # Re-query the row (the icon element is swapped out, per DD-8) — the row NODE
    # itself is never replaced, but the captured icon Locator would be stale.
    co_owner_icon = page.locator(
        f'{HPL.BADGES_MEMBERS}[memberid="{other_member.id}"] svg.bi-diamond-half'
    )
    expect(co_owner_icon).to_be_visible()
    # The role menu item flips to "Revoke co-owner" (targeted by its stable class,
    # not text — the text is exactly what changed).
    expect(role_item).to_have_text(REVOKE_CO_OWNER_ACTION)


def test_revoke_co_owner_happy_path(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with a pre-seeded co-owner
    WHEN they open the co-owner's kebab, pick "Revoke co-owner", and submit
    THEN the row's icon returns to people-fill (plain member)
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)
    seed_co_creator_in_utub(
        app=app, utub_id=utub_user_created.id, username=other_member.username
    )
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_member_row_role_action(page=page, member_id=other_member.id)

    role_item = page.locator(
        f'{HPL.BADGES_MEMBERS}[memberid="{other_member.id}"] {HPL.MEMBER_ROW_MENU_ROLE}'
    )
    # The co-owner's item offers "Revoke co-owner".
    expect(role_item).to_have_text(REVOKE_CO_OWNER_ACTION)

    _submit_confirm_modal(page=page)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    member_icon = page.locator(
        f'{HPL.BADGES_MEMBERS}[memberid="{other_member.id}"] svg.bi-people-fill'
    )
    expect(member_icon).to_be_visible()


def test_role_icons_display_per_role(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a UTub with an owner, a seeded co-owner, and a plain member
    WHEN the owner views the members panel
    THEN each row shows its role icon: diamond-fill (owner), diamond-half
        (co-owner), people-fill (plain member) — independent of any grant action
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    with app.app_context():
        other_members: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id != user_id,
            Utub_Members.utub_id == utub_user_created.id,
        ).all()
        co_owner_user = other_members[0].to_user
        plain_member_user = other_members[1].to_user

    seed_co_creator_in_utub(
        app=app, utub_id=utub_user_created.id, username=co_owner_user.username
    )
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    # Owner row (diamond-fill), scoped to #UTubOwner.
    expect(page.locator(f"{HPL.BADGE_OWNER} svg.bi-diamond-fill")).to_be_visible()
    # Co-owner row (diamond-half).
    expect(
        page.locator(
            f'{HPL.BADGES_MEMBERS}[memberid="{co_owner_user.id}"] svg.bi-diamond-half'
        )
    ).to_be_visible()
    # Exactly one co-owner glyph deck-wide (the owner is diamond-fill, not half).
    expect(page.locator(HPL.MEMBER_ROW_CO_CREATOR_ICON)).to_have_count(1)
    # Plain member row (people-fill).
    expect(
        page.locator(
            f'{HPL.BADGES_MEMBERS}[memberid="{plain_member_user.id}"] '
            "svg.bi-people-fill"
        )
    ).to_be_visible()


# --------------------------------------------------------------------------- #
# Sad paths
# --------------------------------------------------------------------------- #


def test_role_change_rate_limits(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with a plain member but they are rate limited
    WHEN they submit the make-co-owner confirmation modal
    THEN the 429 error page is shown
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    open_member_row_role_action(page=page, member_id=other_member.id)

    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    assert_on_429_page(page=page)


def test_role_change_invalid_csrf_token(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with a plain member
    WHEN they submit the make-co-owner modal with an invalid CSRF token
    THEN U4I responds with the 403 body-swap and reload
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    open_member_row_role_action(page=page, member_id=other_member.id)

    invalidate_csrf_token_on_page(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    assert_visited_403_on_invalid_csrf_and_reload(page=page)


def test_role_change_submit_button_reenables_on_server_error(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with a plain member and the make-co-owner modal is open
    WHEN the PATCH request fails with a 500 server error
    THEN the #modalSubmit button is re-enabled so the user can retry
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    open_member_row_role_action(page=page, member_id=other_member.id)

    force_next_patch_ajax_failure_no_navigate(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_enabled()


def test_role_change_owner_guard_surfaces_message(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with a plain member and the make-co-owner modal is open
    WHEN the PATCH is rejected 400 (owner-targets-self / non-member server guard)
    THEN the panel surfaces the server message in the row-action live region and
        does NOT redirect away
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    open_member_row_role_action(page=page, member_id=other_member.id)

    force_role_change_400_response(page=page, message=_OWNER_GUARD_MESSAGE)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # The server message is surfaced via the members-panel row-action live region,
    # not a redirect — the members deck stays put.
    expect(page.locator("#MemberRowActionAnnouncement")).to_have_text(
        _OWNER_GUARD_MESSAGE
    )
    expect(page.locator(HPL.MEMBER_DECK)).to_be_visible()


# --------------------------------------------------------------------------- #
# Keyboard operability
# --------------------------------------------------------------------------- #


def test_role_menu_keyboard_open_navigate_escape(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with a plain member
    WHEN they focus the row's kebab, press Enter, ArrowDown, then Escape
    THEN Enter opens the menu (first item focused), ArrowDown moves to the next
        item, and Escape closes the menu and returns focus to the kebab trigger
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    badge = page.locator(f'{HPL.BADGES_MEMBERS}[memberid="{other_member.id}"]')
    expect(badge).to_be_visible()
    badge.hover()

    kebab = badge.locator(HPL.MEMBER_ROW_KEBAB)
    kebab.focus()
    expect(kebab).to_be_focused()

    # Enter opens the menu; focus lands on the first item (the role toggle).
    page.keyboard.press("Enter")
    role_item = badge.locator(HPL.MEMBER_ROW_MENU_ROLE)
    expect(role_item).to_be_focused()

    # ArrowDown moves focus to the next item ("Remove member").
    page.keyboard.press("ArrowDown")
    expect(badge.locator(HPL.MEMBER_ROW_MENU_REMOVE)).to_be_focused()

    # Escape closes the menu and returns focus to the kebab trigger.
    page.keyboard.press("Escape")
    expect(badge.locator(HPL.MEMBER_ROW_MENU)).to_be_hidden()
    expect(kebab).to_be_focused()


def test_role_menu_keyboard_enter_activates_item(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a user owns a UTub with a plain member and the kebab menu is open
    WHEN they press Enter on the focused "Make co-owner" item
    THEN the confirm modal is shown
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)

    badge = page.locator(f'{HPL.BADGES_MEMBERS}[memberid="{other_member.id}"]')
    expect(badge).to_be_visible()
    badge.hover()

    kebab = badge.locator(HPL.MEMBER_ROW_KEBAB)
    kebab.focus()
    page.keyboard.press("Enter")

    role_item = badge.locator(HPL.MEMBER_ROW_MENU_ROLE)
    expect(role_item).to_be_focused()

    # Enter activates the focused item, opening the shared confirm modal.
    page.keyboard.press("Enter")
    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)
    expect(page.locator(HPL.HOME_MODAL)).to_be_visible()
