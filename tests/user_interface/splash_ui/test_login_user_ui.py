# External libraries
from selenium.webdriver.common.by import By

# from webdriver_manager.chrome import ChromeDriverManager

# Internal libraries
import tests.user_interface.constants as const
from tests.user_interface.utils import click_and_wait, send_keys_to_input_field


# The one test that will always work to make me feel good
def test_example(browser):

    # Check if the title contains "URLS4IRL"
    assert "URLS4IRL" in browser.title


#
def test_login_test_user(browser):
    # Find login button to open modal
    click_and_wait(browser, ".to-login")

    # Input login details
    send_keys_to_input_field(browser, "#username", const.USERNAME)

    send_keys_to_input_field(browser, "#password", const.PASSWORD)

    # Find submit button to login
    click_and_wait(browser, "#submit")

    # Confirm user logged in
    # Logout button visible
    btn_logout = browser.find_element(By.ID, "Logout")
    assert btn_logout.text == "Logout"

    # Correct user logged in
    user_logged_in = browser.find_element(By.ID, "userLoggedIn")
    userLoggedInText = "Logged in as " + const.USERNAME

    assert user_logged_in.text == userLoggedInText
