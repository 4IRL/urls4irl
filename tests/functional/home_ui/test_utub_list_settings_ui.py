from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, Route, expect

from backend.models.user_preferences import UtubSort
from backend.utils.strings.utub_strs import (
    PANEL_SETTINGS_REVERTED,
    PANEL_SETTINGS_SAVE_FAILED,
    UTUB_LIST_SETTINGS_LIST_TOTALS_HIDDEN_NOTICE,
    UTUB_LIST_SETTINGS_LIST_TOTALS_LABEL,
    UTUB_LIST_SETTINGS_LIST_TOTALS_SHOWN_NOTICE,
    UTUB_LIST_SETTINGS_ROW_COUNTS_HIDDEN_NOTICE,
    UTUB_LIST_SETTINGS_ROW_COUNTS_LABEL,
    UTUB_LIST_SETTINGS_ROW_COUNTS_SHOWN_NOTICE,
    UTUB_LIST_SETTINGS_SECTION_TITLE,
    UTUB_LIST_SETTINGS_SORT_LABEL,
    UTUB_LIST_SETTINGS_SORT_NOTICE_PREFIX,
    UTUB_LIST_SETTINGS_SORT_OPTION_NAME_AZ,
    UTUB_LIST_SETTINGS_SORT_OPTION_NEWEST,
    UTUB_LIST_SETTINGS_SORT_OPTION_OLDEST,
    UTUB_LIST_SETTINGS_SORT_OPTION_OPENED,
    UTUB_LIST_SETTINGS_SORT_OPTION_RECENT,
    UTUB_ROW_MEMBER_PLURAL,
    UTUB_ROW_MEMBER_SINGULAR,
    UTUB_ROW_URL_PLURAL,
    UTUB_ROW_URL_SINGULAR,
)
from tests.functional.db_utils import (
    count_live_urls_and_members,
    create_utubs_owned_by,
    get_url_in_utub,
    get_utub_id_by_name,
    get_utub_this_user_created,
    set_utub_list_preferences,
    set_utub_timeline,
    trash_utub_url,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import TrashPanelLocators as TPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    wait_for_css_transitions_to_finish,
    wait_then_click_element,
)
from tests.functional.trash_ui.playwright_utils import open_trash
from tests.functional.urls_ui.playwright_login_utils import (
    click_delete_on_selected_url_and_wait_for_toast,
)
from tests.functional.utubs_ui.playwright_utils import (
    create_utub,
    open_utub_name_filter,
    update_utub_name,
)

pytestmark = pytest.mark.home_ui

USER_ID_FOR_TEST = 1

DECK_NAMES = "#listUTubs > .UTubSelector .UTubName"
DECK_ROWS = "#listUTubs > .UTubSelector"
POPOVER_ERROR_STATUS = (
    f"{HPL.PANEL_SETTINGS_POPOVER} .panelSettingsStatus[data-state='error']"
)
UTUB_PREFERENCES_ROUTE = "**/users/preferences/utubs"
MOCK_UTUB_COUNT = 5

# value -> (option label, spoken label in the live-region notice)
SORT_UI: dict[str, tuple[str, str]] = {
    "recent_activity": (UTUB_LIST_SETTINGS_SORT_OPTION_RECENT, "Recent activity"),
    "last_opened": (UTUB_LIST_SETTINGS_SORT_OPTION_OPENED, "Last opened by me"),
    "name_az": (UTUB_LIST_SETTINGS_SORT_OPTION_NAME_AZ, "Name A to Z"),
    "newest_created": (UTUB_LIST_SETTINGS_SORT_OPTION_NEWEST, "Newest created"),
    "oldest_created": (UTUB_LIST_SETTINGS_SORT_OPTION_OLDEST, "Oldest created"),
}

# Deck order (by MockUTub_<n>) under each sort for the timeline seeded by
# seed_sortable_mock_utubs. Every order is distinct from the others.
ORDER_BY_SORT: dict[str, list[int]] = {
    "recent_activity": [5, 4, 2, 1, 3],
    "last_opened": [3, 4, 2, 5, 1],
    "name_az": [1, 2, 3, 4, 5],
    "newest_created": [4, 2, 5, 1, 3],
    "oldest_created": [3, 1, 5, 2, 4],
}

# (days ago created, days ago last updated) of MockUTub_<n>; MockUTub_3 was also
# opened by the test user 9.2 days ago (older than MockUTub_1's last update, so
# "recent activity" and "last opened" differ).
_TIMELINE_DAYS: dict[int, tuple[float, float]] = {
    3: (10, 10),
    1: (9, 9),
    5: (8, 2),
    2: (7, 7),
    4: (6, 6),
}
_OPENED_MOCK_UTUB = 3
_OPENED_DAYS_AGO = 9.2

