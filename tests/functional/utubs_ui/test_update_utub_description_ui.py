from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.cli.mock_constants import MOCK_UTUB_DESCRIPTION
from backend.models.users import Users
from backend.models.utubs import Utubs
from backend.utils.constants import CONSTANTS
from backend.utils.strings.utub_strs import UTUB_FAILURE
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_login_with_username,
    assert_not_visible_css_selector,
    assert_on_429_page,
    assert_visible_css_selector,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    update_utub_to_empty_desc,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    clear_then_send_keys,
    invalidate_csrf_token_on_page,
    login_user_to_home_page,
    select_utub_by_id,
    select_utub_by_name,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_utub_name_appears,
    wait_until_visible,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.playwright_utils import (
    create_utub,
    open_update_utub_desc_input,
    update_utub_description,
    wait_for_add_utub_description_button,
)

pytestmark = pytest.mark.utubs_ui


def test_open_update_utub_description_input_creator(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    url_deck_subheader = wait_then_get_element(
        page=page, css_selector=HPL.SUBHEADER_URL_DECK
    )
    assert url_deck_subheader is not None
    utub_description = url_deck_subheader.inner_text()

    open_update_utub_desc_input(page=page)

    utub_description_update_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert utub_description_update_input is not None

    assert utub_description == utub_description_update_input.input_value()


def test_open_update_utub_description_hides_add_url_btn(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a user owns a UTub and the Add URL button is visible
    WHEN the user opens the description edit input
    THEN the Add URL button is hidden, and restored when the edit is cancelled
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE
    )

    open_update_utub_desc_input(page=page)

    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE
    )

    wait_then_click_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_CANCEL_UPDATE
    )

    wait_until_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE
    )
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)


def test_open_update_utub_description_input_member(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a fresh load of the U4I Home page
    WHEN a non-owner member selects a UTub
    THEN the UTub description does not have the editable class and clicking it does not open the edit input
    """
    app = provide_app
    user_id = 1
    utub = get_utub_this_user_did_not_create(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub.name
    )
    wait_until_utub_name_appears(page=page, utub_name=utub.name)

    utub_description = wait_then_get_element(
        page=page, css_selector=HPL.SUBHEADER_URL_DECK
    )
    class_attr = utub_description.get_attribute("class") or ""
    assert HPL.EDITABLE_CLASS not in class_attr

    utub_description.click()
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )


def test_switch_from_owned_to_non_owned_utub_removes_description_editable(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a user who owns one UTub and is a member of another
    WHEN the user selects their owned UTub, then switches to a non-owned UTub
    THEN the UTub description should lose the editable class and clicking it should not open the edit input
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    with app.app_context():
        utub_not_owned: Utubs = Utubs.query.filter(
            Utubs.utub_creator != user_id
        ).first()

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    utub_description = wait_then_get_element(
        page=page, css_selector=HPL.SUBHEADER_URL_DECK
    )
    class_attr = utub_description.get_attribute("class") or ""
    assert HPL.EDITABLE_CLASS in class_attr

    select_utub_by_name(page=page, utub_name=utub_not_owned.name)
    wait_until_utub_name_appears(page=page, utub_name=utub_not_owned.name)

    utub_description = wait_then_get_element(
        page=page, css_selector=HPL.SUBHEADER_URL_DECK
    )
    class_attr = utub_description.get_attribute("class") or ""
    assert HPL.EDITABLE_CLASS not in class_attr

    utub_description.click()
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )


def test_close_update_utub_description_input_btn(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_update_utub_desc_input(page=page)

    wait_then_click_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_CANCEL_UPDATE
    )

    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)


def test_close_update_utub_description_input_key(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_update_utub_desc_input(page=page)

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE)
    page.keyboard.press("Escape")

    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)


def test_update_utub_description_btn(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests a UTub owner's ability to update the selected UTub description.

    GIVEN a user is the UTub owner
    WHEN the utubDescriptionUpdate form is populated and submitted
    THEN ensure the new description is successfully added to the UTub.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    update_utub_description(page=page, utub_description=MOCK_UTUB_DESCRIPTION)

    # Submits new UTub description
    wait_then_click_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE
    )

    utub_description_elem = page.locator(HPL.SUBHEADER_URL_DECK)

    # Wait for POST request
    utub_description_elem = wait_until_visible(locator=utub_description_elem)
    assert utub_description_elem is not None
    assert utub_description_elem.inner_text() == MOCK_UTUB_DESCRIPTION


def test_update_utub_description_key(page: Page, create_test_utubs, provide_app: Flask):
    """
    Tests a UTub owner's ability to update the selected UTub description.

    GIVEN a user is the UTub owner
    WHEN the utubDescriptionUpdate form is populated and submitted
    THEN ensure the new description is successfully added to the UTub.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    update_utub_description(page=page, utub_description=MOCK_UTUB_DESCRIPTION)

    # Submits new UTub description
    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE)
    page.keyboard.press("Enter")

    utub_description_elem = page.locator(HPL.SUBHEADER_URL_DECK)

    # Wait for POST request
    utub_description_elem = wait_until_visible(locator=utub_description_elem)
    assert utub_description_elem is not None
    assert utub_description_elem.inner_text() == MOCK_UTUB_DESCRIPTION


