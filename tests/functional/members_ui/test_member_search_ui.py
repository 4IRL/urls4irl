from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.members_ui.selenium_utils import open_member_name_filter
from tests.functional.selenium_utils import (
    Decks,
    click_on_navbar,
    wait_for_class_to_be_removed,
    wait_then_click_element,
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
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
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
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    wait_until_visible_css_selector(browser, HPL.BADGES_MEMBERS, timeout=3)

    # Before opening: funnel shown, search wrap hidden.
    assert_visible_css_selector(browser, HPL.BUTTON_MEMBER_NAME_FILTER, time=3)
    assert_not_visible_css_selector(browser, HPL.MEMBER_SEARCH_WRAP, time=3)

    # Opening the funnel reveals the search input wrap and input.
    input_elem = open_member_name_filter(browser)
    assert input_elem is not None
    assert_visible_css_selector(browser, HPL.MEMBER_SEARCH_WRAP, time=3)
    assert_visible_css_selector(browser, HPL.MEMBER_SEARCH_INPUT, time=3)


def test_member_filter_togglable_on_mobile(
    browser_mobile_portrait: WebDriver, create_test_utubmembers, provide_app: Flask
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
    browser = browser_mobile_portrait

    login_user_and_select_utub_by_utubid_mobile(
        app, browser, user_id, utub_user_created.id
    )

    # On mobile the member deck is a separate panel; navigate to it via the navbar.
    click_on_navbar(browser)
    wait_then_click_element(browser, HPL.NAVBAR_MEMBER_DECK)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    assert_panel_visibility_mobile(browser, visible_deck=Decks.MEMBERS)

    wait_until_visible_css_selector(browser, HPL.BADGES_MEMBERS, timeout=3)

    # Mobile: the search wrap is hidden by default; the funnel toggles it (this is
    # the divergence from the UTub filter, which is always-visible on mobile).
    assert_visible_css_selector(browser, HPL.BUTTON_MEMBER_NAME_FILTER, time=3)
    assert_not_visible_css_selector(browser, HPL.MEMBER_SEARCH_WRAP, time=3)

    open_member_name_filter(browser)
    assert_visible_css_selector(browser, HPL.MEMBER_SEARCH_WRAP, time=3)
    assert_visible_css_selector(browser, HPL.MEMBER_SEARCH_INPUT, time=3)


def test_typing_substring_hides_non_matching_members_and_clearing_shows_all(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
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
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    owner, other_member = _get_owner_and_other_member(
        app, utub_user_created.id, user_id
    )
    match_term = _unique_username_substring(other_member, [owner])
    matched_selector = _member_badge_selector(other_member.id)
    owner_selector = _member_badge_selector(owner.id)

    wait_until_visible_css_selector(browser, HPL.BADGES_MEMBERS, timeout=3)

    # Before typing: both the matching member and the owner are visible.
    assert_visible_css_selector(browser, matched_selector, time=3)
    assert_visible_css_selector(browser, owner_selector, time=3)

    input_elem = open_member_name_filter(browser)
    input_elem.send_keys(match_term)

    # Matching row stays visible; the owner (non-matching) becomes hidden.
    assert_visible_css_selector(browser, matched_selector, time=3)
    assert_not_visible_css_selector(browser, owner_selector, time=3)

    # Clearing the term shows all rows again. Backspace one key per typed char so
    # each deletion fires an `input` event.
    input_elem.send_keys(Keys.BACKSPACE * len(match_term))
    assert_visible_css_selector(browser, matched_selector, time=3)
    assert_visible_css_selector(browser, owner_selector, time=3)


def test_filter_term_not_matching_owner_hides_owner_row(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
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
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    owner, other_member = _get_owner_and_other_member(
        app, utub_user_created.id, user_id
    )
    # A term unique to a non-owner member, so the owner does not match.
    non_owner_term = _unique_username_substring(other_member, [owner])

    wait_until_visible_css_selector(browser, HPL.BADGES_MEMBERS, timeout=3)

    # Before typing: the owner row is visible.
    assert_visible_css_selector(browser, HPL.BADGE_OWNER, time=3)

    input_elem = open_member_name_filter(browser)
    input_elem.send_keys(non_owner_term)

    # The owner is hidden because its username does not contain the term.
    assert_not_visible_css_selector(browser, HPL.BADGE_OWNER, time=3)
    assert_visible_css_selector(
        browser, _member_badge_selector(other_member.id), time=3
    )


def test_filter_term_matching_only_owner_shows_owner_hides_list_members(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with an owner and other members is selected
    WHEN the user types a term that matches ONLY the owner's username
    THEN the owner row stays visible while every #listMembers row is hidden.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

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

    wait_until_visible_css_selector(browser, HPL.BADGES_MEMBERS, timeout=3)

    # Before typing: the owner and at least one list member are visible.
    assert_visible_css_selector(browser, HPL.BADGE_OWNER, time=3)
    assert len(other_members) >= 1
    assert_visible_css_selector(
        browser, _member_badge_selector(other_members[0].id), time=3
    )

    input_elem = open_member_name_filter(browser)
    input_elem.send_keys(owner_only_term)

    # The owner stays visible; every non-owner list member is hidden.
    assert_visible_css_selector(browser, HPL.BADGE_OWNER, time=3)
    for other_member in other_members:
        assert_not_visible_css_selector(
            browser, _member_badge_selector(other_member.id), time=3
        )


def test_no_results_message_shown_when_term_matches_no_members(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
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
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    wait_until_visible_css_selector(browser, HPL.BADGES_MEMBERS, timeout=3)

    # Before typing: the no-results message is hidden.
    assert_not_visible_css_selector(browser, HPL.MEMBER_SEARCH_NO_RESULTS, time=3)

    input_elem = open_member_name_filter(browser)
    input_elem.send_keys(NO_MATCH_SEARCH_TERM)

    assert_visible_css_selector(browser, HPL.MEMBER_SEARCH_NO_RESULTS, time=3)
    no_results_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.MEMBER_SEARCH_NO_RESULTS
    )
    assert no_results_elem.text == UTS.MEMBER_SEARCH_NO_MEMBERS


def test_escape_closes_filter_returns_focus_to_funnel_and_clears_term(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
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
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    owner, other_member = _get_owner_and_other_member(
        app, utub_user_created.id, user_id
    )
    typed_term = _unique_username_substring(other_member, [owner])

    wait_until_visible_css_selector(browser, HPL.BADGES_MEMBERS, timeout=3)

    input_elem = open_member_name_filter(browser)
    input_elem.send_keys(typed_term)

    # Before ESC: the term is present and the funnel is hidden (X shown instead).
    assert input_elem.get_attribute("value") == typed_term
    assert_not_visible_css_selector(browser, HPL.BUTTON_MEMBER_NAME_FILTER, time=3)

    input_elem.send_keys(Keys.ESCAPE)

    # After ESC: the filter closes, the funnel reappears and regains focus, and the
    # term is cleared.
    assert_visible_css_selector(browser, HPL.BUTTON_MEMBER_NAME_FILTER, time=3)
    assert_not_visible_css_selector(browser, HPL.MEMBER_SEARCH_WRAP, time=3)
    wait_until_in_focus(browser, HPL.BUTTON_MEMBER_NAME_FILTER, timeout=3)

    open_member_name_filter(browser)
    reopened_input = browser.find_element(By.CSS_SELECTOR, HPL.MEMBER_SEARCH_INPUT)
    assert reopened_input.get_attribute("value") == ""


def test_filter_resets_on_add_member_form_open(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
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
    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    owner, other_member = _get_owner_and_other_member(
        app, utub_user_created.id, user_id
    )
    typed_term = _unique_username_substring(other_member, [owner])

    wait_until_visible_css_selector(browser, HPL.BADGES_MEMBERS, timeout=3)

    input_elem = open_member_name_filter(browser)
    input_elem.send_keys(typed_term)

    # Before opening the add-member form: the filter is open.
    member_deck = browser.find_element(By.CSS_SELECTOR, HPL.MEMBER_DECK)
    assert "member-search-open" in (member_deck.get_attribute("class") or "")

    # Opening the add-member form closes the filter and hides the member list.
    wait_then_click_element(browser, HPL.BUTTON_MEMBER_CREATE, time=3)

    WebDriverWait(browser, 3).until(
        lambda _: "member-search-open"
        not in (
            browser.find_element(By.CSS_SELECTOR, HPL.MEMBER_DECK).get_attribute(
                "class"
            )
            or ""
        )
    )
    assert_not_visible_css_selector(browser, HPL.DISPLAY_MEMBER_WRAP, time=3)
