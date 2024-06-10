# External libraries
import pytest
from selenium.webdriver.common.by import By

# Internal libraries
import constants as const
from tests.functional.utils import (
    click_and_wait,
    find_element_by_css_selector,
    send_keys_to_input_field,
)


# @pytest.mark.skip(reason="This test is not yet implemented")
def test_add_utub(browser):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    create_utub_btn = find_element_by_css_selector(browser, "#createUTubBtn")
    create_utub_btn.click()

    send_keys_to_input_field(browser, "#createUTub", const.TEST_UTUB_NAME)

    click_and_wait(browser, "#submitCreateUTub", 1)

    selector_UTub1 = browser.find_element(
        By.XPATH,
        "//div[@id='listUTubs']/div[@class='UTubSelector']/b[@class='UTubName']",
    )

    # Assert new UTub selector was created with input UTub Name
    assert selector_UTub1.text == const.TEST_UTUB_NAME
    assert selector_UTub1.getAttribute("class") == "active"


@pytest.mark.skip(reason="This test is not yet implemented")
def test_add_utub_name_length_exceeded(browser):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    create_utub_btn = browser.find_element(By.ID, "createUTubBtn")
    create_utub_btn.click()

    utub_input = browser.find_element(By.ID, "createUTub")
    utub_input.clear()
    browser.implicitly_wait(2)  # Program reacts too fast, needs to take a beat
    utub_input.send_keys(const.UTUB_NAME)

    submit_utub_btn = browser.find_element(By.ID, "submitCreateUTub")
    submit_utub_btn.click()

    selector_UTub1 = browser.find_element(
        By.XPATH,
        "//div[@id='listUTubs']/div[@class='UTubSelector']/b[@class='UTubName']",
    )

    # Assert new UTub selector was created with input UTub Name
    assert selector_UTub1.text == const.UTUB_NAME
    assert selector_UTub1.getAttribute("class") == "active"


@pytest.mark.skip(reason="This test is not yet implemented")
def test_add_utub_name_similar(browser):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    create_utub_btn = browser.find_element(By.ID, "createUTubBtn")
    create_utub_btn.click()

    utub_input = browser.find_element(By.ID, "createUTub")
    utub_input.clear()
    browser.implicitly_wait(2)  # Program reacts too fast, needs to take a beat
    utub_input.send_keys(const.UTUB_NAME)

    submit_utub_btn = browser.find_element(By.ID, "submitCreateUTub")
    submit_utub_btn.click()

    selector_UTub1 = browser.find_element(
        By.XPATH,
        "//div[@id='listUTubs']/div[@class='UTubSelector']/b[@class='UTubName']",
    )

    # Assert new UTub selector was created with input UTub Name
    assert selector_UTub1.text == const.UTUB_NAME
    assert selector_UTub1.getAttribute("class") == "active"
