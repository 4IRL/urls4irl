from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.models.utub_urls import Utub_Urls
from backend.utils.strings.short_link_strs import SHORT_LINK_UI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from backend.utils.strings.url_strs import URL_ADDED_BY
from backend.utils.strings.utub_strs import URLS_SETTINGS_SHORT_LINKS_OFF_NOTICE
from tests.functional.db_utils import (
    get_url_in_utub,
    get_urls_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    set_member_role_in_utub,
    set_member_settings,
    set_utub_locked_state,
    set_utub_settings,
)
from tests.functional.home_ui.test_urls_panel_settings_ui import (
    USER_ID_FOR_TEST,
    _close_settings_popover,
    _login_to_owned_utub,
    _open_create_form,
    _open_urls_settings,
    _pick_default_scheme,
    _submit_create_form,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_settings_panel_controls_fit
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    get_css_selector_for_url_by_id,
    select_utub_by_id,
    wait_then_click_element,
)
from tests.functional.tags_ui.playwright_utils import open_tag_combobox
from tests.functional.urls_ui.playwright_utils import ClipboardMockHelper

pytestmark = pytest.mark.home_ui

URL_DECK = HPL.URL_DECK
URL_TITLES = f"{HPL.ROWS_URLS} {HPL.URL_TITLE_READ}"
SELECTED_COPY = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_COPY}"
SELECTED_SHORT_LINK = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_SHORT_LINK}"
SELECTED_STACKED_BADGE = f"{HPL.ROW_SELECTED_URL} {HPL.URL_DATE_ADDED_BADGE_STACKED}"
DEFAULT_OPTION_VALUE = ""
NEW_URL_TITLE = "This is https://www.ccc.com/."
NEW_URL_STRING = "https://ccc.example.org/"
STACKED_DATE_SEPARATOR = "·"


def _sort_seed(sort: str) -> dict:
    return {"urls": {"sort": sort}}


def _row_titles(*, page: Page) -> list[str]:
    return [title.strip() for title in page.locator(URL_TITLES).all_text_contents()]


def _expect_row_titles(*, page: Page, titles: list[str]) -> None:
    expect(page.locator(URL_TITLES)).to_have_text(titles)


def _adder_username(*, app: Flask, utub_url_id: int) -> str:
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        return Users.query.get(utub_url.user_id).username


def _select_card(*, page: Page, utub_url_id: int) -> None:
    wait_then_click_element(
        page=page, css_selector=get_css_selector_for_url_by_id(url_id=utub_url_id)
    )
    expect(page.locator(HPL.ROW_SELECTED_URL)).to_have_attribute(
        "utuburlid", str(utub_url_id)
    )


def _login_as_plain_member_in_utub(*, app: Flask, page: Page, utub_id: int) -> int:
    """Log user 1 into ``utub_id`` (a UTub they did not create; callers resolve the
    id once, since an unordered ``.first()`` can return another row after a write)
    as a plain member, with its first URL selected. Returns the URL id."""
    set_member_role_in_utub(app, USER_ID_FOR_TEST, utub_id, Member_Role.MEMBER)
    utub_url_id = get_url_in_utub(app, utub_id).id
    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=USER_ID_FOR_TEST,
        utub_id=utub_id,
        utub_url_id=utub_url_id,
    )
    return utub_url_id


def _reopen_urls_settings(*, page: Page) -> None:
    """Open the popover without assuming the first section is expanded."""
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SETTINGS_GEAR)
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()


def _toggle_selector(*, section_id: str) -> str:
    return HPL.SETTINGS_SECTION_TOGGLE_FORMAT.format(section_id=section_id)


def _pick(*, page: Page, select_selector: str, value: str) -> None:
    page.locator(select_selector).select_option(value)


def _title_az_of(*, default_titles: list[str]) -> list[str]:
    title_az = sorted(default_titles, key=str.casefold)
    assert default_titles != title_az, (
        "Test premise violated: default order must differ from title A-Z"
    )
    return title_az


