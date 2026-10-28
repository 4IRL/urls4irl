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
from tests.functional.urls_ui.playwright_utils import (
    get_url_row_selector,
    swipe_url_card_delete,
)

pytestmark = pytest.mark.urls_ui

USER_ID_FOR_TEST = 1
MAX_COLLAPSED_ROW_HEIGHT_PX = 36
SELECTED_HEIGHT_TOLERANCE_PX = 2
MOBILE_MAX_WIDTH_PX = 992
TABLET_VIEWPORT = {"width": 800, "height": 900}
GRID_WIDTH_TOLERANCE_PX = 2
LONG_URL = "https://example.com/" + "a-very-long-path-segment/" * 12
SHORT_URL = "https://a.io"
LONG_TITLE = " ".join(["An exceedingly long bookmark title"] * 12)
SHORT_TITLE = "Short"
CARD_TEXT_SELECTORS = (
    HPL.URL_TITLE_READ,
    HPL.URL_STRING_READ,
    HPL.URL_DATE_ADDED_BADGE_INLINE,
)

# Resolves a design token (e.g. --selectedUrlBorder) to the browser-normalised
# rgb() string, so colour assertions are theme-agnostic.
_RESOLVE_TOKEN_COLOR_JS = """(token) => {
    const probe = document.createElement('span');
    probe.style.color = getComputedStyle(document.documentElement)
        .getPropertyValue(token);
    document.body.appendChild(probe);
    const normalized = getComputedStyle(probe).color;
    probe.remove();
    return normalized;
}"""

# The box of a row's absolutely-positioned ::after (the tag drop hint), derived
# from its computed size and offsets since a pseudo-element has no bounding rect.
_AFTER_RECT_JS = """(element) => {
    const row = element.getBoundingClientRect();
    const rowStyle = getComputedStyle(element);
    const after = getComputedStyle(element, '::after');
    const width = parseFloat(after.width);
    const height = parseFloat(after.height);
    const right = row.right - parseFloat(rowStyle.borderRightWidth) - parseFloat(after.right);
    const bottom = row.bottom - parseFloat(rowStyle.borderBottomWidth) - parseFloat(after.bottom);
    const rect = { left: right - width, right, top: bottom - height, bottom };
    return Object.values(rect).every(Number.isFinite) ? rect : null;
}"""

_GRID_CONTENT_WIDTH_JS = """(element) => {
    const style = getComputedStyle(element);
    return element.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
}"""
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


def _width(locator: Locator) -> float:
    box = locator.bounding_box()
    assert box is not None
    return box["width"]


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


def _prepare_cards(*, app: Flask, page: Page) -> Locator:
    """Load the deck in Cards at the desktop viewport; returns every card."""
    _prepare(app=app, page=page, view_mode="cards")
    page.mouse.move(0, 0)  # a hovered card would repaint its background
    rows = page.locator(HPL.ROWS_URLS)
    assert rows.count() >= 5
    return rows


def _set_title(*, row: Locator, text: str) -> None:
    row.locator(HPL.URL_TITLE_READ).evaluate(
        "(element, text) => { element.textContent = text; }", text
    )


def _resolve_token(*, page: Page, token: str) -> str:
    return page.evaluate(_RESOLVE_TOKEN_COLOR_JS, token)


def _grid_content_width(*, page: Page) -> float:
    return page.locator("#listURLs").evaluate(_GRID_CONTENT_WIDTH_JS)


def _assert_no_overlap_with_card_text(*, row: Locator, overlay: dict) -> None:
    for selector in CARD_TEXT_SELECTORS:
        rect = _rect(row.locator(selector).first)
        if rect is not None:
            assert not _intersects(overlay, rect), selector


