from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.utils.strings.trash_strs import TRASH_UI
from backend.utils.strings.url_strs import URL_REVIVED_LOST_TAGS_ONE
from tests.functional.db_utils import set_utub_locked_state, trash_utub, trash_utub_url
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import TrashPanelLocators as TPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    select_utub_by_id,
    wait_for_modal_ready,
)
from tests.functional.trash_ui.db_utils import (
    add_tag_to_url,
    add_url_to_utub,
    create_utub_as_creator,
    delete_utub_tag,
    purge_utub_url_row,
    seed_trashed_urls,
)
from tests.functional.trash_ui.playwright_utils import (
    login_user_and_open_trash,
    open_trash,
    open_utubs_tab,
    wait_for_trash_list_loaded,
)
from tests.functional.urls_ui.playwright_utils import enter_multi_select_mode

pytestmark = pytest.mark.trash_ui

USER_ID: int = 1


@pytest.fixture(autouse=True)
def seeded_users(page: Page, create_test_users):
    """Every test seeds its own UTubs and URLs, but needs the mock users to exist.

    Depends on ``page`` so it seeds AFTER the page fixture's database wipe."""


def _url_row(utub_url_id: int) -> str:
    return f"{TPL.ROWS_URLS}[data-utub-url-id='{utub_url_id}']"


def _utub_row(utub_id: int) -> str:
    return f"{TPL.ROWS_UTUBS}[data-utub-id='{utub_id}']"


def _confirm_in_modal(page: Page) -> None:
    wait_for_modal_ready(page=page, modal_selector=TPL.CONFIRM_MODAL)
    page.locator(TPL.CONFIRM_MODAL_SUBMIT).click()
    expect(page.locator(TPL.CONFIRM_MODAL)).to_be_hidden()


def test_badge_shows_row_total_across_both_tabs(page: Page, provide_app: Flask):
    """
    GIVEN two trashed URLs in a live UTub and a trashed UTub holding two URLs
    WHEN the home page loads and Trash is opened
    THEN the badge counts URL rows plus UTub rows (2 + 2 ride-along + 1) and the
        panel lists the same rows
    """
    app = provide_app
    live_utub_id = create_utub_as_creator(app, USER_ID, "Trash live utub")
    seed_trashed_urls(app, live_utub_id, 2, "badge-live")
    doomed_utub_id = create_utub_as_creator(app, USER_ID, "Trash doomed utub")
    add_url_to_utub(app, doomed_utub_id, USER_ID, "https://badge-a.example.com/", "A")
    add_url_to_utub(app, doomed_utub_id, USER_ID, "https://badge-b.example.com/", "B")
    trash_utub(app, doomed_utub_id, USER_ID)

    login_user_to_home_page(app=app, page=page, user_id=USER_ID)
    expect(page.locator(TPL.SELECTOR_COUNT)).to_have_text("(5)")

    open_trash(page=page)
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(4)
    expect(page.locator(TPL.ROWS_UTUBS)).to_have_count(1)
    expect(page.locator(TPL.TAB_URLS)).to_have_text(TRASH_UI.TAB_URLS.format(n=4))
    expect(page.locator(TPL.TAB_UTUBS)).to_have_text(TRASH_UI.TAB_UTUBS.format(n=1))


def test_opening_trash_swaps_panel_and_pushes_view_url(page: Page, provide_app: Flask):
    """
    GIVEN a user on the home page
    WHEN they open Trash
    THEN the Trash panel replaces the URL deck and the URL is /home?view=trash
    """
    app = provide_app
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)

    expect(page.locator(TPL.PANEL)).to_be_visible()
    expect(page.locator(HPL.URL_DECK)).to_be_hidden()
    expect(page.locator(TPL.SELECTOR)).to_have_attribute("aria-current", "page")
    expect(page).to_have_url(
        re.compile(rf"/home\?{TRASH_UI.VIEW_QUERY_PARAM}={TRASH_UI.TRASH_VIEW}$")
    )


def test_back_returns_to_previous_utub_and_reload_reopens_trash(
    page: Page, provide_app: Flask
):
    """
    GIVEN a user viewing a UTub who then opens Trash
    WHEN they reload, then press Back
    THEN the reload reopens Trash and Back returns to the previous UTub
    """
    app = provide_app
    utub_name = "Trash back utub"
    utub_id = create_utub_as_creator(app, USER_ID, utub_name)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID, utub_id=utub_id
    )
    open_trash(page=page)

    page.reload()
    wait_for_trash_list_loaded(page=page)
    expect(page.locator(HPL.URL_DECK)).to_be_hidden()

    page.go_back()
    expect(page.locator(TPL.PANEL)).to_be_hidden()
    expect(page.locator(HPL.URL_DECK)).to_be_visible()
    expect(page.locator(HPL.HEADER_URL_DECK)).to_have_text(utub_name)


