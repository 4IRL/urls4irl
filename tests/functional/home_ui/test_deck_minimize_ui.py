from __future__ import annotations

import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import leave_utub_as_member
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    wait_then_click_element,
)
from tests.functional.utubs_ui.playwright_utils import delete_utub_as_creator

pytestmark = pytest.mark.home_ui

_COLLAPSED_CLASS_RE = re.compile(r"(^|\s)collapsed(\s|$)")
_DECK_LOCKED_CLASS_RE = re.compile(r"(^|\s)deck-locked(\s|$)")
# Matches any attribute value, so `not_to_have_attribute(name, _ANY_VALUE_RE)`
# asserts the attribute is absent entirely rather than merely a different value.
_ANY_VALUE_RE = re.compile(r"[\s\S]*")

# Ids of the three visible deck title spans. Each has a visually-hidden real
# <h2> sibling at "<id>A11y" carrying the same text.
_DECK_HEADER_IDS: tuple[str, ...] = (
    "UTubDeckHeader",
    "MemberDeckHeader",
    "TagDeckHeader",
)

# Type properties a real <h2> and the title span must agree on at any viewport
# width. Margins are excluded: `.visually-hidden` overrides them on the sibling.
_RAMPED_TYPE_KEYS: tuple[str, ...] = (
    "fontSize",
    "fontWeight",
    "color",
    "lineHeight",
)

# The three deck disclosure buttons, paired with the `.content` element each one
# owns via aria-controls.
_DECK_HEADER_BUTTONS: tuple[tuple[str, str], ...] = (
    (HPL.HEADER_AND_CARET_UTUB_DECK, "UTubDeckContent"),
    (HPL.HEADER_AND_CARET_MEMBER_DECK, "MemberDeckContent"),
    (HPL.HEADER_AND_CARET_TAG_DECK, "TagDeckContent"),
)

_DESKTOP_VIEWPORT_WIDTH_PX = 1920
_DESKTOP_VIEWPORT_HEIGHT_PX = 1080
_MOBILE_VIEWPORT_WIDTH_PX = 420
_MOBILE_VIEWPORT_HEIGHT_PX = 900


def _caret_hidden(page: Page, deck_selector: str) -> bool:
    return bool(
        page.evaluate(
            """(cssSelector) => {
                const caret = document.querySelector(cssSelector + ' .title-caret');
                if (!caret) return false;
                return getComputedStyle(caret).visibility === 'hidden';
            }""",
            deck_selector,
        )
    )


def _header_typography(page: Page, header_id: str) -> dict[str, str]:
    """Computed type styling of a deck title element, by element id.

    Raises rather than returning a partial dict when the id is gone, so a
    renamed/dropped header fails with the real cause instead of an opaque
    dict mismatch.
    """
    typography: dict[str, str] | None = page.evaluate(
        """(headerId) => {
            const header = document.getElementById(headerId);
            if (!header) return null;
            const style = getComputedStyle(header);
            return {
                fontSize: style.fontSize,
                fontWeight: style.fontWeight,
                color: style.color,
                lineHeight: style.lineHeight,
                marginTop: style.marginTop,
                marginBottom: style.marginBottom,
            };
        }""",
        header_id,
    )
    assert typography is not None, f"No element with id '{header_id}' on the page"
    return typography


def _tab_until_focused(page: Page, element_id: str, max_presses: int = 80) -> bool:
    """Tab forward with the real keyboard until `element_id` holds focus.

    Real Tab presses (not `element.focus()`) are what put the browser in
    keyboard modality, which is the precondition for `:focus-visible` to match —
    so this doubles as proof that the element is a genuine tab stop.
    """
    for _ in range(max_presses):
        page.keyboard.press("Tab")
        if page.evaluate(
            "(elementId) => document.activeElement?.id === elementId", element_id
        ):
            return True
    return False


