import re
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Generator

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect

from backend.models.utubs import Utubs
from backend.utils.datetime_utils import utc_now
from tests.functional.db_utils import add_url_to_utub_as_other_member
from tests.functional.invite_links_ui.db_utils import mint_invite_link_in_db
from tests.functional.locators import InvitePageLocators as IPL
from tests.functional.playwright_utils import (
    PageBundle,
    current_base_url,
)
from tests.functional.playwright_utils import (
    add_cookie_banner_cookie as add_playwright_cookie_banner_cookie,
)

pytestmark = pytest.mark.invite_links_ui

CREATOR_ID = 1
TAB_PRESS_LIMIT = 20
TOLERANCE_PX = 1
DESKTOP_WIDE = {"width": 1280, "height": 800}
DESKTOP_NARROW = {"width": 800, "height": 800}
MOBILE = {"width": 390, "height": 844}
SHORT = {"width": 667, "height": 375}
MIN_TOUCH_TARGET_PX = 44
MIN_CONTRAST = 4.5
BANNER_VISIBLE = re.compile(r"(^|\s)is-visible(\s|$)")
LONG_TITLE = "T" * 140  # urlTitle is String(140)
LONG_URL = "https://example.com/" + "a" * 200
NON_WEB_URLS = ("ftp://files.example.com/one", "ftp://files.example.com/two")
NO_JS_BODY_PADDING = "144px"  # 9rem static fallback at a 16px root
GET_RECTS_JS = """() => {
    const rect = (selector) => {
        const el = document.querySelector(selector);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { top: r.top, bottom: r.bottom, left: r.left, right: r.right };
    };
    return {
        bar: rect('#invitePreviewBar'),
        banner: rect('#CookieBanner'),
        viewport: window.innerHeight,
    };
}"""
BAR_ABOVE_BANNER_JS = """(tolerance) => {
    const bar = document.querySelector('#invitePreviewBar').getBoundingClientRect();
    const banner = document.querySelector('#CookieBanner').getBoundingClientRect();
    return bar.bottom <= banner.top + tolerance;
}"""
BAR_AT_BOTTOM_JS = """(tolerance) => {
    const bar = document.querySelector('#invitePreviewBar').getBoundingClientRect();
    return Math.abs(bar.bottom - window.innerHeight) <= tolerance;
}"""
# `instant`: the page's smooth scroll would otherwise leave a mid-animation read.
SCROLL_BOTTOM_JS = """() => window.scrollTo({
    top: document.documentElement.scrollHeight, behavior: 'instant'
})"""
AT_BOTTOM_JS = """() => {
    const el = document.scrollingElement;
    return el.scrollTop > 0 && el.scrollTop + el.clientHeight >= el.scrollHeight - 1;
}"""
POLL_INTERVAL_MS = 50
ACTIVE_MATCHES_JS = "(selector) => document.activeElement?.matches(selector) ?? false"
CONTRAST_JS = """(el) => {
    const parse = (color) => color.match(/[\\d.]+/g).slice(0, 3).map(Number);
    const channel = (value) => {
        const scaled = value / 255;
        return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4;
    };
    const luminance = ([red, green, blue]) =>
        0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue);
    const fg = luminance(parse(getComputedStyle(el).color));
    const bg = luminance(parse(getComputedStyle(el.closest('li')).backgroundColor));
    return (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05);
}"""
SAFE_AREA_RULE_JS = """() => {
    for (const sheet of document.styleSheets) {
        let rules;
        try { rules = sheet.cssRules; } catch (e) { continue; }
        for (const rule of rules) {
            if (rule.selectorText === '#invitePreviewBar'
                && rule.style.paddingBottom.includes('env(safe-area-inset-bottom')) {
                return rule.style.paddingBottom;
            }
        }
    }
    return null;
}"""


def _creator_utub_id(app: Flask) -> int:
    """The lowest-id UTub user 1 created. Ordered: an unordered ``.first()`` can return
    a different UTub after a row update moves the tuple."""
    with app.app_context():
        utub = (
            Utubs.query.filter(Utubs.utub_creator == CREATOR_ID)
            .order_by(Utubs.id)
            .first()
        )
        assert utub is not None
        return utub.id


def _seed_preview(
    *, app: Flask, page_url_base: str, ends_in: timedelta = timedelta(days=2)
) -> str:
    """Mint a preview-enabled link for the UTub user 1 created; return its URL."""
    token = mint_invite_link_in_db(
        app=app,
        utub_id=_creator_utub_id(app),
        created_by=CREATOR_ID,
        preview_enabled=True,
        preview_ends_at=utc_now() + ends_in,
    )
    return f"{page_url_base}/invite/{token}"