def test_update_utub_description_rate_limits(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    update_utub_description(page=page, utub_description=MOCK_UTUB_DESCRIPTION)

    # Submits new UTub description
    add_forced_rate_limit_header(page=page)
    wait_then_click_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE
    )

    assert_on_429_page(page=page)


def test_update_utub_description_length_exceeded(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    new_utub_description = "a" * (CONSTANTS.UTUBS.MAX_DESCRIPTION_LENGTH + 1)

    update_utub_description(page=page, utub_description=new_utub_description)

    update_utub_description_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert update_utub_description_input is not None
    new_utub_description = update_utub_description_input.input_value()
    assert new_utub_description is not None

    assert len(new_utub_description) == CONSTANTS.UTUBS.MAX_DESCRIPTION_LENGTH


def test_update_utub_description_sanitized(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    update_utub_description(page=page, utub_description='<img src="evl.jpg">')

    # Submits new UTub description
    wait_then_click_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE
    )

    # Wait for POST request
    invalid_utub_desc_field = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_utub_desc_field is not None
    assert invalid_utub_desc_field.inner_text() == UTUB_FAILURE.INVALID_INPUT


def test_update_utub_description_to_empty(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    utub_description_elem = page.locator(HPL.SUBHEADER_URL_DECK)
    expect(utub_description_elem.first).to_be_visible()

    update_utub_description(page=page, utub_description="")

    utub_description_elem = page.locator(HPL.SUBHEADER_URL_DECK)
    expect(utub_description_elem.first).to_be_hidden()

    # Submits new UTub description
    wait_then_click_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE
    )

    # Wait until the submit button is hidden and then verify description is still hidden
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE)

    utub_description_elem = page.locator(HPL.SUBHEADER_URL_DECK)
    expect(utub_description_elem.first).to_be_hidden()


def test_update_empty_utub_description_btn_shows_after_updating_to_empty(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    update_utub_description(page=page, utub_description="")

    # Submits new UTub description
    wait_then_click_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE
    )

    # Wait until the submit button is hidden and then verify description is still hidden
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE)

    wait_for_add_utub_description_button(page=page)

    add_utub_desc = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY
    )
    assert add_utub_desc is not None


def test_update_empty_utub_description_btn_shows_after_selecting_utub(
    page: Page, create_test_utubmembers, provide_app: Flask
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
        app=app, page=page, user_id=user_id, utub_name=utub_user_did_not_create.name
    )
    select_utub_by_name(page=page, utub_name=utub_user_created.name)
    wait_until_utub_name_appears(page=page, utub_name=utub_user_created.name)

    wait_for_add_utub_description_button(page=page)

    add_utub_desc = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY
    )
    assert add_utub_desc is not None


