from datetime import datetime
from flask import Flask
import pytest
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src import db
from src.config import ConfigTest
from src.models.forgot_passwords import Forgot_Passwords
from src.models.users import Users
from src.utils.constants import CONSTANTS
from src.utils.datetime_utils import utc_now
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.json_strs import FAILURE_GENERAL
from src.utils.strings.reset_password_strs import RESET_PASSWORD
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import (
    assert_on_404_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.locators import ModalLocators, SplashPageLocators as SPL
from tests.functional.selenium_utils import (
    dismiss_modal_with_click_out,
    invalidate_csrf_token_in_form,
    wait_for_page_complete_and_dom_stable,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.splash_ui


def test_password_reset_routes_user_properly(
    browser: WebDriver, create_user_resetting_password
):
    """
    Tests a user's ability to click a non-expired password reset URL

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password
    THEN ensure the splash page opens and the reset password modal shows
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)

    assert wait_then_get_element(browser, SPL.INPUT_NEW_PASSWORD, time=3) is not None
    assert wait_then_get_element(browser, SPL.INPUT_CONFIRM_NEW_PASSWORD) is not None


def test_password_reset_dismiss_modal_click(
    browser: WebDriver, create_user_resetting_password, provide_port, provide_config
):
    """
    Tests a user's ability to click a non-expired password reset URL

    GIVEN a valid user requesting to reset their password
    WHEN user clicks anywhere outside of the modal
    THEN ensure the modal is closed
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)

    assert wait_then_get_element(browser, SPL.INPUT_NEW_PASSWORD, time=3) is not None
    splash_modal = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert splash_modal is not None

    # Put focus on splash modal and wait, or else escape key won't work
    splash_modal.click()
    wait_for_page_complete_and_dom_stable(browser, timeout=10)

    dismiss_modal_with_click_out(browser)
    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)
    assert not modal_element.is_displayed()
    config: ConfigTest = provide_config
    base_url = UTS.DOCKER_BASE_URL if config.DOCKER else UTS.BASE_URL
    assert browser.current_url == f"{base_url}{provide_port}/"


def test_password_reset_dismiss_modal_x(
    browser: WebDriver, create_user_resetting_password, provide_port, provide_config
):
    """
    Tests a user's ability to click a non-expired password reset URL

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the 'x' of the modal
    THEN ensure the modal is closed
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)

    assert wait_then_get_element(browser, SPL.INPUT_NEW_PASSWORD, time=3) is not None
    splash_modal = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert splash_modal is not None

    # Put focus on splash modal and wait, or else escape key won't work
    splash_modal.click()
    wait_for_page_complete_and_dom_stable(browser, timeout=10)

    wait_then_click_element(browser, ModalLocators.BUTTON_X_MODAL_DISMISS, time=3)
    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL)
    assert not modal_element.is_displayed()

    config: ConfigTest = provide_config
    base_url = UTS.DOCKER_BASE_URL if config.DOCKER else UTS.BASE_URL
    assert browser.current_url == f"{base_url}{provide_port}/"


def test_password_reset_dismiss_modal_key(
    browser: WebDriver,
    create_user_resetting_password,
    provide_port: int,
    provide_config,
):
    """
    Tests a user's ability to click a non-expired password reset URL

    GIVEN a valid user requesting to reset their password
    WHEN user presses the escape key
    THEN ensure the modal is closed
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)

    assert wait_then_get_element(browser, SPL.INPUT_NEW_PASSWORD, time=3) is not None
    splash_modal = wait_then_get_element(browser, SPL.SPLASH_MODAL)
    assert splash_modal is not None

    # Put focus on splash modal and wait, or else escape key won't work
    splash_modal.click()
    wait_for_page_complete_and_dom_stable(browser, timeout=10)

    ActionChains(browser).send_keys(Keys.ESCAPE).perform()
    modal_element = wait_until_hidden(browser, SPL.SPLASH_MODAL, timeout=5)
    assert not modal_element.is_displayed()
    config: ConfigTest = provide_config
    base_url = UTS.DOCKER_BASE_URL if config.DOCKER else UTS.BASE_URL
    assert browser.current_url == f"{base_url}{provide_port}/"


