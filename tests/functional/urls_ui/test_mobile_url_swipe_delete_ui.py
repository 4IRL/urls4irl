from flask import Flask
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from backend.utils.strings.url_strs import DELETE_URL_WARNING
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.db_utils import (
    get_url_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as ML
from tests.functional.login_utils import login_user_and_select_utub_by_utubid_mobile
from tests.functional.selenium_utils import (
    Decks,
    get_num_url_rows,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_until_css_property,
    wait_until_hidden,
)
from tests.functional.urls_ui.selenium_utils import (
    get_url_row_selector,
    swipe_url_card_below_threshold,
    swipe_url_card_delete,
    wait_until_url_card_swipe_committed,
    wait_until_url_card_swipe_reset,
)

pytestmark = [pytest.mark.urls_ui, pytest.mark.mobile_ui]

USER_ID_FOR_TEST = 1
SWIPE_COMMITTED_CLASS = "swipe-committed"
SWIPE_DRAGGING_CLASS = "swipe-dragging"
# --borderColor (frontend/styles/tokens.css), as a browser-normalized rgb() string.
NEUTRAL_ROW_BORDER_COLOR = "rgb(52, 60, 61)"


def test_url_swipe_commit_opens_confirm_modal(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a deletable URL
    WHEN they swipe the URL row left past the commit threshold
    THEN the row commits (swipe-committed class) and the delete confirmation
        modal opens, proving the real browser commits the drag gesture end-to-end
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url.id)
    assert_visible_css_selector(browser, row_selector)

    swipe_url_card_delete(browser, row_selector)
    wait_until_url_card_swipe_committed(browser)

    assert_visible_css_selector(browser, ML.ELEMENT_MODAL)
    modal_body = browser.find_element(By.CSS_SELECTOR, HPL.BODY_MODAL)
    assert modal_body.text == DELETE_URL_WARNING


def test_url_swipe_commit_confirm_deletes_and_removes_row(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a committed swipe-to-delete gesture with the confirm modal open
    WHEN the user confirms the deletion
    THEN the URL is deleted and its row is removed from the DOM
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url.id)
    url_row = browser.find_element(By.CSS_SELECTOR, row_selector)
    init_num_url_rows = get_num_url_rows(browser)

    swipe_url_card_delete(browser, row_selector)
    wait_until_url_card_swipe_committed(browser)
    assert_visible_css_selector(browser, ML.ELEMENT_MODAL)

    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(browser, HPL.HOME_MODAL)

    assert wait_for_element_to_be_removed(browser, url_row)
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, row_selector)
    assert init_num_url_rows - 1 == get_num_url_rows(browser)


def test_url_swipe_commit_dismiss_snaps_back_without_deleting(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a committed swipe-to-delete gesture with the confirm modal open
    WHEN the user dismisses the modal instead of confirming
    THEN the URL is not deleted, the row resets to a clean state with no
        leftover swipe-committed/swipe-dragging class, and the WCAG
        focus-return suppression actually renders a neutral border rather
        than the focus-ring green (regression coverage for a CSS-specificity
        bug where the suppression rule lost the cascade to the pre-existing
        focus-ring rule despite the suppression class being correctly applied)
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url.id)
    init_num_url_rows = get_num_url_rows(browser)

    swipe_url_card_delete(browser, row_selector)
    wait_until_url_card_swipe_committed(browser)
    assert_visible_css_selector(browser, ML.ELEMENT_MODAL)

    wait_then_click_element(browser, HPL.BUTTON_MODAL_DISMISS)
    wait_until_hidden(browser, HPL.HOME_MODAL)

    wait_until_url_card_swipe_reset(browser)
    url_row = browser.find_element(By.CSS_SELECTOR, row_selector)
    row_class = url_row.get_attribute("class") or ""
    assert SWIPE_COMMITTED_CLASS not in row_class
    assert SWIPE_DRAGGING_CLASS not in row_class
    assert init_num_url_rows == get_num_url_rows(browser)

    wait_until_css_property(
        browser, row_selector, "border-bottom-color", NEUTRAL_ROW_BORDER_COLOR
    )


def test_url_swipe_below_threshold_snaps_back_no_op(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a deletable URL
    WHEN they swipe the row left by a small amount well below the ~35% commit
        threshold (sub-threshold drag)
    THEN the row snaps back to its resting position and does not open the
        confirm modal, proving the real browser only commits once the
        threshold is crossed
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url.id)
    init_num_url_rows = get_num_url_rows(browser)

    swipe_url_card_below_threshold(browser, row_selector)
    wait_until_url_card_swipe_reset(browser)

    assert_not_visible_css_selector(browser, ML.ELEMENT_MODAL)
    url_row = browser.find_element(By.CSS_SELECTOR, row_selector)
    row_class = url_row.get_attribute("class") or ""
    assert SWIPE_COMMITTED_CLASS not in row_class
    assert init_num_url_rows == get_num_url_rows(browser)


def test_url_tap_to_select_delete_button_still_works(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a deletable URL
    WHEN they tap the row to select it, then tap the existing .urlBtnDelete
    THEN the confirm modal opens exactly as before the swipe gesture was added
        (non-regression of the existing tap-to-select delete flow)
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url.id)
    wait_then_click_element(browser, row_selector, time=10)

    # The selected-row padding/transform transition must settle before the
    # delete button's post-select position is stable, otherwise the click
    # lands on a still-animating sibling (e.g. .urlTags) instead of the
    # button — mirrors login_select_utub_select_url_click_delete_get_modal_url.
    wait_for_animation_to_end_check_top_lhs_corner(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    delete_btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}"
    wait_then_click_element(browser, delete_btn_selector, time=5)

    assert_visible_css_selector(browser, ML.ELEMENT_MODAL)
    modal_body = browser.find_element(By.CSS_SELECTOR, HPL.BODY_MODAL)
    assert modal_body.text == DELETE_URL_WARNING


def test_url_swipe_inert_for_non_deletable_row(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a URL they cannot delete
        (added by a different member, in a UTub they did not create)
    WHEN they attempt the same left-swipe gesture used to delete a row
    THEN the row is inert — no swipe reveal panel exists, no swipe class is
        applied, and no confirm modal opens
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    assert (
        utub.utub_creator != USER_ID_FOR_TEST
    ), "Test premise violated: seeded UTub is created by the test user"
    assert (
        utub_url.user_id != USER_ID_FOR_TEST
    ), "Test premise violated: seeded URL was added by the test user"

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url.id)
    assert_visible_css_selector(browser, row_selector)
    url_row = browser.find_element(By.CSS_SELECTOR, row_selector)
    assert len(url_row.find_elements(By.CSS_SELECTOR, ".urlRowSwipeReveal")) == 0

    swipe_url_card_delete(browser, row_selector)

    assert_not_visible_css_selector(browser, ML.ELEMENT_MODAL)
    url_row = browser.find_element(By.CSS_SELECTOR, row_selector)
    row_class = url_row.get_attribute("class") or ""
    assert SWIPE_COMMITTED_CLASS not in row_class
    assert SWIPE_DRAGGING_CLASS not in row_class