def test_selecting_a_utub_closes_trash(page: Page, provide_app: Flask):
    """
    GIVEN Trash is open
    WHEN the user selects a UTub in the deck
    THEN Trash closes and the UTub's URL deck is shown
    """
    app = provide_app
    utub_name = "Trash select utub"
    utub_id = create_utub_as_creator(app, USER_ID, utub_name)
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)

    select_utub_by_id(page=page, utub_id=utub_id)

    expect(page.locator(TPL.PANEL)).to_be_hidden()
    expect(page.locator(HPL.URL_DECK)).to_be_visible()
    expect(page.locator(TPL.SELECTOR)).not_to_have_attribute("aria-current", "page")


def test_entering_trash_exits_multi_select_mode(page: Page, provide_app: Flask):
    """
    GIVEN the URL deck is in multi-select mode
    WHEN the user opens Trash
    THEN multi-select mode is exited
    """
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash multi utub")
    add_url_to_utub(app, utub_id, USER_ID, "https://multi.example.com/", "Multi")
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID, utub_id=utub_id
    )
    enter_multi_select_mode(page=page)
    expect(page.locator("#URLDeck")).to_have_class(re.compile(r"multiSelectActive"))

    open_trash(page=page)

    expect(page.locator("#URLDeck")).not_to_have_class(re.compile(r"multiSelectActive"))


def test_tabs_switch_by_click_and_keyboard(page: Page, provide_app: Flask):
    """
    GIVEN the Trash panel is open on the URLs tab
    WHEN the user clicks a tab and uses ArrowRight/ArrowLeft/End/Home
    THEN aria-selected, tabindex and the panels' hidden state follow
    """
    app = provide_app
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)
    urls_tab = page.locator(TPL.TAB_URLS)
    utubs_tab = page.locator(TPL.TAB_UTUBS)

    def assert_active(active: str) -> None:
        urls_active = active == "urls"
        expect(urls_tab).to_have_attribute("aria-selected", str(urls_active).lower())
        expect(urls_tab).to_have_attribute("tabindex", "0" if urls_active else "-1")
        expect(utubs_tab).to_have_attribute(
            "aria-selected", str(not urls_active).lower()
        )
        expect(utubs_tab).to_have_attribute("tabindex", "-1" if urls_active else "0")
        if urls_active:
            expect(page.locator(TPL.PANEL_URLS)).to_be_visible()
            expect(page.locator(TPL.PANEL_UTUBS)).to_be_hidden()
        else:
            expect(page.locator(TPL.PANEL_UTUBS)).to_be_visible()
            expect(page.locator(TPL.PANEL_URLS)).to_be_hidden()

    assert_active("urls")

    utubs_tab.click()
    assert_active("utubs")
    urls_tab.click()
    assert_active("urls")

    urls_tab.focus()
    page.keyboard.press("ArrowRight")
    assert_active("utubs")
    expect(utubs_tab).to_be_focused()

    page.keyboard.press("ArrowLeft")
    assert_active("urls")
    expect(urls_tab).to_be_focused()

    page.keyboard.press("End")
    assert_active("utubs")
    page.keyboard.press("Home")
    assert_active("urls")


def test_empty_tabs_show_empty_state_and_disable_empty_trash(
    page: Page, provide_app: Flask
):
    """
    GIVEN a user with nothing in Trash
    WHEN they view each tab
    THEN each tab shows its empty state and Empty trash is disabled
    """
    app = provide_app
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)

    expect(page.locator(TPL.EMPTY_STATE_URLS)).to_be_visible()
    expect(page.locator(TPL.EMPTY_STATE_URLS)).to_have_text(TRASH_UI.EMPTY_STATE)
    expect(page.locator(TPL.BUTTON_EMPTY)).to_be_disabled()
    expect(page.locator(TPL.BUTTON_EMPTY)).to_have_attribute("aria-disabled", "true")

    open_utubs_tab(page=page)
    expect(page.locator(TPL.EMPTY_STATE_UTUBS)).to_be_visible()
    expect(page.locator(TPL.EMPTY_STATE_UTUBS)).to_have_text(TRASH_UI.EMPTY_STATE)
    expect(page.locator(TPL.BUTTON_EMPTY)).to_be_disabled()
    expect(page.locator(TPL.BUTTON_EMPTY)).to_have_attribute("aria-disabled", "true")


