from typing import Tuple

from flask import Flask
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as ML
from tests.functional.login_utils import (
    login_user_select_utub_by_name_and_url_by_string,
)
from tests.functional.selenium_utils import (
    get_selected_url,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_visible_css_selector,
)


def login_select_utub_select_url_click_delete_get_modal_url(
    browser: WebDriver,
    app: Flask,
    user_id: int,
    utub_name: str,
    url_string: str,
    timeout: int = 5,
) -> Tuple[WebElement, WebElement]:
    login_user_select_utub_by_name_and_url_by_string(
        app, browser, user_id, utub_name, url_string
    )
    url_row = get_selected_url(browser)
    wait_for_animation_to_end_check_top_lhs_corner(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}", time=timeout
    )
    wait_until_visible_css_selector(browser, ML.ELEMENT_MODAL, timeout)
    modal = wait_then_get_element(browser, HPL.BODY_MODAL)
    assert modal is not None

    return modal, url_row