def test_update_empty_utub_description_btn_shows_after_creating_utub(
    page: Page, create_test_users, provide_app: Flask
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
    login_user_to_home_page(app=app, page=page, user_id=user_id)
    create_utub(page=page, utub_name="UTub Name", utub_description="")
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE
    )

    wait_for_add_utub_description_button(page=page)

    add_utub_desc = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY
    )
    assert add_utub_desc is not None


def test_update_empty_utub_description_btn_opens_input(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    wait_for_add_utub_description_button(page=page)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY)

    utub_description_update_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert utub_description_update_input is not None

    assert utub_description_update_input.input_value() == ""


def test_update_empty_utub_description_updates_description_creator(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    wait_for_add_utub_description_button(page=page)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY)

    wait_until_visible_css_selector(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )

    update_utub_desc_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert update_utub_desc_input is not None

    clear_then_send_keys(locator=update_utub_desc_input, input_text=NEW_UTUB_DESC)

    # Submits new UTub description
    wait_then_click_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE
    )

    utub_description_elem = page.locator(HPL.SUBHEADER_URL_DECK)

    # Wait for POST request
    utub_description_elem = wait_until_visible(locator=utub_description_elem)
    assert utub_description_elem is not None
    assert utub_description_elem.inner_text() == NEW_UTUB_DESC


def test_update_empty_utub_description_shows_no_description_for_member(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests that a non-owner member sees the "No description" placeholder
    when the UTub has no description.

    GIVEN a user is a member (not owner) of a UTub with no description
    WHEN they select that UTub
    THEN ensure "No description" placeholder is visible and "Add a description?" button is not
    """
    app = provide_app
    user_id = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    update_utub_to_empty_desc(app, utub_user_member_of.id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_member_of.id
    )

    no_desc_label = wait_then_get_element(
        page=page, css_selector=HPL.LABEL_NO_DESCRIPTION
    )
    assert no_desc_label is not None
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY
    )


def test_update_utub_description_form_closes_when_selecting_other_utub(
    page: Page, create_test_utubmembers, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    open_update_utub_desc_input(page=page)

    utub_description_update_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert utub_description_update_input is not None

    select_utub_by_name(page=page, utub_name=utub_user_did_not_create.name)
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE)


def test_open_update_utub_description_btn_not_visible_with_no_utub_selected(
    page: Page, create_test_utubs, provide_app: Flask
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
    assert page.locator(HPL.SELECTOR_SELECTED_UTUB).count() == 0

    login_user_to_home_page(app=app, page=page, user_id=user_id)
    assert_login_with_username(page=page, username=username)

    utub_description = page.locator(HPL.SUBHEADER_URL_DECK)
    desc_classes = utub_description.get_attribute("class") or ""
    assert HPL.EDITABLE_CLASS not in desc_classes


def test_no_description_label_visible_on_member_utub_after_own_utub_with_no_description(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests that switching from an owned UTub with no description to a non-owned UTub
    with no description shows "No description" placeholder instead of "Add a description?" button.

    GIVEN a fresh load of the U4I Home page
    WHEN user selects a UTub they created with no description, then a UTub they do not own
        that has no description
    THEN ensure "No description" placeholder is visible and "Add a description?" button is not
    """
    app = provide_app
    user_id = 1

    utub_user_created = get_utub_this_user_created(app, user_id)
    update_utub_to_empty_desc(app, utub_user_created.id)

    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    update_utub_to_empty_desc(app, utub_user_member_of.id)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_created.id
    )

    select_utub_by_id(page=page, utub_id=utub_user_member_of.id)

    no_desc_label = wait_then_get_element(
        page=page, css_selector=HPL.LABEL_NO_DESCRIPTION
    )
    assert no_desc_label is not None
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY
    )


def test_update_utub_description_invalid_csrf_token(
    page: Page, create_test_utubs, provide_app: Flask
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

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    update_utub_description(page=page, utub_description=MOCK_UTUB_DESCRIPTION)
    invalidate_csrf_token_on_page(page=page)

    # Submits new UTub description
    wait_then_click_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DESCRIPTION_SUBMIT_UPDATE
    )

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    # Page reloads after user clicks button in CSRF 403 error page
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE)
    assert_login_with_username(page=page, username=username)
