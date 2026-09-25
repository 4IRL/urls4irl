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
    select_utub_by_name,
    wait_then_click_element,
    wait_until_css_property,
    wait_until_utub_name_appears,
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

# The localStorage key deck-layout-storage.ts persists the Member/Tag collapse
# combination under. Read directly (never seeded, except where a test says so)
# so an assertion can tell "saved as expanded" from "never saved at all".
_DECK_LAYOUT_STORAGE_KEY = "u4i:deckLayout"

# The `.content` element ids for the two persistable decks — named separately
# from _DECK_HEADER_BUTTONS above because the helpers below take one deck at a
# time rather than iterating all three.
_MEMBER_DECK_CONTENT_ID = "MemberDeckContent"
_TAG_DECK_CONTENT_ID = "TagDeckContent"

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


def _persisted_deck_layout(page: Page) -> dict[str, bool] | None:
    """The raw saved deck layout, or None when the key was never written."""
    return page.evaluate(
        """(storageKey) => {
            const raw = window.localStorage.getItem(storageKey);
            return raw === null ? null : JSON.parse(raw);
        }""",
        _DECK_LAYOUT_STORAGE_KEY,
    )


def _seed_persisted_deck_layout(
    page: Page, *, members_minimized: bool, tags_minimized: bool
) -> None:
    """Write the saved layout straight into localStorage for THIS page.

    Only for the one case a real in-tab click cannot produce: a saved layout
    that disagrees with what is currently on screen. Every in-tab collapse
    writes the preference in the same handler that toggles the class, so the
    two can only diverge via another tab (or the mobile crossing's
    force-expand, which deliberately leaves storage alone). Deliberately NOT
    `context.add_init_script` — this has to land on an already-loaded page,
    after the decks have been built.
    """
    page.evaluate(
        """({ storageKey, layout }) => {
            window.localStorage.setItem(storageKey, JSON.stringify(layout));
        }""",
        {
            "storageKey": _DECK_LAYOUT_STORAGE_KEY,
            "layout": {
                "membersMinimized": members_minimized,
                "tagsMinimized": tags_minimized,
            },
        },
    )


def _collapse_deck_by_header_click(
    page: Page, *, header_selector: str, deck_selector: str, content_id: str
) -> None:
    """Collapse a deck with a real header click, then wait for it to settle.

    Both gates are root causes, not padding. The class assert proves the click
    handler ran (and with it the localStorage write, which happens in the same
    synchronous handler). The computed-`visibility` wait proves the 0.3s
    transition has ENDED: per the CSS Transitions spec a `visible`->`hidden`
    `visibility` transition holds `visible` until its very last frame, so
    anything that depends on the content actually being hidden (focus order,
    a following `page.reload()`) would race it otherwise.
    """
    page.locator(header_selector).click()
    expect(page.locator(deck_selector)).to_have_class(_COLLAPSED_CLASS_RE)
    wait_until_css_property(
        page=page,
        css_selector=f"#{content_id}",
        css_property="visibility",
        expected_value="hidden",
    )


def _expand_deck_by_header_click(
    page: Page, *, header_selector: str, deck_selector: str, content_id: str
) -> None:
    """Inverse of the above. `hidden`->`visible` flips at 0%, so the wait here
    settles immediately — it is kept for symmetry and to prove the content is
    genuinely back in the focus/a11y tree, not merely un-classed."""
    page.locator(header_selector).click()
    expect(page.locator(deck_selector)).not_to_have_class(_COLLAPSED_CLASS_RE)
    wait_until_css_property(
        page=page,
        css_selector=f"#{content_id}",
        css_property="visibility",
        expected_value="visible",
    )


def _tab_presses_until_inside(
    page: Page, container_id: str, max_presses: int = 15
) -> int | None:
    """Press Tab until focus lands inside `container_id`.

    Returns the number of presses it took, or None if focus never got there
    within `max_presses`. Used both ways round: as a positive control that the
    container really does hold tab stops, and as the negative assertion that a
    collapsed deck's content has left the tab order.
    """
    for press_count in range(1, max_presses + 1):
        page.keyboard.press("Tab")
        if page.evaluate(
            """(containerId) => {
                const container = document.getElementById(containerId);
                return container !== null &&
                    document.activeElement !== null &&
                    container.contains(document.activeElement);
            }""",
            container_id,
        ):
            return press_count
    return None


