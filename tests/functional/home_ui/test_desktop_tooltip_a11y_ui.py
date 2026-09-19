"""Desktop accessibility contract for the hover tooltips (WCAG 2.1 SC 1.4.13).

Bootstrap gives a tooltip none of this, so ``frontend/lib/tooltips.ts`` adds it
on top of the plain ``data-bs-trigger="hover"`` configuration and this suite is
the end-to-end proof:

* **Dismissible** — Escape hides a visible bubble without moving the pointer.
* **Keyboard triggering** — a bubble appears on ``:focus-visible`` (Tab) but NOT
  on click-focus, which is why the trigger stays ``"hover"`` rather than
  ``"hover focus"``.
* **No double announcement** — every bubble's text is a duplicate of its
  trigger's ``aria-label``, so the ``aria-describedby`` Bootstrap wires up on
  show is removed and the bubble is hidden from the accessibility tree.

The coarse-pointer (mobile) twin of this file is
``test_mobile_tooltip_suppression_ui.py``, which proves none of this machinery
is created on touch at all.
"""

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.utils.constants import STRINGS
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
)
from tests.functional.playwright_utils import (
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.home_ui

# The delete-UTub deck-header button stands in for every Group A/B trigger: they
# all share one code path in `lib/tooltips.ts`, so proving the contract once here
# beats repeating it per deck.
DELETE_UTUB_TOOLTIP_SELECTOR = (
    f"{HPL.TOOLTIP_CLASS_STEM_UTUB_DELETE}{HPL.TOOLTIP_SUFFIX}"
)

# Generous enough to cross the whole nav plus the UTub deck header, small enough
# to fail fast if the button ever leaves the tab order entirely.
MAX_TAB_PRESSES = 40

_ACTIVE_ELEMENT_MATCHES_JS = (
    "selector => document.activeElement !== null "
    "&& document.activeElement.matches(selector)"
)


def _tab_until_focused(*, page: Page, css_selector: str) -> None:
    """Walk the tab order with real ``Tab`` keypresses until ``css_selector`` has
    focus.

    Real keypresses are what make the browser treat the focus as keyboard-driven
    and therefore match ``:focus-visible`` — a programmatic ``locator.focus()``
    does not, so it would silently test nothing. Mirrors the bounded-loop shape
    of ``test_splash_hero_ui.py::test_splash_hero_button_keyboard_focusable``.
    """
    for _ in range(MAX_TAB_PRESSES):
        page.keyboard.press("Tab")
        if page.evaluate(_ACTIVE_ELEMENT_MATCHES_JS, css_selector):
            return
    raise AssertionError(
        f"{css_selector} was never reached within {MAX_TAB_PRESSES} Tab presses"
    )


def _login_and_select_own_utub(*, app: Flask, page: Page) -> None:
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=utub_user_created.name,
    )


