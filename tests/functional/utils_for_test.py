# Standard library
import secrets
from time import sleep

# External libraries
from flask import Flask, session
from flask.testing import FlaskCliRunner
import pytest
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# Internal libraries
from src.models.users import Users
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as MP


# General
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


def wait_then_get_element(
    browser: WebDriver, css_selector: str, time: float = 2
) -> WebElement | None:
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
        wait = WebDriverWait(browser, time)
        element = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, css_selector))
        )

        return element
    except ElementNotInteractableException:
        return None
    except NoSuchElementException:
        return None
    except TimeoutException:
        return None
    except StaleElementReferenceException:
        return None


def wait_then_get_elements(
    browser: WebDriver, css_selector: str, time: float = 2
) -> list[WebElement]:
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
            EC.visibility_of_all_elements_located(
                (
                    By.CSS_SELECTOR,
                    css_selector,
                )
            )
        )

        return elements
    except ElementNotInteractableException:
        return []
    except NoSuchElementException:
        return []
    except TimeoutException:
        return []


def wait_then_click_element(
    browser: WebDriver, css_selector: str, time: float = 2
) -> WebElement | None:
    """
    Streamlines waiting for load and clicking a single element after user interaction.
    Uses CSS Selector to locate element.

    Args:
        WebDriver open to U4I
        A target CSS selector string
        (Optional) Time to wait, default 2s

    Returns:
        Returns clicked WebElement
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
        return element
    except NoSuchElementException:
        return None


def wait_for_web_element_and_click(browser: WebDriver, element: WebElement, timeout=10):
    """
    Waits for an already located WebElement to be clickable and clicks it.

    Args:
        driver: The WebDriver instance.
        element: The WebElement that you want to click.
        timeout: The maximum number of seconds to wait for the element to become clickable.

    Returns:
        None
    """
    WebDriverWait(browser, timeout).until(
        lambda _: element.is_enabled() and element.is_displayed()
    )
    element.click()


def wait_for_element_to_be_removed(
    browser: WebDriver, elem: WebElement, timeout=10
) -> bool:
    """
    Waits for an element to be removed from the DOM after an animation completes.

    Args:
        browser (WebDriver): The Selenium WebDriver instance.
        elem (WebElement): The element to check if removed
        timeout (int): Maximum time to wait (in seconds).

    Returns:
        (bool): True if the element is removed within the timeout period, False otherwise
    """
    try:
        WebDriverWait(browser, timeout).until(EC.staleness_of(elem))
        return True
    except (TimeoutException, NoSuchElementException):
        return False


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


def wait_until_hidden(
    browser: WebDriver, css_selector: str, timeout: int = 2
) -> WebElement:
    element = browser.find_element(By.CSS_SELECTOR, css_selector)

    wait = WebDriverWait(browser, timeout)
    wait.until(lambda _: not element.is_displayed())

    return element


def wait_until_all_hidden(browser: WebDriver, css_selector: str, timeout: int = 2):
    wait = WebDriverWait(browser, timeout)
    wait.until_not(
        EC.visibility_of_all_elements_located((By.CSS_SELECTOR, css_selector))
    )


def wait_until_visible(browser: WebDriver, element: WebElement, timeout: int = 2):
    wait = WebDriverWait(browser, timeout)
    wait.until(lambda _: element.is_displayed())

    return element


def wait_until_visible_css_selector(
    browser: WebDriver, css_selector: str, timeout: int = 10
):
    wait = WebDriverWait(browser, timeout)
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, css_selector)))


def assert_not_visible_css_selector(
    browser: WebDriver, css_selector: str, time: float = 10
):
    try:
        WebDriverWait(browser, time).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        assert True
    except TimeoutException:
        assert False


def assert_on_404_page(browser: WebDriver):
    error_header = wait_then_get_element(browser, css_selector="h2", time=3)
    assert error_header is not None
    assert error_header.text == IDENTIFIERS.HTML_404
    assert "Invalid Request - URLS4IRL" == browser.title


# Modal
def dismiss_modal_with_click_out(browser: WebDriver):
    action = ActionChains(browser)
    modal_element = wait_then_get_element(browser, MP.ELEMENT_MODAL)
    assert modal_element is not None
    width = modal_element.rect["width"]
    height = modal_element.rect["height"]
    offset = 15
    action.move_to_element_with_offset(
        modal_element, -width / 2 + offset, -height / 2 + offset
    )
    action.click()
    action.perform()


# Splash Page
def create_user_session_and_provide_session_id(app: Flask, user_id: int) -> str:
    """
    Manually creates a user session to allow user to be logged in
    without needing UI interaction.

    Args:
        app (Flask): The Flask application is necessary to generate a request context in order to insert the session into the appropriate session engine
        user_id (int): The user ID wanting to be logged in as

    Returns:
        (str): The session ID of the user that can be used to log the user in
    """
    random_sid = _create_random_sid()
    with app.test_request_context("/"):
        user: Users = Users.query.get(user_id)
        session["_user_id"] = user.get_id()
        session["_fresh"] = True
        session["_id"] = _create_random_identifier()
        session.sid = random_sid
        session.modified = True

        app.session_interface.save_session(
            app, session, response=app.make_response("Testing")
        )
    return random_sid


def _create_random_identifier() -> str:
    return secrets.token_hex(64)


def _create_random_sid() -> str:
    return secrets.token_urlsafe(32)


def login_user_with_cookie_from_session(browser: WebDriver, session_id: str):
    cookie = {
        "name": "session",
        "value": session_id,
        "path": "/",
        "httpOnly": True,
    }

    browser.add_cookie(cookie)

    # Refresh to redirect user to their home page since they're logged in
    browser.refresh()


def login_user_to_home_page(app: Flask, browser: WebDriver, user_id: int):
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)


def login_user_and_select_utub_by_utubid(
    app: Flask, browser: WebDriver, user_id: int, utub_id: int
):
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)
    browser.get_screenshot_as_file("p1.png")
    wait_then_click_element(
        browser, f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']", time=10
    )


def login_user_and_select_utub_by_name(
    app: Flask, browser: WebDriver, user_id: int, utub_name: str
):
    session_id = create_user_session_and_provide_session_id(app, user_id)
    login_user_with_cookie_from_session(browser, session_id)
    select_utub_by_name(browser, utub_name)


def login_user_select_utub_by_name_and_url_by_title(
    app: Flask, browser: WebDriver, user_id: int, utub_name: str, url_title: str
):
    login_user_and_select_utub_by_name(app, browser, user_id, utub_name)
    select_url_by_title(browser, url_title)


def login_user_select_utub_by_name_and_url_by_string(
    app: Flask, browser: WebDriver, user_id: int, utub_name: str, url_string: str
):
    login_user_and_select_utub_by_name(app, browser, user_id, utub_name)
    select_url_by_url_string(browser, url_string)


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
    assert username_input is not None
    clear_then_send_keys(username_input, username)

    password_input = wait_then_get_element(browser, SPL.INPUT_PASSWORD)
    assert password_input is not None
    clear_then_send_keys(password_input, password)

    return password_input


def assert_login(browser: WebDriver):
    """
    Streamlines actions needed to confirm a user is logged in.

    Args:
        WebDriver open to U4I Home Page
    """

    # Confirm user logged in
    # Logout button visible
    btn_logout = wait_then_get_element(browser, HPL.BUTTON_LOGOUT)
    assert btn_logout is not None
    assert btn_logout.text == "Logout"

    # Correct user logged in
    user_logged_in = wait_then_get_element(browser, HPL.LOGGED_IN_USERNAME_READ)
    assert user_logged_in is not None
    userLoggedInText = "Logged in as " + UTS.TEST_USERNAME_1

    assert user_logged_in.text == userLoggedInText


def assert_login_with_username(browser: WebDriver, username: str):
    """
    Streamlines actions needed to confirm a user is logged in.

    Args:
        WebDriver open to U4I Home Page
    """

    # Confirm user logged in
    # Logout button visible
    btn_logout = wait_then_get_element(browser, HPL.BUTTON_LOGOUT)
    assert btn_logout is not None
    assert btn_logout.text == "Logout"

    # Correct user logged in
    user_logged_in = wait_then_get_element(browser, HPL.LOGGED_IN_USERNAME_READ)
    assert user_logged_in is not None
    userLoggedInText = "Logged in as " + username

    assert user_logged_in.text == userLoggedInText


# UTub Deck
def select_utub_by_name(browser: WebDriver, utub_name: str):
    """
    Selects the first UTub selector matching the supplied UTub name

    Args:
        WebDriver open to U4I Home Page
        Name of UTub to be selected
    """

    utub_selectors = wait_then_get_elements(browser, HPL.SELECTORS_UTUB)
    assert utub_selectors

    for selector in utub_selectors:
        utub_name_elem = selector.find_element(By.CSS_SELECTOR, HPL.SELECTORS_UTUB_NAME)

        if utub_name_elem.text == utub_name:
            selector.click()
            wait_until_utub_name_appears(browser, utub_name)
            return


def wait_until_utub_name_appears(browser: WebDriver, utub_name: str):
    utub_name_deck_header = wait_then_get_element(browser, HPL.HEADER_URL_DECK, time=10)
    assert utub_name_deck_header is not None
    if utub_name_deck_header.text != utub_name:
        WebDriverWait(browser, 10).until(
            lambda _: utub_name_deck_header.text == utub_name
        )


def wait_until_update_btn_has_hidden_class(browser: WebDriver, btn_css_selector: str):
    btn = browser.find_element(By.CSS_SELECTOR, btn_css_selector)
    WebDriverWait(browser, 10).until(
        lambda _: HPL.HIDDEN_BTN_CLASS in btn.get_dom_attribute("class")
    )


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

    # Find submit button to login
    wait_then_click_element(browser, SPL.BUTTON_SUBMIT)

    sleep(3)

    select_utub_by_name(browser, utub_name)


def get_num_utubs(browser: WebDriver) -> int:
    """
    Count number of UTub selectors

    Args:
        WebDriver open to U4I Home Page

    Returns:
        Integer length of UTub selectors available to user
    """
    utub_selectors = wait_then_get_elements(browser, HPL.SELECTORS_UTUB)
    if utub_selectors:
        return len(utub_selectors)
    return 0


def get_all_utub_selector_names(browser: WebDriver) -> list[str]:
    """
    Find all UTub selectors the current user has access to.

    Args:
        WebDriver open to U4I Home Page

    Returns:
        Array of strings corresponding to UTub selectors available to user
    """
    utub_selectors = wait_then_get_elements(browser, HPL.SELECTORS_UTUB)

    utub_names = []
    if utub_selectors:
        for utub_selector in utub_selectors:
            utub_names.append(utub_selector.text)
    return utub_names


def get_selected_utub_name(browser: WebDriver) -> str:
    """
    Extracts name of selected UTub.

    Args:
        WebDriver open to a selected UTub

    Returns:
        String containing the selected UTub name.
    """

    selected_utub_selector = browser.find_element(
        By.CSS_SELECTOR, HPL.SELECTOR_SELECTED_UTUB
    )

    return selected_utub_selector.text


# Members Deck
def get_selected_utub_owner_id(browser: WebDriver):
    """
    Extracts the user ID associated with the selected UTub owner.

    Args:
        WebDriver open to a selected UTub

    Returns:
        Integer user ID
    """

    owner_badge = wait_then_get_element(browser, HPL.BADGE_OWNER)
    assert owner_badge is not None

    owner_id = owner_badge.get_attribute("memberid")
    assert owner_id is not None
    assert isinstance(owner_id, str)
    return int(owner_id)


def get_current_user_name(browser: WebDriver) -> str:
    """
    Extracts the user ID associated with the logged in user.

    Args:
        WebDriver open to the U4I Home Page

    Returns:
        String username
    """

    logged_in_user = wait_then_get_element(browser, HPL.LOGGED_IN_USERNAME_READ)
    assert logged_in_user is not None
    logged_in_user_string = logged_in_user.get_attribute("innerText")
    assert logged_in_user_string is not None
    assert isinstance(logged_in_user_string, str)
    user_name = logged_in_user_string.split("as ")

    return user_name[1]


def get_current_user_id(browser: WebDriver) -> int:
    """
    Extracts the user ID associated with the logged in user.

    Args:
        WebDriver open to the U4I Home Page

    Returns:
        Integer user ID
    """
    logged_in_user = wait_then_get_element(browser, HPL.LOGGED_IN_USERNAME_READ)
    assert logged_in_user is not None

    parent_element = logged_in_user.find_element(By.XPATH, "..")
    assert parent_element is not None

    user_id = parent_element.get_attribute("userid")
    assert user_id is not None
    assert isinstance(user_id, str)

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
def get_url_by_title(browser: WebDriver, url_title: str) -> WebElement | None:
    """
    If a UTub is selected and the UTub contains URLs, this function shall return the URL row associated with the supplied URL title.

    Args:
        WebDriver open to a selected UTub
        URL Title

    Returns:
        URL row with the provided URL title
    """

    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)
    if url_rows is None:
        return None

    for url_row in url_rows:

        url_row_title = url_row.find_element(
            By.CSS_SELECTOR, HPL.URL_TITLE_READ
        ).get_attribute("innerText")
        if url_row_title == url_title:
            return url_row

    return None


def select_url_by_title(browser: WebDriver, url_title: str):
    """
    If a UTub is selected and the UTub contains URLs, this function shall select the URL row associated with the supplied URL title.

    Args:
        WebDriver open to a selected UTub
        URL Title
    """

    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)
    assert url_rows

    for url_row in url_rows:

        url_row_title = url_row.find_element(
            By.CSS_SELECTOR, HPL.URL_TITLE_READ
        ).get_attribute("innerText")
        if url_row_title == url_title:
            url_row.click()
            return


def select_url_by_url_string(browser: WebDriver, url_string: str):
    """
    If a UTub is selected and the UTub contains URLs, this function shall select the URL row associated with the supplied URL url string.

    Args:
        WebDriver open to a selected UTub
        URL String

    Returns:
        Boolean indicating a successful click of the indicated URL row with the provided URL title
    """

    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)
    assert url_rows

    for url_row in url_rows:

        url_row_string = url_row.find_element(
            By.CSS_SELECTOR, HPL.URL_STRING_READ
        ).get_attribute("data-url")
        if url_row_string == url_string:
            url_row.click()
            return


def verify_elem_with_url_string_exists(browser: WebDriver, url_string: str) -> bool:
    """
    If a UTub is selected and the UTub contains URLs, find a URL containing a given string.

    Args:
        browser (WebDriver): The browser driver open to a selected UTub
        url_string (str): URL String

    Returns:
        (bool): True if element exists, False otherwise

    """
    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)
    if url_rows is None:
        return False

    for url_row in url_rows:
        url_row_string = url_row.find_element(
            By.CSS_SELECTOR, HPL.URL_STRING_READ
        ).get_attribute("data-url")

        if url_row_string == url_string:
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
    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)
    if url_rows:
        return len(url_rows)
    return 0


def get_all_url_ids_in_selected_utub(browser: WebDriver) -> list[int]:
    """
    Find all URL IDs in the active UTub.

    Args:
        WebDriver open to U4I Home Page and active UTub selected.

    Returns:
        Array of ints corresponding to URL IDs in the UTub
    """

    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)

    url_ids = []
    if url_rows:
        for row in url_rows:
            url_id = row.get_attribute("urlid")
            assert url_id is not None
            assert isinstance(url_id, str) and url_id.isdecimal()
            url_ids.append(int(url_id))

    return url_ids


def get_all_tag_ids_in_url_row(url_row: WebElement) -> list[int] | None:
    tag_badges: list[WebElement] = url_row.find_elements(
        By.CSS_SELECTOR, HPL.TAG_BADGES
    )
    if tag_badges:
        tag_ids = [
            int(tag_badge.get_attribute("data-utub-tag-id")) for tag_badge in tag_badges
        ]
        return tag_ids
    return None


def url_row_unfiltered(url_rows: list[WebElement]):
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
    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)

    if url_rows:
        visible_url_rows = [
            url_row
            for url_row, condition in zip(url_rows, url_row_unfiltered(url_rows))
            if condition
        ]

        return len(visible_url_rows)
    return 0


def get_selected_url(browser: WebDriver) -> WebElement:
    """
    If a URL is selected, this function streamlines the extraction of that WebElement.

    Args:
        WebDriver open to a selected URL

    Returns:
        Yields WebDriver to tests
    """
    selected_url = wait_then_get_element(browser, HPL.ROW_SELECTED_URL, time=3)
    assert selected_url is not None
    return selected_url


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
        By.CSS_SELECTOR, HPL.URL_TITLE_READ
    ).get_attribute("innerText")


def get_url_row_by_id(browser: WebDriver, urlid: int):
    return browser.find_element(By.CSS_SELECTOR, HPL.ROWS_URLS + f'[urlid="{urlid}"]')


def get_tag_badge_by_id(browser: WebDriver, urlid: int, tagid: int):
    url_row = get_url_row_by_id(browser, urlid)
    return url_row.find_element(
        By.CSS_SELECTOR, HPL.TAG_BADGES + f'[data-utub-tag-id="{tagid}"]'
    )


def get_tag_badge_by_name(url_row: WebElement, tag_name: str) -> WebElement | None:
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


def add_mock_urls(runner: FlaskCliRunner, urls: list[str]):
    args = (
        ["addmock", "url"]
        + urls
        + [
            "--no-dupes",
        ]
    )
    runner.invoke(args=args)


def verify_update_url_state_is_shown(url_row: WebElement):
    hidden_btns = (
        HPL.BUTTON_URL_DELETE,
        HPL.BUTTON_TAG_CREATE,
        HPL.BUTTON_URL_ACCESS,
    )

    for btn in hidden_btns:
        assert not url_row.find_element(By.CSS_SELECTOR, btn).is_displayed()

    with pytest.raises(NoSuchElementException):
        url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_STRING_UPDATE)

    visible_btns = (
        HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE,
        HPL.BUTTON_URL_STRING_SUBMIT_UPDATE,
        HPL.BUTTON_URL_STRING_CANCEL_UPDATE,
    )

    for btn in visible_btns:
        assert url_row.find_element(By.CSS_SELECTOR, btn).is_displayed()

    assert url_row.find_element(
        By.CSS_SELECTOR, HPL.INPUT_URL_STRING_UPDATE
    ).is_displayed()

    assert not url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).is_displayed()
    assert not url_row.find_element(By.CSS_SELECTOR, HPL.GO_TO_URL_ICON).is_displayed()


def verify_update_url_state_is_hidden(url_row: WebElement):
    visible_btns = (
        HPL.BUTTON_URL_DELETE,
        HPL.BUTTON_TAG_CREATE,
        HPL.BUTTON_URL_ACCESS,
        HPL.BUTTON_URL_STRING_UPDATE,
    )

    for btn in visible_btns:
        assert url_row.find_element(By.CSS_SELECTOR, btn).is_displayed()

    with pytest.raises(NoSuchElementException):
        url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)

    hidden_btns = (
        HPL.BUTTON_URL_STRING_SUBMIT_UPDATE,
        HPL.BUTTON_URL_STRING_CANCEL_UPDATE,
    )

    for btn in hidden_btns:
        assert not url_row.find_element(By.CSS_SELECTOR, btn).is_displayed()

    assert not url_row.find_element(
        By.CSS_SELECTOR, HPL.INPUT_URL_STRING_UPDATE
    ).is_displayed()

    assert url_row.find_element(By.CSS_SELECTOR, HPL.URL_STRING_READ).is_displayed()
    assert url_row.find_element(By.CSS_SELECTOR, HPL.GO_TO_URL_ICON).is_displayed()


# Tag Deck
def get_tag_filter_name_by_id(browser: WebDriver, tag_id: int) -> str | None:
    """
    Simplifies extraction of a tag filter name by its id.

    Args:
        WebDriver open to a selected UTub

    Returns:
        Tag filter name string
    """
    tag_filter = get_tag_filter_by_id(browser, tag_id)

    if tag_filter is None:
        return None

    tag_filter_name = tag_filter.find_element(By.TAG_NAME, "span").get_attribute(
        "innerText"
    )

    return tag_filter_name


def get_tag_filter_by_id(browser: WebDriver, tag_id: int) -> WebElement | None:
    return browser.find_element(
        By.CSS_SELECTOR, HPL.TAG_FILTERS + '[data-utub-tag-id="' + str(tag_id) + '"]'
    )


def get_tag_filter_id(tag_filter: WebElement) -> int | None:
    tag_filter_id = tag_filter.get_attribute("data-utub-tag-id")

    if tag_filter_id is None or not tag_filter_id.isnumeric():
        return None

    return int(tag_filter_id)


def get_tag_filter_by_name(browser: WebDriver, tag_name: str) -> WebElement | None:
    """
    Simplifies extraction of a tag filter WebElement by its name.

    Args:
        WebDriver open to a selected UTub

    Returns:
        Tag filter WebElement
    """
    tag_filters = get_utub_tag_filters(browser)
    if tag_filters is None:
        return None

    for tag_filter in tag_filters:

        tag_filter_name = tag_filter.find_element(By.TAG_NAME, "span").get_attribute(
            "innerText"
        )
        if tag_filter_name == tag_name:
            return tag_filter

    return None


def get_utub_tag_filters(browser: WebDriver) -> list[WebElement]:
    return wait_then_get_elements(browser, HPL.TAG_FILTERS, 0)


def get_selected_url_tags(url_row: WebElement) -> list[WebElement]:
    return url_row.find_elements(By.CSS_SELECTOR, HPL.TAG_BADGES)


def invalidate_csrf_token_on_page(browser: WebDriver):
    browser.execute_script(
        """
    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
          if (
            !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) &&
            !this.crossDomain
          ) {
            xhr.setRequestHeader("X-CSRFToken", "invalid-csrf-token");
          }
          return true;
        }
    });
    """
    )


def invalidate_csrf_token_in_form(browser: WebDriver):
    invalid_csrf_token = "invalid-csrf-token"
    browser.execute_script(
        f"document.querySelector('input[id=\"csrf_token\"]').setAttribute('value', '{invalid_csrf_token}');"
    )

    csrf_token = browser.find_element(By.CSS_SELECTOR, "input#csrf_token")
    WebDriverWait(browser, 3).until(
        lambda _: csrf_token.get_attribute("value") == invalid_csrf_token
    )
    assert csrf_token.get_attribute("value") == invalid_csrf_token


def assert_visited_403_on_invalid_csrf_and_reload(browser: WebDriver):
    # Await 403 response
    error_page_subheader = wait_then_get_element(
        browser, f"{SPL.ERROR_PAGE_HANDLER} h2", time=3
    )
    assert error_page_subheader is not None
    assert error_page_subheader.text == IDENTIFIERS.HTML_403

    wait_until_visible_css_selector(browser, SPL.ERROR_PAGE_REFRESH_BTN, timeout=3)

    # Click button to refresh page
    wait_then_click_element(browser, SPL.ERROR_PAGE_REFRESH_BTN, time=3)
