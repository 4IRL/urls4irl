from enum import Enum
from os import environ
import time
from urllib.parse import urlencode, urlsplit, urlunsplit

from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
)
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


from backend.config import ConfigTest
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as MP
from tests.functional.locators import SplashPageLocators as SPL


class Decks(Enum):
    UTUBS = HPL.UTUB_DECK
    MEMBERS = HPL.MEMBER_DECK
    TAGS = HPL.TAG_DECK
    URLS = HPL.URL_DECK


class ChromeRemoteWebDriver(WebDriver):
    def __init__(self, command_executor, options=None):
        super().__init__(command_executor=command_executor, options=options)

    def execute_cdp_cmd(self, cmd, cmd_args=None):
        if cmd_args is None:
            cmd_args = {}
        return self.execute("executeCdpCommand", {"cmd": cmd, "params": cmd_args})[
            "value"
        ]


def cpu_throttle_for_testing(browser: ChromeRemoteWebDriver, rate: int):
    """
    Throttles cpu by rate value, i.e. if rate is 4, then CPU is 4x slower.
    Helpful for determining how to fix flaky tests.
    DO NOT REMOVE even if not being used in tests.
    """
    browser.execute_cdp_cmd("Emulation.setCPUThrottlingRate", {"rate": rate})


def click_on_navbar(browser: WebDriver):
    # Settle any in-progress collapse transition before tapping the toggler:
    # Bootstrap ignores a toggle click while `collapsing` is active, so clicking
    # mid-transition (e.g. right after a deck-nav button collapsed the dropdown)
    # silently no-ops and the dropdown never opens. This pre-wait is a no-op when
    # nothing is transitioning.
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")
    wait_then_click_element(browser, HPL.NAVBAR_TOGGLER)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="collapsing")


def close_navbar(browser: WebDriver):
    """Collapse an already-open mobile navbar by tapping the toggler again.

    Mirrors `click_on_navbar` but waits for the `show` class to be removed
    from the dropdown, signalling Bootstrap's `hide.bs.collapse` animation
    has finished. The toggler-driven hide fires `onMobileNavbarClosed`
    (see `frontend/home/navbar.ts`), which emits `UI_NAVBAR_DROPDOWN_CLOSE`.
    """
    wait_then_click_element(browser, HPL.NAVBAR_TOGGLER)
    wait_for_class_to_be_removed(browser, HPL.NAVBAR_DROPDOWN, class_name="show")


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


def wait_for_element_presence(
    browser: WebDriver, css_selector: str, timeout: int = 10
) -> WebElement | None:
    try:
        element = WebDriverWait(browser, timeout).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    css_selector,
                )
            )
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


def wait_then_get_at_least_n_elements(
    browser: WebDriver, css_selector: str, minimum_count: int, time: float = 2
) -> list[WebElement]:
    """
    Waits until at least ``minimum_count`` elements matching the selector are
    present in the DOM, then returns every matching element.

    Use this instead of ``wait_then_get_elements`` when a known number of
    elements fill in asynchronously (e.g. one card per independent XHR). The
    underlying ``visibility_of_all_elements_located`` wait used by
    ``wait_then_get_elements`` resolves as soon as a single element is visible,
    so it can snapshot a partially-rendered grid; this helper polls the live
    count so the sample is only taken once the expected number has settled.

    Args:
        browser: WebDriver open to U4I
        css_selector: A target CSS selector string
        minimum_count: The minimum number of matching elements to wait for
        time: (Optional) Time to wait, default 2s

    Returns:
        List of WebElements matching the selector (empty list on timeout)
    """

    try:
        WebDriverWait(browser, time).until(
            lambda driver: len(driver.find_elements(By.CSS_SELECTOR, css_selector))
            >= minimum_count
        )
        return browser.find_elements(By.CSS_SELECTOR, css_selector)
    except TimeoutException:
        return browser.find_elements(By.CSS_SELECTOR, css_selector)


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

        browser.find_element(By.CSS_SELECTOR, css_selector).click()
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


def wait_for_selector_to_be_removed(
    browser: WebDriver, css_selector: str, timeout: int = 10
) -> bool:
    """
    Waits for all elements matching a CSS selector to be absent from the DOM.
    Re-queries the DOM each poll cycle, avoiding stale element references.

    Args:
        browser: The Selenium WebDriver instance.
        css_selector: CSS selector for the element(s) expected to be removed.
        timeout: Maximum time to wait (in seconds).

    Returns:
        True if the selector matches no elements within the timeout, False otherwise.
    """
    try:
        WebDriverWait(browser, timeout).until(
            lambda driver: len(driver.find_elements(By.CSS_SELECTOR, css_selector)) == 0
        )
        return True
    except TimeoutException:
        return False


