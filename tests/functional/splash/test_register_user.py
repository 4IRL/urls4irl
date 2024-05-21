import pytest

from selenium.webdriver.common.by import By

# from webdriver_manager.chrome import ChromeDriverManager

import tests.functional.constants as const


# Registers a new user
@pytest.mark.skip(
    reason="This test is excluded to limit number of validation email requests"
)
def test_register_new_user(browser):
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


# Attempts to register a new user. Ensures alert is shown to user
@pytest.mark.skip(reason="This test is excluded to test another in isolation")
def test_register_existing_user(browser):
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

    alert_title = browser.find_element(By.ID, "SplashModalAlertBanner")
    alert_title_text = "An account already exists with that information but the email has not been validated."

    assert alert_title.text == alert_title_text
