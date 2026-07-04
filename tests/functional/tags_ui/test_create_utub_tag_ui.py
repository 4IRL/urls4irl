from flask import Flask
import pytest
from playwright.sync_api import Page

from backend.models.users import Users
from backend.models.utub_tags import Utub_Tags
from backend.models.utubs import Utubs
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR
from backend.utils.strings.tag_strs import TAGS_FAILURE
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    count_urls_with_tag_applied_by_tag_string,
    get_tag_in_utub_by_tag_string,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_login_with_username,
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_select_utub_by_id_open_create_utub_tag,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    invalidate_csrf_token_on_page,
    set_focus_on_element,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
)
from tests.functional.tags_ui.playwright_assert_utils import (
    assert_create_utub_tag_input_form_is_hidden,
    assert_create_utub_tag_input_form_is_shown,
    assert_new_utub_tag_created,
)
from tests.functional.tags_ui.playwright_utils import (
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
)

pytestmark = pytest.mark.tags_ui


def test_open_input_create_utub_tag(page: Page, create_test_tags, provide_app: Flask):
    """
    Tests ability to open the create UTub tag form

    GIVEN a user is a UTub member and has selected the UTub
    WHEN the user clicks on the create UTub tag plus button
    THEN ensure the createUTubTag form is opened
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_CREATE)
    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)

    assert_create_utub_tag_input_form_is_shown(page=page)


def test_open_input_create_utub_tag_tab_focus(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests ability to open the create UTub tag form

    GIVEN a user is a UTub member and has selected the UTub
    WHEN the user tabs to the create UTub tag plus button
    THEN ensure the createUTubTag form is opened
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    create_utub_tag_btn = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_UTUB_TAG_CREATE
    )
    assert create_utub_tag_btn is not None

    set_focus_on_element(page=page, locator=create_utub_tag_btn)
    create_utub_tag_btn.press("Enter")

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)

    assert_create_utub_tag_input_form_is_shown(page=page)


def test_open_input_create_utub_tag_click_cancel_btn(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests ability to close the create UTub tag form by clicking cancel button

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user clicks on the cancel button
    THEN ensure the createUTubTag form is closed
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_select_utub_by_id_open_create_utub_tag(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_CANCEL_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_UTUB_TAG_CANCEL_CREATE)
    assert_create_utub_tag_input_form_is_hidden(page=page)


def test_open_input_create_utub_tag_press_esc_key(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests ability to close the create UTub tag form by pressing Escape

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the escape key while focused on the input field
    THEN ensure the createUTubTag form is closed
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_select_utub_by_id_open_create_utub_tag(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    page.keyboard.press("Escape")
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_UTUB_TAG_CANCEL_CREATE)
    assert_create_utub_tag_input_form_is_hidden(page=page)


def test_open_input_create_utub_tag_click_submit_btn(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests ability to add a new tag to the UTub

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button after typing in a new UTub tag
    THEN ensure the createUTubTag form is closed and the new UTub tag is added
    """
    app = provide_app
    user_id_for_test = 1
    new_tag = "WOWZA123"
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == UTS.TEST_UTUB_NAME_1).first()
        init_num_of_utub_tags = len(utub.utub_tags)

        # Count urls with new tag in UTub. Should be 0.
        init_tag_count_in_utub: int = count_urls_with_tag_applied_by_tag_string(
            app, utub.id, new_tag
        )

    login_user_select_utub_by_id_open_create_utub_tag(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    page.keyboard.type(new_tag)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    assert_create_utub_tag_input_form_is_hidden(page=page)
    assert_new_utub_tag_created(
        page=page, new_tag_str=new_tag, init_utub_tag_count=init_num_of_utub_tags
    )

    # Assert Tag Deck counter initialized at 0
    utub_tag = get_tag_in_utub_by_tag_string(app, utub_user_created.id, new_tag)
    utub_tag_selector = f'{HPL.TAG_FILTERS}[data-utub-tag-id="{utub_tag.id}"]'
    utub_tag_elem = wait_then_get_element(page=page, css_selector=utub_tag_selector)
    assert utub_tag_elem

    visible_urls, total_urls = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=utub_tag.id
    )
    assert visible_urls == 0
    assert total_urls == init_tag_count_in_utub


