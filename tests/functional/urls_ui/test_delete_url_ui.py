import random
from typing import Tuple

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from playwright.sync_api import Page, expect

from backend.cli.mock_constants import MOCK_URL_STRINGS
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.constants import STRINGS
from backend.utils.strings.trash_strs import TRASH_UI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.url_strs import (
    URL_MOVED_TO_TRASH_ONE,
    URL_REVIVED_FROM_TRASH,
    URL_REVIVED_LOST_TAGS_ONE,
)
from tests.functional.db_utils import (
    add_mock_urls,
    get_url_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import TrashPanelLocators as TrashPL
from tests.functional.playwright_assert_utils import (
    assert_active_utub,
    assert_login_with_username,
    assert_on_429_page,
    assert_tooltip_animates,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import (
    login_user_select_utub_by_id_and_url_by_id,
    login_user_select_utub_by_name_and_url_by_string,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    force_next_delete_ajax_failure_no_navigate,
    get_num_url_rows,
    invalidate_csrf_token_on_page,
    select_utub_by_id,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_in_focus,
)
from tests.functional.trash_ui.db_utils import (
    add_tag_to_url,
    delete_utub_tag,
    purge_utub_url_row,
)
from tests.functional.urls_ui.playwright_login_utils import (
    click_delete_on_selected_url,
    click_delete_on_selected_url_and_wait_for_toast,
    login_select_utub_select_url_click_delete,
)

pytestmark = pytest.mark.urls_ui


def _get_trash_count(*, page: Page) -> int:
    text = page.locator(TrashPL.SELECTOR_COUNT).inner_text()
    return int(text.strip("()"))


def _get_deck_url_ids(*, page: Page) -> list[str]:
    return page.eval_on_selector_all(
        HPL.ROWS_URLS, "rows => rows.map(row => row.getAttribute('utuburlid'))"
    )


def _get_utub_url_id(*, app: Flask, utub_name: str, url_string: str) -> int:
    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.name == utub_name).first()
        url: Urls = Urls.query.filter(Urls.url_string == url_string).first()
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub.id, Utub_Urls.url_id == url.id
        ).first()
        return utub_url.id


def test_delete_url_tooltip_animates(
    page: Page,
    create_test_urls,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests a tooltip showing when user hovers over the edit URL button .

    GIVEN a user has access to a URL
    WHEN the user hover over the edit URL button
    THEN ensure a tooltip is shown appropriately
    """

    _, _ = runner
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_url = get_url_in_utub(app, utub_id=utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=utub_url.id,
    )

    assert_tooltip_animates(
        page=page,
        parent_css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}",
        tooltip_parent_class=HPL.BUTTON_URL_DELETE,
        tooltip_text=STRINGS.DELETE_URL_TOOLTIP,
    )


def test_delete_url_moves_to_trash_and_shows_undo_toast(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests user's ability to delete a URL without a confirmation step

    GIVEN a user, selected UTub and selected URL
    WHEN the deleteURL button is clicked
    THEN the URL leaves the deck at once, no confirm modal appears, the undo toast
        reports it, focus moves to the next row and the Trash count goes up
    """
    user_id_for_test = 1

    login_user_select_utub_by_name_and_url_by_string(
        app=provide_app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=UTS.TEST_URL_STRING_CREATE,
    )

    css_selector = f'{HPL.URL_STRING_READ}[href="{UTS.TEST_URL_STRING_CREATE}"]'
    expect(page.locator(css_selector).first).to_be_attached()

    init_num_url_rows = get_num_url_rows(page=page)
    init_trash_count = _get_trash_count(page=page)
    deck_ids = _get_deck_url_ids(page=page)
    deleted_id = page.locator(HPL.ROW_SELECTED_URL).first.get_attribute("utuburlid")
    assert deleted_id is not None
    deleted_index = deck_ids.index(deleted_id)
    expected_focus_id = (
        deck_ids[deleted_index + 1]
        if deleted_index + 1 < len(deck_ids)
        else deck_ids[deleted_index - 1]
    )

    url_elem_to_delete = click_delete_on_selected_url_and_wait_for_toast(page=page)

    expect(page.locator(HPL.HOME_MODAL)).not_to_be_visible()
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_MOVED_TO_TRASH_ONE
    )

    # Wait for animation to complete
    wait_for_element_to_be_removed(page=page, locator=url_elem_to_delete)

    expect(page.locator(css_selector)).to_have_count(0)
    assert init_num_url_rows - 1 == get_num_url_rows(page=page)
    wait_until_in_focus(
        page=page, css_selector=f"{HPL.ROWS_URLS}[utuburlid='{expected_focus_id}']"
    )
    expect(page.locator(TrashPL.SELECTOR_COUNT)).to_have_text(
        f"({init_trash_count + 1})"
    )