def test_password_reset_successful_reset_btn(
    browser: WebDriver, create_user_resetting_password, provide_app: Flask
):
    """
    Tests a user's ability to change their password using the form provided

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password and changes their password by clicking submit
    THEN ensure the password shows as reset
    """
    NEW_PASSWORD = "ABCDEFGH1234568"

    app = provide_app

    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)

    new_password_input = wait_then_get_element(browser, SPL.INPUT_NEW_PASSWORD, time=3)
    assert new_password_input is not None

    confirm_new_password_input = wait_then_get_element(
        browser, SPL.INPUT_CONFIRM_NEW_PASSWORD
    )
    assert confirm_new_password_input is not None

    new_password_input.send_keys(NEW_PASSWORD)
    confirm_new_password_input.send_keys(NEW_PASSWORD)

    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)
    confirm_alert = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT, time=3)
    assert confirm_alert is not None

    assert confirm_alert.text == RESET_PASSWORD.PASSWORD_RESET

    with app.app_context():
        user: Users = Users.query.first()
        assert user.is_password_correct(NEW_PASSWORD)


def test_password_reset_successful_reset_key(
    browser: WebDriver, create_user_resetting_password, provide_app: Flask
):
    """
    Tests a user's ability to change their password using the form provided

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password and changes their password by pressing enter on last input
    THEN ensure the password shows as reset
    """
    NEW_PASSWORD = "ABCDEFGH1234568"

    app = provide_app

    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)

    new_password_input = wait_then_get_element(browser, SPL.INPUT_NEW_PASSWORD, time=3)
    assert new_password_input is not None

    confirm_new_password_input = wait_then_get_element(
        browser, SPL.INPUT_CONFIRM_NEW_PASSWORD
    )
    assert confirm_new_password_input is not None

    new_password_input.send_keys(NEW_PASSWORD)
    confirm_new_password_input.send_keys(NEW_PASSWORD)

    browser.switch_to.active_element.send_keys(Keys.ENTER)

    confirm_alert = wait_then_get_element(browser, SPL.SPLASH_MODAL_ALERT, time=3)
    assert confirm_alert is not None

    assert confirm_alert.text == RESET_PASSWORD.PASSWORD_RESET

    with app.app_context():
        user: Users = Users.query.first()
        assert user.is_password_correct(NEW_PASSWORD)


def test_password_reset_with_hour_old_token(
    browser: WebDriver, create_user_resetting_password, provide_app: Flask
):
    """
    Tests U4I response for user clicking on reset password URL with more than hour old token

    GIVEN a valid user wanting to reset their password
    WHEN user clicks the URL generated for resetting their password but URL contains token that is more than an hour old
    THEN ensure 404 page is shown
    """
    app = provide_app
    with app.app_context():
        forgot_password: Forgot_Passwords = Forgot_Passwords.query.first()
        forgot_password.initial_attempt = datetime.fromtimestamp(
            int(datetime.timestamp(utc_now()))
            - (CONSTANTS.USERS.WAIT_TO_RETRY_FORGOT_PASSWORD_MAX + 5)
        )
        db.session.commit()

    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)
    assert_on_404_page(browser)


def test_password_reset_with_expired_token(
    browser: WebDriver, create_user_resetting_password, provide_app: Flask
):
    """
    Tests U4I response for user clicking on reset password URL with expired token

    GIVEN a valid user wanting to reset their password
    WHEN user clicks the URL generated for resetting their password but URL contains expired token
    THEN ensure 404 page is shown
    """
    app = provide_app
    with app.app_context():
        user: Users = Users.query.first()
        expired_token = user.get_password_reset_token(expires_in=0)
        forgot_password: Forgot_Passwords = Forgot_Passwords.query.first()
        forgot_password.reset_token = expired_token
        db.session.commit()

    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)
    assert_on_404_page(browser)


def test_password_reset_with_invalid_token(
    browser: WebDriver, create_user_resetting_password
):
    """
    Tests U4I response for user clicking on reset password URL with invalid token

    GIVEN a valid user wanting to reset their password
    WHEN user clicks the URL generated for resetting their password but URL contains invalid token
    THEN ensure 404 page is shown
    """
    INVALID_TOKEN = "abcdefghijklmnop"

    reset_password_url = browser.current_url + "reset-password/" + INVALID_TOKEN
    browser.get(reset_password_url)
    assert_on_404_page(browser)