def test_restore_url_in_place_announces_focuses_next_row_and_updates_badge(
    page: Page, provide_app: Flask
):
    """
    GIVEN two trashed URLs in a live UTub
    WHEN the user restores the first row
    THEN the row leaves, the banner announces it, focus lands on the next row, the
        badge drops by one and the URL is back in its UTub
    """
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash restore utub")
    first_id, second_id = seed_trashed_urls(app, utub_id, 2, "restore")
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)
    expect(page.locator(TPL.SELECTOR_COUNT)).to_have_text("(2)")
    open_trash(page=page)
    rows = page.locator(TPL.ROWS_URLS)
    expect(rows).to_have_count(2)

    restored_selector = _url_row(first_id)
    remaining_selector = _url_row(second_id)
    page.locator(f"{restored_selector} {TPL.BUTTON_RESTORE}").click()

    expect(page.locator(restored_selector)).to_have_count(0)
    expect(page.locator(TPL.OUTCOME_BANNER)).to_be_visible()
    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text("Restored from trash.")
    expect(page.locator(remaining_selector)).to_be_focused()
    expect(page.locator(TPL.SELECTOR_COUNT)).to_have_text("(1)")

    select_utub_by_id(page=page, utub_id=utub_id)
    expect(page.locator(f"{HPL.ROWS_URLS}[utuburlid='{first_id}']")).to_be_visible()


def test_restoring_last_url_row_focuses_empty_state(page: Page, provide_app: Flask):
    """
    GIVEN a single trashed URL
    WHEN the user restores it
    THEN the tab's empty state appears and takes focus
    """
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash last row utub")
    (only_id,) = seed_trashed_urls(app, utub_id, 1, "last")
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)

    page.locator(f"{_url_row(only_id)} {TPL.BUTTON_RESTORE}").click()

    expect(page.locator(TPL.ROWS_URLS)).to_have_count(0)
    expect(page.locator(TPL.EMPTY_STATE_URLS)).to_be_visible()
    expect(page.locator(TPL.EMPTY_STATE_URLS)).to_be_focused()
    expect(page.locator(TPL.SELECTOR_COUNT)).to_have_text("(0)")


def test_restore_reports_lost_tag(page: Page, provide_app: Flask):
    """
    GIVEN a trashed URL whose tag was deleted while the URL sat in Trash
    WHEN the user restores the URL
    THEN the banner reports that one tag no longer exists
    """
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash tags utub")
    utub_url_id = add_url_to_utub(
        app, utub_id, USER_ID, "https://lost-tag.example.com/", "Lost tag"
    )
    tag_id = add_tag_to_url(app, utub_id, utub_url_id, USER_ID, "doomedtag")
    trash_utub_url(app, utub_url_id, USER_ID, [tag_id])
    delete_utub_tag(app, tag_id)
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)

    page.locator(f"{_url_row(utub_url_id)} {TPL.BUTTON_RESTORE}").click()

    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(URL_REVIVED_LOST_TAGS_ONE)


