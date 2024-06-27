# Standard library
import multiprocessing
from typing import Generator

# External libraries
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver

# from selenium.webdriver.chrome.options import Options

# Internal libraries
from src import create_app
from src.config import TestingConfig
import tests.user_interface.constants as const
from tests.user_interface.utils import ping_server
from tests.utils_for_test import drop_database


# Builds and runs test configuration
def run_app():
    config = TestingConfig()
    app_for_test = create_app(config)
    app_for_test.run()


# Creates a process separate from pytest to run the app in parallel
@pytest.fixture(scope="session")
def init_multiprocessing():
    multiprocessing.set_start_method("spawn")


# Manages set up and tear down of app process
@pytest.fixture(scope="session")
def parallelize_app(init_multiprocessing):
    process = multiprocessing.Process(target=run_app)
    process.start()
    yield process
    process.kill()
    process.join()


# Manages set up and tear down of app process
@pytest.fixture(scope="session")
def build_driver(parallelize_app) -> Generator[WebDriver, None, None]:
    # Uncomment below to hide UI
    # options = Options()
    # options.add_argument("--headless=new")
    # options.add_argument("–-disable-gpu")
    # driver = webdriver.Chrome(options=options)

    # Uncomment below to see UI
    driver = webdriver.Chrome()
    driver.maximize_window()
    ping_server(const.BASE_URL)

    yield driver

    # Teardown: Quit the browser after tests
    driver.quit()


# Setup fixture for the webdriver. Accesses U4I and supplies driver
@pytest.fixture
def browser(build_driver: WebDriver):
    driver = build_driver

    driver.delete_all_cookies()

    driver.get(const.BASE_URL)

    # Clear db
    # driver.get(const.CLEAR_DB_URL)
    # driver.implicitly_wait(3)

    # Load test users
    # driver.get(const.ADD_TEST_USERS_URL)
    # driver.implicitly_wait(3)

    # Return the driver object to be used in the test functions
    yield driver

    drop_database(TestingConfig())


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
