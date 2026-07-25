from playwright.sync_api import Locator, Page, expect

from backend.models.utubs import Utubs
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_css_property,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)


def open_utub_name_filter(*, page: Page) -> Locator:
    """Open the UTub name filter input and return the ready input locator.

    On desktop the UTub name search input is hidden behind the funnel toggle.
    Click the funnel to reveal the input, wait for it to become visible and
    focused (the open handler focuses it), then return the now-ready locator.

    Waiting for focus before any keys are sent hardens the root cause of the
    focus/send_keys race rather than padding a timeout.

    Args:
        page: Playwright Page open to the U4I Home Page (desktop viewport)
            with UTubs present

    Returns:
        The visible, focused #UTubNameSearch input locator
    """
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_FILTER)
    wait_until_visible_css_selector(page=page, css_selector=HPL.UTUB_SEARCH_INPUT)
    wait_until_in_focus(page=page, css_selector=HPL.UTUB_SEARCH_INPUT)
    return wait_then_get_element(page=page, css_selector=HPL.UTUB_SEARCH_INPUT)


def create_utub(*, page: Page, utub_name: str, utub_description: str) -> None:
    """Fill the create-UTub form without submitting it.

    Clicks the create button, fills the name input, then fills the description
    input. Does NOT submit — the caller is responsible for clicking the submit
    button or pressing Enter.

    Args:
        page: Playwright Page open to the U4I Home Page
        utub_name: Name for the new UTub
        utub_description: Description for the new UTub
    """
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_CREATE)

    create_utub_name_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_NAME_CREATE
    )
    clear_then_send_keys(locator=create_utub_name_input, input_text=utub_name)

    create_utub_description_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_CREATE
    )
    clear_then_send_keys(
        locator=create_utub_description_input, input_text=utub_description
    )


def open_update_utub_name_input(*, page: Page) -> None:
    """Click the UTub title text to open the name edit input (owner only)."""
    wait_then_click_element(page=page, css_selector=HPL.HEADER_URL_DECK)


def open_update_utub_desc_input(*, page: Page) -> None:
    """Click the UTub description text to open the description edit input (owner only)."""
    wait_then_click_element(page=page, css_selector=HPL.SUBHEADER_URL_DECK)


def open_utub_edit_panel_mobile(*, page: Page) -> None:
    """Tap the consolidated UTub edit-panel toggle (mobile/coarse-pointer flow).

    On mobile the two inline name/description pencils are replaced by a single
    toggle button in the URL-deck header. Tapping it opens BOTH the UTub name and
    description forms together; this waits for both inputs to become visible so
    the caller can drive either field.

    Args:
        page: Playwright Page open to a selected, owned, unlocked UTub on a
            mobile (coarse-pointer) viewport
    """
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_EDIT_PANEL_TOGGLE)
    wait_until_visible_css_selector(page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE)
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )


def update_utub_name(*, page: Page, utub_name: str) -> None:
    """Open the UTub name edit input and fill it with the given name.

    Args:
        page: Playwright Page open to the U4I Home Page with a UTub selected
        utub_name: New UTub name to enter
    """
    open_update_utub_name_input(page=page)
    utub_name_update_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_NAME_UPDATE
    )
    clear_then_send_keys(locator=utub_name_update_input, input_text=utub_name)


def update_utub_description(*, page: Page, utub_description: str) -> None:
    """Open the UTub description edit input and fill it with the given description.

    Args:
        page: Playwright Page open to the U4I Home Page with a UTub selected
        utub_description: New UTub description to enter
    """
    open_update_utub_desc_input(page=page)
    utub_description_update_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    clear_then_send_keys(
        locator=utub_description_update_input, input_text=utub_description
    )


def wait_for_add_utub_description_button(*, page: Page) -> None:
    """Wait for the 'Add a description?' button to be visible and the UTub
    description subheader to be hidden.

    Args:
        page: Playwright Page open to the U4I Home Page with a UTub selected
    """
    wait_until_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY
    )
    expect(page.locator(HPL.SUBHEADER_URL_DECK).first).to_be_hidden()


def delete_utub_as_creator(*, page: Page, utub_to_delete: Utubs) -> None:
    """Delete a UTub as its creator: opens the confirm modal, waits for the
    Bootstrap fade-in to settle, clicks submit, asserts the submit button is
    disabled immediately after click, then waits for the modal and UTub
    selector to disappear.

    Args:
        page: Playwright Page open to the U4I Home Page with the UTub to
            delete already selected
        utub_to_delete: The UTub model instance to delete
    """
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)

    utub_selector = f'{HPL.SELECTORS_UTUB}[utubid="{utub_to_delete.id}"]'
    expect(page.locator(utub_selector)).to_be_visible()

    # The confirmation modal fades in via a Bootstrap transition. Submitting while
    # that fade-in is still running causes Bootstrap to drop the subsequent
    # modal("hide") call (it ignores show/hide requests mid-transition), so the
    # modal never becomes invisible. Gate the submit click on the modal being
    # fully settled (opacity == 1) so the later hide is honored deterministically.
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)

    # Assert submit button is disabled immediately after click to prevent double-submit
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_disabled()

    # Wait for DELETE request
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    wait_for_selector_to_be_removed(page=page, css_selector=utub_selector)
