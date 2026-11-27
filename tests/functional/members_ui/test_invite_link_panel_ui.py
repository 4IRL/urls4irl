"""Real-browser acceptance for the Members deck invite link panel (read-only):
who sees the trigger, each rendered state, the keyboard/focus model and the
close-on-change / close-on-lock behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.utub_members import Member_Role
from backend.utils.strings.invite_link_strs import INVITE_LINK_PANEL
from tests.functional.db_utils import (
    get_utub_this_user_created,
    set_member_role_in_utub,
    set_utub_locked_state,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    CO_OWNER_ID,
    OWNER_ID,
    TARGET_ID,
    login_as,
    seed_policy,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
)
from tests.utils_for_test import add_invite_link, seed_hide_list_utub

pytestmark = [pytest.mark.members_ui, pytest.mark.home_ui]

REFRESH_INTERVAL_PASSED_MS = 31_000


def _open_panel(*, page: Page) -> None:
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).click()
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_visible()
    # Bootstrap ignores a hide while the fade runs; focus lands inside the modal
    # only once it has fully shown, so wait for it before acting on the modal.
    expect(page.locator(f"{HPL.INVITE_LINK_MODAL} :focus")).to_have_count(1)


def test_trigger_visible_to_owner(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner of a UTub
    WHEN they view the Members deck
    THEN the invite link trigger is visible
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, members_can_add=True)
    login_as(app=app, page=page, user_id=OWNER_ID)
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_visible()


def test_trigger_visible_to_co_owner(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a co-owner
    WHEN they view the Members deck
    THEN the invite link trigger is visible
    """
    login_as(
        app=provide_app, page=page, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_visible()


def test_trigger_hidden_from_member_even_when_members_can_add(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a plain member in a UTub where members can add members
    WHEN they view the Members deck
    THEN the add button is shown but the invite link trigger is not
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, members_can_add=True)
    login_as(app=app, page=page, user_id=TARGET_ID)
    expect(page.locator(HPL.BUTTON_MEMBER_CREATE)).to_be_visible()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_hidden()


def test_trigger_hidden_when_utub_locked(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a locked UTub
    WHEN the owner views the Members deck
    THEN the invite link trigger is hidden
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    set_utub_locked_state(app, utub_id, True)
    login_as(app=app, page=page, user_id=OWNER_ID)
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_hidden()


def test_empty_state_shows_create_form(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with no invite link
    WHEN the owner opens the panel
    THEN the empty state shows the expiry and uses selects and a create button
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    expect(page.locator(HPL.INVITE_LINK_CREATE_BTN)).to_be_visible()
    expect(page.locator(HPL.INVITE_LINK_EXPIRES_SELECT)).to_have_value("7")
    expect(page.locator(HPL.INVITE_LINK_USES_SELECT)).to_have_value("")
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_have_attribute(
        "aria-haspopup", "dialog"
    )
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_have_attribute("role", "dialog")
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_have_attribute(
        "aria-labelledby", "inviteLinkModalTitle"
    )


def test_live_state_shows_link_read_only(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with a live invite link
    WHEN the owner opens the panel
    THEN the link URL and a copy button are shown
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    add_invite_link(app, utub_id, OWNER_ID, max_uses=10)
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    expect(page.locator(HPL.INVITE_LINK_URL_INPUT)).to_be_visible()
    expect(page.locator(HPL.INVITE_LINK_COPY_BTN)).to_be_visible()


def test_dead_state_expired_shows_reason(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub whose invite link has expired
    WHEN the owner opens the panel
    THEN the expired reason is shown with no URL input
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    add_invite_link(
        app,
        utub_id,
        OWNER_ID,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    expect(page.locator(HPL.INVITE_LINK_MODAL_BODY)).to_contain_text(
        INVITE_LINK_PANEL.DEAD_EXPIRED.split("{date}")[0]
    )
    expect(page.locator(HPL.INVITE_LINK_URL_INPUT)).to_have_count(0)


def test_escape_closes_modal_and_returns_focus_to_trigger(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open invite link modal
    WHEN the user presses Escape
    THEN the modal closes and focus returns to the trigger
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    page.locator(HPL.INVITE_LINK_EXPIRES_SELECT).focus()
    page.keyboard.press("Escape")
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_focused()


def test_close_button_closes_modal_and_returns_focus_to_trigger(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open invite link modal
    WHEN the user clicks its close button
    THEN the modal closes and focus returns to the trigger
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    page.locator(HPL.INVITE_LINK_MODAL_CLOSE).click()
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_focused()


def test_backdrop_click_closes_modal(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open invite link modal
    WHEN the user clicks the backdrop outside the dialog
    THEN the modal closes and the UTub underneath is not switched
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    url_before = page.url
    _open_panel(page=page)
    page.mouse.click(5, 5)
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_focused()
    assert page.url == url_before


def test_modal_traps_focus(page: Page, create_test_utubmembers, provide_app: Flask):
    """
    GIVEN an open invite link modal
    WHEN the user tabs repeatedly
    THEN focus stays inside the modal
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    for _ in range(8):
        page.keyboard.press("Tab")
        assert page.evaluate(
            "() => document.getElementById('inviteLinkModal').contains("
            "document.activeElement)"
        )


def test_trigger_reopens_modal_after_close(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an invite link modal that was opened and closed
    WHEN the trigger is activated again
    THEN the modal reopens with the form
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    page.keyboard.press("Escape")
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_hidden()
    _open_panel(page=page)
    expect(page.locator(HPL.INVITE_LINK_CREATE_BTN)).to_be_visible()


def test_panel_closes_when_utub_gets_locked(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open invite link panel
    WHEN the UTub is locked elsewhere and the viewer returns to the tab
    THEN the panel closes and the trigger is hidden
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    page.clock.install()
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    expect(page.locator(HPL.INVITE_LINK_CREATE_BTN)).to_be_visible()

    set_utub_locked_state(app, utub_id, True)
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    page.evaluate(
        """() => {
            window.dispatchEvent(new Event('blur'));
            window.dispatchEvent(new Event('focus'));
        }"""
    )
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_hidden()
    expect(page.locator(HPL.MEMBER_ROW_ACTION_ANNOUNCEMENT)).to_have_text(
        INVITE_LINK_PANEL.FORCED_CLOSE
    )


def test_opening_panel_closes_open_add_form(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner with the add-member form open
    WHEN they open the invite link modal
    THEN the add form is closed and the modal is shown
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    page.locator(HPL.BUTTON_MEMBER_CREATE).click()
    expect(page.locator(HPL.MEMBER_COMBOBOX_WRAP)).to_be_visible()

    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).click()
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_visible()
    expect(page.locator(HPL.MEMBER_COMBOBOX_WRAP)).to_have_count(0)


def test_opening_panel_closes_open_filter(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner with the member filter open
    WHEN they open the invite link modal
    THEN the filter is closed and the modal is shown
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    page.locator(HPL.BUTTON_MEMBER_NAME_FILTER).click()
    expect(page.locator(HPL.BUTTON_MEMBER_NAME_FILTER_CLOSE)).to_be_visible()

    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).click()
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_visible()
    expect(page.locator(HPL.BUTTON_MEMBER_NAME_FILTER_CLOSE)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_NAME_FILTER)).to_be_visible()


def test_opening_panel_closes_open_gear_popover(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the owner with the Members gear popover open
    WHEN they open the invite link modal from the keyboard
    THEN the invite trigger is unreachable (inert, unfocusable, covered by the
        dialog root) while the dialog is open
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    page.locator(HPL.BUTTON_MEMBER_SETTINGS_GEAR).click()
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()

    trigger = page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)
    reach = page.evaluate(
        """({ triggerSelector, rootSelector }) => {
            const trigger = document.querySelector(triggerSelector);
            const rect = trigger.getBoundingClientRect();
            const hit = document.elementFromPoint(
                rect.left + rect.width / 2, rect.top + rect.height / 2
            );
            const before = document.activeElement;
            trigger.focus();
            return {
                width: rect.width,
                inert: !!trigger.closest('[inert]'),
                focusMoved: document.activeElement !== before,
                focusedTrigger: document.activeElement === trigger,
                hitIsTrigger: hit === trigger || trigger.contains(hit),
                hitInRoot: !!hit && document.querySelector(rootSelector).contains(hit),
            };
        }""",
        {
            "triggerSelector": HPL.BUTTON_MEMBER_INVITE_LINK,
            "rootSelector": HPL.PANEL_SETTINGS_ROOT,
        },
    )
    assert reach["width"] > 0, reach
    assert reach["inert"], reach
    assert not reach["focusMoved"] and not reach["focusedTrigger"], reach
    assert not reach["hitIsTrigger"] and reach["hitInRoot"], reach
    expect(trigger).not_to_be_focused()
    # Chromium fires a DOM click() on an inert trigger, so this proves the silent
    # forced close on INVITE_PANEL_OPENED end to end (the vitest describe covers
    # the same contract at unit level).
    page.evaluate(
        "(sel) => document.querySelector(sel).click()",
        HPL.BUTTON_MEMBER_INVITE_LINK,
    )
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_visible()
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_hidden()
    expect(page.locator(HPL.MAIN_PANEL)).not_to_have_attribute("inert", "")


def test_hide_member_list_keeps_trigger_for_managers_and_hides_it_from_members(
    page: Page, runner, provide_app: Flask
):
    """
    GIVEN a UTub with the member list hidden from plain members
    WHEN the owner and a co-owner open it
    THEN each still sees the trigger and can open the panel
    AND WHEN a plain member opens it THEN they see no trigger and no panel
    """
    app = provide_app
    seed = seed_hide_list_utub(app, True)

    for manager_id in (seed.owner_id, seed.co_owner_id):
        login_user_and_select_utub_by_utubid(
            app=app, page=page, user_id=manager_id, utub_id=seed.utub_id
        )
        _open_panel(page=page)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=seed.member_a_id, utub_id=seed.utub_id
    )
    # Positive readiness wait: only owner, co-owner and self render under hide-list,
    # so the deck has been built before the hidden assertions can run.
    expect(page.locator(f"{HPL.MEMBER_DECK} {HPL.BADGES_MEMBERS}")).to_have_count(3)
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_hidden()
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_hidden()


def test_trigger_hidden_from_co_owner_when_only_the_owner_can_create(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub whose invite links are owner-only
    WHEN a co-owner views the Members deck
    THEN the invite link trigger is hidden
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    seed_policy(app=app, utub_id=utub_id, invite_link_creators="owner_only")
    login_as(app=app, page=page, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR)
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_hidden()


def test_owner_sees_creator_not_allowed_copy_for_a_link_the_setting_killed(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a live co-owner link that was never revoked and an owner-only setting
    WHEN the owner opens the panel
    THEN the dead state gives the creator-not-allowed reason and no URL input
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    set_member_role_in_utub(app, CO_OWNER_ID, utub_id, Member_Role.CO_CREATOR)
    seed_policy(app=app, utub_id=utub_id, invite_link_creators="owner_only")
    add_invite_link(app, utub_id, CO_OWNER_ID)
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    expect(page.locator(HPL.INVITE_LINK_MODAL_BODY)).to_contain_text(
        INVITE_LINK_PANEL.DEAD_CREATOR_NOT_ALLOWED
    )
    expect(page.locator(HPL.INVITE_LINK_URL_INPUT)).to_have_count(0)


def test_co_owner_preview_switch_is_disabled_with_the_owner_only_hint(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a live link while co-owners cannot turn on previews (the default)
    WHEN a co-owner opens the panel
    THEN the preview switch is aria-disabled and the owner-only hint is shown
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    add_invite_link(app, utub_id, OWNER_ID)
    login_as(app=app, page=page, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR)
    _open_panel(page=page)
    expect(page.locator(HPL.INVITE_LINK_PREVIEW_SWITCH)).to_have_attribute(
        "aria-disabled", "true"
    )
    expect(page.locator(HPL.INVITE_LINK_PREVIEW_OWNER_HINT)).to_have_text(
        INVITE_LINK_PANEL.PREVIEW_OWNER_ONLY_HINT
    )


def test_co_owner_create_after_owner_tightens_closes_panel_with_the_refusal(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a co-owner with the empty create form open
    WHEN the owner switches creation to owner-only and the co-owner presses Create
    THEN the panel closes, the errorCode 7 message is announced and the trigger is
        hidden once the UTub refreshes
    """
    app = provide_app
    utub_id = login_as(
        app=app, page=page, user_id=CO_OWNER_ID, role=Member_Role.CO_CREATOR
    )
    _open_panel(page=page)
    expect(page.locator(HPL.INVITE_LINK_CREATE_BTN)).to_be_visible()

    seed_policy(app=app, utub_id=utub_id, invite_link_creators="owner_only")
    page.locator(HPL.INVITE_LINK_CREATE_BTN).click()

    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_hidden()
    expect(page.locator(HPL.MEMBER_ROW_ACTION_ANNOUNCEMENT)).to_have_text(
        INVITE_LINK_PANEL.CREATE_NOT_ALLOWED
    )
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_hidden()