_IN_DECK_VIEWPORT_JS = """(utubName) => {
    const row = Array.from(
        document.querySelectorAll('#listUTubs > .UTubSelector')
    ).find((candidate) => candidate.querySelector('.UTubName').textContent === utubName);
    if (!row) return false;
    let scroller = row.parentElement;
    while (scroller) {
        const overflowY = getComputedStyle(scroller).overflowY;
        if (overflowY === 'auto' || overflowY === 'scroll') break;
        scroller = scroller.parentElement;
    }
    const viewport = (scroller || document.documentElement).getBoundingClientRect();
    const rect = row.getBoundingClientRect();
    return rect.top >= viewport.top - 1 && rect.bottom <= viewport.bottom + 1;
}"""

_DECK_SCROLL_STATE_JS = """() => {
    const row = document.querySelector('#listUTubs > .UTubSelector');
    let scroller = row.parentElement;
    while (scroller) {
        const overflowY = getComputedStyle(scroller).overflowY;
        if (overflowY === 'auto' || overflowY === 'scroll') break;
        scroller = scroller.parentElement;
    }
    return {
        scrollable: scroller.scrollHeight > scroller.clientHeight,
        scrollTop: scroller.scrollTop,
    };
}"""

# WCAG contrast of the row-counts text against the row's effective background:
# every ancestor background is composited (root first) through a canvas, which
# also normalises any computed colour syntax to sRGB.
_COUNTS_CONTRAST_JS = """(rowSelector) => {
    const row = document.querySelector(rowSelector);
    if (!row) return null;
    const counts = row.querySelector('.UTubRowCounts');
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    const toRgba = (css) => {
        context.clearRect(0, 0, 1, 1);
        context.fillStyle = '#000';
        context.fillStyle = css;
        context.fillRect(0, 0, 1, 1);
        const data = context.getImageData(0, 0, 1, 1).data;
        return [data[0], data[1], data[2], data[3] / 255];
    };
    const over = (top, bottom) => [0, 1, 2].map(
        (index) => top[index] * top[3] + bottom[index] * (1 - top[3])
    );
    const chain = [];
    for (let node = row; node; node = node.parentElement) chain.unshift(node);
    let background = [255, 255, 255];
    for (const node of chain) {
        background = over(toRgba(getComputedStyle(node).backgroundColor), background);
    }
    const text = over(toRgba(getComputedStyle(counts).color), background);
    const luminance = (rgb) => {
        const [red, green, blue] = rgb.map((channel) => {
            const unit = channel / 255;
            return unit <= 0.03928 ? unit / 12.92 : Math.pow((unit + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
    };
    const lighter = Math.max(luminance(text), luminance(background));
    const darker = Math.min(luminance(text), luminance(background));
    return (lighter + 0.05) / (darker + 0.05);
}"""

_MIN_TEXT_CONTRAST = 4.5


def seed_sortable_mock_utubs(app: Flask) -> None:
    """Pin the created / updated / opened timestamps of MockUTub_1..5 so every
    sort option yields a distinct, known order (ORDER_BY_SORT)."""
    now = datetime.now(timezone.utc)
    for number, (created_days, updated_days) in _TIMELINE_DAYS.items():
        utub_id = get_utub_id_by_name(app, f"MockUTub_{number}")
        opened = (
            now - timedelta(days=_OPENED_DAYS_AGO)
            if number == _OPENED_MOCK_UTUB
            else None
        )
        set_utub_timeline(
            app,
            utub_id,
            created_at=now - timedelta(days=created_days),
            last_updated=now - timedelta(days=updated_days),
            user_id=USER_ID_FOR_TEST,
            last_opened_at=opened,
        )


def mock_names(*, order: list[int]) -> list[str]:
    return [f"MockUTub_{number}" for number in order]


def expect_deck_order(*, page: Page, names: list[str]) -> None:
    expect(page.locator(DECK_NAMES)).to_have_text(names)


def sort_select(*, page: Page, surface: str = HPL.PANEL_SETTINGS_POPOVER) -> Locator:
    return page.locator(surface).get_by_role(
        "combobox", name=UTUB_LIST_SETTINGS_SORT_LABEL, exact=True
    )


def counts_switch(*, page: Page, surface: str = HPL.PANEL_SETTINGS_POPOVER) -> Locator:
    return page.locator(surface).get_by_role(
        "switch", name=UTUB_LIST_SETTINGS_ROW_COUNTS_LABEL, exact=True
    )


def totals_switch(*, page: Page, surface: str = HPL.PANEL_SETTINGS_POPOVER) -> Locator:
    return page.locator(surface).get_by_role(
        "switch", name=UTUB_LIST_SETTINGS_LIST_TOTALS_LABEL, exact=True
    )


def sort_notice(*, sort: str) -> str:
    return f"{UTUB_LIST_SETTINGS_SORT_NOTICE_PREFIX}{SORT_UI[sort][1]}"


