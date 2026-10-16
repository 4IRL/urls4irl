from typing import Any

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    update_utub_name_and_description,
    update_utub_to_empty_desc,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    select_utub_by_name,
    wait_then_get_element,
    wait_until_utub_name_appears,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.playwright_utils import (
    open_update_utub_desc_input,
    open_update_utub_name_input,
)

pytestmark = pytest.mark.utubs_ui


def _scroll_height_within_client_height(*, locator: Locator) -> bool:
    """True when the element is fully visible (no clipped overflow)."""
    return locator.evaluate(
        "element => element.scrollHeight <= element.clientHeight + 1"
    )


def _single_line_height(*, locator: Locator) -> int:
    """Return the rendered clientHeight (px) of the element."""
    return locator.evaluate("element => element.clientHeight")


def _parse_font_px(css_value: str) -> int:
    """Parse a CSS font-size string (e.g. ``"32px"`` or ``"32.00px"``) to int px."""
    return int(float(css_value.rstrip("px")))


def _computed_line_height_px(*, locator: Locator) -> float:
    """Return the element's computed single-line height in px.

    Reads ``getComputedStyle(element).lineHeight``. When the browser reports
    the keyword ``"normal"`` (no explicit line-height resolved to a length),
    falls back to measuring the actual rendered height of a single line by
    cloning the element, forcing its content to one short line, and reading
    the clone's ``clientHeight``. This keeps the test robust to stylesheet
    line-height changes instead of assuming a fixed multiple of the font size.
    """
    return locator.evaluate("""
        (element) => {
            const computed = window.getComputedStyle(element);
            const lineHeight = computed.lineHeight;
            if (lineHeight && lineHeight !== "normal") {
                const parsed = parseFloat(lineHeight);
                if (!Number.isNaN(parsed)) {
                    return parsed;
                }
            }
            const clone = element.cloneNode(false);
            clone.textContent = "M";
            clone.style.height = "auto";
            clone.style.minHeight = "0";
            clone.style.maxHeight = "none";
            clone.style.whiteSpace = "nowrap";
            clone.style.position = "absolute";
            clone.style.visibility = "hidden";
            clone.style.pointerEvents = "none";
            element.parentElement.appendChild(clone);
            const measured = clone.clientHeight;
            clone.remove();
            return measured;
        }
        """)


