from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.utub_members import Member_Role
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    set_member_role_in_utub,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    wait_then_click_element,
    wait_until_css_property,
)
from tests.functional.tags_ui.playwright_utils import click_open_update_utub_tags_btn
from tests.functional.urls_ui.playwright_utils import enter_multi_select_mode

pytestmark = pytest.mark.home_ui

USER_ID_FOR_TEST = 1

_HIDDEN_CLASS_RE = re.compile(r"(^|\s)hidden(\s|$)")
_COLLAPSED_CLASS_RE = re.compile(r"(^|\s)collapsed(\s|$)")

_ALL_GEARS: tuple[str, ...] = (
    HPL.BUTTON_UTUB_SETTINGS_GEAR,
    HPL.BUTTON_MEMBER_SETTINGS_GEAR,
    HPL.BUTTON_TAG_SETTINGS_GEAR,
    HPL.BUTTON_URL_SETTINGS_GEAR,
)

_NARROW_DESKTOP_VIEWPORT = {"width": 1000, "height": 900}
# Wide enough for the 992px desktop layout but narrow enough that the left
# panel (25% wide) sits on its 350px minimum.
_LEFT_PANEL_MIN_VIEWPORT = {"width": 1100, "height": 900}

# The two boundary tests below load fresh at each width instead of shrinking to
# 991 then growing to 992. Existing behaviour, not the gear: initMobileLayout
# (frontend/home/mobile.ts) uses matchMedia("(max-width: 992px)") from
# TABLET_WIDTH = 992 (frontend/lib/constants.ts), which is inclusive. Going
# 991 -> 992 fires no change event, so #leftPanel keeps `.hidden` (UTubs deck and
# its create button are 0x0 too) until 993px, while the deck CSS and the gear
# rule already treat 992px as desktop.
_BELOW_DESKTOP_WIDTH_PX = 991
_AT_DESKTOP_WIDTH_PX = 992

# Lowest bulk-actions overlay z-index and the tag-sheet peek z-index that the
# settings shell must sit between (see styles/home/panel-settings.css).
_TAG_SHEET_PEEK_Z_INDEX = 30
_LOWEST_BULK_ACTIONS_OVERLAY_Z_INDEX = 1036


def _assert_no_gear_visible(page: Page) -> None:
    for gear_selector in _ALL_GEARS:
        expect(page.locator(gear_selector)).to_be_attached()
        expect(page.locator(gear_selector)).to_be_hidden()


def _assert_live_region_idle(page: Page) -> None:
    live_region = page.locator(HPL.PANEL_SETTINGS_ANNOUNCEMENT)
    expect(live_region).to_have_attribute("aria-live", "polite")
    expect(live_region).to_have_text("")


def _unhide_gears(page: Page) -> None:
    """DOM-only: strip the `hidden` class the shell has not removed (no section
    registered yet), so the CSS hide rules can be asserted on their own.

    Waits two animation frames first: the breakpoint `matchMedia` change handler
    (which re-applies `hidden`) fires in the rendering update after a viewport
    resize, so unhiding before it runs would be undone."""
    page.evaluate(
        """(gearSelector) => new Promise((resolve) => {
            requestAnimationFrame(() => requestAnimationFrame(() => {
                document.querySelectorAll(gearSelector).forEach((gear) => {
                    gear.classList.remove('hidden');
                });
                resolve();
            }));
        })""",
        HPL.PANEL_SETTINGS_GEARS,
    )


def _assert_gears_have_no_hidden_class(page: Page) -> None:
    """Guard so a pass can only come from the CSS rule under test."""
    for gear_selector in _ALL_GEARS:
        has_hidden_class = page.evaluate(
            "(cssSelector) => document.querySelector(cssSelector).classList.contains('hidden')",
            gear_selector,
        )
        assert has_hidden_class is False, f"{gear_selector} still has .hidden"


def _reveal_gears(page: Page) -> None:
    _unhide_gears(page)
    _assert_gears_have_no_hidden_class(page)


def _computed_display(page: Page, css_selector: str) -> str:
    return page.evaluate(
        "(cssSelector) => getComputedStyle(document.querySelector(cssSelector)).display",
        css_selector,
    )


def _login_and_select_owned_utub(app: Flask, page: Page) -> int:
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    return utub.id


@pytest.mark.parametrize(
    "member_role", [None, Member_Role.CO_CREATOR, Member_Role.MEMBER]
)
def test_no_gear_visible_with_selected_utub_and_zero_urls(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
    member_role: Member_Role | None,
):
    """
    GIVEN a UTub with no URLs selected as owner (None), co-owner or member
    WHEN no settings section is registered (nothing ships in this phase)
    THEN no gear is visible on any of the four decks and the live region is idle
    """
    app = provide_app
    if member_role is None:
        utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    else:
        utub_id = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST).id
        set_member_role_in_utub(app, USER_ID_FOR_TEST, utub_id, member_role)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )

    _assert_no_gear_visible(page)
    _assert_live_region_idle(page)


def test_no_gear_visible_with_no_utub_selected(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the home page with no UTub selected
    WHEN no settings section is registered
    THEN no gear is visible and the live region is idle
    """
    login_user_to_home_page(app=provide_app, page=page, user_id=USER_ID_FOR_TEST)

    expect(page.locator(HPL.UTUB_DECK)).to_be_visible()
    _assert_no_gear_visible(page)
    _assert_live_region_idle(page)


def test_no_gear_visible_with_urls_and_tags(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN an owned UTub that has URLs and tags
    WHEN no settings section is registered
    THEN no gear is visible on any deck and the live region is idle
    """
    _login_and_select_owned_utub(provide_app, page)

    expect(page.locator(HPL.ROWS_URLS).first).to_be_visible()
    _assert_no_gear_visible(page)
    _assert_live_region_idle(page)


def test_no_gear_visible_at_narrow_desktop_width(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a narrow (1000px) desktop viewport with an owned UTub selected
    WHEN no settings section is registered
    THEN no gear is visible and the live region is idle
    """
    page.set_viewport_size(_NARROW_DESKTOP_VIEWPORT)
    _login_and_select_owned_utub(provide_app, page)

    _assert_no_gear_visible(page)
    _assert_live_region_idle(page)


def test_no_gear_visible_on_mobile_portrait_and_shell_mount_exists(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a mobile-portrait viewport
    WHEN no settings section is registered
    THEN no gear is visible, the shell mount is a sibling right after <main>,
        and the live region is idle
    """
    page = page_mobile_portrait
    login_user_to_home_page(app=provide_app, page=page, user_id=USER_ID_FOR_TEST)

    _assert_no_gear_visible(page)
    expect(page.locator(HPL.PANEL_SETTINGS_ROOT)).to_be_attached()
    is_sibling_after_main = page.evaluate(
        """(rootSelector) => {
            const root = document.querySelector(rootSelector);
            return root !== null && root.previousElementSibling?.tagName === 'MAIN';
        }""",
        HPL.PANEL_SETTINGS_ROOT,
    )
    assert is_sibling_after_main is True
    _assert_live_region_idle(page)


def test_gear_markup_invariants(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the home page
    WHEN it loads
    THEN all four gears are in the DOM carrying the `hidden` class, the popover
        root is hidden, and the Tags gear lives inside #utubTagStandardBtns
    """
    _login_and_select_owned_utub(provide_app, page)

    for gear_selector in _ALL_GEARS:
        gear = page.locator(gear_selector)
        expect(gear).to_be_attached()
        expect(gear).to_have_class(_HIDDEN_CLASS_RE)
        expect(gear).to_have_attribute("aria-haspopup", "dialog")
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_have_class(_HIDDEN_CLASS_RE)
    expect(
        page.locator(
            f"{HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS} {HPL.BUTTON_TAG_SETTINGS_GEAR}"
        )
    ).to_be_attached()


def test_multi_select_hides_only_the_urls_gear(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN URL multi-select mode is active
    WHEN the gears are un-hidden through the DOM
    THEN only the URLs gear is display:none; UTubs, Members and Tags stay visible
    """
    _login_and_select_owned_utub(provide_app, page)
    enter_multi_select_mode(page=page)

    _reveal_gears(page)

    assert _computed_display(page, HPL.BUTTON_URL_SETTINGS_GEAR) == "none"
    expect(page.locator(HPL.BUTTON_UTUB_SETTINGS_GEAR)).to_be_visible()
    expect(page.locator(HPL.BUTTON_MEMBER_SETTINGS_GEAR)).to_be_visible()
    expect(page.locator(HPL.BUTTON_TAG_SETTINGS_GEAR)).to_be_visible()


@pytest.mark.parametrize(
    "caret_selector, deck_selector, gear_selector, content_id",
    [
        (
            HPL.HEADER_AND_CARET_UTUB_DECK,
            HPL.UTUB_DECK,
            HPL.BUTTON_UTUB_SETTINGS_GEAR,
            "UTubDeckContent",
        ),
        (
            HPL.HEADER_AND_CARET_MEMBER_DECK,
            HPL.MEMBER_DECK,
            HPL.BUTTON_MEMBER_SETTINGS_GEAR,
            "MemberDeckContent",
        ),
        (
            HPL.HEADER_AND_CARET_TAG_DECK,
            HPL.TAG_DECK,
            HPL.BUTTON_TAG_SETTINGS_GEAR,
            "TagDeckContent",
        ),
    ],
)
def test_collapsed_deck_hides_its_gear(
    page: Page,
    create_test_tags,
    provide_app: Flask,
    caret_selector: str,
    deck_selector: str,
    gear_selector: str,
    content_id: str,
):
    """
    GIVEN a deck is collapsed with its header caret
    WHEN the gears are un-hidden through the DOM
    THEN that deck's gear is not visible
    """
    _login_and_select_owned_utub(provide_app, page)
    page.locator(caret_selector).click()
    expect(page.locator(deck_selector)).to_have_class(_COLLAPSED_CLASS_RE)
    wait_until_css_property(
        page=page,
        css_selector=f"#{content_id}",
        css_property="visibility",
        expected_value="hidden",
    )

    _reveal_gears(page)

    expect(page.locator(gear_selector)).to_be_hidden()
    # Positive control: a gear on a deck that is NOT collapsed is visible.
    control_selector = (
        HPL.BUTTON_TAG_SETTINGS_GEAR
        if gear_selector != HPL.BUTTON_TAG_SETTINGS_GEAR
        else HPL.BUTTON_MEMBER_SETTINGS_GEAR
    )
    expect(page.locator(control_selector)).to_be_visible()


def test_create_utub_mode_hides_the_utubs_gear(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the create-UTub form is open
    WHEN the gears are un-hidden through the DOM
    THEN the UTubs gear is not visible
    """
    login_user_to_home_page(app=provide_app, page=page, user_id=USER_ID_FOR_TEST)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_CREATE)
    expect(page.locator(HPL.INPUT_UTUB_NAME_CREATE)).to_be_visible()

    _reveal_gears(page)

    expect(page.locator(HPL.BUTTON_UTUB_SETTINGS_GEAR)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MEMBER_SETTINGS_GEAR)).to_be_attached()


def test_tags_update_row_hides_the_tags_gear(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN the Tags close/update row is active
    WHEN the gears are un-hidden through the DOM
    THEN the Tags gear is not visible
    """
    _login_and_select_owned_utub(provide_app, page)
    click_open_update_utub_tags_btn(page=page)

    _reveal_gears(page)

    expect(page.locator(HPL.BUTTON_TAG_SETTINGS_GEAR)).to_be_hidden()
    # Positive control: the other decks' gears render once revealed.
    expect(page.locator(HPL.BUTTON_UTUB_SETTINGS_GEAR)).to_be_visible()
    expect(page.locator(HPL.BUTTON_MEMBER_SETTINGS_GEAR)).to_be_visible()


def test_gears_hidden_below_992(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN an owned UTub selected on desktop
    WHEN the viewport is resized to 991px and the gears are un-hidden
    THEN all four are display:none
    """
    _login_and_select_owned_utub(provide_app, page)

    page.set_viewport_size(
        {"width": _BELOW_DESKTOP_WIDTH_PX, "height": _NARROW_DESKTOP_VIEWPORT["height"]}
    )
    _reveal_gears(page)

    for gear_selector in _ALL_GEARS:
        assert _computed_display(page, gear_selector) == "none"


def test_gears_visible_at_992(page: Page, create_test_utubmembers, provide_app: Flask):
    """
    GIVEN an owned UTub selected on desktop
    WHEN the viewport is resized to exactly 992px and the gears are un-hidden
    THEN all four are visible
    """
    _login_and_select_owned_utub(provide_app, page)

    page.set_viewport_size(
        {"width": _AT_DESKTOP_WIDTH_PX, "height": _NARROW_DESKTOP_VIEWPORT["height"]}
    )
    _reveal_gears(page)

    for gear_selector in _ALL_GEARS:
        expect(page.locator(gear_selector)).to_be_visible()


def test_revealed_gears_do_not_overflow_or_wrap_headers_at_left_panel_minimum(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN the left panel is at its 350px minimum with an owned UTub selected
    WHEN the gears are un-hidden through the DOM
    THEN the Members (owner) and Tags button containers neither overflow
        horizontally nor wrap their visible buttons
    """
    page.set_viewport_size(_LEFT_PANEL_MIN_VIEWPORT)
    _login_and_select_owned_utub(provide_app, page)
    expect(page.locator(HPL.BUTTON_MEMBER_SETTINGS_GEAR)).to_be_hidden()

    _reveal_gears(page)
    left_panel_width = page.evaluate(
        "() => Math.round(document.getElementById('leftPanel').getBoundingClientRect().width)"
    )

    for gear_selector in (
        HPL.BUTTON_MEMBER_SETTINGS_GEAR,
        HPL.BUTTON_TAG_SETTINGS_GEAR,
    ):
        expect(page.locator(gear_selector)).to_be_visible()
        # Margin boxes, not border boxes: the gear's 44px hit area (7px padding)
        # is handed back by a -7px margin, so its transparent padding pokes 7px
        # past the container's content edge by design. That inflates scrollWidth
        # and shifts the border-box top without any real overflow or wrap.
        metrics = page.evaluate(
            """(gearSelector) => {
                const container = document.querySelector(gearSelector).parentElement;
                const containerRect = container.getBoundingClientRect();
                const containerStyle = getComputedStyle(container);
                const contentRight =
                    containerRect.right - parseFloat(containerStyle.paddingRight);
                const boxes = Array.from(container.children)
                    .filter((child) => child.getClientRects().length > 0)
                    .map((child) => {
                        const rect = child.getBoundingClientRect();
                        const style = getComputedStyle(child);
                        return {
                            top: Math.round(rect.top - parseFloat(style.marginTop)),
                            right: rect.right + parseFloat(style.marginRight),
                        };
                    });
                return {
                    gear: gearSelector,
                    contentRight,
                    maxMarginBoxRight: Math.max(...boxes.map((box) => box.right)),
                    visibleButtons: boxes.length,
                    distinctTops: new Set(boxes.map((box) => box.top)).size,
                };
            }""",
            gear_selector,
        )
        assert metrics["maxMarginBoxRight"] <= metrics["contentRight"] + 0.5, metrics
        assert metrics["visibleButtons"] >= 3, metrics
        assert left_panel_width == 350, left_panel_width
        assert metrics["distinctTops"] == 1, metrics


def test_popover_placed_by_test_stays_in_viewport_scrolls_and_layers_correctly(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN the popover is un-hidden and positioned by the test under a gear
        with tall placeholder content
    WHEN its geometry and stacking are measured
    THEN it fits the viewport, scrolls (overflow-y auto) and sits between the
        tag-sheet peek and the lowest bulk-actions overlay in z-index
    """
    _login_and_select_owned_utub(provide_app, page)
    _reveal_gears(page)
    expect(page.locator(HPL.BUTTON_UTUB_SETTINGS_GEAR)).to_be_visible()

    geometry = page.evaluate(
        """({ gearSelector, popoverSelector, rootSelector }) => {
            const gear = document.querySelector(gearSelector);
            const popover = document.querySelector(popoverSelector);
            const root = document.querySelector(rootSelector);
            popover.classList.remove('hidden');
            popover.innerHTML = '<div style="height: 3000px">tall placeholder</div>';
            const gearRect = gear.getBoundingClientRect();
            popover.style.top = gearRect.bottom + 'px';
            popover.style.left = (gearRect.right - popover.offsetWidth) + 'px';
            const popoverRect = popover.getBoundingClientRect();
            const rootZIndex = getComputedStyle(root).zIndex;
            return {
                hasHiddenClass: popover.classList.contains('hidden'),
                height: popoverRect.height,
                bottom: popoverRect.bottom,
                innerHeight: window.innerHeight,
                overflowY: getComputedStyle(popover).overflowY,
                scrollHeight: popover.scrollHeight,
                clientHeight: popover.clientHeight,
                position: getComputedStyle(popover).position,
                rootZIndex,
            };
        }""",
        {
            "gearSelector": HPL.BUTTON_UTUB_SETTINGS_GEAR,
            "popoverSelector": HPL.PANEL_SETTINGS_POPOVER,
            "rootSelector": HPL.PANEL_SETTINGS_ROOT,
        },
    )

    assert geometry["hasHiddenClass"] is False
    assert geometry["position"] == "fixed"
    assert geometry["height"] <= geometry["innerHeight"], geometry
    assert geometry["bottom"] <= geometry["innerHeight"], geometry
    assert geometry["overflowY"] == "auto"
    assert geometry["scrollHeight"] > geometry["clientHeight"], geometry
    # The root is fixed, so it is its own stacking context: the popover's
    # effective layer is the root's z-index.
    root_z_index = int(geometry["rootZIndex"])
    assert (
        _TAG_SHEET_PEEK_Z_INDEX < root_z_index < _LOWEST_BULK_ACTIONS_OVERLAY_Z_INDEX
    ), geometry
    expect(page.locator(HPL.PANEL_SETTINGS_POPOVER)).to_be_visible()