def test_delete_url_undo_restores_row(page: Page, create_test_tags, provide_app: Flask):
    """
    Tests that Undo on the delete toast puts the URL back with its tags

    GIVEN a user who just deleted a tagged URL
    WHEN Undo is clicked on the toast
    THEN the row is back with the same tags, the toast reports the restore and the
        Trash count returns
    """
    user_id_for_test = 1

    login_user_select_utub_by_name_and_url_by_string(
        app=provide_app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=UTS.TEST_URL_STRING_CREATE,
    )
    deleted_id = page.locator(HPL.ROW_SELECTED_URL).first.get_attribute("utuburlid")
    assert deleted_id is not None
    row_selector = f"{HPL.ROWS_URLS}[utuburlid='{deleted_id}']"
    init_num_tags = page.locator(f"{row_selector} {HPL.TAG_BADGES}").count()
    assert init_num_tags > 0
    init_trash_count = _get_trash_count(page=page)
    init_num_url_rows = get_num_url_rows(page=page)

    url_elem_to_delete = click_delete_on_selected_url_and_wait_for_toast(page=page)
    wait_for_element_to_be_removed(page=page, locator=url_elem_to_delete)
    expect(page.locator(TrashPL.SELECTOR_COUNT)).to_have_text(
        f"({init_trash_count + 1})"
    )

    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)

    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_REVIVED_FROM_TRASH
    )
    expect(page.locator(row_selector)).to_have_count(1)
    expect(page.locator(f"{row_selector} {HPL.TAG_BADGES}")).to_have_count(
        init_num_tags
    )
    assert init_num_url_rows == get_num_url_rows(page=page)
    expect(page.locator(TrashPL.SELECTOR_COUNT)).to_have_text(f"({init_trash_count})")


