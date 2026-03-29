from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.assert_utils import (
    assert_login,
    assert_on_429_page,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    create_user_session_and_provide_session_id,
    login_user_with_cookie_from_session,
)
from tests.functional.selenium_utils import (
    ChromeRemoteWebDriver,
    contact_form_entry,
    modify_navigational_link_for_rate_limit,
    visit_contact_us_page,
    visit_privacy_page,
    visit_terms_page,
    wait_then_click_element,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.home_ui


def test_privacy_policy(browser: WebDriver, create_test_users, provide_app: Flask):
    """
    Tests a logged in user's ability to visit the privacy page from the home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the privacy button in the footer
    THEN ensure the U4I Privacy Policy is displayed
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_privacy_page(browser)


def test_privacy_policy_rate_limits(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a logged in user's ability to visit the privacy page from the home page but they are rate limited.

    GIVEN a fresh load of the U4I Home page and the user is rate limited.
    WHEN user clicks the privacy button in the footer
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    modify_navigational_link_for_rate_limit(browser, HPL.PRIVACY_BTN.lstrip("#"))
    wait_then_click_element(browser, HPL.PRIVACY_BTN, time=3)
    assert_on_429_page(browser)


@pytest.mark.parametrize("home_btn_css_selector", [HPL.U4I_LOGO, HPL.BACK_HOME_BTN])
def test_privacy_policy_return_home(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    home_btn_css_selector: str,
):
    """
    Tests a logged in user's ability to visit the privacy page and then return to home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the privacy button in the footer and then tries to go home via the buttons
    THEN ensure the home page is displayed
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_privacy_page(browser)
    wait_then_click_element(browser, home_btn_css_selector, time=3)
    assert_login(browser)


def test_terms_page(browser: WebDriver, create_test_users, provide_app: Flask):
    """
    Tests a logged in user's ability to visit the terms page from the home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the terms button in the footer
    THEN ensure the U4I Terms & Conditions are displayed
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_terms_page(browser)


def test_terms_page_rate_limits(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a logged in user's ability to visit the terms page from the home page and is rate limited.

    GIVEN a fresh load of the U4I Home page and user is rate limited
    WHEN user clicks the terms button in the footer
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    modify_navigational_link_for_rate_limit(browser, HPL.TERMS_BTN.lstrip("#"))
    wait_then_click_element(browser, HPL.TERMS_BTN)
    assert_on_429_page(browser)


@pytest.mark.parametrize("home_btn_css_selector", [HPL.U4I_LOGO, HPL.BACK_HOME_BTN])
def test_terms_return_home(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    home_btn_css_selector: str,
):
    """
    Tests a logged in user's ability to visit the terms page and then return to home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the terms button in the footer and then tries to go home via the buttons
    THEN ensure the home page is displayed
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_terms_page(browser)
    wait_then_click_element(browser, home_btn_css_selector, time=3)
    assert_login(browser)


def test_visit_contact_page(browser: WebDriver, create_test_users, provide_app: Flask):
    """
    GIVEN a logged in user
    WHEN they click on the contact us button in the footer
    THEN verify that the contact page is shown
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_contact_us_page(browser)


@pytest.mark.parametrize("home_btn_css_selector", [HPL.U4I_LOGO, HPL.BACK_HOME_BTN])
def test_visit_contact_page_return_home(
    browser: WebDriver,
    create_test_users,
    provide_app: Flask,
    home_btn_css_selector: str,
):
    """
    GIVEN a logged in user on the contact page
    WHEN they click on the buttons to return to the home page
    THEN verify that the home page is shown
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_contact_us_page(browser)
    wait_then_click_element(browser, home_btn_css_selector, time=3)
    assert_login(browser)


def test_submit_contact_form_entry(
    browser: ChromeRemoteWebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a user on the contact us page
    WHEN they submit an entry in the form
    THEN verify that the form is sent and the flash banner is shown
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_contact_us_page(browser)
    contact_form_entry(browser=browser, subject="Subject" * 2, content="Content" * 10)
    wait_then_click_element(browser, HPL.CONTACT_SUBMIT)

    wait_until_visible_css_selector(browser, HPL.CONTACT_BANNER)
    banner = browser.find_element(By.CSS_SELECTOR, HPL.CONTACT_BANNER)
    assert "Sent! Thanks for reaching out." in banner.text


@pytest.mark.parametrize(
    "contact_form_fields",
    [
        ("", "ValidContent" * 8),
        ("ValidSubject" * 2, ""),
        ("", ""),
    ],
)
def test_submit_empty_fields(
    browser: ChromeRemoteWebDriver,
    create_test_users,
    provide_app: Flask,
    contact_form_fields: tuple[str, str],
):
    """
    GIVEN a user on the contact us page
    WHEN they submit an entry in the form with an empty field
    THEN verify that proper error response is shown
    """
    subject, content = contact_form_fields
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_contact_us_page(browser)
    contact_form_entry(browser=browser, subject=subject, content=content)
    wait_then_click_element(browser, HPL.CONTACT_SUBMIT)

    # Wait for the is-invalid class to appear on the first invalid field
    empty_field_count = len([val for val in contact_form_fields if not bool(val)])

    # Wait for is-invalid class on the first empty field's input
    first_empty_selector = (
        f"{HPL.CONTACT_SUBJECT_INPUT}.is-invalid"
        if not subject
        else f"{HPL.CONTACT_CONTENT_INPUT}.is-invalid"
    )
    wait_until_visible_css_selector(browser, first_empty_selector)

    # Count visible error divs with text
    visible_error_count = 0
    if not subject:
        subject_error = browser.find_element(By.CSS_SELECTOR, HPL.CONTACT_SUBJECT_ERROR)
        assert subject_error.text != ""
        visible_error_count += 1
    if not content:
        content_error = browser.find_element(By.CSS_SELECTOR, HPL.CONTACT_CONTENT_ERROR)
        assert content_error.text != ""
        visible_error_count += 1

    assert visible_error_count == empty_field_count


def test_contact_form_button_disables_on_submit(
    browser: ChromeRemoteWebDriver,
    create_test_users,
    provide_app: Flask,
):
    """
    GIVEN a user on the contact us page
    WHEN they submit an entry in the form with an empty field
    THEN verify that proper error response is shown
    """
    app = provide_app
    user_id = 1
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)

    visit_contact_us_page(browser)
    contact_form_entry(browser=browser, subject="Subject" * 2, content="Content" * 10)
    wait_then_click_element(browser, HPL.CONTACT_SUBMIT)

    wait_until_visible_css_selector(browser, HPL.CONTACT_BANNER)
    submit_btn = browser.find_element(By.CSS_SELECTOR, HPL.CONTACT_SUBMIT)
    assert submit_btn.get_property("disabled")
