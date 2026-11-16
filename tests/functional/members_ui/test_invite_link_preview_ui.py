"""Real-browser acceptance for the invite link panel's preview controls: the
switch, the length select, the lapsed and capped opens, the warning contrast in
both themes and the hand-off to the public invite page."""

from __future__ import annotations

from datetime import timedelta

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect

from backend.utils.datetime_utils import utc_now
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import InvitePageLocators as IPL
from tests.functional.members_ui.playwright_utils import (
    OWNER_ID,
    get_invite_link_preview_row,
    login_as,
    set_user_theme_to_system_in_db,
)
from tests.functional.playwright_utils import (
    PageBundle,
    add_cookie_banner_cookie,
    current_base_url,
)
from tests.utils_for_test import add_invite_link

pytestmark = [pytest.mark.members_ui, pytest.mark.home_ui]

ANNOUNCEMENT = "#MemberRowActionAnnouncement"
MIN_CONTRAST = 4.5
STORED_DAYS = 3
DATE_TOLERANCE = timedelta(minutes=2)
DESKTOP = {"width": 1280, "height": 800}
PREVIEW_ON_PREFIX = UTS.INVITE_PANEL_PREVIEW_ON.split("{date}")[0]
WARNING_GLYPH = "⚠"
# The warning's background is translucent, so composite it over the first opaque
# ancestor's background (walking up to the modal body) before taking the ratio.
PANEL_WARNING_CONTRAST_JS = """(warning) => {
    const parse = (color) => {
        const srgb = color.match(/^color\\(srgb ([\\d.]+) ([\\d.]+) ([\\d.]+)(?: \\/ ([\\d.]+))?\\)/);
        if (srgb) {
            const alpha = srgb[4] === undefined ? 1 : Number(srgb[4]);
            return [...srgb.slice(1, 4).map((v) => Number(v) * 255), alpha];
        }
        const parts = color.match(/[\\d.]+/g).map(Number);
        return [parts[0], parts[1], parts[2], parts.length > 3 ? parts[3] : 1];
    };
    const over = (top, base) => {
        const alpha = top[3];
        return [0, 1, 2].map((i) => top[i] * alpha + base[i] * (1 - alpha)).concat([1]);
    };
    const layers = [];
    let node = warning;
    let base = null;
    while (node) {
        const bg = parse(getComputedStyle(node).backgroundColor);
        if (bg[3] === 1) { base = bg; break; }
        if (bg[3] > 0) layers.push(bg);
        node = node.parentElement;
    }
    if (base === null) base = [255, 255, 255, 1];
    for (const layer of layers.reverse()) base = over(layer, base);
    const channel = (value) => {
        const scaled = value / 255;
        return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4;
    };
    const luminance = ([red, green, blue]) =>
        0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue);
    const ratio = (color) => {
        const fg = luminance(over(parse(color), base));
        const bgLum = luminance(base);
        return (Math.max(fg, bgLum) + 0.05) / (Math.min(fg, bgLum) + 0.05);
    };
    return {
        text: ratio(getComputedStyle(warning).color),
        glyph: ratio(getComputedStyle(warning, '::before').color),
        content: getComputedStyle(warning, '::before').content,
    };
}"""


def _open_panel(*, page: Page) -> None:
    page.locator(HPL.BUTTON_MEMBER_INVITE_LINK).click()
    expect(page.locator(HPL.INVITE_LINK_MODAL)).to_be_visible()
    # Focus lands inside the modal only once the open fade has finished.
    expect(page.locator(f"{HPL.INVITE_LINK_MODAL} :focus")).to_have_count(1)


def _seed_and_open(
    *,
    app: Flask,
    page: Page,
    expires_in: timedelta = timedelta(days=30),
    preview_enabled: bool = False,
    preview_window_days: int = STORED_DAYS,
    preview_ends_in: timedelta | None = None,
) -> int:
    utub_id = get_utub_this_user_created(app, OWNER_ID).id
    add_invite_link(
        app,
        utub_id,
        OWNER_ID,
        expires_at=utc_now() + expires_in,
        preview_enabled=preview_enabled,
        preview_window_days=preview_window_days,
        preview_ends_at=(
            utc_now() + preview_ends_in if preview_ends_in is not None else None
        ),
    )
    login_as(app=app, page=page, user_id=OWNER_ID)
    _open_panel(page=page)
    return utub_id


