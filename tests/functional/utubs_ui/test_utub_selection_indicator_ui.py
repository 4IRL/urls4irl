import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.home_ui.playwright_utils import toggle_lhs_panels
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import (
    click_on_navbar,
    collapse_deck_by_header_click,
    expand_deck_by_header_click,
    get_selected_utub_id,
    login_user_to_home_page,
    select_utub_by_id,
    wait_then_click_element,
    wait_until_css_property,
)
from tests.functional.trash_ui.playwright_utils import open_trash
from tests.functional.utubs_ui.playwright_utils import (
    create_utub,
    delete_utub_as_creator,
    get_selection_bar_and_active_row_boxes,
    get_selection_bar_animate_call_count,
    install_selection_bar_animate_spy,
    open_utub_name_filter,
    wait_for_selection_bar_on_utub,
    wait_for_selection_shimmer_animation_count,
)

pytestmark = pytest.mark.utubs_ui

USER_ID_FOR_TEST = 1
POSITION_TOLERANCE_PX = 1
_UTUB_DECK_CONTENT_ID = "UTubDeckContent"
_NEW_UTUB_NAME = "Brand new indicator utub"
_IDLE_CLASS_RE = re.compile(r"(^|\s)isIdle(\s|$)")


def _row_selector(utub_id: int) -> str:
    return f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']"


def test_bar_matches_active_row_after_select(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user on the home page with multiple UTubs
    WHEN the user selects a UTub
    THEN the selection bar's top and height match the active row's within 1px
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=utub.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)

    bar_box, row_box = get_selection_bar_and_active_row_boxes(page=page)
    assert abs(bar_box["y"] - row_box["y"]) <= POSITION_TOLERANCE_PX
    assert abs(bar_box["height"] - row_box["height"]) <= POSITION_TOLERANCE_PX


def test_bar_and_aria_current_move_to_second_utub(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user with one UTub selected
    WHEN the user selects a second UTub
    THEN the bar moves onto it and aria-current moves with it
    """
    app = provide_app
    first = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    second = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=first.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=first.id)

    select_utub_by_id(page=page, utub_id=second.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=second.id)

    expect(page.locator(_row_selector(second.id))).to_have_attribute(
        "aria-current", "true"
    )
    expect(page.locator(f"{_row_selector(first.id)}[aria-current]")).to_have_count(0)
    expect(page.locator(f"{HPL.LIST_UTUB} [aria-current]")).to_have_count(1)


def test_selecting_second_utub_stretches_bar_once(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user with one UTub selected and the animate spy installed
    WHEN the user selects a second, different UTub
    THEN the bar is animated exactly once and settles on the new row
    """
    app = provide_app
    first = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    second = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=first.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=first.id)
    install_selection_bar_animate_spy(page=page)
    assert get_selection_bar_animate_call_count(page=page) == 0

    select_utub_by_id(page=page, utub_id=second.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=second.id)

    assert get_selection_bar_animate_call_count(page=page) == 1
    bar_box, row_box = get_selection_bar_and_active_row_boxes(page=page)
    assert abs(bar_box["y"] - row_box["y"]) <= POSITION_TOLERANCE_PX
    assert abs(bar_box["height"] - row_box["height"]) <= POSITION_TOLERANCE_PX


