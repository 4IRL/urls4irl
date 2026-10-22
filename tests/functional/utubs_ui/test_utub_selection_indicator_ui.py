import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    select_utub_by_id,
    wait_until_css_property,
)
from tests.functional.trash_ui.playwright_utils import open_trash
from tests.functional.utubs_ui.playwright_utils import (
    get_selection_bar_and_active_row_boxes,
    get_selection_bar_animate_call_count,
    install_selection_bar_animate_spy,
    wait_for_selection_bar_on_utub,
)

pytestmark = pytest.mark.utubs_ui

USER_ID_FOR_TEST = 1
POSITION_TOLERANCE_PX = 1


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
