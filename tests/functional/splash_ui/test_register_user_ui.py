# Standard library

# External libraries
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By

# from webdriver_manager.chrome import ChromeDriverManager

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.utils_for_test import wait_then_get_element, clear_then_send_keys


@pytest.fixture
def populate_register_form(browser):
    """
    Args:
        Webdriver open to U4I Splash Page

    Returns:
        Webdriver handoff to register tests
    """

    # Identify and load register modal
    wait_then_get_element(browser, ".to-register", True, 5)

    # Input register user details
    clear_then_send_keys(browser, "#username", UI_TEST_STRINGS.TEST_USER_1)

    clear_then_send_keys(browser, "#email", UI_TEST_STRINGS.TEST_PASSWORD_1)

    clear_then_send_keys(browser, "#confirmEmail", UI_TEST_STRINGS.TEST_PASSWORD_1)

    clear_then_send_keys(browser, "#password", UI_TEST_STRINGS.TEST_PASSWORD_1)

    clear_then_send_keys(browser, "#confirmPassword", UI_TEST_STRINGS.TEST_PASSWORD_1)

    # Attempt to register
    wait_then_get_element(browser, "#submit", True, 5)

    return browser


def test_register_new_user(populate_register_form):
    """
    GIVEN a fresh load of the U4I Splash page
    WHEN initiates registration modal and inputs desired login information
    THEN U4I responds with a success modal prompting user to 'Validate Your Email!'
    """
    browser = populate_register_form

    modal_title = wait_then_get_element(browser, ".validate-email-title")
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
