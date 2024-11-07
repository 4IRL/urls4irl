# Standard library
import time

# External libraries
import pytest
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.locators import ModalLocators as ML
from tests.functional.splash_ui.utils_for_test_splash_ui import (
    register_user,
    register_user_unconfirmed_email,
    register_user_unconfirmed_password,
)
from tests.functional.utils_for_test import (
    dismiss_modal_with_click_out,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
)

pytestmark = pytest.mark.splash_ui


def test_register_modal_center_btn(browser: WebDriver):
    """
    Tests a user's ability to open the Register modal using the center button.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the center register button
    THEN ensure the modal opens
    """
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)
    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)

    assert modal_element.is_displayed()

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Register"


def test_register_modal_RHS_btn(browser: WebDriver):
    """
    Tests a user's ability to open the Register modal using the RHS corner button

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the RHS register button
    THEN ensure the modal opens
    """

    # Find and click login button to open modal
    navbar = wait_then_get_element(browser, SPL.SPLASH_NAVBAR)

    register_btn = navbar.find_element(By.CSS_SELECTOR, SPL.BUTTON_REGISTER)
    register_btn.click()

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)

    assert modal_element.is_displayed()

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Register"


def test_login_to_register_modal_btn(browser: WebDriver):
    """
    Tests a user's ability to change view from the Login modal to the Register modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens Login modal and wants to change to Register
    THEN ensure the modal view changes
    """
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)
    wait_then_click_element(browser, SPL.BUTTON_REGISTER_FROM_LOGIN)

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Register"


def test_dismiss_register_modal_btn(browser: WebDriver):
    """
    Tests a user's ability to close the splash page register modal by clicking the upper RHS 'x' button

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the register, then clicks the 'x'
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)

    wait_then_click_element(browser, ML.BUTTON_MODAL_DISMISS)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_register_modal_click(browser: WebDriver):
    """
    Tests a user's ability to close the splash page register modal by clicking outside of the modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the register, then clicks anywhere outside of the modal
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)

    dismiss_modal_with_click_out(browser)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_register_modal_x(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by clicking the 'x' button in the upper right hand corner

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks the 'x' of the modal
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)

    wait_then_click_element(browser, SPL.BUTTON_X_MODAL_DISMISS)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


# @pytest.mark.skip(reason="Testing another in isolation")
def test_register_new_user(browser: WebDriver):
    """
    Tests a user's ability to register as a new user.

    GIVEN a fresh load of the U4I Splash page
    WHEN initiates registration modal and inputs desired login information
    THEN U4I responds with a success modal prompting user to 'Validate Your Email!'
    """

    register_user(
        browser, UTS.TEST_USERNAME_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )

    # Await response
    time.sleep(3)

    modal_title = wait_then_get_element(browser, SPL.HEADER_VALIDATE_EMAIL)

    assert modal_title.text == UTS.HEADER_MODAL_EMAIL_VALIDATION


@pytest.mark.skip(reason="Not happy path. PASSES")
def test_register_existing_username(browser: WebDriver, add_test_users):
    """
    Tests the site error response to a user's attempt to register with a username that is already registered in the database.

    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing user again
    THEN U4I responds with a failure modal and reminds user to 'Validate Your Email!'
    """

    # register_user(browser, username, email, password)
    register_user(
        browser,
        UTS.TEST_USERNAME_1,
        UTS.TEST_PASSWORD_UNLISTED,
        UTS.TEST_PASSWORD_UNLISTED,
    )

    # Extract error message text
    invalid_feedback_username_message = wait_then_get_element(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK
    )

    assert invalid_feedback_username_message.text == UTS.MESSAGE_USERNAME_TAKEN


@pytest.mark.skip(reason="Not happy path. FAILS")
def test_register_existing_email(browser: WebDriver, add_test_users):
    """
    Tests the site error response to a user's attempt to register with an email that is already registered in the database.

    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing user again
    THEN U4I responds with a failure modal and reminds user to 'Validate Your Email!'
    """

    # register_user(browser, username, email, password)
    register_user(
        browser, UTS.TEST_USER_UNLISTED, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )

    # Extract error message text
    invalid_feedback_email_message = wait_then_get_element(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK
    )

    assert invalid_feedback_email_message.text == UTS.MESSAGE_EMAIL_TAKEN


@pytest.mark.skip(reason="Not happy path. FAILS")
def test_register_existing_username_and_email(browser: WebDriver, add_test_users):
    """
    Tests the site error response to a user's attempt to register with a username and email that is already registered in the database.

    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing user again
    THEN U4I responds with a failure modal and reminds user to 'Validate Your Email!'
    """

    # register_user(browser, username, email, password)
    register_user(
        browser, UTS.TEST_USERNAME_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )

    # Extract error message text
    invalid_feedback_messages = wait_then_get_elements(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK
    )
    invalid_feedback_username_message = invalid_feedback_messages[0]
    invalid_feedback_email_message = invalid_feedback_messages[1]

    assert invalid_feedback_username_message.text == UTS.MESSAGE_USERNAME_TAKEN
    assert invalid_feedback_email_message.text == UTS.MESSAGE_EMAIL_TAKEN


@pytest.mark.skip(reason="Not on happy path.")
def test_register_failed_email_confirmation(browser: WebDriver):
    """
    Tests the site error response to a user submitting a register form with mismatched email inputs.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with mismatched email addresses
    THEN U4I responds with a failure modal and prompts user to double check inputs
    """

    register_user_unconfirmed_email(
        browser, UTS.TEST_USERNAME_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )


@pytest.mark.skip(reason="Not on happy path.")
def test_register_failed_password_confirmation(browser: WebDriver):
    """
    Tests the site error response to a user submitting a register form with mismatched password inputs.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with mismatched passwords
    THEN U4I responds with a failure modal and prompts user to double check inputs
    """

    register_user_unconfirmed_password(
        browser, UTS.TEST_USERNAME_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )
