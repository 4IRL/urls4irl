# External libraries
# from webdriver_manager.chrome import ChromeDriverManager

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.utils_for_test import login_user, wait_then_get_element
from tests.functional.locators import MainPageLocators as MPL


def test_example(browser):
    """
    The one test that will always work to make me feel good
    """
    # Check if the title contains "URLS4IRL"
    assert "URLS4IRL" in browser.title


def test_login_test_user(browser, add_test_users):
    login_user(browser)

    # Confirm user logged in
    # Logout button visible
    btn_logout = wait_then_get_element(browser, MPL.BUTTON_LOGOUT)
    assert btn_logout.text == "Logout"

    # Correct user logged in
    user_logged_in = wait_then_get_element(browser, MPL.OUTPUT_LOGGED_IN_USERNAME)
    userLoggedInText = "Logged in as " + UI_TEST_STRINGS.TEST_USER_1

    assert user_logged_in.text == userLoggedInText
