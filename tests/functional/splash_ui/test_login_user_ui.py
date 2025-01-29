import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src.utils.strings.email_validation_strs import EMAILS
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from src.utils.strings.user_strs import USER_FAILURE
from tests.functional.locators import ModalLocators as ML
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.utils_for_test import (
    assert_login,
    assert_visited_403_on_invalid_csrf_and_reload,
    invalidate_csrf_token_in_form,
    login_user,
    wait_for_web_element_and_click,
    wait_then_click_element,
    wait_then_get_element,
    dismiss_modal_with_click_out,
    wait_then_get_elements,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.splash_ui


def test_example(browser: WebDriver):
    """
    The one test that will always work to make me feel good
    """
    # Check if the title contains "URLS4IRL"
    assert "URLS4IRL" in browser.title


def test_open_login_modal_center_btn(browser: WebDriver):
    """
    Tests a user's ability to open the Login modal using the center button.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the center login button
    THEN ensure the modal opens
    """
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)
    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    assert modal_element.is_displayed()

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Login!"


def test_open_login_modal_RHS_btn(browser: WebDriver):
    """
    Tests a user's ability to open the Login modal using the RHS corner button

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the RHS login button
    THEN ensure the modal opens
    """

    # Find and click login button to open modal
    navbar = wait_then_get_element(browser, SPL.SPLASH_NAVBAR)
    assert navbar is not None

    login_btn = navbar.find_element(By.CSS_SELECTOR, SPL.BUTTON_LOGIN)
    login_btn.click()

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    assert modal_element.is_displayed()

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Login!"


def test_register_to_login_modal_btn(browser: WebDriver):
    """
    Tests a user's ability to change view from the Register modal to the Login modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens Register modal and wants to change to Login
    THEN ensure the modal view changes
    """
    wait_then_click_element(browser, SPL.BUTTON_REGISTER)
    wait_then_click_element(browser, SPL.BUTTON_LOGIN_FROM_REGISTER)
    wait_until_visible_css_selector(browser, SPL.BUTTON_FORGOT_PASSWORD_MODAL)

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert modal_element is not None

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Login!"


def test_dismiss_login_modal_btn(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by clicking the upper RHS 'x' button

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks the 'x'
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)

    wait_then_click_element(browser, ML.BUTTON_MODAL_DISMISS)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_login_modal_click(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by clicking outside of the modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks anywhere outside of the modal
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)

    dismiss_modal_with_click_out(browser)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_login_modal_x(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by clicking the 'x' button in the upper right hand corner

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks the 'x' of the modal
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)

    wait_then_click_element(browser, SPL.BUTTON_X_MODAL_DISMISS)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_dismiss_login_modal_key(browser: WebDriver):
    """
    Tests a user's ability to close the splash page login modal by pressing the Esc key

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login modal, then presses 'Esc'
    THEN the modal is closed
    """
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)

    splash_modal = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert splash_modal is not None

    splash_modal.send_keys(Keys.ESCAPE)

    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)

    assert not modal_element.is_displayed()


def test_login_test_user_btn(browser: WebDriver, create_test_users):
    """
    Tests a user's ability to login using the splash page login modal

    GIVEN a fresh load of the U4I Splash page and validated user
    WHEN user initiates login sequence
    THEN U4I will login user and display the home page
    """

    login_user(browser)

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    assert_login(browser)


def test_login_test_user_key(browser: WebDriver, create_test_users):
    """
    Tests a user's ability to login using the splash page login modal

    GIVEN a fresh load of the U4I Splash page and validated user
    WHEN user initiates login sequence
    THEN U4I will login user and display the home page
    """

    password_input = login_user(browser)

    # Submit form
    password_input.send_keys(Keys.ENTER)

    assert_login(browser)


def test_login_user_unconfirmed_email_shows_alert(
    browser: WebDriver, create_user_unconfirmed_email
):
    """
    Tests the site error response to a user submitting a login form with unconfirmed email.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to login with an unconfirmed email address
    THEN U4I responds with a failure message and prompts user to confirm email
    """

    login_user(browser, username=UTS.TEST_USERNAME_1, password=UTS.TEST_PASSWORD_1)

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)
    splash_modal_alert_elem = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT)
    assert splash_modal_alert_elem is not None

    assert splash_modal_alert_elem.is_displayed()
    assert (
        splash_modal_alert_elem.find_element(By.CSS_SELECTOR, "div").text
        == USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    )
    assert (
        splash_modal_alert_elem.find_element(By.CSS_SELECTOR, "button").text
        == "Validate My Email"
    )


