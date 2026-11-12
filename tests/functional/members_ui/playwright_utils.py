import json
import re
from datetime import timedelta
from typing import Callable

from flask import Flask
from playwright.sync_api import Locator, Page, Response, Route, expect

from backend import db
from backend.cli.mock_constants import USERNAME_BASE
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.datetime_utils import utc_now
from tests.functional.db_utils import (
    get_utub_this_user_created,
    set_member_role_in_utub,
    set_utub_settings,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    wait_for_css_transitions_to_finish,
    wait_for_modal_ready,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)

# Matches ONLY the add-member POST route (`/utubs/<id>/members`), never the
# co-member candidates GET (`/utubs/<id>/co-members`) nor the per-member DELETE
# (`/utubs/<id>/members/<user_id>`), so a forced response delay isolates the
# batch-add request.
_MEMBER_ADD_POST_URL_RE = re.compile(r"/utubs/\d+/members$")

# Matches ONLY the per-member role PATCH (`/utubs/<id>/members/<user_id>`), used
# to fulfil a forced 400 for the owner-targets-self / non-member guarded case.
_MEMBER_ROLE_PATCH_URL_RE = re.compile(r"/utubs/\d+/members/\d+$")

# Matches ONLY the ownership-transfer PATCH (`/utubs/<id>/owner`), used to fulfil
# a forced 400 for the target-already-owner / already-transferred guarded case.
# Distinct from the per-member role PATCH regex above (no trailing `/members/id`).
_TRANSFER_OWNER_PATCH_URL_RE = re.compile(r"/utubs/\d+/owner$")

# Matches ONLY the UTub settings PATCH (`/utubs/<id>/settings`), never the
# per-user `/utubs/<id>/member-settings` PATCH.
_UTUB_SETTINGS_PATCH_URL_RE = re.compile(r"/utubs/\d+/settings$")

# The mock users the member-permission acceptance tests act as and on.
OWNER_ID = 1
CO_OWNER_ID = 2
TARGET_ID = 3
SUGGESTED_ID = 4
OUTSIDER_ID = 5
SUGGESTED_NAME = f"{USERNAME_BASE}{SUGGESTED_ID}"
OUTSIDER_NAME = f"{USERNAME_BASE}{OUTSIDER_ID}"

# Anchored to the URL path so an error page that merely contains "/home" fails.
_HOME_URL_RE = re.compile(r"/home(\?|$)")


def is_settings_patch(response: Response) -> bool:
    """True for the UTub settings PATCH response."""
    return (
        response.request.method == "PATCH"
        and _UTUB_SETTINGS_PATCH_URL_RE.search(response.url) is not None
    )


def seed_policy(
    *,
    app: Flask,
    utub_id: int,
    co_owners_can_remove: bool = False,
    members_can_add: bool = False,
) -> None:
    """Write both member-permission switches into the UTub's settings."""
    set_utub_settings(
        app,
        utub_id,
        {
            "members": {
                "co_owners_can_remove": co_owners_can_remove,
                "members_can_add": members_can_add,
            }
        },
    )


def login_as(
    *, app: Flask, page: Page, user_id: int, role: Member_Role | None = None
) -> int:
    """Seed ``user_id``'s role in the owner's UTub (when given), log them in on
    that UTub and wait for the member rows. Returns the UTub id."""
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    if role is not None:
        set_member_role_in_utub(app, user_id, utub_id, role)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_id
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_ROW_ROLE_ICON)
    return utub_id


def expect_notice(*, page: Page, text: str) -> None:
    """The deck refusal notice is visible with ``text`` and the page did not
    redirect to the error page."""
    notice = page.locator(HPL.MEMBER_DECK_NOTICE)
    expect(notice).to_be_visible()
    expect(notice).to_contain_text(text)
    expect(page).to_have_url(_HOME_URL_RE)


def open_member_name_filter(*, page: Page) -> Locator:
    """Open the member name filter input and return the ready input locator.

    The member name filter input is hidden behind the funnel toggle on all
    viewports. Click the funnel to reveal the input, wait for it to become
    visible and focused (the open handler focuses it), then return the
    now-ready locator.

    Waiting for focus before any keys are sent hardens the root cause of the
    focus/send_keys race rather than padding a timeout.

    Args:
        page: Playwright Page open to the U4I Home Page with a UTub selected

    Returns:
        The visible, focused #MemberNameSearch input locator
    """
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_NAME_FILTER)
    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_SEARCH_INPUT)
    wait_until_in_focus(page=page, css_selector=HPL.MEMBER_SEARCH_INPUT)
    return wait_then_get_element(page=page, css_selector=HPL.MEMBER_SEARCH_INPUT)


