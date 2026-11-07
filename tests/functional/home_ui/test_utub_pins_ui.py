from __future__ import annotations

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, Route, expect

from backend.utils.strings.utub_strs import (
    PANEL_SETTINGS_REVERTED,
    PANEL_SETTINGS_SAVE_FAILED,
    UTUB_PINS_CAP_REACHED,
    UTUB_PINS_EMPTY_HINT,
    UTUB_PINS_NO_MATCH,
    UTUB_PINS_NONE_LEFT_HINT,
    UTUB_PINS_PINNED_NOTICE,
    UTUB_PINS_UNPINNED_NOTICE,
    UTUB_PINS_UTUB_GONE,
)
from backend.utubs.constants import MAX_PINNED_UTUBS
from tests.functional.db_utils import (
    create_utubs_owned_by,
    get_utub_id_by_name,
    pin_utubs_for_user,
    trash_utub,
)
from tests.functional.home_ui.test_utub_list_settings_ui import (
    DECK_NAMES,
    ORDER_BY_SORT,
    USER_ID_FOR_TEST,
    expect_deck_order,
    mock_names,
    open_utubs_settings,
    pick_sort,
    seed_sortable_mock_utubs,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import TrashPanelLocators as TPL
from tests.functional.playwright_utils import login_user_to_home_page
from tests.functional.trash_ui.playwright_utils import open_trash, open_utubs_tab
from tests.functional.utubs_ui.playwright_utils import open_utub_name_filter

pytestmark = pytest.mark.home_ui

UTUB_PIN_ROUTE = "**/utubs/*/pin"
DECK_PINNED_NAMES = "#listUTubs > .UTubSelector:has(> .UTubPinIcon) .UTubName"
DECK_PIN_ICONS = "#listUTubs > .UTubSelector > .UTubPinIcon"
DECK_PIN_DIVIDER = "#UTubPinDivider"
PICKER_INPUT = "#utub-pins-input"
NONE_LEFT_HINT = "#utub-pins-none-left"


def pins_body(*, page: Page, surface: str = HPL.PANEL_SETTINGS_POPOVER) -> Locator:
    return page.locator(f"{surface} .utubPins")


def picker_input(*, page: Page, surface: str = HPL.PANEL_SETTINGS_POPOVER) -> Locator:
    return pins_body(page=page, surface=surface).locator(PICKER_INPUT)


def remove_button(
    *, page: Page, utub_id: int, surface: str = HPL.PANEL_SETTINGS_POPOVER
) -> Locator:
    return pins_body(page=page, surface=surface).locator(
        f"[id='utub-pins-remove-{utub_id}']"
    )


def pinned_notice(*, name: str, count: int) -> str:
    return _fill(UTUB_PINS_PINNED_NOTICE, name=name, count=count)


def unpinned_notice(*, name: str, count: int) -> str:
    return _fill(UTUB_PINS_UNPINNED_NOTICE, name=name, count=count)


def counter_text(*, count: int) -> str:
    return f"{count} of {MAX_PINNED_UTUBS}"


def _fill(template: str, *, name: str, count: int) -> str:
    return (
        template.replace("{name}", name)
        .replace("{count}", str(count))
        .replace("{max}", str(MAX_PINNED_UTUBS))
    )


def mock_ids(*, app: Flask, numbers: list[int]) -> list[int]:
    return [get_utub_id_by_name(app, f"MockUTub_{number}") for number in numbers]


def pin_mocks_in_db(*, app: Flask, numbers: list[int]) -> None:
    pin_utubs_for_user(app, USER_ID_FOR_TEST, mock_ids(app=app, numbers=numbers))


def pin_from_picker(
    *,
    page: Page,
    text: str,
    option_name: str,
    use_enter: bool,
    tap: bool = False,
    surface: str = HPL.PANEL_SETTINGS_POPOVER,
) -> None:
    """Type ``text`` into the picker, then commit the matching option with Enter or
    by activating its row."""
    input_locator = picker_input(page=page, surface=surface)
    input_locator.fill(text)
    option = pins_body(page=page, surface=surface).locator(
        ".utubPinsOption", has_text=option_name
    )
    expect(option.first).to_be_visible()
    if use_enter:
        input_locator.press("Enter")
    elif tap:
        option.first.tap()
    else:
        option.first.click()


def expect_divider(*, page: Page, visible: bool) -> None:
    divider = page.locator(DECK_PIN_DIVIDER)
    if visible:
        expect(divider).to_be_visible()
    else:
        expect(divider).to_be_hidden()


def expect_pinned_rows(*, page: Page, names: list[str]) -> None:
    expect(page.locator(DECK_PINNED_NAMES)).to_have_text(names)
    expect(page.locator(DECK_PIN_ICONS)).to_have_count(len(names))


def fail_all_pin_writes(*, page: Page) -> None:
    """Answer every pin write (``PATCH /utubs/<id>/pin``) with a 500 until the page
    closes. The preferences route is not intercepted."""

    def fulfill_with_server_error(route: Route) -> None:
        route.fulfill(
            status=500,
            content_type="application/json",
            body='{"status": "Failure", "message": "forced failure"}',
        )

    page.route(UTUB_PIN_ROUTE, fulfill_with_server_error)


def expect_pin_failure_surfaced(
    *, page: Page, surface: str = HPL.PANEL_SETTINGS_POPOVER
) -> None:
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        PANEL_SETTINGS_SAVE_FAILED
    )
    expect(
        page.locator(f"{surface} .panelSettingsStatus[data-state='error']")
    ).to_have_text(PANEL_SETTINGS_REVERTED)


