from typing import Tuple

from flask import Flask
from playwright.sync_api import Locator, Page

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as ML
from tests.functional.playwright_login_utils import (
    login_user_select_utub_by_name_and_url_by_string,
)
from tests.functional.playwright_utils import (
    get_selected_url,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_visible_css_selector,
)


def login_select_utub_select_url_click_delete_get_modal_url(
    *,
    page: Page,
    app: Flask,
    user_id: int,
    utub_name: str,
    url_string: str,
) -> Tuple[Locator, Locator]:
    login_user_select_utub_by_name_and_url_by_string(
        app=app, page=page, user_id=user_id, utub_name=utub_name, url_string=url_string
    )
    url_row = get_selected_url(page=page)
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}"
    )
    wait_until_visible_css_selector(page=page, css_selector=ML.ELEMENT_MODAL)
    modal = wait_then_get_element(page=page, css_selector=HPL.BODY_MODAL)

    return modal, url_row