def test_url_deck_header_and_subheader_render_at_max_font_when_short(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub whose title and description are short enough to fit on one line
    WHEN the owner selects it
    THEN the title (#URLDeckHeader) renders at the max title font and the
        description (#URLDeckSubheader) renders at the max description font.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    update_utub_name_and_description(
        app,
        utub_user_created.id,
        UI_TEST_STRINGS.SHORT_FIT_UTUB_NAME,
        UI_TEST_STRINGS.SHORT_FIT_UTUB_DESCRIPTION,
    )

    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id,
        utub_name=UI_TEST_STRINGS.SHORT_FIT_UTUB_NAME,
    )
    wait_until_utub_name_appears(
        page=page, utub_name=UI_TEST_STRINGS.SHORT_FIT_UTUB_NAME
    )

    header = wait_then_get_element(page=page, css_selector=HPL.HEADER_URL_DECK)
    subheader = wait_then_get_element(page=page, css_selector=HPL.SUBHEADER_URL_DECK)
    assert header is not None
    assert subheader is not None

    header_font_size = header.evaluate(
        "element => window.getComputedStyle(element).fontSize"
    )
    subheader_font_size = subheader.evaluate(
        "element => window.getComputedStyle(element).fontSize"
    )

    assert _parse_font_px(header_font_size) == UI_TEST_STRINGS.TITLE_MAX_FONT_PX
    assert _parse_font_px(subheader_font_size) == UI_TEST_STRINGS.DESC_MAX_FONT_PX

    # Short text fits on a single line, so it is never clipped.
    assert _scroll_height_within_client_height(locator=subheader)


def test_url_deck_header_and_subheader_shrink_and_wrap_when_long(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub whose title (30 chars) and description (~244 chars) overflow
        a single line
    WHEN the owner selects it
    THEN the description renders at the min description font, the title renders
        between min and max title font, neither is truncated (full text present),
        and both are fully visible (wrapped, scrollHeight <= clientHeight).
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    update_utub_name_and_description(
        app,
        utub_user_created.id,
        UI_TEST_STRINGS.LONG_FIT_UTUB_NAME,
        UI_TEST_STRINGS.LONG_FIT_UTUB_DESCRIPTION,
    )

    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id,
        utub_name=UI_TEST_STRINGS.LONG_FIT_UTUB_NAME,
    )
    wait_until_utub_name_appears(
        page=page, utub_name=UI_TEST_STRINGS.LONG_FIT_UTUB_NAME
    )

    header = wait_then_get_element(page=page, css_selector=HPL.HEADER_URL_DECK)
    subheader = wait_then_get_element(page=page, css_selector=HPL.SUBHEADER_URL_DECK)
    assert header is not None
    assert subheader is not None

    # 1. Description clamps to its minimum font; the 30-char title shrinks into
    #    the [min, max] range (it may or may not hit min depending on its width).
    subheader_font_size = subheader.evaluate(
        "element => window.getComputedStyle(element).fontSize"
    )
    assert _parse_font_px(subheader_font_size) == UI_TEST_STRINGS.DESC_MIN_FONT_PX
    header_font_size = header.evaluate(
        "element => window.getComputedStyle(element).fontSize"
    )
    header_font_px = _parse_font_px(header_font_size)
    assert UI_TEST_STRINGS.TITLE_MIN_FONT_PX <= header_font_px
    assert header_font_px <= UI_TEST_STRINGS.TITLE_MAX_FONT_PX

    # 2. Not truncated: the full text is present (no ellipsis substitution).
    assert header.inner_text() == UI_TEST_STRINGS.LONG_FIT_UTUB_NAME
    assert subheader.inner_text() == UI_TEST_STRINGS.LONG_FIT_UTUB_DESCRIPTION

    # 3. Wrapped / fully visible: nothing clipped, and the description spans more
    #    than a single line.
    assert _scroll_height_within_client_height(locator=subheader)
    single_desc_line_px = _computed_line_height_px(locator=subheader)
    assert _single_line_height(locator=subheader) > single_desc_line_px

    # 4. A full-width title's trailing edit-name pencil must not butt up against
    #    the action buttons (filter/add): the name group reserves an inline-end
    #    gap before them.
    name_group_margin_end_px = float(
        page.evaluate(
            "window.getComputedStyle("
            "document.getElementById('UTubNameOuterUpdateWrap')"
            ").marginInlineEnd"
        ).rstrip("px")
    )
    assert name_group_margin_end_px > 0


def test_url_deck_header_edit_still_opens_after_font_fit(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a UTub with a long, font-fitted/wrapped title and description
    WHEN the owner clicks the title text and the description text
    THEN the inline name-edit and description-edit inputs still open — the
        wrapping/scaling did not break click-to-edit.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    update_utub_name_and_description(
        app,
        utub_user_created.id,
        UI_TEST_STRINGS.LONG_FIT_UTUB_NAME,
        UI_TEST_STRINGS.LONG_FIT_UTUB_DESCRIPTION,
    )

    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id,
        utub_name=UI_TEST_STRINGS.LONG_FIT_UTUB_NAME,
    )
    wait_until_utub_name_appears(
        page=page, utub_name=UI_TEST_STRINGS.LONG_FIT_UTUB_NAME
    )

    open_update_utub_name_input(page=page)
    wait_until_visible_css_selector(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)
    name_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE
    )
    assert name_input is not None
    name_input.wait_for(state="visible")

    open_update_utub_desc_input(page=page)
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    desc_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert desc_input is not None
    desc_input.wait_for(state="visible")


_OUTER_WRAP = "#UTubDescriptionSubheaderOuterWrap"
_LAYOUT_TOLERANCE_PX = 4
_NARROW_DESKTOP_WIDTH_PX = 1000
_WIDENED_DESKTOP_WIDTH_PX = 1500
_RESIZE_DEBOUNCE_WAIT_MS = 400


