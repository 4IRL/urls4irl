# Standard library
from typing import List

# External libraries
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Internal libraries
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.locators import MainPageLocators as MPL


def get_all_attributes(driver: WebDriver, element: WebElement):
    """
    Args:
        WebDriver open to U4I
        An element on page

    Returns:
        List of attributes of element supplied
    """

    driver.execute_script(
        "var items = {};"
        + "element = arguments[0];"
        + "for (i = 0; i < element.attributes.length; ++i) { "
        + "items[element.attributes[i].name] = element.attributes[i].value;"
        + "}; "
        + "return items;",
        element,
    )


def wait_then_get_element(browser: WebDriver, css_selector: str, time: float = 2):
    """
    Streamlines waiting for single element load after user interaction.

    Args:
        WebDriver open to U4I
        A target CSS selector string
        (Optional) Time to wait, default 2s

    Returns:
        WebElement matching CSS selector criteria
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
        return None
    except TimeoutException:
        print("Timeout")
        return None


def wait_then_get_elements(browser: WebDriver, css_selector: str, time: float = 2):
    """
    Streamlines waiting for multiple elements load after user interaction.

    Args:
        WebDriver open to U4I
        A target CSS selector string
        (Optional) Time to wait, default 2s

    Returns:
        List of WebElements matching CSS selector criteria
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
        return None
    except TimeoutException:
        print("Timeout")
        return None


def wait_then_click_element(browser: WebDriver, css_selector: str, time: float = 2):
    """
    Streamlines waiting for load and clicking a single element after user interaction.

    Args:
        WebDriver open to U4I
        A target CSS selector string
        (Optional) Time to wait, default 2s

    Returns:
        Yields WebDriver
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
        return None


def clear_then_send_keys(element: WebElement, input_text: str):
    """
    Streamlines clearing an input field and sending keys provided.

    Args:
        WebElement input text field
        Text to send

    Returns:
        N/A
    """
    input_field = element
    input_field.clear()
    input_field.send_keys(input_text)


# Splash Page
def login_user(
    browser: WebDriver,
    username: str = UTS.TEST_USERNAME_1,
    password: str = UTS.TEST_PASSWORD_1,
):
    """
    Streamlines actions needed to login a user.

    Args:
        WebDriver open to U4I Splash Page
        (Optional) Username of user to login as, defaults to u4i_test1
        (Optional) Password, defaults to u4i_test1@urls4irl.app

    Returns:
        N/A
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
def select_utub_by_name(browser: WebDriver, utub_name: str):
    """
    Selects the first UTub selector matching the supplied UTub name

    Args:
        WebDriver open to U4I Home Page
        Name of UTub to be selected

    Returns:
        Boolean confirmation of UTub selection
    """

    utub_list = wait_then_get_element(browser, MPL.LIST_UTUB)

    utub_selectors = utub_list.find_elements(By.CSS_SELECTOR, "*")

    for selector in utub_selectors:
        utub_selector_name = selector.get_attribute("innerText")

        if utub_selector_name == utub_name:
            selector.click()
            return True

    return False


def login_utub(
    browser: WebDriver,
    username: str = UTS.TEST_USERNAME_1,
    password: str = UTS.TEST_PASSWORD_1,
    utub_name: str = UTS.TEST_UTUB_NAME_1,
):
    """
    Streamlines test setup actions of logging in and selecting a UTub

    Args:
        WebDriver open to U4I Splash Page
        (Optional) Username of user to login as, defaults to u4i_test1
        (Optional) Password, defaults to u4i_test1@urls4irl.app
        (Optional) Name of UTub to select, defaults to MockUTub_1

    Returns:
        Yields WebDriver to tests
    """

    login_user(browser, username, password)

    select_utub_by_name(browser, utub_name)


def get_num_utubs(browser: WebDriver):
    """
    Count number of UTub selectors

    Args:
        WebDriver open to U4I Home Page

    Returns:
        Integer length of UTub selectors available to user
    """
    utub_selectors = wait_then_get_elements(browser, MPL.SELECTORS_UTUB)
    if utub_selectors:
        return len(utub_selectors)
    else:
        return 0


def get_selected_utub_name(browser: WebDriver):
    """
    Extracts name of selected UTub.

    Args:
        WebDriver open to a selected UTub

    Returns:
        String containing the selected UTub name.
    """

    selected_utub_selector = browser.find_element(
        By.CSS_SELECTOR, MPL.SELECTOR_SELECTED_UTUB
    )

    utub_name = selected_utub_selector.get_attribute("innerText")

    return utub_name


# Members Deck
def get_selected_utub_owner_id(browser: WebDriver):
    """
    Extracts the user ID associated with the selected UTub owner.

    Args:
        WebDriver open to a selected UTub

    Returns:
        Integer user ID
    """

    owner_badge = wait_then_get_element(browser, MPL.BADGE_OWNER)
    owner_id = owner_badge.get_attribute("memberid")
    return int(owner_id)


def get_current_user_name(browser: WebDriver):
    """
    Extracts the user ID associated with the logged in user.

    Args:
        WebDriver open to the U4I Home Page

    Returns:
        String username
    """

    logged_in_user = wait_then_get_element(browser, MPL.LOGGED_IN_USERNAME_READ)
    logged_in_user_string = logged_in_user.get_attribute("innerText")
    user_name = logged_in_user_string.split("as ")

    return user_name[1]


def get_current_user_id(browser: WebDriver):
    """
    Extracts the user ID associated with the logged in user.

    Args:
        WebDriver open to the U4I Home Page

    Returns:
        Integer user ID
    """
    logged_in_user = wait_then_get_element(browser, MPL.LOGGED_IN_USERNAME_READ)

    parent_element = logged_in_user.find_element(By.XPATH, "..")

    user_id = parent_element.get_attribute("userid")

    return int(user_id)


