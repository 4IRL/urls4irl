import pytest

from selenium import webdriver

import tests.functional.constants as const


# Setup fixture for the webdriver
@pytest.fixture(scope="session")
def browser():
    driver = webdriver.Chrome()
    driver.maximize_window()

    # Clear db
    # driver.get(const.CLEAR_DB_URL)
    # driver.implicitly_wait(3)

    # If title contains "*Cloudflare", click button first
    # Find element containing ".AuthBoxRow--name" containing "Rehan"
    # Trickle up "closest() in jQuery" to <a>.Button.click()
    # driver.implicitly_wait(10)

    # Load test users
    # driver.get(const.ADD_TEST_USERS_URL)
    # driver.implicitly_wait(3)

    # Load U4I site
    driver.get(const.BASE_URL)

    # Return the driver object to be used in the test functions
    yield driver

    # Teardown: Quit the browser after tests
    driver.quit()


# This fixture is not yet implemented because I can't figure out how to start each test independently. Currently the implementation of each subsequent test is dependent on the success of its predecessors
# Logs in newly created user
# @pytest.fixture
# def login(browser):
#     # Load U4I
#     browser.get(const.BASE_URL)

#     # Example interaction: Find an element by its tag name and check its text
#     btn_login = browser.find_element(By.CLASS_NAME, "to-login")
#     btn_login.click()

#     # Input login details
#     input_field_username = browser.find_element(By.ID, "username")
#     input_field_username.clear()
#     input_field_username.send_keys(const.USERNAME)

#     input_field_password = browser.find_element(By.ID, "password")
#     input_field_password.clear()
#     input_field_password.send_keys(const.PASSWORD)
