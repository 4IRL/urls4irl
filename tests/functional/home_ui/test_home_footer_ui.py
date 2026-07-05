from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_login,
    assert_on_429_page,
)
from tests.functional.playwright_utils import (
    click_on_navbar,
    contact_form_entry,
    login_user_to_home_page,
    modify_navigational_link_for_rate_limit,
    visit_contact_us_page,
    visit_privacy_page,
    visit_terms_page,
    wait_then_click_element,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.home_ui


def test_privacy_policy(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a logged in user's ability to visit the privacy page from the home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the privacy button in the footer
    THEN ensure the U4I Privacy Policy is displayed
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_privacy_page(page=page)


def test_privacy_policy_rate_limits(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a logged in user's ability to visit the privacy page from the home page but they are rate limited.

    GIVEN a fresh load of the U4I Home page and the user is rate limited.
    WHEN user clicks the privacy button in the footer
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    modify_navigational_link_for_rate_limit(
        page=page, element_id=HPL.PRIVACY_BTN.lstrip("#")
    )
    wait_then_click_element(page=page, css_selector=HPL.PRIVACY_BTN)
    assert_on_429_page(page=page)


@pytest.mark.parametrize("home_btn_css_selector", [HPL.U4I_LOGO, HPL.BACK_HOME_BTN])
def test_privacy_policy_return_home(
    page: Page,
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
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_privacy_page(page=page)
    # The back-home button now lives inside the always-collapsed navbar
    # dropdown; the wordmark logo stays inline. Open the hamburger first when
    # the target is the dropdown button.
    if home_btn_css_selector == HPL.BACK_HOME_BTN:
        click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=home_btn_css_selector)
    assert_login(page=page)


def test_terms_page(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a logged in user's ability to visit the terms page from the home page.

    GIVEN a fresh load of the U4I Home page
    WHEN user clicks the terms button in the footer
    THEN ensure the U4I Terms & Conditions are displayed
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_terms_page(page=page)


def test_terms_page_rate_limits(page: Page, create_test_users, provide_app: Flask):
    """
    Tests a logged in user's ability to visit the terms page from the home page and is rate limited.

    GIVEN a fresh load of the U4I Home page and user is rate limited
    WHEN user clicks the terms button in the footer
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    modify_navigational_link_for_rate_limit(
        page=page, element_id=HPL.TERMS_BTN.lstrip("#")
    )
    wait_then_click_element(page=page, css_selector=HPL.TERMS_BTN)
    assert_on_429_page(page=page)


@pytest.mark.parametrize("home_btn_css_selector", [HPL.U4I_LOGO, HPL.BACK_HOME_BTN])
def test_terms_return_home(
    page: Page,
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
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_terms_page(page=page)
    # The back-home button now lives inside the always-collapsed navbar
    # dropdown; the wordmark logo stays inline. Open the hamburger first when
    # the target is the dropdown button.
    if home_btn_css_selector == HPL.BACK_HOME_BTN:
        click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=home_btn_css_selector)
    assert_login(page=page)


def test_visit_contact_page(page: Page, create_test_users, provide_app: Flask):
    """
    GIVEN a logged in user
    WHEN they click on the contact us button in the footer
    THEN verify that the contact page is shown
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_contact_us_page(page=page)


@pytest.mark.parametrize("home_btn_css_selector", [HPL.U4I_LOGO, HPL.BACK_HOME_BTN])
def test_visit_contact_page_return_home(
    page: Page,
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
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_contact_us_page(page=page)
    # The back-home button now lives inside the always-collapsed navbar
    # dropdown; the wordmark logo stays inline. Open the hamburger first when
    # the target is the dropdown button.
    if home_btn_css_selector == HPL.BACK_HOME_BTN:
        click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=home_btn_css_selector)
    assert_login(page=page)


def test_submit_contact_form_entry(page: Page, create_test_users, provide_app: Flask):
    """
    GIVEN a user on the contact us page
    WHEN they submit an entry in the form
    THEN verify that the form is sent and the flash banner is shown
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_contact_us_page(page=page)
    contact_form_entry(page=page, subject="Subject" * 2, content="Content" * 10)
    wait_then_click_element(page=page, css_selector=HPL.CONTACT_SUBMIT)

    wait_until_visible_css_selector(page=page, css_selector=HPL.CONTACT_BANNER)
    banner = page.locator(HPL.CONTACT_BANNER).first
    expect(banner).to_contain_text("Sent! Thanks for reaching out.")


@pytest.mark.parametrize(
    "contact_form_fields",
    [
        ("", "ValidContent" * 8),
        ("ValidSubject" * 2, ""),
        ("", ""),
    ],
)
def test_submit_empty_fields(
    page: Page,
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
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_contact_us_page(page=page)
    contact_form_entry(page=page, subject=subject, content=content)
    wait_then_click_element(page=page, css_selector=HPL.CONTACT_SUBMIT)

    # Wait for the is-invalid class to appear on the first invalid field
    empty_field_count = len([val for val in contact_form_fields if not bool(val)])

    # Wait for is-invalid class on the first empty field's input
    first_empty_selector = (
        f"{HPL.CONTACT_SUBJECT_INPUT}.is-invalid"
        if not subject
        else f"{HPL.CONTACT_CONTENT_INPUT}.is-invalid"
    )
    wait_until_visible_css_selector(page=page, css_selector=first_empty_selector)

    # Count visible error divs with text
    visible_error_count = 0
    if not subject:
        subject_error = page.locator(HPL.CONTACT_SUBJECT_ERROR).first
        expect(subject_error).not_to_have_text("")
        visible_error_count += 1
    if not content:
        content_error = page.locator(HPL.CONTACT_CONTENT_ERROR).first
        expect(content_error).not_to_have_text("")
        visible_error_count += 1

    assert visible_error_count == empty_field_count


def test_contact_form_button_disables_on_submit(
    page: Page,
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
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    visit_contact_us_page(page=page)
    contact_form_entry(page=page, subject="Subject" * 2, content="Content" * 10)
    wait_then_click_element(page=page, css_selector=HPL.CONTACT_SUBMIT)

    wait_until_visible_css_selector(page=page, css_selector=HPL.CONTACT_BANNER)
    expect(page.locator(HPL.CONTACT_SUBMIT)).to_be_disabled()