def test_delete_url_dismiss_keeps_url_in_trash(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests that dismissing the delete toast leaves the URL in Trash

    GIVEN a user who just deleted a URL
    WHEN the toast's dismiss button is clicked
    THEN the toast hides, the row stays gone and the Trash count stays incremented
    """
    user_id_for_test = 1

    login_user_select_utub_by_name_and_url_by_string(
        app=provide_app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=UTS.TEST_URL_STRING_CREATE,
    )
    init_trash_count = _get_trash_count(page=page)
    init_num_url_rows = get_num_url_rows(page=page)

    url_elem_to_delete = click_delete_on_selected_url_and_wait_for_toast(page=page)
    wait_for_element_to_be_removed(page=page, locator=url_elem_to_delete)

    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_DISMISS)
    wait_until_hidden(page=page, css_selector=HPL.URL_OUTCOME_BANNER)

    assert init_num_url_rows - 1 == get_num_url_rows(page=page)
    expect(page.locator(TrashPL.SELECTOR_COUNT)).to_have_text(
        f"({init_trash_count + 1})"
    )


def test_delete_url_rate_limits(page: Page, create_test_urls, provide_app: Flask):
    """
    Tests user's ability to delete a URL when they are rate limited

    GIVEN a user, selected UTub and selected URL and they are rate limited
    WHEN the deleteURL button is clicked
    THEN ensure the 429 error page is shown
    """
    user_id_for_test = 1

    login_user_select_utub_by_name_and_url_by_string(
        app=provide_app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=UTS.TEST_URL_STRING_CREATE,
    )

    css_selector = f'{HPL.URL_STRING_READ}[href="{UTS.TEST_URL_STRING_CREATE}"]'
    expect(page.locator(css_selector).first).to_be_attached()

    add_forced_rate_limit_header(page=page)
    click_delete_on_selected_url(page=page)
    assert_on_429_page(page=page)


def test_delete_last_url(
    page: Page,
    runner: Tuple[Flask, FlaskCliRunner],
    create_test_utubs,
    provide_app: Flask,
):
    """
    Confirms site UI prompts user to create a URL when last URL is deleted.

    GIVEN a user has URLs
    WHEN all URLs are deleted
    THEN ensure the empty UTub prompts user to create a URL and takes focus.
    """
    _, cli_runner = runner

    random_url_to_add_as_last = random.sample(MOCK_URL_STRINGS, 1)[0]

    add_mock_urls(
        cli_runner,
        [
            random_url_to_add_as_last,
        ],
    )

    user_id_for_test = 1

    url_elem_to_delete = login_select_utub_select_url_click_delete(
        page=page,
        app=provide_app,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=random_url_to_add_as_last,
    )

    css_selector = f'{HPL.URL_STRING_READ}[href="{random_url_to_add_as_last}"]'
    wait_for_element_to_be_removed(page=page, locator=url_elem_to_delete)
    expect(page.locator(css_selector)).to_have_count(0)

    no_url_subheader = wait_then_get_element(
        page=page, css_selector=HPL.SUBHEADER_NO_URLS
    )
    expect(no_url_subheader).to_have_text(UTS.UTUB_NO_URLS)
    wait_until_in_focus(page=page, css_selector=HPL.EMPTY_STATE_NO_URLS)


def test_delete_url_invalid_csrf_token(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to attempt to delete a URL with an invalid CSRF token

    GIVEN a user attempting to delete a URL in a UTub
    WHEN the delete request is sent with an invalid CSRF token
    THEN ensure U4I responds with a proper error message
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)
        url_to_delete: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).first()
        url_string_to_delete = url_to_delete.standalone_url.url_string

    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=url_string_to_delete,
    )

    invalidate_csrf_token_on_page(page=page)
    click_delete_on_selected_url(page=page)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    # Page reloads after user clicks button in CSRF 403 error page
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    assert_login_with_username(page=page, username=user.username)

    # Reload will bring user back to the UTub they were in before
    assert_active_utub(page=page, utub_name=utub_user_created.name)


def test_delete_url_button_reenables_on_server_error(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests that the delete button re-enables after a server error so the user can retry.

    GIVEN a user with a selected URL
    WHEN the DELETE request fails with a 500 server error
    THEN the row is still present and its delete button is not aria-disabled
    """
    user_id_for_test = 1

    login_user_select_utub_by_name_and_url_by_string(
        app=provide_app,
        page=page,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=UTS.TEST_URL_STRING_CREATE,
    )
    selected_row = page.locator(HPL.ROW_SELECTED_URL).first
    selected_id = selected_row.get_attribute("utuburlid")

    # Force the next DELETE ajax call to fail (with early return to prevent navigation)
    force_next_delete_ajax_failure_no_navigate(page=page)

    click_delete_on_selected_url(page=page)

    delete_btn = page.locator(
        f"{HPL.ROWS_URLS}[utuburlid='{selected_id}'] {HPL.BUTTON_URL_DELETE}"
    )
    # Poll until the async failure handler clears aria-disabled
    expect(delete_btn).not_to_have_attribute("aria-disabled", "true")
    expect(page.locator(f"{HPL.ROWS_URLS}[utuburlid='{selected_id}']")).to_have_count(1)
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_count(0)


def test_deleting_second_url_replaces_toast(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests that a second delete leaves exactly one fresh toast

    GIVEN a user who deleted URL A and sees its toast
    WHEN they select URL B (which clears toast A) and delete it
    THEN exactly one fresh toast is visible and Undo restores only B
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        first_utub_url_id = utub_urls[0].id
        first_utub_url_string = utub_urls[0].standalone_url.url_string
        second_utub_url_id = utub_urls[1].id

    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
        url_string=first_utub_url_string,
    )
    first_row = click_delete_on_selected_url_and_wait_for_toast(page=page)
    wait_for_element_to_be_removed(page=page, locator=first_row)

    # Select the second URL and delete it too
    second_url_row_selector = f'{HPL.ROWS_URLS}[utuburlid="{second_utub_url_id}"]'
    wait_then_click_element(page=page, css_selector=second_url_row_selector)
    wait_until_hidden(page=page, css_selector=HPL.URL_OUTCOME_BANNER)
    second_row = click_delete_on_selected_url_and_wait_for_toast(page=page)
    wait_for_element_to_be_removed(page=page, locator=second_row)

    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_count(1)
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_MOVED_TO_TRASH_ONE
    )

    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)

    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_REVIVED_FROM_TRASH
    )
    expect(page.locator(second_url_row_selector)).to_have_count(1)
    expect(
        page.locator(f'{HPL.ROWS_URLS}[utuburlid="{first_utub_url_id}"]')
    ).to_have_count(0)


