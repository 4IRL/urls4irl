import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, expect

from tests.functional.db_utils import (
    add_url_to_utub_as_other_member,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_not_visible_css_selector
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    wait_then_click_element,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.urls_ui

# Utub_Urls.url_title is String(140). A long run of wide glyphs plus a
# space-separated tail overflows one line at the default desktop width and at
# 390px (the run alone exceeds the card, so an unwrapped token is clipped), while
# the spaces give a drag-selection real word boundaries.
LONG_TITLE_UNBROKEN_RUN = "W" * 110
LONG_URL_TITLE = f"{LONG_TITLE_UNBROKEN_RUN} lorem ipsum dolor sit amet"
LONG_TITLE_URL_STRING = "https://long-title.example.com/path"
USER_ID_FOR_TEST = 1

assert len(LONG_URL_TITLE) <= 140


def _seed_long_title_url(*, app: Flask) -> tuple[int, int]:
    """Seed a URL with a long title in the user's own UTub. Returns
    (utub_id, utub_url_id)."""
    utub = get_utub_this_user_created(app, user_id=USER_ID_FOR_TEST)
    utub_url_id = add_url_to_utub_as_other_member(
        app, utub.id, USER_ID_FOR_TEST, LONG_TITLE_URL_STRING, LONG_URL_TITLE
    )
    return utub.id, utub_url_id


def _wait_until_layout_stable(locator: Locator) -> None:
    """Resolve once the element's rect is unchanged for several animation frames
    (the selected card animates open, so an early rect is stale)."""
    locator.evaluate(
        """el => new Promise(resolve => {
            let last = "";
            let stableFrames = 0;
            const tick = () => {
                const rect = el.getBoundingClientRect();
                const key = [rect.x, rect.y, rect.width, rect.height].join();
                stableFrames = key === last ? stableFrames + 1 : 0;
                last = key;
                if (stableFrames >= 5) resolve(true);
                else requestAnimationFrame(tick);
            };
            tick();
        })"""
    )


def _overflow_metrics(title: Locator) -> dict[str, float]:
    return title.evaluate(
        """el => ({
            scrollWidth: el.scrollWidth,
            clientWidth: el.clientWidth,
            right: el.getBoundingClientRect().right,
            rowRight: el.closest('.urlRow').getBoundingClientRect().right,
        })"""
    )


def _assert_selected_title_wraps(*, page: Page, utub_url_id: int) -> None:
    row_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"

    # Precondition: unselected, the title is clipped with an ellipsis.
    unselected_title = page.locator(f"{row_selector} {HPL.URL_TITLE_READ}").first
    wait_until_visible_css_selector(
        page=page, css_selector=f"{row_selector} {HPL.URL_TITLE_READ}"
    )
    unselected = _overflow_metrics(unselected_title)
    assert unselected["scrollWidth"] > unselected["clientWidth"]

    wait_then_click_element(page=page, css_selector=row_selector)
    selected_row = f"{row_selector}[urlselected='true']"
    wait_until_visible_css_selector(page=page, css_selector=selected_row)

    title = page.locator(f"{selected_row} {HPL.URL_TITLE_READ}").first
    expect(title).to_have_css("white-space", "normal")

    _wait_until_layout_stable(title)
    metrics = _overflow_metrics(title)
    assert metrics["scrollWidth"] <= metrics["clientWidth"] + 1
    assert metrics["right"] <= metrics["rowRight"] + 1

    # The long title spans more than one line.
    line_count = title.evaluate(
        "el => el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight)"
    )
    assert line_count > 1.5


def test_selected_url_title_wraps_desktop(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a URL whose title is longer than one line
    WHEN the card is selected on desktop
    THEN the full title wraps inside the card instead of being clipped
    """
    app = provide_app
    utub_id, utub_url_id = _seed_long_title_url(app=app)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )

    _assert_selected_title_wraps(page=page, utub_url_id=utub_url_id)


@pytest.mark.mobile_ui
def test_selected_url_title_wraps_mobile(
    page_mobile_portrait: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a URL whose title is longer than one line
    WHEN the card is selected on a touch device
    THEN the full title wraps inside the card instead of being clipped
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id, utub_url_id = _seed_long_title_url(app=app)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )

    _assert_selected_title_wraps(page=page, utub_url_id=utub_url_id)


@pytest.mark.mobile_ui
def test_selected_url_title_not_underlined_while_pressed_mobile(
    page_mobile_portrait: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a selected URL card on a touch device
    WHEN the title is pressed (:active)
    THEN the title is not underlined (the edit affordance is desktop-only)
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id, utub_url_id = _seed_long_title_url(app=app)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )

    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    )
    title_selector = f"{HPL.ROW_SELECTED_URL} {HPL.URL_TITLE_READ}"
    wait_until_visible_css_selector(page=page, css_selector=title_selector)
    title = page.locator(title_selector).first

    box = title.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    try:
        expect(title).to_have_css("text-decoration-line", "none")
    finally:
        page.mouse.up()


def test_selecting_url_title_text_does_not_open_edit_form(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a selected URL card with a long title on desktop
    WHEN the user drag-selects the title text
    THEN the edit form does not open, but a plain click still opens it
    """
    app = provide_app
    utub_id, utub_url_id = _seed_long_title_url(app=app)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )

    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
    )
    title_selector = f"{HPL.ROW_SELECTED_URL} {HPL.URL_TITLE_READ}"
    wait_until_visible_css_selector(page=page, css_selector=title_selector)
    title = page.locator(title_selector).first

    _wait_until_layout_stable(title)
    box = title.bounding_box()
    assert box is not None
    y_mid = box["y"] + box["height"] / 4  # inside the first of >= 2 lines
    page.mouse.move(box["x"] + 1, y_mid)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.6, y_mid, steps=8)
    page.mouse.up()

    # Text is selected and stays selected (opening the form would focus its input
    # and drop the selection), which also makes the visibility check falsifiable.
    assert page.evaluate("window.getSelection().toString()") != ""

    input_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}"
    assert_not_visible_css_selector(page=page, css_selector=input_selector)

    # A plain click (its mousedown collapses the selection) still opens the form.
    title.click()
    wait_until_visible_css_selector(page=page, css_selector=input_selector)