def test_cards_are_top_aligned_boxes_that_never_stretch(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the Cards view at desktop width with one very long and one short title
        sharing a grid row
    WHEN nothing is selected
    THEN every unselected card has the same height (a fixed card size, neither
        stretched nor sized by its text), both tops match, and no red swipe
        layer shows
    """
    rows = _prepare_cards(app=provide_app, page=page)
    long_card, short_card = rows.nth(0), rows.nth(1)
    _set_title(row=long_card, text=LONG_TITLE)
    _set_title(row=short_card, text=SHORT_TITLE)
    long_card.locator(HPL.URL_STRING_READ).evaluate(
        "(element, text) => { element.textContent = text; }", LONG_URL
    )
    short_card.locator(HPL.URL_STRING_READ).evaluate(
        "(element, text) => { element.textContent = text; }", SHORT_URL
    )
    wait_for_css_transitions_to_finish(locator=long_card)

    assert abs(_rect(long_card)["top"] - _rect(short_card)["top"]) <= 1
    heights = {round(_height(rows.nth(index)), 1) for index in range(rows.count())}
    assert len(heights) == 1, heights
    # The fixed height still holds the clamped title, URL and date.
    long_content = long_card.locator(".urlRowContent")
    assert long_content.evaluate("(el) => el.scrollHeight <= el.clientHeight + 1")
    assert page.locator(".urlRowSwipeReveal").count() > 0  # else the check is vacuous
    visible_reveals = page.evaluate(
        """() => Array.from(document.querySelectorAll('.urlRowSwipeReveal'))
            .filter((element) => element.getClientRects().length > 0).length"""
    )
    assert visible_reveals == 0


def test_unselected_cards_share_one_background(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the Cards view at desktop width
    WHEN nothing is selected
    THEN even and odd cards have the same background colour (striping is off)
    """
    rows = _prepare_cards(app=provide_app, page=page)
    for index in range(rows.count()):
        wait_for_css_transitions_to_finish(locator=rows.nth(index))

    backgrounds = page.evaluate(
        """() => Array.from(document.querySelectorAll('.urlRow'))
            .map((element) => getComputedStyle(element).backgroundColor)"""
    )
    assert len(set(backgrounds)) == 1


@pytest.mark.parametrize("hide_buttons", [False, True], ids=["buttons", "hidden"])
def test_selected_card_spans_the_row_without_overlap(
    page: Page, create_test_urls, provide_app: Flask, hide_buttons: bool
):
    """
    GIVEN the Cards view at desktop width, with the copy and short-link buttons
        shown or hidden
    WHEN a card is selected
    THEN it spans the grid row, its selected border shows on all four sides, and
        the "Added by" badge sits below the buttons without touching them
    """
    rows = _prepare_cards(app=provide_app, page=page)
    if hide_buttons:
        page.evaluate(
            """() => {
                const deck = document.querySelector('#URLDeck');
                deck.setAttribute('data-hide-copy', 'true');
                deck.setAttribute('data-hide-short-link', 'true');
            }"""
        )
    card = rows.nth(1)
    card.click()
    expect(card).to_have_attribute("urlselected", "true")
    wait_for_css_transitions_to_finish(locator=card)

    assert abs(_width(card) - _grid_content_width(page=page)) <= GRID_WIDTH_TOLERANCE_PX
    options = _rect(card.locator(".urlOptions"))
    badge = _rect(card.locator(HPL.URL_DATE_ADDED_BADGE_STACKED))
    assert options is not None and badge is not None
    assert not _intersects(options, badge)
    assert badge["top"] >= options["bottom"]
    selected_border = _resolve_token(page=page, token="--selectedUrlBorder")
    for side in ("top", "right", "bottom", "left"):
        expect(card).to_have_css(f"border-{side}-color", selected_border)


def test_tag_drop_hint_and_bulk_cue_do_not_overlap_card_text(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN an unselected card at desktop width
    WHEN a tag drop hint is set, and separately a bulk result cue is added
    THEN the overlay's box never intersects the title, URL or date text
    """
    rows = _prepare_cards(app=provide_app, page=page)
    card = rows.nth(1)

    card.evaluate(
        "(el) => el.setAttribute('data-drop-hint', 'Add \"a rather long tag\" to this URL')"
    )
    wait_for_css_transitions_to_finish(locator=card)
    hint_rect = card.evaluate(_AFTER_RECT_JS)
    assert hint_rect is not None
    _assert_no_overlap_with_card_text(row=card, overlay=hint_rect)

    card.evaluate("(el) => el.removeAttribute('data-drop-hint')")
    card.evaluate(
        """(el) => {
            const cue = document.createElement('span');
            cue.className = 'bulkCardResultCue bulkCardResultCue--applied';
            cue.setAttribute('aria-hidden', 'true');
            cue.textContent = 'At tag limit';
            el.appendChild(cue);
        }"""
    )
    wait_for_css_transitions_to_finish(locator=card)
    cue_rect = _rect(card.locator(".bulkCardResultCue"))
    assert cue_rect is not None
    _assert_no_overlap_with_card_text(row=card, overlay=cue_rect)


def test_keyboard_focused_card_shows_only_a_two_pixel_outline(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN an unselected card at desktop width
    WHEN it takes keyboard focus
    THEN it shows a 2px selection-green outline and matching top and bottom borders
    """
    rows = _prepare_cards(app=provide_app, page=page)
    card = rows.nth(1)

    card.focus()
    expect(card).to_be_focused()

    expect(card).to_have_css("outline-width", "2px")
    expect(card).to_have_css("outline-style", "solid")
    expect(card).to_have_css(
        "outline-color", _resolve_token(page=page, token="--deckSelectionGreen")
    )
    border_color = _resolve_token(page=page, token="--borderColor")
    for side in ("top", "bottom"):
        expect(card).to_have_css(f"border-{side}-color", border_color)
        expect(card).to_have_css(f"border-{side}-width", "1px")


def test_create_url_form_and_error_banner_span_the_grid(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the Cards view at desktop width
    WHEN the create-URL form is opened
    THEN the form is as wide as the grid, and the form and the error banner both
        occupy every grid column
    """
    _prepare_cards(app=provide_app, page=page)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)
    form = page.locator(HPL.WRAP_URL_CREATE)
    expect(form).to_be_visible()

    assert abs(_width(form) - _grid_content_width(page=page)) <= GRID_WIDTH_TOLERANCE_PX
    expect(form).to_have_css("grid-column-end", "-1")
    expect(page.locator(HPL.URL_DECK_ERROR_INDICATOR)).to_have_css(
        "grid-column-end", "-1"
    )


def test_multi_select_card_shows_checkbox_and_title_inside_the_card(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the Cards view at desktop width in multi-select mode
    WHEN a card shows its checkbox column
    THEN the checkbox and title are visible and the title stays inside the card
    """
    rows = _prepare_cards(app=provide_app, page=page)
    page.evaluate(
        "() => document.querySelector('#URLDeck').classList.add('multiSelectActive')"
    )
    card = rows.nth(1)

    expect(card.locator(HPL.URL_SELECT_CHECKBOX)).to_be_visible()
    expect(card.locator(HPL.URL_TITLE_READ)).to_be_visible()
    title_rect, card_rect = _rect(card.locator(HPL.URL_TITLE_READ)), _rect(card)
    assert title_rect is not None and card_rect is not None
    assert title_rect["right"] <= card_rect["right"]
    assert _width(card) <= 400  # the narrow card column is really exercised


@pytest.mark.mobile_ui
@pytest.mark.parametrize("view_mode", ["list", "title_line"])
def test_selected_row_badge_does_not_overlap_buttons_at_tablet_width(
    page: Page, create_test_urls, provide_app: Flask, view_mode: str
):
    """
    GIVEN a List or Title line row at 800px
    WHEN the row is selected
    THEN the "Added by" badge flows below the buttons instead of overlapping them
    """
    page.set_viewport_size(TABLET_VIEWPORT)
    utub_url_id, row = _prepare(app=provide_app, page=page, view_mode=view_mode)

    wait_then_click_element(
        page=page, css_selector=get_css_selector_for_url_by_id(url_id=utub_url_id)
    )
    expect(row).to_have_attribute("urlselected", "true")
    wait_for_css_transitions_to_finish(locator=row)

    options = _rect(row.locator(".urlOptions"))
    badge = _rect(row.locator(HPL.URL_DATE_ADDED_BADGE_STACKED))
    assert options is not None and badge is not None
    assert not _intersects(options, badge)
    assert badge["top"] >= options["bottom"]


def test_selected_list_row_keeps_the_corner_badge_on_desktop(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a List row at desktop width
    WHEN the row is selected
    THEN the "Added by" badge is still the absolute bottom-right one
    """
    utub_url_id, row = _prepare(app=provide_app, page=page, view_mode="list")

    wait_then_click_element(
        page=page, css_selector=get_css_selector_for_url_by_id(url_id=utub_url_id)
    )
    expect(row).to_have_attribute("urlselected", "true")

    expect(row.locator(HPL.URL_DATE_ADDED_BADGE_STACKED)).to_have_css(
        "position", "absolute"
    )


@pytest.mark.mobile_ui
def test_cards_preference_renders_as_list_on_a_phone_and_still_swipes(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a Cards preference at 420px
    WHEN the deck loads
    THEN it is not a grid, rows have no radius, and swipe-to-delete still works
    """
    page = page_mobile_portrait
    utub_url_id, row = _prepare(app=provide_app, page=page, view_mode="cards")

    expect(page.locator("#listURLs")).not_to_have_css("display", "grid")
    expect(row).to_have_css("border-top-left-radius", "0px")

    row_selector = get_url_row_selector(utub_url_id=utub_url_id)
    swipe_url_card_delete(page=page, url_row_selector=row_selector)
    expect(page.locator(HPL.URL_OUTCOME_BANNER)).to_be_visible()
    expect(page.locator(row_selector)).to_have_count(0)
