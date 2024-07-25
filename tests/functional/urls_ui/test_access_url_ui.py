# External libraries
import pytest
from selenium.webdriver.common.by import By

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    get_selected_url,
    login_utub_url,
)


@pytest.mark.skip(reason="Test not yet implemented")
def test_access_url_by_button(browser, create_test_urls):
    """
    Tests a user's ability to navigate to a URL using the URLOptions button.

    GIVEN access to UTubs and URLs
    WHEN a user selects a URL and clicks 'Access URL' button
    THEN ensure the URL opens in a new tab
    """

    login_utub_url(browser)

    url_row = get_selected_url(browser)

    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_ACCESS).click()

    # Assert new tab is opened and navigated to url string


@pytest.mark.skip(reason="Test not yet implemented")
def test_access_url_by_text(browser, create_test_urls):
    """
    Tests a user's ability to navigate to a URL using the displayed URL string.

    GIVEN access to UTubs and URLs
    WHEN a user clicks the URL text
    THEN ensure the URL opens in a new tab
    """

    login_utub_url(browser)

    url_row = get_selected_url(browser)

    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_ACCESS).click()

    # Assert new tab is opened and navigated to url string