def _seed_url(*, app: Flask, title: str, url: str) -> None:
    add_url_to_utub_as_other_member(app, _creator_utub_id(app), CREATOR_ID, url, title)


@contextmanager
def _visitor_page(
    *, browser: Browser, base_url: str, consent: bool = True, **context_options: Any
) -> Generator[Page, None, None]:
    context = browser.new_context(**context_options)
    try:
        context.set_default_timeout(10_000)
        context.set_default_navigation_timeout(30_000)
        if consent:
            add_playwright_cookie_banner_cookie(context=context, base_url=base_url)
        yield context.new_page()
    finally:
        context.close()


def _open_with_banner(*, bundle: PageBundle, app: Flask, viewport: dict) -> Page:
    page = bundle.page
    page.set_viewport_size(viewport)
    page.goto(_seed_preview(app=app, page_url_base=bundle.base_url))
    expect(page.locator(IPL.PREVIEW_BAR)).to_be_visible()
    expect(page.locator(IPL.COOKIE_BANNER)).to_have_class(BANNER_VISIBLE)
    return page


def _wait_bar_above_banner(*, page: Page) -> None:
    page.wait_for_function(BAR_ABOVE_BANNER_JS, arg=TOLERANCE_PX)


def _wait_bar_at_bottom(*, page: Page) -> None:
    page.wait_for_function(BAR_AT_BOTTOM_JS, arg=TOLERANCE_PX)


def _tab_until(
    *, page: Page, selector: str, limit: int = TAB_PRESS_LIMIT
) -> list[bool]:
    """Press Tab until ``selector`` is focused; return, per press, whether an
    ``a.invite-preview-url`` was focused."""
    anchors_focused: list[bool] = []
    for _ in range(limit):
        page.keyboard.press("Tab")
        anchors_focused.append(page.evaluate(ACTIVE_MATCHES_JS, IPL.PREVIEW_URL_ANCHOR))
        if page.evaluate(ACTIVE_MATCHES_JS, selector):
            return anchors_focused
    pytest.fail(f"{selector} not focused within {limit} Tab presses")


def _box(*, page: Page, selector: str) -> dict:
    box = page.locator(selector).bounding_box()
    assert box is not None, selector
    return box


def _wait_scrolled_to_bottom(*, page: Page, timeout_ms: int = 5000) -> None:
    """Poll until the page is scrolled to its max (evaluate works with JS disabled,
    unlike wait_for_function)."""
    deadline = time.monotonic() + timeout_ms / 1000
    while not page.evaluate(AT_BOTTOM_JS):
        assert time.monotonic() < deadline, "page never reached max scroll"
        page.wait_for_timeout(POLL_INTERVAL_MS)


def _assert_last_card_and_footer_above_bar(*, page: Page) -> None:
    page.evaluate(SCROLL_BOTTOM_JS)
    bar_top = _box(page=page, selector=IPL.PREVIEW_BAR)["y"]
    last_card = page.locator(IPL.PREVIEW_CARD).last.bounding_box()
    assert last_card is not None
    assert last_card["y"] + last_card["height"] <= bar_top + TOLERANCE_PX
    for selector in (IPL.PRIVACY_BTN, IPL.TERMS_BTN):
        box = _box(page=page, selector=selector)
        assert box["y"] + box["height"] <= bar_top + TOLERANCE_PX, selector


@pytest.mark.parametrize(
    "viewport", [DESKTOP_WIDE, DESKTOP_NARROW, MOBILE], ids=["1280", "800", "390"]
)
def test_bar_sits_above_visible_banner_then_drops_after_dismiss(
    page_without_cookie_banner_cookie: PageBundle,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
    viewport: dict,
):
    """
    GIVEN an anonymous visitor on a preview page whose cookie banner is visible
    WHEN the page settles, then the banner is dismissed
    THEN the bar sits above the banner at every width, then at the viewport bottom
    """
    page = _open_with_banner(
        bundle=page_without_cookie_banner_cookie, app=provide_app, viewport=viewport
    )
    _wait_bar_above_banner(page=page)

    page.locator(IPL.COOKIE_BANNER_BTN).click()
    expect(page.locator(IPL.COOKIE_BANNER)).not_to_have_class(BANNER_VISIBLE)
    _wait_bar_at_bottom(page=page)