def get_all_member_badges(*, page: Page) -> list[Locator]:
    """Return per-element locators for every visible member badge.

    Args:
        page: Playwright Page open to a selected UTub

    Returns:
        List of member badge Locators
    """
    return wait_then_get_elements(page=page, css_selector=HPL.BADGES_MEMBERS)


def get_all_member_usernames(*, page: Page) -> list[str]:
    """Return the bare username of every visible member badge as a list.

    Each ``.member`` badge concatenates the username with a role annotation
    ("Owner"/"Member"/"Co-owner"), so the badge's full text content is
    ``"<username>\\n<Role>"``. The username itself lives in the row's direct-child
    ``<b>`` element (``createMemberBadge``/``createOwnerBadge`` build
    ``.html("<b>" + username + "</b>")`` plus the separate role wrap), so read the
    ``<b>`` text to return bare usernames rather than the role-suffixed row text.

    Args:
        page: Playwright Page open to a selected UTub

    Returns:
        List of member usernames
    """
    badges_locator = page.locator(HPL.BADGES_MEMBERS)
    expect(badges_locator.first).to_be_visible()
    return page.locator(f"{HPL.BADGES_MEMBERS} > b").all_inner_texts()


def member_badge_by_username(*, page: Page, username: str) -> Locator:
    """Locate the member deck badge for `username`, matching on a word boundary.

    Uses a `\\b`-anchored regex rather than a bare substring so a lookup for
    ``u4i_test2`` never also matches ``u4i_test20`` — robust regardless of how
    many mock users exist.
    """
    return page.locator(HPL.BADGES_MEMBERS).filter(
        has_text=re.compile(rf"\b{re.escape(username)}\b")
    )


def open_add_member_combobox(*, page: Page) -> Locator:
    """Open the add-member combobox (owner-only) and return the ready input.

    Clicks the #memberBtnCreate opener, then waits for the TS-built combobox
    input to become visible AND focused (the open lifecycle focuses it). Waiting
    for focus before typing hardens the focus/type race at its root rather than
    padding a timeout.

    Args:
        page: Playwright Page open to the U4I Home Page with a UTub selected and
            the current user the UTub owner (only owners see the opener).

    Returns:
        The visible, focused add-member combobox input locator.
    """
    # no_wait_after: a phone run once stalled 10s at "waiting for scheduled
    # navigations to finish" after the click had completed (combobox open, no
    # navigation on this path). The visible + focused waits below are the real
    # readiness check, so the post-click navigation wait is skipped.
    page.locator(HPL.BUTTON_MEMBER_CREATE).first.click(no_wait_after=True)
    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_COMBOBOX_INPUT)
    wait_until_in_focus(page=page, css_selector=HPL.MEMBER_COMBOBOX_INPUT)
    return wait_then_get_element(page=page, css_selector=HPL.MEMBER_COMBOBOX_INPUT)


def type_in_member_combobox(*, page: Page, text: str) -> None:
    """Type into the (already-open) add-member combobox input.

    `fill` fires an `input` event that trips the combobox's 200ms-debounced
    render; callers then wait on the option/hint they expect.

    Args:
        page: Playwright Page with the add-member combobox open
        text: The text to type (a username or substring)
    """
    combobox_input = wait_then_get_element(
        page=page, css_selector=HPL.MEMBER_COMBOBOX_INPUT
    )
    clear_then_send_keys(locator=combobox_input, input_text=text)


def _suggestion_option_locator(*, page: Page, username: str) -> Locator:
    """Locate the co-member suggestion option whose label is exactly `username`.

    `text-is` (exact match) both excludes the amber outsider row (its label is
    `Add "..." by username`) and prevents a substring collision between
    otherwise-similar mock usernames.
    """
    return page.locator(HPL.MEMBER_COMBOBOX_OPTION).filter(
        has=page.locator(f"{HPL.MEMBER_COMBOBOX_OPTION_LABEL}:text-is('{username}')")
    )


def stage_co_member_suggestion(*, page: Page, username: str) -> Locator:
    """Type a co-member's exact username, click its suggestion row, return chip.

    Typing the exact username narrows the listbox to that single co-member
    suggestion and suppresses the outsider row (an exact co-member match), so the
    clicked option is unambiguously the search-result suggestion.

    Args:
        page: Playwright Page with the add-member combobox open
        username: The co-member candidate's exact username

    Returns:
        The staged chip locator for the picked co-member.
    """
    type_in_member_combobox(page=page, text=username)
    suggestion = _suggestion_option_locator(page=page, username=username).first
    expect(suggestion).to_be_visible()
    suggestion.click()
    return get_staged_chip(page=page, username=username)


def stage_outsider_username(*, page: Page, username: str) -> Locator:
    """Type a non-co-member username, click the amber outsider row, return chip.

    The outsider row (`+ Add "username" by username`) is the exact-add
    fallback for anyone who is neither a co-member candidate nor a current
    member. Staging it carries `source='exact_username'`.

    Args:
        page: Playwright Page with the add-member combobox open
        username: The exact username to stage as an outsider (any casing)

    Returns:
        The staged chip locator for the outsider.
    """
    type_in_member_combobox(page=page, text=username)
    outsider = page.locator(HPL.MEMBER_COMBOBOX_OPTION_OUTSIDER).first
    expect(outsider).to_be_visible()
    outsider.click()
    return get_staged_chip(page=page, username=username)


def get_staged_chip(*, page: Page, username: str) -> Locator:
    """Return the staged chip locator for `username` (unique, case-sensitive)."""
    return page.locator(
        f"{HPL.MEMBER_COMBOBOX_STAGED_CHIP}[data-staged-username='{username}']"
    )


def click_add_member_submit(*, page: Page) -> None:
    """Click the combobox's 'Add N' batch-submit button."""
    wait_then_click_element(page=page, css_selector=HPL.MEMBER_COMBOBOX_SUBMIT)


def close_add_member_combobox(*, page: Page) -> None:
    """Close the (stay-open) combobox via its in-place Cancel button.

    A successful batch add keeps the combobox open (the mock's continuous
    "Add another…" flow), which hides #displayMemberWrap — so tests that need to
    see the resulting member badges in the deck must close it first.
    """
    wait_then_click_element(page=page, css_selector=HPL.MEMBER_COMBOBOX_CANCEL_BTN)
    wait_until_visible_css_selector(page=page, css_selector=HPL.DISPLAY_MEMBER_WRAP)


def hold_member_add_response(*, page: Page) -> Callable[[], None]:
    """Intercept the add-member POST(s) and hold them paused until released.

    The interceptor captures each add POST *without* resolving it, so the
    request stays in flight while the test asserts the transient per-chip
    `.dual-loading-ring` (shown 50ms after submit). Calling the returned
    ``release()`` continues every held request so the batch settles. This
    request-hold pattern (rather than a blocking `time.sleep` in the handler)
    both avoids racing the ring away before the assertion and stays clear of
    jQuery's 1000ms ajax timeout — the caller releases as soon as the ring is
    observed, well inside that window. Only the add POST is matched; the
    co-member GET and per-member DELETE are untouched.

    Args:
        page: Playwright Page under test

    Returns:
        A ``release()`` callable that continues every held add POST and removes
        the interceptor.
    """
    held_routes: list[Route] = []

    def _capture(route: Route) -> None:
        held_routes.append(route)

    page.route(_MEMBER_ADD_POST_URL_RE, _capture)

    def _release() -> None:
        for route in held_routes:
            route.continue_()
        page.unroute(_MEMBER_ADD_POST_URL_RE, _capture)

    return _release


def seed_co_members_for_owner(
    *,
    app: Flask,
    owner_id: int,
    co_member_usernames: list[str],
    shared_utub_name: str = "SharedCoMemberUTub",
) -> int:
    """Seed co-member candidates for `owner_id`'s add-member combobox.

    Creates a NEW UTub owned by `owner_id` and adds the named existing users to
    it. Because they now share this *other* UTub with the owner (and are not
    members of the owner's target UTub), they surface as co-member candidates
    when the owner opens the add-member combobox on the target UTub. Mirrors the
    integration service test's `_make_utub` + `_add_member` seeding shape.

    Args:
        app: The Flask app under test
        owner_id: The user id that owns both the target UTub and the shared UTub
        co_member_usernames: Existing usernames to add to the shared UTub
        shared_utub_name: Name for the seeded shared UTub

    Returns:
        The id of the seeded shared UTub.
    """
    with app.app_context():
        owner: Users = Users.query.get(owner_id)
        shared_utub = Utubs(
            name=shared_utub_name,
            utub_creator=owner.id,
            utub_description="",
        )
        db.session.add(shared_utub)
        db.session.commit()

        creator_membership = Utub_Members(member_role=Member_Role.CREATOR)
        creator_membership.utub_id = shared_utub.id
        creator_membership.user_id = owner.id
        db.session.add(creator_membership)
        db.session.commit()

        for username in co_member_usernames:
            co_member: Users = Users.query.filter(Users.username == username).first()
            membership = Utub_Members()
            membership.utub_id = shared_utub.id
            membership.user_id = co_member.id
            db.session.add(membership)
        db.session.commit()
        return shared_utub.id


def add_existing_user_as_member_of_utub(
    *, app: Flask, utub_id: int, username: str
) -> None:
    """Add an existing user to `utub_id` directly in the DB as a regular member.

    Used to create a server-side duplicate mid-flow (after the combobox already
    staged a chip from the stale co-member list) so the batch POST resolves to
    MEMBER_ALREADY_IN_UTUB — the deterministic per-chip duplicate-error path.
    """
    with app.app_context():
        user: Users = Users.query.filter(Users.username == username).first()
        membership = Utub_Members()
        membership.utub_id = utub_id
        membership.user_id = user.id
        membership.member_role = Member_Role.MEMBER
        db.session.add(membership)
        db.session.commit()


def delete_member_active_utub(*, page: Page, member_name: str) -> None:
    """Open the named member row's kebab menu and click "Remove member".

    The owner's per-row actions now live behind a kebab (overflow) menu instead
    of a standalone remove button. Hovering the row reveals the kebab (opacity:0
    until :hover on fine pointers), clicking it toggles the menu open (`.open` +
    unset `hidden`), and the menu's "Remove member" item opens the confirm modal.
    Playwright auto-waits for each target to be actionable — no pauses needed.

    Args:
        page: Playwright Page open to a selected UTub owned by the current user
        member_name: Exact username text of the member to delete
    """
    badge = page.locator(HPL.BADGES_MEMBERS).filter(has_text=member_name).first
    expect(badge).to_be_visible()
    badge.hover()
    badge.locator(HPL.MEMBER_ROW_KEBAB).click()
    remove_item = badge.locator(HPL.MEMBER_ROW_MENU_REMOVE)
    expect(remove_item).to_be_visible()
    remove_item.click()


def seed_co_creator_in_utub(*, app: Flask, utub_id: int, username: str) -> int:
    """Promote an existing member of `utub_id` to CO_CREATOR (co-owner) in place.

    Mirrors `add_existing_user_as_member_of_utub` but sets
    `member_role=Member_Role.CO_CREATOR`. Because `create_test_utubmembers`
    already seeds every user as a plain member of every UTub, this promotes the
    existing `(utub_id, user_id)` membership row rather than inserting a
    duplicate — the analogue of `tests/utils_for_test.py::set_member_role`, kept
    members_ui-local so the co-owner-panel suites read as a self-contained set.
    Used by the revoke, gating, and role-icon tests so they do not depend on the
    grant flow existing.

    Args:
        app: The Flask app under test
        utub_id: The UTub whose member is being promoted
        username: The exact username of the existing member to promote

    Returns:
        The promoted member's user id (for `.member[memberid=...]` targeting).
    """
    with app.app_context():
        user: Users = Users.query.filter(Users.username == username).first()
        membership: Utub_Members = Utub_Members.query.get((utub_id, user.id))
        membership.member_role = Member_Role.CO_CREATOR
        db.session.commit()
        return user.id


def expire_invite_link_in_db(*, app: Flask, invite_link_id: int) -> None:
    """Set an existing invite link's `expires_at` to the past, in place.

    `add_invite_link` only inserts, so a test that needs the link to die after
    the panel is open updates the existing row with this.
    """
    with app.app_context():
        invite: Utub_Invite_Links = Utub_Invite_Links.query.get(invite_link_id)
        invite.expires_at = utc_now() - timedelta(days=1)
        db.session.commit()


def set_invite_link_use_count_in_db(
    *, app: Flask, invite_link_id: int, use_count: int
) -> None:
    """Set an existing invite link's `use_count` in place (simulates joins that
    happened after the panel loaded)."""
    with app.app_context():
        invite: Utub_Invite_Links = Utub_Invite_Links.query.get(invite_link_id)
        invite.use_count = use_count
        db.session.commit()


