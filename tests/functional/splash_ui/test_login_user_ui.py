# External libraries
from selenium.webdriver.common.by import By

# from webdriver_manager.chrome import ChromeDriverManager

# Internal libraries
from src.mocks.mock_constants import USERNAME_BASE, EMAIL_SUFFIX
import tests.functional.constants as const
from tests.functional.utils_for_test import click_and_wait, send_keys_to_input_field


def test_example(browser):
    """
    The one test that will always work to make me feel good
    """
    # Check if the title contains "URLS4IRL"
    assert "URLS4IRL" in browser.title


def test_login_test_user(browser, add_test_user):
    # Find login button to open modal
    click_and_wait(browser, ".to-login")

    # Input login details
    send_keys_to_input_field(browser, "#username", USERNAME_BASE + "1")

    send_keys_to_input_field(browser, "#password", USERNAME_BASE + "1" + EMAIL_SUFFIX)

    # Find submit button to login
    click_and_wait(browser, "#submit")

    # Confirm user logged in
    # Logout button visible
    btn_logout = browser.find_element(By.ID, "Logout")
    assert btn_logout.text == "Logout"

    # Correct user logged in
    user_logged_in = browser.find_element(By.ID, "userLoggedIn")
    userLoggedInText = "Logged in as " + const.USERNAME_TEST

    assert user_logged_in.text == userLoggedInText