def wait_until_hidden(
    browser: WebDriver, css_selector: str, timeout: int = 10
) -> WebElement | None:
    try:
        element = browser.find_element(By.CSS_SELECTOR, css_selector)
    except NoSuchElementException:
        # Element not in DOM (e.g. page navigated away) — treat as hidden
        return None
    try:
        WebDriverWait(browser, timeout).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, css_selector))
        )
    except (NoSuchElementException, StaleElementReferenceException):
        # Element was removed during wait (e.g. page navigated) — treat as hidden
        return None
    return element


def wait_until_css_property(
    browser: WebDriver,
    css_selector: str,
    css_property: str,
    expected_value: str,
    timeout: int = 10,
) -> WebElement:
    """Wait until an element's computed CSS property equals expected_value.

    Use for elements hidden via CSS transitions (opacity, width) rather than
    display:none, where is_displayed() is unreliable.
    """

    def check_property(driver: WebDriver) -> bool:
        element = driver.find_element(By.CSS_SELECTOR, css_selector)
        value = driver.execute_script(
            "return window.getComputedStyle(arguments[0]).getPropertyValue(arguments[1]);",
            element,
            css_property,
        )
        return value == expected_value

    WebDriverWait(browser, timeout).until(check_property)
    return browser.find_element(By.CSS_SELECTOR, css_selector)


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


def wait_until_in_focus(browser: WebDriver, css_selector: str, timeout=10):
    WebDriverWait(browser, timeout).until(
        lambda driver: driver.execute_script(
            "return document.activeElement === arguments[0];",
            driver.find_element(By.CSS_SELECTOR, css_selector),
        )
    )


def wait_for_animation_to_end_check_top_lhs_corner(
    browser: WebDriver, locator: str, timeout=10, interval=0.1
):
    """Wait until an element stops moving by checking its position via the top LHS corner."""

    def element_stopped_moving(browser: WebDriver):
        element = browser.find_element(By.CSS_SELECTOR, locator)
        initial_position = browser.execute_script(
            "return [arguments[0].getBoundingClientRect().left, arguments[0].getBoundingClientRect().top];",
            element,
        )
        time.sleep(interval)  # Wait a bit before checking again
        new_position = browser.execute_script(
            "return [arguments[0].getBoundingClientRect().left, arguments[0].getBoundingClientRect().top];",
            element,
        )
        return initial_position == new_position

    WebDriverWait(browser, timeout).until(element_stopped_moving)


def wait_for_animation_to_end_check_height(
    browser: WebDriver, locator: str, timeout=10, interval=0.1
):
    """Wait until an element stops moving by checking its height."""

    def element_stopped_moving(browser: WebDriver):
        element = browser.find_element(By.CSS_SELECTOR, locator)
        initial_position = browser.execute_script(
            "return [arguments[0].getBoundingClientRect().height];",
            element,
        )
        time.sleep(interval)  # Wait a bit before checking again
        new_position = browser.execute_script(
            "return [arguments[0].getBoundingClientRect().height];",
            element,
        )
        return initial_position == new_position

    WebDriverWait(browser, timeout).until(element_stopped_moving)


def wait_for_element_visible(browser: WebDriver, locator: str, timeout=10):
    """Wait until an element stops moving by checking its position."""
    WebDriverWait(browser, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, locator))
    )


def wait_for_element_with_text(
    browser: WebDriver, selector: str, expected_text: str, timeout=10
):
    """
    Wait for an element with specific CSS selector to contain expected text

    Args:
        tooltip_class: CSS class of the element
        expected_text: The text to wait for
        timeout: Maximum time to wait
    """
    return WebDriverWait(browser, timeout).until(
        EC.text_to_be_present_in_element((By.CSS_SELECTOR, selector), expected_text)
    )


def wait_for_any_element_with_text(
    browser: WebDriver, selector: str, expected_text: str, timeout=10
):
    """
    Wait for any element with specific CSS selector to contain expected text

    Args:
        tooltip_class: CSS class of the element
        expected_text: The text to wait for
        timeout: Maximum time to wait
    """

    def check_any_element_contains_text(driver):
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        for element in elements:
            try:
                if expected_text in element.text:
                    return element
            except StaleElementReferenceException:
                # Element became stale, continue checking others
                continue
        return False

    return WebDriverWait(browser, timeout).until(check_any_element_contains_text)


