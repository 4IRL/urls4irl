import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from src.utils.strings.email_validation_strs import (
    EMAILS,
    VALIDATE_MY_EMAIL,
    VALIDATE_YOUR_EMAIL,
)
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from src.utils.strings.user_strs import USER_FAILURE
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.locators import ModalLocators as ML
from tests.functional.splash_ui.utils_for_test_splash_ui import (
    register_user_ui,
)
from tests.functional.utils_for_test import (
    assert_visited_403_on_invalid_csrf_and_reload,
    dismiss_modal_with_click_out,
    invalidate_csrf_token_in_form,
    wait_for_web_element_and_click,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.splash_ui


def test_open_register_modal_center_btn(browser: WebDriver):
    """
    Tests a user's ability to open the Register modal using the center button.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the center register button
    THEN ensure the modal opens
    """
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)
    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    assert modal_element.is_displayed()

    modal_title = wait_then_get_element(
        browser, f"{SPL.SPLASH_MODAL} .modal-title", time=3
    )
    assert modal_title is not None
    assert modal_title.text == "Register"


def test_open_register_modal_RHS_btn(browser: WebDriver):
    """
    Tests a user's ability to open the Register modal using the RHS corner button

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the RHS register button
    THEN ensure the modal opens
    """

    # Find and click login button to open modal
    navbar = wait_then_get_element(browser, SPL.SPLASH_NAVBAR)
    assert navbar is not None

    register_btn = navbar.find_element(By.CSS_SELECTOR, SPL.NAVBAR_REGISTER)
    register_btn.click()

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    assert modal_element.is_displayed()

    modal_title = wait_then_get_element(
        browser, f"{SPL.SPLASH_MODAL} .modal-title", time=3
    )
    assert modal_title is not None
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
    assert modal_element is not None

    modal_title = wait_then_get_element(
        browser, f"{SPL.SPLASH_MODAL} .modal-title", time=3
    )
    assert modal_title is not None
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