def get_invite_link_row(*, app: Flask, invite_link_id: int) -> tuple[int | None, int]:
    """Return an invite link row's `(max_uses, days_until_expiry)` (rounded)."""
    with app.app_context():
        invite: Utub_Invite_Links = Utub_Invite_Links.query.get(invite_link_id)
        remaining = invite.expires_at - utc_now()
        return invite.max_uses, round(remaining.total_seconds() / 86400)


def revoke_invite_link_in_db(*, app: Flask, invite_link_id: int) -> None:
    """Stamp `revoked_at` on an existing invite link, in place."""
    with app.app_context():
        invite: Utub_Invite_Links = Utub_Invite_Links.query.get(invite_link_id)
        invite.revoked_at = utc_now()
        db.session.commit()


def open_member_row_role_action(*, page: Page, member_id: int) -> None:
    """Open the named member row's kebab menu and click the role-toggle item.

    Hovers the row (the kebab is opacity:0 until :hover on fine pointers),
    clicks the kebab to open the menu (`.open` + unset `hidden`), then clicks the
    "Make/Revoke co-owner" item (targeted by its dedicated `.memberRowMenuItemRole`
    class, since its label alternates with the row's role). The item opens the
    shared confirm modal. Playwright auto-waits for each target to be actionable.

    Args:
        page: Playwright Page open to a selected UTub owned by the current user
        member_id: The user id of the member row to act on
    """
    badge = page.locator(f'{HPL.BADGES_MEMBERS}[memberid="{member_id}"]')
    expect(badge).to_be_visible()
    badge.hover()
    badge.locator(HPL.MEMBER_ROW_KEBAB).click()
    role_item = badge.locator(HPL.MEMBER_ROW_MENU_ROLE)
    expect(role_item).to_be_visible()
    role_item.click()


def submit_confirm_modal(*, page: Page) -> None:
    """Gate on the modal fade-in settling before clicking submit.

    Clicking while Bootstrap's show-transition is still running causes the
    subsequent modal("hide") to be dropped as an overlapping transition, leaving
    the modal visible and racing wait_until_hidden (mirrors the delete tests).
    """
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    # Also wait for every transition on the modal and its dialog to finish.
    wait_for_css_transitions_to_finish(locator=page.locator(HPL.HOME_MODAL))
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)


def force_role_change_400_response(*, page: Page, message: str) -> None:
    """Intercept the next member-role PATCH and fulfil it with a real 400.

    Reproduces the server-side owner-targets-self / non-member guard
    (`CANNOT_MODIFY_OWNER_ROLE` errorCode 4 / `MEMBER_NOT_IN_UTUB`) without
    needing a UI path to target the owner's own (kebab-less) row: the response
    carries `{ "message": ... }` so `role.ts modifyMemberRoleFail` surfaces it via
    `#MemberRowActionAnnouncement` (assertive) rather than redirecting. Only the
    PATCH is matched; the route is removed after the first fulfil so a retry hits
    the real endpoint.

    Args:
        page: Playwright Page under test
        message: The server message the panel should surface
    """

    def _handler(route: Route) -> None:
        route.fulfill(
            status=400,
            content_type="application/json",
            body=json.dumps({"message": message, "errorCode": 4}),
        )

    # `times=1` retires the route after the first match, so a later retry hits the
    # real endpoint and we never call `page.unroute` from inside the handler
    # (which errors mid-handling and lets the request fall through to the server).
    page.route(_MEMBER_ROLE_PATCH_URL_RE, _handler, times=1)


def open_members_gear(*, page: Page, mobile: bool = False) -> None:
    """Open the Members gear (popover on desktop, bottom sheet on a phone).

    Waits for the always-rendered sort select so the section body is built before
    the caller looks for the owner-only Transfer ownership row. On mobile the
    sheet slides in, so its transition is awaited before any tap lands.

    Args:
        page: Playwright Page open to a UTub, on the Members deck when mobile
        mobile: True to tap the gear and wait out the sheet transition
    """
    gear = page.locator(HPL.BUTTON_MEMBER_SETTINGS_GEAR)
    if mobile:
        gear.tap()
    else:
        gear.click()
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.MEMBERS_SETTINGS_SORT_SELECT
    )
    if mobile:
        wait_for_css_transitions_to_finish(
            locator=page.locator(HPL.PANEL_SETTINGS_SHEET)
        )