def test_manager_turns_allow_short_links_off_and_button_goes_away_after_reload(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a manager viewing a selected card with a visible Copy short link button
    WHEN they turn Allow short links off
    THEN the button is hidden on every card at once and stays hidden after a reload
    """
    app = provide_app
    utub_id = _login_to_owned_utub(app=app, page=page)
    utub_url_id = get_url_in_utub(app, utub_id).id
    _select_card(page=page, utub_url_id=utub_url_id)
    expect(page.locator(SELECTED_SHORT_LINK)).to_be_visible()
    other_url_id = next(
        url.id for url in get_urls_in_utub(app, utub_id) if url.id != utub_url_id
    )
    _select_card(page=page, utub_url_id=other_url_id)
    expect(page.locator(SELECTED_SHORT_LINK)).to_be_visible()

    _open_urls_settings(page=page)
    allow_switch = page.locator(HPL.URLS_SETTINGS_ALLOW_SHORT_LINKS_SWITCH)
    expect(allow_switch).to_have_attribute("aria-checked", "true")
    allow_switch.click()
    expect(allow_switch).to_have_attribute("aria-checked", "false")
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        URLS_SETTINGS_SHORT_LINKS_OFF_NOTICE
    )
    _close_settings_popover(page=page)

    expect(page.locator(URL_DECK)).to_have_attribute("data-allow-short-links", "false")
    expect(page.locator(SELECTED_SHORT_LINK)).to_be_hidden()
    expect(page.locator(SELECTED_COPY)).to_be_visible()
    _select_card(page=page, utub_url_id=utub_url_id)
    expect(page.locator(SELECTED_COPY)).to_be_visible()
    expect(page.locator(SELECTED_SHORT_LINK)).to_be_hidden()

    page.reload()
    expect(page.locator(HPL.BUTTON_URL_SETTINGS_GEAR)).to_be_visible()
    _select_card(page=page, utub_url_id=utub_url_id)
    expect(page.locator(URL_DECK)).to_have_attribute("data-allow-short-links", "false")
    expect(page.locator(SELECTED_COPY)).to_be_visible()
    expect(page.locator(SELECTED_SHORT_LINK)).to_be_hidden()


def test_plain_member_loading_a_short_links_off_utub_has_no_short_link_button(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub whose manager turned Allow short links off
    WHEN a plain member loads it and selects a card
    THEN Copy short link is gone for them while Copy is still there
    """
    app = provide_app
    utub_id = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST).id
    set_utub_settings(app, utub_id, {"urls": {"allow_short_links": False}})

    _login_as_plain_member_in_utub(app=app, page=page, utub_id=utub_id)

    expect(page.locator(URL_DECK)).to_have_attribute("data-allow-short-links", "false")
    expect(page.locator(SELECTED_COPY)).to_be_visible()
    expect(page.locator(SELECTED_SHORT_LINK)).to_be_hidden()


def test_stale_member_clicking_short_link_gets_the_policy_message(
    page: Page,
    create_test_urls,
    provide_app: Flask,
    clipboard_mock: ClipboardMockHelper,
):
    """
    GIVEN a plain member whose page still shows Copy short link
    WHEN the manager turns the policy off (seeded after load) and they click it
    THEN the server refuses the mint and the deck shows the policy message
    """
    app = provide_app
    clipboard_mock.setup_clipboard_mock()
    utub_id = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST).id
    _login_as_plain_member_in_utub(app=app, page=page, utub_id=utub_id)
    expect(page.locator(SELECTED_SHORT_LINK)).to_be_visible()

    set_utub_settings(app, utub_id, {"urls": {"allow_short_links": False}})

    wait_then_click_element(page=page, css_selector=SELECTED_SHORT_LINK)
    expect(page.locator(HPL.URL_DECK_ERROR_INDICATOR)).to_have_text(
        SHORT_LINK_UI.SHORT_LINKS_DISABLED
    )


