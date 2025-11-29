from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)

from tests.functional.locators import HomePageLocators as HPL


def assert_elems_hidden_after_utub_deleted(browser: WebDriver):
    non_visible_elems = (
        HPL.BUTTON_UTUB_DELETE,
        HPL.BUTTON_MEMBER_CREATE,
        HPL.BUTTON_UTUB_TAG_CREATE,
        HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN,
        HPL.BUTTON_UNSELECT_ALL,
        HPL.BUTTON_CORNER_URL_CREATE,
        HPL.SUBHEADER_TAG_DECK,
    )

    for elem in non_visible_elems:
        assert not browser.find_element(By.CSS_SELECTOR, elem).is_displayed()

    update_utub_desc_btn = browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_UTUB_DESCRIPTION_UPDATE
    )
    assert HPL.HIDDEN_BTN_CLASS in update_utub_desc_btn.get_dom_attribute("class")

    update_utub_name_btn = browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_UTUB_NAME_UPDATE
    )
    assert (
        HPL.HIDDEN_BTN_CLASS in update_utub_name_btn.get_dom_attribute("class")
        or not update_utub_name_btn.is_displayed()
    )


def assert_in_created_utub(browser: WebDriver):
    assert_visible_css_selector(browser, HPL.BUTTON_MEMBER_CREATE)
    assert_visible_css_selector(browser, HPL.BUTTON_UTUB_DELETE)
    assert_visible_css_selector(browser, HPL.BUTTON_UTUB_CREATE)
    assert_not_visible_css_selector(browser, HPL.BUTTON_UTUB_LEAVE)
    assert_visible_css_selector(browser, HPL.BUTTON_UTUB_TAG_CREATE)
    assert_visible_css_selector(browser, HPL.BUTTON_UNSELECT_ALL)
    assert_visible_css_selector(browser, HPL.BUTTON_CORNER_URL_CREATE)


def assert_in_member_utub(browser: WebDriver):
    assert_not_visible_css_selector(browser, HPL.BUTTON_MEMBER_CREATE)
    assert_not_visible_css_selector(browser, HPL.BUTTON_UTUB_DELETE)
    assert_visible_css_selector(browser, HPL.BUTTON_UTUB_CREATE)
    assert_visible_css_selector(browser, HPL.BUTTON_UTUB_LEAVE)
    assert_visible_css_selector(browser, HPL.BUTTON_UTUB_TAG_CREATE)
    assert_visible_css_selector(browser, HPL.BUTTON_UNSELECT_ALL)
    assert_visible_css_selector(browser, HPL.BUTTON_CORNER_URL_CREATE)
