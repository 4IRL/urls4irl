import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.cli.mock_constants import USERNAME_BASE
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    create_member_active_utub,
    open_member_name_filter,
)
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    click_on_navbar,
    wait_for_class_to_be_removed,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.members_ui

# A search term whose substring matches no member username in the seeded UTub.
NO_MATCH_SEARCH_TERM = "zzzzzz"


def _get_owner_and_other_member(
    app: Flask, utub_id: int, owner_user_id: int
) -> tuple[Users, Users]:
    """
    Returns the (owner, other_member) Users for the given UTub. The owner is the
    creator (``owner_user_id``); the other member is any non-owner member.
    """
    with app.app_context():
        owner: Users = Users.query.get(owner_user_id)
        other_membership: Utub_Members = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id,
            Utub_Members.user_id != owner_user_id,
        ).first()
        return owner, other_membership.to_user


def _member_badge_selector(member_id: int) -> str:
    return f"{HPL.BADGES_MEMBERS}[memberid='{member_id}']"


def _add_existing_user_as_member(
    app: Flask, utub_id: int, username: str
) -> tuple[int, str]:
    """
    Adds the existing U4I user with ``username`` to ``utub_id`` as a regular
    member (not creator). Used to seed a second member so an active filter has a
    non-owner row to keep visible while the owner is filtered out. Returns the
    (user_id, username) as primitives so callers do not hold a detached ORM row.
    """
    with app.app_context():
        user: Users = Users.query.filter(Users.username == username).first()
        membership = Utub_Members()
        membership.utub_id = utub_id
        membership.user_id = user.id
        membership.member_role = Member_Role.MEMBER
        db.session.add(membership)
        db.session.commit()
        return user.id, user.username


def _unique_username_substring(target: Users, others: list[Users]) -> str:
    """
    Returns the shortest trailing-character substring of ``target.username`` that
    is NOT a substring of any username in ``others``. Mock usernames share the
    ``u4i_test`` prefix and differ only by a trailing digit, so the unique digit
    suffix isolates a single member when typed into the filter.
    """
    username = target.username
    other_names = [member.username for member in others]
    for length in range(1, len(username) + 1):
        candidate = username[-length:]
        if all(candidate not in name for name in other_names):
            return candidate
    return username


def test_member_filter_funnel_visible_when_utub_selected(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a user selects a UTub that has members
    WHEN the member deck renders
    THEN the funnel toggle (#memberNameFilterBtn) is visible while the filter input
         wrap (#SearchMemberWrap) stays hidden until the funnel is opened.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    wait_until_visible_css_selector(page=page, css_selector=HPL.BADGES_MEMBERS)

    # Before opening: funnel shown, search wrap hidden.
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_MEMBER_NAME_FILTER)
    assert_not_visible_css_selector(page=page, css_selector=HPL.MEMBER_SEARCH_WRAP)

    # Opening the funnel reveals the search input wrap and input.
    input_elem = open_member_name_filter(page=page)
    assert input_elem is not None
    assert_visible_css_selector(page=page, css_selector=HPL.MEMBER_SEARCH_WRAP)
    assert_visible_css_selector(page=page, css_selector=HPL.MEMBER_SEARCH_INPUT)


def test_member_filter_togglable_on_mobile(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a user on a mobile viewport (<992px) selects a UTub with members
    WHEN the member deck renders
    THEN the filter input is hidden by default and the funnel reveals it
         (divergence from the UTub filter, which is always-visible on mobile).
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app,
        page=page_mobile_portrait,
        user_id=user_id,
        utub_id=utub_user_created.id,
    )

    # On mobile the member deck is a separate panel; navigate to it via the navbar.
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

    wait_until_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.BADGES_MEMBERS
    )

    # Mobile: the search wrap is hidden by default; the funnel toggles it (this is
    # the divergence from the UTub filter, which is always-visible on mobile).
    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.BUTTON_MEMBER_NAME_FILTER
    )
    assert_not_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.MEMBER_SEARCH_WRAP
    )

    open_member_name_filter(page=page_mobile_portrait)
    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.MEMBER_SEARCH_WRAP
    )
    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.MEMBER_SEARCH_INPUT
    )


