import pytest
from playwright.sync_api import Page, expect

from backend.api_common.request_errors import INVALID_EMAIL_STR, min_length_message
from backend.utils.strings.email_validation_strs import (
    EMAILS,
    VALIDATE_MY_EMAIL,
    VALIDATE_YOUR_EMAIL,
)
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.user_strs import USER_FAILURE
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_assert_utils import (
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    dismiss_modal_with_click_out,
    invalidate_csrf_token_in_form,
    wait_for_modal_hidden,
    wait_for_modal_ready,
    wait_for_web_element_and_click,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.splash_ui.playwright_utils import register_user_ui

pytestmark = pytest.mark.splash_ui


def test_open_register_modal_center_btn(page: Page):
    """
    Tests a user's ability to open the Register modal using the center button.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the center register button
    THEN ensure the modal opens
    """
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER)
    modal_element = wait_then_get_element(page=page, css_selector=SPL.REGISTER_MODAL)
    expect(modal_element).to_be_visible()
    expect(modal_element.locator(".modal-title").first).to_have_text("Register")


def test_open_register_modal_RHS_btn(page: Page):
    """
    Tests a user's ability to open the Register modal using the RHS corner button

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the RHS register button
    THEN ensure the modal opens
    """
    navbar = wait_then_get_element(page=page, css_selector=SPL.SPLASH_NAVBAR)
    register_btn = navbar.locator(SPL.NAVBAR_REGISTER).first
    register_btn.click()

    modal_element = wait_then_get_element(page=page, css_selector=SPL.REGISTER_MODAL)
    expect(modal_element).to_be_visible()
    expect(modal_element.locator(".modal-title").first).to_have_text("Register")


def test_login_to_register_modal_btn(page: Page):
    """
    Tests a user's ability to change view from the Login modal to the Register modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens Login modal and wants to change to Register
    THEN ensure the modal view changes
    """
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_LOGIN)
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER_FROM_LOGIN)
    wait_for_modal_hidden(page=page, modal_selector=SPL.LOGIN_MODAL)
    wait_for_modal_ready(page=page, modal_selector=SPL.REGISTER_MODAL)

    modal_element = wait_then_get_element(page=page, css_selector=SPL.REGISTER_MODAL)
    expect(modal_element.locator(".modal-title").first).to_have_text("Register")


def test_dismiss_register_modal_btn(page: Page):
    """
    Tests a user's ability to close the splash page register modal by clicking the upper RHS 'x' button

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the register, then clicks the 'x'
    THEN the modal is closed
    """
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER)
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BTN_CLOSE)
    wait_until_hidden(page=page, css_selector=SPL.REGISTER_MODAL)


def test_dismiss_register_modal_key(page: Page):
    """
    Tests a user's ability to close the splash page register modal by pressing the Esc key

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the register modal, then presses 'Esc'
    THEN the modal is closed
    """
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER)
    wait_for_modal_ready(page=page, modal_selector=SPL.REGISTER_MODAL)
    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=SPL.REGISTER_MODAL)


def test_dismiss_register_modal_click(page: Page):
    """
    Tests a user's ability to close the splash page register modal by clicking outside of the modal

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the register, then clicks anywhere outside of the modal
    THEN the modal is closed
    """
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER)
    wait_for_modal_ready(page=page, modal_selector=SPL.REGISTER_MODAL)
    dismiss_modal_with_click_out(page=page, modal_selector=SPL.REGISTER_MODAL)
    wait_until_hidden(page=page, css_selector=SPL.REGISTER_MODAL)


def test_dismiss_register_modal_x(page: Page):
    """
    Tests a user's ability to close the splash page login modal by clicking the 'x' button in the upper right hand corner

    GIVEN a fresh load of the U4I Splash page
    WHEN user opens the login, then clicks the 'x' of the modal
    THEN the modal is closed
    """
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER)
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_X_MODAL_DISMISS)
    wait_until_hidden(page=page, css_selector=SPL.REGISTER_MODAL)