def user_is_selected_utub_owner(browser: WebDriver):
    """
    Determines whether logged in user is the owner of the selected UTub

    Args:
        WebDriver open to a selected UTub

    Returns:
        Boolean confirmation the logged in user owns the selected UTub
    """

    return get_current_user_id(browser) == get_selected_utub_owner_id(browser)


# URL Deck
def select_url_by_title(browser: WebDriver, url_title: str):
    """
    If a UTub is selected and the UTub contains URLs, this function shall select the URL row associated with the supplied URL title.

    Args:
        WebDriver open to a selected UTub
        URL Title

    Returns:
        Boolean indicating a successful click of the indicated URL row with the provided URL title
    """

    url_rows = wait_then_get_elements(browser, MPL.ROWS_URLS)

    for url_row in url_rows:

        url_row_title = url_row.find_element(
            By.CSS_SELECTOR, MPL.URL_TITLE_READ
        ).get_attribute("innerText")
        if url_row_title == url_title:
            url_row.click()
            return True

    return False


def login_utub_url(
    browser: WebDriver,
    username: str = UTS.TEST_USERNAME_1,
    password: str = UTS.TEST_PASSWORD_1,
    utub_name: str = UTS.TEST_UTUB_NAME_1,
    url_title: str = UTS.TEST_URL_TITLE_1,
):
    """
    Streamlines test setup actions of logging in, selecting a UTub, and selecting a URL

    Args:
        WebDriver open to U4I Home Page, logged in as u4i_test1
        (Optional) Password, defaults to u4i_test1@urls4irl.app
        (Optional) Name of UTub to select
        (Optional) Title of URL to select

    Returns:
        WebElement corresponding to the url_row matching the supplied URL title
        Yields WebDriver to tests
    """

    login_utub(browser, username, password, utub_name)

    select_url_by_title(browser, url_title)


def get_num_url_rows(browser: WebDriver):
    """
    Count number of URL rows in selected UTub, regardless of filter state

    Args:
        WebDriver open to U4I Home Page with a UTub selected

    Returns:
        Integer length of URL rows in UTub
    """
    url_rows = wait_then_get_elements(browser, MPL.ROWS_URLS)
    if url_rows:
        return len(url_rows)
    else:
        return 0


def url_row_unfiltered(url_rows: List[WebElement]):
    """
    Checks if each URL row is unfiltered.

    Args:
        WebDriver open to U4I Home Page with a UTub selected. Some tag filters may be applied.

    Returns:
        List of booleans indicating whether a URL row is visible.
    """
    unfiltered = []
    for url_row in url_rows:
        unfiltered.append(url_row.get_attribute("filterable") == "true")

    return unfiltered


def get_num_url_unfiltered_rows(browser: WebDriver):
    """
    Count number of URL rows visible to user, based on filter state

    Args:
        WebDriver open to U4I Home Page with a UTub selected

    Returns:
        Integer length of visible URL rows in UTub available to user
    """
    url_rows = wait_then_get_elements(browser, MPL.ROWS_URLS)
    if url_rows:
        visible_url_rows = [
            url_row
            for url_row, condition in zip(url_rows, url_row_unfiltered(url_rows))
            if condition
        ]

        return len(visible_url_rows)
    else:
        return 0


def get_selected_url(browser: WebDriver) -> WebElement:
    """
    If a URL is selected, this function streamlines the extraction of that WebElement.

    Args:
        WebDriver open to a selected URL

    Returns:
        Yields WebDriver to tests
    """
    return browser.find_element(By.CSS_SELECTOR, MPL.ROW_SELECTED_URL)


def get_selected_url_title(browser: WebDriver):
    """
    Extracts title of selected URL.

    Args:
        WebDriver open to a selected URL

    Returns:
        String containing the selected URL title.
    """

    selected_url_row = get_selected_url(browser)

    return selected_url_row.find_element(
        By.CSS_SELECTOR, MPL.URL_TITLE_READ
    ).get_attribute("innerText")


# Tag Deck
def get_tag_filter_by_name(browser: WebDriver, tag_name: str) -> WebElement:
    """
    Simplifies extraction of a tag filter WebElement by its name.

    Args:
        WebDriver open to a selected UTub

    Returns:
        Tag filter WebElement
    """
    tag_filters = get_selected_utub_tags(browser)

    for tag_filter in tag_filters:

        tag_filter_name = tag_filter.find_element(By.TAG_NAME, "span").get_attribute(
            "innerText"
        )
        print(tag_filter_name)
        if tag_filter_name == tag_name:
            return tag_filter

    return None


def get_tag_badge_by_name(url_row: WebElement, tag_name: str) -> WebElement:
    """
    Simplifies extraction of a tag badge WebElement by its name in a selected URL.

    Args:
        WebDriver open to a selected URL

    Returns:
        Tag badge WebElement
    """
    tag_badges = get_selected_url_tags(url_row)

    for tag_badge in tag_badges:

        tag_text = tag_badge.find_element(By.CLASS_NAME, "tagText").get_attribute(
            "innerText"
        )
        if tag_text == tag_name:
            return tag_badge

    return None


def get_selected_utub_tags(browser: WebDriver):
    return wait_then_get_elements(browser, MPL.TAG_FILTERS, 0)


def get_selected_url_tags(url_row: WebElement):
    return url_row.find_elements(By.CSS_SELECTOR, MPL.TAG_BADGES)
