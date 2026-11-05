"""Playwright UI tests for the "Your tags" personal display settings (Tags gear).

Each setting is exercised two ways: seeded straight into the database (a default
on ``UserPreferences`` or an override in ``Utub_Members.settings["tags"]``) to prove
how the deck renders it, and changed live through the real gear UI (no reload, no
seeding) to prove it applies at once. Waits are all auto-retrying assertions on
the DOM, never fixed sleeps.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, Route, expect

from backend.models.user_preferences import (
    CollapsedTagsStyle,
    TagCountStyle,
    TagMatchMode,
    TagSort,
    ViewMode,
)
from backend.models.utub_members import Member_Role
from backend.utils.strings.tag_strs import (
    TAG_FILTER_PILL_ANY_SUFFIX,
    TAG_FILTER_PILL_COUNT,
    TAG_FILTER_RESULT_ALL_ONE,
    TAG_FILTER_RESULT_ANY,
    TAG_FILTER_TRIM_ANNOUNCEMENT,
    TAG_MATCH_MODE_CUE,
    TAG_MORE_COUNT,
    TAG_MORE_COUNT_ONE,
)
from backend.utils.strings.utub_strs import (
    PANEL_SETTINGS_SAVE_FAILED,
    PANEL_SETTINGS_SAVED,
)
from tests.functional.db_utils import (
    get_member_settings_section,
    get_other_utub_this_user_is_member_of,
    get_tag_display_defaults,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    set_member_role_in_utub,
    set_member_settings,
    set_tag_display_defaults,
    set_tag_overrides,
    set_utub_locked_state,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_and_select_utub_by_utubid_mobile,
    login_user_select_utub_by_id_open_create_utub_tag,
)
from tests.functional.playwright_utils import (
    select_utub_by_id,
    wait_then_click_element,
)
from tests.functional.tags_ui.db_utils import (
    apply_tag_to_url_in_db,
    create_utub_tag,
    get_url_ids_in_utub_ordered,
)
from tests.functional.tags_ui.playwright_utils import (
    apply_tag_filter_based_on_id,
    drag_tag_onto_url,
    expect_badge_count_on_url_row,
    get_card_height,
    get_url_card_selector,
    get_utub_tag_filter_selector,
    wait_until_tag_sheet_open,
)

pytestmark = pytest.mark.tags_ui

USER_ID_FOR_TEST = 1
DESKTOP_VIEWPORT = {"width": 1280, "height": 900}
TAG_PREFERENCES_ROUTE = "**/users/preferences/tags"
OLD_FIXED_CARD_HEIGHT_PX = 152
DB_POLL_TIMEOUT_S = 10
DB_POLL_INTERVAL_MS = 50
CHIP_NAMES = f"{HPL.LIST_TAGS} {HPL.TAG_FILTERS} > span"
SELECTED_CHIPS = f"{HPL.LIST_TAGS} {HPL.TAG_FILTERS}.selected"

# Tag name -> number of URLs it is applied to (see _seed_sortable_tags). Creation
# order is Mango, apple, Cherry, so id order (oldest first) is that same order.
SORT_TAGS: dict[str, int] = {"Mango": 3, "apple": 1, "Cherry": 2}
SORT_ORDERS: dict[str, list[str]] = {
    "most_used": ["Mango", "Cherry", "apple"],
    "name_az": ["apple", "Cherry", "Mango"],
    "newest": ["Cherry", "apple", "Mango"],
    "oldest": ["Mango", "apple", "Cherry"],
}
SORT_ENUMS: dict[str, TagSort] = {
    "most_used": TagSort.MOST_USED,
    "name_az": TagSort.NAME_AZ,
    "newest": TagSort.NEWEST,
    "oldest": TagSort.OLDEST,
}


# --- Seeding and navigation helpers -------------------------------------------


def _owned_utub_id(*, app: Flask) -> int:
    return get_utub_this_user_created(app, USER_ID_FOR_TEST).id


def _seed_tag(*, app: Flask, utub_id: int, tag_string: str, url_ids: list[int]) -> int:
    """Create a UTub tag and apply it to ``url_ids``. Returns the tag id."""
    tag_id = create_utub_tag(
        app=app, utub_id=utub_id, user_id=USER_ID_FOR_TEST, tag_string=tag_string
    )
    for url_id in url_ids:
        apply_tag_to_url_in_db(
            app=app,
            utub_id=utub_id,
            user_id=USER_ID_FOR_TEST,
            utub_url_id=url_id,
            utub_tag_id=tag_id,
        )
    return tag_id


def _seed_sortable_tags(*, app: Flask, utub_id: int) -> dict[str, int]:
    """Apply Mango to 3 URLs, apple to 1 and Cherry to 2, created in that order,
    so every sort yields a distinct deck order. Returns tag name -> tag id."""
    url_ids = get_url_ids_in_utub_ordered(app=app, utub_id=utub_id)
    assert len(url_ids) >= 3
    return {
        name: _seed_tag(
            app=app, utub_id=utub_id, tag_string=name, url_ids=url_ids[:count]
        )
        for name, count in SORT_TAGS.items()
    }


def _login(*, app: Flask, page: Page, utub_id: int | None = None) -> int:
    """Log in at a desktop viewport and select the user's own UTub."""
    page.set_viewport_size(DESKTOP_VIEWPORT)
    utub_id = _owned_utub_id(app=app) if utub_id is None else utub_id
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    expect(page.locator(HPL.TAG_FILTERS).first).to_be_attached()
    return utub_id


