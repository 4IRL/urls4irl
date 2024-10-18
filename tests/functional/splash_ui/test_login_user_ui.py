# External libraries
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.utils_for_test import login_user, wait_then_get_element
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.locators import SplashPageLocators as SPL


def test_example(browser: WebDriver):
    """
    The one test that will always work to make me feel good
    """
    # Check if the title contains "URLS4IRL"
    assert "URLS4IRL" in browser.title


def test_login_modal_center_btn(browser: WebDriver):
    """
    Tests a user's ability to open the Login modal using the center button.

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the center login button
    THEN ensure the modal opens
    """

    # Find and click login button to open modal
    login_btn = wait_then_get_element(browser, SPL.BUTTON_LOGIN)
    login_btn.click()

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)

    assert modal_element.is_displayed()

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Login!"


def test_login_modal_RHS_btn(browser: WebDriver):
    """
    Tests a user's ability to open the Login modal using the RHS corner button

    GIVEN a fresh load of the U4I Splash page
    WHEN user clicks the RHS login button
    THEN ensure the modal opens
    """

    # Find and click login button to open modal
    navbar = wait_then_get_element(browser, SPL.SPLASH_NAVBAR)

    login_btn = navbar.find_element(By.CSS_SELECTOR, SPL.BUTTON_LOGIN)
    login_btn.click()

    modal_element = wait_then_get_element(browser, SPL.SPLASH_MODAL)

    assert modal_element.is_displayed()

    modal_title = modal_element.find_element(By.CLASS_NAME, "modal-title")

    assert modal_title.text == "Login!"


def test_login_test_user(browser: WebDriver, create_test_users):
    """
    Tests a user's ability to login using the splash page login modal

    GIVEN a fresh load of the U4I Splash page and validated user
    WHEN user initiates login sequence
    THEN U4I will login user and display the home page
    """

    login_user(browser)

    # Confirm user logged in
    # Logout button visible
    btn_logout = wait_then_get_element(browser, MPL.BUTTON_LOGOUT)
    assert btn_logout.text == "Logout"

    # Correct user logged in
    user_logged_in = wait_then_get_element(browser, MPL.LOGGED_IN_USERNAME_READ)
    userLoggedInText = "Logged in as " + UI_TEST_STRINGS.TEST_USERNAME_1

    assert user_logged_in.text == userLoggedInText
