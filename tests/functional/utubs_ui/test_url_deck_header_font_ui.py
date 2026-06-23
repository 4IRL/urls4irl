from flask import Flask
import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.db_utils import (
    get_utub_this_user_created,
    update_utub_name_and_description,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_and_select_utub_by_name
from tests.functional.selenium_utils import (
    wait_then_get_element,
    wait_until_utub_name_appears,
    wait_until_visible_css_selector,
)
from tests.functional.utubs_ui.selenium_utils import (
    open_update_utub_desc_input,
    open_update_utub_name_input,
)

pytestmark = pytest.mark.utubs_ui


def _scroll_height_within_client_height(browser: WebDriver, element) -> bool:
    """True when the element is fully visible (no clipped overflow)."""
    return browser.execute_script(
        "return arguments[0].scrollHeight <= arguments[0].clientHeight + 1;",
        element,
    )


def _single_line_height(browser: WebDriver, element) -> int:
    """Return the rendered clientHeight (px) of the element."""
    return browser.execute_script("return arguments[0].clientHeight;", element)


def _parse_font_px(css_value: str) -> int:
    """Parse a CSS font-size string (e.g. ``"32px"`` or ``"32.00px"``) to int px."""
    return int(float(css_value.rstrip("px")))


def _computed_line_height_px(browser: WebDriver, element) -> float:
    """Return the element's computed single-line height in px.

    Reads ``getComputedStyle(element).lineHeight``. When the browser reports
    the keyword ``"normal"`` (no explicit line-height resolved to a length),
    falls back to measuring the actual rendered height of a single line by
    cloning the element, forcing its content to one short line, and reading
    the clone's ``clientHeight``. This keeps the test robust to stylesheet
    line-height changes instead of assuming a fixed multiple of the font size.
    """
    return browser.execute_script(
        """
        const element = arguments[0];
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
        """,
        element,
    )


def test_url_deck_header_and_subheader_render_at_max_font_when_short(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id, UI_TEST_STRINGS.SHORT_FIT_UTUB_NAME
    )
    wait_until_utub_name_appears(browser, UI_TEST_STRINGS.SHORT_FIT_UTUB_NAME)

    header = wait_then_get_element(browser, HPL.HEADER_URL_DECK)
    subheader = wait_then_get_element(browser, HPL.SUBHEADER_URL_DECK)
    assert header is not None
    assert subheader is not None

    assert (
        _parse_font_px(header.value_of_css_property("font-size"))
        == UI_TEST_STRINGS.TITLE_MAX_FONT_PX
    )
    assert (
        _parse_font_px(subheader.value_of_css_property("font-size"))
        == UI_TEST_STRINGS.DESC_MAX_FONT_PX
    )

    # Short text fits on a single line, so it is never clipped.
    assert _scroll_height_within_client_height(browser, subheader)


def test_url_deck_header_and_subheader_shrink_and_wrap_when_long(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id, UI_TEST_STRINGS.LONG_FIT_UTUB_NAME
    )
    wait_until_utub_name_appears(browser, UI_TEST_STRINGS.LONG_FIT_UTUB_NAME)

    header = wait_then_get_element(browser, HPL.HEADER_URL_DECK)
    subheader = wait_then_get_element(browser, HPL.SUBHEADER_URL_DECK)
    assert header is not None
    assert subheader is not None

    # 1. Description clamps to its minimum font; the 30-char title shrinks into
    #    the [min, max] range (it may or may not hit min depending on its width).
    assert (
        _parse_font_px(subheader.value_of_css_property("font-size"))
        == UI_TEST_STRINGS.DESC_MIN_FONT_PX
    )
    header_font_px = _parse_font_px(header.value_of_css_property("font-size"))
    assert UI_TEST_STRINGS.TITLE_MIN_FONT_PX <= header_font_px
    assert header_font_px <= UI_TEST_STRINGS.TITLE_MAX_FONT_PX

    # 2. Not truncated: the full text is present (no ellipsis substitution).
    assert header.text == UI_TEST_STRINGS.LONG_FIT_UTUB_NAME
    assert subheader.text == UI_TEST_STRINGS.LONG_FIT_UTUB_DESCRIPTION

    # 3. Wrapped / fully visible: nothing clipped, and the description spans more
    #    than a single line.
    assert _scroll_height_within_client_height(browser, subheader)
    single_desc_line_px = _computed_line_height_px(browser, subheader)
    assert _single_line_height(browser, subheader) > single_desc_line_px


def test_url_deck_header_edit_still_opens_after_font_fit(
    browser: WebDriver, create_test_utubs, provide_app: Flask
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
        app, browser, user_id, UI_TEST_STRINGS.LONG_FIT_UTUB_NAME
    )
    wait_until_utub_name_appears(browser, UI_TEST_STRINGS.LONG_FIT_UTUB_NAME)

    open_update_utub_name_input(browser)
    wait_until_visible_css_selector(browser, HPL.INPUT_UTUB_NAME_UPDATE, timeout=3)
    name_input = wait_then_get_element(browser, HPL.INPUT_UTUB_NAME_UPDATE)
    assert name_input is not None
    assert name_input.is_displayed()

    open_update_utub_desc_input(browser)
    wait_until_visible_css_selector(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE, timeout=3
    )
    desc_input = wait_then_get_element(browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE)
    assert desc_input is not None
    assert desc_input.is_displayed()
