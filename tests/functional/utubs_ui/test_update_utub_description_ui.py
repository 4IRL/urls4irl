from flask import Flask
import pytest
from selenium.common.exceptions import ElementNotInteractableException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from locators import HomePageLocators as HPL
from src.cli.mock_constants import MOCK_UTUB_DESCRIPTION
from src.models.users import Users
from src.utils.constants import CONSTANTS
from src.utils.strings.utub_strs import UTUB_FAILURE
from tests.functional.assert_utils import (
    assert_login_with_username,
    assert_not_visible_css_selector,
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    update_utub_to_empty_desc,
)
from tests.functional.login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
    login_user_to_home_page,
)
from tests.functional.selenium_utils import (
    add_forced_rate_limit_header,
    clear_then_send_keys,
    invalidate_csrf_token_on_page,
    select_utub_by_id,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_update_btn_has_hidden_class,
    wait_until_utub_name_appears,
    wait_until_visible,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.selenium_utils import (
    create_utub,
    hover_over_utub_title_to_show_add_utub_description,
    open_update_utub_desc_input,
    update_utub_description,
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
    wait_until_utub_name_appears(browser, utub.name)
    wait_until_update_btn_has_hidden_class(browser, HPL.BUTTON_UTUB_DESCRIPTION_UPDATE)

    # ElementNotInteractableException is raised when selenium tries to hover over the UTub Name,
    # and then click on the edit UTub description button - but as a member, the button doesn't
    # show on hover
    with pytest.raises(ElementNotInteractableException):
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


def test_update_utub_description_rate_limits(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update the selected UTub description while rate limited.

    GIVEN a user is the UTub owner and they are rate limited
    WHEN the utubDescriptionUpdate form is populated and submitted
    THEN ensure the 429 error page is shown.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    update_utub_description(browser, MOCK_UTUB_DESCRIPTION)

    # Submits new UTub description
    add_forced_rate_limit_header(browser)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE)

    assert_on_429_page(browser)


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


def test_update_utub_description_sanitized(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update a selected UTub's description.

    GIVEN a user owns a UTub
    WHEN they attempt to enter a UTub description that is sanitized by the backend
    THEN ensure the input field retains the max number of characters allowed.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    update_utub_description(browser, utub_description='<img src="evl.jpg">')

    # Submits new UTub description
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE)

    # Wait for POST request
    invalid_utub_desc_field = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE + HPL.INVALID_FIELD_SUFFIX
    )
    assert invalid_utub_desc_field is not None
    assert invalid_utub_desc_field.text == UTUB_FAILURE.INVALID_INPUT


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
    wait_until_utub_name_appears(browser, utub_user_created.name)

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


def test_update_empty_utub_description_updates_description_creator(
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


def test_update_empty_utub_description_updates_description_member(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests a UTub owner's ability to update UTub description after it was empty

    GIVEN a user owns a UTub
    WHEN they attempt to add a UTub description after owning a UTub with an empty name
    THEN ensure the UTub Description is updated properly
    """
    app = provide_app
    user_id = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    update_utub_to_empty_desc(app, utub_user_member_of.id)

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_member_of.id)

    actions = ActionChains(browser)

    utub_title_elem = browser.find_element(By.CSS_SELECTOR, HPL.HEADER_URL_DECK)
    utub_desc_input_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY
    )

    # Exception raised since hovering over the element should not pop up the
    # empty UTub description update button
    with pytest.raises(ElementNotInteractableException):
        actions.move_to_element(utub_title_elem).pause(5).move_to_element(
            utub_desc_input_elem
        ).pause(5).perform()


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


def test_open_update_utub_description_btn_not_visible_with_no_utub_selected(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a user's ability to not see the update UTub description button when no UTub selected.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub they created, then clicks the edit UTub description button
    THEN ensure the updateUTubDescription input opens
    """
    app = provide_app
    user_id = 1
    with app.app_context():
        user: Users = Users.query.get(user_id)
        username = user.username
    selected_utub = wait_then_get_element(browser, HPL.SELECTOR_SELECTED_UTUB, time=3)
    assert selected_utub is None

    login_user_to_home_page(app, browser, user_id)
    assert_login_with_username(browser, username)

    update_utub_desc_btn = browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_UTUB_DESCRIPTION_UPDATE
    )
    assert not update_utub_desc_btn.is_displayed()


def test_open_update_utub_description_btn_not_visible_on_member_utub_after_own_utub_with_no_description(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests a user's ability to not see the update UTub description button when switching from a UTub
    they own with no description to switching to a UTub they do not own with no description.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub they created with no description, then a UTub they do not own
        that has no description
    THEN ensure the updateUTubDescription input does not open
    """
    app = provide_app
    user_id = 1

    utub_user_created = get_utub_this_user_created(app, user_id)
    update_utub_to_empty_desc(app, utub_user_created.id)

    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    update_utub_to_empty_desc(app, utub_user_member_of.id)

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    select_utub_by_id(browser, utub_user_member_of.id)

    actions = ActionChains(browser)

    utub_title_elem = browser.find_element(By.CSS_SELECTOR, HPL.HEADER_URL_DECK)
    utub_desc_input_elem = browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY
    )

    # Exception raised since hovering over the element should not pop up the
    # empty UTub description update button
    with pytest.raises(ElementNotInteractableException):
        actions.move_to_element(utub_title_elem).pause(5).move_to_element(
            utub_desc_input_elem
        ).pause(5).perform()


def test_update_utub_description_invalid_csrf_token(
    browser: WebDriver, create_test_utubs, provide_app: Flask
):
    """
    Tests a UTub owner's ability to attempt to update the selected UTub description with an invalid CSRF token

    GIVEN a user is the UTub owner
    WHEN the utubDescriptionUpdate form is populated and submitted with an invalid CSRF token
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    user_id = 1
    with app.app_context():
        user: Users = Users.query.get(user_id)
        username = user.username
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(app, browser, user_id, utub_user_created.name)

    update_utub_description(browser, MOCK_UTUB_DESCRIPTION)
    invalidate_csrf_token_on_page(browser)

    # Submits new UTub description
    wait_then_click_element(browser, HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE)

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    update_utub_desc_input = wait_until_hidden(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE, timeout=3
    )
    assert not update_utub_desc_input.is_displayed()
    assert_login_with_username(browser, username)
