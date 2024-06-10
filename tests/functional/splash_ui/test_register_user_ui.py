# Standard library

# External libraries
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By

# from webdriver_manager.chrome import ChromeDriverManager

import tests.functional.constants as const
from tests.functional.utils import (
    click_and_wait,
    find_element_by_css_selector,
    send_keys_to_input_field,
)


@pytest.fixture
def populate_register_form(browser):
    """
    Args:
        Webdriver open to U4I Splash Page

    Returns:
        Webdriver handoff to register tests
    """

    # Identify and load register modal
    click_and_wait(browser, ".to-register", 5)

    # Input register user details
    send_keys_to_input_field(browser, "#username", const.USERNAME_REGISTER)

    send_keys_to_input_field(browser, "#email", const.EMAIL_REGISTER)

    send_keys_to_input_field(browser, "#confirmEmail", const.EMAIL_REGISTER)

    send_keys_to_input_field(browser, "#password", const.PASSWORD_REGISTER)

    send_keys_to_input_field(browser, "#confirmPassword", const.PASSWORD_REGISTER)

    # Attempt to register
    click_and_wait(browser, "#submit")

    return browser


def test_register_new_user(populate_register_form):
    """
    GIVEN a fresh load of the U4I Splash page
    WHEN initiates registration modal and inputs desired login information
    THEN U4I responds with a success modal prompting user to 'Validate Your Email!'
    """
    browser = populate_register_form

    modal_title = find_element_by_css_selector(browser, ".validate-email-title")
    register_success_text = "Validate Your Email!"

    assert modal_title.text == register_success_text


@pytest.mark.skip(
    reason="This test needs a db proxy set up to test against an existing user"
)
def test_register_existing_user(populate_register_form):
    """
    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing user again
    THEN U4I responds with a failure modal and reminds user to 'Validate Your Email!'
    """

    browser = populate_register_form

    alert_title = browser.find_element(
        By.XPATH, "//div[@id='SplashModalAlertBanner']/div[1]"
    )
    webdriver.ActionChains(browser).move_to_element(alert_title).click(
        alert_title
    ).perform()
    alert_title_text = "An account already exists with that information but the email has not been validated."

    assert alert_title.text == alert_title_text