def _layout_rects(*, page: Page) -> dict[str, Any]:
    """Return the outer wrap content width, the bounding rects (top/bottom/right/
    width) of the description wrap, its text, its pencil and the search wrap, and
    whether the description wrap carries the full-row state class."""
    return page.evaluate(
        """
        () => {
            const rect = (selector) => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {
                    top: r.top,
                    bottom: r.bottom,
                    right: r.right,
                    width: r.width,
                };
            };
            const outer = document.querySelector("#UTubDescriptionSubheaderOuterWrap");
            const style = window.getComputedStyle(outer);
            const contentWidth =
                outer.clientWidth -
                parseFloat(style.paddingLeft) -
                parseFloat(style.paddingRight);
            return {
                outerContentWidth: contentWidth,
                outerHeight: outer.getBoundingClientRect().height,
                desc: rect("#UTubDescriptionSubheaderWrap"),
                search: rect("#SearchURLWrap"),
                descText: rect("#URLDeckSubheader"),
                descPencil: rect("#UTubDescriptionSubheaderWrap .edit-pencil-icon"),
                descFillsRow: document
                    .querySelector("#UTubDescriptionSubheaderWrap")
                    .classList.contains("descriptionFillsRow"),
                descFontPx: parseFloat(
                    window.getComputedStyle(
                        document.querySelector("#URLDeckSubheader")
                    ).fontSize
                ),
            };
        }
        """
    )


def _wait_for_font_fit_settled(*, page: Page) -> None:
    """Poll until the fitted description font is unchanged across a window longer
    than the resize debounce, so a pending re-fit cannot race the layout reads."""
    previous_font_px = -1.0
    for _ in range(20):
        current_font_px = _layout_rects(page=page)["descFontPx"]
        if current_font_px == previous_font_px:
            return
        previous_font_px = current_font_px
        page.wait_for_timeout(_RESIZE_DEBOUNCE_WAIT_MS)
    raise AssertionError("Description font fit did not settle")


def _assert_search_below_full_width_description(*, page: Page) -> None:
    _wait_for_font_fit_settled(page=page)
    rects = _layout_rects(page=page)
    assert (
        abs(rects["desc"]["width"] - rects["outerContentWidth"]) <= _LAYOUT_TOLERANCE_PX
    )
    assert rects["search"]["top"] >= rects["desc"]["bottom"] - 1
    assert rects["descFillsRow"]


def _assert_description_click_target_is_text_width(*, page: Page) -> None:
    """The description wrap (the owner's click-to-edit target) must not extend
    past its text plus the edit pencil."""
    rects = _layout_rects(page=page)
    content_right = max(rects["descText"]["right"], rects["descPencil"]["right"])
    assert rects["desc"]["right"] - content_right <= _LAYOUT_TOLERANCE_PX
    assert rects["desc"]["width"] < rects["outerContentWidth"] / 2
    assert not rects["descFillsRow"]


def _assert_search_beside(*, page: Page, anchor_selector: str) -> None:
    search_top = page.locator(HPL.URL_SEARCH_WRAP).evaluate(
        "element => element.getBoundingClientRect().top"
    )
    anchor_bottom = page.locator(anchor_selector).evaluate(
        "element => element.getBoundingClientRect().bottom"
    )
    assert search_top < anchor_bottom


def _select_utub_with_description(*, app: Flask, page: Page, description: str) -> None:
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    update_utub_name_and_description(
        app,
        utub_user_created.id,
        UI_TEST_STRINGS.SHORT_FIT_UTUB_NAME,
        description,
    )
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id,
        utub_name=UI_TEST_STRINGS.SHORT_FIT_UTUB_NAME,
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_WRAP)


def test_long_description_takes_full_row_and_search_drops_below(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a desktop viewport and a UTub with a long description
    WHEN the owner selects it
    THEN the description fills the row and the search box renders below it.
    """
    _select_utub_with_description(
        app=provide_app,
        page=page,
        description=UI_TEST_STRINGS.LONG_FIT_UTUB_DESCRIPTION,
    )
    _assert_search_below_full_width_description(page=page)


def test_short_description_keeps_search_beside(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a desktop viewport and a UTub with a short description
    WHEN the owner selects it
    THEN the search box stays beside the description on the same row, and the
    description's click target does not extend past its text.
    """
    _select_utub_with_description(
        app=provide_app,
        page=page,
        description=UI_TEST_STRINGS.SHORT_FIT_UTUB_DESCRIPTION,
    )

    _assert_search_beside(page=page, anchor_selector=HPL.WRAP_UTUB_DESCRIPTION_UPDATE)
    _assert_description_click_target_is_text_width(page=page)
    rects = _layout_rects(page=page)
    desc_height = rects["desc"]["bottom"] - rects["desc"]["top"]
    assert rects["outerHeight"] < 2 * desc_height


def test_empty_description_owner_keeps_search_beside_add_button(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a desktop viewport and an owned UTub with an empty description
    WHEN the owner selects it
    THEN the "Add a description?" button is visible and the search stays beside it.
    """
    app = provide_app
    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    update_utub_to_empty_desc(app, utub_user_created.id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_WRAP)
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY
    )

    _assert_search_beside(page=page, anchor_selector=HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY)


def test_empty_description_member_keeps_search_beside_no_description(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a desktop viewport and a UTub the user is a member of with no description
    WHEN the member selects it
    THEN the "No description" label is visible and the search stays beside it.
    """
    app = provide_app
    user_id = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id)
    update_utub_to_empty_desc(app, utub_user_member_of.id)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id, utub_id=utub_user_member_of.id
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_WRAP)
    wait_until_visible_css_selector(page=page, css_selector=HPL.LABEL_NO_DESCRIPTION)

    _assert_search_beside(page=page, anchor_selector=HPL.LABEL_NO_DESCRIPTION)