def test_plain_member_in_locked_utub_hides_copy_short_link_and_date_live(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a plain member in a locked UTub with a card selected
    WHEN they hide Copy, Copy short link and the date added
    THEN the buttons and the inline date go away live, the expanded card shows
        "Added by <name>" with no date, and it all survives a reload
    """
    app = provide_app
    utub_id = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST).id
    set_utub_locked_state(app, utub_id, True)
    utub_url_id = _login_as_plain_member_in_utub(app=app, page=page, utub_id=utub_id)
    adder = _adder_username(app=app, utub_url_id=utub_url_id)

    expect(page.locator(SELECTED_COPY)).to_be_visible()
    expect(page.locator(SELECTED_SHORT_LINK)).to_be_visible()
    stacked_badge = page.locator(SELECTED_STACKED_BADGE)
    expect(stacked_badge).to_contain_text(
        f"{URL_ADDED_BY} {adder} {STACKED_DATE_SEPARATOR}"
    )

    unselected_inline_date = page.locator(
        f"{HPL.ROWS_URLS}:not([urlselected='true']) {HPL.URL_DATE_ADDED_BADGE_INLINE}"
    ).first
    expect(unselected_inline_date).to_be_visible()

    _open_urls_settings(page=page)
    for switch_selector, deck_attr in (
        (HPL.URLS_PERSONAL_HIDE_COPY_SWITCH, "data-hide-copy"),
        (HPL.URLS_PERSONAL_HIDE_SHORT_LINK_SWITCH, "data-hide-short-link"),
        (HPL.URLS_PERSONAL_HIDE_DATE_SWITCH, "data-hide-date"),
    ):
        switch = page.locator(switch_selector)
        expect(switch).to_have_attribute("aria-checked", "false")
        switch.click()
        expect(switch).to_have_attribute("aria-checked", "true")
        expect(page.locator(URL_DECK)).to_have_attribute(deck_attr, "true")
    _close_settings_popover(page=page)

    def expect_hidden_state() -> None:
        expect(page.locator(SELECTED_COPY)).to_be_hidden()
        expect(page.locator(SELECTED_SHORT_LINK)).to_be_hidden()
        expect(unselected_inline_date).to_be_hidden()
        expect(page.locator(SELECTED_STACKED_BADGE)).to_have_text(
            f"{URL_ADDED_BY} {adder}"
        )

    expect_hidden_state()

    page.reload()
    expect(page.locator(HPL.BUTTON_URL_SETTINGS_GEAR)).to_be_visible()
    _select_card(page=page, utub_url_id=utub_url_id)
    expect_hidden_state()


def test_sort_override_reorders_live_persists_and_is_per_utub(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two UTubs that both follow the Display default sort
    WHEN a member overrides the sort to Title A-Z in UTub A
    THEN UTub A reorders live and after a reload, UTub B keeps the default order,
        and choosing "Default: ..." restores UTub A's default order
    """
    app = provide_app
    utub_a_id = _login_to_owned_utub(app=app, page=page)
    utub_b_id = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST).id

    default_a = _row_titles(page=page)
    title_az_a = _title_az_of(default_titles=default_a)
    select_utub_by_id(page=page, utub_id=utub_b_id)
    default_b = _row_titles(page=page)
    _title_az_of(default_titles=default_b)
    select_utub_by_id(page=page, utub_id=utub_a_id)
    _expect_row_titles(page=page, titles=default_a)

    _open_urls_settings(page=page)
    _pick(page=page, select_selector=HPL.URLS_PERSONAL_SORT_SELECT, value="title_az")
    _expect_row_titles(page=page, titles=title_az_a)
    _close_settings_popover(page=page)

    page.reload()
    expect(page.locator(HPL.BUTTON_URL_SETTINGS_GEAR)).to_be_visible()
    _expect_row_titles(page=page, titles=title_az_a)

    select_utub_by_id(page=page, utub_id=utub_b_id)
    _expect_row_titles(page=page, titles=default_b)

    select_utub_by_id(page=page, utub_id=utub_a_id)
    _expect_row_titles(page=page, titles=title_az_a)

    _reopen_urls_settings(page=page)
    _pick(
        page=page,
        select_selector=HPL.URLS_PERSONAL_SORT_SELECT,
        value=DEFAULT_OPTION_VALUE,
    )
    _expect_row_titles(page=page, titles=default_a)