def _click_deck_header(page: Page, header_selector: str) -> None:
    # A real pointer click can't reach the header (pointer-events:none on the
    # locked state), so fire the click directly to prove the JS guard — not only
    # the CSS — keeps the deck collapsed when no UTub is selected.
    page.evaluate(
        "(cssSelector) => { document.querySelector(cssSelector).click(); }",
        header_selector,
    )


def test_member_and_tag_decks_minimized_when_no_utub_selected(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a user loads the home page (desktop) with no UTub selected
    WHEN the page initializes
    THEN the Member and Tag decks are minimized while the UTub deck stays expanded
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.UTUB_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)


def test_member_and_tag_decks_expand_when_utub_selected(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the home page is loaded with no UTub selected (Member/Tag decks minimized)
    WHEN the user selects a UTub
    THEN the Member and Tag decks expand again
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)

    # Before-state: Member/Tag decks are minimized while no UTub is selected
    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)

    wait_then_click_element(page=page, css_selector=HPL.SELECTORS_UTUB)

    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)


def test_member_and_tag_decks_minimized_after_leaving_utub(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a member has a UTub selected (Member/Tag decks expanded)
    WHEN they leave the UTub, after which no UTub is selected (others remain)
    THEN the Member and Tag decks are minimized again
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_member_of.name,
    )

    # With the UTub selected, the Member/Tag decks are expanded
    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)

    leave_utub_as_member(page=page, utub_to_leave=utub_user_member_of)

    # After leaving, no UTub is selected, so the decks minimize again
    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_COLLAPSED_CLASS_RE)


def test_member_and_tag_decks_locked_when_no_utub_selected(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a user loads the home page (desktop) with no UTub selected
    WHEN the page initializes
    THEN the Member and Tag decks are visibly marked non-expandable
        (deck-locked class applied, caret hidden)
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_DECK_LOCKED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_DECK_LOCKED_CLASS_RE)
    assert _caret_hidden(page, HPL.MEMBER_DECK)
    assert _caret_hidden(page, HPL.TAG_DECK)


def test_member_and_tag_decks_not_expandable_when_no_utub_selected(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the home page is loaded with no UTub selected (Member/Tag decks locked)
    WHEN the user attempts to expand a locked Member/Tag deck via its header
    THEN the deck stays minimized
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_DECK_LOCKED_CLASS_RE)

    _click_deck_header(page, HPL.HEADER_AND_CARET_MEMBER_DECK)
    _click_deck_header(page, HPL.HEADER_AND_CARET_TAG_DECK)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_COLLAPSED_CLASS_RE)


def test_member_and_tag_decks_unlocked_when_utub_selected(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the home page is loaded with no UTub selected (Member/Tag decks locked)
    WHEN the user selects a UTub
    THEN the lock is removed so the decks become expandable again
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_DECK_LOCKED_CLASS_RE)

    wait_then_click_element(page=page, css_selector=HPL.SELECTORS_UTUB)

    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_DECK_LOCKED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).not_to_have_class(_DECK_LOCKED_CLASS_RE)


def test_member_and_tag_decks_minimized_after_deleting_utub(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner has a UTub selected (Member/Tag decks expanded)
    WHEN they delete the UTub, after which no UTub is selected (others remain)
    THEN the Member and Tag decks are minimized again
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )

    # With the UTub selected, the Member/Tag decks are expanded
    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)

    delete_utub_as_creator(page=page, utub_to_delete=utub_user_created)

    # After deleting, no UTub is selected, so the decks minimize again
    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_COLLAPSED_CLASS_RE)