def test_dismiss_register_modal_key(browser: WebDriver):
    """
    Tests a user's ability to close the splash page register modal by pressing the Esc key

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the register modal, then presses 'Esc'
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)

    wait_until_visible_css_selector(browser, SPL.INPUT_USERNAME, timeout=3)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

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


def test_register_new_user_btn(browser: WebDriver):
    """
    Tests a user's ability to register as a new user.

    GIVEN a fresh load of the U4I Splash page
    WHEN initiates registration modal and inputs desired login information
    THEN U4I responds with a success modal prompting user to 'Validate Your Email!'
    """

    register_user_ui(
        browser, UTS.TEST_USERNAME_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Await response
    modal_title = wait_then_get_element(browser, SPL.HEADER_VALIDATE_EMAIL, time=3)
    assert modal_title is not None

    assert modal_title.text == VALIDATE_YOUR_EMAIL


def test_register_new_user_key(browser: WebDriver):
    """
    Tests a user's ability to register as a new user.

    GIVEN a fresh load of the U4I Splash page
    WHEN initiates registration modal and inputs desired login information
    THEN U4I responds with a success modal prompting user to 'Validate Your Email!'
    """

    register_user_ui(
        browser, UTS.TEST_USERNAME_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )

    # Submit form
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    # Await response
    modal_title = wait_then_get_element(browser, SPL.HEADER_VALIDATE_EMAIL, time=3)
    assert modal_title is not None

    assert modal_title.text == VALIDATE_YOUR_EMAIL


def test_register_existing_username(browser: WebDriver, create_test_users):
    """
    Tests the site error response to a user's attempt to register with a username that is already registered in the database.

    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing username
    THEN U4I responds with a failure on register form
    """

    register_user_ui(
        browser=browser,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_UNLISTED,
        password=UTS.TEST_PASSWORD_UNLISTED,
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Extract error message text
    invalid_feedback_username_message = wait_then_get_element(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK, time=3
    )
    assert invalid_feedback_username_message is not None

    assert invalid_feedback_username_message.text == USER_FAILURE.USERNAME_TAKEN


def test_register_sanitized_username(browser: WebDriver, create_test_users):
    """
    Tests the site error response to a user's attempt to register with a username that is sanitized by the backend.

    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing username
    THEN U4I responds with a failure on register form
    """

    register_user_ui(
        browser=browser,
        username='<img src="evl.jpg">',
        email=UTS.TEST_PASSWORD_UNLISTED,
        password=UTS.TEST_PASSWORD_UNLISTED,
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Extract error message text
    invalid_feedback_username_message = wait_then_get_element(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK, time=3
    )
    assert invalid_feedback_username_message is not None

    assert invalid_feedback_username_message.text == USER_FAILURE.INVALID_INPUT


def test_register_existing_email(browser: WebDriver, create_test_users):
    """
    Tests the site error response to a user's attempt to register with an email that is already registered in the database.

    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing email
    THEN U4I responds with a failure on register form
    """

    register_user_ui(
        browser=browser,
        username=UTS.TEST_USERNAME_UNLISTED,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Extract error message text
    invalid_feedback_email_message = wait_then_get_element(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK
    )
    assert invalid_feedback_email_message is not None

    assert invalid_feedback_email_message.text == USER_FAILURE.EMAIL_TAKEN


def test_register_existing_username_and_email(browser: WebDriver, create_test_users):
    """
    Tests the site error response to a user's attempt to register with a username and email that is already registered in the database.

    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing username and email
    THEN U4I responds with a failure on register form
    """

    register_user_ui(
        browser=browser,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Extract error message text
    invalid_feedback_messages = wait_then_get_elements(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK
    )
    assert len(invalid_feedback_messages) == 2
    assert any(
        [elem.text == USER_FAILURE.USERNAME_TAKEN for elem in invalid_feedback_messages]
    )
    assert any(
        [elem.text == USER_FAILURE.EMAIL_TAKEN for elem in invalid_feedback_messages]
    )


def test_register_user_unconfirmed_email_shows_alert(
    browser: WebDriver, create_user_unconfirmed_email
):
    """
    Tests the site error response to a user submitting a register form with unconfirmed email.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with unconfirmed email address
    THEN U4I responds with a failure message and prompts user to confirm email
    """

    register_user_ui(
        browser, UTS.TEST_USERNAME_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Extract error message text
    unconfirmed_email_feedback = wait_then_get_element(
        browser, SPL.SPLASH_MODAL_ALERT, time=3
    )
    assert unconfirmed_email_feedback is not None

    assert unconfirmed_email_feedback.is_displayed()
    assert (
        unconfirmed_email_feedback.find_element(By.CSS_SELECTOR, "div").text
        == USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    )
    assert (
        unconfirmed_email_feedback.find_element(By.CSS_SELECTOR, "button").text
        == VALIDATE_MY_EMAIL
    )


def test_register_user_unconfirmed_email_validate_btn_shows_validate_modal(
    browser: WebDriver, create_user_unconfirmed_email
):
    """
    Tests the site error response to a user submitting a register form with unconfirmed email, and then clicking on the "Validate My Email" button.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with unconfirmed email address, and then clicks on the "Validate My Email" button
    THEN U4I responds with the Validate My Email modal, alert shows with "Email Sent!"
    """

    register_user_ui(
        browser, UTS.TEST_USERNAME_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Extract error message text
    unconfirmed_email_feedback = wait_then_get_element(
        browser, SPL.SPLASH_MODAL_ALERT, time=3
    )
    assert unconfirmed_email_feedback is not None

    assert unconfirmed_email_feedback.is_displayed()
    validate_email_btn = unconfirmed_email_feedback.find_element(
        By.CSS_SELECTOR, "button"
    )
    wait_for_web_element_and_click(browser, validate_email_btn)
    wait_until_visible_css_selector(browser, SPL.HEADER_VALIDATE_EMAIL)

    email_sent = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT, time=3)
    assert email_sent is not None
    assert email_sent.text == EMAILS.EMAIL_SENT


def test_register_failed_password_equality(browser: WebDriver):
    """
    Tests the site error response to a user submitting a register form with mismatched password inputs.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with mismatched passwords
    THEN U4I responds with a failure message and prompts user to double check inputs
    """

    register_user_ui(
        browser=browser,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
        email_confirm=UTS.TEST_PASSWORD_1,
        pass_confirm=UTS.TEST_PASSWORD_1 + "a",
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Extract error message text
    invalid_feedback_username_message = wait_then_get_element(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK, time=3
    )
    assert invalid_feedback_username_message is not None

    assert invalid_feedback_username_message.text == UTS.PASSWORD_EQUALITY_FAILED


def test_register_failed_email_equality(browser: WebDriver):
    """
    Tests the site error response to a user submitting a register form with mismatched email inputs.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with mismatched emails
    THEN U4I responds with a failure message and prompts user to double check inputs
    """

    register_user_ui(
        browser=browser,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
        email_confirm=UTS.TEST_PASSWORD_1 + "a",
        pass_confirm=UTS.TEST_PASSWORD_1,
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Extract error message text
    invalid_feedback_username_message = wait_then_get_element(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK, time=3
    )
    assert invalid_feedback_username_message is not None

    assert invalid_feedback_username_message.text == UTS.EMAIL_EQUALITY_FAILED


def test_register_failed_empty_fields(browser: WebDriver):
    """
    Tests the site error response to a user submitting a register form with empty fields.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with empty fields
    THEN U4I responds with a failure empty and prompts user to double check inputs
    """
    register_user_ui(
        browser=browser,
        username="",
        email="",
        password="",
        email_confirm="",
        pass_confirm="",
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Extract error message text
    invalid_feedback_messages = wait_then_get_elements(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK
    )
    assert len(invalid_feedback_messages) == 5
    assert all(
        [
            elem.text == USER_FAILURE.FIELD_REQUIRED_STR
            for elem in invalid_feedback_messages
        ]
    )


def test_register_form_resets_on_close(browser: WebDriver):
    """
    Tests the site error response to a user submitting a register form with empty fields.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with empty fields
    THEN U4I responds with a failure empty and prompts user to double check inputs
    """
    register_user_ui(
        browser=browser,
        username="",
        email="",
        password="",
        email_confirm="",
        pass_confirm="",
    )

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Extract error message text
    invalid_feedback_messages = wait_then_get_elements(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK
    )
    assert len(invalid_feedback_messages) == 5
    assert all(
        [
            elem.text == USER_FAILURE.FIELD_REQUIRED_STR
            for elem in invalid_feedback_messages
        ]
    )

    wait_then_click_element(browser, ML.BUTTON_MODAL_DISMISS)

    wait_until_hidden(browser, SPL.SPLASH_MODAL)
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)
    wait_until_visible_css_selector(browser, SPL.INPUT_USERNAME, timeout=3)

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, SPL.SUBHEADER_INVALID_FEEDBACK)


def test_register_new_user_invalid_csrf(browser: WebDriver):
    """
    Tests a user's ability to register as a new user.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts registration with an invalid CSRF token
    THEN browser redirects user to error page, where user can refresh
    """
    '''
    browser.execute_script("""
    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
          if (
            !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) &&
            !this.crossDomain
          ) {
            xhr.setRequestHeader("X-CSRFToken", "invalid-csrf-token");
          }
          return true;
        }
    });
    """)
    '''
    register_user_ui(
        browser, UTS.TEST_USERNAME_1, UTS.TEST_PASSWORD_1, UTS.TEST_PASSWORD_1
    )
    invalidate_csrf_token_in_form(browser)

    # Submit form
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Visit 403 error page due to CSRF, then reload
    assert_visited_403_on_invalid_csrf_and_reload(browser)

    welcome_text = wait_then_get_element(browser, SPL.WELCOME_TEXT, time=3)
    assert welcome_text is not None

    assert welcome_text.text == IDENTIFIERS.SPLASH_PAGE
