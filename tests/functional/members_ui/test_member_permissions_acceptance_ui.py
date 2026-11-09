"""Real-browser acceptance for the Members "Member permissions" settings: the
role matrix, the co-owner Remove-only kebab (including the CSS-level contract
jsdom cannot assert), the plain-member add gate and the stale-policy refusals."""

from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.utub_members import Member_Role
from backend.utils.strings.user_strs import (
    CO_OWNER_REMOVE_NOT_ALLOWED,
    INVALID_PERMISSION_TO_REMOVE,
    MEMBER_ADD_NOT_ALLOWED,
    MEMBER_DELETE_WARNING,
    MEMBER_LEAVE_WARNING,
)
from backend.utils.strings.utub_strs import PANEL_SETTINGS_OWNER_ONLY
from tests.functional.db_utils import (
    get_utub_this_user_created,
    is_user_member_of_utub,
    isolate_user_from_viewer,
    remove_user_from_utub,
    set_member_role_in_utub,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    CO_OWNER_ID,
    OUTSIDER_ID,
    OUTSIDER_NAME,
    OWNER_ID,
    SUGGESTED_ID,
    SUGGESTED_NAME,
    TARGET_ID,
    click_add_member_submit,
    close_add_member_combobox,
    co_owner_kebab,
    computed_styles,
    element_box,
    expect_notice,
    is_settings_patch,
    login_as,
    member_badge_by_username,
    member_row,
    open_add_member_combobox,
    open_co_owner_menu_and_click_remove,
    open_members_gear,
    seed_policy,
    stage_co_member_suggestion,
    stage_outsider_username,
    submit_confirm_modal,
    text_contrast_ratio,
)
from tests.functional.playwright_utils import (
    wait_for_css_transitions_to_finish,
    wait_for_modal_ready,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = [pytest.mark.members_ui, pytest.mark.home_ui]

_SWITCHES = [
    pytest.param(
        HPL.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_SWITCH,
        id="co_owners_can_remove",
    ),
    pytest.param(
        HPL.MEMBERS_PERMISSIONS_MEMBERS_ADD_SWITCH,
        id="members_can_add",
    ),
]


def login_as_co_owner(*, app: Flask, page: Page) -> int:
    return login_as(
        app=app, page=page, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )


def confirm_modal_and_wait_closed(*, page: Page) -> None:
    submit_confirm_modal(page=page)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)


@pytest.mark.parametrize("switch_selector", _SWITCHES)
def test_owner_toggles_switch_and_value_survives_reload(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
    switch_selector: str,
):
    """
    GIVEN the owner of a UTub with both permission switches off
    WHEN they turn one on in the Members gear and reload the page
    THEN the PATCH succeeds and the switch is still on after the reload
    """
    app = provide_app
    login_as(app=app, page=page, user_id=OWNER_ID)

    open_members_gear(page=page)
    switch = page.locator(switch_selector)
    expect(switch).to_have_attribute("aria-checked", "false")
    with page.expect_response(is_settings_patch) as response_info:
        switch.click()
    assert response_info.value.status == 200
    expect(switch).to_have_attribute("aria-checked", "true")

    page.reload()
    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_ROW_ROLE_ICON)
    open_members_gear(page=page)
    expect(page.locator(switch_selector)).to_have_attribute("aria-checked", "true")


