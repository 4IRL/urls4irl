from flask import Flask
import pytest
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)

from src.models.utub_members import Member_Role, Utub_Members
from src.models.utub_tags import Utub_Tags
from src.models.utub_urls import Utub_Urls
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.selenium_utils import (
    Decks,
    wait_for_animation_to_end,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_visible_css_selector,
)


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


def assert_visible_css_selector(
    browser: WebDriver, css_selector: str, time: float = 10
):
    try:
        WebDriverWait(browser, time).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        assert True
    except TimeoutException:
        assert False


def assert_panel_visibility_mobile(browser: WebDriver, visible_deck: Decks):
    wait_until_visible_css_selector(browser, HPL.MAIN_PANEL, timeout=10)

    for deck in Decks:
        if visible_deck == deck:
            continue
        assert_not_visible_css_selector(browser, deck.value)

    assert_visible_css_selector(browser, visible_deck.value)


def assert_tooltip_animates(
    browser: WebDriver,
    parent_css_selector: str,
    tooltip_parent_class: str,
    tooltip_text: str,
    outside_elem: str = HPL.U4I_LOGO,
):
    """
    Asserts that a tooltip with prefix tooltip_parent_class properly:
        1) Is hidden before mouse is hovered over parent element
        2) Is shown with mouse hovering over parent elementshows and hides based when hovering
        3) Is hidden again after mouse moves away from parent element

    Args:
        browser: WebDriver for Selenium
        parent_css_selector: String, the parent element's css selector.
        tooltip_parent_class: String, the parent element's class that will show the tooltip.
            By standard, U4I, uses `{parent-class}-tooltip` as an HTML class on the tooltip
        tooltip_text: String, the text within the tooltip.
        outside_elem: String - An outside element to move the mouse away to to hide the toolip
    """
    tooltip_selector = f"{tooltip_parent_class}{HPL.TOOLTIP_SUFFIX}"
    assert_not_visible_css_selector(browser, tooltip_selector)

    url_access_btn = wait_then_get_element(browser, parent_css_selector)
    assert url_access_btn
    ActionChains(browser).move_to_element(url_access_btn).perform()

    wait_for_animation_to_end(browser, tooltip_selector)
    assert_visible_css_selector(browser, tooltip_selector)
    tooltip = wait_then_get_element(browser, tooltip_selector)
    assert tooltip
    assert tooltip.text == tooltip_text

    logo = wait_then_get_element(browser, outside_elem)
    assert logo
    ActionChains(browser).move_to_element(logo).perform()
    assert_not_visible_css_selector(browser, tooltip_selector)


def assert_on_404_page(browser: WebDriver):
    error_header = wait_then_get_element(browser, css_selector="h2", time=3)
    assert error_header is not None
    assert error_header.text == IDENTIFIERS.HTML_404
    assert "Invalid Request - URLS4IRL" == browser.title


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


def assert_no_utub_selected(browser: WebDriver):
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, f"#UTubOwner {HPL.BADGES_MEMBERS}")

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.BADGES_MEMBERS)

    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, HPL.TAG_FILTERS)

    assert not wait_then_get_elements(browser, HPL.ROWS_URLS)


def assert_utub_selected(browser: WebDriver, app: Flask, utub_id: int):
    with app.app_context():
        members_in_utub: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id
        ).all()
        member_ids: list[int] = [utub_member.user_id for utub_member in members_in_utub]
        assert_members_exist_in_member_deck(browser, member_ids)

        urls_in_utub: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).all()
        utub_url_ids: list[int] = [utub_url.id for utub_url in urls_in_utub]
        assert_utub_url_exists_in_url_deck(browser, utub_url_ids)
        assert_url_coloring_is_correct(browser)

        tags_in_utub: list[Utub_Tags] = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_id
        ).all()
        utub_tag_ids: list[int] = [utub_tag.id for utub_tag in tags_in_utub]
        assert_tags_exist_in_tag_deck(browser, utub_tag_ids)


def assert_utub_icon(browser: WebDriver, app: Flask, user_id: int, utub_id: int):
    with app.app_context():
        membership: Utub_Members = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id, Utub_Members.user_id == user_id
        ).first()

    icon_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}'] "
    if membership.member_role == Member_Role.CREATOR.value:
        icon_selector += HPL.CREATOR_ICON

    elif membership.member_role == Member_Role.CO_CREATOR.value:
        icon_selector += HPL.CO_CREATOR_ICON

    elif membership.member_role == Member_Role.MEMBER.value:
        icon_selector += HPL.MEMBER_ICON

    wait_until_visible_css_selector(browser, icon_selector, timeout=10)
    icon = wait_then_get_element(browser, icon_selector, time=10)
    assert icon is not None
    assert icon.is_displayed()