def test_reduced_motion_snaps_bar_without_animating(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user who prefers reduced motion with one UTub selected
    WHEN the user selects a second UTub
    THEN the bar is never animated and already matches the new row
    """
    app = provide_app
    first = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    second = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST)
    page.emulate_media(reduced_motion="reduce")
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=first.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=first.id)
    install_selection_bar_animate_spy(page=page)

    select_utub_by_id(page=page, utub_id=second.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=second.id)

    assert get_selection_bar_animate_call_count(page=page) == 0
    bar_box, row_box = get_selection_bar_and_active_row_boxes(page=page)
    assert abs(bar_box["y"] - row_box["y"]) <= POSITION_TOLERANCE_PX
    assert abs(bar_box["height"] - row_box["height"]) <= POSITION_TOLERANCE_PX


def test_opening_trash_hides_indicator(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a selected UTub with the indicator visible
    WHEN the user opens Trash (which clears the selection)
    THEN the indicator hides and no row keeps aria-current or the hidden node
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=utub.id)
    wait_until_css_property(
        page=page,
        css_selector=HPL.UTUB_SELECTION_INDICATOR,
        css_property="opacity",
        expected_value="1",
    )

    open_trash(page=page)

    wait_until_css_property(
        page=page,
        css_selector=HPL.UTUB_SELECTION_INDICATOR,
        css_property="opacity",
        expected_value="0",
    )
    expect(page.locator(f"{HPL.LIST_UTUB} [aria-current]")).to_have_count(0)
    expect(page.locator(f"{HPL.LIST_UTUB} {HPL.UTUB_SELECTED_ANNOUNCE}")).to_have_count(
        0
    )


def test_indicator_is_click_through_and_aria_hidden(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a selected UTub with the indicator visible
    THEN the indicator ignores pointer events, is aria-hidden, and the element at
    the bar's center is the active row (or a descendant), never the indicator
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=utub.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)

    wait_until_css_property(
        page=page,
        css_selector=HPL.UTUB_SELECTION_INDICATOR,
        css_property="pointer-events",
        expected_value="none",
    )
    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).to_have_attribute(
        "aria-hidden", "true"
    )

    bar_box, _ = get_selection_bar_and_active_row_boxes(page=page)
    hit_is_row_or_descendant = page.evaluate(
        """({ x, y, rowSelector, indicatorSelector }) => {
            const hit = document.elementFromPoint(x, y);
            if (!hit) return false;
            const row = document.querySelector(rowSelector);
            const indicator = document.querySelector(indicatorSelector);
            return row.contains(hit) && !indicator.contains(hit);
        }""",
        {
            "x": bar_box["x"] + bar_box["width"] / 2,
            "y": bar_box["y"] + bar_box["height"] / 2,
            "rowSelector": HPL.SELECTOR_SELECTED_UTUB,
            "indicatorSelector": HPL.UTUB_SELECTION_INDICATOR,
        },
    )
    assert hit_is_row_or_descendant


def test_active_row_announces_selection_without_changing_layout(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a selected UTub
    THEN only the active row has aria-current and exactly one visually-hidden
    "selected" node, the name text is unchanged and the row geometry equals a
    non-active row's
    """
    app = provide_app
    selected = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=selected.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=selected.id)

    active_row = page.locator(HPL.SELECTOR_SELECTED_UTUB)
    announce = page.locator(f"{HPL.LIST_UTUB} {HPL.UTUB_SELECTED_ANNOUNCE}")
    expect(active_row).to_have_attribute("aria-current", "true")
    expect(announce).to_have_count(1)
    expect(active_row.locator(HPL.UTUB_SELECTED_ANNOUNCE)).to_have_count(1)
    expect(announce).to_have_text(UTS.UTUB_SELECTED_ANNOUNCEMENT)
    expect(announce).to_have_css("position", "absolute")
    expect(page.locator(f"{HPL.LIST_UTUB} [aria-current]")).to_have_count(1)

    expect(active_row.locator(HPL.SELECTORS_UTUB_NAME)).to_have_text(selected.name)

    inactive_row = page.locator(f"{HPL.SELECTORS_UTUB}:not(.active)").first
    expect(inactive_row).to_be_visible()
    active_box = active_row.bounding_box()
    inactive_box = inactive_row.bounding_box()
    assert active_box is not None and inactive_box is not None
    assert active_box["width"] == pytest.approx(
        inactive_box["width"], abs=POSITION_TOLERANCE_PX
    )
    assert active_box["height"] == pytest.approx(
        inactive_box["height"], abs=POSITION_TOLERANCE_PX
    )


def test_rendered_selected_label_matches_backend_constant(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN the home page
    THEN the indicator's data-selected-label equals the backend constant
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)

    assert UTS.UTUB_SELECTED_ANNOUNCEMENT
    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).to_have_attribute(
        "data-selected-label", UTS.UTUB_SELECTED_ANNOUNCEMENT
    )


def _select_first_utub_and_settle(*, app: Flask, page: Page) -> None:
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=utub.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)


def test_shimmer_runs_once_selection_settles(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a selected UTub whose selection has settled
    THEN the indicator is idle and the shimmer has a running CSS animation
    """
    _select_first_utub_and_settle(app=provide_app, page=page)

    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).to_have_class(_IDLE_CLASS_RE)
    wait_for_selection_shimmer_animation_count(page=page, running=True)


def test_reduced_motion_has_no_shimmer_animation(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user who prefers reduced motion with a settled selection
    THEN the indicator may be idle but the shimmer has no running animation
    """
    page.emulate_media(reduced_motion="reduce")
    _select_first_utub_and_settle(app=provide_app, page=page)

    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).to_have_class(_IDLE_CLASS_RE)
    wait_for_selection_shimmer_animation_count(page=page, running=False)


def test_opening_trash_removes_idle(page: Page, create_test_tags, provide_app: Flask):
    """
    GIVEN an idle shimmer on a selected UTub
    WHEN the user opens Trash (which clears the selection)
    THEN isIdle is removed
    """
    _select_first_utub_and_settle(app=provide_app, page=page)
    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).to_have_class(_IDLE_CLASS_RE)

    open_trash(page=page)

    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).not_to_have_class(_IDLE_CLASS_RE)


