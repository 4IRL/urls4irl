"""Real-browser acceptance for the invite link panel's lifecycle actions:
Create, New link and Revoke (inline confirms, stale-state resyncs, lock)."""

from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.utub_invite_links import Utub_Invite_Links
from backend.utils.strings.invite_link_strs import INVITE_LINK_PANEL
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    OWNER_ID,
    expire_invite_link_in_db,
    login_as,
    revoke_invite_link_in_db,
)
from tests.utils_for_test import add_invite_link, lock_utub

pytestmark = [pytest.mark.members_ui, pytest.mark.home_ui]

ANNOUNCEMENT = "#MemberRowActionAnnouncement"


def _open_panel(*, page: Page) -> None:
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).click()
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_visible()


def test_create_shows_live_link_and_copy(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with no invite link and the panel open
    WHEN the owner presses Create link
    THEN the live link and Copy button are shown, Copy has focus and it is announced
    """
    login_as(app=provide_app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)

    page.locator(HPL.INVITE_LINK_CREATE_BTN).click()

    expect(page.locator(HPL.INVITE_LINK_URL_INPUT)).to_have_value(
        re.compile(r"/invite/.+")
    )
    expect(page.locator(HPL.INVITE_LINK_COPY_BTN)).to_be_focused()
    expect(page.locator(ANNOUNCEMENT)).to_have_text(INVITE_LINK_PANEL.CREATED)


def test_new_link_replaces_token_and_kills_the_old_invite_page(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with a live invite link
    WHEN the owner confirms New link
    THEN the token changes, Copy has focus and the old invite page is dead
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    add_invite_link(app, utub_id, OWNER_ID, max_uses=10)
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    old_url = page.locator(HPL.INVITE_LINK_URL_INPUT).input_value()

    page.locator(HPL.INVITE_LINK_NEW_BTN).click()
    expect(page.locator(HPL.INVITE_LINK_CONFIRM_CANCEL_BTN)).to_be_focused()
    page.locator(HPL.INVITE_LINK_CONFIRM_ACTION_BTN).click()

    expect(page.locator(HPL.INVITE_LINK_URL_INPUT)).not_to_have_value(old_url)
    expect(page.locator(HPL.INVITE_LINK_COPY_BTN)).to_be_focused()
    expect(page.locator(ANNOUNCEMENT)).to_have_text(INVITE_LINK_PANEL.REPLACED)

    # A member's invite visit always redirects home (even for a dead link), so
    # the old link's death is asserted on its row: revoked, never live again.
    new_url = page.locator(HPL.INVITE_LINK_URL_INPUT).input_value()
    with app.app_context():
        old_row = Utub_Invite_Links.query.filter_by(
            token=old_url.rsplit("/", 1)[1]
        ).one()
        new_row = Utub_Invite_Links.query.filter_by(
            token=new_url.rsplit("/", 1)[1]
        ).one()
        assert old_row.revoked_at is not None
        assert new_row.revoked_at is None


def test_revoke_shows_empty_state_and_focuses_create(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub with a live invite link
    WHEN the owner confirms Revoke
    THEN the empty state is shown with focus on Create link
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    add_invite_link(app, utub_id, OWNER_ID)
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)

    page.locator(HPL.INVITE_LINK_REVOKE_BTN).click()
    expect(page.locator(HPL.INVITE_LINK_CONFIRM_GROUP)).to_be_visible()
    page.locator(HPL.INVITE_LINK_CONFIRM_ACTION_BTN).click()

    expect(page.locator(HPL.INVITE_LINK_URL_INPUT)).to_have_count(0)
    expect(page.locator(HPL.INVITE_LINK_CREATE_BTN)).to_be_focused()
    expect(page.locator(ANNOUNCEMENT)).to_have_text(INVITE_LINK_PANEL.REVOKED)


def test_escape_cancels_confirm_then_closes_panel(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open Revoke confirm
    WHEN Escape is pressed twice
    THEN the first restores the footer with focus on Revoke, the second closes the panel
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    add_invite_link(app, utub_id, OWNER_ID)
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)

    page.locator(HPL.INVITE_LINK_REVOKE_BTN).click()
    page.keyboard.press("Escape")
    expect(page.locator(HPL.INVITE_LINK_CONFIRM_GROUP)).to_have_count(0)
    expect(page.locator(HPL.INVITE_LINK_REVOKE_BTN)).to_be_focused()

    page.keyboard.press("Escape")
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_hidden()


def test_revoke_after_db_revoke_resyncs_to_empty(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open panel on a live link that was revoked in the DB meanwhile
    WHEN the owner confirms Revoke
    THEN the 404 (code 1) resyncs the panel to the empty state and announces it
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    link_id = add_invite_link(app, utub_id, OWNER_ID)
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    revoke_invite_link_in_db(app=app, invite_link_id=link_id)

    page.locator(HPL.INVITE_LINK_REVOKE_BTN).click()
    page.locator(HPL.INVITE_LINK_CONFIRM_ACTION_BTN).click()

    expect(page.locator(HPL.INVITE_LINK_CREATE_BTN)).to_be_visible()
    expect(page.locator(HPL.INVITE_LINK_URL_INPUT)).to_have_count(0)
    expect(page.locator(ANNOUNCEMENT)).to_have_text(INVITE_LINK_PANEL.RESYNC_REVOKED)


def test_new_link_replaces_a_link_that_expired_meanwhile(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open panel on a live link that expired in the DB meanwhile
    WHEN the owner confirms New link
    THEN the panel shows no generic error (replace accepts a dead link)
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    link_id = add_invite_link(app, utub_id, OWNER_ID)
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    old_url = page.locator(HPL.INVITE_LINK_URL_INPUT).input_value()
    expire_invite_link_in_db(app=app, invite_link_id=link_id)

    page.locator(HPL.INVITE_LINK_NEW_BTN).click()
    page.locator(HPL.INVITE_LINK_CONFIRM_ACTION_BTN).click()

    expect(page.locator(HPL.INVITE_LINK_URL_INPUT)).not_to_have_value(old_url)
    expect(page.locator(HPL.INVITE_LINK_COPY_BTN)).to_be_focused()
    expect(page.locator(ANNOUNCEMENT)).to_have_text(INVITE_LINK_PANEL.REPLACED)
    expect(page.locator(HPL.INVITE_LINK_INLINE_ERROR)).to_have_count(0)


def test_create_after_db_insert_resyncs_to_live(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open empty panel while a live link is inserted in the DB
    WHEN the owner presses Create link
    THEN the 409 (code 4) resyncs the panel to the live link and announces it
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    add_invite_link(app, utub_id, OWNER_ID)

    page.locator(HPL.INVITE_LINK_CREATE_BTN).click()

    expect(page.locator(HPL.INVITE_LINK_URL_INPUT)).to_be_visible()
    expect(page.locator(ANNOUNCEMENT)).to_have_text(
        INVITE_LINK_PANEL.RESYNC_LIVE_EXISTS
    )


def test_revoke_in_locked_utub_closes_panel_and_hides_trigger(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open panel on a live link
    WHEN the UTub is locked in the DB and the owner confirms Revoke
    THEN the panel closes, the lock is announced and the trigger disappears
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    add_invite_link(app, utub_id, OWNER_ID)
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    lock_utub(app, utub_id)

    page.locator(HPL.INVITE_LINK_REVOKE_BTN).click()
    page.locator(HPL.INVITE_LINK_CONFIRM_ACTION_BTN).click()

    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_INVITE_LINK)).to_be_hidden()
