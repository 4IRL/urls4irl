from flask import Flask
import pytest
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from locators import HomePageLocators as HPL
from src.cli.mock_constants import MOCK_UTUB_DESCRIPTION
from src.utils.constants import CONSTANTS
from tests.functional.utils_for_test import (
    assert_not_visible_css_selector,
    clear_then_send_keys,
    login_user_and_select_utub_by_name,
    login_user_to_home_page,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.utils_for_test_utub_ui import (
    create_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    hover_over_utub_title_to_show_add_utub_description,
    open_update_utub_desc_input,
    update_utub_description,
    update_utub_to_empty_desc,
)

pytestmark = pytest.mark.utubs_ui


def test_open_update_utub_description_input_creator(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to open the updateUTubDescription input using the pencil button.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub they created, then clicks the edit UTub description button
    THEN ensure the updateUTubDescription input opens
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)
    url_deck_subheader = wait_then_get_element(browser, HPL.SUBHEADER_URL_DECK)
    assert url_deck_subheader is not None
    utub_description = url_deck_subheader.text

    open_update_utub_desc_input(browser)

    utub_description_update_input = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert utub_description_update_input is not None

    assert utub_description_update_input.is_displayed()

    assert utub_description == utub_description_update_input.get_attribute("value")


def test_open_update_utub_description_input_member(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
):
    """
    Tests a user's ability to open the updateUTubName input using the pencil button.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub they did not create, then tries to click the edit UTub description button
    THEN ensure the updateUTubDescription button does not show
    """
    app = provide_app
    user_id = 1
    utub = get_utub_this_user_did_not_create(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub.name)

    # Javascript Exception is raised when selenium tries to hover over the UTub Name,
    # and then click on the edit UTub name button - but as a member, the button doesn't
    # show on hover
    with pytest.raises(JavascriptException):
        open_update_utub_desc_input(browser)

    assert_not_visible_css_selector(browser, HPL.BUTTON_UTUB_DESCRIPTION_UPDATE)


def test_close_update_utub_description_input_btn(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to close the updateUTubDescription input by clicking the 'x' button

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the updateUTubDescription input, then clicks the 'x'
    THEN ensure the updateUTubDescription input is closed
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    open_update_utub_desc_input(browser)

    wait_then_click_element(browser, HPL.BUTTON_UTUB_DESCRIPTION_CANCEL_UPDATE)

    update_utub_name_input = wait_until_hidden(browser, HPL.INPUT_UTUB_NAME_UPDATE, 5)

    assert not update_utub_name_input.is_displayed()


def test_close_update_utub_description_input_key(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to close the updateUTubDescription input by pressing the Escape key

    GIVEN a fresh load of the U4I Home page
    WHEN user opens the updateUTubDescription input, then presses 'Esc'
    THEN ensure the updateUTubDescription input is closed
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    open_update_utub_desc_input(browser)

    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    update_utub_name_input = wait_until_hidden(browser, HPL.INPUT_UTUB_NAME_UPDATE, 5)

    assert not update_utub_name_input.is_displayed()


def test_update_utub_description_btn(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update the selected UTub description.

    GIVEN a user is the UTub owner
    WHEN the utubDescriptionUpdate form is populated and submitted
    THEN ensure the new description is successfully added to the UTub.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    update_utub_description(browser, MOCK_UTUB_DESCRIPTION)

    # Submits new UTub description
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE)

    utub_description_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.SUBHEADER_URL_DECK
    )

    # Wait for POST request
    utub_description_elem = wait_until_visible(
        browser, utub_description_elem, timeout=3
    )
    assert utub_description_elem is not None
    assert utub_description_elem.text == MOCK_UTUB_DESCRIPTION


def test_update_utub_description_key(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update the selected UTub description.

    GIVEN a user is the UTub owner
    WHEN the utubDescriptionUpdate form is populated and submitted
    THEN ensure the new description is successfully added to the UTub.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    update_utub_description(browser, MOCK_UTUB_DESCRIPTION)

    # Submits new UTub description
    browser.switch_to.active_element.send_keys(Keys.ENTER)

    utub_description_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.SUBHEADER_URL_DECK
    )

    # Wait for POST request
    utub_description_elem = wait_until_visible(
        browser, utub_description_elem, timeout=3
    )
    assert utub_description_elem is not None
    assert utub_description_elem.text == MOCK_UTUB_DESCRIPTION


def test_update_utub_description_length_exceeded(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update a selected UTub's description.

    GIVEN a user owns a UTub
    WHEN they attempt to enter a UTub description that is too long
    THEN ensure the input field retains the max number of characters allowed.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    new_utub_description = "a" * (CONSTANTS.UTUBS.MAX_DESCRIPTION_LENGTH + 1)

    update_utub_description(browser, new_utub_description)

    update_utub_description_input = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert update_utub_description_input is not None
    new_utub_description = update_utub_description_input.get_attribute("value")
    assert new_utub_description is not None

    assert len(new_utub_description) == CONSTANTS.UTUBS.MAX_DESCRIPTION_LENGTH


def test_update_utub_description_to_empty(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update a selected UTub's description to an empty value

    GIVEN a user owns a UTub
    WHEN they attempt to enter a UTub description that is empty
    THEN ensure the description field remains hidden after updating
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    utub_description_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.SUBHEADER_URL_DECK
    )
    assert utub_description_elem.is_displayed()

    update_utub_description(browser, utub_description="")

    utub_description_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.SUBHEADER_URL_DECK
    )
    assert not utub_description_elem.is_displayed()

    # Submits new UTub description
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE)

    # Wait until the submit button is hidden and then verify description is still hidden
    wait_until_hidden(browser, HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE, timeout=3)

    utub_description_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.SUBHEADER_URL_DECK
    )
    assert not utub_description_elem.is_displayed()