def test_collapsing_utub_deck_pauses_shimmer_until_expand(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN an idle shimmer on a selected UTub
    WHEN the UTub deck is collapsed, then expanded
    THEN isIdle is removed on collapse and returns after the expand settles
    """
    _select_first_utub_and_settle(app=provide_app, page=page)
    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).to_have_class(_IDLE_CLASS_RE)

    collapse_deck_by_header_click(
        page=page,
        header_selector=HPL.HEADER_AND_CARET_UTUB_DECK,
        deck_selector=HPL.UTUB_DECK,
        content_id=_UTUB_DECK_CONTENT_ID,
    )
    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).not_to_have_class(_IDLE_CLASS_RE)

    expand_deck_by_header_click(
        page=page,
        header_selector=HPL.HEADER_AND_CARET_UTUB_DECK,
        deck_selector=HPL.UTUB_DECK,
        content_id=_UTUB_DECK_CONTENT_ID,
    )
    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).to_have_class(_IDLE_CLASS_RE)
    wait_for_selection_shimmer_animation_count(page=page, running=True)


def test_collapsing_left_panel_pauses_shimmer_until_expand(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN an idle shimmer on a selected UTub at desktop width
    WHEN the left panel is collapsed with the seam toggle, then expanded
    THEN isIdle is removed on collapse and returns after the expand settles
    """
    _select_first_utub_and_settle(app=provide_app, page=page)
    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).to_have_class(_IDLE_CLASS_RE)

    toggle_lhs_panels(page=page)
    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).not_to_have_class(_IDLE_CLASS_RE)

    toggle_lhs_panels(page=page)
    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).to_have_class(_IDLE_CLASS_RE)


def _wait_for_indicator_hidden(*, page: Page) -> None:
    wait_until_css_property(
        page=page,
        css_selector=HPL.UTUB_SELECTION_INDICATOR,
        css_property="opacity",
        expected_value="0",
    )


def _wait_for_bar_height_equals_row_height(*, page: Page, expected_px: float) -> None:
    """Poll until the active row is expected_px tall and the bar matches it."""
    page.wait_for_function(
        """({ rowSelector, barSelector, expected }) => {
            const row = document.querySelector(rowSelector);
            const bar = document.querySelector(barSelector);
            if (!row || !bar) return false;
            const rowHeight = row.getBoundingClientRect().height;
            const barHeight = bar.getBoundingClientRect().height;
            return Math.abs(rowHeight - expected) <= 1 &&
                Math.abs(barHeight - rowHeight) <= 1;
        }""",
        arg={
            "rowSelector": HPL.SELECTOR_SELECTED_UTUB,
            "barSelector": HPL.UTUB_SELECTION_BAR,
            "expected": expected_px,
        },
    )


def test_filtering_out_active_utub_hides_indicator_and_clearing_restores_it(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a selected UTub with the indicator visible
    WHEN the UTub list is filtered so the active UTub is hidden, then cleared
    THEN the indicator hides, and comes back aligned with the active row
        without a stretch
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=utub.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)
    install_selection_bar_animate_spy(page=page)

    search_input = open_utub_name_filter(page=page)
    search_input.fill("zzzz-no-such-utub")
    expect(page.locator(_row_selector(utub.id))).to_be_hidden()
    _wait_for_indicator_hidden(page=page)

    search_input.fill("")
    expect(page.locator(_row_selector(utub.id))).to_be_visible()
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)
    wait_until_css_property(
        page=page,
        css_selector=HPL.UTUB_SELECTION_INDICATOR,
        css_property="opacity",
        expected_value="1",
    )
    assert get_selection_bar_animate_call_count(page=page) == 0


def test_creating_utub_places_bar_on_new_row_without_stretch(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a selected UTub and the animate spy installed
    WHEN the user creates a new UTub (which prepends and selects its row)
    THEN the bar snaps onto the new row; no stretch animate call is made
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=utub.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)
    install_selection_bar_animate_spy(page=page)

    create_utub(
        page=page,
        utub_name=_NEW_UTUB_NAME,
        utub_description=_NEW_UTUB_NAME,
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE)
    expect(
        page.locator(f"{HPL.SELECTOR_SELECTED_UTUB} {HPL.SELECTORS_UTUB_NAME}")
    ).to_have_text(_NEW_UTUB_NAME)

    new_utub_id = get_selected_utub_id(page=page)
    assert new_utub_id != utub.id
    wait_for_selection_bar_on_utub(page=page, utub_id=new_utub_id)
    assert get_selection_bar_animate_call_count(page=page) == 0
    expect(page.locator(f"{HPL.LIST_UTUB} [aria-current]")).to_have_count(1)


