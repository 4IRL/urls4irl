"""Real-browser acceptance for the invite link panel's settings saves (Expires
and Uses), the code 6 race, the code 5 dead-link resync and Copy."""

from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.utils.strings.invite_link_strs import INVITE_LINK_PANEL
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import (
    OWNER_ID,
    expire_invite_link_in_db,
    get_invite_link_row,
    login_as,
    set_invite_link_use_count_in_db,
)
from tests.functional.urls_ui.playwright_utils import ClipboardMockHelper
from tests.utils_for_test import add_invite_link

pytestmark = [pytest.mark.members_ui, pytest.mark.home_ui]

ANNOUNCEMENT = "#MemberRowActionAnnouncement"
INVITE_URL_PATTERN = re.compile(r"^https?://[^/]+/invite/[A-Za-z0-9_-]{22}$")


def _open_panel(*, page: Page) -> None:
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).click()
    expect(page.locator(HPL.MEMBER_INVITE_PANEL)).to_be_visible()


def _seed_live_link_and_open(*, app: Flask, page: Page, max_uses: int | None) -> int:
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    link_id = add_invite_link(app, utub_id, OWNER_ID, max_uses=max_uses)
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    return link_id


def test_expires_save_persists_and_keeps_focus(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a live link (default 7 day expiry) and the panel open
    WHEN the owner picks "30 days from now" in Expires
    THEN the expiry is saved in the DB, announced, and the select keeps focus
    """
    app = provide_app
    link_id = _seed_live_link_and_open(app=app, page=page, max_uses=None)

    expires = page.locator(HPL.INVITE_LINK_EXPIRES_SELECT)
    expires.focus()
    expires.select_option(value="30")

    expect(page.locator(ANNOUNCEMENT)).to_contain_text("Link now expires")
    expect(expires).to_be_focused()
    assert get_invite_link_row(app=app, invite_link_id=link_id)[1] == 30


def test_uses_save_persists_including_unlimited(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a live link limited to 10 uses
    WHEN the owner picks 25 uses and then Unlimited
    THEN each value is saved in the DB and announced
    """
    app = provide_app
    link_id = _seed_live_link_and_open(app=app, page=page, max_uses=10)
    uses = page.locator(HPL.INVITE_LINK_USES_SELECT)

    uses.select_option(value="25")
    expect(page.locator(ANNOUNCEMENT)).to_have_text(
        INVITE_LINK_PANEL.USES_SET.format(label="25 uses")
    )
    assert get_invite_link_row(app=app, invite_link_id=link_id)[0] == 25

    uses.select_option(value="")
    expect(page.locator(ANNOUNCEMENT)).to_have_text(
        INVITE_LINK_PANEL.USES_SET.format(label=INVITE_LINK_PANEL.USES_UNLIMITED)
    )
    assert get_invite_link_row(app=app, invite_link_id=link_id)[0] is None


def test_code_6_race_restores_value_and_names_the_minimum(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open panel whose link gained joins in the DB meanwhile
    WHEN the owner picks a limit below the joined count
    THEN the old value comes back, the select is flagged invalid and the message
        names the joined count
    """
    app = provide_app
    link_id = _seed_live_link_and_open(app=app, page=page, max_uses=10)
    set_invite_link_use_count_in_db(app=app, invite_link_id=link_id, use_count=7)

    uses = page.locator(HPL.INVITE_LINK_USES_SELECT)
    uses.select_option(value="5")

    expect(page.locator(HPL.INVITE_LINK_INLINE_ERROR)).to_have_text(
        INVITE_LINK_PANEL.USES_BELOW_JOINED.format(count=7)
    )
    expect(uses).to_have_value("10")
    expect(uses).to_have_attribute("aria-invalid", "true")
    expect(uses).to_have_attribute("aria-describedby", "inviteLinkInlineError")
    assert get_invite_link_row(app=app, invite_link_id=link_id)[0] == 10


def test_dead_link_save_resyncs_to_dead_state(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an open panel on a link that expired in the DB meanwhile
    WHEN the owner changes a select
    THEN the code 5 409 resyncs the panel to the dead state with Create link focused
    """
    app = provide_app
    link_id = _seed_live_link_and_open(app=app, page=page, max_uses=None)
    expire_invite_link_in_db(app=app, invite_link_id=link_id)

    page.locator(HPL.INVITE_LINK_USES_SELECT).select_option(value="5")

    expect(page.locator(HPL.INVITE_LINK_CREATE_BTN)).to_be_focused()
    expect(page.locator(HPL.INVITE_LINK_URL_INPUT)).to_have_count(0)
    expect(page.locator(ANNOUNCEMENT)).to_contain_text(
        INVITE_LINK_PANEL.RESYNC_DEAD_UPDATE
    )


def test_copy_writes_the_invite_url(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
    clipboard_mock: ClipboardMockHelper,
):
    """
    GIVEN a live link and a working clipboard
    WHEN the owner presses Copy
    THEN the clipboard holds `<origin>/invite/<token>` and Copy reads "Copied"
    """
    app = provide_app
    _seed_live_link_and_open(app=app, page=page, max_uses=None)
    clipboard_mock.setup_clipboard_mock()

    page.locator(HPL.INVITE_LINK_COPY_BTN).click()
    clipboard_mock.wait_for_write_count(count=1)

    assert INVITE_URL_PATTERN.match(clipboard_mock.get_clipboard_content())
    expect(page.locator(HPL.INVITE_LINK_COPY_BTN)).to_have_text(
        INVITE_LINK_PANEL.COPIED
    )
    expect(page.locator(ANNOUNCEMENT)).to_have_text(INVITE_LINK_PANEL.COPY_SUCCESS)


def test_copy_fallback_selects_the_input(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
    clipboard_mock: ClipboardMockHelper,
):
    """
    GIVEN a clipboard that rejects writes
    WHEN the owner presses Copy
    THEN the input is focused with its whole text selected and the hint is shown
    """
    app = provide_app
    _seed_live_link_and_open(app=app, page=page, max_uses=None)
    clipboard_mock.setup_clipboard_failure()

    page.locator(HPL.INVITE_LINK_COPY_BTN).click()

    url_input = page.locator(HPL.INVITE_LINK_URL_INPUT)
    expect(url_input).to_be_focused()
    expect(page.locator("#inviteLinkCopyHint")).to_have_text(
        INVITE_LINK_PANEL.COPY_FALLBACK
    )
    selected = page.evaluate(
        "() => { const input = document.querySelector('#inviteLinkUrlInput');"
        " return input.value.substring(input.selectionStart, input.selectionEnd); }"
    )
    assert selected == url_input.input_value()
