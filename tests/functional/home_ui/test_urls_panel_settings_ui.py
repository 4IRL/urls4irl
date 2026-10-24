from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from playwright.sync_api import Page, expect

from backend.models.utub_members import Member_Role
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from backend.utils.strings.utub_strs import (
    PANEL_SETTINGS_MANAGERS_ONLY,
    PANEL_SETTINGS_SAVED,
    URLS_SETTINGS_SELECTOR_RESTORED,
)
from tests.functional.db_utils import (
    add_mock_urls,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    set_member_role_in_utub,
    set_utub_settings,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_select_utub_by_name_and_url_by_string,
)
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    get_selected_url,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.urls_ui.playwright_utils import (
    expect_selected_scheme,
    wait_for_update_input_highlight,
)

pytestmark = pytest.mark.home_ui

USER_ID_FOR_TEST = 1

_HIDE_ON_HTTPS = {"urls": {"default_url_scheme": "https", "hide_scheme_selector": True}}
_HTTPS_PREFIX = "https://"
_STORED_FTP_URL = "ftp://files.example.com/a"


def _login_to_owned_utub(*, app: Flask, page: Page) -> int:
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    return utub_id


def _open_urls_settings(*, page: Page) -> None:
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SETTINGS_GEAR)
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_visible()


def _pick_default_scheme(*, page: Page, scheme: str) -> None:
    """Pick ``scheme`` in the settings popover's default-scheme picker."""
    page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME).click()
    listbox = page.locator(HPL.URLS_SETTINGS_SCHEME_LISTBOX)
    expect(listbox).to_be_visible()
    page.locator(HPL.URLS_SETTINGS_SCHEME_FILTER).fill(scheme)
    option = page.locator(
        f"{HPL.PANEL_SETTINGS_POPOVER} "
        + HPL.SCHEME_OPTION_BY_SCHEME_FORMAT.format(scheme=scheme)
    )
    expect(option).to_be_visible()
    option.click()
    expect(listbox).to_be_hidden()


def _close_settings_popover(*, page: Page) -> None:
    """Escape with the list closed closes the popover (focus is on the control)."""
    page.keyboard.press("Escape")
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_hidden()


def _open_create_form(*, page: Page) -> None:
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)
    expect(page.locator(HPL.WRAP_URL_CREATE)).to_be_visible()


def _fill_create_form(*, page: Page, url_string: str) -> None:
    clear_then_send_keys(
        locator=page.locator(HPL.INPUT_URL_TITLE_CREATE), input_text="Settings URL"
    )
    clear_then_send_keys(
        locator=page.locator(HPL.INPUT_URL_STRING_CREATE), input_text=url_string
    )


def _submit_create_form(*, page: Page) -> None:
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)
    wait_until_hidden(page=page, css_selector=HPL.INPUT_URL_STRING_CREATE)
    expect(page.locator(HPL.WRAP_URL_CREATE)).to_be_hidden()


def _expect_url_card_with_href_prefix(*, page: Page, href_prefix: str) -> None:
    expect(
        page.locator(
            f"{HPL.ROWS_URLS} {HPL.URL_STRING_READ}"
            f"[{HPL.URL_STRING_IN_DATA}^='{href_prefix}']"
        )
    ).to_have_count(1)


def _open_edit_form_for_stored_url(*, app: Flask, page: Page, stored_url: str) -> None:
    login_user_select_utub_by_name_and_url_by_string(
        app=app,
        page=page,
        user_id=USER_ID_FOR_TEST,
        utub_name=UTS.TEST_UTUB_NAME_1,
        url_string=stored_url,
    )
    get_selected_url(page=page)
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}",
    )
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.INPUT_URL_STRING_UPDATE_SELECTED
    )
    # The form re-focuses and selects its input shortly after the reveal.
    wait_for_update_input_highlight(
        page=page, input_css_selector=HPL.INPUT_URL_STRING_UPDATE_SELECTED
    )


def _active_element_is_scheme_toggle(*, page: Page) -> bool:
    return page.evaluate(
        "document.activeElement !== null && "
        "document.activeElement.classList.contains('urlSchemeToggle')"
    )