def open_utubs_settings(*, page: Page) -> None:
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SETTINGS_GEAR)
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()
    expect(sort_select(page=page)).to_be_visible()


def close_settings_popover(*, page: Page) -> None:
    page.keyboard.press("Escape")
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_hidden()


def pick_sort(*, page: Page, sort: str, surface: str = HPL.PANEL_SETTINGS_POPOVER):
    """Pick ``sort`` and wait for the saved-notice, which is announced only after
    the debounced PATCH has been answered and applied."""
    sort_select(page=page, surface=surface).select_option(label=SORT_UI[sort][0])
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        sort_notice(sort=sort)
    )


def row_count_numbers(*, page: Page, utub_id: int) -> Locator:
    return page.locator(f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}'] .UTubRowCountNum")


def expect_row_counts(*, page: Page, utub_id: int, urls: int, members: int) -> None:
    expect(row_count_numbers(page=page, utub_id=utub_id)).to_have_text(
        [str(urls), str(members)]
    )


def trash_button(*, page: Page, name: str) -> Locator:
    return page.get_by_role("button", name=name, exact=True)


def expected_counts_label(*, urls: int, members: int) -> str:
    url_noun = UTUB_ROW_URL_SINGULAR if urls == 1 else UTUB_ROW_URL_PLURAL
    member_noun = UTUB_ROW_MEMBER_SINGULAR if members == 1 else UTUB_ROW_MEMBER_PLURAL
    return f", {urls} {url_noun}, {members} {member_noun}"


def _fail_all_saves(*, page: Page) -> None:
    """Answer every preferences request with a 500 until the page closes."""

    def fulfill_with_server_error(route: Route) -> None:
        route.fulfill(
            status=500,
            content_type="application/json",
            body='{"status": "Failure", "message": "forced failure"}',
        )

    page.route(UTUB_PREFERENCES_ROUTE, fulfill_with_server_error)


def _owned_utub_id(*, app: Flask) -> int:
    return get_utub_this_user_created(app, USER_ID_FOR_TEST).id


@pytest.mark.parametrize(
    "sort", ["last_opened", "name_az", "newest_created", "oldest_created"]
)
def test_each_sort_reorders_immediately_and_persists_across_reload(
    page: Page, create_test_utubmembers, provide_app: Flask, sort: str
):
    """
    GIVEN a user whose five UTubs have distinct activity, open, name and created order
    WHEN they pick a sort in the UTubs gear
    THEN the deck reorders at once, and the choice and order survive a reload
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect_deck_order(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )

    open_utubs_settings(page=page)
    expect(sort_select(page=page)).to_have_value("recent_activity")
    pick_sort(page=page, sort=sort)
    expect_deck_order(page=page, names=mock_names(order=ORDER_BY_SORT[sort]))

    page.reload()
    expect_deck_order(page=page, names=mock_names(order=ORDER_BY_SORT[sort]))
    open_utubs_settings(page=page)
    expect(sort_select(page=page)).to_have_value(sort)


def test_sort_change_keeps_the_name_filter_and_its_hidden_rows(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a name filter that hides the five mock UTubs and shows three "Pear" UTubs
    WHEN the user picks name A-Z
    THEN the mock rows stay hidden, the filter text is unchanged, and the visible
        rows are the filtered subset in name order
    """
    app = provide_app
    pears = ["Pear 2", "Pear 3", "Pear 1"]
    create_utubs_owned_by(app, USER_ID_FOR_TEST, pears)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utub_name_filter(page=page).fill("Pear")
    visible_names = page.locator(DECK_NAMES).filter(visible=True)
    expect(visible_names).to_have_count(len(pears))

    open_utubs_settings(page=page)
    pick_sort(page=page, sort="name_az")

    expect(visible_names).to_have_text(sorted(pears))
    mock_rows = page.locator(DECK_NAMES).filter(has_text="MockUTub_")
    expect(mock_rows).to_have_count(MOCK_UTUB_COUNT)
    for index in range(MOCK_UTUB_COUNT):
        expect(mock_rows.nth(index)).to_be_hidden()
    expect(page.locator(HPL.UTUB_SEARCH_INPUT)).to_have_value("Pear")