def wait_for_class_to_be_removed(
    browser: WebDriver, css_selector: str, class_name: str, timeout: float = 10
):
    """
    Wait for a specific class to be removed from an element.

    Args:
        browser: WebDriver instance
        css_selector: CSS selector to locate the element
        class_name: Class name to check for removal
        timeout: Maximum time to wait in seconds

    Returns:
        True if the class was removed, False if timeout occurred
    """

    def class_is_removed(driver):
        element = driver.find_element(By.CSS_SELECTOR, css_selector)
        element_classes = element.get_attribute("class").split()
        return class_name not in element_classes

    try:
        WebDriverWait(browser, timeout).until(class_is_removed)
        return True
    except TimeoutException:
        return False


def wait_for_page_complete(browser: WebDriver, timeout: int = 10):
    """
    Wait for the page to be completely loaded and stable.
        This is a more comprehensive wait function that checks multiple indicators
            of page readiness.
    """
    # Wait for document.readyState to be 'complete'
    WebDriverWait(browser, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

    # Wait for jQuery to be loaded and active requests to be completed
    jquery_check = """
            return (typeof jQuery !== 'undefined') ?
                           jQuery.active == 0 :
                                          true;
                                              """
    WebDriverWait(browser, timeout).until(lambda d: d.execute_script(jquery_check))

    # Check for any animations
    animation_check = """
            return (typeof jQuery !== 'undefined') ?
                           jQuery(':animated').length == 0 :
                                          true;
                                              """
    WebDriverWait(browser, timeout).until(lambda d: d.execute_script(animation_check))

    return True


def wait_for_dom_stable(
    browser: WebDriver, timeout: int = 5, poll_frequency: float = 0.5
):
    """
    Wait until the DOM is stable (no changes for a period of time).
        This helps with pages that have dynamic content loading.
    """
    start_time = time.time()
    last_snapshot, current_snapshot = None, None

    while time.time() - start_time < timeout:
        current_snapshot = browser.execute_script(
            "return document.documentElement.outerHTML"
        )

        if last_snapshot == current_snapshot:
            # DOM hasn't changed since last check
            return True

        last_snapshot = current_snapshot
        time.sleep(poll_frequency)

    # The DOM kept changing until timeout
    return False


def wait_for_page_complete_and_dom_stable(browser: WebDriver, timeout: int = 10):
    assert wait_for_page_complete(browser, timeout=timeout)
    assert wait_for_dom_stable(browser, timeout=timeout)


def login_user_ui(
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

    wait_for_modal_ready(browser, SPL.LOGIN_MODAL)

    wait_for_element_presence(browser, SPL.LOGIN_INPUT_USERNAME)
    wait_until_visible_css_selector(browser, SPL.LOGIN_INPUT_USERNAME)

    return input_login_fields(browser, username, password)


def login_with_google_ui(
    browser: WebDriver,
    subject: str = UTS.OAUTH_RETURNING_USER_SUBJECT,
    email: str = UTS.OAUTH_RETURNING_USER_EMAIL,
    name: str = UTS.OAUTH_RETURNING_USER_NAME,
    from_register: bool = False,
):
    """
    Streamlines actions needed to sign in (or register) via the fake Google
    OAuth provider (backend/testing/fake_oauth_provider.py).

    Args:
        WebDriver open to U4I Splash Page
        (Optional) Subject claim the fake provider should return, defaults to a returning-user subject
        (Optional) Email claim the fake provider should return, defaults to a returning-user email
        (Optional) Display name claim the fake provider should return, defaults to a returning-user name
        (Optional) Whether to click Google's button from the Register modal instead of Login, defaults to False

    Returns:
        N/A
    """
    splash_url = browser.current_url
    split_splash_url = urlsplit(splash_url)
    set_identity_url = urlunsplit(
        (
            split_splash_url.scheme,
            split_splash_url.netloc,
            "/fake-oauth/set-identity",
            urlencode({"subject": subject, "email": email, "name": name}),
            "",
        )
    )

    # Seeding the identity is its own navigation (the fake provider has no
    # session-shared way to receive it otherwise), so return to the splash
    # page afterward before opening the login/register modal.
    browser.get(set_identity_url)
    browser.get(splash_url)

    if from_register:
        wait_then_click_element(browser, SPL.BUTTON_REGISTER)
        wait_for_modal_ready(browser, SPL.REGISTER_MODAL)
        wait_then_click_element(browser, SPL.REGISTER_BUTTON_GOOGLE_OAUTH)
    else:
        wait_then_click_element(browser, SPL.BUTTON_LOGIN)
        wait_for_modal_ready(browser, SPL.LOGIN_MODAL)
        wait_then_click_element(browser, SPL.LOGIN_BUTTON_GOOGLE_OAUTH)


def input_login_fields(
    browser: WebDriver,
    username: str = UTS.TEST_USERNAME_1,
    password: str = UTS.TEST_PASSWORD_1,
):
    # Input login details
    username_input = wait_then_get_element(browser, SPL.LOGIN_INPUT_USERNAME)
    assert username_input is not None
    clear_then_send_keys(username_input, username)

    password_input = wait_then_get_element(browser, SPL.LOGIN_INPUT_PASSWORD)
    assert password_input is not None
    clear_then_send_keys(password_input, password)

    return password_input


# Modal
def wait_for_modal_ready(browser, modal_selector, timeout=10):
    '''
    """Wait for Bootstrap modal to be fully loaded and interactive"""

    wait = WebDriverWait(browser, timeout)

    modal = wait.until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, modal_selector))
    )

    wait.until(lambda _: "show" in modal.get_attribute("class"))  # type: ignore
    time.sleep(0.2)
    return modal
    '''
    wait = WebDriverWait(browser, timeout)

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, modal_selector)))
    wait.until(
        lambda driver: "show"
        in driver.find_element(By.CSS_SELECTOR, modal_selector).get_attribute("class")
    )
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, modal_selector)))

    # Ensure modal is not in transition state
    max_transition_wait = 10  # 10 attempts
    for _ in range(max_transition_wait):
        try:
            modal_element = browser.find_element(By.CSS_SELECTOR, modal_selector)
            classes = modal_element.get_attribute("class")

            # Check if transition is complete
            if "show" in classes and "fade" in classes:
                # For Bootstrap fade modals, check opacity
                opacity = browser.execute_script(
                    "return window.getComputedStyle(arguments[0]).opacity;",
                    modal_element,
                )
                if float(opacity) >= 1.0:
                    break
            elif "show" in classes:
                break

            time.sleep(0.1)
        except StaleElementReferenceException:
            time.sleep(0.1)
            continue

    # Clickability is a final verification that modal is interactive
    final_modal = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, modal_selector))
    )

    # Bootstrap 5 Modal.hide() returns early when _isTransitioning is true,
    # so clicking .btn-close mid-show silently no-ops. Block until Bootstrap
    # reports the show animation has actually finished.
    wait.until(
        lambda driver: driver.execute_script(
            "var i = bootstrap.Modal.getInstance(arguments[0]);"
            "return !i || i._isTransitioning === false;",
            final_modal,
        )
    )
    return final_modal