def _open_tags_gear(*, page: Page) -> None:
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_TAG_SETTINGS_GEAR)
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()
    expect(page.locator(HPL.TAGS_PERSONAL_SORT_DEFAULT)).to_be_visible()


def _close_tags_gear(*, page: Page) -> None:
    page.keyboard.press("Escape")
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_hidden()


def _pick(*, page: Page, selector: str, value: str) -> None:
    page.locator(selector).select_option(value)


def _toggle(*, page: Page, selector: str, checked: bool) -> None:
    switch = page.locator(selector)
    expect(switch).to_be_visible()
    switch.click()
    expect(switch).to_have_attribute("aria-checked", str(checked).lower())


def _expect_saved(*, page: Page) -> None:
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        PANEL_SETTINGS_SAVED
    )


def _wait_for_db(*, page: Page, predicate: Callable[[], bool], what: str) -> None:
    """Poll a database predicate (bounded) for state with no DOM signal of its own,
    such as a saved switch whose effect is only seen on the next drop."""
    deadline = time.monotonic() + DB_POLL_TIMEOUT_S
    while not predicate():
        assert time.monotonic() < deadline, f"timed out waiting for {what}"
        page.wait_for_timeout(DB_POLL_INTERVAL_MS)


def _expect_chip_order(*, page: Page, names: list[str]) -> None:
    expect(page.locator(CHIP_NAMES)).to_have_text(names)


def _row(*, page: Page, url_id: int) -> Locator:
    return page.locator(get_url_card_selector(utub_url_id=url_id))


def _visible_url_ids(*, page: Page) -> list[int]:
    """Ids of the URL rows currently shown (not filtered out)."""
    return sorted(
        int(row_id)
        for row_id in page.locator(HPL.ROW_VISIBLE_URL).evaluate_all(
            "rows => rows.map(row => row.getAttribute('utuburlid'))"
        )
    )


def _expect_visible_url_count(*, page: Page, count: int) -> None:
    expect(page.locator(HPL.ROW_VISIBLE_URL)).to_have_count(count)


def _collapse_tag_deck(*, page: Page) -> None:
    wait_then_click_element(page=page, css_selector=HPL.HEADER_AND_CARET_TAG_DECK)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(re.compile(r"\bcollapsed\b"))


# --- Sort ---------------------------------------------------------------------