def test_login_user_unconfirmed_email_validate_btn_shows_validate_modal(
    browser: WebDriver, create_user_unconfirmed_email
):
    """
    Tests the site error response to a user submitting a login form with unconfirmed email, and then clicking on the "Validate My Email" button.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to login with unconfirmed email address, and then clicks on the "Validate My Email" button
    THEN U4I responds with the Validate My Email modal, alert shows with "Email Sent!"
    """

    login_user(browser, username=UTS.TEST_USERNAME_1, password=UTS.TEST_PASSWORD_1)

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)
    splash_modal_alert_elem = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT)
    assert splash_modal_alert_elem is not None

    assert splash_modal_alert_elem.is_displayed()
    validate_email_btn = splash_modal_alert_elem.find_element(By.CSS_SELECTOR, "button")
    wait_for_web_element_and_click(browser, validate_email_btn)
    wait_until_visible_css_selector(browser, SPL.HEADER_VALIDATE_EMAIL)

    email_sent = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT, time=3)
    assert email_sent is not None
    assert email_sent.text == EMAILS.EMAIL_SENT


def test_login_with_nonexistent_user(browser: WebDriver, create_test_users):
    """
    Tests site response when user attempts to login with a user not found in database

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts login with nonexistent username
    THEN U4I will respond with error message
    """

    login_user(
        browser, username=UTS.TEST_PASSWORD_1 + "a", password=UTS.TEST_PASSWORD_1 + "a"
    )

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    error_elem = wait_then_get_elements(browser, SPL.SUBHEADER_INVALID_FEEDBACK)
    assert len(error_elem) == 1
    error_elem = error_elem.pop()

    assert error_elem.text == USER_FAILURE.USER_NOT_EXIST


def test_login_with_invalid_password(browser: WebDriver, create_test_users):
    """
    Tests site response when user attempts to login with an invalid password

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts login with existing user and invalid password
    THEN U4I will respond with error message
    """

    login_user(
        browser, username=UTS.TEST_USERNAME_1, password=UTS.TEST_PASSWORD_1 + "a"
    )

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    error_elem = wait_then_get_elements(browser, SPL.SUBHEADER_INVALID_FEEDBACK)
    assert len(error_elem) == 1
    error_elem = error_elem.pop()

    assert error_elem.text == USER_FAILURE.INVALID_PASSWORD


def test_invalid_username_error_dismissed_on_modal_reload(browser: WebDriver):
    """
    Tests site response when user attempts to login with a user not found in database,
    then closes and reopens modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts login with nonexistent username, then closes and reopens modal
    THEN login modal no longer shows nonexistent user error
    """

    login_user(
        browser, username=UTS.TEST_PASSWORD_1 + "a", password=UTS.TEST_PASSWORD_1 + "a"
    )

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    error_elem = wait_then_get_elements(browser, SPL.SUBHEADER_INVALID_FEEDBACK)
    assert len(error_elem) == 1

    wait_then_click_element(browser, SPL.BUTTON_X_MODAL_DISMISS)

    login_user(
        browser, username=UTS.TEST_PASSWORD_1 + "a", password=UTS.TEST_PASSWORD_1 + "a"
    )
    error_elem = wait_then_get_elements(browser, SPL.SUBHEADER_INVALID_FEEDBACK)
    assert len(error_elem) == 0


def test_invalid_password_error_dismissed_on_modal_reload(browser: WebDriver):
    """
    Tests site response when user attempts to login with an invalid password,
    then closes and reopens modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts login with invalid password, then closes and reopens modal
    THEN login modal no longer shows invalid password error
    """

    login_user(
        browser, username=UTS.TEST_USERNAME_1, password=UTS.TEST_PASSWORD_1 + "a"
    )

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    error_elem = wait_then_get_elements(browser, SPL.SUBHEADER_INVALID_FEEDBACK)
    assert len(error_elem) == 1

    wait_then_click_element(browser, SPL.BUTTON_X_MODAL_DISMISS)

    login_user(
        browser, username=UTS.TEST_PASSWORD_1 + "a", password=UTS.TEST_PASSWORD_1 + "a"
    )
    error_elem = wait_then_get_elements(browser, SPL.SUBHEADER_INVALID_FEEDBACK)
    assert len(error_elem) == 0


def test_login_with_empty_fields(browser: WebDriver):
    """
    Tests site response when user attempts to login with an empty login form

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts login with an empty login field form
    THEN login modal shows field required errors
    """
    login_user(browser, username="", password="")
    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    error_elems = wait_then_get_elements(browser, SPL.SUBHEADER_INVALID_FEEDBACK)
    assert len(error_elems) == 2
    assert all([elem.text == USER_FAILURE.FIELD_REQUIRED_STR for elem in error_elems])


def test_login_user_invalid_csrf(browser: WebDriver):
    """
    Tests site response when user attempts to login with an invalid CSRF token

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts login with an invalid CSRF token
    THEN browser redirects user to error page, where user can refresh
    """
    login_user(browser, username="", password="")

    # Find submit button to login
    invalidate_csrf_token_in_form(browser)
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    # Visit 403 error page due to CSRF, then reload
    assert_visited_403_on_invalid_csrf_and_reload(browser)

    welcome_text = wait_then_get_element(browser, SPL.WELCOME_TEXT, time=3)
    assert welcome_text is not None

    assert welcome_text.text == IDENTIFIERS.SPLASH_PAGE
