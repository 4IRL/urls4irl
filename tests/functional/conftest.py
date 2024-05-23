# Standard library
import multiprocessing

# External libraries
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import pytest

# Internal libraries
from src import create_app
from src.config import TestingConfig
import tests.functional.constants as const


def app():
    config = TestingConfig()
    app_for_test = create_app(config)
    app_for_test.run()


@pytest.fixture(scope="session")
def init_multiprocessing():
    multiprocessing.set_start_method("spawn")


@pytest.fixture(scope="session")
def run_app(init_multiprocessing):
    process = multiprocessing.Process(target=app)
    process.start()
    yield process
    process.kill()
    process.join()


# Setup fixture for the webdriver
@pytest.fixture(scope="session")
def browser(run_app):
    options = Options()
    options.add_argument("–-headless=new")
    options.add_argument("–-disable-gpu")
    driver = webdriver.Chrome(options=options)
    # driver.maximize_window()

    # Clear db
    # driver.get(const.CLEAR_DB_URL)
    # driver.implicitly_wait(3)

    # Load test users
    # driver.get(const.ADD_TEST_USERS_URL)
    # driver.implicitly_wait(3)

    # Return the driver object to be used in the test functions
    yield driver

    # Teardown: Quit the browser after tests
    driver.quit()


@pytest.fixture
def provide_browser(browser):
    yield browser
    # Reset browser here - clear cookies
    browser.get(const.BASE_URL)


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
