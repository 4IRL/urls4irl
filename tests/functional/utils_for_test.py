# Standard library
# from os import environ, path
import requests
from time import sleep
from typing import Tuple

# External libraries
from flask import Flask
from flask.testing import FlaskCliRunner
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Internal libraries
from src import create_app
from src.config import TestingConfig
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS


def run_app():
    """
    Runs app
    """
    config = TestingConfig()
    app_for_test = create_app(config)
    app_for_test.run(debug=False)


def clear_db(runner: Tuple[Flask, FlaskCliRunner]):
    # Clear db
    _, cli_runner = runner
    cli_runner.invoke(args=["managedb", "clear", "test"])
    print("db cleared")


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
def wait_then_get_element(
    browser, css_selector: str, click: bool = False, time: float = 10
):
    """
    Streamlines waiting for UI load after interaction.
    Returns element by default; clicks if `click` bool = True
    """
    element = WebDriverWait(browser, time).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
    )
    if click:
        element.click()
    else:
        return element


# Streamline function for inputting test values into input fields on site
def clear_then_send_keys(element, input_text: str):
    """
    Sends keys for specified input into supplied input element field.
    """
    input_field = element
    input_field.clear()
    input_field.send_keys(input_text)


def login_user(
    browser,
    username: str = UI_TEST_STRINGS.TEST_USER_1,
    password: str = UI_TEST_STRINGS.TEST_PASSWORD_1,
):

    # Find and click login button to open modal
    wait_then_get_element(browser, ".to-login", True)

    # Input login details
    login_input_field = wait_then_get_element(browser, "#username")
    clear_then_send_keys(login_input_field, username)

    password_input_field = wait_then_get_element(browser, "#password")
    clear_then_send_keys(password_input_field, password)

    # Find submit button to login
    wait_then_get_element(browser, "#submit", True)


# Adds new UTub
def add_utub(browser, utub_name: str):

    # Click createUTub button to show input
    wait_then_get_element(browser, "#createUTubBtn", True)

    # Types new UTub name
    create_utub_input = wait_then_get_element(browser, "#createUTub")
    clear_then_send_keys(create_utub_input, utub_name)

    # Submits new UTub
    wait_then_get_element(browser, "#submitCreateUTub", True, 2)
