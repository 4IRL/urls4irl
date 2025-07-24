from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from src.utils.strings.reset_password_strs import EMAIL_SENT_MESSAGE
from src.utils.strings.splash_form_strs import FORGOT_YOUR_PASSWORD
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.selenium_utils import (
    wait_then_get_element,
)


def assert_forgot_password_modal_open(browser: WebDriver):
    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    assert modal_element.is_displayed()

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == FORGOT_YOUR_PASSWORD


def assert_forgot_password_submission(browser: WebDriver):
    modal_alert = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT)
    assert modal_alert is not None

    assert modal_alert.text == EMAIL_SENT_MESSAGE

    submit_btn = wait_then_get_element(browser, SPL.BUTTON_SUBMIT)
    assert submit_btn is not None

    assert submit_btn.get_attribute("disabled")