def _active_element_id(page: Page) -> str:
    return page.evaluate("() => document.activeElement?.id ?? ''")


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
    GIVEN the home page is loaded with no UTub selected (Member/Tag decks
          minimized) and NOTHING is persisted in `u4i:deckLayout`
    WHEN the user selects a UTub
    THEN the Member and Tag decks expand again

    This pins the DEFAULT layout, not an unconditional force-expand: the decks
    are now restored from the saved layout on every UTub selection, and the
    `page` fixture builds a fresh browser context per test (conftest.py), so
    localStorage starts empty and `getDeckLayout()` returns both-expanded.
    A regression that ignored a saved layout would still pass here — that is
    what `test_persisted_deck_layout_applies_to_next_utub` below covers.
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
    GIVEN a member has a UTub selected (Member/Tag decks expanded by default,
          nothing persisted in `u4i:deckLayout`)
    WHEN they leave the UTub, after which no UTub is selected (others remain)
    THEN the Member and Tag decks are minimized again

    The no-UTub auto-minimize is unconditional — it overrides the saved layout
    on screen because an empty deck has nothing to show — but it must not
    WRITE that collapse back as the user's preference. That half is covered by
    `test_auto_minimize_does_not_overwrite_saved_layout` below.
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

    Unchanged by deck-layout persistence: the click handlers still early-return
    on `!isUTubSelected()` before they reach the persistence write, so a locked
    header click saves nothing as well as doing nothing.
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

    The unlock is deliberately unconditional and runs AHEAD of the saved-layout
    handoff (`restoreMemberAndTagDecksForUTub`), so it holds whatever
    `u4i:deckLayout` says — a deck restored collapsed is still unlocked and
    expandable. Nothing is persisted here (fresh context per test), so this
    pins the default path.
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
    GIVEN an owner has a UTub selected (Member/Tag decks expanded by default,
          nothing persisted in `u4i:deckLayout`)
    WHEN they delete the UTub, after which no UTub is selected (others remain)
    THEN the Member and Tag decks are minimized again

    Same reading as the leave-UTub case above: the no-UTub auto-minimize is an
    on-screen override, not a saved preference.
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
        assert _header_typography(page, header_id) == expected_typography, (
            f"#{header_id} typography changed after the header button conversion"
        )


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
        assert title_span["fontSize"] != "32px", (
            f"#{header_id} did not ramp below 1200px — the ceiling is still applied"
        )
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

    assert _tab_until_focused(page, "MemberDeckHeaderAndCaret"), (
        "#MemberDeckHeaderAndCaret was never reached by tabbing — it is not a tab stop"
    )

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


