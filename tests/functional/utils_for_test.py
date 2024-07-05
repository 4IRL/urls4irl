# Standard library
# from os import environ, path
import requests
import socket
from time import sleep
from typing import Tuple

# External libraries
from flask import Flask
from flask.testing import FlaskCliRunner
from selenium.common.exceptions import NoSuchElementException
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


def get_all_attributes(driver, element):
    driver.execute_script(
        "var items = {};"
        + "element = arguments[0];"
        + "for (i = 0; i < element.attributes.length; ++i) { "
        + "items[element.attributes[i].name] = element.attributes[i].value;"
        + "}; "
        + "return items;",
        element,
    )


def wait_then_get_element(browser, css_selector: str, time: float = 2):
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


def wait_then_get_elements(browser, css_selector: str, time: float = 2):
    """
    Streamlines waiting for UI load after interaction.
    Returns list of elements
    """

    elements = WebDriverWait(browser, time).until(
        EC.presence_of_all_elements_located(
            (
                By.CSS_SELECTOR,
                css_selector,
            )
        )
    )

    return elements


def wait_then_click_element(browser, css_selector: str, time: float = 2):
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
    return element


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
    wait_then_click_element(browser, SPL.LOGIN_OPTION_BUTTON)

    # Input login details
    login_input_field = wait_then_get_element(browser, SPL.USERNAME_INPUT)
    clear_then_send_keys(login_input_field, username)

    password_input_field = wait_then_get_element(browser, SPL.PASSWORD_INPUT)
    clear_then_send_keys(password_input_field, password)

    # Find submit button to login
    wait_then_click_element(browser, SPL.LOGIN_BUTTON)


def create_utub(browser, utub_name: str, utub_description: str):
    """
    Once logged in, this function adds new UTub by selecting the option to open the input field, fills in the fields with the specified values for utub_name and utub_description, and submits the form.
    """

    # Click createUTub button to show input
    wait_then_click_element(browser, MPL.BUTTON_UTUB_CREATE)

    # Types new UTub name
    create_utub_name_input = wait_then_get_element(browser, MPL.INPUT_UTUB_NAME_CREATE)
    clear_then_send_keys(create_utub_name_input, utub_name)

    # Types new UTub description
    create_utub_description_input = wait_then_get_element(
        browser, MPL.INPUT_UTUB_DESCRIPTION_CREATE
    )
    clear_then_send_keys(create_utub_description_input, utub_description)

    # Submits new UTub
    wait_then_click_element(browser, MPL.BUTTON_UTUB_SUBMIT_CREATE)


def delete_active_utub(browser, user_name):
    if is_owner(user_name):
        wait_then_click_element(browser, MPL.BUTTON_UTUB_DELETE)
    else:
        return False


def select_utub_by_name(browser, utub_name: str):
    """
    Regardless of the current page state, this function clicks the UTub selector matching the indicated utub_name
    """

    utub_selectors = wait_then_get_elements(browser, MPL.SELECTORS_UTUB)

    # Cycle through all
    for selector in utub_selectors:
        utub_selector_name = selector.get_attribute("innerText")
        print(utub_selector_name)

        if utub_selector_name == utub_name:
            selector.click()
            return True
        else:
            return False


def get_selected_utub_name(browser):
    active_utub_selector = wait_then_get_element(browser, MPL.SELECTOR_SELECTED_UTUB)

    utub_name = active_utub_selector.get_attribute("innerText")

    return utub_name


def leave_active_utub(browser):
    """
    Selects UTub matching the indicated utub_name, selects and confirms leaving the UTub
    """

    try:
        leave_utub_btn = browser.find_element_by_css_selector(MPL.BUTTON_UTUB_LEAVE)
    except NoSuchElementException:
        return False

    leave_utub_btn.click()

    # assert modal
    # wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)


def leave_all_utubs(browser, user_name):
    """
    Cycles through all user's UTubs and leaves them, if not owner.
    """

    UTub_selectors = wait_then_get_elements(browser, MPL.SELECTORS_UTUB)

    # Cycle through all UTubs and leave, if possible.
    for selector in UTub_selectors:
        selector.click()
        if is_owner(browser, user_name):
            continue
        else:
            leave_active_utub(browser)


def get_active_utub_owner_id(browser):
    return True


def get_current_user_id(browser):
    return True


def is_owner(browser):
    """
    Returns true if user is the owner of the selected UTub
    """
    return get_current_user_id(browser) == get_active_utub_owner_id(browser)
