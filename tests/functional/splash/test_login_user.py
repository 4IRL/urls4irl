# External libraries
import pytest
from selenium.webdriver.common.by import By

# from webdriver_manager.chrome import ChromeDriverManager

# Internal libraries
import tests.functional.constants as const


# The one test that will always work to make me feel good
def test_example(browser):

    # Check if the title contains "URLS4IRL"
    assert "URLS4IRL" in browser.title


# The one test that will always work to make me feel good
def test_example1(browser):

    # Check if the title contains "URLS4IRL"
    assert "URLS4IRL" in browser.title


# The one test that will always work to make me feel good
def test_example2(browser):

    # Check if the title contains "URLS4IRL"
    assert "URLS4IRL" in browser.title


# Example test case
@pytest.mark.skip(reason="no way of currently testing this")
def test_login_test_user(browser):
    # Find login button to open modal
    login_btn = browser.find_element(By.CLASS_NAME, "to-login")
    login_btn.click()
    browser.implicitly_wait(10)

    # Input login details
    username_input = browser.find_element(By.ID, "username")
    username_input.clear()
    browser.implicitly_wait(2)  # Program reacts too fast, needs to take a beat
    username_input.send_keys(const.USERNAME)

    password_input = browser.find_element(By.ID, "password")
    password_input.clear()
    browser.implicitly_wait(2)  # Program reacts too fast, needs to take a beat
    password_input.send_keys(const.PASSWORD)

    # Find submit button to login
    submit_btn = browser.find_element(By.ID, "submit")
    submit_btn.click()
    browser.implicitly_wait(3)

    # Confirm user logged in
    # Logout button visible
    btn_logout = browser.find_element(By.ID, "Logout")
    assert btn_logout.text == "Logout"

    # Correct user logged in
    user_logged_in = browser.find_element(By.ID, "userLoggedIn")
    userLoggedInText = "Logged in as " + const.USERNAME

    assert user_logged_in.text == userLoggedInText
