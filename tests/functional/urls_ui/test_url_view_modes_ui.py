from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, expect

from tests.functional.db_utils import (
    get_url_in_utub,
    get_utub_this_user_created,
    set_member_settings,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    get_css_selector_for_url_by_id,
    wait_for_css_transitions_to_finish,
    wait_then_click_element,
)

pytestmark = pytest.mark.urls_ui

USER_ID_FOR_TEST = 1
MAX_COLLAPSED_ROW_HEIGHT_PX = 36
SELECTED_HEIGHT_TOLERANCE_PX = 2
MOBILE_MAX_WIDTH_PX = 768
LINE_ROW_PADDING = "3px"
LINE_MODES = ["title_line", "url_line"]
VIEWPORTS = [
    pytest.param("desktop", id="desktop"),
    pytest.param("mobile", id="mobile", marks=pytest.mark.mobile_ui),
]

# Rectangles (not Playwright boxes) so a hidden element (display: none) reports
# nothing instead of a 0x0 box at the origin.
_VISIBLE_RECT_JS = """(element) => {
    if (element.getClientRects().length === 0) return null;
    const rect = element.getBoundingClientRect();
    return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
}"""


def _prepare(
    *,
    app: Flask,
    page: Page,
    view_mode: str,
    extra_urls_settings: dict | None = None,
) -> tuple[int, Locator]:
    """Seed the member's view mode, log in, and return the first URL's id and row."""
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    set_member_settings(
        app,
        utub_id,
        USER_ID_FOR_TEST,
        {"urls": {"view_mode": view_mode, **(extra_urls_settings or {})}},
    )
    utub_url_id = get_url_in_utub(app, utub_id).id
    if is_mobile_viewport(page=page):
        login_user_and_select_utub_by_utubid_mobile(
            app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
        )
    else:
        login_user_and_select_utub_by_utubid(
            app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
        )
    row = page.locator(get_css_selector_for_url_by_id(url_id=utub_url_id))
    expect(row).to_be_visible()
    expect(page.locator("body")).to_have_attribute("data-view", view_mode)
    return utub_url_id, row


@pytest.fixture
def viewport_page(request: pytest.FixtureRequest) -> Page:
    """The desktop or mobile-portrait page, per the indirect ``viewport_page``
    parametrization. Tests list it BEFORE ``create_test_urls`` so the page's
    database setup runs first, like every test that takes ``page`` directly."""
    fixture_name = "page" if request.param == "desktop" else "page_mobile_portrait"
    return request.getfixturevalue(fixture_name)


def is_mobile_viewport(*, page: Page) -> bool:
    viewport = page.viewport_size
    return viewport is not None and viewport["width"] < MOBILE_MAX_WIDTH_PX


def _height(locator: Locator) -> float:
    box = locator.bounding_box()
    assert box is not None
    return box["height"]


def _rect(locator: Locator) -> dict | None:
    return locator.evaluate(_VISIBLE_RECT_JS)


def _intersects(first: dict, second: dict) -> bool:
    return (
        first["left"] < second["right"]
        and second["left"] < first["right"]
        and first["top"] < second["bottom"]
        and second["top"] < first["bottom"]
    )