def test_password_reset_with_unconfirmed_email(
    browser: WebDriver, create_user_resetting_password, provide_app: Flask
):
    """
    Tests U4I response for user clicking on reset password URL with an unconfirmed email

    GIVEN a valid user wanting to reset their password
    WHEN user clicks the URL generated for resetting their password but haven't confirmed their email
    THEN ensure 404 page is shown
    """
    app = provide_app
    with app.app_context():
        user: Users = Users.query.first()
        user.email_validated = False
        db.session.commit()

    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)
    assert_on_404_page(browser)


def test_password_reset_unequal_password_fields(
    browser: WebDriver, create_user_resetting_password
):
    """
    Tests a user's ability to change their password using the form provided

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password and a confirm password that is not
    equal to the new password
    THEN ensure U4I responds with appropriate error message
    """
    NEW_PASSWORD = "ABCDEFGH1234568"

    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)

    new_password_input = wait_then_get_element(browser, SPL.INPUT_NEW_PASSWORD, time=3)
    assert new_password_input is not None

    confirm_new_password_input = wait_then_get_element(
        browser, SPL.INPUT_CONFIRM_NEW_PASSWORD
    )
    assert confirm_new_password_input is not None

    new_password_input.send_keys(NEW_PASSWORD)
    confirm_new_password_input.send_keys(NEW_PASSWORD + "a")

    wait_for_page_complete_and_dom_stable(browser, timeout=10)
    browser.find_element(By.CSS_SELECTOR, SPL.BUTTON_SUBMIT).click()
    wait_for_page_complete_and_dom_stable(browser, timeout=10)

    invalid_field = wait_then_get_element(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK, time=3
    )
    assert invalid_field is not None
    assert invalid_field.text == RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL


def test_password_reset_missing_fields(
    browser: WebDriver, create_user_resetting_password
):
    """
    Tests a user's ability to change their password using the form provided

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password and submits with empty fields
    THEN ensure U4I responds with appropriate error message
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)

    wait_until_visible_css_selector(browser, SPL.BUTTON_SUBMIT, timeout=3)
    submit_btn = wait_then_click_element(browser, SPL.BUTTON_SUBMIT, time=3)
    assert submit_btn is not None

    wait_until_visible_css_selector(browser, SPL.SUBHEADER_INVALID_FEEDBACK, timeout=3)
    invalid_fields = wait_then_get_elements(
        browser, SPL.SUBHEADER_INVALID_FEEDBACK, time=3
    )
    assert len(invalid_fields) == 2

    assert all(
        [field.text == FAILURE_GENERAL.FIELD_REQUIRED_STR for field in invalid_fields]
    )


def test_password_reset_invalid_csrf_token(
    browser: WebDriver, create_user_resetting_password
):
    """
    Tests a user's ability to attempt to submit password reset with invalid CSRF token

    GIVEN a valid user requesting to reset their password
    WHEN user clicks the URL generated for resetting their password and submits with an invalid CSRF token
    THEN browser redirects user to error page, where user can refresh
    """
    reset_password_suffix = create_user_resetting_password
    reset_password_suffix = (
        reset_password_suffix[1:]
        if reset_password_suffix[0] == "/"
        else reset_password_suffix
    )
    reset_password_url = browser.current_url + reset_password_suffix

    browser.get(reset_password_url)

    new_password_input = wait_then_get_element(browser, SPL.INPUT_NEW_PASSWORD, time=3)
    assert new_password_input is not None

    confirm_new_password_input = wait_then_get_element(
        browser, SPL.INPUT_CONFIRM_NEW_PASSWORD
    )
    assert confirm_new_password_input is not None
    wait_for_page_complete_and_dom_stable(browser, timeout=10)

    invalidate_csrf_token_in_form(browser)
    wait_for_page_complete_and_dom_stable(browser, timeout=10)
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT, time=10)

    # Visit 403 error page due to CSRF, then reload
    assert_visited_403_on_invalid_csrf_and_reload(browser)

    welcome_text = wait_then_get_element(browser, SPL.WELCOME_TEXT, time=3)
    assert welcome_text is not None

    assert welcome_text.text == IDENTIFIERS.SPLASH_PAGE