def test_restore_utub_returns_it_to_the_deck_and_removes_ride_along_urls(
    page: Page, provide_app: Flask
):
    """
    GIVEN a trashed UTub holding two URLs
    WHEN the user restores the UTub from the UTubs tab
    THEN the UTub reappears in the deck and its URL rows leave the URLs tab
    """
    app = provide_app
    utub_name = "Trash utub restore"
    utub_id = create_utub_as_creator(app, USER_ID, utub_name)
    add_url_to_utub(app, utub_id, USER_ID, "https://ride-a.example.com/", "Ride A")
    add_url_to_utub(app, utub_id, USER_ID, "https://ride-b.example.com/", "Ride B")
    trash_utub(app, utub_id, USER_ID)
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)
    deck_entry = page.locator(f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']")
    expect(deck_entry).to_have_count(0)
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(2)

    open_utubs_tab(page=page)
    page.locator(f"{_utub_row(utub_id)} {TPL.BUTTON_RESTORE}").click()

    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(
        TRASH_UI.UTUB_RESTORED.format(utub=utub_name)
    )
    expect(deck_entry).to_have_count(1)
    expect(page.locator(TPL.ROWS_UTUBS)).to_have_count(0)
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(0)
    expect(page.locator(TPL.SELECTOR_COUNT)).to_have_text("(0)")


def test_restore_url_to_destination_utub(page: Page, provide_app: Flask):
    """
    GIVEN a trashed URL whose origin UTub is trashed, and a live and a locked UTub
    WHEN the user opens "Restore to…" and picks the live UTub
    THEN the picker lists both with the locked one aria-disabled, and the URL is
        restored into the chosen UTub with a "Restored to {UTub}." banner
    """
    app = provide_app
    origin_id = create_utub_as_creator(app, USER_ID, "Trash origin utub")
    utub_url_id = add_url_to_utub(
        app, origin_id, USER_ID, "https://dest.example.com/", "Dest URL"
    )
    destination_name = "Trash destination utub"
    destination_id = create_utub_as_creator(app, USER_ID, destination_name)
    locked_id = create_utub_as_creator(app, USER_ID, "Trash locked destination")
    set_utub_locked_state(app, locked_id, True)
    trash_utub(app, origin_id, USER_ID)
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)

    restore_button = page.locator(f"{_url_row(utub_url_id)} {TPL.BUTTON_RESTORE}")
    expect(restore_button).to_have_text(TRASH_UI.RESTORE_TO)
    restore_button.click()

    options = page.locator(TPL.DESTINATION_OPTION)
    expect(page.locator(TPL.DESTINATION_PICKER)).to_be_visible()
    expect(options).to_have_count(2)
    locked_option = page.locator(
        f"{TPL.DESTINATION_OPTION}[data-dest-utub-id='{locked_id}']"
    )
    expect(locked_option).to_have_attribute("aria-disabled", "true")
    expect(
        page.locator(f"{TPL.DESTINATION_OPTION}[data-dest-utub-id='{destination_id}']")
    ).not_to_have_attribute("aria-disabled", "true")

    page.locator(
        f"{TPL.DESTINATION_OPTION}[data-dest-utub-id='{destination_id}']"
    ).click()

    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(
        TRASH_UI.RESTORED_TO.format(utub=destination_name)
    )
    expect(page.locator(_url_row(utub_url_id))).to_have_count(0)

    select_utub_by_id(page=page, utub_id=destination_id)
    expect(page.locator(HPL.ROWS_URLS)).to_have_count(1)


def test_destination_picker_keyboard_activation(page: Page, provide_app: Flask):
    """
    GIVEN the destination picker is open for a trashed URL
    WHEN the user presses Enter on the Restore button, then Enter on an option
    THEN focus moves into the picker without activating it, and the option restores
        the URL
    """
    app = provide_app
    origin_id = create_utub_as_creator(app, USER_ID, "Trash kb origin utub")
    utub_url_id = add_url_to_utub(
        app, origin_id, USER_ID, "https://kb-dest.example.com/", "KB Dest"
    )
    destination_name = "Trash kb destination"
    create_utub_as_creator(app, USER_ID, destination_name)
    trash_utub(app, origin_id, USER_ID)
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)

    restore_button = page.locator(f"{_url_row(utub_url_id)} {TPL.BUTTON_RESTORE}")
    restore_button.focus()
    page.keyboard.press("Enter")

    expect(page.locator(TPL.DESTINATION_PICKER)).to_be_visible()
    expect(page.locator(TPL.DESTINATION_OPTION).first).to_be_focused()
    # The Enter keyup that opened the picker must not have activated an option.
    expect(page.locator(_url_row(utub_url_id))).to_have_count(1)

    page.keyboard.press("Escape")
    expect(page.locator(TPL.DESTINATION_PICKER)).to_have_count(0)
    expect(restore_button).to_be_focused()

    page.keyboard.press("Enter")
    expect(page.locator(TPL.DESTINATION_OPTION).first).to_be_focused()
    page.keyboard.press("Enter")

    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(
        TRASH_UI.RESTORED_TO.format(utub=destination_name)
    )
    expect(page.locator(_url_row(utub_url_id))).to_have_count(0)


def test_delete_forever_cancel_keeps_row_and_confirm_removes_it(
    page: Page, provide_app: Flask
):
    """
    GIVEN two trashed URLs
    WHEN the user opens Delete forever and cancels, then opens it again and confirms
    THEN Cancel keeps the row; confirming removes it and focus moves to the next row
    """
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash purge utub")
    first_id, second_id = seed_trashed_urls(app, utub_id, 2, "purge")
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)
    purge_button = page.locator(f"{_url_row(first_id)} {TPL.BUTTON_PURGE}")

    purge_button.click()
    wait_for_modal_ready(page=page, modal_selector=TPL.CONFIRM_MODAL)
    expect(page.locator(TPL.CONFIRM_MODAL_TITLE)).to_have_text(
        TRASH_UI.CONFIRM_PURGE_TITLE
    )
    expect(page.locator(TPL.CONFIRM_MODAL_BODY)).to_have_text(
        TRASH_UI.CONFIRM_PURGE_URL_BODY.format(title="purge title 0")
    )
    page.locator(TPL.CONFIRM_MODAL_DISMISS).click()
    expect(page.locator(TPL.CONFIRM_MODAL)).to_be_hidden()
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(2)

    purge_button.click()
    _confirm_in_modal(page)

    expect(page.locator(_url_row(first_id))).to_have_count(0)
    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(TRASH_UI.URL_PURGED)
    expect(page.locator(_url_row(second_id))).to_be_focused()
    expect(page.locator(TPL.SELECTOR_COUNT)).to_have_text("(1)")


