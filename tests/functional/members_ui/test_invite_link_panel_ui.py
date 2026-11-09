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
from tests.utils_for_test import add_invite_link

pytestmark = [pytest.mark.members_ui, pytest.mark.home_ui]

REFRESH_INTERVAL_PASSED_MS = 31_000


def _open_panel(*, page: Page) -> None:
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).click()
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_visible()


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
        "aria-expanded", "true"
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
    expect(page.locator(HPL.MEMBER_INVITE_PANEL_BODY)).to_contain_text(
        INVITE_LINK_PANEL.DEAD_EXPIRED.split("{date}")[0]
    )
    expect(page.locator(HPL.INVITE_LINK_URL_INPUT)).to_have_count(0)


def test_escape_closes_panel_and_returns_focus_to_trigger(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open invite link panel
    WHEN the user presses Escape
    THEN the panel closes and focus returns to the trigger
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    page.locator(HPL.INVITE_LINK_EXPIRES_SELECT).focus()
    page.keyboard.press("Escape")
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_focused()


def test_trigger_toggles_panel_closed(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open invite link panel
    WHEN the trigger is clicked again
    THEN the panel closes
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).click()
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_hidden()


def test_panel_closes_when_utub_changes(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open invite link panel
    WHEN the user selects a different UTub
    THEN the panel is closed
    """
    app = provide_app
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    other = page.locator(f"{HPL.SELECTORS_UTUB}:not(.active)")
    expect(other.first).to_be_visible()
    other.first.click()
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_have_attribute(
        "aria-expanded", "false"
    )


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
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_hidden()
    expect(page.locator("#MemberRowActionAnnouncement")).to_have_text(
        INVITE_LINK_PANEL.FORCED_CLOSE
    )
