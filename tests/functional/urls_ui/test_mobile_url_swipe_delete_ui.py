import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.utils.strings.url_strs import URL_MOVED_TO_TRASH_ONE
from tests.functional.db_utils import (
    get_url_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as ML
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    get_all_url_ids_in_selected_utub,
    get_num_url_rows,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_until_css_property,
)
from tests.functional.urls_ui.db_utils import (
    FORMER_MEMBER_BADGE_PATTERN,
    seed_orphaned_url_scenario,
)
from tests.functional.urls_ui.playwright_utils import (
    get_url_row_selector,
    swipe_url_card_below_threshold,
    swipe_url_card_delete,
    wait_until_url_card_swipe_reset,
)

pytestmark = [pytest.mark.urls_ui, pytest.mark.mobile_ui]

USER_ID_FOR_TEST = 1
SWIPE_COMMITTED_CLASS = "swipe-committed"
SWIPE_DRAGGING_CLASS = "swipe-dragging"
SWIPE_FOCUS_RETURN_CLASS = "swipe-focus-return"
MIN_TOUCH_TARGET_PX = 44
# Reads the active theme's --borderColor (frontend/styles/tokens.css) and returns
# it as a browser-normalized rgb() string. The value is theme-dependent (dark
# #343c3d vs light #d5dbdb), and the default "system" theme resolves to light or
# dark from the browser's prefers-color-scheme — so a hardcoded rgb() would be
# wrong under the other theme. Resolving the token at runtime keeps the neutral-
# border assertion below theme-agnostic while still failing loudly if the focus-
# ring green ever leaks through (green never equals --borderColor in either theme).
_RESOLVE_NEUTRAL_ROW_BORDER_COLOR_JS = """() => {
    const probe = document.createElement('span');
    probe.style.color = getComputedStyle(document.documentElement)
        .getPropertyValue('--borderColor');
    document.body.appendChild(probe);
    const normalized = getComputedStyle(probe).color;
    probe.remove();
    return normalized;
}"""


def test_url_swipe_commit_moves_to_trash_and_shows_undo_toast(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a deletable URL
    WHEN they swipe the URL row left past the commit threshold
    THEN the URL is moved to Trash at once with no confirm modal: the row is
        removed and the undo toast reports URL_MOVED_TO_TRASH_ONE
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    assert_visible_css_selector(page=page, css_selector=row_selector)
    init_num_url_rows = get_num_url_rows(page=page)

    swipe_url_card_delete(page=page, url_row_selector=row_selector)

    assert_visible_css_selector(page=page, css_selector=HPL.URL_OUTCOME_BANNER)
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_MOVED_TO_TRASH_ONE
    )
    expect(page.locator(HPL.HOME_MODAL)).not_to_be_visible()
    wait_for_element_to_be_removed(page=page, locator=page.locator(row_selector))
    assert init_num_url_rows - 1 == get_num_url_rows(page=page)


def test_url_swipe_undo_restores_row(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a URL moved to Trash by a swipe-delete
    WHEN the user taps Undo on the toast
    THEN the row is restored to the deck
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    init_num_url_rows = get_num_url_rows(page=page)

    swipe_url_card_delete(page=page, url_row_selector=row_selector)
    wait_for_element_to_be_removed(page=page, locator=page.locator(row_selector))

    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)

    expect(page.locator(row_selector)).to_have_count(1)
    assert init_num_url_rows == get_num_url_rows(page=page)