@pytest.mark.parametrize("use_enter", [True, False], ids=["enter", "click"])
def test_pinning_from_the_picker_moves_the_row_to_the_top_with_icon_and_rule(
    page: Page, create_test_utubmembers, provide_app: Flask, use_enter: bool
):
    """
    GIVEN a user with no pins and the default recent-activity sort
    WHEN they type into the Pin a UTub picker and pick MockUTub_3 (Enter or click)
    THEN the row moves to the top with the pin icon, the rule appears, the section
        lists it and the notice is announced
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect_deck_order(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )
    expect(page.locator(DECK_PIN_ICONS)).to_have_count(0)
    expect_divider(page=page, visible=False)

    open_utubs_settings(page=page)
    body = pins_body(page=page)
    expect(body.locator(".utubPinsCounter")).to_have_text(counter_text(count=0))
    expect(body.locator(".utubPinsHint")).to_have_text(UTUB_PINS_EMPTY_HINT)
    expect(picker_input(page=page)).not_to_be_focused()

    pin_from_picker(
        page=page, text="MockUTub_3", option_name="MockUTub_3", use_enter=use_enter
    )

    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        pinned_notice(name="MockUTub_3", count=1)
    )
    expect_deck_order(page=page, names=mock_names(order=[3, 5, 4, 2, 1]))
    expect_pinned_rows(page=page, names=["MockUTub_3"])
    expect_divider(page=page, visible=True)
    expect(body.locator(".utubPinsCounter")).to_have_text(counter_text(count=1))
    expect(body.locator(".utubPinsName")).to_have_text(["MockUTub_3"])
    expect(picker_input(page=page)).to_have_value("")
    expect(picker_input(page=page)).to_be_focused()


def test_unpinning_returns_the_row_to_its_place_and_moves_focus_to_the_next_x(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN three pinned UTubs (MockUTub_5, 1 and 3 in the deck's order)
    WHEN the user unpins the first, then the rest
    THEN the row returns to its sorted place with focus on the next X, and once no
        pins remain the rule is hidden and focus lands on the picker
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    pin_mocks_in_db(app=app, numbers=[5, 1, 3])
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect_deck_order(page=page, names=mock_names(order=[5, 1, 3, 4, 2]))
    expect_divider(page=page, visible=True)
    five, one, three = mock_ids(app=app, numbers=[5, 1, 3])

    open_utubs_settings(page=page)
    remove_button(page=page, utub_id=five).click()

    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        unpinned_notice(name="MockUTub_5", count=2)
    )
    expect_deck_order(page=page, names=mock_names(order=[1, 3, 5, 4, 2]))
    expect_pinned_rows(page=page, names=["MockUTub_1", "MockUTub_3"])
    expect(remove_button(page=page, utub_id=one)).to_be_focused()

    remove_button(page=page, utub_id=one).click()
    expect(remove_button(page=page, utub_id=three)).to_be_focused()
    remove_button(page=page, utub_id=three).click()

    expect(page.locator(DECK_PIN_ICONS)).to_have_count(0)
    expect_deck_order(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )
    expect_divider(page=page, visible=False)
    expect(pins_body(page=page).locator(".utubPinsHint")).to_have_text(
        UTUB_PINS_EMPTY_HINT
    )
    expect(picker_input(page=page)).to_be_focused()


@pytest.mark.parametrize(
    "sort, pinned_first, rest",
    [
        ("name_az", [3, 5], [1, 2, 4]),
        ("newest_created", [5, 3], [4, 2, 1]),
    ],
)
def test_pinned_first_holds_under_each_sort_after_a_sort_change(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
    sort: str,
    pinned_first: list[int],
    rest: list[int],
):
    """
    GIVEN MockUTub_3 and MockUTub_5 pinned under recent activity
    WHEN the user changes the sort
    THEN the pins stay first (in the new sort), then the rule, then the rest in
        the new sort
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    pin_mocks_in_db(app=app, numbers=[3, 5])
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect_deck_order(page=page, names=mock_names(order=[5, 3, 4, 2, 1]))

    open_utubs_settings(page=page)
    pick_sort(page=page, sort=sort)

    expect_deck_order(page=page, names=mock_names(order=[*pinned_first, *rest]))
    expect_pinned_rows(page=page, names=mock_names(order=pinned_first))
    expect_divider(page=page, visible=True)