@pytest.mark.parametrize("sort", list(SORT_ORDERS))
def test_each_stored_sort_orders_the_deck_and_survives_a_reload(
    page: Page, create_test_urls, provide_app: Flask, sort: str
):
    """
    GIVEN tags whose usage, name and creation order all differ
    WHEN the user's default sort is each non-default sort
    THEN the deck is in that order on load, and still is after a reload
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    _seed_sortable_tags(app=app, utub_id=utub_id)
    set_tag_display_defaults(app, USER_ID_FOR_TEST, tag_sort=SORT_ENUMS[sort])

    _login(app=app, page=page, utub_id=utub_id)
    _expect_chip_order(page=page, names=SORT_ORDERS[sort])

    page.reload()
    _expect_chip_order(page=page, names=SORT_ORDERS[sort])


def test_most_in_view_sort_follows_the_applied_filter(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the default "Most in view" sort, where "Alpha" (3 URLs) leads
    WHEN a tag filter leaves only a URL that "Alpha" is not on
    THEN "Alpha" has nothing in view and sorts last
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    url_ids = get_url_ids_in_utub_ordered(app=app, utub_id=utub_id)
    assert len(url_ids) >= 4
    _seed_tag(app=app, utub_id=utub_id, tag_string="Alpha", url_ids=url_ids[:3])
    _seed_tag(app=app, utub_id=utub_id, tag_string="Bravo", url_ids=url_ids[2:4])
    filter_id = _seed_tag(
        app=app, utub_id=utub_id, tag_string="Filt", url_ids=url_ids[3:4]
    )
    _login(app=app, page=page, utub_id=utub_id)
    expect(page.locator(CHIP_NAMES).first).to_have_text("Alpha")

    apply_tag_filter_based_on_id(page=page, utub_tag_id=filter_id)

    expect(page.locator(CHIP_NAMES).last).to_have_text("Alpha")


def test_creating_a_tag_under_name_az_lands_in_sorted_place(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the Name A-Z sort
    WHEN a new tag is created from the Tag deck
    THEN it appears between its alphabetical neighbours, not at the end
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    _seed_sortable_tags(app=app, utub_id=utub_id)
    set_tag_display_defaults(app, USER_ID_FOR_TEST, tag_sort=TagSort.NAME_AZ)
    page.set_viewport_size(DESKTOP_VIEWPORT)
    login_user_select_utub_by_id_open_create_utub_tag(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    _expect_chip_order(page=page, names=SORT_ORDERS["name_az"])

    page.keyboard.type("Banana")
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE)

    _expect_chip_order(page=page, names=["apple", "Banana", "Cherry", "Mango"])


# --- Match mode ---------------------------------------------------------------


BOX_TOLERANCE_PX = 1
# One 0.8rem line plus its 4px bottom padding is ~23px; a squeezed 3-line wrap
# (the regression) is ~79px.
CUE_MAX_HEIGHT_PX = 32


def _expect_box_within(*, page: Page, selector: str, container: str) -> None:
    """The element's bounding box lies inside the container's and the viewport."""
    box = page.locator(selector).bounding_box()
    outer = page.locator(container).first.bounding_box()
    viewport = page.viewport_size
    assert box is not None and outer is not None and viewport is not None
    assert box["x"] >= outer["x"] - BOX_TOLERANCE_PX, (selector, box, outer)
    assert box["x"] + box["width"] <= outer["x"] + outer["width"] + BOX_TOLERANCE_PX, (
        selector,
        box,
        outer,
    )
    assert box["x"] + box["width"] <= viewport["width"] + BOX_TOLERANCE_PX, (
        selector,
        box,
        viewport,
    )


def _expect_cue_laid_out_on_one_line(*, page: Page, container: str) -> None:
    _expect_box_within(page=page, selector=HPL.TAG_MATCH_MODE_CUE, container=container)
    cue_box = page.locator(HPL.TAG_MATCH_MODE_CUE).bounding_box()
    assert cue_box is not None
    assert cue_box["height"] <= CUE_MAX_HEIGHT_PX, cue_box


def _seed_overlapping_tags(*, app: Flask, utub_id: int) -> tuple[int, int, list[int]]:
    """Tag A on URLs 0-1 and tag B on URLs 1-2: the union is 3 URLs, the
    intersection 1. Returns (tag A id, tag B id, the three URL ids)."""
    url_ids = get_url_ids_in_utub_ordered(app=app, utub_id=utub_id)
    assert len(url_ids) >= 4
    tag_a = _seed_tag(app=app, utub_id=utub_id, tag_string="TagA", url_ids=url_ids[:2])
    tag_b = _seed_tag(app=app, utub_id=utub_id, tag_string="TagB", url_ids=url_ids[1:3])
    return tag_a, tag_b, url_ids[:3]


def test_all_mode_shows_the_intersection_and_no_cue(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the default "all" match mode and two overlapping tags
    WHEN both tags are selected
    THEN only URLs with both are shown, with no "matching any" cue, and the
        collapsed pill reads "2 filtered" with no "any" suffix
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tag_a, tag_b, url_ids = _seed_overlapping_tags(app=app, utub_id=utub_id)
    _login(app=app, page=page, utub_id=utub_id)

    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_a)
    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_b)

    _expect_visible_url_count(page=page, count=1)
    assert _visible_url_ids(page=page) == [url_ids[1]]
    expect(page.locator(HPL.TAG_MATCH_MODE_CUE)).to_be_hidden()
    _collapse_tag_deck(page=page)
    expect(page.locator(HPL.TAG_DECK_FILTER_PILL)).to_have_text(
        TAG_FILTER_PILL_COUNT.replace("{n}", "2")
    )


def test_any_mode_shows_the_union_with_the_cue_and_pill_suffix(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN "any" as the default match mode and two overlapping tags
    WHEN one tag is selected, then the second
    THEN a single tag shows no cue; with two the union of URLs is shown, the cue
        reads "Matching any selected tag", and the collapsed pill reads
        "2 filtered · any"
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tag_a, tag_b, url_ids = _seed_overlapping_tags(app=app, utub_id=utub_id)
    set_tag_display_defaults(app, USER_ID_FOR_TEST, tag_match_mode=TagMatchMode.ANY)
    _login(app=app, page=page, utub_id=utub_id)

    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_a)
    expect(page.locator(HPL.TAG_MATCH_MODE_CUE)).to_be_hidden()
    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_b)

    _expect_visible_url_count(page=page, count=3)
    assert _visible_url_ids(page=page) == sorted(url_ids)
    cue = page.locator(HPL.TAG_MATCH_MODE_CUE)
    expect(cue).to_be_visible()
    expect(cue).to_have_text(TAG_MATCH_MODE_CUE)
    _expect_cue_laid_out_on_one_line(page=page, container=HPL.TAG_DECK)
    _collapse_tag_deck(page=page)
    pill = page.locator(HPL.TAG_DECK_FILTER_PILL)
    expect(pill).to_have_text(
        TAG_FILTER_PILL_COUNT.replace("{n}", "2") + TAG_FILTER_PILL_ANY_SUFFIX
    )
    _expect_box_within(
        page=page, selector=HPL.TAG_DECK_FILTER_PILL, container=HPL.TAG_DECK
    )
    # The pill's text must not be clipped by its own box ("2 filt...").
    assert pill.evaluate("el => el.scrollWidth <= el.clientWidth + 1")


def test_any_mode_cue_fits_the_mobile_tag_sheet(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN "any" as the match mode and two tags selected on a mobile viewport
    WHEN the tag sheet is open
    THEN the cue sits on one line inside the sheet and the viewport, not squeezed
        beside the gear and overflowing the edge
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tag_a, tag_b, _ = _seed_overlapping_tags(app=app, utub_id=utub_id)
    set_tag_display_defaults(app, USER_ID_FOR_TEST, tag_match_mode=TagMatchMode.ANY)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page_mobile_portrait, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE
    )
    wait_until_tag_sheet_open(page=page_mobile_portrait)
    apply_tag_filter_based_on_id(page=page_mobile_portrait, utub_tag_id=tag_a)
    apply_tag_filter_based_on_id(page=page_mobile_portrait, utub_tag_id=tag_b)

    expect(page_mobile_portrait.locator(HPL.TAG_MATCH_MODE_CUE)).to_be_visible()
    _expect_cue_laid_out_on_one_line(page=page_mobile_portrait, container=HPL.TAG_SHEET)


def _seed_many_tags(*, app: Flask, utub_id: int, count: int) -> list[int]:
    return [
        create_utub_tag(
            app=app,
            utub_id=utub_id,
            user_id=USER_ID_FOR_TEST,
            tag_string=f"Cap{index:02d}",
        )
        for index in range(count)
    ]


def test_any_mode_has_no_selection_cap_and_all_mode_trims_to_twenty(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN "any" as the default and 21 tags
    WHEN all 21 are selected, then the match mode is switched to "all" in the gear
    THEN every selection is accepted under "any"; on the switch the first 20 stay
        selected, the 21st is unselected and the trim sentence is announced in
        the settings live region (not in the deck's own announcement region)
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tag_ids = _seed_many_tags(app=app, utub_id=utub_id, count=21)
    set_tag_display_defaults(app, USER_ID_FOR_TEST, tag_match_mode=TagMatchMode.ANY)
    _login(app=app, page=page, utub_id=utub_id)

    for tag_id in tag_ids:
        apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_id)
    expect(page.locator(SELECTED_CHIPS)).to_have_count(21)
    expect(page.locator(f"{HPL.TAG_FILTERS}.disabled")).to_have_count(0)

    deck_announcement = page.locator(HPL.TAG_FILTER_ANNOUNCEMENT).text_content()
    _open_tags_gear(page=page)
    _pick(page=page, selector=HPL.TAGS_PERSONAL_MATCH_DEFAULT, value="all")

    expect(page.locator(SELECTED_CHIPS)).to_have_count(20)
    expect(
        page.locator(get_utub_tag_filter_selector(utub_tag_id=tag_ids[20]))
    ).to_have_class(re.compile(r"\bunselected\b"))
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        TAG_FILTER_TRIM_ANNOUNCEMENT
    )
    expect(page.locator(HPL.TAG_FILTER_ANNOUNCEMENT)).to_have_text(deck_announcement)


def test_gear_match_mode_change_announces_the_filter_result(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two overlapping tags selected under "all" (1 URL shown)
    WHEN the match mode is switched to "any" in the open Tags gear
    THEN the deck shows the union at once, the cue appears, and the settings live
        region carries the filter-result sentence while the deck's own
        announcement region stays empty
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tag_a, tag_b, _ = _seed_overlapping_tags(app=app, utub_id=utub_id)
    _login(app=app, page=page, utub_id=utub_id)
    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_a)
    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_b)
    _expect_visible_url_count(page=page, count=1)

    _open_tags_gear(page=page)
    _pick(page=page, selector=HPL.TAGS_PERSONAL_MATCH_DEFAULT, value="any")

    _expect_visible_url_count(page=page, count=3)
    expect(page.locator(HPL.TAG_MATCH_MODE_CUE)).to_be_visible()
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        TAG_FILTER_RESULT_ANY.replace("{n}", "3")
    )
    expect(page.locator(HPL.TAG_FILTER_ANNOUNCEMENT)).to_be_empty()

    _pick(page=page, selector=HPL.TAGS_PERSONAL_MATCH_DEFAULT, value="all")

    _expect_visible_url_count(page=page, count=1)
    expect(page.locator(HPL.TAG_MATCH_MODE_CUE)).to_be_hidden()
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        TAG_FILTER_RESULT_ALL_ONE
    )


# --- Count style --------------------------------------------------------------


def test_count_style_applies_live_through_the_gear(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN tags on URLs and the default count style
    WHEN the Tags gear's count style is changed to Total only, then Hide counts,
        then back to In view / total
    THEN the deck styles change each time with no reload, and the count text is
        what the style shows
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tag_ids = _seed_sortable_tags(app=app, utub_id=utub_id)
    _login(app=app, page=page, utub_id=utub_id)
    deck = page.locator(HPL.TAG_DECK)
    chip = page.locator(get_utub_tag_filter_selector(utub_tag_id=tag_ids["Mango"]))
    count = chip.locator(HPL.TAG_COUNT)
    expect(deck).to_have_attribute("data-tag-count-style", "in_view_total")
    expect(count).to_have_text("3 / 3", use_inner_text=True)

    _open_tags_gear(page=page)
    _pick(page=page, selector=HPL.TAGS_PERSONAL_COUNT_DEFAULT, value="total_only")
    expect(deck).to_have_attribute("data-tag-count-style", "total_only")
    expect(count).to_have_text("3", use_inner_text=True)
    _expect_saved(page=page)

    _pick(page=page, selector=HPL.TAGS_PERSONAL_COUNT_DEFAULT, value="hidden")
    expect(deck).to_have_attribute("data-tag-count-style", "hidden")
    expect(chip.locator(HPL.UTUB_TAG_COUNT_WRAP)).to_be_hidden()

    _pick(page=page, selector=HPL.TAGS_PERSONAL_COUNT_DEFAULT, value="in_view_total")
    expect(deck).to_have_attribute("data-tag-count-style", "in_view_total")
    expect(count).to_have_text("3 / 3", use_inner_text=True)


def test_in_view_total_style_shows_in_view_over_total_under_a_filter(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the default count style
    WHEN a tag filter hides some URLs
    THEN a chip's count reads "in view / total"
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tag_ids = _seed_sortable_tags(app=app, utub_id=utub_id)
    _login(app=app, page=page, utub_id=utub_id)

    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_ids["apple"])

    mango_count = page.locator(
        get_utub_tag_filter_selector(utub_tag_id=tag_ids["Mango"])
    ).locator(HPL.TAG_COUNT)
    expect(mango_count).to_have_text("1 / 3", use_inner_text=True)


# --- Collapsed tags -----------------------------------------------------------

COLLAPSED_TAG_COUNT = 14


def _seed_wrapping_tags(*, app: Flask, utub_id: int) -> tuple[int, int]:
    """Apply enough long-named tags to one URL that its badges wrap at 1280px.
    Returns (that URL's id, another URL's id that has no tags)."""
    url_ids = get_url_ids_in_utub_ordered(app=app, utub_id=utub_id)
    for index in range(COLLAPSED_TAG_COUNT):
        _seed_tag(
            app=app,
            utub_id=utub_id,
            tag_string=f"LongTagName{index:02d}",
            url_ids=url_ids[:1],
        )
    return url_ids[0], url_ids[1]


def _seed_collapsed_tags_setting(
    *, app: Flask, utub_id: int, style: CollapsedTagsStyle, view: ViewMode
) -> None:
    set_tag_display_defaults(
        app,
        USER_ID_FOR_TEST,
        show_tags_on_collapsed=True,
        collapsed_tags_style=style,
    )
    set_member_settings(
        app, utub_id, USER_ID_FOR_TEST, {"urls": {"view_mode": view.value}}
    )


def _badge_counts(*, page: Page, url_id: int) -> dict:
    """Total, visible and "+N" numbers for one collapsed row's tag badges."""
    # Two animation frames first, so a pending resize/overflow recompute has landed.
    return page.evaluate(
        """(selector) => new Promise((resolve) => {
            requestAnimationFrame(() => requestAnimationFrame(() => {
                const container = document.querySelector(
                    selector + ' .urlTagsContainer'
                );
                const badges = Array.from(
                    container.querySelectorAll(':scope > .tagBadge')
                ).filter((badge) => !badge.classList.contains('tagBadgeMore'));
                const more = container.querySelector(':scope > .tagBadgeMore');
                const visible = badges.filter(
                    (badge) => badge.getClientRects().length > 0
                );
                resolve({
                    total: badges.length,
                    visible: visible.length,
                    moreVisual: more
                        ? more.querySelector('[aria-hidden]').textContent
                        : null,
                    moreSpoken: more
                        ? more.querySelector('.visually-hidden').textContent
                        : null,
                });
            }));
        })""",
        get_url_card_selector(utub_url_id=url_id),
    )