def test_bar_at_bottom_without_banner(
    page: Page,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a visitor who already consented to cookies
    WHEN the preview page renders
    THEN the bar sits at the bottom of the viewport
    """
    page.goto(_seed_preview(app=provide_app, page_url_base=current_base_url(page=page)))
    expect(page.locator(IPL.PREVIEW_BAR)).to_be_visible()
    _wait_bar_at_bottom(page=page)


def test_reduced_motion_bar_tracks_banner_on_first_read(
    page: Page,
    build_page_browser: Browser,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a visitor who prefers reduced motion
    WHEN the banner is visible, then dismissed
    THEN the bar bottom equals the banner top, then the viewport bottom, on a
         single read
    """
    base_url = current_base_url(page=page)
    url = _seed_preview(app=provide_app, page_url_base=base_url)
    with _visitor_page(
        browser=build_page_browser,
        base_url=base_url,
        consent=False,
        viewport=DESKTOP_WIDE,
        reduced_motion="reduce",
    ) as visitor:
        visitor.goto(url)
        expect(visitor.locator(IPL.COOKIE_BANNER)).to_have_class(BANNER_VISIBLE)
        rects = visitor.evaluate(GET_RECTS_JS)
        assert abs(rects["bar"]["bottom"] - rects["banner"]["top"]) <= TOLERANCE_PX

        visitor.locator(IPL.COOKIE_BANNER_BTN).click()
        expect(visitor.locator(IPL.COOKIE_BANNER)).not_to_have_class(BANNER_VISIBLE)
        rects = visitor.evaluate(GET_RECTS_JS)
        assert abs(rects["bar"]["bottom"] - rects["viewport"]) <= TOLERANCE_PX


@pytest.mark.parametrize("viewport", [DESKTOP_WIDE, MOBILE], ids=["1280", "390"])
def test_last_card_and_footer_reachable_above_bar(
    page: Page,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
    viewport: dict,
):
    """
    GIVEN a preview page
    WHEN the visitor scrolls to the bottom
    THEN the last card and the Terms/Privacy links end above the bar
    """
    page.set_viewport_size(viewport)
    page.goto(_seed_preview(app=provide_app, page_url_base=current_base_url(page=page)))
    expect(page.locator(IPL.PREVIEW_BAR)).to_be_visible()
    _wait_bar_at_bottom(page=page)
    _assert_last_card_and_footer_above_bar(page=page)


def test_bar_stacks_below_768_and_shares_a_row_above(
    page: Page,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a preview page
    WHEN rendered at 390 and at 1280
    THEN the copy sits above full-width buttons at 390 and shares one row at 1280
    """
    page.goto(_seed_preview(app=provide_app, page_url_base=current_base_url(page=page)))

    page.set_viewport_size(MOBILE)
    text = _box(page=page, selector=IPL.PREVIEW_BAR_TEXT)
    actions = _box(page=page, selector=IPL.PREVIEW_BAR_ACTIONS)
    create = _box(page=page, selector=IPL.PREVIEW_BAR_CREATE_ACCOUNT)
    log_in = _box(page=page, selector=IPL.PREVIEW_BAR_LOG_IN)
    assert text["y"] + text["height"] <= actions["y"] + TOLERANCE_PX
    assert abs(create["y"] - log_in["y"]) <= TOLERANCE_PX
    assert create["x"] + create["width"] <= log_in["x"] + TOLERANCE_PX
    assert abs(create["x"] - actions["x"]) <= TOLERANCE_PX
    assert (
        abs(log_in["x"] + log_in["width"] - (actions["x"] + actions["width"]))
        <= TOLERANCE_PX
    )

    page.set_viewport_size(DESKTOP_WIDE)
    text = _box(page=page, selector=IPL.PREVIEW_BAR_TEXT)
    actions = _box(page=page, selector=IPL.PREVIEW_BAR_ACTIONS)
    assert text["x"] + text["width"] <= actions["x"] + TOLERANCE_PX
    assert text["y"] < actions["y"] + actions["height"]
    assert actions["y"] < text["y"] + text["height"]


def test_no_horizontal_overflow_with_long_unbroken_strings(
    page: Page,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a URL with a maximum-length unbroken title and a 200-character URL
    WHEN the preview renders at 390
    THEN the page has no horizontal overflow
    """
    _seed_url(app=provide_app, title=LONG_TITLE, url=LONG_URL)
    page.set_viewport_size(MOBILE)
    page.goto(_seed_preview(app=provide_app, page_url_base=current_base_url(page=page)))
    expect(page.locator(IPL.PREVIEW_URL_ANCHOR).first).to_be_visible()
    layout = page.evaluate(
        """() => ({
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
        })"""
    )
    assert layout["scrollWidth"] <= layout["clientWidth"], layout


def test_keyboard_focus_ring_on_preview_anchor(
    page: Page,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a preview page with 3-5 URLs
    WHEN the visitor tabs into the list
    THEN the first preview anchor is :focus-visible with a 3px outline
    """
    page.goto(_seed_preview(app=provide_app, page_url_base=current_base_url(page=page)))
    assert 3 <= page.locator(IPL.PREVIEW_CARD).count() <= 5
    _tab_until(page=page, selector=IPL.PREVIEW_URL_ANCHOR)
    assert page.evaluate(
        "(s) => document.activeElement.matches(s + ':focus-visible')",
        IPL.PREVIEW_URL_ANCHOR,
    )
    outline = page.evaluate(
        "() => getComputedStyle(document.activeElement).outlineWidth"
    )
    assert outline == "3px"


@pytest.mark.parametrize("scheme", ["dark", "light"])
def test_non_web_url_text_meets_contrast_on_both_card_backgrounds(
    page: Page,
    build_page_browser: Browser,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    provide_app: Flask,
    scheme: str,
):
    """
    GIVEN two stored non-http(s) URLs landing on an odd and an even card
    WHEN rendered in the dark and the light theme
    THEN each plain-text span has at least 4.5:1 contrast on its card
    """
    for index, non_web_url in enumerate(NON_WEB_URLS):
        _seed_url(app=provide_app, title=f"Non web {index}", url=non_web_url)
    base_url = current_base_url(page=page)
    url = _seed_preview(app=provide_app, page_url_base=base_url)
    with _visitor_page(
        browser=build_page_browser,
        base_url=base_url,
        viewport=DESKTOP_WIDE,
        color_scheme=scheme,
    ) as visitor:
        visitor.goto(url)
        spans = visitor.locator(IPL.PREVIEW_URL_SPAN)
        expect(visitor.locator(IPL.PREVIEW_CARD).first).to_be_visible()
        expect(spans).to_have_count(len(NON_WEB_URLS))
        for index in range(len(NON_WEB_URLS)):
            contrast = spans.nth(index).evaluate(CONTRAST_JS)
            assert contrast >= MIN_CONTRAST, (scheme, index, contrast)


@pytest.mark.parametrize("viewport", [MOBILE, DESKTOP_WIDE], ids=["390", "1280"])
def test_focused_anchor_not_obscured_by_bar_or_banner(
    page_without_cookie_banner_cookie: PageBundle,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
    viewport: dict,
):
    """
    GIVEN a preview page with the cookie banner visible
    WHEN the visitor tabs to the last preview anchor
    THEN its bottom is above both the bar and the banner (WCAG 2.4.11)
    """
    page = _open_with_banner(
        bundle=page_without_cookie_banner_cookie, app=provide_app, viewport=viewport
    )
    _wait_bar_above_banner(page=page)
    count = page.locator(IPL.PREVIEW_URL_ANCHOR).count()
    last = f"{IPL.PREVIEW_CARD}:last-child {IPL.PREVIEW_URL_ANCHOR}"
    _tab_until(page=page, selector=last, limit=TAB_PRESS_LIMIT + count)
    # Let any focus-driven scroll settle before measuring.
    page.wait_for_function(
        """() => {
            const a = document.activeElement.getBoundingClientRect();
            const bar = document.querySelector('#invitePreviewBar').getBoundingClientRect();
            return a.bottom <= bar.top + 1;
        }"""
    )
    rects = page.evaluate(GET_RECTS_JS)
    anchor = _box(page=page, selector=last)
    assert anchor["y"] + anchor["height"] <= rects["bar"]["top"] + TOLERANCE_PX
    assert anchor["y"] + anchor["height"] <= rects["banner"]["top"] + TOLERANCE_PX


def test_preview_anchors_are_at_least_44px_tall_on_mobile(
    page: Page,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a preview page at 390
    THEN every preview anchor has a hit area at least 44px tall
    """
    page.set_viewport_size(MOBILE)
    page.goto(_seed_preview(app=provide_app, page_url_base=current_base_url(page=page)))
    anchors = page.locator(IPL.PREVIEW_URL_ANCHOR)
    expect(anchors.first).to_be_visible()
    for index in range(anchors.count()):
        box = anchors.nth(index).bounding_box()
        assert box is not None
        assert box["height"] >= MIN_TOUCH_TARGET_PX - 0.01, (index, box)


def test_skip_link_reaches_bar_with_visible_focus_ring(
    page: Page,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a preview page
    WHEN the visitor tabs to the skip link and presses Enter
    THEN it is hidden until focused, no URL is focused before it, focus moves to the
         bar with a 3px inside ring, and the next Tab lands on Create account
    """
    page.set_viewport_size(MOBILE)
    page.goto(_seed_preview(app=provide_app, page_url_base=current_base_url(page=page)))
    hidden = _box(page=page, selector=IPL.PREVIEW_SKIP_LINK)
    assert hidden["width"] <= TOLERANCE_PX and hidden["height"] <= TOLERANCE_PX

    anchors_focused = _tab_until(page=page, selector=IPL.PREVIEW_SKIP_LINK)
    assert not any(anchors_focused)
    shown = _box(page=page, selector=IPL.PREVIEW_SKIP_LINK)
    viewport = page.viewport_size
    assert viewport is not None
    assert shown["width"] > TOLERANCE_PX and shown["height"] > TOLERANCE_PX
    assert shown["x"] >= 0 and shown["y"] >= 0
    assert shown["x"] + shown["width"] <= viewport["width"]
    assert shown["y"] + shown["height"] <= viewport["height"]

    page.keyboard.press("Enter")
    page.wait_for_function(ACTIVE_MATCHES_JS, arg=IPL.PREVIEW_BAR)
    ring = page.evaluate(
        """() => {
            const style = getComputedStyle(document.activeElement);
            return [style.outlineWidth, style.outlineOffset];
        }"""
    )
    assert ring == ["3px", "-3px"]
    bar = _box(page=page, selector=IPL.PREVIEW_BAR)
    assert bar["x"] >= 0 and bar["x"] + bar["width"] <= viewport["width"]
    assert bar["y"] + bar["height"] <= viewport["height"] + TOLERANCE_PX

    page.keyboard.press("Tab")
    assert page.evaluate(ACTIVE_MATCHES_JS, IPL.PREVIEW_BAR_CREATE_ACCOUNT)


def test_short_viewport_bar_is_static_and_reachable(
    page_without_cookie_banner_cookie: PageBundle,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a 667x375 viewport
    THEN the bar is static in flow; with the banner visible the bar and footer links
         scroll fully above it; after dismissal the body padding is 0
    """
    page = _open_with_banner(
        bundle=page_without_cookie_banner_cookie, app=provide_app, viewport=SHORT
    )
    assert (
        page.evaluate(
            "() => getComputedStyle(document.querySelector('#invitePreviewBar')).position"
        )
        == "static"
    )

    page.evaluate(SCROLL_BOTTOM_JS)
    page.wait_for_function(
        """() => {
            const banner = document.querySelector('#CookieBanner').getBoundingClientRect();
            return ['#invitePreviewBar', '#PrivacyBtn', '#TermsBtn'].every(
                (selector) =>
                    document.querySelector(selector).getBoundingClientRect().bottom
                    <= banner.top + 1
            );
        }"""
    )

    page.locator(IPL.COOKIE_BANNER_BTN).click()
    expect(page.locator(IPL.COOKIE_BANNER)).not_to_have_class(BANNER_VISIBLE)
    page.wait_for_function(
        "() => getComputedStyle(document.body).paddingBottom === '0px'"
    )
    page.evaluate(SCROLL_BOTTOM_JS)
    last_card = page.locator(IPL.PREVIEW_CARD).last
    expect(last_card).to_be_in_viewport()
    for selector in (IPL.PRIVACY_BTN, IPL.TERMS_BTN):
        expect(page.locator(selector)).to_be_in_viewport()


@pytest.mark.parametrize("viewport", [MOBILE, DESKTOP_WIDE], ids=["390", "1280"])
def test_no_js_fallback_keeps_last_card_and_footer_reachable(
    page: Page,
    build_page_browser: Browser,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
    viewport: dict,
):
    """
    GIVEN a JS-disabled visitor (invite.ts never runs, so no CSS vars are written)
    THEN body padding-bottom is the 9rem fallback and the last card and footer links
         still end above the bar
    """
    base_url = current_base_url(page=page)
    url = _seed_preview(app=provide_app, page_url_base=base_url)
    with _visitor_page(
        browser=build_page_browser,
        base_url=base_url,
        java_script_enabled=False,
        viewport=viewport,
    ) as visitor:
        visitor.goto(url)
        expect(visitor.locator(IPL.PREVIEW_BAR)).to_be_visible()
        padding = visitor.locator("body").evaluate(
            "(el) => getComputedStyle(el).paddingBottom"
        )
        assert padding == NO_JS_BODY_PADDING
        # No JS: scroll with the keyboard-free API Playwright exposes.
        visitor.mouse.wheel(0, 100_000)
        _wait_scrolled_to_bottom(page=visitor)
        bar_top = _box(page=visitor, selector=IPL.PREVIEW_BAR)["y"]
        last_card = visitor.locator(IPL.PREVIEW_CARD).last.bounding_box()
        assert last_card is not None
        assert last_card["y"] + last_card["height"] <= bar_top + TOLERANCE_PX
        for selector in (IPL.PRIVACY_BTN, IPL.TERMS_BTN):
            box = _box(page=visitor, selector=selector)
            assert box["y"] + box["height"] <= bar_top + TOLERANCE_PX, selector


@pytest.mark.parametrize(
    ("reduced_motion", "duration"), [("no-preference", "0.2s"), ("reduce", "0s")]
)
def test_bar_transition_duration(
    page: Page,
    build_page_browser: Browser,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
    reduced_motion: str,
    duration: str,
):
    """
    GIVEN a preview page
    THEN the bar's transition lasts 0.2s normally and 0s under reduced motion
    """
    base_url = current_base_url(page=page)
    url = _seed_preview(app=provide_app, page_url_base=base_url)
    with _visitor_page(
        browser=build_page_browser, base_url=base_url, reduced_motion=reduced_motion
    ) as visitor:
        visitor.goto(url)
        expect(visitor.locator(IPL.PREVIEW_BAR)).to_be_visible()
        assert (
            visitor.locator(IPL.PREVIEW_BAR).evaluate(
                "(el) => getComputedStyle(el).transitionDuration"
            )
            == duration
        )


def test_bar_padding_rule_uses_safe_area_inset(
    page: Page,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a preview page (headless Chromium resolves the inset to 0)
    THEN the bar's padding-bottom rule is declared with env(safe-area-inset-bottom)
    """
    page.goto(_seed_preview(app=provide_app, page_url_base=current_base_url(page=page)))
    expect(page.locator(IPL.PREVIEW_BAR)).to_be_visible()
    assert page.evaluate(SAFE_AREA_RULE_JS) is not None


def test_badge_date_is_the_utc_fallback_in_a_utc_context(
    page: Page,
    build_page_browser: Browser,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a UTC browser context
    THEN the badge <time> text is `Mon D, YYYY` of the ISO `datetime` attribute's date
         (the local-vs-UTC rewrite itself is covered by Vitest)
    """
    base_url = current_base_url(page=page)
    ends_at = utc_now() + timedelta(days=2)
    token = mint_invite_link_in_db(
        app=provide_app,
        utub_id=_creator_utub_id(provide_app),
        created_by=CREATOR_ID,
        preview_enabled=True,
        preview_ends_at=ends_at,
    )
    with _visitor_page(
        browser=build_page_browser,
        base_url=base_url,
        timezone_id="UTC",
        viewport=DESKTOP_WIDE,
    ) as visitor:
        visitor.goto(f"{base_url}/invite/{token}")
        time_el = visitor.locator(IPL.PREVIEW_BADGE_TIME)
        expect(time_el).to_be_visible()
        iso = time_el.get_attribute("datetime")
        assert iso is not None
        end = datetime.fromisoformat(iso)
        assert abs((end - ends_at).total_seconds()) < 5
        expect(time_el).to_have_text(f"{end:%b} {end.day}, {end.year}")


def test_bar_links_match_state_two_splash_urls(
    page: Page,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a preview page
    THEN the bar's Create account and Log in hrefs equal the state-2 splash URLs
    """
    url = _seed_preview(app=provide_app, page_url_base=current_base_url(page=page))
    token = url.rsplit("/", 1)[1]
    page.goto(url)
    expect(page.locator(IPL.PREVIEW_BAR_CREATE_ACCOUNT)).to_have_attribute(
        "href", f"/?next=/invite/{token}/register"
    )
    expect(page.locator(IPL.PREVIEW_BAR_LOG_IN)).to_have_attribute(
        "href", f"/?next=/invite/{token}"
    )