def _input_edge_styles(*, page: Page, input_selector: str) -> dict:
    return page.evaluate(
        """(inputSelector) => {
            const style = getComputedStyle(document.querySelector(inputSelector));
            return {
                borderLeftWidth: parseFloat(style.borderLeftWidth),
                borderTopLeftRadius: parseFloat(style.borderTopLeftRadius),
            };
        }""",
        input_selector,
    )


def test_manager_picks_default_scheme_and_new_create_panel_starts_on_it(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub manager on the URLs settings popover
    WHEN they pick ssh as the default scheme
    THEN "Saved" is announced and a newly opened create panel starts on ssh
    """
    _login_to_owned_utub(app=provide_app, page=page)

    _open_urls_settings(page=page)
    _pick_default_scheme(page=page, scheme="ssh")

    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        PANEL_SETTINGS_SAVED
    )
    _close_settings_popover(page=page)

    _open_create_form(page=page)
    expect_selected_scheme(
        page=page, toggle_locator=HPL.SCHEME_TOGGLE_CREATE, scheme="ssh"
    )


def test_manager_turns_hide_on_and_create_panel_shows_helper_and_submits_https(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub manager with an https default
    WHEN they turn "hide scheme selector" on
    THEN the create panel shows no toggle but the helper "Will be saved as
        https://..." for a bare host, and submitting stores https://...
    """
    _login_to_owned_utub(app=provide_app, page=page)

    _open_urls_settings(page=page)
    hide_switch = page.locator(HPL.URLS_SETTINGS_HIDE_SWITCH)
    expect(hide_switch).to_have_attribute("aria-checked", "false")
    hide_switch.click()
    expect(hide_switch).to_have_attribute("aria-checked", "true")
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        PANEL_SETTINGS_SAVED
    )
    _close_settings_popover(page=page)

    _open_create_form(page=page)
    expect(page.locator(HPL.SCHEME_TOGGLE_CREATE)).to_be_hidden()
    _fill_create_form(page=page, url_string="example.com")
    helper = page.locator(HPL.SCHEME_HELPER_CREATE)
    expect(helper).to_contain_text("Will be saved as")
    expect(helper).to_contain_text(f"{_HTTPS_PREFIX}example.com")

    _submit_create_form(page=page)
    _expect_url_card_with_href_prefix(
        page=page, href_prefix=f"{_HTTPS_PREFIX}example.com"
    )


@pytest.mark.parametrize(
    "typed_url, expected_prefix",
    [
        ("http://example.com/a", "http://example.com/a"),
        ("mailto:x@y.com", "mailto:x@y.com"),
    ],
)
def test_hidden_selector_typed_or_pasted_scheme_is_submitted(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    typed_url: str,
    expected_prefix: str,
):
    """
    GIVEN a UTub that hides the scheme selector
    WHEN an http:// URL is typed or a mailto: address is pasted
    THEN the submitted URL keeps that scheme
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_utub_settings(app, utub_id, _HIDE_ON_HTTPS)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )

    _open_create_form(page=page)
    _fill_create_form(page=page, url_string=typed_url)
    expect(page.locator(HPL.SCHEME_HELPER_CREATE)).to_contain_text("Will be saved as")
    _submit_create_form(page=page)

    _expect_url_card_with_href_prefix(page=page, href_prefix=expected_prefix)


def test_hidden_selector_edit_keeps_stored_ftp_scheme_after_save(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    GIVEN a UTub that hides the scheme selector and a stored ftp:// URL
    WHEN the URL's text is edited and saved
    THEN the URL is still ftp://
    """
    app = provide_app
    _, cli_runner = runner
    add_mock_urls(cli_runner, [_STORED_FTP_URL])
    set_utub_settings(
        app, get_utub_this_user_created(app, USER_ID_FOR_TEST).id, _HIDE_ON_HTTPS
    )

    _open_edit_form_for_stored_url(app=app, page=page, stored_url=_STORED_FTP_URL)
    expect(page.locator(HPL.SCHEME_TOGGLE_UPDATE)).to_be_hidden()
    string_input = page.locator(HPL.INPUT_URL_STRING_UPDATE_SELECTED)
    expect(string_input).to_have_value("files.example.com/a")
    # Append rather than clear: clearing the input drops back to the UTub default.
    string_input.focus()
    page.keyboard.press("End")
    page.keyboard.type("b")
    expect(string_input).to_have_value("files.example.com/ab")
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}",
    )
    wait_until_hidden(page=page, css_selector=HPL.UPDATE_URL_STRING_WRAP)

    _expect_url_card_with_href_prefix(
        page=page, href_prefix="ftp://files.example.com/ab"
    )