@pytest.mark.parametrize("view", [ViewMode.LIST, ViewMode.CARDS])
def test_one_line_collapsed_tags_show_plus_n_equal_to_the_hidden_badges(
    page: Page, create_test_urls, provide_app: Flask, view: ViewMode
):
    """
    GIVEN "show tags on collapsed URLs" with "One line (+N more)" in List or Cards
    WHEN a collapsed card has more tags than fit on one line
    THEN the first line of badges shows plus a "+N" where N is (total badges
        minus visible badges), with matching visually hidden "N more tags" text;
        a card with no tags shows none
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tagged_url_id, untagged_url_id = _seed_wrapping_tags(app=app, utub_id=utub_id)
    _seed_collapsed_tags_setting(
        app=app, utub_id=utub_id, style=CollapsedTagsStyle.ONE_LINE, view=view
    )
    _login(app=app, page=page, utub_id=utub_id)
    expect(page.locator(HPL.URL_DECK)).to_have_attribute(
        "data-collapsed-tags", "one_line"
    )

    row = _row(page=page, url_id=tagged_url_id)
    expect(row.locator(".tagBadgeMore")).to_have_count(1)
    counts = _badge_counts(page=page, url_id=tagged_url_id)

    hidden = counts["total"] - counts["visible"]
    assert counts["total"] == COLLAPSED_TAG_COUNT
    assert 0 < counts["visible"] < counts["total"], counts
    assert counts["moreVisual"] == f"+{hidden}", counts
    assert counts["moreSpoken"] == TAG_MORE_COUNT.replace("{n}", str(hidden)), counts
    expect(_row(page=page, url_id=untagged_url_id).locator(".tagBadge")).to_have_count(
        0
    )


@pytest.mark.parametrize("view", [ViewMode.LIST, ViewMode.CARDS])
def test_all_collapsed_tags_show_every_badge_without_plus_n(
    page: Page, create_test_urls, provide_app: Flask, view: ViewMode
):
    """
    GIVEN "show tags on collapsed URLs" with "All" in List or Cards
    WHEN a collapsed card has many tags
    THEN every badge is visible and there is no "+N"
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tagged_url_id, _ = _seed_wrapping_tags(app=app, utub_id=utub_id)
    _seed_collapsed_tags_setting(
        app=app, utub_id=utub_id, style=CollapsedTagsStyle.ALL, view=view
    )
    _login(app=app, page=page, utub_id=utub_id)
    expect(page.locator(HPL.URL_DECK)).to_have_attribute("data-collapsed-tags", "all")

    row = _row(page=page, url_id=tagged_url_id)
    expect(row.locator(".tagBadge")).to_have_count(COLLAPSED_TAG_COUNT)
    expect(row.locator(".tagBadge").last).to_be_visible()
    expect(row.locator(".tagBadgeMore")).to_have_count(0)
    counts = _badge_counts(page=page, url_id=tagged_url_id)
    assert counts["visible"] == counts["total"] == COLLAPSED_TAG_COUNT, counts