def test_deck_header_typography_matches_original(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the deck titles are now plain <span>s inside the header <button>s
          (they used to be <h2>s, which a <button> cannot legally contain)
    WHEN the home page renders with a UTub selected
    THEN each title still renders exactly as the <h2> did, so the
         div->button+span conversion is visually invisible

    The literal values below were measured from the pre-conversion markup at the
    desktop test viewport (>=1200px, so the responsive h2 ramp the replacement
    rule mirrors resolves to its 2rem ceiling). Asserting the literals — not
    merely "not the browser default" — is what catches a regression to a
    wrong-but-plausible value. line-height and the margins are included because
    they are the properties whose loss would silently move the header band
    rather than merely restyle the text.
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)
    wait_then_click_element(page=page, css_selector=HPL.SELECTORS_UTUB)

    # Decks expanded means every title is rendered in its normal, everyday state
    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)

    expected_typography = {
        "fontSize": "32px",
        "fontWeight": "500",
        "color": "rgb(36, 167, 69)",
        "lineHeight": "38.4px",
        "marginTop": "0px",
        "marginBottom": "0px",
    }

    for header_id in _DECK_HEADER_IDS:
        assert (
            _header_typography(page, header_id) == expected_typography
        ), f"#{header_id} typography changed after the header button conversion"


def test_deck_header_typography_tracks_the_heading_ramp_below_1200px(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the deck title spans restate a responsive font-size ramp that a real
          <h2> gets for free, and the decks stay collapsible down to 992px
    WHEN the viewport sits inside that ramp's fluid band (below 1200px)
    THEN each title span still matches its own visually-hidden <h2> sibling,
         which is a real heading and therefore renders the ramp natively

    Comparing against the sibling rather than another hardcoded string keeps
    this check self-maintaining: it stays true for every width in the band
    without enumerating them. Margins are excluded because `.visually-hidden`
    deliberately gives the sibling a -1px margin.
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)
    wait_then_click_element(page=page, css_selector=HPL.SELECTORS_UTUB)

    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)

    viewport = page.viewport_size
    assert viewport is not None
    page.set_viewport_size({"width": 1100, "height": viewport["height"]})

    for header_id in _DECK_HEADER_IDS:
        title_span = _header_typography(page, header_id)
        hidden_heading = _header_typography(page, f"{header_id}A11y")

        # Guards against a vacuous pass: 1100px must land inside the fluid band,
        # not on the 2rem ceiling asserted by the test above.
        assert (
            title_span["fontSize"] != "32px"
        ), f"#{header_id} did not ramp below 1200px — the ceiling is still applied"
        assert {key: title_span[key] for key in _RAMPED_TYPE_KEYS} == {
            key: hidden_heading[key] for key in _RAMPED_TYPE_KEYS
        }, f"#{header_id} diverged from its <h2> sibling below 1200px"


def test_deck_header_aria_expanded_tracks_the_collapsed_state(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the deck headers are real <button> disclosure controls
    WHEN the page loads with no UTub selected, a UTub is then selected, and a
         deck is then collapsed by hand
    THEN each header's aria-expanded matches its deck's actual collapsed state
         at every point, and the locked headers are also aria-disabled AND
         removed from the tab order

    The templates render a static aria-expanded="true", which is already wrong
    on first paint: minimizeMemberAndTagDecksWhenNoUTub() collapses Members and
    Tags at init. This is the real-browser proof that the JS sync corrects it.
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)

    # No UTub selected: Members + Tags are collapsed AND locked; UTubs is not.
    expect(page.locator(HPL.HEADER_AND_CARET_MEMBER_DECK)).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(page.locator(HPL.HEADER_AND_CARET_TAG_DECK)).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(page.locator(HPL.HEADER_AND_CARET_UTUB_DECK)).to_have_attribute(
        "aria-expanded", "true"
    )
    for header_selector in (
        HPL.HEADER_AND_CARET_MEMBER_DECK,
        HPL.HEADER_AND_CARET_TAG_DECK,
    ):
        # aria-disabled alone would leave a dead control in the tab order.
        expect(page.locator(header_selector)).to_have_attribute("aria-disabled", "true")
        expect(page.locator(header_selector)).to_have_attribute("tabindex", "-1")

    wait_then_click_element(page=page, css_selector=HPL.SELECTORS_UTUB)

    for header_selector in (
        HPL.HEADER_AND_CARET_MEMBER_DECK,
        HPL.HEADER_AND_CARET_TAG_DECK,
    ):
        expect(page.locator(header_selector)).to_have_attribute("aria-expanded", "true")
        expect(page.locator(header_selector)).not_to_have_attribute(
            "aria-disabled", _ANY_VALUE_RE
        )
        expect(page.locator(header_selector)).not_to_have_attribute(
            "tabindex", _ANY_VALUE_RE
        )

    # A user-driven collapse flips it back.
    _click_deck_header(page, HPL.HEADER_AND_CARET_MEMBER_DECK)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.HEADER_AND_CARET_MEMBER_DECK)).to_have_attribute(
        "aria-expanded", "false"
    )