def dismiss_modal_with_click_out(
    browser: WebDriver, modal_selector: str = MP.ELEMENT_MODAL
):
    action = ActionChains(browser)
    modal_element = wait_then_get_element(browser, modal_selector)
    assert modal_element is not None
    width = modal_element.rect["width"]
    height = modal_element.rect["height"]
    offset = 15
    action.move_to_element_with_offset(
        modal_element, -width / 2 + offset, -height / 2 + offset
    )
    action.click()
    action.perform()


def wait_for_modal_hidden(
    browser: WebDriver, modal_selector: str, timeout: int = 10
) -> None:
    """Wait for Bootstrap modal to be fully hidden"""
    wait = WebDriverWait(browser, timeout)
    modal = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, modal_selector))
    )

    def modal_class_lacks_show(_driver):
        try:
            return "show" not in modal.get_attribute("class")
        except StaleElementReferenceException:
            # Stale element = modal removed from DOM = hidden (the positive signal we want)
            return True

    wait.until(modal_class_lacks_show)
    wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, modal_selector)))


# UTub Deck
def select_utub_by_name(browser: WebDriver, utub_name: str):
    """
    Selects the first UTub selector matching the supplied UTub name

    Args:
        WebDriver open to U4I Home Page
        Name of UTub to be selected
    """

    def find_and_click_utub_by_name(driver):
        selectors = driver.find_elements(By.CSS_SELECTOR, HPL.SELECTORS_UTUB)
        for selector in selectors:
            try:
                name_elem = selector.find_element(
                    By.CSS_SELECTOR, HPL.SELECTORS_UTUB_NAME
                )
                if name_elem.is_displayed() and name_elem.text == utub_name:
                    selector.click()
                    return True
            except StaleElementReferenceException:
                return False
        return False

    WebDriverWait(
        browser, 10, ignored_exceptions=[StaleElementReferenceException]
    ).until(find_and_click_utub_by_name)
    wait_until_utub_name_appears(browser, utub_name)