def test_layout_override_sets_view_for_that_utub_only_and_default_restores(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a Display default layout that is not "cards"
    WHEN a member overrides the Layout to cards in UTub A
    THEN body[data-view] is cards in UTub A only, and choosing the default
        restores the preference
    """
    app = provide_app
    utub_a_id = _login_to_owned_utub(app=app, page=page)
    utub_b_id = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST).id
    body = page.locator("body")

    default_view = body.get_attribute("data-view")
    assert default_view not in (None, "cards")

    _open_urls_settings(page=page)
    _pick(page=page, select_selector=HPL.URLS_PERSONAL_VIEW_SELECT, value="cards")
    expect(body).to_have_attribute("data-view", "cards")
    _close_settings_popover(page=page)

    select_utub_by_id(page=page, utub_id=utub_b_id)
    expect(body).to_have_attribute("data-view", default_view)

    select_utub_by_id(page=page, utub_id=utub_a_id)
    expect(body).to_have_attribute("data-view", "cards")

    _reopen_urls_settings(page=page)
    _pick(
        page=page,
        select_selector=HPL.URLS_PERSONAL_VIEW_SELECT,
        value=DEFAULT_OPTION_VALUE,
    )
    expect(body).to_have_attribute("data-view", default_view)


def test_title_line_layout_override_sets_view_and_persists_after_reload(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member in a UTub on desktop
    WHEN they select the Title line layout
    THEN body[data-view] is title_line, and it persists after a reload
    """
    _login_to_owned_utub(app=provide_app, page=page)
    body = page.locator("body")

    _open_urls_settings(page=page)
    _pick(page=page, select_selector=HPL.URLS_PERSONAL_VIEW_SELECT, value="title_line")
    expect(body).to_have_attribute("data-view", "title_line")

    page.reload()
    expect(body).to_have_attribute("data-view", "title_line")
    _reopen_urls_settings(page=page)
    expect(page.locator(HPL.URLS_PERSONAL_VIEW_SELECT)).to_have_value("title_line")


def test_density_select_is_disabled_with_a_hint_in_title_line_and_back_in_list(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member on desktop whose effective layout is List
    WHEN they select Title line, then List again, in the popover
    THEN the Density select is aria-disabled with the hint visible for Title
        line, and enabled with the hint hidden for List
    """
    _login_to_owned_utub(app=provide_app, page=page)
    _open_urls_settings(page=page)
    density = page.locator(HPL.URLS_PERSONAL_DENSITY_SELECT)
    hint = page.locator(HPL.URLS_PERSONAL_DENSITY_HINT)

    _pick(page=page, select_selector=HPL.URLS_PERSONAL_VIEW_SELECT, value="list")
    expect(density).not_to_have_attribute("aria-disabled", "true")
    expect(hint).to_be_hidden()

    _pick(page=page, select_selector=HPL.URLS_PERSONAL_VIEW_SELECT, value="title_line")
    expect(density).to_have_attribute("aria-disabled", "true")
    expect(hint).to_be_visible()
    expect(hint).to_have_text("Density applies to List view and the selected URL")

    _pick(page=page, select_selector=HPL.URLS_PERSONAL_VIEW_SELECT, value="list")
    expect(density).not_to_have_attribute("aria-disabled", "true")
    expect(hint).to_be_hidden()


def test_real_css_keeps_hidden_buttons_hidden_after_edit_and_tag_forms_close(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN personal hides for Copy and Copy short link, and the policy off
    WHEN a card's URL edit form and tag combobox are opened and closed
    THEN the real stylesheet keeps both buttons hidden although the form code
        re-shows them, while the card's other buttons come back
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_utub_settings(app, utub_id, {"urls": {"allow_short_links": False}})
    set_member_settings(
        app,
        utub_id,
        USER_ID_FOR_TEST,
        {"urls": {"hide_copy_button": True, "hide_short_link_button": True}},
    )
    utub_url_id = get_url_in_utub(app, utub_id).id
    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=USER_ID_FOR_TEST,
        utub_id=utub_id,
        utub_url_id=utub_url_id,
    )
    access_button = page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}")
    expect(access_button).to_be_visible()
    expect(page.locator(SELECTED_COPY)).to_be_hidden()
    expect(page.locator(SELECTED_SHORT_LINK)).to_be_hidden()

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}",
    )
    expect(
        page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}")
    ).to_be_visible()
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_CANCEL_UPDATE}",
    )
    expect(access_button).to_be_visible()
    expect(page.locator(SELECTED_COPY)).to_be_hidden()
    expect(page.locator(SELECTED_SHORT_LINK)).to_be_hidden()

    open_tag_combobox(page=page, url_id=utub_url_id)
    expect(page.locator(SELECTED_COPY)).to_be_hidden()
    page.keyboard.press("Escape")
    expect(access_button).to_be_visible()
    expect(page.locator(SELECTED_COPY)).to_be_hidden()
    expect(page.locator(SELECTED_SHORT_LINK)).to_be_hidden()


def test_new_url_lands_in_override_sort_order(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member with a Title A-Z sort override
    WHEN they add a URL whose title sorts in the middle
    THEN the new card lands in override order, not at the newest-first top
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_member_settings(app, utub_id, USER_ID_FOR_TEST, _sort_seed("title_az"))
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    titles = _row_titles(page=page)
    assert titles == sorted(titles, key=str.casefold)
    assert titles[0] < NEW_URL_TITLE < titles[-1]

    _open_create_form(page=page)
    clear_then_send_keys(
        locator=page.locator(HPL.INPUT_URL_TITLE_CREATE), input_text=NEW_URL_TITLE
    )
    clear_then_send_keys(
        locator=page.locator(HPL.INPUT_URL_STRING_CREATE), input_text=NEW_URL_STRING
    )
    _submit_create_form(page=page)

    _expect_row_titles(
        page=page, titles=sorted([*titles, NEW_URL_TITLE], key=str.casefold)
    )


def test_disable_swipe_delete_restores_touch_action_and_hides_reveal(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a member with swipe to delete turned off
    WHEN the deck loads
    THEN the real stylesheet restores the row's touch-action to manipulation and
        hides the swipe reveal panel
    """
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_member_settings(
        app, utub_id, USER_ID_FOR_TEST, {"urls": {"disable_swipe_delete": True}}
    )
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )

    expect(page.locator(URL_DECK)).to_have_attribute("data-swipe-delete", "off")
    row = page.locator(HPL.ROWS_URLS).first
    expect(row.locator(HPL.URL_ROW_SWIPE_REVEAL)).to_be_attached()
    expect(row.locator(HPL.URL_ROW_SWIPE_REVEAL)).to_be_hidden()
    expect(row).to_have_css("touch-action", "manipulation")


def test_escape_on_closed_sort_select_closes_popover(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the settings popover with the Sort select focused but closed
    WHEN Escape is pressed
    THEN the popover closes and focus returns to the gear
    """
    _login_to_owned_utub(app=provide_app, page=page)
    _open_urls_settings(page=page)

    sort_select = page.locator(HPL.URLS_PERSONAL_SORT_SELECT)
    sort_select.focus()
    expect(sort_select).to_be_focused()
    page.keyboard.press("Escape")

    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_URL_SETTINGS_GEAR)).to_be_focused()


def test_escape_on_closed_layout_select_closes_popover(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the settings popover with the Layout select reached by Tab but closed
    WHEN Escape is pressed
    THEN the popover closes
    """
    _login_to_owned_utub(app=provide_app, page=page)
    _open_urls_settings(page=page)

    page.locator(HPL.URLS_PERSONAL_SORT_SELECT).focus()
    page.keyboard.press("Tab")
    expect(page.locator(HPL.URLS_PERSONAL_VIEW_SELECT)).to_be_focused()
    page.keyboard.press("Escape")

    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_hidden()


def test_density_select_is_present_with_a_fine_pointer(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a desktop (fine pointer) viewport
    WHEN the URLs settings open
    THEN the Density select is present next to Sort and Layout
    """
    _login_to_owned_utub(app=provide_app, page=page)
    _open_urls_settings(page=page)

    expect(page.locator(HPL.URLS_PERSONAL_SORT_SELECT)).to_be_visible()
    expect(page.locator(HPL.URLS_PERSONAL_VIEW_SELECT)).to_be_visible()
    expect(page.locator(HPL.URLS_PERSONAL_DENSITY_SELECT)).to_be_visible()


def test_every_popover_control_fits_inside_the_panel(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings popover with both parents and all sections expanded
    WHEN the default scheme is https, then a non-https one (which adds the hint)
    THEN no row element extends past the popover's right inner edge, the popover
        does not scroll horizontally, and the scheme toggle is a complete box
    """
    _login_to_owned_utub(app=provide_app, page=page)
    _open_urls_settings(page=page)
    expect(page.locator(HPL.PANEL_SETTINGS_SCHEME_TOGGLE)).to_be_visible()
    expect(page.locator(HPL.URLS_PERSONAL_DENSITY_SELECT)).to_be_visible()
    expect(page.locator(HPL.URLS_PERSONAL_HIDE_DATE_SWITCH)).to_be_visible()

    assert_settings_panel_controls_fit(
        page=page, container_selector=HPL.PANEL_SETTINGS_POPOVER
    )

    _pick_default_scheme(page=page, scheme="ftp")
    expect(page.locator(HPL.URLS_SETTINGS_HIDE_HINT)).to_be_visible()
    assert_settings_panel_controls_fit(
        page=page, container_selector=HPL.PANEL_SETTINGS_POPOVER
    )


def test_title_click_collapses_only_that_section_and_expands_again(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings with both sections open
    WHEN the "New URLs" title is clicked, then clicked again
    THEN its controls are hidden while the personal section stays visible, and
        come back visible on re-expand
    """
    _login_to_owned_utub(app=provide_app, page=page)
    _open_urls_settings(page=page)
    toggle = page.locator(
        _toggle_selector(section_id=HPL.SETTINGS_SECTION_URLS_DEFAULTS)
    )
    default_scheme = page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)
    allow_switch = page.locator(HPL.URLS_SETTINGS_ALLOW_SHORT_LINKS_SWITCH)
    sort_select = page.locator(HPL.URLS_PERSONAL_SORT_SELECT)

    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(default_scheme).to_be_hidden()
    expect(allow_switch).to_be_hidden()
    expect(sort_select).to_be_visible()

    toggle.click()
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(default_scheme).to_be_visible()
    expect(allow_switch).to_be_visible()
    expect(sort_select).to_be_visible()


def test_parent_headers_nest_the_sections_and_heading_row_click_is_inert(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the URLs settings
    WHEN they open
    THEN "Shared with this UTub" and "Just for you" are expanded parent headers,
        "New URLs" sits under the first and "Your view of this UTub" under the
        second, and clicking a parent's heading row (not its button) collapses nothing
    """
    _login_to_owned_utub(app=provide_app, page=page)
    _open_urls_settings(page=page)
    shared_toggle = page.locator(
        HPL.SETTINGS_GROUP_TOGGLE_FORMAT.format(scope=HPL.SETTINGS_GROUP_UTUB)
    )
    personal_toggle = page.locator(
        HPL.SETTINGS_GROUP_TOGGLE_FORMAT.format(scope=HPL.SETTINGS_GROUP_USER)
    )

    expect(shared_toggle).to_have_text(UI_TEST_STRINGS.PANEL_SETTINGS_SCOPE_UTUB)
    expect(personal_toggle).to_have_text(UI_TEST_STRINGS.PANEL_SETTINGS_SCOPE_USER)
    expect(shared_toggle).to_have_attribute("aria-expanded", "true")
    expect(personal_toggle).to_have_attribute("aria-expanded", "true")
    expect(
        page.locator(
            HPL.SETTINGS_GROUP_SECTION_FORMAT.format(
                scope=HPL.SETTINGS_GROUP_UTUB,
                section_id=HPL.SETTINGS_SECTION_URLS_DEFAULTS,
            )
        )
    ).to_have_count(1)
    expect(
        page.locator(
            HPL.SETTINGS_GROUP_SECTION_FORMAT.format(
                scope=HPL.SETTINGS_GROUP_USER,
                section_id=HPL.SETTINGS_SECTION_URLS_PERSONAL,
            )
        )
    ).to_have_count(1)

    # A click past the button's right edge lands on the inert heading row.
    heading = page.locator(
        HPL.SETTINGS_GROUP_HEADING_FORMAT.format(scope=HPL.SETTINGS_GROUP_UTUB)
    )
    box = heading.bounding_box()
    toggle_box = shared_toggle.bounding_box()
    assert box is not None and toggle_box is not None
    click_x = box["width"] - 2
    assert click_x > toggle_box["x"] - box["x"] + toggle_box["width"], (
        "Test premise violated: the click point must lie outside the toggle button"
    )
    heading.click(position={"x": click_x, "y": box["height"] / 2})

    expect(shared_toggle).to_have_attribute("aria-expanded", "true")
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_visible()


def test_parent_collapse_hides_nested_sections_and_keeps_their_state(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the "New URLs" subheader collapsed under an expanded "Shared with this UTub"
    WHEN the "Shared with this UTub" parent is collapsed and expanded again
    THEN its sections are hidden meanwhile, "Just for you" is untouched, and the
        subheader comes back still collapsed
    """
    _login_to_owned_utub(app=provide_app, page=page)
    _open_urls_settings(page=page)
    shared_toggle = page.locator(
        HPL.SETTINGS_GROUP_TOGGLE_FORMAT.format(scope=HPL.SETTINGS_GROUP_UTUB)
    )
    section_toggle = page.locator(
        _toggle_selector(section_id=HPL.SETTINGS_SECTION_URLS_DEFAULTS)
    )

    section_toggle.click()
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_hidden()

    shared_toggle.click()
    expect(shared_toggle).to_have_attribute("aria-expanded", "false")
    expect(section_toggle).to_be_hidden()
    expect(page.locator(HPL.URLS_PERSONAL_SORT_SELECT)).to_be_visible()

    shared_toggle.click()
    expect(shared_toggle).to_have_attribute("aria-expanded", "true")
    expect(section_toggle).to_be_visible()
    expect(section_toggle).to_have_attribute("aria-expanded", "false")
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_hidden()


def test_collapsed_parent_survives_popover_reopen_and_page_reload(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the "Just for you" parent collapsed
    WHEN the popover is closed and reopened, and then the page is reloaded
    THEN that parent stays collapsed each time while "Shared with this UTub" is open
    """
    _login_to_owned_utub(app=provide_app, page=page)
    _open_urls_settings(page=page)
    personal_toggle = page.locator(
        HPL.SETTINGS_GROUP_TOGGLE_FORMAT.format(scope=HPL.SETTINGS_GROUP_USER)
    )
    personal_toggle.click()
    expect(page.locator(HPL.URLS_PERSONAL_SORT_SELECT)).to_be_hidden()
    _close_settings_popover(page=page)

    _reopen_urls_settings(page=page)
    expect(personal_toggle).to_have_attribute("aria-expanded", "false")
    expect(page.locator(HPL.URLS_PERSONAL_SORT_SELECT)).to_be_hidden()
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_visible()
    _close_settings_popover(page=page)

    page.reload()
    expect(page.locator(HPL.BUTTON_URL_SETTINGS_GEAR)).to_be_visible()
    _reopen_urls_settings(page=page)
    expect(personal_toggle).to_have_attribute("aria-expanded", "false")
    expect(page.locator(HPL.URLS_PERSONAL_SORT_SELECT)).to_be_hidden()
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_visible()


def test_collapsed_section_survives_popover_reopen_and_page_reload(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the "New URLs" section collapsed
    WHEN the popover is closed and reopened, and then the page is reloaded
    THEN the section's controls are still hidden each time
    """
    _login_to_owned_utub(app=provide_app, page=page)
    _open_urls_settings(page=page)
    page.locator(
        _toggle_selector(section_id=HPL.SETTINGS_SECTION_URLS_DEFAULTS)
    ).click()
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_hidden()
    _close_settings_popover(page=page)

    _reopen_urls_settings(page=page)
    expect(page.locator(HPL.URLS_PERSONAL_SORT_SELECT)).to_be_visible()
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_hidden()
    expect(page.locator(HPL.URLS_SETTINGS_ALLOW_SHORT_LINKS_SWITCH)).to_be_hidden()
    _close_settings_popover(page=page)

    page.reload()
    expect(page.locator(HPL.BUTTON_URL_SETTINGS_GEAR)).to_be_visible()
    _reopen_urls_settings(page=page)
    expect(page.locator(HPL.URLS_PERSONAL_SORT_SELECT)).to_be_visible()
    expect(page.locator(HPL.URLS_SETTINGS_DEFAULT_SCHEME)).to_be_hidden()
    expect(page.locator(HPL.URLS_SETTINGS_ALLOW_SHORT_LINKS_SWITCH)).to_be_hidden()
