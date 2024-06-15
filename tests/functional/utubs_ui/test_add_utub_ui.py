# External libraries
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Internal libraries
from src.mocks.mock_constants import UTUB_NAME_BASE
from tests.functional.utils_for_test import add_utub, wait_then_get_element


@pytest.mark.skip(reason="Testing another in isolation")
def test_add_utub(login_test_user):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    browser = login_test_user

    add_utub(browser, UTUB_NAME_BASE + "1")

    # Extract confirming result
    selector_UTub1 = WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".UTubSelector.active"))
    )

    # Assert new UTub selector was created with input UTub Name
    assert selector_UTub1.text == UTUB_NAME_BASE + "1"
    # Assert new UTub is now active and displayed to user
    assert "active" in selector_UTub1.get_attribute("class")


@pytest.mark.skip(reason="This test is not yet implemented")
def test_add_utub_name_length_exceeded(login_test_user):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    browser = login_test_user

    create_utub_btn = browser.find_element(By.ID, "createUTubBtn")
    create_utub_btn.click()

    utub_input = browser.find_element(By.ID, "createUTub")
    utub_input.clear()
    browser.implicitly_wait(2)  # Program reacts too fast, needs to take a beat
    utub_input.send_keys(UTUB_NAME_BASE)

    submit_utub_btn = browser.find_element(By.ID, "submitCreateUTub")
    submit_utub_btn.click()

    selector_UTub1 = browser.find_element(
        By.XPATH,
        "//div[@id='listUTubs']/div[@class='UTubSelector']/b[@class='UTubName']",
    )

    # Assert new UTub selector was created with input UTub Name
    assert selector_UTub1.text == UTUB_NAME_BASE + "1"
    assert selector_UTub1.getAttribute("class") == "active"


# @pytest.mark.skip(reason="This test is not yet implemented")
def test_add_utub_name_similar(create_test_utubs):
    """
    GIVEN a user trying to add a new UTub
    WHEN they submit the addUTub form
    THEN ensure the appropriate input field is shown and in focus
    """

    browser = create_test_utubs

    # Extract name of a pre-existing UTub
    first_UTub_selector = wait_then_get_element(browser, ".UTubSelector")
    utub_name = first_UTub_selector.get_attribute("innerText")

    # Attempt to add a new UTub with the same name
    add_utub(browser, utub_name)

    print(utub_name)

    # Extract modal body element
    confirmation_modal_body = wait_then_get_element(
        browser, "#confirmModalBody", False, 100
    )

    # Assert modal prompts user to consider duplicate UTub naming
    assert (
        confirmation_modal_body.text == "A UTub in your repository has a similar name."
    )