def select_utub_by_id(browser: WebDriver, utub_id: int):
    utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
    utub_selector_elem = wait_then_get_element(browser, utub_selector, time=10)
    assert utub_selector_elem is not None
    utub_name_elem = utub_selector_elem.find_element(
        By.CSS_SELECTOR, HPL.SELECTORS_UTUB_NAME
    )
    utub_name = utub_name_elem.text
    wait_then_click_element(browser, utub_selector, time=3)
    wait_until_utub_name_appears(browser, utub_name)


def select_utub_by_id_mobile(browser: WebDriver, utub_id: int):
    utub_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"
    utub_selector_elem = wait_for_element_presence(browser, utub_selector, timeout=10)
    assert utub_selector_elem is not None
    wait_then_click_element(browser, utub_selector, time=3)


def wait_until_utub_name_appears(browser: WebDriver, utub_name: str):
    WebDriverWait(
        browser, 10, ignored_exceptions=[StaleElementReferenceException]
    ).until(
        lambda driver: (
            elem := driver.find_elements(By.CSS_SELECTOR, HPL.HEADER_URL_DECK)
        )
        and elem[0].is_displayed()
        and elem[0].text == utub_name
    )


def get_selected_utub_id(browser: WebDriver) -> int:
    utub = browser.find_element(By.CSS_SELECTOR, HPL.SELECTOR_SELECTED_UTUB)
    utub_id = utub.get_attribute("utubid")
    assert utub_id is not None
    return int(utub_id)


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


# URL Deck
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

    attempts = 3
    for _ in range(attempts):
        for url_row in url_rows:
            url_row_string = url_row.find_element(
                By.CSS_SELECTOR, HPL.URL_STRING_READ
            ).get_attribute("href")
            if url_row_string == url_string:
                url_row.click()
                break

        wait_for_animation_to_end_check_height(browser, HPL.ROW_SELECTED_URL)
        wait_for_page_complete_and_dom_stable(browser)
        url_string_css = f"{HPL.ROW_SELECTED_URL} {HPL.URL_STRING_READ}"

        try:
            url_string_elem = wait_then_get_element(
                browser, css_selector=url_string_css
            )
            assert url_string_elem
            assert url_string_elem.get_attribute("href") == url_string
            return
        except Exception:
            continue


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
            url_id = row.get_attribute("utuburlid")
            assert url_id is not None
            assert isinstance(url_id, str) and url_id.isdecimal()
            url_ids.append(int(url_id))

    return url_ids


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


def get_url_row_by_id(browser: WebDriver, utuburlid: int) -> WebElement:
    url_row = wait_then_get_element(
        browser, HPL.ROWS_URLS + f'[utuburlid="{utuburlid}"]'
    )
    assert url_row is not None
    return url_row


def open_update_url_title(browser: WebDriver, selected_url_row: WebElement):
    """
    Streamlines actions required to updated a URL in the selected URL.

    Args:
        WebDriver open to a selected URL
        New URL title

    Returns:
        Yields WebDriver to tests
    """

    # Select url title button
    url_title_text = wait_then_get_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.URL_TITLE_READ}"
    )
    assert url_title_text

    actions = ActionChains(browser)

    # Hover over URL title to display editURLTitle button
    actions.move_to_element(url_title_text)

    # Pause to make sure editURLTitle button is visible
    actions.pause(3).perform()

    update_url_title_button = selected_url_row.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_URL_TITLE_UPDATE
    )

    actions.move_to_element(update_url_title_button).pause(2)

    actions.click(update_url_title_button)

    actions.perform()

    update_url_title_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}"
    wait_until_visible_css_selector(browser, update_url_title_selector)


