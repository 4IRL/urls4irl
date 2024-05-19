import pytest

from selenium.webdriver.common.by import By

# from webdriver_manager.chrome import ChromeDriverManager

import tests.functional.constants as const


# Example test case
def test_example(browser):
    # URL of the website to be tested

    # Example test: Check if the title contains "URLS4IRL"
    assert "URLS4IRL" in browser.title


def test_register_new_user(browser):
    # Load site
    browser.get(const.BASE_URL)

    # Identify and load register modal
    btn_register = browser.find_element(By.CLASS_NAME, "to-register")
    btn_register.click()

    # Input register user details
    input_field_username = browser.find_element(By.ID, "username")
    input_field_username.clear()
    input_field_username.send_keys(const.USERNAME_REGISTER)

    input_field_email = browser.find_element(By.ID, "email")
    input_field_email.clear()
    input_field_email.send_keys(const.EMAIL_REGISTER)

    input_field_email_conf = browser.find_element(By.ID, "confirmEmail")
    input_field_email_conf.clear()
    input_field_email_conf.send_keys(const.EMAIL_REGISTER)

    input_field_password = browser.find_element(By.ID, "password")
    input_field_password.clear()
    input_field_password.send_keys(const.PASSWORD_REGISTER)

    input_field_password_conf = browser.find_element(By.ID, "confirmPassword")
    input_field_password_conf.clear()
    input_field_password_conf.send_keys(const.PASSWORD_REGISTER)

    # Register
    btn_submit = browser.find_element(By.ID, "submit")
    btn_submit.click()

    validate_email_title = browser.find_element(By.CLASS_NAME, "validate-email-title")
    register_success_text = "Validate Your Email!"

    assert validate_email_title.text == register_success_text


# Example test case
@pytest.mark.skip(reason="This test is not yet implemented")
def test_login_test_user(browser):
    # Load U4I
    browser.get(const.BASE_URL)

    # Example interaction: Find an element by its tag name and check its text
    btn_login = browser.find_element(By.CLASS_NAME, "to-login")
    btn_login.click()

    # Input login details
    input_field_username = browser.find_element(By.ID, "username")
    input_field_username.clear()
    input_field_username.send_keys(const.USERNAME)

    input_field_password = browser.find_element(By.ID, "password")
    input_field_password.clear()
    input_field_password.send_keys(const.PASSWORD)

    # Confirm user logged in
    user_logged_in = browser.execute_script("return $('#userLoggedIn').text();")
    userLoggedInText = "Logged in as " + const.USERNAME

    assert user_logged_in.text == userLoggedInText