def test_co_owner_sees_owner_only_note(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a co-owner of a UTub
    WHEN they open the Members gear
    THEN the Member permissions section shows the owner-only note and both
        switches are read-only
    """
    login_as_co_owner(app=provide_app, page=page)

    open_members_gear(page=page)
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_SECTION)).to_be_visible()
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_NOTE)).to_have_text(
        PANEL_SETTINGS_OWNER_ONLY
    )
    for selector in (
        HPL.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_SWITCH,
        HPL.MEMBERS_PERMISSIONS_MEMBERS_ADD_SWITCH,
    ):
        expect(page.locator(selector)).to_have_attribute("aria-disabled", "true")


def test_plain_member_gear_has_no_permissions_section(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a plain member of a UTub
    WHEN they open the Members gear
    THEN the gear opens but has no Member permissions section
    """
    login_as(app=provide_app, page=page, user_id=CO_OWNER_ID)

    open_members_gear(page=page)
    expect(page.locator(HPL.MEMBERS_PERMISSIONS_SECTION)).to_have_count(0)


def test_co_owner_removes_plain_member_through_remove_only_menu(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner allowed co-owners to remove members
    WHEN a co-owner opens a plain member's kebab and confirms Remove
    THEN the menu held only Remove, the delete copy was shown and the member is
        gone from the deck and the UTub
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, co_owners_can_remove=True)
    login_as_co_owner(app=app, page=page)

    open_co_owner_menu_and_click_remove(page=page, member_id=TARGET_ID)
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    expect(page.locator(HPL.BODY_MODAL)).to_have_text(MEMBER_DELETE_WARNING)
    confirm_modal_and_wait_closed(page=page)

    wait_for_selector_to_be_removed(
        page=page, css_selector=f'{HPL.BADGES_MEMBERS}[memberid="{TARGET_ID}"]'
    )
    assert not is_user_member_of_utub(app, TARGET_ID, utub_id)


def test_co_owner_kebab_visibility_follows_the_deck_attribute_in_css(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a co-owner whose UTub has removal switched off (kebabs are built but hidden)
    WHEN the #MemberDeck[data-co-owners-can-remove] attribute is true, false or missing
    THEN the kebab's computed display is none (and it cannot take focus) unless
        the attribute is exactly "true", when it is visible and keyboard-reachable
    """
    login_as_co_owner(app=provide_app, page=page)
    deck = page.locator(HPL.MEMBER_DECK)
    kebab = co_owner_kebab(page=page, member_id=TARGET_ID)
    row = member_row(page=page, member_id=TARGET_ID)

    def can_focus() -> bool:
        return kebab.evaluate(
            "(el) => { el.focus(); return document.activeElement === el; }"
        )

    # Default state: removal off, so the attribute is not "true".
    expect(kebab).to_be_attached()
    assert computed_styles(locator=kebab, properties=["display"]) == {"display": "none"}
    assert not can_focus()

    deck.evaluate("(el) => el.removeAttribute('data-co-owners-can-remove')")
    assert computed_styles(locator=kebab, properties=["display"]) == {"display": "none"}
    assert not can_focus()

    deck.evaluate("(el) => el.setAttribute('data-co-owners-can-remove', 'false')")
    assert computed_styles(locator=kebab, properties=["display"]) == {"display": "none"}
    assert not can_focus()

    deck.evaluate("(el) => el.setAttribute('data-co-owners-can-remove', 'true')")
    assert computed_styles(locator=kebab, properties=["display"])["display"] != "none"
    expect(kebab).to_be_visible()
    kebab.focus()
    expect(kebab).to_be_focused()
    page.keyboard.press("Enter")
    expect(row.locator(HPL.MEMBER_ROW_MENU)).to_be_visible()
    page.keyboard.press("Escape")


def test_co_owner_kebab_is_inert_while_add_is_open_and_sized_like_the_owners(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN removal is on and the co-owner (who can add) opens the add combobox
    WHEN the kebab's computed style is read
    THEN pointer-events is none and opacity 0.5, equal to the owner kebab's
        values in the same state, and (fine pointer) its box equals the owner's
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, co_owners_can_remove=True)
    props = ["pointer-events", "opacity"]

    def measure(*, selector: str) -> tuple[dict[str, float], dict[str, str]]:
        kebab = member_row(page=page, member_id=TARGET_ID).locator(selector)
        expect(kebab).to_be_visible()
        box = element_box(locator=kebab)
        open_add_member_combobox(page=page)
        # The kebab fades to 0.5 over 0.2s; the retrying assertion waits it out.
        expect(kebab).to_have_css("opacity", "0.5")
        return box, computed_styles(locator=kebab, properties=props)

    login_as_co_owner(app=app, page=page)
    co_owner_box, co_owner_styles = measure(selector=HPL.MEMBER_ROW_KEBAB_CO_OWNER)
    assert co_owner_styles == {"pointer-events": "none", "opacity": "0.5"}

    page.context.clear_cookies()
    login_as(app=app, page=page, user_id=OWNER_ID)
    owner_box, owner_styles = measure(selector=HPL.MEMBER_ROW_KEBAB)
    assert owner_styles == co_owner_styles
    assert co_owner_box == owner_box


def test_stale_demoted_co_owner_remove_is_refused_with_notice(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a co-owner's page still shows the kebab after the owner demoted them
    WHEN they confirm Remove on a plain member
    THEN the modal closes, the not-allowed notice shows, the member stays and
        the page does not redirect to the error page
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, co_owners_can_remove=True)
    login_as_co_owner(app=app, page=page)
    kebab = co_owner_kebab(page=page, member_id=TARGET_ID)
    expect(kebab).to_be_visible()

    set_member_role_in_utub(app, CO_OWNER_ID, utub_id, Member_Role.MEMBER)
    open_co_owner_menu_and_click_remove(page=page, member_id=TARGET_ID)
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    confirm_modal_and_wait_closed(page=page)

    expect_notice(page=page, text=INVALID_PERMISSION_TO_REMOVE)
    expect(member_row(page=page, member_id=TARGET_ID)).to_be_attached()
    assert is_user_member_of_utub(app, TARGET_ID, utub_id)


def test_removal_switched_off_after_load_is_learned_on_refusal(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a co-owner loaded the page with removal on, then the owner turned it off
    WHEN the co-owner confirms Remove on a plain member (no refresh)
    THEN the refusal is announced and shown in the notice, the co-owner kebabs
        hide, the modal closes, the member stays and there is no redirect
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, co_owners_can_remove=True)
    login_as_co_owner(app=app, page=page)
    expect(co_owner_kebab(page=page, member_id=TARGET_ID)).to_be_visible()

    seed_policy(app=app, utub_id=utub_id, co_owners_can_remove=False)
    open_co_owner_menu_and_click_remove(page=page, member_id=TARGET_ID)
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    confirm_modal_and_wait_closed(page=page)

    expect_notice(page=page, text=CO_OWNER_REMOVE_NOT_ALLOWED)
    expect(page.locator(HPL.MEMBER_ROW_ACTION_ANNOUNCEMENT)).to_contain_text(
        CO_OWNER_REMOVE_NOT_ALLOWED
    )
    expect(co_owner_kebab(page=page, member_id=TARGET_ID)).to_have_css(
        "display", "none"
    )
    expect(member_row(page=page, member_id=TARGET_ID)).to_be_attached()
    assert is_user_member_of_utub(app, TARGET_ID, utub_id)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_refusal_notice_text_meets_aa_contrast_in_both_themes(
    page: Page, create_test_utubmembers, provide_app: Flask, theme: str
):
    """
    GIVEN a refusal notice is showing in the Members deck
    WHEN its text colour is compared with its effective background
    THEN the WCAG contrast ratio is at least 4.5 in the dark and light themes
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, co_owners_can_remove=True)
    login_as_co_owner(app=app, page=page)
    seed_policy(app=app, utub_id=utub_id, co_owners_can_remove=False)
    open_co_owner_menu_and_click_remove(page=page, member_id=TARGET_ID)
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    confirm_modal_and_wait_closed(page=page)
    expect_notice(page=page, text=CO_OWNER_REMOVE_NOT_ALLOWED)

    page.evaluate(
        "(theme) => document.documentElement.setAttribute('data-theme', theme)", theme
    )
    expect(page.locator("html")).to_have_attribute("data-theme", theme)
    # Let the theme's colour transitions on the notice and its ancestors settle.
    wait_for_css_transitions_to_finish(locator=page.locator("html"))
    ratio = text_contrast_ratio(locator=page.locator(HPL.MEMBER_DECK_NOTICE))
    assert ratio >= 4.5, f"{theme} notice contrast {ratio:.2f}"


def test_co_owner_leaves_after_adding_a_member(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a co-owner who added a member through the combobox
    WHEN they click Leave and confirm
    THEN the leave copy is shown and the co-owner's own membership is removed,
        not the appended member's
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    remove_user_from_utub(app, OUTSIDER_ID, utub_id)
    isolate_user_from_viewer(app, user_id=OUTSIDER_ID, viewer_id=CO_OWNER_ID)
    login_as_co_owner(app=app, page=page)

    open_add_member_combobox(page=page)
    stage_outsider_username(page=page, username=OUTSIDER_NAME)
    click_add_member_submit(page=page)
    expect(member_badge_by_username(page=page, username=OUTSIDER_NAME)).to_be_attached()
    close_add_member_combobox(page=page)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    expect(page.locator(HPL.BODY_MODAL)).to_have_text(MEMBER_LEAVE_WARNING)
    confirm_modal_and_wait_closed(page=page)
    wait_for_selector_to_be_removed(
        page=page, css_selector=f'{HPL.SELECTORS_UTUB}[utubid="{utub_id}"]'
    )

    assert not is_user_member_of_utub(app, CO_OWNER_ID, utub_id)
    assert is_user_member_of_utub(app, OUTSIDER_ID, utub_id)


@pytest.mark.parametrize("by_suggestion", [True, False], ids=["suggestion", "exact"])
def test_plain_member_adds_when_adding_is_on(
    page: Page, create_test_utubmembers, provide_app: Flask, by_suggestion: bool
):
    """
    GIVEN the owner allowed members to add members
    WHEN a plain member stages a co-member suggestion, or an exact username,
        and submits
    THEN the new member badge appears and the user joined the UTub
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, members_can_add=True)
    new_id = SUGGESTED_ID if by_suggestion else OUTSIDER_ID
    new_name = SUGGESTED_NAME if by_suggestion else OUTSIDER_NAME
    remove_user_from_utub(app, new_id, utub_id)
    if not by_suggestion:
        isolate_user_from_viewer(app, user_id=new_id, viewer_id=CO_OWNER_ID)
    login_as(app=app, page=page, user_id=CO_OWNER_ID)

    open_add_member_combobox(page=page)
    if by_suggestion:
        stage_co_member_suggestion(page=page, username=new_name)
    else:
        stage_outsider_username(page=page, username=new_name)
    click_add_member_submit(page=page)

    expect(member_badge_by_username(page=page, username=new_name)).to_be_attached()
    close_add_member_combobox(page=page)
    expect(member_badge_by_username(page=page, username=new_name)).to_be_visible()
    assert is_user_member_of_utub(app, new_id, utub_id)


def test_plain_member_has_no_add_button_when_adding_is_off(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN adding is off (the default)
    WHEN a plain member views the Members deck
    THEN there is no add button
    """
    login_as(app=provide_app, page=page, user_id=CO_OWNER_ID)

    expect(page.locator(HPL.BUTTON_MEMBER_CREATE)).to_be_hidden()


def test_submit_after_adding_was_turned_off_shows_notice_without_redirect(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a plain member staged a chip with adding on, then the owner turned it off
    WHEN the member submits before any refresh
    THEN the refusal notice shows, the add UI goes away, nobody is added and
        the page does not redirect
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, members_can_add=True)
    remove_user_from_utub(app, OUTSIDER_ID, utub_id)
    isolate_user_from_viewer(app, user_id=OUTSIDER_ID, viewer_id=CO_OWNER_ID)
    login_as(app=app, page=page, user_id=CO_OWNER_ID)

    open_add_member_combobox(page=page)
    stage_outsider_username(page=page, username=OUTSIDER_NAME)
    seed_policy(app=app, utub_id=utub_id, members_can_add=False)
    click_add_member_submit(page=page)

    expect_notice(page=page, text=MEMBER_ADD_NOT_ALLOWED)
    expect(page.locator(HPL.BUTTON_MEMBER_CREATE)).to_be_hidden()
    expect(page.locator(HPL.MEMBER_COMBOBOX_INPUT)).to_be_hidden()
    assert not is_user_member_of_utub(app, OUTSIDER_ID, utub_id)


def test_refresh_after_adding_was_turned_off_removes_the_add_ui(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a plain member has the add combobox open
    WHEN the owner turns adding off and the page is refreshed
    THEN the add button and combobox are gone
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, members_can_add=True)
    login_as(app=app, page=page, user_id=CO_OWNER_ID)
    open_add_member_combobox(page=page)

    seed_policy(app=app, utub_id=utub_id, members_can_add=False)
    page.reload()

    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_ROW_ROLE_ICON)
    expect(page.locator(HPL.BUTTON_MEMBER_CREATE)).to_be_hidden()
    expect(page.locator(HPL.MEMBER_COMBOBOX_INPUT)).to_be_hidden()