def _settled_on(*, page: Page) -> None:
    switch = page.locator(HPL.INVITE_LINK_PREVIEW_SWITCH)
    announcement = page.locator(ANNOUNCEMENT)
    expect(switch).to_have_attribute("aria-checked", "true")
    # The announcement lands only after the save response, so it settles the save.
    expect(announcement).to_contain_text(PREVIEW_ON_PREFIX)
    warning = page.locator(HPL.INVITE_LINK_PREVIEW_WARNING)
    expect(warning).to_be_visible()
    effective_date = announcement.inner_text().removeprefix(PREVIEW_ON_PREFIX)
    expect(warning).to_contain_text(effective_date.rstrip("."))
    expect(switch).not_to_have_attribute("aria-busy", "true")


def _settled_off(*, page: Page) -> None:
    switch = page.locator(HPL.INVITE_LINK_PREVIEW_SWITCH)
    expect(page.locator(ANNOUNCEMENT)).to_have_text(UTS.INVITE_PANEL_PREVIEW_OFF)
    expect(switch).to_have_attribute("aria-checked", "false")
    expect(page.locator(HPL.INVITE_LINK_PREVIEW_WARNING)).to_have_count(0)
    expect(switch).not_to_have_attribute("aria-busy", "true")


def _assert_on_persisted(*, app: Flask, utub_id: int) -> None:
    enabled, days, ends_at = get_invite_link_preview_row(app=app, utub_id=utub_id)
    assert enabled is True
    assert days == STORED_DAYS
    assert ends_at is not None
    expected = utc_now() + timedelta(days=STORED_DAYS)
    assert abs(ends_at - expected) <= DATE_TOLERANCE, (ends_at, expected)


def _assert_off_persisted(*, app: Flask, utub_id: int) -> None:
    enabled, _, ends_at = get_invite_link_preview_row(app=app, utub_id=utub_id)
    assert enabled is False
    assert ends_at is None


def test_switch_on_and_off_by_click_persists(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a live link with preview off and the panel open
    WHEN the owner clicks the switch on, then off
    THEN each state is saved, the warning follows, the change is announced and
        focus stays on the switch
    """
    app = provide_app
    utub_id = _seed_and_open(app=app, page=page)
    switch = page.locator(HPL.INVITE_LINK_PREVIEW_SWITCH)

    switch.click()
    _settled_on(page=page)
    expect(switch).to_be_focused()
    _assert_on_persisted(app=app, utub_id=utub_id)

    switch.click()
    _settled_off(page=page)
    expect(page.locator(ANNOUNCEMENT)).to_have_text(UTS.INVITE_PANEL_PREVIEW_OFF)
    expect(switch).to_be_focused()
    _assert_off_persisted(app=app, utub_id=utub_id)


def test_switch_toggles_by_space_key(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a live link with preview off and the switch focused
    WHEN the owner presses Space twice
    THEN preview turns on then off, saved each time, with focus kept
    """
    app = provide_app
    utub_id = _seed_and_open(app=app, page=page)
    switch = page.locator(HPL.INVITE_LINK_PREVIEW_SWITCH)
    switch.focus()

    page.keyboard.press("Space")
    _settled_on(page=page)
    expect(switch).to_be_focused()
    _assert_on_persisted(app=app, utub_id=utub_id)

    page.keyboard.press("Space")
    _settled_off(page=page)
    expect(switch).to_be_focused()
    _assert_off_persisted(app=app, utub_id=utub_id)


def test_lapsed_seed_opens_with_switch_off(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a link whose stored preview ended yesterday
    WHEN the owner opens the panel
    THEN the switch is off and there is no warning
    """
    _seed_and_open(
        app=provide_app,
        page=page,
        preview_enabled=True,
        preview_ends_in=timedelta(days=-1),
    )

    expect(page.locator(HPL.INVITE_LINK_PREVIEW_SWITCH)).to_have_attribute(
        "aria-checked", "false"
    )
    expect(page.locator(HPL.INVITE_LINK_PREVIEW_WARNING)).to_have_count(0)


def test_capped_seed_opens_with_capped_option(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a 7 day preview on a link that expires in 2 days
    WHEN the owner opens the panel
    THEN the capped option is selected, 3 and 7 days are disabled and the capped
        hint is visible
    """
    _seed_and_open(
        app=provide_app,
        page=page,
        expires_in=timedelta(days=2),
        preview_enabled=True,
        preview_window_days=7,
        preview_ends_in=timedelta(days=7),
    )
    select = page.locator(HPL.INVITE_LINK_PREVIEW_WINDOW_SELECT)

    first = select.locator("option").first
    expect(first).to_contain_text("(link expiry)")
    expect(first).to_be_disabled()
    expect(select).to_have_value("")
    expect(select.locator('option[value="1"]')).to_be_enabled()
    expect(select.locator('option[value="3"]')).to_be_disabled()
    expect(select.locator('option[value="7"]')).to_be_disabled()
    hint = page.locator(HPL.INVITE_LINK_PREVIEW_WINDOW_HINT)
    expect(hint).to_be_visible()
    expect(hint).to_contain_text(
        UTS.INVITE_PANEL_PREVIEW_WINDOW_CAPPED_HINT.format(
            label=UTS.INVITE_PANEL_PREVIEW_WINDOW_DAYS.format(days=7)
        )
    )


def test_window_change_persists_and_keeps_focus(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a live link with preview off and a stored length of 3 days
    WHEN the owner picks 7 days in Preview length
    THEN the stored length is saved and the select keeps focus
    """
    app = provide_app
    utub_id = _seed_and_open(app=app, page=page)
    select = page.locator(HPL.INVITE_LINK_PREVIEW_WINDOW_SELECT)
    select.focus()

    select.select_option(value="7")

    expect(page.locator(ANNOUNCEMENT)).to_contain_text(
        UTS.INVITE_PANEL_PREVIEW_WINDOW_SET.split(".")[0].format(
            label=UTS.INVITE_PANEL_PREVIEW_WINDOW_DAYS.format(days=7)
        )
    )
    expect(select).to_be_focused()
    expect(select).not_to_have_attribute("aria-busy", "true")
    enabled, days, ends_at = get_invite_link_preview_row(app=app, utub_id=utub_id)
    assert (enabled, days, ends_at) == (False, 7, None)


def test_panel_preview_drives_public_page(
    page: Page,
    build_page_browser: Browser,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a live link and the panel open
    WHEN the owner turns preview on, then off
    THEN a logged-out visitor sees the read-only preview (state 3), then the
        plain invite page (state 2)
    """
    app = provide_app
    _seed_and_open(app=app, page=page)
    base_url = current_base_url(page=page)
    page.locator(HPL.INVITE_LINK_PREVIEW_SWITCH).click()
    _settled_on(page=page)
    token = page.locator(HPL.INVITE_LINK_URL_INPUT).input_value().rsplit("/", 1)[-1]

    context = build_page_browser.new_context(viewport=DESKTOP)
    try:
        context.set_default_timeout(10_000)
        add_cookie_banner_cookie(context=context, base_url=base_url)
        visitor = context.new_page()
        visitor.goto(f"{base_url}/invite/{token}")
        expect(visitor.locator(IPL.PREVIEW_BADGE)).to_be_visible()

        page.locator(HPL.INVITE_LINK_PREVIEW_SWITCH).click()
        _settled_off(page=page)
        visitor.reload()
        expect(visitor.locator(IPL.PREVIEW_BADGE)).to_have_count(0)
        expect(visitor.locator(IPL.PREVIEW_BAR)).to_have_count(0)
    finally:
        context.close()


@pytest.mark.parametrize("scheme", ["dark", "light"])
def test_preview_warning_meets_contrast_in_both_themes(
    page_without_cookie_banner_cookie: PageBundle,
    build_page_browser: Browser,
    create_test_utubmembers,
    provide_app: Flask,
    scheme: str,
):
    """
    GIVEN a link with preview on, opened in a dark or a light colour scheme
    WHEN the warning's text and its glyph are measured
    THEN each has at least 4.5:1 contrast against the warning's composited
        background, and the glyph is present
    """
    app = provide_app
    base_url = page_without_cookie_banner_cookie.base_url
    context = build_page_browser.new_context(color_scheme=scheme, viewport=DESKTOP)
    try:
        context.set_default_timeout(10_000)
        add_cookie_banner_cookie(context=context, base_url=base_url)
        page = context.new_page()
        page.set_viewport_size(DESKTOP)
        page.goto(base_url)
        utub_id = get_utub_this_user_created(app, OWNER_ID).id
        add_invite_link(
            app,
            utub_id,
            OWNER_ID,
            expires_at=utc_now() + timedelta(days=30),
            preview_enabled=True,
            preview_ends_at=utc_now() + timedelta(days=3),
        )
        set_user_theme_to_system_in_db(app=app, user_id=OWNER_ID)
        login_as(app=app, page=page, user_id=OWNER_ID)
        assert page.evaluate(f"matchMedia('(prefers-color-scheme: {scheme})').matches")
        assert page.evaluate("document.documentElement.dataset.theme") == scheme
        _open_panel(page=page)
        warning = page.locator(HPL.INVITE_LINK_PREVIEW_WARNING)
        expect(warning).to_be_visible()

        measured = warning.evaluate(PANEL_WARNING_CONTRAST_JS)
        assert WARNING_GLYPH in measured["content"], (scheme, measured["content"])
        assert measured["content"] not in ("none", "normal"), scheme
        assert measured["text"] >= MIN_CONTRAST, (scheme, "text", measured)
        assert measured["glyph"] >= MIN_CONTRAST, (scheme, "glyph", measured)
    finally:
        context.close()