def test_deck_headers_are_not_tab_stops_on_mobile(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the decks are not collapsible below 992px (no click handler is bound
          and the caret is display:none)
    WHEN the viewport crosses below the breakpoint and then back above it
    THEN the three header buttons leave the tab order and lose their disclosure
         ARIA on mobile, and regain both — with aria-expanded re-derived from
         the live collapsed state — on the return to desktop

    Without this the buttons would be dead tab stops announcing
    "expanded, button, controls ...DeckContent". Worse for the Tag deck, which
    sheet.ts relocates into the bottom sheet: activating the button there
    bubbles to #TagDeckTitleGroup and closes the whole sheet.
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)
    wait_then_click_element(page=page, css_selector=HPL.SELECTORS_UTUB)

    page.set_viewport_size(
        {"width": _MOBILE_VIEWPORT_WIDTH_PX, "height": _MOBILE_VIEWPORT_HEIGHT_PX}
    )

    for header_selector, _ in _DECK_HEADER_BUTTONS:
        expect(page.locator(header_selector)).to_have_attribute("tabindex", "-1")
        expect(page.locator(header_selector)).not_to_have_attribute(
            "aria-expanded", _ANY_VALUE_RE
        )
        expect(page.locator(header_selector)).not_to_have_attribute(
            "aria-controls", _ANY_VALUE_RE
        )

    page.set_viewport_size(
        {"width": _DESKTOP_VIEWPORT_WIDTH_PX, "height": _DESKTOP_VIEWPORT_HEIGHT_PX}
    )

    for header_selector, content_id in _DECK_HEADER_BUTTONS:
        expect(page.locator(header_selector)).not_to_have_attribute(
            "tabindex", _ANY_VALUE_RE
        )
        expect(page.locator(header_selector)).to_have_attribute("aria-expanded", "true")
        expect(page.locator(header_selector)).to_have_attribute(
            "aria-controls", content_id
        )


def test_deck_header_button_takes_keyboard_focus_and_shows_its_ring(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN the header is now a real <button> carrying the :focus-visible ring
    WHEN a keyboard user tabs onto the Member deck header
    THEN the button actually receives focus and the ring renders on it

    This is the check that the Step 3 ring and the Step 4 focus retarget line
    up: the outline is bound to #MemberDeckHeaderAndCaret, so it stays invisible
    if focus ever lands on the inner #MemberDeckHeader span instead.
    """
    app = provide_app
    login_user_to_home_page(app=app, page=page, user_id=1)
    wait_then_click_element(page=page, css_selector=HPL.SELECTORS_UTUB)
    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)

    assert _tab_until_focused(
        page, "MemberDeckHeaderAndCaret"
    ), "#MemberDeckHeaderAndCaret was never reached by tabbing — it is not a tab stop"

    focus_ring = page.evaluate("""() => {
            const header = document.getElementById('MemberDeckHeaderAndCaret');
            const style = getComputedStyle(header);
            return {
                matchesFocusVisible: header.matches(':focus-visible'),
                outlineStyle: style.outlineStyle,
                outlineWidth: style.outlineWidth,
            };
        }""")

    assert focus_ring["matchesFocusVisible"] is True
    assert focus_ring["outlineStyle"] == "solid"
    assert focus_ring["outlineWidth"] == "2px"