def test_typing_substring_hides_non_matching_members_and_clearing_shows_all(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with multiple members is selected and the filter is open
    WHEN the user types a substring matching only one member, then clears it
    THEN the non-matching member rows are hidden while the matching one stays
         visible, and clearing the term shows all rows again.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    owner, other_member = _get_owner_and_other_member(
        app, utub_user_created.id, user_id
    )
    match_term = _unique_username_substring(other_member, [owner])
    matched_selector = _member_badge_selector(other_member.id)
    owner_selector = _member_badge_selector(owner.id)

    wait_until_visible_css_selector(page=page, css_selector=HPL.BADGES_MEMBERS)

    # Before typing: both the matching member and the owner are visible.
    assert_visible_css_selector(page=page, css_selector=matched_selector)
    assert_visible_css_selector(page=page, css_selector=owner_selector)

    input_elem = open_member_name_filter(page=page)
    input_elem.fill(match_term)

    # Matching row stays visible; the owner (non-matching) becomes hidden.
    assert_visible_css_selector(page=page, css_selector=matched_selector)
    assert_not_visible_css_selector(page=page, css_selector=owner_selector)

    # Clearing the term shows all rows again. fill("") fires an input event that
    # resets the filter.
    input_elem.fill("")
    assert_visible_css_selector(page=page, css_selector=matched_selector)
    assert_visible_css_selector(page=page, css_selector=owner_selector)


def test_filter_term_not_matching_owner_hides_owner_row(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with an owner and other members is selected
    WHEN the user types a term that does NOT match the owner's username
    THEN the owner row (#UTubOwner > .member) is hidden (the filter scope includes
         the owner — design decision #1).
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    owner, other_member = _get_owner_and_other_member(
        app, utub_user_created.id, user_id
    )
    # A term unique to a non-owner member, so the owner does not match.
    non_owner_term = _unique_username_substring(other_member, [owner])

    wait_until_visible_css_selector(page=page, css_selector=HPL.BADGES_MEMBERS)

    # Before typing: the owner row is visible.
    assert_visible_css_selector(page=page, css_selector=HPL.BADGE_OWNER)

    input_elem = open_member_name_filter(page=page)
    input_elem.fill(non_owner_term)

    # The owner is hidden because its username does not contain the term.
    assert_not_visible_css_selector(page=page, css_selector=HPL.BADGE_OWNER)
    assert_visible_css_selector(
        page=page, css_selector=_member_badge_selector(other_member.id)
    )


def test_filter_term_matching_only_owner_shows_owner_hides_list_members(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with an owner and other members is selected
    WHEN the user types a term that matches ONLY the owner's username
    THEN the owner row stays visible while every #listMembers row is hidden.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    with app.app_context():
        owner: Users = Users.query.get(user_id)
        other_members = [
            membership.to_user
            for membership in Utub_Members.query.filter(
                Utub_Members.utub_id == utub_user_created.id,
                Utub_Members.user_id != user_id,
            ).all()
        ]
    owner_only_term = _unique_username_substring(owner, other_members)

    wait_until_visible_css_selector(page=page, css_selector=HPL.BADGES_MEMBERS)

    # Before typing: the owner and at least one list member are visible.
    assert_visible_css_selector(page=page, css_selector=HPL.BADGE_OWNER)
    assert len(other_members) >= 1
    assert_visible_css_selector(
        page=page, css_selector=_member_badge_selector(other_members[0].id)
    )

    input_elem = open_member_name_filter(page=page)
    input_elem.fill(owner_only_term)

    # The owner stays visible; every non-owner list member is hidden.
    assert_visible_css_selector(page=page, css_selector=HPL.BADGE_OWNER)
    for other_member in other_members:
        assert_not_visible_css_selector(
            page=page, css_selector=_member_badge_selector(other_member.id)
        )


def test_no_results_message_shown_when_term_matches_no_members(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with members is selected and the filter is open
    WHEN the user types a term matching no member name
    THEN the no-results message (#MemberSearchNoResults) is shown with the expected
         text from UTS.MEMBER_SEARCH_NO_MEMBERS.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    wait_until_visible_css_selector(page=page, css_selector=HPL.BADGES_MEMBERS)

    # Before typing: the no-results message is hidden.
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.MEMBER_SEARCH_NO_RESULTS
    )

    input_elem = open_member_name_filter(page=page)
    input_elem.fill(NO_MATCH_SEARCH_TERM)

    assert_visible_css_selector(page=page, css_selector=HPL.MEMBER_SEARCH_NO_RESULTS)
    expect(page.locator(HPL.MEMBER_SEARCH_NO_RESULTS)).to_have_text(
        UTS.MEMBER_SEARCH_NO_MEMBERS
    )


def test_escape_closes_filter_returns_focus_to_funnel_and_clears_term(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with members is selected and the filter is open with a typed term
    WHEN the user presses ESC
    THEN the filter closes, focus returns to the funnel toggle, and the term is
         cleared.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    owner, other_member = _get_owner_and_other_member(
        app, utub_user_created.id, user_id
    )
    typed_term = _unique_username_substring(other_member, [owner])

    wait_until_visible_css_selector(page=page, css_selector=HPL.BADGES_MEMBERS)

    input_elem = open_member_name_filter(page=page)
    input_elem.fill(typed_term)

    # Before ESC: the term is present and the funnel is hidden (X shown instead).
    assert input_elem.input_value() == typed_term
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_MEMBER_NAME_FILTER
    )

    # Ensure the input has focus before pressing ESC so the keydown is delivered.
    wait_until_in_focus(page=page, css_selector=HPL.MEMBER_SEARCH_INPUT)
    page.keyboard.press("Escape")

    # After ESC: the filter closes, the funnel reappears and regains focus, and the
    # term is cleared.
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_MEMBER_NAME_FILTER)
    assert_not_visible_css_selector(page=page, css_selector=HPL.MEMBER_SEARCH_WRAP)
    wait_until_in_focus(page=page, css_selector=HPL.BUTTON_MEMBER_NAME_FILTER)

    open_member_name_filter(page=page)
    assert page.locator(HPL.MEMBER_SEARCH_INPUT).input_value() == ""


def test_filter_resets_on_add_member_form_open(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub owner has the member filter open with a typed term
    WHEN they open the add-member form via the create button
    THEN the filter box collapses (#MemberDeck loses .member-search-open) and the
         member list (#displayMemberWrap) is hidden.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    owner, other_member = _get_owner_and_other_member(
        app, utub_user_created.id, user_id
    )
    typed_term = _unique_username_substring(other_member, [owner])

    wait_until_visible_css_selector(page=page, css_selector=HPL.BADGES_MEMBERS)

    input_elem = open_member_name_filter(page=page)
    input_elem.fill(typed_term)

    # Before opening the add-member form: the filter is open.
    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(
        re.compile(r"(^|\s)member-search-open(\s|$)")
    )

    # Opening the add-member form closes the filter and hides the member list.
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)

    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(
        re.compile(r"(^|\s)member-search-open(\s|$)")
    )
    assert_not_visible_css_selector(page=page, css_selector=HPL.DISPLAY_MEMBER_WRAP)


def test_member_filter_reapplied_after_successful_add(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub owner has a filter term active that hides the owner row while a
          seeded non-owner member stays visible
    WHEN they open the add-member form (which collapses the filter and clears the
         term) and successfully add a NEW member
    THEN createMemberSuccess -> reapplyMemberFilter re-evaluates the refreshed
         #listMembers against the now-empty term: every row (the previously hidden
         owner, the seeded member, and the newly appended member) is visible. This
         proves reapplyMemberFilter ran on the create-success path rather than the
         new badge merely being appended while stale `.hidden` state persisted on
         the owner row.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    # Seed a second (non-owner) member BEFORE selecting the UTub so the member deck
    # renders it on the initial load (a re-select of the already-active UTub would
    # not re-fetch the member list).
    seeded_username = USERNAME_BASE + "3"
    seeded_member_id, seeded_member_username = _add_existing_user_as_member(
        app, utub_user_created.id, seeded_username
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_member_username = USERNAME_BASE + "2"
    with app.app_context():
        owner: Users = Users.query.get(user_id)
        owner_id = owner.id
        owner_username = owner.username
        new_member: Users = Users.query.filter(
            Users.username == new_member_username
        ).first()
        new_member_id = new_member.id

    # A term unique to the seeded member, so the owner does not match and is hidden.
    filter_term = next(
        seeded_member_username[-length:]
        for length in range(1, len(seeded_member_username) + 1)
        if seeded_member_username[-length:] not in owner_username
    )

    owner_selector = _member_badge_selector(owner_id)
    seeded_selector = _member_badge_selector(seeded_member_id)
    new_member_selector = _member_badge_selector(new_member_id)

    # Gate on the member deck finishing its render before targeting a specific
    # badge (mirrors the sibling filter tests): the deck repaints just after UTub
    # select, so wait for any member badge first to avoid racing the render.
    wait_until_visible_css_selector(page=page, css_selector=HPL.BADGES_MEMBERS)
    wait_until_visible_css_selector(page=page, css_selector=seeded_selector)

    # Before adding: owner and seeded member are both visible.
    assert_visible_css_selector(page=page, css_selector=owner_selector)
    assert_visible_css_selector(page=page, css_selector=seeded_selector)

    # Apply the filter: the owner row is hidden, the seeded member stays visible.
    input_elem = open_member_name_filter(page=page)
    input_elem.fill(filter_term)
    assert_not_visible_css_selector(page=page, css_selector=owner_selector)
    assert_visible_css_selector(page=page, css_selector=seeded_selector)

    # Add a brand-new member (opening the form collapses the filter and clears the
    # term; on success reapplyMemberFilter runs against the empty term).
    create_member_active_utub(page=page, member_name=new_member_username)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_MEMBER_SUBMIT_CREATE)

    # After the add: reapplyMemberFilter re-evaluated every row against the cleared
    # term, so the previously hidden owner is visible again and the newly appended
    # member is visible alongside the seeded member.
    wait_until_visible_css_selector(page=page, css_selector=new_member_selector)
    assert_visible_css_selector(page=page, css_selector=owner_selector)
    assert_visible_css_selector(page=page, css_selector=seeded_selector)
    assert_visible_css_selector(page=page, css_selector=new_member_selector)