def test_the_cap_disables_the_picker_and_a_stale_tab_sixth_pin_reseeds(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN four pins in this tab, a fifth written elsewhere after load, and a sixth
        UTub still pinnable in this tab
    WHEN the user pins the sixth
    THEN the server refuses (409): the cap message, the counter, the last-notice
        line and the shell's reverted line show together, the deck reseeds with
        the fifth pin, and the picker is disabled at the cap
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    create_utubs_owned_by(app, USER_ID_FOR_TEST, ["Extra UTub"])
    pin_mocks_in_db(app=app, numbers=[1, 2, 3, 4])
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect(page.locator(DECK_PIN_ICONS)).to_have_count(MAX_PINNED_UTUBS - 1)
    open_utubs_settings(page=page)
    body = pins_body(page=page)
    expect(body.locator(".utubPinsCounter")).to_have_text(
        counter_text(count=MAX_PINNED_UTUBS - 1)
    )
    expect(picker_input(page=page)).to_have_attribute("aria-disabled", "false")

    pin_mocks_in_db(app=app, numbers=[5])
    pin_from_picker(page=page, text="Extra", option_name="Extra UTub", use_enter=True)

    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        UTUB_PINS_CAP_REACHED
    )
    expect(body.locator(".utubPinsCounter")).to_have_text(
        counter_text(count=MAX_PINNED_UTUBS)
    )
    expect(body.locator(".utubPinsNotice")).to_have_text(UTUB_PINS_CAP_REACHED)
    expect(
        page.locator(
            f"{HPL.PANEL_SETTINGS_POPOVER} .panelSettingsStatus[data-state='error']"
        )
    ).to_have_text(PANEL_SETTINGS_REVERTED)
    expect_deck_order(
        page=page,
        names=[*mock_names(order=ORDER_BY_SORT["recent_activity"]), "Extra UTub"],
    )
    expect_pinned_rows(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )
    expect(picker_input(page=page)).to_have_attribute("aria-disabled", "true")
    expect(body.locator(".utubPinsCapNote")).to_have_text(UTUB_PINS_CAP_REACHED)

    # aria-disabled makes Playwright treat the input as not editable, so type
    # through the keyboard like a user would.
    picker_input(page=page).focus()
    expect(picker_input(page=page)).to_be_focused()
    page.keyboard.type("Extra")
    expect(picker_input(page=page)).to_have_value("")
    expect(body.locator(".utubPinsOption")).to_have_count(0)


def test_pinning_the_fifth_utub_through_the_ui_disables_the_picker(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN four pins and a fifth UTub still pinnable
    WHEN the user pins it from the picker
    THEN the pinned notice is announced with the cap message, the counter reads
        5 of 5, and the picker is disabled with the cap note
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    pin_mocks_in_db(app=app, numbers=[1, 2, 3, 4])
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utubs_settings(page=page)

    pin_from_picker(
        page=page, text="MockUTub_5", option_name="MockUTub_5", use_enter=True
    )

    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        pinned_notice(name="MockUTub_5", count=MAX_PINNED_UTUBS)
    )
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        UTUB_PINS_CAP_REACHED
    )
    body = pins_body(page=page)
    expect(body.locator(".utubPinsCounter")).to_have_text(
        counter_text(count=MAX_PINNED_UTUBS)
    )
    expect(picker_input(page=page)).to_have_attribute("aria-disabled", "true")
    expect(body.locator(".utubPinsCapNote")).to_have_text(UTUB_PINS_CAP_REACHED)
    expect(body.locator(NONE_LEFT_HINT)).to_have_count(0)
    expect_pinned_rows(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )
    expect_divider(page=page, visible=False)