@pytest.mark.parametrize("viewport_page", VIEWPORTS, indirect=True)
def test_title_line_collapsed_row_shows_only_title_on_one_short_line(
    viewport_page: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a member whose URL view is Title line
    WHEN the deck loads
    THEN an unselected row hides the URL, shows the title on a single line, and is
        no taller than 36px
    """
    _, row = _prepare(
        app=provide_app,
        page=viewport_page,
        view_mode="title_line",
    )

    expect(row.locator(HPL.URL_STRING_READ)).to_be_hidden()
    title = row.locator(HPL.URL_TITLE_READ)
    expect(title).to_be_visible()
    wait_for_css_transitions_to_finish(locator=row)
    assert _height(row) <= MAX_COLLAPSED_ROW_HEIGHT_PX
    line_height = title.evaluate("(el) => parseFloat(getComputedStyle(el).lineHeight)")
    assert _height(title) <= line_height * 1.2


@pytest.mark.parametrize("viewport_page", VIEWPORTS, indirect=True)
def test_url_line_collapsed_row_shows_only_url_on_one_short_line(
    viewport_page: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a member whose URL view is URL line
    WHEN the deck loads
    THEN an unselected row hides the title, shows the URL, and is no taller than 36px
    """
    _, row = _prepare(
        app=provide_app,
        page=viewport_page,
        view_mode="url_line",
    )

    expect(row.locator(HPL.URL_TITLE_READ)).to_be_hidden()
    expect(row.locator(HPL.URL_STRING_READ)).to_be_visible()
    wait_for_css_transitions_to_finish(locator=row)
    assert _height(row) <= MAX_COLLAPSED_ROW_HEIGHT_PX


@pytest.mark.parametrize("view_mode", LINE_MODES)
@pytest.mark.parametrize("viewport_page", VIEWPORTS, indirect=True)
def test_selecting_a_line_row_expands_it_like_list(
    viewport_page: Page,
    create_test_urls,
    provide_app: Flask,
    view_mode: str,
):
    """
    GIVEN a collapsed Title line or URL line row
    WHEN the user selects it
    THEN the title, URL, tags, buttons and the stacked "Added by" badge all show,
        and the row is as tall as a selected List row (within 2px)
    """
    page = viewport_page
    utub_url_id, row = _prepare(
        app=provide_app,
        page=page,
        view_mode=view_mode,
    )

    wait_then_click_element(
        page=page, css_selector=get_css_selector_for_url_by_id(url_id=utub_url_id)
    )
    expect(row).to_have_attribute("urlselected", "true")
    expect(row.locator(HPL.URL_TITLE_READ)).to_be_visible()
    expect(row.locator(HPL.URL_STRING_READ)).to_be_visible()
    expect(row.locator(HPL.URL_TAGS_CONTAINER)).to_be_attached()
    expect(row.locator(".urlOptions")).to_be_visible()
    expect(row.locator(HPL.URL_DATE_ADDED_BADGE_STACKED)).to_be_visible()
    wait_for_css_transitions_to_finish(locator=row)
    line_selected_height = _height(row)

    page.evaluate("() => { document.body.dataset.view = 'list'; }")
    wait_for_css_transitions_to_finish(locator=row)
    list_selected_height = _height(row)

    assert (
        abs(line_selected_height - list_selected_height) <= SELECTED_HEIGHT_TOLERANCE_PX
    )


@pytest.mark.parametrize("view_mode", LINE_MODES)
def test_keyboard_focused_line_row_has_a_two_pixel_outline(
    page: Page, create_test_urls, provide_app: Flask, view_mode: str
):
    """
    GIVEN a collapsed line row
    WHEN it takes keyboard focus
    THEN it shows a 2px outline instead of the 1px border
    """
    _, row = _prepare(app=provide_app, page=page, view_mode=view_mode)

    row.focus()
    expect(row).to_be_focused()

    expect(row).to_have_css("outline-width", "2px")
    expect(row).to_have_css("outline-style", "solid")


@pytest.mark.parametrize("view_mode", LINE_MODES)
def test_compact_density_does_not_change_line_row_padding(
    page: Page, create_test_urls, provide_app: Flask, view_mode: str
):
    """
    GIVEN a line view with Density set to compact
    WHEN the deck loads
    THEN a collapsed row's vertical padding stays 3px
    """
    _, row = _prepare(
        app=provide_app,
        page=page,
        view_mode=view_mode,
        extra_urls_settings={"density": "compact"},
    )

    content = row.locator(".urlRowContent")
    expect(page.locator("body")).to_have_attribute("data-density", "compact")
    expect(content).to_have_css("padding-top", LINE_ROW_PADDING)
    expect(content).to_have_css("padding-bottom", LINE_ROW_PADDING)


@pytest.mark.parametrize("view_mode", LINE_MODES)
def test_line_row_truncated_text_has_a_tooltip_until_selected(
    page: Page, create_test_urls, provide_app: Flask, view_mode: str
):
    """
    GIVEN a collapsed line row
    WHEN it is unselected, then selected
    THEN the title and URL carry the full text as a title attribute only while
        unselected
    """
    utub_url_id, row = _prepare(app=provide_app, page=page, view_mode=view_mode)
    title = row.locator(HPL.URL_TITLE_READ)
    url_string = row.locator(HPL.URL_STRING_READ)

    expect(title).to_have_attribute("title", title.text_content() or "")
    expect(url_string).to_have_attribute(
        "title", url_string.get_attribute("href") or ""
    )

    wait_then_click_element(
        page=page, css_selector=get_css_selector_for_url_by_id(url_id=utub_url_id)
    )
    expect(row).to_have_attribute("urlselected", "true")
    expect(title).not_to_have_attribute("title", re.compile(".*"))
    expect(url_string).not_to_have_attribute("title", re.compile(".*"))


@pytest.mark.parametrize("view_mode", LINE_MODES)
def test_tag_drop_hint_does_not_overlap_line_row_text(
    page: Page, create_test_urls, provide_app: Flask, view_mode: str
):
    """
    GIVEN a collapsed line row on desktop
    WHEN a tag drop hint is set on it
    THEN the hint sits inside the row's height and the row's text and date end
        before the space reserved for it
    """
    _, row = _prepare(app=provide_app, page=page, view_mode=view_mode)

    row.evaluate(
        "(el) => el.setAttribute('data-drop-hint', 'Add \"a rather long tag\" to this URL')"
    )
    # .urlRowContent animates its padding, so measure once the reservation settled.
    wait_for_css_transitions_to_finish(locator=row)
    reserved_left = row.evaluate(
        """(el) => {
            const rootFontSize = parseFloat(
                getComputedStyle(document.documentElement).fontSize
            );
            // The hint is right: 14px and clamped to 14rem.
            return el.getBoundingClientRect().right - 14 - 14 * rootFontSize;
        }"""
    )
    for selector in (
        HPL.URL_TITLE_READ,
        HPL.URL_STRING_READ,
        HPL.URL_DATE_ADDED_BADGE_INLINE,
    ):
        rect = _rect(row.locator(selector).first)
        if rect is not None:
            assert rect["right"] <= reserved_left
    assert _height(row) <= MAX_COLLAPSED_ROW_HEIGHT_PX


@pytest.mark.parametrize("view_mode", LINE_MODES)
def test_bulk_result_cue_does_not_overlap_line_row_text(
    page: Page, create_test_urls, provide_app: Flask, view_mode: str
):
    """
    GIVEN a collapsed line row
    WHEN a bulk result cue is added to it
    THEN the cue stays within the row and never intersects its text or date
    """
    _, row = _prepare(app=provide_app, page=page, view_mode=view_mode)

    row.evaluate(
        """(el) => {
            const cue = document.createElement('span');
            cue.className = 'bulkCardResultCue bulkCardResultCue--applied';
            cue.setAttribute('aria-hidden', 'true');
            cue.textContent = 'At tag limit';
            el.appendChild(cue);
        }"""
    )
    # .urlRowContent animates its padding, so measure once the reservation settled.
    wait_for_css_transitions_to_finish(locator=row)
    cue_rect = _rect(row.locator(".bulkCardResultCue"))
    row_rect = _rect(row)
    assert cue_rect is not None and row_rect is not None
    assert cue_rect["top"] >= row_rect["top"]
    assert cue_rect["bottom"] <= row_rect["bottom"]
    for selector in (
        HPL.URL_TITLE_READ,
        HPL.URL_STRING_READ,
        HPL.URL_DATE_ADDED_BADGE_INLINE,
    ):
        rect = _rect(row.locator(selector).first)
        if rect is not None:
            assert not _intersects(cue_rect, rect)


@pytest.mark.parametrize("view_mode", LINE_MODES)
def test_multi_select_checkbox_fits_in_a_line_row(
    page: Page, create_test_urls, provide_app: Flask, view_mode: str
):
    """
    GIVEN a collapsed line row in multi-select mode
    WHEN the checkbox column shows
    THEN the 24px checkbox fits inside the row
    """
    _, row = _prepare(app=provide_app, page=page, view_mode=view_mode)

    page.evaluate(
        "() => document.querySelector('#URLDeck').classList.add('multiSelectActive')"
    )
    checkbox_rect = _rect(row.locator(".urlSelectCheckbox"))
    row_rect = _rect(row)
    assert checkbox_rect is not None and row_rect is not None
    assert checkbox_rect["top"] >= row_rect["top"]
    assert checkbox_rect["bottom"] <= row_rect["bottom"]


@pytest.mark.mobile_ui
@pytest.mark.parametrize("view_mode", LINE_MODES)
def test_swipe_reveal_icon_fits_inside_a_line_row(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask, view_mode: str
):
    """
    GIVEN a collapsed line row on mobile
    WHEN its delete reveal is laid out behind it
    THEN the reveal icon's box sits inside the row's box (not clipped)
    """
    _, row = _prepare(
        app=provide_app,
        page=page_mobile_portrait,
        view_mode=view_mode,
    )

    icon_rect = _rect(row.locator(".urlRowSwipeRevealIcon"))
    row_rect = _rect(row)
    assert icon_rect is not None and row_rect is not None
    assert icon_rect["top"] >= row_rect["top"]
    assert icon_rect["bottom"] <= row_rect["bottom"]
