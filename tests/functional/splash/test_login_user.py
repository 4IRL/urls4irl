from selenium.webdriver.common.by import By

# from webdriver_manager.chrome import ChromeDriverManager

import tests.functional.constants as const


# The one test that will always work to make me feel good
def test_example(browser):

    # Check if the title contains "URLS4IRL"
    assert "URLS4IRL" in browser.title


# Example test case
def test_login_test_user(browser):
    # Find login button to open modal
    btn_login = browser.find_element(By.CLASS_NAME, "to-login")
    btn_login.click()
    browser.implicitly_wait(10)

    # Input login details
    input_field_username = browser.find_element(By.ID, "username")
    input_field_username.clear()
    browser.implicitly_wait(2)  # Program reacts too fast, needs to take a beat
    input_field_username.send_keys(const.USERNAME)

    input_field_password = browser.find_element(By.ID, "password")
    input_field_password.clear()
    browser.implicitly_wait(2)  # Program reacts too fast, needs to take a beat
    input_field_password.send_keys(const.PASSWORD)

    # Find submit button to login
    btn_submit = browser.find_element(By.ID, "submit")
    btn_submit.click()
    browser.implicitly_wait(3)

    # Confirm user logged in
    # Logout button visible
    btn_logout = browser.find_element(By.ID, "Logout")
    assert btn_logout.text == "Logout"

    # Correct user logged in
    user_logged_in = browser.find_element(By.ID, "userLoggedIn")
    userLoggedInText = "Logged in as " + const.USERNAME

    assert user_logged_in.text == userLoggedInText