def test_persisted_deck_layout_applies_to_next_utub(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a user collapsed the Member deck while one UTub was open
    WHEN they select a DIFFERENT UTub
    THEN the Member deck comes back collapsed and the Tag deck comes back
         expanded — the saved layout, not a force-expand

    This is the feature's core behavior and had zero coverage in either suite:
    restoreMemberAndTagDecksForUTub() used to expand both decks on every UTub
    selection, erasing the collapse on the very next click.
    """
    app = provide_app
    user_id_for_test = 1
    first_utub = get_utub_this_user_created(app, user_id_for_test)
    second_utub = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=first_utub.name,
    )

    _collapse_deck_by_header_click(
        page,
        header_selector=HPL.HEADER_AND_CARET_MEMBER_DECK,
        deck_selector=HPL.MEMBER_DECK,
        content_id=_MEMBER_DECK_CONTENT_ID,
    )
    # Only the Member deck was touched, so the Tag deck's saved value must be
    # the untouched default — proving the write is a read-merge-write, not a
    # blanket overwrite of both decks.
    assert _persisted_deck_layout(page) == {
        "membersMinimized": True,
        "tagsMinimized": False,
    }

    select_utub_by_name(page=page, utub_name=second_utub.name)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)
    # The restored-collapsed deck is still a working disclosure control, not an
    # inert one: it must be unlocked and announce its real state.
    expect(page.locator(HPL.HEADER_AND_CARET_MEMBER_DECK)).to_have_attribute(
        "aria-expanded", "false"
    )
    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_DECK_LOCKED_CLASS_RE)


def test_persisted_deck_layout_survives_reload(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a user collapsed BOTH the Member and Tag decks by hand
    WHEN they reload the page
    THEN both decks come back collapsed once the UTub is selected again

    [DD-14] No localStorage seeding: `page.reload()` keeps localStorage for the
    same origin, and driving the collapse through real clicks exercises the
    write path as well as the read path — a strictly stronger test than seeding
    the value would be. The `context.add_init_script` pattern used by the
    onboarding-nudge tests exists for a flag with no UI path that sets it,
    which is not the case here.

    Two decks collapsed is also the cap's boundary, not past it: the Tag
    collapse sees one deck already collapsed, so `ensureOnlyTwoDecksCollapsedAtOnce`
    does not fire and neither deck is evicted.
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

    _collapse_deck_by_header_click(
        page,
        header_selector=HPL.HEADER_AND_CARET_MEMBER_DECK,
        deck_selector=HPL.MEMBER_DECK,
        content_id=_MEMBER_DECK_CONTENT_ID,
    )
    _collapse_deck_by_header_click(
        page,
        header_selector=HPL.HEADER_AND_CARET_TAG_DECK,
        deck_selector=HPL.TAG_DECK,
        content_id=_TAG_DECK_CONTENT_ID,
    )
    # Gate the reload on the WRITE, not on the clicks: both helpers above
    # already waited out the 0.3s visibility transition, and this proves the
    # preference itself reached localStorage before the page is torn down.
    assert _persisted_deck_layout(page) == {
        "membersMinimized": True,
        "tagsMinimized": True,
    }

    page.reload()

    # Selecting a UTub pushed `/home?UTubID=<id>`, so the reload lands back on
    # that URL and window-events.ts's pageshow handler re-selects the UTub
    # itself — that IS the "select a UTub" step, driven by the app rather than
    # by a second click.
    wait_until_utub_name_appears(page=page, utub_name=utub_user_created.name)

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.UTUB_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)


def test_auto_minimize_does_not_overwrite_saved_layout(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a saved layout of Members EXPANDED and Tags COLLAPSED
    WHEN the user leaves the UTub — firing the unconditional no-UTub
         auto-minimize, which collapses both decks on screen — and then selects
         another UTub
    THEN the Member deck is expanded again and the Tag deck is still collapsed

    This is the storage-poisoning regression `test_member_and_tag_decks_minimized_after_leaving_utub`
    structurally cannot catch: it asserts the on-screen collapse, which is
    correct either way. If `minimizeMemberAndTagDecksWhenNoUTub()` ever routed
    through the persistence write, the user's expanded Member deck would be
    silently saved as collapsed and never come back.

    Members is collapsed and re-expanded first so `membersMinimized: false` is
    a value genuinely WRITTEN by the user, not the same `false` a
    never-written key defaults to — otherwise a poisoning bug could be masked
    by the default.
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

    _collapse_deck_by_header_click(
        page,
        header_selector=HPL.HEADER_AND_CARET_MEMBER_DECK,
        deck_selector=HPL.MEMBER_DECK,
        content_id=_MEMBER_DECK_CONTENT_ID,
    )
    _expand_deck_by_header_click(
        page,
        header_selector=HPL.HEADER_AND_CARET_MEMBER_DECK,
        deck_selector=HPL.MEMBER_DECK,
        content_id=_MEMBER_DECK_CONTENT_ID,
    )
    _collapse_deck_by_header_click(
        page,
        header_selector=HPL.HEADER_AND_CARET_TAG_DECK,
        deck_selector=HPL.TAG_DECK,
        content_id=_TAG_DECK_CONTENT_ID,
    )
    assert _persisted_deck_layout(page) == {
        "membersMinimized": False,
        "tagsMinimized": True,
    }

    leave_utub_as_member(page=page, utub_to_leave=utub_user_member_of)

    # On screen both decks are now collapsed (the no-UTub state), but the saved
    # preference must be untouched.
    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    assert _persisted_deck_layout(page) == {
        "membersMinimized": False,
        "tagsMinimized": True,
    }

    wait_then_click_element(page=page, css_selector=HPL.SELECTORS_UTUB)

    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_COLLAPSED_CLASS_RE)


def test_collapsing_a_deck_by_keyboard_removes_its_content_from_the_tab_order(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN a keyboard user has tabbed onto the Member deck's header button
    WHEN they press Enter to collapse the deck
    THEN the deck collapses, aria-expanded flips to "false", and every control
         inside the collapsed `.content` leaves the tab order

    The tab-order half is the real-browser proof of the Step 2 CSS change:
    `.deck.collapsed .content` is `visibility: hidden`, because `opacity: 0`
    alone left every member row, filter input and button focusable and
    screen-reader-readable inside a deck the user had shut. `decks.css` is
    never loaded into happy-dom, so no vitest case can assert this.

    The pre-collapse pass is a deliberate positive control: it proves the
    deck's content DOES hold reachable tab stops while expanded, so the
    post-collapse `is None` cannot pass vacuously against an empty container.
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
    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)

    assert _tab_until_focused(page, "MemberDeckHeaderAndCaret"), (
        "#MemberDeckHeaderAndCaret was never reached by tabbing — it is not a tab stop"
    )

    presses_to_content = _tab_presses_until_inside(page, _MEMBER_DECK_CONTENT_ID)
    assert presses_to_content is not None, (
        "No control inside the EXPANDED #MemberDeckContent was tab-reachable — "
        "the negative assertion below would pass for the wrong reason"
    )

    # Walk back exactly as far as we came. The tab order is unchanged in
    # between, so this lands on the header button itself and the Enter below is
    # a genuine keyboard activation of the disclosure control.
    for _ in range(presses_to_content):
        page.keyboard.press("Shift+Tab")
    assert _active_element_id(page) == "MemberDeckHeaderAndCaret"

    page.keyboard.press("Enter")

    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.HEADER_AND_CARET_MEMBER_DECK)).to_have_attribute(
        "aria-expanded", "false"
    )
    # A `visible`->`hidden` visibility transition holds `visible` until its last
    # frame, so assert the transition has landed rather than racing it.
    wait_until_css_property(
        page=page,
        css_selector=f"#{_MEMBER_DECK_CONTENT_ID}",
        css_property="visibility",
        expected_value="hidden",
    )
    # Focus never left the header (it sits in `.titleElement:first-child`,
    # which is never hidden), so this tabs forward from the same place as the
    # positive control above.
    assert _active_element_id(page) == "MemberDeckHeaderAndCaret"

    assert _tab_presses_until_inside(page, _MEMBER_DECK_CONTENT_ID) is None, (
        "A control inside the COLLAPSED #MemberDeckContent is still tab-reachable "
        "— `.deck.collapsed .content { visibility: hidden }` is not in effect"
    )


def test_programmatic_collapse_moves_focus_to_the_deck_header(
    page: Page,
    create_test_tags,
    provide_app: Flask,
):
    """
    GIVEN focus sits on a control inside an expanded Member deck, and the saved
          layout says the Member deck should be collapsed
    WHEN a UTub selection that moves no focus of its own (browser Back, i.e.
         the popstate path) applies that layout
    THEN focus lands on the Member deck's header button instead of <body>

    Collapsing a deck that contains `document.activeElement` used to drop focus
    to `<body>`, because `.deck.collapsed .content`/`.button-container` are
    `visibility: hidden` and that prunes the focused node out of the focus
    tree — a WCAG 2.4.3 break with no indicator and nothing to Shift+Tab back
    to. The caret-click path was always safe (focus is already on the header);
    every PROGRAMMATIC collapse was not, and persistence is what makes those
    routine.

    The saved layout is seeded rather than clicked because an in-tab click
    keeps storage and the DOM in lockstep — see `_seed_persisted_deck_layout`.
    Back is used rather than a click on a UTub selector because a selector is
    `tabindex="0"`: clicking one focuses it, which would move focus out of the
    deck before the collapse and make the assertion vacuous.
    """
    app = provide_app
    user_id_for_test = 1
    previous_utub = get_utub_this_user_did_not_create(app, user_id_for_test)
    owned_utub = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=previous_utub.name,
    )
    # Second selection: pushes a history entry, and lands on a UTub this user
    # owns so #memberBtnCreate (inside the Member deck's `.button-container`)
    # is actually rendered and focusable.
    select_utub_by_name(page=page, utub_name=owned_utub.name)
    expect(page.locator(HPL.MEMBER_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)
    expect(page.locator(HPL.BUTTON_MEMBER_CREATE)).to_be_visible()

    _seed_persisted_deck_layout(page, members_minimized=True, tags_minimized=False)
    page.locator(HPL.BUTTON_MEMBER_CREATE).focus()
    assert _active_element_id(page) == "memberBtnCreate"

    page.go_back()

    wait_until_utub_name_appears(page=page, utub_name=previous_utub.name)
    expect(page.locator(HPL.MEMBER_DECK)).to_have_class(_COLLAPSED_CLASS_RE)
    assert _active_element_id(page) == "MemberDeckHeaderAndCaret", (
        "Collapsing the Member deck out from under the focused #memberBtnCreate "
        "dropped focus instead of handing it to the deck's own header button"
    )
