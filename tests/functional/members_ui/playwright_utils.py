from playwright.sync_api import Locator, Page, expect

from backend.models.utubs import Utubs
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)


def open_member_name_filter(*, page: Page) -> Locator:
    """Open the member name filter input and return the ready input locator.

    The member name filter input is hidden behind the funnel toggle on all
    viewports. Click the funnel to reveal the input, wait for it to become
    visible and focused (the open handler focuses it), then return the
    now-ready locator.

    Waiting for focus before any keys are sent hardens the root cause of the
    focus/send_keys race rather than padding a timeout.

    Args:
        page: Playwright Page open to the U4I Home Page with a UTub selected

    Returns:
        The visible, focused #MemberNameSearch input locator
    """
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_NAME_FILTER)
    wait_until_visible_css_selector(page=page, css_selector=HPL.MEMBER_SEARCH_INPUT)
    wait_until_in_focus(page=page, css_selector=HPL.MEMBER_SEARCH_INPUT)
    return wait_then_get_element(page=page, css_selector=HPL.MEMBER_SEARCH_INPUT)


def get_all_member_badges(*, page: Page) -> list[Locator]:
    """Return per-element locators for every visible member badge.

    Args:
        page: Playwright Page open to a selected UTub

    Returns:
        List of member badge Locators
    """
    return wait_then_get_elements(page=page, css_selector=HPL.BADGES_MEMBERS)


def get_all_member_usernames(*, page: Page) -> list[str]:
    """Return the inner-text of every visible member badge as a list.

    Args:
        page: Playwright Page open to a selected UTub

    Returns:
        List of member usernames
    """
    badges_locator = page.locator(HPL.BADGES_MEMBERS)
    expect(badges_locator.first).to_be_visible()
    return badges_locator.all_inner_texts()


def create_member_active_utub(*, page: Page, member_name: str) -> None:
    """Open the create-member form and type the username.

    Args:
        page: Playwright Page open to a selected UTub
        member_name: Username of the U4I user to invite as a member
    """
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)
    create_member_input = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_MEMBER_CREATE
    )
    clear_then_send_keys(locator=create_member_input, input_text=member_name)


def delete_member_active_utub(*, page: Page, member_name: str) -> None:
    """Hover over the named member badge and click the delete button.

    Playwright's click auto-waits for the delete button to be actionable
    (visible, stable, enabled) after the hover reveals it — no pause needed.

    Args:
        page: Playwright Page open to a selected UTub owned by the current user
        member_name: Exact username text of the member to delete
    """
    badge = page.locator(HPL.BADGES_MEMBERS).filter(has_text=member_name).first
    expect(badge).to_be_visible()
    badge.hover()
    badge.locator(HPL.BUTTON_MEMBER_DELETE).click()


def leave_utub_as_member(*, page: Page, utub_to_leave: Utubs) -> None:
    """Click the leave-UTub button, confirm the modal, and wait for the UTub
    selector to be removed from the DOM.

    Args:
        page: Playwright Page open to the selected UTub to leave
        utub_to_leave: UTub model instance to leave
    """
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    expect(page.locator(HPL.BODY_MODAL)).to_be_visible()
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_selector_to_be_removed(
        page=page,
        css_selector=f'{HPL.SELECTORS_UTUB}[utubid="{utub_to_leave.id}"]',
    )