def test_cards_all_collapsed_row_grows_past_the_old_fixed_height(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN Cards view with collapsed tags set to "All" and a card whose tags wrap
    WHEN the page loads
    THEN the collapsed card is taller than the old fixed 152px, and a card with no
        tags is still the ordinary height
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tagged_url_id, untagged_url_id = _seed_wrapping_tags(app=app, utub_id=utub_id)
    _seed_collapsed_tags_setting(
        app=app, utub_id=utub_id, style=CollapsedTagsStyle.ALL, view=ViewMode.CARDS
    )
    _login(app=app, page=page, utub_id=utub_id)
    expect(
        _row(page=page, url_id=tagged_url_id).locator(".tagBadge").last
    ).to_be_visible()

    assert (
        get_card_height(page=page, utub_url_id=tagged_url_id) > OLD_FIXED_CARD_HEIGHT_PX
    )
    assert (
        get_card_height(page=page, utub_url_id=untagged_url_id)
        >= OLD_FIXED_CARD_HEIGHT_PX - 1
    )


@pytest.mark.parametrize("style", [CollapsedTagsStyle.ONE_LINE, CollapsedTagsStyle.ALL])
@pytest.mark.parametrize("view", [ViewMode.TITLE_LINE, ViewMode.URL_LINE])
def test_line_views_never_show_collapsed_tags(
    page: Page,
    create_test_urls,
    provide_app: Flask,
    view: ViewMode,
    style: CollapsedTagsStyle,
):
    """
    GIVEN collapsed tags turned on in either style
    WHEN the URL deck is in a line view mode
    THEN the collapsed rows show no tag badges and no "+N"
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tagged_url_id, _ = _seed_wrapping_tags(app=app, utub_id=utub_id)
    _seed_collapsed_tags_setting(app=app, utub_id=utub_id, style=style, view=view)
    _login(app=app, page=page, utub_id=utub_id)
    expect(page.locator("body")).to_have_attribute("data-view", view.value)
    expect(page.locator(HPL.URL_DECK)).to_have_attribute(
        "data-collapsed-tags", style.value
    )

    row = _row(page=page, url_id=tagged_url_id)
    expect(row).to_be_visible()
    expect(row.locator(".urlTags")).to_have_css("opacity", "0")
    expect(row.locator(".tagBadgeMore")).to_have_count(0)


def test_collapsed_tags_apply_live_through_the_gear(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a card with wrapping tags and collapsed tags off
    WHEN the Tags gear switch is turned on, then the style set to "All", then the
        switch turned off
    THEN the deck shows "+N" (One line), then every badge (All), then no tags,
        each time with no reload; the nested style select is disabled while the
        switch is off
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tagged_url_id, _ = _seed_wrapping_tags(app=app, utub_id=utub_id)
    _login(app=app, page=page, utub_id=utub_id)
    deck = page.locator(HPL.URL_DECK)
    row = _row(page=page, url_id=tagged_url_id)
    expect(deck).to_have_attribute("data-collapsed-tags", "off")
    expect(row.locator(".urlTags")).to_have_css("opacity", "0")

    _open_tags_gear(page=page)
    nested = page.locator(HPL.TAGS_PERSONAL_COLLAPSED_STYLE_DEFAULT)
    expect(nested).to_have_attribute("aria-disabled", "true")

    _toggle(page=page, selector=HPL.TAGS_PERSONAL_COLLAPSED_DEFAULT, checked=True)
    expect(nested).not_to_have_attribute("aria-disabled", "true")
    expect(deck).to_have_attribute("data-collapsed-tags", "one_line")
    expect(row.locator(".tagBadgeMore")).to_have_count(1)

    _pick(page=page, selector=HPL.TAGS_PERSONAL_COLLAPSED_STYLE_DEFAULT, value="all")
    expect(deck).to_have_attribute("data-collapsed-tags", "all")
    expect(row.locator(".tagBadgeMore")).to_have_count(0)
    expect(row.locator(".tagBadge").last).to_be_visible()

    _toggle(page=page, selector=HPL.TAGS_PERSONAL_COLLAPSED_DEFAULT, checked=False)
    expect(deck).to_have_attribute("data-collapsed-tags", "off")
    expect(row.locator(".urlTags")).to_have_css("opacity", "0")
    expect(nested).to_have_attribute("aria-disabled", "true")


def test_singular_more_tags_text_for_a_single_hidden_badge(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN one-line collapsed tags where exactly one badge wraps
    WHEN the page loads
    THEN the "+1" badge's spoken text is the singular "1 more tag"
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tagged_url_id, _ = _seed_wrapping_tags(app=app, utub_id=utub_id)
    _seed_collapsed_tags_setting(
        app=app, utub_id=utub_id, style=CollapsedTagsStyle.ONE_LINE, view=ViewMode.LIST
    )
    _login(app=app, page=page, utub_id=utub_id)

    # Text widths are layout-dependent: measure how many same-length badges fit on
    # the first line, then tag another URL with exactly one more than that.
    fits = _badge_counts(page=page, url_id=tagged_url_id)["visible"]
    assert 0 < fits < COLLAPSED_TAG_COUNT - 1
    url_ids = get_url_ids_in_utub_ordered(app=app, utub_id=utub_id)
    single_wrap_url_id = url_ids[2]
    for index in range(fits + 1):
        _seed_tag(
            app=app,
            utub_id=utub_id,
            tag_string=f"LongTagName{COLLAPSED_TAG_COUNT + index:02d}",
            url_ids=[single_wrap_url_id],
        )
    page.reload()

    row = _row(page=page, url_id=single_wrap_url_id)
    expect(row.locator(".tagBadge:not(.tagBadgeMore)")).to_have_count(fits + 1)
    expect(row.locator(".tagBadgeMore")).to_have_count(1)
    counts = _badge_counts(page=page, url_id=single_wrap_url_id)
    assert counts["total"] - counts["visible"] == 1, counts
    assert counts["moreVisual"] == "+1", counts
    assert counts["moreSpoken"] == TAG_MORE_COUNT_ONE, counts


# --- Drop toggle --------------------------------------------------------------


def _seed_drop_scene(*, app: Flask, utub_id: int) -> tuple[int, int]:
    """One tag applied to no URL. Returns (tag id, the first URL's id)."""
    url_ids = get_url_ids_in_utub_ordered(app=app, utub_id=utub_id)
    tag_id = create_utub_tag(
        app=app, utub_id=utub_id, user_id=USER_ID_FOR_TEST, tag_string="DropTag"
    )
    return tag_id, url_ids[0]


def test_drop_with_the_toggle_off_adds_the_tag_but_leaves_the_card_collapsed(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN "Open the URL after dropping a tag on it" stored as off
    WHEN a tag chip is dropped on an unselected card
    THEN the badge is added but the card is not opened
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    tag_id, url_id = _seed_drop_scene(app=app, utub_id=utub_id)
    set_tag_display_defaults(app, USER_ID_FOR_TEST, tag_drop_opens_url=False)
    _login(app=app, page=page, utub_id=utub_id)

    drag_tag_onto_url(page=page, utub_tag_id=tag_id, utub_url_id=url_id)

    expect_badge_count_on_url_row(page=page, utub_url_id=url_id, expected=1)
    expect(_row(page=page, url_id=url_id)).not_to_have_attribute("urlselected", "true")


def _stored_drop_opens_url(*, app: Flask) -> bool | None:
    defaults = get_tag_display_defaults(app, USER_ID_FOR_TEST)
    return None if defaults is None else defaults.tag_drop_opens_url


def test_drop_toggle_applies_live_through_the_gear(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the default (a drop opens the card) and two URLs
    WHEN the toggle is turned off in the Tags gear and a tag is dropped on the first
        URL, then turned on again and dropped on the second
    THEN the first card stays collapsed and the second opens
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    url_ids = get_url_ids_in_utub_ordered(app=app, utub_id=utub_id)
    tag_id, _ = _seed_drop_scene(app=app, utub_id=utub_id)
    _login(app=app, page=page, utub_id=utub_id)

    _open_tags_gear(page=page)
    _toggle(page=page, selector=HPL.TAGS_PERSONAL_DROP_DEFAULT, checked=False)
    _wait_for_db(
        page=page,
        predicate=lambda: _stored_drop_opens_url(app=app) is False,
        what="drop toggle stored off",
    )
    _close_tags_gear(page=page)
    drag_tag_onto_url(page=page, utub_tag_id=tag_id, utub_url_id=url_ids[0])
    expect_badge_count_on_url_row(page=page, utub_url_id=url_ids[0], expected=1)
    expect(_row(page=page, url_id=url_ids[0])).not_to_have_attribute(
        "urlselected", "true"
    )

    _open_tags_gear(page=page)
    _toggle(page=page, selector=HPL.TAGS_PERSONAL_DROP_DEFAULT, checked=True)
    _wait_for_db(
        page=page,
        predicate=lambda: _stored_drop_opens_url(app=app) is True,
        what="drop toggle stored on",
    )
    _close_tags_gear(page=page)
    drag_tag_onto_url(page=page, utub_tag_id=tag_id, utub_url_id=url_ids[1])
    expect(_row(page=page, url_id=url_ids[1])).to_have_attribute("urlselected", "true")


# --- Overrides, persistence and failures --------------------------------------


def test_override_stays_in_its_utub_and_does_not_leak(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a per-UTub count style override stored for one UTub
    WHEN that UTub, then the user's other UTub, is opened
    THEN only the first one shows the override; the other uses the default
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    other_utub_id = get_other_utub_this_user_is_member_of(
        app, USER_ID_FOR_TEST, utub_id
    ).id
    _seed_sortable_tags(app=app, utub_id=utub_id)
    set_tag_overrides(app, utub_id, USER_ID_FOR_TEST, {"tag_count_style": "total_only"})
    _login(app=app, page=page, utub_id=utub_id)
    deck = page.locator(HPL.TAG_DECK)
    expect(deck).to_have_attribute("data-tag-count-style", "total_only")

    select_utub_by_id(page=page, utub_id=other_utub_id)

    expect(deck).to_have_attribute("data-tag-count-style", "in_view_total")

    select_utub_by_id(page=page, utub_id=utub_id)

    expect(deck).to_have_attribute("data-tag-count-style", "total_only")


def test_default_and_override_set_in_the_gear_survive_a_reload(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the Tags gear open on the user's UTub
    WHEN the default sort is set to Name A-Z and a this-UTub count style override
        is revealed and set to Hide counts
    THEN both are stored (default on the account, override on the membership),
        apply at once, and still apply after a reload; "Use my default" clears
        the stored override
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    _seed_sortable_tags(app=app, utub_id=utub_id)
    _login(app=app, page=page, utub_id=utub_id)
    deck = page.locator(HPL.TAG_DECK)

    _open_tags_gear(page=page)
    _pick(page=page, selector=HPL.TAGS_PERSONAL_SORT_DEFAULT, value="name_az")
    _expect_saved(page=page)
    _expect_chip_order(page=page, names=SORT_ORDERS["name_az"])
    page.locator(HPL.TAGS_PERSONAL_COUNT_REVEAL).click()
    _pick(page=page, selector=HPL.TAGS_PERSONAL_COUNT_OVERRIDE, value="hidden")
    expect(deck).to_have_attribute("data-tag-count-style", "hidden")
    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        PANEL_SETTINGS_SAVED
    )

    defaults = get_tag_display_defaults(app, USER_ID_FOR_TEST)
    assert defaults is not None and defaults.tag_sort == TagSort.NAME_AZ
    assert defaults.tag_count_style == TagCountStyle.IN_VIEW_TOTAL
    assert get_member_settings_section(app, utub_id, USER_ID_FOR_TEST, "tags") == {
        "tag_count_style": "hidden"
    }

    page.reload()
    _expect_chip_order(page=page, names=SORT_ORDERS["name_az"])
    expect(page.locator(HPL.TAG_DECK)).to_have_attribute(
        "data-tag-count-style", "hidden"
    )
    _open_tags_gear(page=page)
    expect(page.locator(HPL.TAGS_PERSONAL_SORT_DEFAULT)).to_have_value("name_az")
    expect(page.locator(HPL.TAGS_PERSONAL_COUNT_OVERRIDE)).to_have_value("hidden")

    page.locator(HPL.TAGS_PERSONAL_COUNT_USE_DEFAULT).click()
    expect(page.locator(HPL.TAG_DECK)).to_have_attribute(
        "data-tag-count-style", "in_view_total"
    )
    _wait_for_db(
        page=page,
        predicate=lambda: (
            "tag_count_style"
            not in (
                get_member_settings_section(app, utub_id, USER_ID_FOR_TEST, "tags")
                or {}
            )
        ),
        what="override cleared",
    )


def test_a_rejected_save_shows_couldnt_save_and_reverts_the_deck(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the Tags gear open and the preferences request answered with a 400
    WHEN the default sort is changed
    THEN "Couldn't save" is announced, the control returns to the stored value
        and the deck order never changes
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    _seed_sortable_tags(app=app, utub_id=utub_id)
    _login(app=app, page=page, utub_id=utub_id)
    initial_order = page.locator(CHIP_NAMES).all_text_contents()

    def reject(route: Route) -> None:
        route.fulfill(
            status=400,
            content_type="application/json",
            body='{"status": "Failure", "message": "forced failure"}',
        )

    page.route(TAG_PREFERENCES_ROUTE, reject)
    _open_tags_gear(page=page)
    _pick(page=page, selector=HPL.TAGS_PERSONAL_SORT_DEFAULT, value="name_az")

    expect(page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)).to_contain_text(
        PANEL_SETTINGS_SAVE_FAILED
    )
    expect(page.locator(HPL.TAGS_PERSONAL_SORT_DEFAULT)).to_have_value("most_in_view")
    assert page.locator(CHIP_NAMES).all_text_contents() == initial_order
    defaults = get_tag_display_defaults(app, USER_ID_FOR_TEST)
    assert defaults is None or defaults.tag_sort == TagSort.MOST_IN_VIEW


def test_sort_applies_live_through_the_gear(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN tags with distinct orders under every sort
    WHEN each sort is picked in the open Tags gear in turn
    THEN the deck reorders each time with no reload
    """
    app = provide_app
    utub_id = _owned_utub_id(app=app)
    _seed_sortable_tags(app=app, utub_id=utub_id)
    _login(app=app, page=page, utub_id=utub_id)

    _open_tags_gear(page=page)
    for sort, order in SORT_ORDERS.items():
        _pick(page=page, selector=HPL.TAGS_PERSONAL_SORT_DEFAULT, value=sort)
        _expect_chip_order(page=page, names=order)
    _expect_saved(page=page)


def test_plain_member_of_a_locked_utub_saves_a_default_that_survives_a_reload(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a plain (non-manager) member of a locked UTub
    WHEN they open the Tags gear and change the count style default
    THEN it applies at once and still applies after a reload
    """
    app = provide_app
    utub_id = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST).id
    set_member_role_in_utub(app, USER_ID_FOR_TEST, utub_id, Member_Role.MEMBER)
    set_utub_locked_state(app, utub_id, True)
    _seed_sortable_tags(app=app, utub_id=utub_id)
    _login(app=app, page=page, utub_id=utub_id)
    deck = page.locator(HPL.TAG_DECK)

    _open_tags_gear(page=page)
    _pick(page=page, selector=HPL.TAGS_PERSONAL_COUNT_DEFAULT, value="total_only")

    expect(deck).to_have_attribute("data-tag-count-style", "total_only")
    _expect_saved(page=page)

    page.reload()
    expect(page.locator(HPL.TAG_DECK)).to_have_attribute(
        "data-tag-count-style", "total_only"
    )