def open_transfer_ownership_picker(*, page: Page, mobile: bool = False) -> None:
    """Open the dedicated ownership-transfer modal from the Members gear.

    Opens the gear, activates the owner-only Transfer ownership action (which
    closes the gear first), waits for #transferOwnerModal to be visible, gates on
    its fade-in settling (Bootstrap transition done) so a subsequent click can't
    be dropped mid show-transition (mirrors `submit_confirm_modal`/
    `wait_until_css_property`), then waits for the PICK view's listbox to render.
    Only a literal owner of a UTub with >= 1 other member sees the action, so
    callers must seed that state first.

    Args:
        page: Playwright Page open to a UTub the current user owns, with at least
            one other member
        mobile: True to drive the gear and action by touch
    """
    open_members_gear(page=page, mobile=mobile)
    action = page.locator(HPL.MEMBER_BTN_TRANSFER_OWNER)
    if mobile:
        action.tap()
    else:
        action.click()
    wait_until_visible_css_selector(page=page, css_selector=HPL.TRANSFER_OWNER_MODAL)
    wait_for_modal_ready(page=page, modal_selector=HPL.TRANSFER_OWNER_MODAL)
    wait_until_visible_css_selector(page=page, css_selector=HPL.TRANSFER_PICKER_LISTBOX)


def stage_transfer_confirm_view(*, page: Page, member_id: int) -> None:
    """Pick a member in the open modal's PICK view and advance to the CONFIRM view.

    Clicks the pick option whose `memberid` matches `member_id` (single-select
    stages exactly that row and enables the footer #transferOwnerSubmit button),
    then clicks Submit once — the "Continue" action that swaps the SAME modal to
    its confirm view (it does NOT commit the PATCH). Waits for the confirm view to
    be visible and the pick view to be hidden. Callers that want to intercept the
    PATCH (429/CSRF/500/400 sad paths) install their route here, then click
    #transferOwnerSubmit again themselves to commit.

    Args:
        page: Playwright Page with the transfer modal already open (PICK view).
        member_id: The user id of the member to transfer ownership to.
    """
    option = page.locator(f'{HPL.TRANSFER_PICKER_OPTION}[memberid="{member_id}"]')
    expect(option).to_be_visible()
    option.click()

    submit_btn = page.locator(HPL.TRANSFER_OWNER_SUBMIT)
    expect(submit_btn).to_be_enabled()
    submit_btn.click()

    # The inline pick→confirm transition swaps views in place (no modal close).
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.TRANSFER_OWNER_CONFIRM_VIEW
    )
    wait_until_hidden(page=page, css_selector=HPL.TRANSFER_OWNER_PICK_VIEW)


def pick_new_owner(*, page: Page, member_id: int) -> None:
    """Full transfer: pick → Continue → commit the ownership PATCH.

    Advances the modal to the confirm view via `stage_transfer_confirm_view`, then
    clicks the relabeled #transferOwnerSubmit ("Transfer to <username>") a second
    time to commit the PATCH (with the double-submit disable). Use this for the
    happy path / delete-flow completion; use `stage_transfer_confirm_view` when the
    test needs to intercept the PATCH before it fires.

    Args:
        page: Playwright Page with the transfer modal already open (PICK view).
        member_id: The user id of the member to transfer ownership to.
    """
    stage_transfer_confirm_view(page=page, member_id=member_id)
    wait_then_click_element(page=page, css_selector=HPL.TRANSFER_OWNER_SUBMIT)


def force_transfer_400_response(*, page: Page, message: str) -> None:
    """Intercept the next ownership-transfer PATCH and fulfil it with a real 400.

    Reproduces the server-side transfer guards (`TARGET_ALREADY_OWNER` errorCode 6
    / `UNABLE_TO_TRANSFER_OWNERSHIP` / `MEMBER_NOT_IN_UTUB`) deterministically: the
    response carries `{ "message": ... }` so `transfer.ts transferOwnershipFail`
    surfaces it via `#MemberRowActionAnnouncement` (assertive) rather than
    redirecting. Only the `/utubs/<id>/owner` PATCH is matched; the route is
    retired after the first fulfil (`times=1`) so a retry hits the real endpoint.

    Args:
        page: Playwright Page under test.
        message: The server message the members panel should surface.
    """

    def _handler(route: Route) -> None:
        route.fulfill(
            status=400,
            content_type="application/json",
            body=json.dumps({"message": message, "errorCode": 6}),
        )

    page.route(_TRANSFER_OWNER_PATCH_URL_RE, _handler, times=1)


