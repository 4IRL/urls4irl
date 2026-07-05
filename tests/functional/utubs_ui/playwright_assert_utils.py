from playwright.sync_api import Page, expect

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)


def assert_elems_hidden_after_utub_deleted(*, page: Page) -> None:
    """Assert that all action buttons and editable classes are absent after a
    UTub is deleted and no UTub remains selected.

    Args:
        page: Playwright Page that just completed a UTub deletion
    """
    non_visible_elems = (
        HPL.BUTTON_UTUB_DELETE,
        HPL.BUTTON_MEMBER_CREATE,
        HPL.BUTTON_UTUB_TAG_CREATE,
        HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN,
        HPL.BUTTON_UNSELECT_ALL,
        HPL.BUTTON_CORNER_URL_CREATE,
    )

    for elem in non_visible_elems:
        expect(page.locator(elem).first).to_be_hidden()

    utub_title = page.locator(HPL.HEADER_URL_DECK)
    title_class = utub_title.get_attribute("class") or ""
    assert HPL.EDITABLE_CLASS not in title_class

    utub_description = page.locator(HPL.SUBHEADER_URL_DECK)
    description_class = utub_description.get_attribute("class") or ""
    assert HPL.EDITABLE_CLASS not in description_class


def assert_in_created_utub(*, page: Page) -> None:
    """Assert that the correct action buttons are shown for a UTub the current
    user created.

    Args:
        page: Playwright Page with a user-created UTub selected
    """
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_CREATE)
    assert_not_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_TAG_CREATE)
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UNSELECT_ALL)
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)


def assert_in_member_utub(*, page: Page) -> None:
    """Assert that the correct action buttons are shown for a UTub the current
    user is a member of but did not create.

    Args:
        page: Playwright Page with a non-owned UTub selected
    """
    assert_not_visible_css_selector(page=page, css_selector=HPL.BUTTON_MEMBER_CREATE)
    assert_not_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_CREATE)
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_LEAVE)
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_TAG_CREATE)
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UNSELECT_ALL)
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)