def test_collapse_then_expand_deck_leaves_bar_aligned(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a selected UTub with the bar aligned
    WHEN the UTub deck is collapsed then expanded
    THEN the bar is aligned with the active row once the transition settles
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=utub.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)

    collapse_deck_by_header_click(
        page=page,
        header_selector=HPL.HEADER_AND_CARET_UTUB_DECK,
        deck_selector=HPL.UTUB_DECK,
        content_id=_UTUB_DECK_CONTENT_ID,
    )
    expand_deck_by_header_click(
        page=page,
        header_selector=HPL.HEADER_AND_CARET_UTUB_DECK,
        deck_selector=HPL.UTUB_DECK,
        content_id=_UTUB_DECK_CONTENT_ID,
    )

    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)
    expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).to_have_class(_IDLE_CLASS_RE)


def test_deleting_active_utub_hides_indicator(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a selected UTub owned by the user
    WHEN the user deletes it
    THEN once the fade-out and removal finish, the indicator is hidden and no
        row keeps aria-current
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=utub.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)

    delete_utub_as_creator(page=page, utub_to_delete=utub)

    _wait_for_indicator_hidden(page=page)
    expect(page.locator(f"{HPL.LIST_UTUB} [aria-current]")).to_have_count(0)


@pytest.mark.parametrize("left_panel_collapsed", [False, True])
def test_crossing_mobile_breakpoint_remeasures_bar_and_idle(
    page: Page, create_test_tags, provide_app: Flask, left_panel_collapsed: bool
):
    """
    GIVEN a desktop user with a selected UTub (left panel expanded or collapsed)
    WHEN the viewport shrinks below 992px, the user returns to the UTub list
        through the mobile nav, and the viewport widens again
    THEN the indicator is hidden while the deck is display:none, the bar matches
        the 2.75rem mobile row, then the 2.2rem desktop row, and isIdle follows
        the left-panel state once back on desktop
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_to_home_page(app=app, page=page, user_id=USER_ID_FOR_TEST)
    select_utub_by_id(page=page, utub_id=utub.id)
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)
    desktop_viewport = page.viewport_size
    assert desktop_viewport is not None
    if left_panel_collapsed:
        toggle_lhs_panels(page=page)
        expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).not_to_have_class(
            _IDLE_CLASS_RE
        )

    page.set_viewport_size({"width": 800, "height": desktop_viewport["height"]})
    _wait_for_indicator_hidden(page=page)

    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_UTUB_DECK)
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)
    _wait_for_bar_height_equals_row_height(page=page, expected_px=44)

    page.set_viewport_size(desktop_viewport)
    wait_for_selection_bar_on_utub(page=page, utub_id=utub.id)
    _wait_for_bar_height_equals_row_height(page=page, expected_px=35.2)

    if left_panel_collapsed:
        expect(page.locator(HPL.MAIN_PANEL)).to_have_class(
            re.compile(r"(^|\s)lhs-collapsed(\s|$)")
        )
        expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).not_to_have_class(
            _IDLE_CLASS_RE
        )
    else:
        expect(page.locator(HPL.UTUB_SELECTION_INDICATOR)).to_have_class(_IDLE_CLASS_RE)


def test_forced_colors_keeps_bar_visible_and_hides_shimmer(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN forced-colors mode with a selected UTub
    THEN the indicator is visible, the bar is painted with the Highlight system
    color and the shimmer clip is display:none
    """
    page.emulate_media(forced_colors="active")
    _select_first_utub_and_settle(app=provide_app, page=page)

    wait_until_css_property(
        page=page,
        css_selector=HPL.UTUB_SELECTION_INDICATOR,
        css_property="opacity",
        expected_value="1",
    )
    wait_until_css_property(
        page=page,
        css_selector=HPL.UTUB_SELECTION_SHIMMER_CLIP,
        css_property="display",
        expected_value="none",
    )
    page.wait_for_function(
        """(barSelector) => {
            const bar = document.querySelector(barSelector);
            if (!bar) return false;
            const barStyle = window.getComputedStyle(bar);
            if (barStyle.display === "none") return false;
            const probe = document.createElement("div");
            probe.style.background = "Highlight";
            probe.style.forcedColorAdjust = "none";
            document.body.appendChild(probe);
            const highlight = window.getComputedStyle(probe).backgroundColor;
            probe.remove();
            return barStyle.backgroundColor === highlight;
        }""",
        arg=HPL.UTUB_SELECTION_BAR,
    )
