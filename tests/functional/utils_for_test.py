# Standard library
# from os import environ, path
import requests
import socket
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
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.locators import MainPageLocators as MPL


def run_app(port: int):
    """
    Runs app
    """
    config = TestingConfig()
    app_for_test = create_app(config)
    app_for_test.run(debug=False, port=port)


def clear_db(runner: Tuple[Flask, FlaskCliRunner]):
    # Clear db
    _, cli_runner = runner
    cli_runner.invoke(args=["managedb", "clear", "test"])
    print("db cleared")


def find_open_port(start_port: int = 1024, end_port: int = 65535) -> int:
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No available port found in the specified range.")


def ping_server(url: str, timeout: float = 2) -> bool:
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


def wait_then_get_element(browser, css_selector: str, time: float = 10):
    """
    Streamlines waiting for UI load after interaction.
    Returns element
    """

    element = WebDriverWait(browser, time).until(
        EC.presence_of_element_located(
            (
                By.CSS_SELECTOR,
                css_selector,
            )
        )
    )

    return element


def wait_then_click_element(browser, css_selector: str, time: float = 10):
    """
    Streamlines waiting for UI load after interaction.
    Clicks element
    """

    element = WebDriverWait(browser, time).until(
        EC.element_to_be_clickable(
            (
                By.CSS_SELECTOR,
                css_selector,
            )
        )
    )

    element.click()


def clear_then_send_keys(element, input_text: str):
    """
    Sends keys for specified input into supplied input element field.
    """
    input_field = element
    input_field.clear()
    input_field.send_keys(input_text)


# Logs a user in using the Splash page modal. Defaults to TEST_USER_1
def login_user(
    browser,
    username: str = UI_TEST_STRINGS.TEST_USER_1,
    password: str = UI_TEST_STRINGS.TEST_PASSWORD_1,
):

    # Find and click login button to open modal
    wait_then_get_element(browser, SPL.LOGIN_OPTION_BUTTON).click()

    # Input login details
    login_input_field = wait_then_get_element(browser, SPL.USERNAME_INPUT)
    clear_then_send_keys(login_input_field, username)

    password_input_field = wait_then_get_element(browser, SPL.PASSWORD_INPUT)
    clear_then_send_keys(password_input_field, password)

    # Find submit button to login
    wait_then_get_element(browser, SPL.LOGIN_BUTTON).click()


def add_utub(browser, utub_name: str):
    """
    Once logged in, this function adds new UTub, awaits its creation, then selects to make active
    """

    # Click createUTub button to show input
    wait_then_get_element(browser, MPL.CREATE_UTUB_BUTTON, 2).click()

    # Types new UTub name
    create_utub_input = wait_then_get_element(browser, MPL.CREATE_UTUB_INPUT)
    clear_then_send_keys(create_utub_input, utub_name)

    # Submits new UTub
    wait_then_get_element(browser, MPL.SUBMIT_UTUB_INPUT).click()

    selector_UTub = wait_then_click_element(browser, MPL.SELECTED_UTUB_SELECTOR)

    return selector_UTub


# Regardless of the current page state, this function clicks the UTub selector matching the indicated utub_name
def select_utub(browser, utub_name: str):

    wait_then_get_element(
        browser,
    )