def test_description_edit_form_keeps_unwrapped_row_layout(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a desktop viewport and a UTub with a long description
    WHEN the owner opens the description edit form
    THEN the outer row is not wrapping (the pre-change edit layout).
    """
    _select_utub_with_description(
        app=provide_app,
        page=page,
        description=UI_TEST_STRINGS.LONG_FIT_UTUB_DESCRIPTION,
    )
    open_update_utub_desc_input(page=page)
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )

    flex_wrap = page.locator(_OUTER_WRAP).evaluate(
        "element => window.getComputedStyle(element).flexWrap"
    )
    assert flex_wrap == "nowrap"


def test_long_description_layout_after_narrowing_viewport_matches_fresh_select(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a long description selected at the default desktop width
    WHEN the viewport narrows (still >=992px) and the resize debounce settles
    THEN the layout and fitted font equal those of a fresh select at that width.
    """
    app = provide_app
    _select_utub_with_description(
        app=app,
        page=page,
        description=UI_TEST_STRINGS.LONG_FIT_UTUB_DESCRIPTION,
    )

    viewport_height = page.evaluate("window.innerHeight")
    page.set_viewport_size(
        {"width": _NARROW_DESKTOP_WIDTH_PX, "height": viewport_height}
    )

    _assert_search_below_full_width_description(page=page)
    resized_font_px = _layout_rects(page=page)["descFontPx"]

    other_utub = get_utub_this_user_did_not_create(app, 1)
    select_utub_by_name(page=page, utub_name=other_utub.name)
    select_utub_by_name(page=page, utub_name=UI_TEST_STRINGS.SHORT_FIT_UTUB_NAME)
    wait_until_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_WRAP)

    _assert_search_below_full_width_description(page=page)
    assert _layout_rects(page=page)["descFontPx"] == pytest.approx(
        resized_font_px, abs=0.5
    )


def test_long_description_font_after_widening_viewport_matches_fresh_select(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a long description fitted at a narrow desktop width
    WHEN the viewport widens (still >=992px) and the resize debounce settles
    THEN the fitted font equals that of a fresh select at the wider width.
    """
    app = provide_app
    _select_utub_with_description(
        app=app,
        page=page,
        description=UI_TEST_STRINGS.LONG_FIT_UTUB_DESCRIPTION,
    )

    viewport_height = page.evaluate("window.innerHeight")
    page.set_viewport_size(
        {"width": _NARROW_DESKTOP_WIDTH_PX, "height": viewport_height}
    )
    _assert_search_below_full_width_description(page=page)
    page.set_viewport_size(
        {"width": _WIDENED_DESKTOP_WIDTH_PX, "height": viewport_height}
    )
    _assert_search_below_full_width_description(page=page)
    widened_font_px = _layout_rects(page=page)["descFontPx"]

    other_utub = get_utub_this_user_did_not_create(app, 1)
    select_utub_by_name(page=page, utub_name=other_utub.name)
    select_utub_by_name(page=page, utub_name=UI_TEST_STRINGS.SHORT_FIT_UTUB_NAME)
    wait_until_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_WRAP)

    _assert_search_below_full_width_description(page=page)
    assert _layout_rects(page=page)["descFontPx"] == pytest.approx(
        widened_font_px, abs=0.5
    )