# Misc
def wait_and_get_deepest_hovered_elem(
    browser: WebDriver, timeout=10
) -> WebElement | None:
    def _predicate(browser: WebDriver) -> WebElement | None:
        script = """
            var el = document.querySelector(':hover');
            while (el && el.querySelector(':hover')) {
                el = el.querySelector(':hover');
            }
            return el;
        """
        element = browser.execute_script(script)
        return element if element else None

    return WebDriverWait(browser, timeout).until(_predicate)


def wait_for_tooltip_with_hover_retry(
    browser: WebDriver, element: WebElement, tooltip_selector: str, max_attempts=5
) -> WebElement | None:
    """
    Attempts to rehover over a given parent element, and checks if a tooltip shows on each hover.
    If tooltip shows, return tooltip Web Element - else return None.

    Args:
        browser: WebDriver for running Selenium
        element: WebElement, parent element for tooltip interaction
        tooltip_selector: str - The CSS selector for the given tooltip
        max_attempts: int - How many times to retry hovering

    Returns:
        WebElement of tooltip if Tooltip found, else None
    """
    for _ in range(max_attempts):
        ActionChains(browser).move_to_element(element).perform()

        for _ in range(10):
            try:
                tooltip = browser.find_element(By.CSS_SELECTOR, tooltip_selector)
                if tooltip.is_displayed():
                    return tooltip
            except Exception:
                pass
            time.sleep(0.1)

        ActionChains(browser).move_by_offset(10, 10).perform()

    return


def invalidate_csrf_token_on_page(browser: WebDriver):
    browser.execute_script("""
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
    """)


def add_forced_rate_limit_header(browser: WebDriver):
    browser.execute_script("""
    (function() {
        var settings = $.ajaxSettings;
        var oldBeforeSend = settings.beforeSend;
        $.ajaxSetup({
            beforeSend: function (xhr, ajaxSettings) {
                // Call the previous beforeSend if it exists
                if (oldBeforeSend) {
                    oldBeforeSend.call(this, xhr, ajaxSettings);
                }

                // Add our custom header
                xhr.setRequestHeader("X-Force-Rate-Limit", "true");
                return true;
            }
        });
    })();
    """)


def modify_navigational_link_for_rate_limit(browser: WebDriver, element_id: str):
    browser.execute_script(
        """
        const link = document.getElementById(arguments[0]);
        if (!link) {
            throw new Error('Element with ID "' + arguments[0] + '" not found');
        }
        const url = new URL(link.href, window.location.origin);
        url.searchParams.set('force_rate_limit', 'true');
        link.href = url.toString();
    """,
        element_id,
    )


def invalidate_csrf_token_in_form(browser: WebDriver):
    invalidate_csrf_token_on_page(browser)


def build_secondary_driver():
    config = ConfigTest()
    options = Options()
    options.add_argument("--disable-notifications")
    options.add_argument("--headless")

    if config.DOCKER:
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver_path = environ.get("CHROMEDRIVER_PATH", "")
        service = webdriver.ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)
    driver.set_window_size(width=1920, height=1080)
    return driver


def set_focus_on_element(driver: WebDriver, element: WebElement):
    driver.execute_script("arguments[0].focus();", element)
    # Avoid circular reference...
    from tests.functional.assert_utils import assert_element_in_focus

    assert_element_in_focus(driver, element)


def get_css_selector_for_url_by_id(url_id: int) -> str:
    return f"{HPL.ROWS_URLS}[utuburlid='{url_id}']"


def scroll_footer_link_into_view(
    browser: WebDriver, css_selector: str, timeout: int = 10
):
    """Scroll a below-the-fold footer link into the viewport before clicking it.

    On taller splash pages the footer links sit below the fold. Selenium's
    native `.click()` auto-scroll assigns the document root's `scrollTop`, which
    no-ops under headless Chrome, so the link stays out of view and the click is
    intercepted. Sending `Keys.END` to the body performs a real key-driven
    scroll (which headless Chrome does honor), bringing the footer into view.
    """
    link = wait_for_element_presence(browser, css_selector)
    assert link is not None
    body = browser.find_element(By.TAG_NAME, "body")
    body.send_keys(Keys.END)
    WebDriverWait(browser, timeout).until(
        lambda driver: driver.execute_script(
            "const rect = arguments[0].getBoundingClientRect();"
            "return rect.top >= 0 && rect.bottom <= window.innerHeight;",
            link,
        )
    )


def visit_privacy_page(browser: WebDriver):
    scroll_footer_link_into_view(browser, HPL.PRIVACY_BTN)
    wait_then_click_element(browser, HPL.PRIVACY_BTN, time=3)
    privacy_title = wait_then_get_element(browser, HPL.PRIVACY_HEADER)
    assert privacy_title

    assert privacy_title.text == "Privacy Policy"