def test_url_swipe_delete_focus_return_has_no_selected_ring(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a deck with 3+ URLs
    WHEN the user swipe-deletes the middle row
    THEN focus moves to the next row, which carries swipe-focus-return and a
        neutral border-bottom-color rather than the focus-ring green
        (regression coverage for a CSS-specificity bug where the suppression
        rule lost the cascade to the pre-existing focus-ring rule despite the
        suppression class being correctly applied)
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 3, "Test premise violated: need 3+ URLs in the UTub"
    middle_selector = get_url_row_selector(utub_url_id=url_ids[1])
    next_selector = get_url_row_selector(utub_url_id=url_ids[2])

    swipe_url_card_delete(page=page, url_row_selector=middle_selector)
    wait_for_element_to_be_removed(page=page, locator=page.locator(middle_selector))

    next_row = page.locator(next_selector)
    expect(next_row).to_be_focused()
    expect(next_row).to_have_class(re.compile(rf"\b{SWIPE_FOCUS_RETURN_CLASS}\b"))

    neutral_row_border_color = page.evaluate(_RESOLVE_NEUTRAL_ROW_BORDER_COLOR_JS)
    wait_until_css_property(
        page=page,
        css_selector=next_selector,
        css_property="border-bottom-color",
        expected_value=neutral_row_border_color,
    )


def test_url_swipe_delete_twice_then_blur_leaves_no_stuck_goto_icon(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two rows that were each swipe-deleted in turn
    WHEN focus subsequently leaves the neighbour row that received it (e.g. the
        user taps elsewhere)
    THEN no remaining row's .goToUrlIcon is left permanently visible
        (regression coverage for a leaked `visible-on-focus` class: the
        pre-existing keyboard-focus handler in cards.ts only clears that class
        when the icon itself blurs — a check designed for real Tab navigation
        that never matches when the swipe module's focus-return blurs the row
        directly, so the class leaked forever once focus moved on)
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 3, "Test premise violated: need 3+ URLs in the UTub"

    for url_id in url_ids[:2]:
        row_selector = get_url_row_selector(utub_url_id=url_id)
        swipe_url_card_delete(page=page, url_row_selector=row_selector)
        wait_for_element_to_be_removed(page=page, locator=page.locator(row_selector))
        wait_until_url_card_swipe_reset(page=page)

    # The second delete moved focus to its neighbour row (the premise of the
    # blur path below), then a tap in the panel's corner (clear of any row)
    # blurs it, the same way a real user would move on after deleting.
    remaining_ids = get_all_url_ids_in_selected_utub(page=page)
    neighbour_row = page.locator(get_url_row_selector(utub_url_id=remaining_ids[0]))
    expect(neighbour_row).to_be_focused()
    page.locator(HPL.MAIN_PANEL).click(position={"x": 1, "y": 1})
    expect(neighbour_row).not_to_be_focused()

    for url_id in remaining_ids:
        icon_selector = (
            f"{get_url_row_selector(utub_url_id=url_id)} {HPL.GO_TO_URL_ICON}"
        )
        assert_not_visible_css_selector(page=page, css_selector=icon_selector)
        icon = page.locator(icon_selector).first
        assert "visible-on-focus" not in (icon.get_attribute("class") or "")


def test_url_swipe_toast_buttons_meet_touch_target(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a swipe-delete on a coarse-pointer viewport
    WHEN the undo toast appears
    THEN its Undo and dismiss controls are at least 44px square
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    swipe_url_card_delete(page=page, url_row_selector=row_selector)
    assert_visible_css_selector(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)
    # Measure only once the toast has finished any enter transition.
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO
    )

    for control_selector in (
        HPL.URL_OUTCOME_BANNER_UNDO,
        HPL.URL_OUTCOME_BANNER_DISMISS,
    ):
        bounding_box = page.locator(control_selector).first.bounding_box()
        assert bounding_box is not None
        assert bounding_box["width"] >= MIN_TOUCH_TARGET_PX, control_selector
        assert bounding_box["height"] >= MIN_TOUCH_TARGET_PX, control_selector


def test_url_swipe_below_threshold_snaps_back_no_op(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a deletable URL
    WHEN they swipe the row left by a small amount well below the ~35% commit
        threshold (sub-threshold drag)
    THEN the row snaps back to its resting position and nothing is deleted (no
        toast), proving the real browser only commits once the threshold is
        crossed
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    init_num_url_rows = get_num_url_rows(page=page)

    swipe_url_card_below_threshold(page=page, url_row_selector=row_selector)
    wait_until_url_card_swipe_reset(page=page)

    assert_not_visible_css_selector(page=page, css_selector=ML.ELEMENT_MODAL)
    assert_not_visible_css_selector(page=page, css_selector=HPL.URL_OUTCOME_BANNER)
    url_row = page.locator(row_selector).first
    row_class = url_row.get_attribute("class") or ""
    assert SWIPE_COMMITTED_CLASS not in row_class
    assert init_num_url_rows == get_num_url_rows(page=page)


def test_url_tap_to_select_delete_button_still_works(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a deletable URL
    WHEN they tap the row to select it, then tap the existing .urlBtnDelete
    THEN the URL is deleted at once with the undo toast and no confirm modal
        (the tap-to-select delete flow, now confirmation-free)
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    wait_then_click_element(page=page, css_selector=row_selector)

    # The selected-row padding/transform transition must settle before the
    # delete button's post-select position is stable, otherwise the click
    # lands on a still-animating sibling (e.g. .urlTags) instead of the
    # button — mirrors click_delete_on_selected_url.
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    delete_btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}"
    wait_then_click_element(page=page, css_selector=delete_btn_selector)

    assert_visible_css_selector(page=page, css_selector=HPL.URL_OUTCOME_BANNER)
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_MOVED_TO_TRASH_ONE
    )
    expect(page.locator(HPL.HOME_MODAL)).not_to_be_visible()
    expect(page.locator(row_selector)).to_have_count(0)


def test_url_swipe_inert_for_non_deletable_row(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a URL they cannot delete
        (added by a different member, in a UTub they did not create)
    WHEN they attempt the same left-swipe gesture used to delete a row
    THEN the row is inert — no swipe reveal panel exists, no swipe class is
        applied, and nothing is deleted
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    assert utub.utub_creator != USER_ID_FOR_TEST, (
        "Test premise violated: seeded UTub is created by the test user"
    )
    assert utub_url.user_id != USER_ID_FOR_TEST, (
        "Test premise violated: seeded URL was added by the test user"
    )

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    assert_visible_css_selector(page=page, css_selector=row_selector)
    url_row = page.locator(row_selector).first
    assert url_row.locator(".urlRowSwipeReveal").count() == 0

    swipe_url_card_delete(page=page, url_row_selector=row_selector)

    assert_not_visible_css_selector(page=page, css_selector=ML.ELEMENT_MODAL)
    assert_not_visible_css_selector(page=page, css_selector=HPL.URL_OUTCOME_BANNER)
    url_row = page.locator(row_selector).first
    row_class = url_row.get_attribute("class") or ""
    assert SWIPE_COMMITTED_CLASS not in row_class
    assert SWIPE_DRAGGING_CLASS not in row_class


def test_url_swipe_delete_works_for_orphaned_url(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a plain member on mobile and a URL whose adder was removed from the UTub
    WHEN they left-swipe that row past the commit threshold
    THEN the row has a swipe reveal panel and is moved to Trash with the undo toast
    """
    page = page_mobile_portrait
    app = provide_app
    scenario = seed_orphaned_url_scenario(app=app, user_id=USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=scenario.utub_id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=scenario.orphaned_utub_url_id)
    assert_visible_css_selector(page=page, css_selector=row_selector)
    expect(page.locator(row_selector).locator(HPL.URL_ROW_SWIPE_REVEAL)).to_have_count(
        1
    )
    control_selector = get_url_row_selector(utub_url_id=scenario.control_utub_url_id)
    assert_visible_css_selector(page=page, css_selector=control_selector)
    expect(
        page.locator(control_selector).locator(HPL.URL_ROW_SWIPE_REVEAL)
    ).to_have_count(0)

    swipe_url_card_delete(page=page, url_row_selector=row_selector)

    assert_visible_css_selector(page=page, css_selector=HPL.URL_OUTCOME_BANNER)
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_MOVED_TO_TRASH_ONE
    )
    wait_for_element_to_be_removed(page=page, locator=page.locator(row_selector))


def test_expanded_orphaned_url_shows_stacked_former_member_badge_below_buttons(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a plain member on mobile and a URL whose adder was removed from the UTub
    WHEN they tap the row to expand it
    THEN the stacked badge reads "Added by a former member · <date>", is visible,
        left-aligned with the row content and sits below the buttons row
    """
    page = page_mobile_portrait
    app = provide_app
    scenario = seed_orphaned_url_scenario(app=app, user_id=USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=scenario.utub_id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=scenario.orphaned_utub_url_id)
    wait_then_click_element(page=page, css_selector=row_selector)
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    badge = page.locator(f"{row_selector} {HPL.URL_DATE_ADDED_BADGE_STACKED}")
    expect(badge).to_be_visible()
    expect(badge).to_have_text(FORMER_MEMBER_BADGE_PATTERN)
    expect(badge).not_to_contain_text(scenario.departed_username)

    access_btn = page.locator(f"{row_selector} {HPL.BUTTON_URL_ACCESS}")
    delete_btn = page.locator(f"{row_selector} {HPL.BUTTON_URL_DELETE}")
    expect(delete_btn).to_be_visible()
    badge_box = badge.bounding_box()
    access_box = access_btn.bounding_box()
    delete_box = delete_btn.bounding_box()
    row_box = page.locator(row_selector).bounding_box()
    assert (
        badge_box is not None
        and access_box is not None
        and delete_box is not None
        and row_box is not None
    )
    buttons_bottom = max(
        access_box["y"] + access_box["height"], delete_box["y"] + delete_box["height"]
    )
    assert badge_box["y"] >= buttons_bottom - 1, "Badge must sit below the buttons row"
    # Stacked left-aligned: starts at the buttons' left edge, not pinned to the right
    assert abs(badge_box["x"] - access_box["x"]) <= 2, (
        "Badge must be left-aligned with the buttons row"
    )
    assert badge_box["x"] + badge_box["width"] <= row_box["x"] + row_box["width"] + 1