def _element_is_visible(browser: WebDriver, selector: str) -> bool:
    """
    Fetches the element fresh from the DOM each time and checks if it is displayed.
    """
    try:
        element = browser.find_element(By.CSS_SELECTOR, selector)
        return element.is_displayed()
    except StaleElementReferenceException:
        return False  # Retry if stale


def assert_members_exist_in_member_deck(browser: WebDriver, member_ids: list[int]):
    for member_id in member_ids:
        member_selector = f"{HPL.BADGES_MEMBERS}[memberid='{member_id}']"
        WebDriverWait(browser, 10).until(
            lambda browser: _element_is_visible(browser, member_selector)
        )

        def retry_assertion():
            """Fetch element fresh and assert it's displayed to avoid stale reference."""
            try:
                fresh_elem = browser.find_element(By.CSS_SELECTOR, member_selector)
                assert (
                    fresh_elem.is_displayed()
                ), f"Member element {member_id} is not displayed"
                return True  # Success
            except StaleElementReferenceException:
                return False  # Retry

        WebDriverWait(browser, 10).until(lambda _: retry_assertion())


def assert_utub_url_exists_in_url_deck(browser: WebDriver, utub_url_ids: list[int]):
    for utub_url_id in utub_url_ids:
        utub_url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
        utub_url_elem = wait_then_get_element(browser, utub_url_selector, time=3)
        assert utub_url_elem is not None
        assert utub_url_elem.is_displayed()


def assert_elem_with_url_string_exists(browser: WebDriver, url_string: str):
    """
    If a UTub is selected and the UTub contains URLs, find a URL containing a given string.

    Args:
        browser (WebDriver): The browser driver open to a selected UTub
        url_string (str): URL String

    Returns:
        (bool): True if element exists, False otherwise

    """
    url_rows = wait_then_get_elements(browser, HPL.ROWS_URLS)
    assert url_rows is not None

    url_row_string = None
    for url_row in url_rows:
        url_row_string = url_row.find_element(
            By.CSS_SELECTOR, HPL.URL_STRING_READ
        ).get_attribute("href")

        if url_row_string == url_string:
            break

    assert url_row_string == url_string


def assert_update_url_state_is_shown(url_row: WebElement):
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


def assert_update_url_state_is_hidden(url_row: WebElement):
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


def assert_url_coloring_is_correct(browser: WebDriver):
    url_cards = wait_then_get_elements(browser, HPL.ROW_VISIBLE_URL, time=3)
    assert url_cards
    url_cards_in_order = sorted(url_cards, key=lambda elem: elem.location["y"])

    for idx, url_card in enumerate(url_cards_in_order):
        if idx % 2 == 0:
            assert "even" in url_card.get_dom_attribute("class")
        else:
            assert "odd" in url_card.get_dom_attribute("class")


def assert_tags_exist_in_tag_deck(browser: WebDriver, utub_tag_ids: list[int]):
    for utub_tag_id in utub_tag_ids:
        utub_tag_selector = (
            f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{utub_tag_id}']"
        )
        utub_tag_elem = wait_then_get_element(browser, utub_tag_selector, time=3)
        assert utub_tag_elem is not None
        assert utub_tag_elem.is_displayed()


def assert_visited_403_on_invalid_csrf_and_reload(browser: WebDriver):
    # Await 403 response
    error_page_subheader = wait_then_get_element(
        browser, f"{SPL.ERROR_PAGE_HANDLER} h2", time=3
    )
    assert error_page_subheader is not None
    assert error_page_subheader.text == IDENTIFIERS.HTML_403

    wait_until_visible_css_selector(browser, SPL.ERROR_PAGE_REFRESH_BTN, timeout=10)

    # Click button to refresh page
    wait_then_click_element(browser, SPL.ERROR_PAGE_REFRESH_BTN, time=10)


def assert_element_in_focus(browser: WebDriver, element: WebElement, timeout=10):
    try:
        # Wait and verify that the element has focus
        WebDriverWait(browser, timeout).until(
            lambda d: d.switch_to.active_element == element
        )
        assert True
    except TimeoutException:
        assert False


def assert_active_utub(browser: WebDriver, utub_name: str):
    """
    Streamlines actions needed to confirm the UTub named utub_name is active.

    Args:
        WebDriver open to U4I Home Page

    Returns:
        Boolean True, if new UTub was created
    """

    # Extract new UTub selector. Selector should be active.
    selector_utub = wait_then_get_element(browser, HPL.SELECTOR_SELECTED_UTUB)
    assert selector_utub is not None

    # Assert new UTub is now active and displayed to user
    class_attrib = selector_utub.get_attribute("class")
    assert class_attrib is not None
    assert "active" in class_attrib

    # Assert new UTub selector was created with input UTub Name
    assert selector_utub.text == utub_name

    current_url_deck_header = wait_then_get_element(browser, HPL.HEADER_URL_DECK)
    assert current_url_deck_header is not None

    # Assert new UTub name is displayed as the URL Deck header
    assert current_url_deck_header.text == utub_name