def test_register_new_user_btn(page: Page):
    """
    Tests a user's ability to register as a new user.

    GIVEN a fresh load of the U4I Splash page
    WHEN initiates registration modal and inputs desired login information
    THEN U4I responds with a success modal prompting user to 'Validate Your Email!'
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
    )
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    modal_title = wait_then_get_element(
        page=page, css_selector=SPL.HEADER_VALIDATE_EMAIL
    )
    expect(modal_title).to_have_text(VALIDATE_YOUR_EMAIL)


def test_register_new_user_key(page: Page):
    """
    Tests a user's ability to register as a new user.

    GIVEN a fresh load of the U4I Splash page
    WHEN initiates registration modal and inputs desired login information
    THEN U4I responds with a success modal prompting user to 'Validate Your Email!'
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
    )
    page.keyboard.press("Enter")

    modal_title = wait_then_get_element(
        page=page, css_selector=SPL.HEADER_VALIDATE_EMAIL
    )
    expect(modal_title).to_have_text(VALIDATE_YOUR_EMAIL)


def test_register_user_rate_limits(page: Page):
    """
    Tests a user's ability to register as a new user but they are rate limited.

    GIVEN a fresh load of the U4I Splash page but user is rate limited
    WHEN initiates registration modal and inputs desired login information
    THEN U4I responds with 429 error page
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
    )
    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)
    assert_on_429_page(page=page)


def test_register_existing_username(page: Page, create_test_users):
    """
    Tests the site error response to a user's attempt to register with a username that is already registered in the database.

    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing username
    THEN U4I responds with a failure on register form
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_UNLISTED,
        password=UTS.TEST_PASSWORD_UNLISTED,
    )
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    invalid_feedback = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_INVALID_FEEDBACK
    )
    expect(invalid_feedback).to_have_text(USER_FAILURE.USERNAME_TAKEN)


def test_register_sanitized_username(page: Page, create_test_users):
    """
    Tests the site error response to a user's attempt to register with a username that is sanitized by the backend.

    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing username
    THEN U4I responds with a failure on register form
    """
    register_user_ui(
        page=page,
        username='<img src="evl.jpg">',
        email=UTS.TEST_PASSWORD_UNLISTED,
        password=UTS.TEST_PASSWORD_UNLISTED,
    )
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    invalid_feedback = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_INVALID_FEEDBACK
    )
    expect(invalid_feedback).to_have_text(USER_FAILURE.INVALID_INPUT)


def test_register_existing_email(page: Page, create_test_users):
    """
    Tests the site error response to a user's attempt to register with an email that is already registered in the database.

    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing email
    THEN U4I responds with a failure on register form
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_UNLISTED,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
    )
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    invalid_feedback = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_INVALID_FEEDBACK
    )
    expect(invalid_feedback).to_have_text(USER_FAILURE.EMAIL_TAKEN)


def test_register_existing_username_and_email(page: Page, create_test_users):
    """
    Tests the site error response to a user's attempt to register with a username and email that is already registered in the database.

    GIVEN a fresh load of the U4I Splash page, and pre-registered user
    WHEN user attempts to register an existing username and email
    THEN U4I responds with a failure on register form
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
    )
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    invalid_feedback_messages = wait_then_get_elements(
        page=page, css_selector=SPL.REGISTER_INVALID_FEEDBACK
    )
    assert len(invalid_feedback_messages) == 2
    texts = [msg.inner_text() for msg in invalid_feedback_messages]
    assert any(USER_FAILURE.USERNAME_TAKEN == text for text in texts)
    assert any(USER_FAILURE.EMAIL_TAKEN == text for text in texts)


def test_register_user_unconfirmed_email_shows_alert(
    page: Page, create_user_unconfirmed_email
):
    """
    Tests the site error response to a user submitting a register form with unconfirmed email.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with unconfirmed email address
    THEN U4I responds with a failure message and prompts user to confirm email
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
    )
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    unconfirmed_email_feedback = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_MODAL_ALERT
    )
    expect(unconfirmed_email_feedback).to_be_visible()
    expect(unconfirmed_email_feedback.locator("div").first).to_have_text(
        USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    )
    expect(unconfirmed_email_feedback.locator("button").first).to_have_text(
        VALIDATE_MY_EMAIL
    )


def test_register_user_unconfirmed_email_validate_btn_shows_validate_modal(
    page: Page, create_user_unconfirmed_email
):
    """
    Tests the site error response to a user submitting a register form with unconfirmed email, and then clicking on the "Validate My Email" button.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with unconfirmed email address, and then clicks on the "Validate My Email" button
    THEN U4I responds with the Validate My Email modal, alert shows with "Email Sent!"
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
    )
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    unconfirmed_email_feedback = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_MODAL_ALERT
    )
    expect(unconfirmed_email_feedback).to_be_visible()

    validate_email_btn = unconfirmed_email_feedback.locator("button").first
    wait_for_web_element_and_click(locator=validate_email_btn)
    wait_until_visible_css_selector(page=page, css_selector=SPL.HEADER_VALIDATE_EMAIL)

    email_sent = wait_then_get_element(
        page=page, css_selector=SPL.EMAIL_VALIDATION_MODAL_ALERT
    )
    expect(email_sent).to_have_text(EMAILS.EMAIL_SENT)