def visit_terms_page(browser: WebDriver):
    scroll_footer_link_into_view(browser, HPL.TERMS_BTN)
    wait_then_click_element(browser, HPL.TERMS_BTN, time=3)
    terms_title = wait_then_get_element(browser, HPL.TERMS_HEADER)
    assert terms_title

    assert terms_title.text == "Terms & Conditions"


def visit_contact_us_page(browser: WebDriver):
    scroll_footer_link_into_view(browser, HPL.CONTACT_BTN)
    wait_then_click_element(browser, HPL.CONTACT_BTN, time=3)
    terms_title = wait_then_get_element(browser, HPL.CONTACT_US_HEADER)
    assert terms_title

    assert terms_title.text == IDENTIFIERS.CONTACT_US_PAGE


def contact_form_entry(
    browser: ChromeRemoteWebDriver,
    subject: str,
    content: str,
):
    wait_for_element_presence(browser, HPL.CONTACT_SUBJECT_INPUT)
    wait_until_visible_css_selector(browser, HPL.CONTACT_SUBJECT_INPUT)

    subject_input = wait_then_get_element(browser, HPL.CONTACT_SUBJECT_INPUT)
    assert subject_input is not None
    clear_then_send_keys(subject_input, subject)

    content_input = wait_then_get_element(browser, HPL.CONTACT_CONTENT_INPUT)
    assert content_input is not None
    clear_then_send_keys(content_input, content)


def force_next_delete_ajax_failure_no_navigate(browser: WebDriver):
    """Monkey-patches $.ajax so the next DELETE request fails with a fake error.

    The fake xhr uses an immutable _429Handled getter that always returns true.
    This causes the failure handler to return early after re-enabling the submit
    button, without attempting any page navigation. The getter is necessary because
    ajaxCall's global fail handler unconditionally writes _429Handled = false
    before the app-level fail handler reads it.
    """
    browser.execute_script("""
    (function() {
        var originalAjax = $.ajax;
        $.ajax = function(options) {
            if (options && options.type && options.type.toLowerCase() === 'delete') {
                // Restore original $.ajax for subsequent calls
                $.ajax = originalAjax;
                var deferred = $.Deferred();
                var fakeXhr = {
                    status: 500,
                    getResponseHeader: function() { return 'application/json'; },
                    responseText: '{"error": "forced test failure"}'
                };
                // Use a getter so _429Handled always reads as true, even after
                // ajaxCall's global handler writes false to it. This makes
                // deleteURLFail return early after re-enabling the button.
                Object.defineProperty(fakeXhr, '_429Handled', {
                    get: function() { return true; },
                    set: function() { /* no-op: ignore writes from ajaxCall */ },
                    configurable: true
                });
                setTimeout(function() {
                    deferred.reject(fakeXhr, 'error', 'Internal Server Error');
                }, 0);
                deferred.promise(fakeXhr);
                return fakeXhr;
            }
            return originalAjax.apply(this, arguments);
        };
    })();
    """)


def add_cookie_banner_cookie(browser: WebDriver):
    cookie = {
        "name": UTS.COOKIE_NAME,
        "value": UTS.COOKIE_VALUE,
        "path": "/",
        "httpOnly": False,
    }

    browser.add_cookie(cookie)
    browser.refresh()
    wait_for_page_complete_and_dom_stable(browser)