@pytest.mark.parametrize("sort", ["last_opened", "recent_activity"])
def test_selecting_a_utub_never_reorders_the_deck(
    page: Page, create_test_utubmembers, provide_app: Flask, sort: str
):
    """
    GIVEN a deck sorted by last opened or recent activity
    WHEN the user selects a UTub that is not at the top
    THEN the deck order is unchanged and the selection stays on the clicked row
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    set_utub_list_preferences(app, USER_ID_FOR_TEST, utub_sort=UtubSort(sort))
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    order = ORDER_BY_SORT[sort]
    expect_deck_order(page=page, names=mock_names(order=order))
    clicked_number = order[-1]
    clicked_id = get_utub_id_by_name(app, f"MockUTub_{clicked_number}")

    wait_then_click_element(
        page=page, css_selector=f"{HPL.SELECTORS_UTUB}[utubid='{clicked_id}']"
    )

    expect(page.locator(HPL.SELECTOR_SELECTED_UTUB)).to_contain_text(
        f"MockUTub_{clicked_number}"
    )
    expect_deck_order(page=page, names=mock_names(order=order))


def test_a_sort_pick_and_two_switch_flips_in_quick_succession_all_persist(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the UTubs popover open on the defaults
    WHEN the user picks name A-Z and flips both switches without waiting for a save
    THEN the deck shows all three changes, and all three survive a reload
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utubs_settings(page=page)

    sort_select(page=page).select_option(label=SORT_UI["name_az"][0])
    # Real pointer clicks: the status slot reserves its height, so the "Saving..."
    # line cannot shift the switches between a click's mousedown and mouseup.
    counts_switch(page=page).click()
    totals_switch(page=page).click()

    deck = page.locator(HPL.UTUB_DECK)
    expect(deck).to_have_class(re.compile(r"showUTubRowCounts"))
    expect(deck).to_have_class(re.compile(r"hideListTotals"))
    expect_deck_order(page=page, names=mock_names(order=ORDER_BY_SORT["name_az"]))

    page.reload()
    expect(deck).to_have_class(re.compile(r"showUTubRowCounts"))
    expect(deck).to_have_class(re.compile(r"hideListTotals"))
    expect_deck_order(page=page, names=mock_names(order=ORDER_BY_SORT["name_az"]))
    open_utubs_settings(page=page)
    expect(sort_select(page=page)).to_have_value("name_az")
    expect(counts_switch(page=page)).to_have_attribute("aria-checked", "true")
    expect(totals_switch(page=page)).to_have_attribute("aria-checked", "false")


def test_the_saving_status_line_never_shifts_the_switches(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the UTubs popover open and a sort save held in flight
    WHEN the status line shows its "Saving..." text
    THEN both switches keep exactly the position they had before the status appeared
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utubs_settings(page=page)
    held: list[Route] = []
    page.route(UTUB_PREFERENCES_ROUTE, lambda route: held.append(route))
    counts_before = counts_switch(page=page).bounding_box()
    totals_before = totals_switch(page=page).bounding_box()
    assert counts_before is not None and totals_before is not None

    sort_select(page=page).select_option(label=SORT_UI["name_az"][0])

    expect(
        page.locator(f"{HPL.PANEL_SETTINGS_POPOVER} .panelSettingsStatus:not(:empty)")
    ).to_be_visible()
    assert counts_switch(page=page).bounding_box() == counts_before
    assert totals_switch(page=page).bounding_box() == totals_before
    for route in held:
        route.continue_()
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        sort_notice(sort="name_az")
    )


@pytest.mark.parametrize("viewport_width", [1280, 420])
def test_the_trash_label_is_vertically_centered_in_its_row(
    page: Page, create_test_utubmembers, provide_app: Flask, viewport_width: int
):
    """
    GIVEN the UTub deck at a desktop or a mobile width
    WHEN the pinned Trash row renders
    THEN its label has the same space above (to the row's rule) as below (to the deck's end)
    """
    app = provide_app
    page.set_viewport_size({"width": viewport_width, "height": 900})
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)

    label = page.locator("#TrashSelector > span").first
    expect(label).to_be_visible()
    gaps = page.evaluate(
        """() => {
            const label = document.querySelector("#TrashSelector > span").getBoundingClientRect();
            const ruleBottom = document.querySelector("#TrashSelectorWrap").getBoundingClientRect().top
                + parseFloat(getComputedStyle(document.querySelector("#TrashSelectorWrap")).borderTopWidth);
            const deckBottom = document.querySelector("#UTubDeck").getBoundingClientRect().bottom;
            return {above: label.top - ruleBottom, below: deckBottom - label.bottom};
        }"""
    )

    assert abs(gaps["above"] - gaps["below"]) <= 1, gaps


def test_create_under_name_az_lands_mid_list_and_is_scrolled_into_view(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a name A-Z user with enough UTubs that the deck scrolls
    WHEN they create a UTub whose name sorts into the middle of the list
    THEN the row lands at its alphabetical place (not first) and is scrolled into view
    """
    app = provide_app
    fillers = [f"Filler {number:02d}" for number in range(1, 41)]
    create_utubs_owned_by(app, USER_ID_FOR_TEST, fillers)
    set_utub_list_preferences(app, USER_ID_FOR_TEST, utub_sort=UtubSort.NAME_AZ)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect(page.locator(DECK_NAMES)).to_have_count(len(fillers) + MOCK_UTUB_COUNT)
    new_name = "Filler 30b"
    neighbour = "Filler 30"
    assert page.evaluate(_DECK_SCROLL_STATE_JS) == {"scrollable": True, "scrollTop": 0}
    assert not page.evaluate(_IN_DECK_VIEWPORT_JS, neighbour), "Test premise violated"

    create_utub(page=page, utub_name=new_name, utub_description="")
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)

    expected_names = sorted(
        [*fillers, *mock_names(order=ORDER_BY_SORT["name_az"]), new_name],
        key=str.casefold,
    )
    assert 0 < expected_names.index(new_name) < len(expected_names) - 1
    expect_deck_order(page=page, names=expected_names)
    page.wait_for_function(_IN_DECK_VIEWPORT_JS, arg=new_name)
    assert page.evaluate(_DECK_SCROLL_STATE_JS)["scrollTop"] > 0


