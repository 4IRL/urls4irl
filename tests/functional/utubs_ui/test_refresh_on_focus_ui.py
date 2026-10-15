import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.utub_strs import UTUB_SELECT
from tests.functional.db_utils import (
    add_url_to_utub_as_other_member,
    get_other_member_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    remove_user_from_utub,
    set_utub_locked_state,
    update_utub_name_and_description,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_panel_visibility_mobile
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    get_all_url_ids_in_selected_utub,
    open_update_url_title,
    wait_then_click_element,
)

pytestmark = pytest.mark.utubs_ui

USER_ID_FOR_TEST = 1

# Longer than UTUB_REFRESH_MIN_INTERVAL_MS (30_000) so the next refocus is due.
REFRESH_INTERVAL_PASSED_MS = 31_000
# Real-time pause (page.wait_for_timeout is not affected by page.clock) used
# only to prove a refresh request did NOT happen; every such test first
# observes a request elsewhere so a dead counter cannot pass vacuously.
SETTLE_MS = 500

RENAMED_UTUB_NAME = "Renamed By Other"
RENAMED_UTUB_NAME_SECOND = "Renamed By Other Again"
NEW_URL_STRING = "https://refresh-on-focus.example.com/"
NEW_URL_TITLE = "Refresh On Focus New URL"


def _track_refresh_requests(*, page: Page, utub_id: int) -> list[str]:
    refresh_suffix = f"/utubs/{utub_id}/refresh"
    seen: list[str] = []
    page.on(
        "request",
        lambda request: (
            seen.append(request.url) if request.url.endswith(refresh_suffix) else None
        ),
    )
    return seen


def _is_refresh_request(*, utub_id: int):
    refresh_suffix = f"/utubs/{utub_id}/refresh"
    return lambda request: request.url.endswith(refresh_suffix)


def _refocus(*, page: Page) -> None:
    # A synthetic visibilitychange keeps visibilityState "visible" in headless
    # Chromium, so the window blur -> focus pair is the portable trigger.
    page.evaluate(
        """() => {
            window.dispatchEvent(new Event('blur'));
            window.dispatchEvent(new Event('focus'));
        }"""
    )


def _login_with_clock(*, app: Flask, page: Page, utub_id: int) -> None:
    page.clock.install()
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )


def test_refresh_on_focus_shows_utub_rename_from_other_member(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member viewing a UTub
    WHEN another member renames the UTub and the viewer returns to the tab
    THEN the deck header and active sidebar entry show the new name, the URL is
        unchanged and no loading ring is shown
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    _login_with_clock(app=app, page=page, utub_id=utub.id)
    url_before = page.url

    update_utub_name_and_description(
        app, utub.id, RENAMED_UTUB_NAME, utub.utub_description or ""
    )
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    _refocus(page=page)

    expect(page.locator(HPL.HEADER_URL_DECK)).to_have_text(RENAMED_UTUB_NAME)
    expect(
        page.locator(f"{HPL.SELECTOR_SELECTED_UTUB} {HPL.SELECTORS_UTUB_NAME}")
    ).to_have_text(RENAMED_UTUB_NAME)
    assert page.url == url_before
    expect(page.locator(HPL.MEMBER_COMBOBOX_LOADING_RING)).to_have_count(0)


def test_refresh_on_focus_shows_new_url_from_other_member_first(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member viewing a UTub
    WHEN another member adds a URL and the viewer returns to the tab
    THEN a new URL row appears and, under the default newest-first sort, is the
        first row in the list
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    other_member = get_other_member_in_utub(app, utub.id, USER_ID_FOR_TEST)
    _login_with_clock(app=app, page=page, utub_id=utub.id)
    count_before = page.locator(HPL.ROWS_URLS).count()

    new_utub_url_id = add_url_to_utub_as_other_member(
        app, utub.id, other_member.id, NEW_URL_STRING, NEW_URL_TITLE
    )
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    _refocus(page=page)

    expect(page.locator(HPL.ROWS_URLS)).to_have_count(count_before + 1)
    expect(
        page.locator(f"{HPL.ROWS_URLS}[utuburlid='{new_utub_url_id}']")
    ).to_be_visible()
    first_row = page.locator(f"{HPL.LIST_URL} {HPL.ROWS_URLS}").first
    expect(first_row).to_have_attribute("utuburlid", str(new_utub_url_id))


def test_refresh_on_focus_applies_utub_lock_from_other_member(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member viewing an unlocked UTub
    WHEN it is locked elsewhere and the viewer returns to the tab
    THEN the body gains the utub-locked class
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    _login_with_clock(app=app, page=page, utub_id=utub.id)
    expect(page.locator("body")).not_to_have_class(re.compile(r"\butub-locked\b"))

    set_utub_locked_state(app, utub.id, True)
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    _refocus(page=page)

    expect(page.locator("body")).to_have_class(re.compile(r"\butub-locked\b"))


def test_refresh_on_focus_is_debounced(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member whose first refocus after the interval refreshed the UTub
    WHEN they refocus again immediately, without the interval passing
    THEN no second refresh request is made and a newer remote change is not applied
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    _login_with_clock(app=app, page=page, utub_id=utub.id)
    requests_seen = _track_refresh_requests(page=page, utub_id=utub.id)

    update_utub_name_and_description(
        app, utub.id, RENAMED_UTUB_NAME, utub.utub_description or ""
    )
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    with page.expect_request(_is_refresh_request(utub_id=utub.id)):
        _refocus(page=page)
    # The applied rename proves the first response has been handled.
    expect(page.locator(HPL.HEADER_URL_DECK)).to_have_text(RENAMED_UTUB_NAME)
    assert len(requests_seen) == 1

    update_utub_name_and_description(
        app, utub.id, RENAMED_UTUB_NAME_SECOND, utub.utub_description or ""
    )
    _refocus(page=page)
    page.wait_for_timeout(SETTLE_MS)

    assert len(requests_seen) == 1
    expect(page.locator(HPL.HEADER_URL_DECK)).to_have_text(RENAMED_UTUB_NAME)


def test_refresh_on_focus_skipped_while_url_title_form_open(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member with the URL title edit form open and text typed into it
    WHEN they refocus after the interval
    THEN no refresh request is made and the typed text is preserved; once the form
        is cancelled, the next refocus makes exactly one request
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    _login_with_clock(app=app, page=page, utub_id=utub.id)
    requests_seen = _track_refresh_requests(page=page, utub_id=utub.id)

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 1
    url_row = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{url_ids[0]}']")
    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROWS_URLS}[utuburlid='{url_ids[0]}']"
    )
    open_update_url_title(page=page, selected_url_row=url_row)
    title_input = url_row.locator(HPL.INPUT_URL_TITLE_UPDATE)
    typed_text = "Typed while busy"
    title_input.fill(typed_text)

    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    _refocus(page=page)
    page.wait_for_timeout(SETTLE_MS)

    assert len(requests_seen) == 0
    expect(title_input).to_have_value(typed_text)

    url_row.locator(HPL.BUTTON_URL_TITLE_CANCEL_UPDATE).click()
    expect(title_input).not_to_be_visible()
    with page.expect_request(_is_refresh_request(utub_id=utub.id)):
        _refocus(page=page)
    page.wait_for_timeout(SETTLE_MS)
    assert len(requests_seen) == 1


def test_refresh_on_focus_removed_member_sees_utub_gone(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a member viewing a UTub they did not create
    WHEN they are removed from it and return to the tab
    THEN the UTub disappears from the sidebar, the URL deck shows the no-UTub state
        and the not-available banner, and the page stays on /home
    """
    app = provide_app
    utub = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST)
    _login_with_clock(app=app, page=page, utub_id=utub.id)

    remove_user_from_utub(app, USER_ID_FOR_TEST, utub.id)
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    _refocus(page=page)

    expect(page.locator(f"{HPL.SELECTORS_UTUB}[utubid='{utub.id}']")).to_have_count(0)
    expect(page.locator(HPL.URL_DECK_ERROR_INDICATOR)).to_have_text(
        UTS.UTUB_NO_LONGER_AVAILABLE
    )
    expect(page.locator(HPL.SUBHEADER_URL_DECK)).to_have_text(UTUB_SELECT)
    expect(page.locator(HPL.ROWS_URLS)).to_have_count(0)
    expect(page.locator(HPL.ERROR_PAGE_HANDLER)).to_have_count(0)
    assert page.url.rstrip("/").endswith("/home")


def test_refresh_on_focus_removed_member_lands_on_utubs_panel_mobile(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a member on mobile viewing a UTub they did not create
    WHEN they are removed from it and return to the app
    THEN the UTubs panel is shown and the live region announces the UTub is gone
    """
    app = provide_app
    page = page_mobile_portrait
    utub = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST)
    page.clock.install()
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    remove_user_from_utub(app, USER_ID_FOR_TEST, utub.id)
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    _refocus(page=page)

    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)
    expect(page.locator(HPL.MOBILE_PANEL_ANNOUNCEMENT)).to_have_text(
        UTS.UTUB_NO_LONGER_AVAILABLE
    )