def test_update_empty_utub_description_btn_shows_after_updating_to_empty(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to select the "Add UTub Description" button after
    updating the UTub description to an empty string

    GIVEN a user owns a UTub
    WHEN they attempt to add a UTub description after updating it to an empty string
    THEN ensure the Add UTub Description button shows
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    update_utub_description(browser, utub_description="")

    # Submits new UTub description
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE)

    # Wait until the submit button is hidden and then verify description is still hidden
    wait_until_hidden(browser, HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE, timeout=3)

    hover_over_utub_title_to_show_add_utub_description(browser)

    add_utub_desc = wait_then_get_element(browser, HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY)
    assert add_utub_desc is not None
    assert add_utub_desc.is_displayed()


def test_update_empty_utub_description_btn_shows_after_selecting_utub(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
):
    """
    Tests a UTub owner's ability to select the "Add UTub Description" button after
    updating the UTub description to an empty string

    GIVEN a user owns a UTub
    WHEN they attempt to add a UTub description after selecting a UTub with an empty description
    after having another UTub selected
    THEN ensure the Add UTub Description button shows
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    update_utub_to_empty_desc(app, utub_user_created.id)
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id)

    login_user_and_select_utub_by_name(
        app, browser, user_id, utub_user_did_not_create.name
    )
    select_utub_by_name(browser, utub_user_created.name)

    hover_over_utub_title_to_show_add_utub_description(browser)

    add_utub_desc = wait_then_get_element(browser, HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY)
    assert add_utub_desc is not None
    assert add_utub_desc.is_displayed()


def test_update_empty_utub_description_btn_shows_after_creating_utub(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    Tests a UTub owner's ability to select the "Add UTub Description" button after
    updating the UTub description to an empty string

    GIVEN a user owns a UTub
    WHEN they attempt to add a UTub description after creating a UTub with an empty name
    THEN ensure the Add UTub Description button shows
    """
    app = provide_app
    user_id = 1
    login_user_to_home_page(app, browser, user_id)
    create_utub(browser, utub_name="UTub Name", utub_description="")
    wait_then_click_element(browser, HPL.BUTTON_UTUB_SUBMIT_CREATE, time=3)
    wait_until_visible_css_selector(browser, HPL.BUTTON_CORNER_URL_CREATE, timeout=3)

    hover_over_utub_title_to_show_add_utub_description(browser)

    add_utub_desc = wait_then_get_element(browser, HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY)
    assert add_utub_desc is not None
    assert add_utub_desc.is_displayed()


def test_update_empty_utub_description_btn_opens_input(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to open UTub description input after the "Add UTub Description"button is shown when UTub description is empty

    GIVEN a user owns a UTub
    WHEN they attempt to add a UTub description after owning a UTub with an empty name
    THEN ensure the UTub Description input shows
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    update_utub_to_empty_desc(app, utub_user_created.id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    hover_over_utub_title_to_show_add_utub_description(browser)

    wait_then_click_element(browser, HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY, time=3)

    utub_description_update_input = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert utub_description_update_input is not None

    assert utub_description_update_input.is_displayed()

    assert "" == utub_description_update_input.get_attribute("value")


def test_update_empty_utub_description_updates_description(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update UTub description after it was empty

    GIVEN a user owns a UTub
    WHEN they attempt to add a UTub description after owning a UTub with an empty name
    THEN ensure the UTub Description is updated properly
    """
    NEW_UTUB_DESC = "My New UTub Description!"
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    update_utub_to_empty_desc(app, utub_user_created.id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    hover_over_utub_title_to_show_add_utub_description(browser)

    wait_then_click_element(browser, HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY, time=3)

    wait_until_visible_css_selector(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE, timeout=3
    )

    update_utub_desc_input = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE, time=3
    )
    assert update_utub_desc_input is not None

    clear_then_send_keys(update_utub_desc_input, NEW_UTUB_DESC)

    # Submits new UTub description
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE)

    utub_description_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.SUBHEADER_URL_DECK
    )

    # Wait for POST request
    utub_description_elem = wait_until_visible(
        browser, utub_description_elem, timeout=3
    )
    assert utub_description_elem is not None
    assert utub_description_elem.text == NEW_UTUB_DESC


def test_update_utub_description_form_closes_when_selecting_other_utub(
    browser: WebDriver, create_test_utubmembers, provide_app: Flask
):
    """
    Tests that UTub Description form closes between updates

    GIVEN a user owns a UTub
    WHEN they attempt to add a UTub description but then switches UTubs
    THEN ensure the UTub Description form is closed
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    open_update_utub_desc_input(browser)

    utub_description_update_input = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert utub_description_update_input is not None
    assert utub_description_update_input.is_displayed()

    select_utub_by_name(browser, utub_name=utub_user_did_not_create.name)
    utub_desc_update_input = wait_until_hidden(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE, timeout=3
    )

    assert not utub_desc_update_input.is_displayed()