def test_empty_trash_empties_only_the_active_tab(page: Page, provide_app: Flask):
    """
    GIVEN two trashed URLs in a live UTub and a separate trashed UTub
    WHEN the user empties the URLs tab
    THEN the confirm body states the count, only the URLs go, and the banner says so
    """
    app = provide_app
    live_utub_id = create_utub_as_creator(app, USER_ID, "Trash empty live utub")
    seed_trashed_urls(app, live_utub_id, 2, "empty")
    doomed_utub_id = create_utub_as_creator(app, USER_ID, "Trash empty doomed utub")
    trash_utub(app, doomed_utub_id, USER_ID)
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(2)

    page.locator(TPL.BUTTON_EMPTY).click()
    wait_for_modal_ready(page=page, modal_selector=TPL.CONFIRM_MODAL)
    expect(page.locator(TPL.CONFIRM_MODAL_TITLE)).to_have_text(
        TRASH_UI.CONFIRM_EMPTY_TITLE
    )
    expect(page.locator(TPL.CONFIRM_MODAL_BODY)).to_have_text(
        TRASH_UI.CONFIRM_EMPTY_URLS_BODY.format(n=2)
    )
    _confirm_in_modal(page)

    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(
        TRASH_UI.EMPTIED.format(n=2)
    )
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(0)
    expect(page.locator(TPL.EMPTY_STATE_URLS)).to_be_visible()
    expect(page.locator(TPL.ROWS_UTUBS)).to_have_count(1)
    expect(page.locator(TPL.SELECTOR_COUNT)).to_have_text("(1)")


def test_locked_origin_disables_row_actions_and_empty_trash_keeps_it(
    page: Page, provide_app: Flask
):
    """
    GIVEN a trashed URL in a locked UTub next to one in an unlocked UTub
    WHEN the user views Trash and empties the tab
    THEN the locked row's Restore and Delete forever are disabled and it shows the
        "Origin UTub locked" chip, and Empty trash reports the locked row was kept
    """
    app = provide_app
    open_utub_id = create_utub_as_creator(app, USER_ID, "Trash unlocked utub")
    (open_url_id,) = seed_trashed_urls(app, open_utub_id, 1, "unlocked")
    locked_utub_id = create_utub_as_creator(app, USER_ID, "Trash locked utub")
    (locked_url_id,) = seed_trashed_urls(app, locked_utub_id, 1, "locked")
    set_utub_locked_state(app, locked_utub_id, True)
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)

    locked_row = page.locator(_url_row(locked_url_id))
    for button_selector in (TPL.BUTTON_RESTORE, TPL.BUTTON_PURGE):
        button = locked_row.locator(button_selector)
        expect(button).to_have_attribute("aria-disabled", "true")
        expect(button).to_have_class(re.compile(r"(^|\s)disabled(\s|$)"))
    expect(locked_row.locator(TPL.CHIP_ORIGIN)).to_have_text(TRASH_UI.ORIGIN_LOCKED)
    expect(
        page.locator(f"{_url_row(open_url_id)} {TPL.BUTTON_RESTORE}")
    ).not_to_have_attribute("aria-disabled", "true")

    page.locator(TPL.BUTTON_EMPTY).click()
    _confirm_in_modal(page)

    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(
        TRASH_UI.EMPTY_SKIPPED_LOCKED_ONE
    )
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(1)
    expect(locked_row).to_have_count(1)


def test_restoring_a_row_purged_elsewhere_reports_not_in_trash(
    page: Page, provide_app: Flask
):
    """
    GIVEN a Trash list showing a row that was purged server-side afterwards
    WHEN the user clicks Restore on it
    THEN the banner says it is no longer in Trash and the list refreshes without it
    """
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash stale utub")
    stale_id, other_id = seed_trashed_urls(app, utub_id, 2, "stale")
    login_user_and_open_trash(app=app, page=page, user_id=USER_ID)
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(2)

    purge_utub_url_row(app, stale_id)
    page.locator(f"{_url_row(stale_id)} {TPL.BUTTON_RESTORE}").click()

    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(TRASH_UI.NOT_IN_TRASH)
    expect(page.locator(_url_row(stale_id))).to_have_count(0)
    expect(page.locator(_url_row(other_id))).to_have_count(1)