def test_rename_under_name_az_moves_the_row(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a name A-Z user with their own UTub selected
    WHEN they rename it to a name that sorts last
    THEN its row moves to the end of the deck
    """
    app = provide_app
    set_utub_list_preferences(app, USER_ID_FOR_TEST, utub_sort=UtubSort.NAME_AZ)
    owned = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=owned.id
    )
    expect_deck_order(page=page, names=mock_names(order=ORDER_BY_SORT["name_az"]))

    renamed = "Zeta renamed"
    update_utub_name(page=page, utub_name=renamed)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

    others = [
        name
        for name in mock_names(order=ORDER_BY_SORT["name_az"])
        if name != owned.name
    ]
    expect_deck_order(page=page, names=[*others, renamed])
    expect(page.locator(HPL.SELECTOR_SELECTED_UTUB)).to_contain_text(renamed)


def test_sort_change_scrolls_the_selected_row_back_into_view(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a long deck with the top (most recent) UTub selected
    WHEN the sort changes to name A-Z, which moves that UTub to the bottom
    THEN the deck scrolls so the selected row is in view
    """
    app = provide_app
    create_utubs_owned_by(
        app, USER_ID_FOR_TEST, [f"Filler {number:02d}" for number in range(1, 41)]
    )
    selected_name = "ZZ Selected"
    selected_id = create_utubs_owned_by(app, USER_ID_FOR_TEST, [selected_name])[
        selected_name
    ]
    now = datetime.now(timezone.utc)
    set_utub_timeline(
        app,
        selected_id,
        created_at=now,
        last_updated=now + timedelta(hours=1),
    )
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    wait_then_click_element(
        page=page, css_selector=f"{HPL.SELECTORS_UTUB}[utubid='{selected_id}']"
    )
    expect(page.locator(HPL.SELECTOR_SELECTED_UTUB)).to_contain_text(selected_name)
    expect(page.locator(DECK_NAMES).first).to_have_text(selected_name)
    assert page.evaluate(_DECK_SCROLL_STATE_JS) == {"scrollable": True, "scrollTop": 0}

    open_utubs_settings(page=page)
    pick_sort(page=page, sort="name_az")

    expect(page.locator(DECK_NAMES).last).to_have_text(selected_name)
    expect(page.locator(HPL.SELECTOR_SELECTED_UTUB)).to_have_count(1)
    expect(page.locator(HPL.SELECTOR_SELECTED_UTUB)).to_contain_text(selected_name)
    expect(page.locator(DECK_ROWS).last).to_have_class(re.compile(r"\bactive\b"))
    page.wait_for_function(_IN_DECK_VIEWPORT_JS, arg=selected_name)
    assert page.evaluate(_DECK_SCROLL_STATE_JS)["scrollTop"] > 0


def test_counts_toggle_shows_each_utub_numbers_and_hides_them_again(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN counts are off (the default) so every row's counts group is display:none
    WHEN the user turns "Show URL and member counts" on, then off
    THEN each row shows its real URL and member numbers, then hides them again
    """
    app = provide_app
    # A UTub with no URLs and a single member covers the singular wording.
    solo_name = "Solo UTub"
    solo_id = create_utubs_owned_by(app, USER_ID_FOR_TEST, [solo_name])[solo_name]
    utub_ids = [
        get_utub_id_by_name(app, f"MockUTub_{number}")
        for number in range(1, MOCK_UTUB_COUNT + 1)
    ]
    for utub_id in utub_ids:
        urls, members = count_live_urls_and_members(app, utub_id)
        assert urls > 0 and members > 0, "Test premise violated: empty counts"
    utub_ids.append(solo_id)
    assert count_live_urls_and_members(app, solo_id) == (0, 1)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    deck = page.locator("#listUTubs")
    all_counts = deck.locator(".UTubRowCounts")
    expect(all_counts).to_have_count(len(utub_ids))
    for index in range(len(utub_ids)):
        expect(all_counts.nth(index)).to_have_css("display", "none")
    # Counts off: the screen-reader label is not in the accessibility tree either.
    assert "URL" not in deck.aria_snapshot()

    open_utubs_settings(page=page)
    switch = counts_switch(page=page)
    expect(switch).to_have_attribute("aria-checked", "false")
    switch.click()
    expect(switch).to_have_attribute("aria-checked", "true")
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        UTUB_LIST_SETTINGS_ROW_COUNTS_SHOWN_NOTICE
    )
    for index in range(len(utub_ids)):
        expect(all_counts.nth(index)).to_be_visible()
    for utub_id in utub_ids:
        urls, members = count_live_urls_and_members(app, utub_id)
        expect_row_counts(page=page, utub_id=utub_id, urls=urls, members=members)
        row_counts = page.locator(
            f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}'] .UTubRowCounts"
        )
        # Announced once as text; the two icon+number groups are hidden from AT.
        expect(row_counts.locator(".visually-hidden")).to_have_text(
            expected_counts_label(urls=urls, members=members)
        )
        expect(row_counts.locator(".UTubRowCount[aria-hidden='true']")).to_have_count(2)
        expect(
            row_counts.locator(".UTubRowCount:not([aria-hidden='true'])")
        ).to_have_count(0)

    switch.click()
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        UTUB_LIST_SETTINGS_ROW_COUNTS_HIDDEN_NOTICE
    )
    for index in range(len(utub_ids)):
        expect(all_counts.nth(index)).to_have_css("display", "none")
    assert "URL" not in deck.aria_snapshot()


def test_deleting_a_url_decrements_the_selected_utub_count(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN counts are on and a UTub with URLs is selected
    WHEN the user deletes a URL
    THEN that UTub's URL count drops by one and its member count is unchanged
    """
    app = provide_app
    set_utub_list_preferences(app, USER_ID_FOR_TEST, show_row_counts=True)
    utub_id = _owned_utub_id(app=app)
    urls, members = count_live_urls_and_members(app, utub_id)
    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=USER_ID_FOR_TEST,
        utub_id=utub_id,
        utub_url_id=get_url_in_utub(app, utub_id).id,
    )
    expect_row_counts(page=page, utub_id=utub_id, urls=urls, members=members)

    click_delete_on_selected_url_and_wait_for_toast(page=page)

    expect_row_counts(page=page, utub_id=utub_id, urls=urls - 1, members=members)


def test_restoring_a_trashed_url_increments_the_selected_utub_count(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN counts are on, a UTub with one trashed URL is selected
    WHEN the user restores that URL from Trash into the UTub
    THEN the UTub's URL count goes up by one
    """
    app = provide_app
    set_utub_list_preferences(app, USER_ID_FOR_TEST, show_row_counts=True)
    utub_id = _owned_utub_id(app=app)
    trash_utub_url(app, get_url_in_utub(app, utub_id).id, USER_ID_FOR_TEST, [])
    urls, members = count_live_urls_and_members(app, utub_id)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    expect_row_counts(page=page, utub_id=utub_id, urls=urls, members=members)

    open_trash(page=page)
    page.locator(f"{TPL.ROWS_URLS} {TPL.BUTTON_RESTORE}").first.click()

    expect_row_counts(page=page, utub_id=utub_id, urls=urls + 1, members=members)


def test_keyboard_stepping_the_sort_select_saves_one_settled_value(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the sort select focused with the default option chosen
    WHEN the user steps through three options with ArrowDown
    THEN one debounced save is sent for the last option, and it persists across reload
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    saves: list[str] = []
    page.on(
        "request",
        lambda request: (
            saves.append(request.method)
            if "/users/preferences/utubs" in request.url
            else None
        ),
    )
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utubs_settings(page=page)
    select = sort_select(page=page)
    select.focus()
    for _ in range(3):
        page.keyboard.press("ArrowDown")

    final_sort = "newest_created"
    expect(select).to_have_value(final_sort)
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        sort_notice(sort=final_sort)
    )
    expect_deck_order(page=page, names=mock_names(order=ORDER_BY_SORT[final_sort]))
    # Let any straggler request (a second, unsettled PATCH) land before counting.
    page.wait_for_load_state("networkidle")

    page.reload()
    expect_deck_order(page=page, names=mock_names(order=ORDER_BY_SORT[final_sort]))
    open_utubs_settings(page=page)
    expect(sort_select(page=page)).to_have_value(final_sort)
    assert saves == ["PATCH"]


def test_totals_toggle_hides_and_restores_deck_title_and_trash_numbers(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN list totals on with a trashed URL, so the deck title and Trash show numbers
    WHEN the user turns "Show list totals" off, then on
    THEN both numbers hide (Trash's accessible name loses its count), then both return
    """
    app = provide_app
    owned_id = _owned_utub_id(app=app)
    trash_utub_url(app, get_url_in_utub(app, owned_id).id, USER_ID_FOR_TEST, [])
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    deck_total = page.locator("#UTubDeckCount")
    trash_total = page.locator(TPL.SELECTOR_COUNT)
    expect(deck_total).to_have_text(f"({MOCK_UTUB_COUNT})")
    expect(trash_total).to_have_text("(1)")
    expect(trash_button(page=page, name="Trash (1)")).to_be_visible()

    open_utubs_settings(page=page)
    switch = totals_switch(page=page)
    expect(switch).to_have_attribute("aria-checked", "true")
    switch.click()
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        UTUB_LIST_SETTINGS_LIST_TOTALS_HIDDEN_NOTICE
    )
    expect(deck_total).to_be_hidden()
    expect(trash_total).to_be_hidden()
    expect(trash_button(page=page, name="Trash")).to_be_visible()
    expect(trash_button(page=page, name=re.compile(r"\(\d+\)"))).to_have_count(0)

    switch.click()
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        UTUB_LIST_SETTINGS_LIST_TOTALS_SHOWN_NOTICE
    )
    expect(deck_total).to_have_text(f"({MOCK_UTUB_COUNT})")
    expect(trash_total).to_have_text("(1)")
    expect(trash_button(page=page, name="Trash (1)")).to_be_visible()