def test_register_failed_password_equality(page: Page):
    """
    Tests the site error response to a user submitting a register form with mismatched password inputs.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with mismatched passwords
    THEN U4I responds with a failure message and prompts user to double check inputs
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
        email_confirm=UTS.TEST_PASSWORD_1,
        pass_confirm=UTS.TEST_PASSWORD_1 + "a",
    )
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    invalid_feedback = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_INVALID_FEEDBACK
    )
    expect(invalid_feedback).to_have_text(UTS.PASSWORD_EQUALITY_FAILED)


def test_register_failed_email_equality(page: Page):
    """
    Tests the site error response to a user submitting a register form with mismatched email inputs.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with mismatched emails
    THEN U4I responds with a failure message and prompts user to double check inputs
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
        email_confirm=UTS.TEST_PASSWORD_1 + "a",
        pass_confirm=UTS.TEST_PASSWORD_1,
    )
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    invalid_feedback = wait_then_get_element(
        page=page, css_selector=SPL.REGISTER_INVALID_FEEDBACK
    )
    expect(invalid_feedback).to_have_text(UTS.EMAIL_EQUALITY_FAILED)


def test_register_failed_empty_fields(page: Page):
    """
    Tests the site error response to a user submitting a register form with empty fields.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with empty fields
    THEN U4I responds with a failure empty and prompts user to double check inputs
    """
    register_user_ui(
        page=page,
        username="",
        email="",
        password="",
        email_confirm="",
        pass_confirm="",
    )
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    invalid_feedback_messages = wait_then_get_elements(
        page=page, css_selector=SPL.REGISTER_INVALID_FEEDBACK
    )
    assert len(invalid_feedback_messages) == 5
    expected_errors = [
        min_length_message(3),
        INVALID_EMAIL_STR,
        USER_FAILURE.FIELD_REQUIRED_STR,
        min_length_message(12),
        USER_FAILURE.FIELD_REQUIRED_STR,
    ]
    actual_texts = [elem.inner_text() for elem in invalid_feedback_messages]
    assert actual_texts == expected_errors


def test_register_form_resets_on_close(page: Page):
    """
    Tests the site error response to a user submitting a register form with empty fields.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts to register with empty fields
    THEN U4I responds with a failure empty and prompts user to double check inputs
    """
    register_user_ui(
        page=page,
        username="",
        email="",
        password="",
        email_confirm="",
        pass_confirm="",
    )
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    invalid_feedback_messages = wait_then_get_elements(
        page=page, css_selector=SPL.REGISTER_INVALID_FEEDBACK
    )
    assert len(invalid_feedback_messages) == 5
    expected_errors = [
        min_length_message(3),
        INVALID_EMAIL_STR,
        USER_FAILURE.FIELD_REQUIRED_STR,
        min_length_message(12),
        USER_FAILURE.FIELD_REQUIRED_STR,
    ]
    actual_texts = [elem.inner_text() for elem in invalid_feedback_messages]
    assert actual_texts == expected_errors

    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BTN_CLOSE)
    wait_until_hidden(page=page, css_selector=SPL.REGISTER_MODAL)

    wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER)
    wait_until_visible_css_selector(page=page, css_selector=SPL.REGISTER_INPUT_USERNAME)

    assert page.locator(SPL.REGISTER_INVALID_FEEDBACK).count() == 0


def test_register_new_user_invalid_csrf(page: Page):
    """
    Tests a user's ability to register as a new user.

    GIVEN a fresh load of the U4I Splash page
    WHEN user attempts registration with an invalid CSRF token
    THEN browser redirects user to error page, where user can refresh
    """
    register_user_ui(
        page=page,
        username=UTS.TEST_USERNAME_1,
        email=UTS.TEST_PASSWORD_1,
        password=UTS.TEST_PASSWORD_1,
    )
    invalidate_csrf_token_in_form(page=page)
    wait_then_click_element(page=page, css_selector=SPL.REGISTER_BUTTON_SUBMIT)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    welcome_text = wait_then_get_element(page=page, css_selector=SPL.WELCOME_TEXT)
    expect(welcome_text).to_have_text(IDENTIFIERS.SPLASH_PAGE)
