from playwright.sync_api import Locator, Page, expect

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import (
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_then_get_element,
)


def assert_select_url_as_non_utub_owner_and_non_url_adder(
    *, page: Page, url_selector: str
) -> None:
    """
    Verifies that a UTub member who neither owns the UTub nor added the URL
    sees only the limited set of valid elements on the URL card.
    """
    url_row = wait_then_get_element(page=page, css_selector=url_selector)

    visible_elements = (
        HPL.BUTTON_URL_ACCESS,
        HPL.BUTTON_TAG_CREATE,
    )
    non_visible_elements = (
        HPL.BUTTON_URL_STRING_UPDATE,
        HPL.BUTTON_URL_DELETE,
    )

    for visible_elem_selector in visible_elements:
        visible_elem = url_row.locator(visible_elem_selector)
        expect(visible_elem).to_be_visible()
        expect(visible_elem).to_be_enabled()

    for non_visible_elem_selector in non_visible_elements:
        expect(url_row.locator(non_visible_elem_selector)).to_have_count(0)

    url_title = url_row.locator(HPL.URL_TITLE_READ)
    expect(url_title).to_be_visible()
    expect(url_title).to_be_enabled()

    # Wait for element to fully get in view
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    # Hover auto-scrolls the title into view before moving the pointer onto it
    url_title.hover()

    expect(url_row.locator(HPL.BUTTON_URL_TITLE_UPDATE)).to_have_count(0)


def assert_select_url_as_utub_owner_or_url_creator(
    *, page: Page, url_selector: str
) -> None:
    """
    Verifies that the owner of a UTub or adder of the URL correctly sees all
    valid elements of the URL card.
    """
    url_row = wait_then_get_element(page=page, css_selector=url_selector)

    expect(url_row).to_have_attribute("urlselected", "true")

    visible_elements = (
        HPL.BUTTON_URL_ACCESS,
        HPL.BUTTON_TAG_CREATE,
        HPL.BUTTON_URL_STRING_UPDATE,
        HPL.BUTTON_URL_DELETE,
    )

    for visible_elem_selector in visible_elements:
        visible_elem = url_row.locator(visible_elem_selector)
        expect(visible_elem).to_be_visible()
        expect(visible_elem).to_be_enabled()

    url_title = url_row.locator(HPL.URL_TITLE_READ)
    expect(url_title).to_be_visible()
    expect(url_title).to_be_enabled()

    # Wait for element to fully get in view
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    # Hover auto-scrolls the title into view before moving the pointer onto it
    url_title.hover()

    edit_url_title_icon = url_row.locator(HPL.BUTTON_URL_TITLE_UPDATE)
    expect(edit_url_title_icon).to_be_visible()
    expect(edit_url_title_icon).to_be_enabled()


def assert_keyed_url_is_selected(*, page: Page, url_row: Locator) -> None:
    """
    Verifies whether a URL that is switched to via key press is open by checking
    if the Access URL button is visible.
    """
    access_url_btn = url_row.locator(HPL.BUTTON_URL_ACCESS)
    expect(access_url_btn).to_be_visible()
    expect(access_url_btn).to_be_enabled()
