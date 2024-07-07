# Standard library
import time

# External libraries
import pytest

# from webdriver_manager.chrome import ChromeDriverManager

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.splash_ui.utils_for_test_splash_ui import (
    register_user,
    register_user_unconfirmed_email,
    register_user_unconfirmed_password,
)
from tests.functional.utils_for_test import (
    wait_then_get_element,
    wait_then_get_elements,
)


# @pytest.mark.skip(reason="Testing another in isolation")
def test_register_new_user(browser):
    """
    GIVEN a fresh load of the U4I Splash page
    WHEN initiates registration modal and inputs desired login information
    THEN U4I responds with a success modal prompting user to 'Validate Your Email!'
    """

    register_user(browser, UTS.TEST_USER_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1)

    # Await response
    time.sleep(3)

    modal_title = wait_then_get_element(browser, SPL.HEADER_VALIDATE_EMAIL)

    assert modal_title.text == UTS.HEADER_MODAL_EMAIL_VALIDATION


@pytest.mark.skip(reason="Not happy path. PASSES")
def test_register_existing_username(browser, add_test_users):
    """
    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing user again
    THEN U4I responds with a failure modal and reminds user to 'Validate Your Email!'
    """

    # register_user(browser, username, email, password)
    register_user(
        browser, UTS.TEST_USER_1, UTS.TEST_PASSWORD_UNLISTED, UTS.TEST_PASSWORD_UNLISTED
    )

    # Extract error message text
    invalid_feedback_username_message = wait_then_get_element(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK
    )

    assert invalid_feedback_username_message.text == UTS.MESSAGE_USERNAME_TAKEN


@pytest.mark.skip(reason="Not happy path. FAILS")
def test_register_existing_email(browser, add_test_users):
    """
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
def test_register_existing_username_and_email(browser, add_test_users):
    """
    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing user again
    THEN U4I responds with a failure modal and reminds user to 'Validate Your Email!'
    """

    # register_user(browser, username, email, password)
    register_user(browser, UTS.TEST_USER_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1)

    # Extract error message text
    invalid_feedback_messages = wait_then_get_elements(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK
    )
    invalid_feedback_username_message = invalid_feedback_messages[0]
    invalid_feedback_email_message = invalid_feedback_messages[1]

    assert invalid_feedback_username_message.text == UTS.MESSAGE_USERNAME_TAKEN
    assert invalid_feedback_email_message.text == UTS.MESSAGE_EMAIL_TAKEN


@pytest.mark.skip(reason="Not on happy path.")
def test_register_failed_email_confirmation(browser):
    register_user_unconfirmed_email(
        browser, UTS.TEST_USER_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )


@pytest.mark.skip(reason="Not on happy path.")
def test_register_failed_password_confirmation(browser):
    register_user_unconfirmed_password(
        browser, UTS.TEST_USER_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )
