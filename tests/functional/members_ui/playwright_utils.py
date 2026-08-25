import re
from typing import Callable

from flask import Flask
from playwright.sync_api import Locator, Page, Route, expect

from backend import db
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import (
    clear_then_send_keys,
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
    """Return the inner-text of every visible member badge as a list.

    Args:
        page: Playwright Page open to a selected UTub

    Returns:
        List of member usernames
    """
    badges_locator = page.locator(HPL.BADGES_MEMBERS)
    expect(badges_locator.first).to_be_visible()
    return badges_locator.all_inner_texts()


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
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)
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
    """Hover over the named member badge and click the delete button.

    Playwright's click auto-waits for the delete button to be actionable
    (visible, stable, enabled) after the hover reveals it — no pause needed.

    Args:
        page: Playwright Page open to a selected UTub owned by the current user
        member_name: Exact username text of the member to delete
    """
    badge = page.locator(HPL.BADGES_MEMBERS).filter(has_text=member_name).first
    expect(badge).to_be_visible()
    badge.hover()
    badge.locator(HPL.BUTTON_MEMBER_DELETE).click()


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
