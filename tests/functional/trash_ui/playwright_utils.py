from flask import Flask
from playwright.sync_api import Page, expect

from tests.functional.locators import TrashPanelLocators as TPL
from tests.functional.playwright_utils import login_user_to_home_page


def wait_for_trash_list_loaded(*, page: Page) -> None:
    """Block until the Trash list response has been rendered. The retention notice
    is only revealed by `renderTrashList()`, so it marks "rows are in the DOM"."""
    expect(page.locator(TPL.PANEL)).to_be_visible()
    expect(page.locator("#TrashRetentionNotice")).to_be_visible()


def open_trash(*, page: Page) -> None:
    """Click the deck's Trash entry and wait for the panel and its list."""
    page.locator(TPL.SELECTOR).click()
    wait_for_trash_list_loaded(page=page)


def login_user_and_open_trash(*, app: Flask, page: Page, user_id: int) -> None:
    """Log `user_id` in via session cookie, land on /home, then open Trash."""
    login_user_to_home_page(app=app, page=page, user_id=user_id)
    open_trash(page=page)


def open_utubs_tab(*, page: Page) -> None:
    """Switch the Trash panel to its UTubs tab."""
    page.locator(TPL.TAB_UTUBS).click()
    expect(page.locator(TPL.TAB_UTUBS)).to_have_attribute("aria-selected", "true")
    expect(page.locator(TPL.PANEL_UTUBS)).to_be_visible()