def test_a_filter_with_no_matching_utub_shows_the_no_match_status(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN pinnable UTubs
    WHEN the user types text that matches none of them
    THEN "No UTubs match." is shown in the status region and no options list
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utubs_settings(page=page)

    picker_input(page=page).fill("zzz-no-such-utub")

    no_match = pins_body(page=page).locator(".utubPinsNoMatch")
    expect(no_match).to_have_text(UTUB_PINS_NO_MATCH)
    expect(no_match).to_have_attribute("role", "status")
    expect(pins_body(page=page).locator(".utubPinsOption")).to_have_count(0)


def test_a_pin_on_a_utub_trashed_elsewhere_reports_it_gone_and_drops_the_row(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub trashed elsewhere after this tab loaded
    WHEN the user pins it from the picker
    THEN the "no longer available" message shows with the shell's reverted line,
        and its row is gone from the deck
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    created = create_utubs_owned_by(app, USER_ID_FOR_TEST, ["Vanishing UTub"])
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect(page.locator(DECK_NAMES).filter(has_text="Vanishing UTub")).to_have_count(1)
    open_utubs_settings(page=page)

    trash_utub(app, created["Vanishing UTub"], USER_ID_FOR_TEST)
    pin_from_picker(
        page=page, text="Vanishing", option_name="Vanishing UTub", use_enter=True
    )

    body = pins_body(page=page)
    expect(body.locator(".utubPinsNotice")).to_have_text(UTUB_PINS_UTUB_GONE)
    expect(
        page.locator(
            f"{HPL.PANEL_SETTINGS_POPOVER} .panelSettingsStatus[data-state='error']"
        )
    ).to_have_text(PANEL_SETTINGS_REVERTED)
    expect(page.locator(DECK_NAMES).filter(has_text="Vanishing UTub")).to_have_count(0)
    expect(body.locator(".utubPinsCounter")).to_have_text(counter_text(count=0))


def test_every_utub_pinned_below_the_cap_shows_the_none_left_hint(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a user whose three live UTubs are all pinned (two others are trashed)
    WHEN they open the UTubs gear and then type into the picker
    THEN "No UTubs left to pin." is shown without focusing the input and stays
        after typing, and "No UTubs match." never appears
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    for trashed in mock_ids(app=app, numbers=[4, 2]):
        trash_utub(app, trashed, USER_ID_FOR_TEST)
    pin_mocks_in_db(app=app, numbers=[5, 1, 3])
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect(page.locator(DECK_PIN_ICONS)).to_have_count(3)

    open_utubs_settings(page=page)
    body = pins_body(page=page)
    expect(body.locator(".utubPinsCounter")).to_have_text(counter_text(count=3))
    expect(body.locator(NONE_LEFT_HINT)).to_have_text(UTUB_PINS_NONE_LEFT_HINT)
    expect(picker_input(page=page)).not_to_be_focused()
    expect(picker_input(page=page)).to_have_attribute("aria-disabled", "false")

    picker_input(page=page).fill("MockUTub")
    expect(body.locator(NONE_LEFT_HINT)).to_have_text(UTUB_PINS_NONE_LEFT_HINT)
    expect(body.locator(".utubPinsNoMatch")).to_have_text("")
    expect(body.locator(".utubPinsOption")).to_have_count(0)


def test_a_failed_pin_save_leaves_the_deck_unchanged(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the pin endpoint answers 500
    WHEN the user pins MockUTub_3
    THEN the failure is announced with the reverted line, the deck, icons and rule
        are unchanged, and a reload shows no pins
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utubs_settings(page=page)
    fail_all_pin_writes(page=page)

    pin_from_picker(
        page=page, text="MockUTub_3", option_name="MockUTub_3", use_enter=True
    )

    expect_pin_failure_surfaced(page=page)
    expect_deck_order(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )
    expect(page.locator(DECK_PIN_ICONS)).to_have_count(0)
    expect_divider(page=page, visible=False)
    expect(pins_body(page=page).locator(".utubPinsCounter")).to_have_text(
        counter_text(count=0)
    )

    page.reload()
    expect_deck_order(
        page=page, names=mock_names(order=ORDER_BY_SORT["recent_activity"])
    )
    expect(page.locator(DECK_PIN_ICONS)).to_have_count(0)


def test_a_failed_unpin_keeps_the_pin_and_returns_focus_to_its_x(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN MockUTub_3 pinned and the pin endpoint answering 500
    WHEN the user unpins it
    THEN the failure is announced, the pin stays in the deck and the list, and
        focus is back on its X
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    pin_mocks_in_db(app=app, numbers=[3])
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    three = mock_ids(app=app, numbers=[3])[0]
    open_utubs_settings(page=page)
    fail_all_pin_writes(page=page)

    remove_button(page=page, utub_id=three).click()

    expect_pin_failure_surfaced(page=page)
    expect_pinned_rows(page=page, names=["MockUTub_3"])
    expect(remove_button(page=page, utub_id=three)).to_be_focused()


def test_the_name_filter_hides_the_rule_when_it_hides_a_whole_group(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN MockUTub_3 pinned
    WHEN the name filter leaves only the pinned row, only unpinned rows, then both
    THEN the rule shows only while both groups have a visible row
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    pin_mocks_in_db(app=app, numbers=[3])
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect_divider(page=page, visible=True)

    search = open_utub_name_filter(page=page)
    search.fill("MockUTub_3")
    expect(page.locator(DECK_NAMES).filter(visible=True)).to_have_text(["MockUTub_3"])
    expect_divider(page=page, visible=False)

    search.fill("MockUTub_1")
    expect(page.locator(DECK_NAMES).filter(visible=True)).to_have_text(["MockUTub_1"])
    expect_divider(page=page, visible=False)

    search.fill("MockUTub_")
    expect(page.locator(DECK_NAMES).filter(visible=True)).to_have_count(5)
    expect_divider(page=page, visible=True)


def test_a_reload_keeps_the_pins(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a pin made through the gear
    WHEN the page reloads
    THEN the deck order, icon, rule and the section's list still show the pin
    """
    app = provide_app
    seed_sortable_mock_utubs(app)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    open_utubs_settings(page=page)
    pin_from_picker(
        page=page, text="MockUTub_1", option_name="MockUTub_1", use_enter=True
    )
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        pinned_notice(name="MockUTub_1", count=1)
    )

    page.reload()

    expect_deck_order(page=page, names=mock_names(order=[1, 5, 4, 2, 3]))
    expect_pinned_rows(page=page, names=["MockUTub_1"])
    expect_divider(page=page, visible=True)
    open_utubs_settings(page=page)
    expect(pins_body(page=page).locator(".utubPinsName")).to_have_text(["MockUTub_1"])


def test_trashing_and_restoring_a_pinned_utub_keeps_the_pin(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a UTub the user created, pinned and then trashed
    WHEN the user restores it from the Trash UTubs tab
    THEN its row is back in the deck with the pin icon, and a reload still shows
        it pinned at the top
    """
    app = provide_app
    name = "Pinned Trash UTub"
    seed_sortable_mock_utubs(app)
    utub_id = create_utubs_owned_by(app, USER_ID_FOR_TEST, [name])[name]
    pin_utubs_for_user(app, USER_ID_FOR_TEST, [utub_id])
    trash_utub(app, utub_id, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    expect(page.locator(DECK_NAMES).filter(has_text=name)).to_have_count(0)
    expect(page.locator(DECK_PIN_ICONS)).to_have_count(0)

    open_trash(page=page)
    open_utubs_tab(page=page)
    page.locator(
        f"{TPL.ROWS_UTUBS}[data-utub-id='{utub_id}'] {TPL.BUTTON_RESTORE}"
    ).click()

    expect(page.locator(DECK_NAMES).filter(has_text=name)).to_have_count(1)
    expect_pinned_rows(page=page, names=[name])

    page.reload()
    expect_deck_order(
        page=page,
        names=[name, *mock_names(order=ORDER_BY_SORT["recent_activity"])],
    )
    expect_pinned_rows(page=page, names=[name])
    expect_divider(page=page, visible=True)
