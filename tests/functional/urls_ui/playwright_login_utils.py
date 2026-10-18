from flask import Flask
from playwright.sync_api import Locator, Page

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_select_utub_by_name_and_url_by_string,
)
from tests.functional.playwright_utils import (
    get_selected_url,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_then_click_element,
    wait_until_visible_css_selector,
)


def click_delete_on_selected_url(*, page: Page) -> Locator:
    """Click the selected URL's delete button (no confirmation). Returns the
    URL's row locator without waiting for the outcome."""
    url_row = get_selected_url(page=page)
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}"
    )
    return url_row


def click_delete_on_selected_url_and_wait_for_toast(*, page: Page) -> Locator:
    """Click the selected URL's delete button (no confirmation) and wait for the
    undo toast. Returns the deleted URL's row locator."""
    url_row = click_delete_on_selected_url(page=page)
    wait_until_visible_css_selector(page=page, css_selector=HPL.URL_OUTCOME_BANNER)

    return url_row


def login_select_utub_select_url_click_delete(
    *,
    page: Page,
    app: Flask,
    user_id: int,
    utub_name: str,
    url_string: str,
) -> Locator:
    login_user_select_utub_by_name_and_url_by_string(
        app=app, page=page, user_id=user_id, utub_name=utub_name, url_string=url_string
    )
    return click_delete_on_selected_url_and_wait_for_toast(page=page)
