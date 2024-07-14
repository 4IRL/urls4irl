# Standard library

# External libraries
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.locators import MainPageLocators as MPL


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

    try:
        element = WebDriverWait(browser, time).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    css_selector,
                )
            )
        )

        return element
    except NoSuchElementException:
        return False
    except TimeoutException:
        return 0


def wait_then_get_elements(browser, css_selector: str, time: float = 2):
    """
    Streamlines waiting for UI load after interaction.
    Returns list of elements
    """

    try:
        elements = WebDriverWait(browser, time).until(
            EC.presence_of_all_elements_located(
                (
                    By.CSS_SELECTOR,
                    css_selector,
                )
            )
        )

        return elements
    except NoSuchElementException:
        return False
    except TimeoutException:
        print("Timeout")
        return 0


def wait_then_click_element(browser, css_selector: str, time: float = 2):
    """
    Streamlines waiting for UI load after interaction.
    Clicks element
    """

    try:
        element = WebDriverWait(browser, time).until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    css_selector,
                )
            )
        )

        element.click()
    except NoSuchElementException:
        return False


def clear_then_send_keys(element, input_text: str):
    """
    Sends keys for specified input into supplied input element field.
    """
    input_field = element
    input_field.clear()
    input_field.send_keys(input_text)


# Splash Page
def login_user(
    browser,
    username: str = UI_TEST_STRINGS.TEST_USERNAME_1,
    password: str = UI_TEST_STRINGS.TEST_PASSWORD_1,
):
    """
    Logs a user in using the Splash page modal. Defaults to TEST_USERNAME_1
    """

    # Find and click login button to open modal
    wait_then_click_element(browser, SPL.BUTTON_LOGIN)

    # Input login details
    username_input = wait_then_get_element(browser, SPL.INPUT_USERNAME)
    clear_then_send_keys(username_input, username)

    password_input = wait_then_get_element(browser, SPL.INPUT_PASSWORD)
    clear_then_send_keys(password_input, password)

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)


# UTub Deck
def select_utub_by_name(browser, utub_name: str):
    """
    Regardless of the current page state, this function clicks the UTub selector matching the indicated utub_name
    """

    utub_list = wait_then_get_element(browser, MPL.LIST_UTUB)

    utub_selectors = utub_list.find_elements(By.CSS_SELECTOR, "*")

    for selector in utub_selectors:
        utub_selector_name = selector.get_attribute("innerText")

        if utub_selector_name == utub_name:
            selector.click()
            return True

    return False


def get_selected_utub_name(browser):
    active_utub_selector = wait_then_get_element(browser, MPL.SELECTOR_SELECTED_UTUB)

    utub_name = active_utub_selector.get_attribute("innerText")

    return utub_name


def get_num_utubs(browser):
    utub_deck_subheader = wait_then_get_element(browser, MPL.SUBHEADER_UTUB_DECK)

    utub_deck_subheader_text = utub_deck_subheader.get_attribute("innerText")
    num_utubs = utub_deck_subheader_text.split(" UTub")[0]

    return int(num_utubs)


def get_active_utub_owner_id(browser):
    owner_badge = wait_then_get_element(browser, MPL.BADGE_OWNER)
    owner_id = owner_badge.find_element(By.TAG_NAME, "span").get_attribute("memberid")
    return int(owner_id)


def get_current_user_name(browser):
    logged_in_user = wait_then_get_element(browser, MPL.OUTPUT_LOGGED_IN_USERNAME)
    logged_in_user_string = logged_in_user.get_attribute("innerText")
    user_name = logged_in_user_string.split("as ")

    return user_name[1]


def get_current_user_id(browser):
    logged_in_user = wait_then_get_element(browser, MPL.OUTPUT_LOGGED_IN_USERNAME)

    parent_element = logged_in_user.find_element(By.XPATH, "..")

    user_id = parent_element.get_attribute("userid")

    return int(user_id)


def current_user_is_owner(browser):
    """
    Returns true if current user is the owner of the selected UTub
    """
    return get_current_user_id(browser) == get_active_utub_owner_id(browser)


def get_url_row_by_title(browser, url_title: str):
    url_rows = wait_then_get_elements(browser, MPL.ROWS_URLS)

    for url_row in url_rows:

        url_row_title = url_row.find_element(By.CLASS_NAME, "urlTitle").get_attribute(
            "innerText"
        )
        if url_row_title == url_title:
            return url_row

    return False
