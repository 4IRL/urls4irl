# Standard library
# from os import environ, path
import requests
from time import sleep

# External libraries
from selenium.webdriver.common.by import By
from sqlalchemy import create_engine, MetaData

# Internal libraries
from src import create_app
from src.config import TestingConfig
from tests.utils_for_test import drop_database


def run_app(config: TestingConfig):
    """
    Runs app
    """
    drop_database(config)
    app_for_test = create_app(config)
    app_for_test.run()


def clear_db(config: TestingConfig):
    """
    Clears rows of db, in preparation for next test
    """
    engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
    engine.connect()
    meta = MetaData(engine)
    meta.reflect()
    meta.drop_all()
    meta.create_all()


def ping_server(url: str, timeout: float = 0.5) -> bool:
    total_time = 0
    max_time = 10
    is_server_ready = False

    # Keep pinging server until status code 200 or time limit is reached
    while not is_server_ready and total_time < max_time:
        try:
            status_code = requests.get(url, timeout=timeout).status_code
        except requests.ConnectTimeout:
            sleep(timeout)
            total_time += timeout
        else:
            is_server_ready = status_code == 200

    return is_server_ready


# Streamline function for awaiting UI load after interaction
def click_and_wait(browser, css_selector: str, time: float = 2):
    button = find_element_by_css_selector(browser, css_selector)
    button.click()
    browser.implicitly_wait(time)


# Streamline function for inputting test values into input fields on site
def send_keys_to_input_field(browser, css_selector: str, input_text: str):
    input_field = find_element_by_css_selector(browser, css_selector)
    input_field.clear()
    input_field.send_keys(input_text)


# Streamlines Selenium's driver.find_element() by css selector
def find_element_by_css_selector(browser, css_selector: str):
    if css_selector[0] == "#":
        return browser.find_element(By.ID, css_selector[1:])
    elif css_selector[0] == ".":
        return browser.find_element(By.CLASS_NAME, css_selector[1:])
    else:
        return False