def leave_utub_as_member(*, page: Page, utub_to_leave: Utubs) -> None:
    """Click the leave-UTub button, confirm the modal, and wait for the UTub
    selector to be removed from the DOM.

    Args:
        page: Playwright Page open to the selected UTub to leave
        utub_to_leave: UTub model instance to leave
    """
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    # Wait for Bootstrap's show transition to settle before clicking submit.
    # Submitting while _isTransitioning is true causes Bootstrap to drop the
    # subsequent modal("hide") call, so the modal never becomes hidden.
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_selector_to_be_removed(
        page=page,
        css_selector=f'{HPL.SELECTORS_UTUB}[utubid="{utub_to_leave.id}"]',
    )


def member_row(*, page: Page, member_id: int) -> Locator:
    """The deck row (`.member`) of ``member_id``."""
    return page.locator(f'{HPL.BADGES_MEMBERS}[memberid="{member_id}"]')


def co_owner_kebab(*, page: Page, member_id: int) -> Locator:
    """The co-owner viewer's Remove-only kebab on ``member_id``'s row."""
    return member_row(page=page, member_id=member_id).locator(
        HPL.MEMBER_ROW_KEBAB_CO_OWNER
    )


def computed_styles(*, locator: Locator, properties: list[str]) -> dict[str, str]:
    """Computed CSS values (read straight from the browser, which jsdom cannot
    give) of the element ``locator`` resolves to."""
    return locator.evaluate(
        """(element, properties) => {
            const style = getComputedStyle(element);
            return Object.fromEntries(
                properties.map((name) => [name, style.getPropertyValue(name)])
            );
        }""",
        properties,
    )


def text_contrast_ratio(*, locator: Locator) -> float:
    """WCAG contrast ratio of the element's computed text colour against its
    effective background: its own (possibly translucent) background colour
    composited over the nearest opaque ancestor background."""
    return locator.evaluate(
        """(element) => {
            const parse = (value) => {
                const match = value.match(/rgba?\\(([^)]+)\\)/);
                if (match === null) throw new Error("unparsed colour: " + value);
                const parts = match[1].split(/[ ,\\/]+/).filter(Boolean).map(Number);
                return [parts[0], parts[1], parts[2], parts.length > 3 ? parts[3] : 1];
            };
            const blend = (top, bottom) =>
                [0, 1, 2].map((i) => top[i] * top[3] + bottom[i] * (1 - top[3]));
            let background = [0, 0, 0, 1];
            const layers = [];
            for (let node = element; node !== null; node = node.parentElement) {
                const layer = parse(getComputedStyle(node).backgroundColor);
                if (layer[3] > 0) layers.push(layer);
                if (layer[3] === 1) break;
            }
            for (const layer of layers.reverse()) {
                background = [...blend(layer, background), 1];
            }
            const luminance = (rgb) => {
                const [red, green, blue] = rgb.slice(0, 3).map((channel) => {
                    const unit = channel / 255;
                    return unit <= 0.03928 ? unit / 12.92 : ((unit + 0.055) / 1.055) ** 2.4;
                });
                return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
            };
            const text = luminance(parse(getComputedStyle(element).color));
            const behind = luminance(background);
            const [lighter, darker] = text > behind ? [text, behind] : [behind, text];
            return (lighter + 0.05) / (darker + 0.05);
        }"""
    )


def element_box(*, locator: Locator) -> dict[str, float]:
    """The rendered width and height of ``locator`` (fails if not rendered)."""
    box = locator.bounding_box()
    assert box is not None, "element is not rendered"
    return {"width": box["width"], "height": box["height"]}


def open_co_owner_menu_and_click_remove(*, page: Page, member_id: int) -> None:
    """Open the co-owner kebab on ``member_id``'s row and click its Remove item.

    The menu holds only that item (no role item, no divider)."""
    row = member_row(page=page, member_id=member_id)
    row.locator(HPL.MEMBER_ROW_KEBAB_CO_OWNER).click()
    menu_items = row.locator(f"{HPL.MEMBER_ROW_MENU} .memberRowMenuItem")
    expect(menu_items).to_have_count(1)
    remove_item = row.locator(HPL.MEMBER_ROW_MENU_REMOVE)
    expect(remove_item).to_be_visible()
    remove_item.click()