def test_reload_with_counts_on_and_totals_off_renders_that_state_on_first_load(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user who saved counts on and totals off
    WHEN the home page loads
    THEN the server-rendered deck already carries both state classes (no JS needed),
        and the page shows row counts with the totals hidden
    """
    app = provide_app
    set_utub_list_preferences(
        app, USER_ID_FOR_TEST, show_row_counts=True, show_list_totals=False
    )
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)

    server_html = page.request.get(page.url).text()
    deck_tag = re.search(r'<div id="UTubDeck" class="([^"]*)"', server_html)
    assert deck_tag is not None
    server_classes = deck_tag.group(1).split()
    assert "showUTubRowCounts" in server_classes
    assert "hideListTotals" in server_classes

    expect(page.locator(HPL.UTUB_DECK)).to_have_class(re.compile(r"showUTubRowCounts"))
    expect(page.locator("#listUTubs .UTubRowCounts").first).to_be_visible()
    expect(page.locator("#UTubDeckCount")).to_be_hidden()
    expect(page.locator(TPL.SELECTOR_COUNT)).to_be_hidden()
    open_utubs_settings(page=page)
    expect(counts_switch(page=page)).to_have_attribute("aria-checked", "true")
    expect(totals_switch(page=page)).to_have_attribute("aria-checked", "false")


def test_controls_are_found_by_role_and_name_and_select_is_keyboard_operable(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the UTubs settings popover
    WHEN controls are looked up by role and accessible name
    THEN the sort select and both switches resolve uniquely, and the select takes
        keyboard input
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utubs_settings(page=page)

    expect(sort_select(page=page)).to_have_count(1)
    expect(counts_switch(page=page)).to_have_count(1)
    expect(totals_switch(page=page)).to_have_count(1)
    expect(counts_switch(page=page)).to_have_attribute("aria-checked", "false")
    expect(totals_switch(page=page)).to_have_attribute("aria-checked", "true")

    sort_select(page=page).focus()
    expect(sort_select(page=page)).to_be_focused()
    page.keyboard.press("ArrowDown")
    expect(sort_select(page=page)).to_have_value("last_opened")


def test_the_lone_section_has_no_heading_but_stays_a_labelled_expanded_group(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the UTubs settings popover, whose "Just for you" group holds one section
    WHEN it opens
    THEN no "Your UTub list" heading or toggle shows, the section is a group named
        by that title, and its controls sit directly under the scope heading
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utubs_settings(page=page)

    section = page.locator(
        HPL.SETTINGS_GROUP_SECTION_FORMAT.format(
            scope=HPL.SETTINGS_GROUP_USER, section_id="utubs-list"
        )
    )
    expect(section).to_have_count(1)
    expect(section).to_have_attribute("role", "group")
    expect(section).to_have_attribute("aria-label", UTUB_LIST_SETTINGS_SECTION_TITLE)
    expect(section.locator("h3")).to_be_hidden()
    expect(section.locator(".panelSettingsSectionToggle")).to_be_hidden()
    expect(section.locator(".panelSettingsSectionToggleTitle")).to_be_hidden()
    expect(sort_select(page=page)).to_be_visible()
    expect(counts_switch(page=page)).to_be_visible()
    expect(totals_switch(page=page)).to_be_visible()


def _expect_failure_surfaced(*, page: Page) -> None:
    """The shell announced the failed save and shows the inline reverted message,
    so the failure path (not a click that never toggled) is what was observed."""
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        PANEL_SETTINGS_SAVE_FAILED
    )
    expect(page.locator(POPOVER_ERROR_STATUS)).to_have_text(PANEL_SETTINGS_REVERTED)


@pytest.mark.parametrize(
    "switch_for, deck_class, saved_checked",
    [
        (counts_switch, "showUTubRowCounts", "false"),
        (totals_switch, "hideListTotals", "true"),
    ],
    ids=["row_counts", "list_totals"],
)
def test_a_failed_switch_save_reverts_the_switch_and_the_deck(
    page: Page,
    create_test_urls,
    provide_app: Flask,
    switch_for,
    deck_class: str,
    saved_checked: str,
):
    """
    GIVEN the preferences endpoint answers 500
    WHEN the user flips the row-counts or list-totals switch
    THEN the failure is announced, the switch reverts with focus kept, the deck
        never takes the class, and a reload still shows the saved value
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utubs_settings(page=page)
    _fail_all_saves(page=page)
    switch = switch_for(page=page)
    expect(switch).to_have_attribute("aria-checked", saved_checked)

    with page.expect_response(UTUB_PREFERENCES_ROUTE):
        switch.click()

    _expect_failure_surfaced(page=page)
    expect(switch).to_have_attribute("aria-checked", saved_checked)
    expect(switch).to_be_focused()
    deck = page.locator(HPL.UTUB_DECK)
    class_pattern = re.compile(rf"\b{deck_class}\b")
    expect(deck).not_to_have_class(class_pattern)

    page.reload()
    expect(page.locator(HPL.UTUB_DECK)).not_to_have_class(class_pattern)
    open_utubs_settings(page=page)
    expect(switch_for(page=page)).to_have_attribute("aria-checked", saved_checked)


def test_a_failed_sort_save_reverts_the_select_and_keeps_the_order(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the preferences endpoint answers 500
    WHEN the user picks name A-Z
    THEN the failure is announced, the select returns to the saved sort with focus
        kept, the deck order is unchanged, and a reload still shows the saved sort
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utubs_settings(page=page)
    _fail_all_saves(page=page)
    select = sort_select(page=page)

    with page.expect_response(UTUB_PREFERENCES_ROUTE):
        select.select_option(label=SORT_UI["name_az"][0])

    _expect_failure_surfaced(page=page)
    expect(select).to_have_value("recent_activity")
    expect(select).to_be_focused()
    expect_deck_order(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )

    page.reload()
    expect_deck_order(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )
    open_utubs_settings(page=page)
    expect(sort_select(page=page)).to_have_value("recent_activity")


def test_focus_returns_to_the_gear_after_the_popover_closes(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the UTubs popover opened from the keyboard
    WHEN the user presses Escape
    THEN the popover closes and focus is back on the UTubs gear
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    gear = page.locator(HPL.BUTTON_UTUB_SETTINGS_GEAR)
    expect(gear).to_be_visible()
    gear.focus()
    page.keyboard.press("Enter")
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()

    close_settings_popover(page=page)

    expect(gear).to_be_focused()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_row_counts_meet_text_contrast_on_every_row_state(
    page: Page, create_test_urls, provide_app: Flask, theme: str
):
    """
    GIVEN counts on, in the light or dark theme
    WHEN the odd, even, selected and hovered rows are measured
    THEN the counts text has at least 4.5:1 contrast against each row's background
    """
    app = provide_app
    set_utub_list_preferences(app, USER_ID_FOR_TEST, show_row_counts=True)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    page.evaluate(
        "(name) => document.documentElement.setAttribute('data-theme', name)", theme
    )
    deck = page.locator("#listUTubs")
    selected_id = _owned_utub_id(app=app)
    wait_then_click_element(
        page=page, css_selector=f"{HPL.SELECTORS_UTUB}[utubid='{selected_id}']"
    )
    expect(page.locator(HPL.SELECTOR_SELECTED_UTUB)).to_have_count(1)

    rows = "#listUTubs > .UTubSelector"
    states = {
        "odd": f"{rows}.odd:not(.active)",
        "even": f"{rows}.even:not(.active)",
        "active": f"{rows}.active",
    }
    page.mouse.move(0, 0)
    wait_for_css_transitions_to_finish(locator=deck)
    ratios = {
        state: page.evaluate(_COUNTS_CONTRAST_JS, selector)
        for state, selector in states.items()
    }

    hover_target = page.locator(states["even"]).last
    hover_target.hover()
    wait_for_css_transitions_to_finish(locator=deck)
    ratios["hover"] = page.evaluate(_COUNTS_CONTRAST_JS, f"{rows}:hover")

    for state, ratio in ratios.items():
        assert ratio is not None, f"No {state} row to measure ({theme})"
        assert ratio >= _MIN_TEXT_CONTRAST, f"{state} row, {theme} theme: {ratio:.2f}"