def test_picking_non_https_with_hide_on_resets_switch_and_shows_toggle(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub with hide on (https default)
    WHEN a manager picks mailto as the default scheme
    THEN the switch turns off and disabled, the restored notice is announced, and
        the create panel shows the toggle again on mailto
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_utub_settings(app, utub_id, _HIDE_ON_HTTPS)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )

    _open_urls_settings(page=page)
    hide_switch = page.locator(HPL.URLS_SETTINGS_HIDE_SWITCH)
    expect(hide_switch).to_have_attribute("aria-checked", "true")
    _pick_default_scheme(page=page, scheme="mailto")

    expect(hide_switch).to_have_attribute("aria-checked", "false")
    expect(hide_switch).to_have_attribute("aria-disabled", "true")
    expect(page.locator(HPL.URLS_SETTINGS_HIDE_HINT)).to_be_visible()
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        URLS_SETTINGS_SELECTOR_RESTORED
    )
    _close_settings_popover(page=page)

    _open_create_form(page=page)
    expect(page.locator(HPL.SCHEME_TOGGLE_CREATE)).to_be_visible()
    expect_selected_scheme(
        page=page, toggle_locator=HPL.SCHEME_TOGGLE_CREATE, scheme="mailto"
    )


def test_plain_member_sees_both_controls_disabled_and_focusable_with_note(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a plain member of a UTub
    WHEN they open the URLs settings
    THEN both controls are aria-disabled but focusable, and the read-only note shows
    """
    app = provide_app
    utub_id = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST).id
    set_member_role_in_utub(app, USER_ID_FOR_TEST, utub_id, Member_Role.MEMBER)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )

    _open_urls_settings(page=page)

    scheme_toggle = page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)
    hide_switch = page.locator(HPL.URLS_SETTINGS_HIDE_SWITCH)
    expect(scheme_toggle).to_have_attribute("aria-disabled", "true")
    expect(hide_switch).to_have_attribute("aria-disabled", "true")
    scheme_toggle.focus()
    expect(scheme_toggle).to_be_focused()
    hide_switch.focus()
    expect(hide_switch).to_be_focused()
    expect(page.locator(HPL.URLS_SETTINGS_READ_ONLY_NOTE)).to_contain_text(
        PANEL_SETTINGS_MANAGERS_ONLY
    )


def test_escape_closes_default_listbox_then_popover_and_returns_focus_to_gear(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN the URLs settings popover with the default-scheme list open
    WHEN Escape is pressed twice
    THEN the first closes only the list and the second closes the popover and
        returns focus to the gear
    """
    _login_to_owned_utub(app=provide_app, page=page)

    _open_urls_settings(page=page)
    page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME).click()
    listbox = page.locator(HPL.URLS_SETTINGS_SCHEME_LISTBOX)
    expect(listbox).to_be_visible()

    page.keyboard.press("Escape")
    expect(listbox).to_be_hidden()
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()

    page.keyboard.press("Escape")
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_URL_SETTINGS_GEAR)).to_be_focused()