def test_open_input_create_utub_tag_press_enter_key(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests ability to add a new tag to the UTub

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the enter key after typing in a new UTub tag and focused on input
    THEN ensure the createUTubTag form is closed and the new UTub tag is added
    """
    app = provide_app
    user_id_for_test = 1
    new_tag = "WOWZA123"
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == UTS.TEST_UTUB_NAME_1).first()
        init_num_of_utub_tags = len(utub.utub_tags)

        # Count urls with new tag in UTub. Should be 0.
        init_tag_count_in_utub: int = count_urls_with_tag_applied_by_tag_string(
            app, utub.id, new_tag
        )

    login_user_select_utub_by_id_open_create_utub_tag(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    page.keyboard.type(new_tag)
    page.keyboard.press("Enter")
    wait_until_hidden(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    assert_create_utub_tag_input_form_is_hidden(page=page)
    assert_new_utub_tag_created(
        page=page, new_tag_str=new_tag, init_utub_tag_count=init_num_of_utub_tags
    )

    # Assert Tag Deck counter initialized at 0
    utub_tag = get_tag_in_utub_by_tag_string(app, utub_user_created.id, new_tag)
    utub_tag_selector = f'{HPL.TAG_FILTERS}[data-utub-tag-id="{utub_tag.id}"]'
    utub_tag_elem = wait_then_get_element(page=page, css_selector=utub_tag_selector)
    assert utub_tag_elem

    visible_urls, total_urls = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=utub_tag.id
    )
    assert visible_urls == 0
    assert total_urls == init_tag_count_in_utub


def test_open_input_create_utub_tag_rate_limits(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests ability to add a new tag to the UTub and user is rate limited

    GIVEN a user is a UTub member, has selected the UTub, opens the create UTub tag form, and user is rate limited
    WHEN the user presses the submit button after typing in a new UTub tag
    THEN ensure the 429 error page is shown
    """
    app = provide_app
    user_id_for_test = 1
    new_tag = "WOWZA123"
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_select_utub_by_id_open_create_utub_tag(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    page.keyboard.type(new_tag)

    add_forced_rate_limit_header(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    assert_on_429_page(page=page)


def test_create_utub_tag_empty_field(page: Page, create_test_tags, provide_app: Flask):
    """
    Tests ability to attempt to add a new tag to the UTub with an empty tag field

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button after not typing in a tag
    THEN ensure U4I provides the proper error response to the user
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_select_utub_by_id_open_create_utub_tag(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    invalid_utub_tag_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_UTUB_TAG_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_utub_tag_error is not None
    assert invalid_utub_tag_error.inner_text() == FIELD_REQUIRED_STR


def test_create_utub_tag_duplicate_tag(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests ability to attempt to add a duplicate tag to the UTub

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button after typing in a tag that is already in this UTub
    THEN ensure U4I provides the proper error response to the user
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    with app.app_context():
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_created.id
        ).first()
        utub_tag_duplicate = utub_tag.tag_string

    login_user_select_utub_by_id_open_create_utub_tag(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    page.keyboard.type(utub_tag_duplicate)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    invalid_utub_tag_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_UTUB_TAG_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_utub_tag_error is not None
    assert invalid_utub_tag_error.inner_text() == TAGS_FAILURE.TAG_ALREADY_IN_UTUB


def test_create_utub_tag_tag_with_whitespace(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests ability to attempt to add a duplicate tag to the UTub with surrounding whitespace

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button after typing in a tag that is already in this UTub
         wrapped with whitespace
    THEN ensure U4I provides the proper error response to the user
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    with app.app_context():
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_created.id
        ).first()
        utub_tag_duplicate = utub_tag.tag_string

    login_user_select_utub_by_id_open_create_utub_tag(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    page.keyboard.type(f" {utub_tag_duplicate} ")
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    invalid_utub_tag_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_UTUB_TAG_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_utub_tag_error is not None
    assert invalid_utub_tag_error.inner_text() == TAGS_FAILURE.TAG_ALREADY_IN_UTUB


def test_create_utub_tag_sanitized_tag(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests ability to attempt to add a tag to the UTub that contains improper or unsanitized inputs

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button after typing in a tag that contains improper or unsanitized inputs
    THEN ensure U4I provides the proper error response to the user
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_select_utub_by_id_open_create_utub_tag(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    page.keyboard.type('<img src="evl.jpg">')
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    invalid_utub_tag_error = wait_then_get_element(
        page=page,
        css_selector=HPL.INPUT_UTUB_TAG_CREATE + HPL.INVALID_FIELD_SUFFIX,
    )
    assert invalid_utub_tag_error is not None
    assert invalid_utub_tag_error.inner_text() == TAGS_FAILURE.INVALID_INPUT


def test_create_utub_tag_invalid_csrf(page: Page, create_test_tags, provide_app: Flask):
    """
    Tests ability to attempt to add a tag to the UTub with an invalid csrf token

    GIVEN a user is a UTub member, has selected the UTub, and opens the create UTub tag form
    WHEN the user presses the submit button with an invalid csrf token
    THEN ensure U4I provides the proper error response to the user
    """
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)

    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_select_utub_by_id_open_create_utub_tag(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    wait_until_in_focus(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    page.keyboard.type("New tag123")
    invalidate_csrf_token_on_page(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)
    wait_until_hidden(page=page, css_selector=HPL.INPUT_UTUB_TAG_CREATE)
    assert_login_with_username(page=page, username=user.username)
