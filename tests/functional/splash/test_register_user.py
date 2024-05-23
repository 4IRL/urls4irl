import pytest

from selenium.webdriver.common.by import By

# from webdriver_manager.chrome import ChromeDriverManager

import tests.functional.constants as const
from tests.functional.utils import (
    click_and_wait,
    find_element_css_selector,
    send_keys_to_input_field,
)


# Registers a new user
@pytest.fixture(scope="package")
def test_register_new_user(provide_browser):
    browser = provide_browser

    # Identify and load register modal
    click_and_wait(browser, ".to-register", 5)

    # Input register user details
    send_keys_to_input_field(browser, "#username", const.USERNAME_REGISTER)

    send_keys_to_input_field(browser, "#email", const.EMAIL_REGISTER)

    send_keys_to_input_field(browser, "#confirmEmail", const.EMAIL_REGISTER)

    send_keys_to_input_field(browser, "#password", const.PASSWORD_REGISTER)

    send_keys_to_input_field(browser, "#confirmPassword", const.PASSWORD_REGISTER)

    # Register
    click_and_wait(browser, "#submit")

    modal_title = find_element_css_selector(browser, ".validate-email-title")
    register_success_text = "Validate Your Email!"

    assert modal_title.text == register_success_text


# Attempts to register a new user. Ensures alert is shown to user
def test_register_existing_user(provide_browser, test_register_new_user):
    browser = provide_browser

    alert_title = browser.find_element(By.ID, "SplashModalAlertBanner")
    alert_title_text = "An account already exists with that information but the email has not been validated."

    assert alert_title.text == alert_title_text