def test_open_create_panel_is_not_changed_by_settings_change_meanwhile(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN an open create panel on https
    WHEN a manager saves ssh as the default in the popover meanwhile
    THEN the open panel keeps https (the default is snapshotted at mount)
    """
    _login_to_owned_utub(app=provide_app, page=page)

    _open_create_form(page=page)
    expect_selected_scheme(
        page=page, toggle_locator=HPL.SCHEME_TOGGLE_CREATE, scheme="https"
    )

    _open_urls_settings(page=page)
    _pick_default_scheme(page=page, scheme="ssh")
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        PANEL_SETTINGS_SAVED
    )

    expect(page.locator(HPL.WRAP_URL_CREATE)).to_be_visible()
    expect_selected_scheme(
        page=page, toggle_locator=HPL.SCHEME_TOGGLE_CREATE, scheme="https"
    )


def test_hidden_selector_create_layout_has_no_orphaned_edge_and_tab_skips_toggle(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub that hides the scheme selector
    WHEN the create panel opens
    THEN the URL input keeps a left border and rounded top-left corner, and Tab
        from the title reaches the URL input and then a later control, never the
        hidden toggle
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_utub_settings(app, utub_id, _HIDE_ON_HTTPS)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )

    _open_create_form(page=page)
    styles = _input_edge_styles(page=page, input_selector=HPL.INPUT_URL_STRING_CREATE)
    assert styles["borderLeftWidth"] > 0
    assert styles["borderTopLeftRadius"] > 0

    page.locator(HPL.INPUT_URL_TITLE_CREATE).focus()
    page.keyboard.press("Tab")
    expect(page.locator(HPL.INPUT_URL_STRING_CREATE)).to_be_focused()
    page.keyboard.press("Tab")
    assert not _active_element_is_scheme_toggle(page=page)
    expect(page.locator(HPL.INPUT_URL_STRING_CREATE)).not_to_be_focused()


def test_hidden_selector_edit_layout_has_no_orphaned_edge_and_tab_skips_toggle(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    GIVEN a UTub that hides the scheme selector and an open edit panel
    THEN the URL input keeps a left border and rounded top-left corner, and Tab
        and Shift+Tab from it never land on the hidden toggle
    """
    app = provide_app
    _, cli_runner = runner
    add_mock_urls(cli_runner, [_STORED_FTP_URL])
    set_utub_settings(
        app, get_utub_this_user_created(app, USER_ID_FOR_TEST).id, _HIDE_ON_HTTPS
    )

    _open_edit_form_for_stored_url(app=app, page=page, stored_url=_STORED_FTP_URL)
    styles = _input_edge_styles(
        page=page, input_selector=HPL.INPUT_URL_STRING_UPDATE_SELECTED
    )
    assert styles["borderLeftWidth"] > 0
    assert styles["borderTopLeftRadius"] > 0

    page.locator(HPL.INPUT_URL_STRING_UPDATE_SELECTED).focus()
    page.keyboard.press("Shift+Tab")
    assert not _active_element_is_scheme_toggle(page=page)
    page.locator(HPL.INPUT_URL_STRING_UPDATE_SELECTED).focus()
    page.keyboard.press("Tab")
    assert not _active_element_is_scheme_toggle(page=page)


def test_hidden_selector_clearing_pasted_scheme_returns_to_default_helper(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub that hides the scheme selector
    WHEN mailto:x@y is pasted, the input is cleared, and https://example.com typed
    THEN the helper shows https:// and the submitted URL is https://example.com
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_utub_settings(app, utub_id, _HIDE_ON_HTTPS)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )

    _open_create_form(page=page)
    url_input = page.locator(HPL.INPUT_URL_STRING_CREATE)
    helper = page.locator(HPL.SCHEME_HELPER_CREATE)

    clear_then_send_keys(locator=url_input, input_text="mailto:x@y")
    expect(helper).to_contain_text("mailto:")
    url_input.fill("")
    expect(helper).to_contain_text(_HTTPS_PREFIX)
    expect(helper).not_to_contain_text("mailto:")

    _fill_create_form(page=page, url_string="https://example.com")
    expect(helper).to_contain_text(_HTTPS_PREFIX)
    _submit_create_form(page=page)

    _expect_url_card_with_href_prefix(page=page, href_prefix="https://example.com")


def test_hidden_selector_edit_cleared_input_helper_names_utub_default(
    page: Page,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    GIVEN a UTub that hides the selector and an edit panel on a stored ftp://x URL
    WHEN the input is cleared
    THEN the empty-input helper names the UTub default (https://), not ftp://
    """
    app = provide_app
    _, cli_runner = runner
    add_mock_urls(cli_runner, [_STORED_FTP_URL])
    set_utub_settings(
        app, get_utub_this_user_created(app, USER_ID_FOR_TEST).id, _HIDE_ON_HTTPS
    )

    _open_edit_form_for_stored_url(app=app, page=page, stored_url=_STORED_FTP_URL)
    string_input = page.locator(HPL.INPUT_URL_STRING_UPDATE_SELECTED)
    string_input.fill("")

    helper = page.locator(HPL.SCHEME_HELPER_UPDATE)
    expect(helper).to_contain_text(_HTTPS_PREFIX)
    expect(helper).not_to_contain_text("ftp://")