def dispatch_pointer_drag(
    browser: WebDriver,
    css_selector: str,
    *,
    start_y: float,
    end_y: float,
    start_x: float | None = None,
    end_x: float | None = None,
    steps: int = 6,
    step_delay_ms: int = 0,
) -> None:
    """
    Drives a synthetic pointer drag on the element matched by ``css_selector``
    by dispatching a ``pointerdown`` at ``(start_x, start_y)``, ``steps``
    interpolated ``pointermove`` events toward ``(end_x, end_y)``, and a final
    ``pointerup`` at ``(end_x, end_y)``.

    ``start_x``/``end_x`` are optional. When omitted, ``clientX`` stays fixed at
    ``0`` for every event (a purely vertical drag), matching this function's
    original behavior for existing vertical tag-sheet callers. Passing both
    produces a horizontal drag (``start_y == end_y``) or a diagonal one
    (``start_y != end_y``).

    Every event is constructed as a real ``PointerEvent`` (``pointerType: "touch"``,
    primary ``button: 0``, ``pointerId: 1``) and dispatched **directly on the
    target element** — never on ``document`` — because the gesture listeners are
    bound via ``element.addEventListener``; synthetic events dispatched on
    ``document`` never reach element-level handlers. With ``bubbles: true`` they
    still propagate upward naturally.

    ``step_delay_ms`` inserts a real wall-clock pause between consecutive
    ``pointermove`` events. The default (``0``) dispatches every event in a single
    synchronous turn, which is fine for distance-threshold gestures. For a
    sub-threshold drag that must NOT fling-commit, pass a non-zero delay so the
    handler's velocity sample (``deltaY / elapsedMs`` or ``deltaX / elapsedMs``)
    stays below the fling threshold — an instantaneous synthetic drag otherwise
    computes a huge velocity and commits regardless of distance.

    Viewport-agnostic and reusable for any drawer/sheet/row drag target.

    @example dispatch_pointer_drag(browser, "#tagSheetHandle", start_y=780, end_y=560)
        # drags the handle 220px up (open gesture), clientX fixed at 0
    @example dispatch_pointer_drag(browser, "#tagSheetHandle", start_y=420, end_y=640)
        # drags the handle 220px down (close gesture), clientX fixed at 0
    @example dispatch_pointer_drag(browser, "#tagSheetHandle", start_y=780, end_y=720,
        step_delay_ms=40)  # slow 60px up drag, sub-threshold, no fling-commit
    @example dispatch_pointer_drag(browser, ".urlRow", start_x=415, end_x=115,
        start_y=450, end_y=450)  # drags the row 300px left (horizontal commit)
    """
    resolved_start_x = start_x if start_x is not None else 0
    resolved_end_x = end_x if end_x is not None else 0

    if step_delay_ms <= 0:
        browser.execute_script(
            """
            const { cssSelector, startX, startY, endX, endY, steps } = arguments[0];
            const element = document.querySelector(cssSelector);
            if (!element) {
                throw new Error('No element found for selector "' + cssSelector + '"');
            }

            function dispatchPointer(type, clientX, clientY) {
                const event = new PointerEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    pointerId: 1,
                    pointerType: "touch",
                    button: 0,
                    clientX: clientX,
                    clientY: clientY,
                });
                element.dispatchEvent(event);
            }

            dispatchPointer("pointerdown", startX, startY);
            for (let step = 1; step <= steps; step++) {
                const interpolatedX = startX + ((endX - startX) * step) / steps;
                const interpolatedY = startY + ((endY - startY) * step) / steps;
                dispatchPointer("pointermove", interpolatedX, interpolatedY);
            }
            dispatchPointer("pointerup", endX, endY);
            """,
            {
                "cssSelector": css_selector,
                "startX": resolved_start_x,
                "startY": start_y,
                "endX": resolved_end_x,
                "endY": end_y,
                "steps": steps,
            },
        )
        return

    browser.execute_async_script(
        """
        const params = arguments[0];
        const done = arguments[1];
        const { cssSelector, startX, startY, endX, endY, steps, stepDelayMs } = params;
        const element = document.querySelector(cssSelector);
        if (!element) {
            throw new Error('No element found for selector "' + cssSelector + '"');
        }

        function dispatchPointer(type, clientX, clientY) {
            const event = new PointerEvent(type, {
                bubbles: true,
                cancelable: true,
                pointerId: 1,
                pointerType: "touch",
                button: 0,
                clientX: clientX,
                clientY: clientY,
            });
            element.dispatchEvent(event);
        }

        dispatchPointer("pointerdown", startX, startY);
        let step = 0;
        function nextMove() {
            step += 1;
            if (step > steps) {
                dispatchPointer("pointerup", endX, endY);
                done();
                return;
            }
            const interpolatedX = startX + ((endX - startX) * step) / steps;
            const interpolatedY = startY + ((endY - startY) * step) / steps;
            dispatchPointer("pointermove", interpolatedX, interpolatedY);
            setTimeout(nextMove, stepDelayMs);
        }
        setTimeout(nextMove, stepDelayMs);
        """,
        {
            "cssSelector": css_selector,
            "startX": resolved_start_x,
            "startY": start_y,
            "endX": resolved_end_x,
            "endY": end_y,
            "steps": steps,
            "stepDelayMs": step_delay_ms,
        },
    )