def test_delete_url_undo_after_purge_reports_not_in_trash(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests the stale Undo message

    GIVEN a user who deleted a URL
    WHEN the URL leaves Trash elsewhere (here: purged) and Undo is clicked
    THEN the toast says the item is no longer in Trash
    """
    app = provide_app
    user_id_for_test = 1
    utub_url_id = _get_utub_url_id(
        app=app, utub_name=UTS.TEST_UTUB_NAME_1, url_string=UTS.TEST_URL_STRING_CREATE
    )

    url_elem_to_delete = login_select_utub_select_url_click_delete(
        page=page,
        app=app,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=UTS.TEST_URL_STRING_CREATE,
    )
    wait_for_element_to_be_removed(page=page, locator=url_elem_to_delete)

    purge_utub_url_row(app, utub_url_id)
    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)

    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        TRASH_UI.NOT_IN_TRASH
    )
    expect(page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']")).to_have_count(0)


def test_delete_url_undo_reports_lost_tags(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests that Undo reports a tag deleted while the URL sat in Trash

    GIVEN a user who deleted a URL carrying one tag
    WHEN that UTub tag is deleted and Undo is clicked
    THEN the toast reports the lost tag
    """
    app = provide_app
    user_id_for_test = 1
    utub_url_id = _get_utub_url_id(
        app=app, utub_name=UTS.TEST_UTUB_NAME_1, url_string=UTS.TEST_URL_STRING_CREATE
    )
    with app.app_context():
        utub_id = Utub_Urls.query.get(utub_url_id).utub_id
    tag_id = add_tag_to_url(
        app, utub_id, utub_url_id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )

    url_elem_to_delete = login_select_utub_select_url_click_delete(
        page=page,
        app=app,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=UTS.TEST_URL_STRING_CREATE,
    )
    wait_for_element_to_be_removed(page=page, locator=url_elem_to_delete)

    delete_utub_tag(app, tag_id)
    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)

    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_REVIVED_LOST_TAGS_ONE
    )


def test_delete_toast_clears_on_utub_switch(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Tests that the delete toast does not outlive its UTub

    GIVEN a user who deleted a URL and sees the toast
    WHEN they switch to another UTub
    THEN the toast is cleared
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    with app.app_context():
        other_utub: Utubs = Utubs.query.filter(Utubs.id != utub_user_created.id).first()
        other_utub_id = other_utub.id

    url_elem_to_delete = login_select_utub_select_url_click_delete(
        page=page,
        app=app,
        user_id=user_id_for_test,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=UTS.TEST_URL_STRING_CREATE,
    )
    wait_for_element_to_be_removed(page=page, locator=url_elem_to_delete)
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_MOVED_TO_TRASH_ONE
    )

    select_utub_by_id(page=page, utub_id=other_utub_id)

    wait_until_hidden(page=page, css_selector=HPL.URL_OUTCOME_BANNER)