def test_escape_dismisses_a_hover_tooltip(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests WCAG 2.1 SC 1.4.13 "Dismissible" for the hover tooltips.

    GIVEN a user hovering a deck-header icon button with its tooltip showing
    WHEN the user presses Escape without moving the pointer
    THEN the tooltip bubble is dismissed
    """
    app = provide_app
    _login_and_select_own_utub(app=app, page=page)

    page.locator(HPL.BUTTON_UTUB_DELETE).first.hover()
    wait_until_visible_css_selector(page=page, css_selector=DELETE_UTUB_TOOLTIP_SELECTOR)

    page.keyboard.press("Escape")

    wait_until_hidden(page=page, css_selector=DELETE_UTUB_TOOLTIP_SELECTOR)


def test_keyboard_focus_shows_tooltip_without_a_duplicate_announcement(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests the `:focus-visible` trigger and the `aria-describedby` suppression.

    GIVEN a sighted keyboard user tabbing through the UTub deck header
    WHEN focus lands on the icon-only delete-UTub button
    THEN the tooltip appears with the expected copy, the bubble is hidden from
         assistive tech, and the button announces its `aria-label` only — never
         the same string twice via `aria-describedby`
    """
    app = provide_app
    _login_and_select_own_utub(app=app, page=page)

    _tab_until_focused(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)

    wait_until_visible_css_selector(page=page, css_selector=DELETE_UTUB_TOOLTIP_SELECTOR)
    tooltip = page.locator(DELETE_UTUB_TOOLTIP_SELECTOR).first
    expect(tooltip).to_have_text(STRINGS.DELETE_UTUB_TOOLTIP)
    expect(tooltip).to_have_attribute("aria-hidden", "true")

    delete_utub_btn = wait_then_get_element(
        page=page, css_selector=HPL.BUTTON_UTUB_DELETE
    )
    assert delete_utub_btn is not None
    assert delete_utub_btn.get_attribute("aria-label") == STRINGS.DELETE_UTUB_TOOLTIP
    assert delete_utub_btn.get_attribute("aria-describedby") is None


def test_keyboard_focus_leaving_the_button_hides_the_tooltip(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests that a focus-raised tooltip cannot outlive its trigger's focus.

    GIVEN the delete-UTub button holds keyboard focus with its tooltip showing
    WHEN the user tabs onward
    THEN the tooltip bubble is gone
    """
    app = provide_app
    _login_and_select_own_utub(app=app, page=page)

    _tab_until_focused(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    wait_until_visible_css_selector(page=page, css_selector=DELETE_UTUB_TOOLTIP_SELECTOR)

    page.keyboard.press("Tab")

    wait_until_hidden(page=page, css_selector=DELETE_UTUB_TOOLTIP_SELECTOR)


def test_escape_dismisses_a_keyboard_focused_tooltip(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests WCAG 2.1 SC 1.4.13 "Dismissible" for the keyboard path.

    GIVEN the delete-UTub button holds keyboard focus with its tooltip showing
    WHEN the user presses Escape
    THEN the tooltip is dismissed and does not immediately re-show, even though
         the button still holds `:focus-visible` focus
    """
    app = provide_app
    _login_and_select_own_utub(app=app, page=page)

    _tab_until_focused(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    wait_until_visible_css_selector(page=page, css_selector=DELETE_UTUB_TOOLTIP_SELECTOR)

    page.keyboard.press("Escape")

    wait_until_hidden(page=page, css_selector=DELETE_UTUB_TOOLTIP_SELECTOR)
    expect(page.locator(HPL.BUTTON_UTUB_DELETE).first).to_be_focused()


def test_keyboard_activation_leaves_no_tooltip_bubble(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests the keyboard-activation hazard: the click-hide guard must not be
    fought by the focus trigger re-showing the bubble.

    GIVEN the delete-UTub button holds keyboard focus with its tooltip showing
    WHEN the user activates it with Enter (opening the confirmation modal)
    THEN the bubble is gone and stays gone — no `focusin` re-fires, so nothing
         re-shows it over the modal
    """
    app = provide_app
    _login_and_select_own_utub(app=app, page=page)

    _tab_until_focused(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    wait_until_visible_css_selector(page=page, css_selector=DELETE_UTUB_TOOLTIP_SELECTOR)

    page.keyboard.press("Enter")

    wait_until_visible_css_selector(page=page, css_selector=HPL.HOME_MODAL)
    wait_until_hidden(page=page, css_selector=DELETE_UTUB_TOOLTIP_SELECTOR)


def test_mouse_click_leaves_no_tooltip_bubble(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    Tests that click-focus never strands a bubble.

    This is the regression bar for keeping `data-bs-trigger="hover"`: Bootstrap's
    own `focus` trigger also fires on click-focus, which would leave a bubble
    stranded over the deck after every mouse click.

    GIVEN a user whose pointer raised the delete-UTub tooltip
    WHEN the user clicks the button (opening the confirmation modal over it)
    THEN no tooltip bubble is left behind
    """
    app = provide_app
    _login_and_select_own_utub(app=app, page=page)

    delete_utub_btn = page.locator(HPL.BUTTON_UTUB_DELETE).first
    delete_utub_btn.hover()
    wait_until_visible_css_selector(page=page, css_selector=DELETE_UTUB_TOOLTIP_SELECTOR)

    delete_utub_btn.click()

    wait_until_hidden(page=page, css_selector=DELETE_UTUB_TOOLTIP_SELECTOR)
