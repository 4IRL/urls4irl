from flask import Flask
import pytest
from playwright.sync_api import Page

from backend.utils.strings.url_strs import DELETE_URL_WARNING
from tests.functional.db_utils import (
    get_url_in_utub,
    get_urls_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as ML
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    get_num_url_rows,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_until_css_property,
    wait_until_hidden,
)
from tests.functional.urls_ui.playwright_utils import (
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
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a deletable URL
    WHEN they swipe the URL row left past the commit threshold
    THEN the row commits (swipe-committed class) and the delete confirmation
        modal opens, proving the real browser commits the drag gesture end-to-end
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    assert_visible_css_selector(page=page, css_selector=row_selector)

    swipe_url_card_delete(page=page, url_row_selector=row_selector)
    wait_until_url_card_swipe_committed(page=page)

    assert_visible_css_selector(page=page, css_selector=ML.ELEMENT_MODAL)
    modal_body = page.locator(HPL.BODY_MODAL).first
    assert modal_body.inner_text() == DELETE_URL_WARNING


def test_url_swipe_commit_confirm_deletes_and_removes_row(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a committed swipe-to-delete gesture with the confirm modal open
    WHEN the user confirms the deletion
    THEN the URL is deleted and its row is removed from the DOM
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    url_row = page.locator(row_selector).first
    init_num_url_rows = get_num_url_rows(page=page)

    swipe_url_card_delete(page=page, url_row_selector=row_selector)
    wait_until_url_card_swipe_committed(page=page)
    assert_visible_css_selector(page=page, css_selector=ML.ELEMENT_MODAL)

    # assert_visible_css_selector only confirms the modal is attached and
    # visible, not that its Bootstrap fade-in transition has finished.
    # Clicking submit mid-transition causes Bootstrap to drop the subsequent
    # modal("hide") call, so the modal never becomes hidden. Gate on the
    # fade-in being fully settled (opacity == 1) before clicking.
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    wait_for_element_to_be_removed(page=page, locator=url_row)
    assert page.locator(row_selector).count() == 0
    assert init_num_url_rows - 1 == get_num_url_rows(page=page)


def test_url_swipe_commit_dismiss_snaps_back_without_deleting(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
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
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    init_num_url_rows = get_num_url_rows(page=page)

    swipe_url_card_delete(page=page, url_row_selector=row_selector)
    wait_until_url_card_swipe_committed(page=page)
    assert_visible_css_selector(page=page, css_selector=ML.ELEMENT_MODAL)

    # assert_visible_css_selector only confirms the modal is attached and
    # visible, not that its Bootstrap fade-in transition has finished.
    # Clicking dismiss mid-transition causes Bootstrap to drop the subsequent
    # modal("hide") call, so the modal never becomes hidden. Gate on the
    # fade-in being fully settled (opacity == 1) before clicking.
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_DISMISS)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    wait_until_url_card_swipe_reset(page=page)
    url_row = page.locator(row_selector).first
    row_class = url_row.get_attribute("class") or ""
    assert SWIPE_COMMITTED_CLASS not in row_class
    assert SWIPE_DRAGGING_CLASS not in row_class
    assert init_num_url_rows == get_num_url_rows(page=page)

    wait_until_css_property(
        page=page,
        css_selector=row_selector,
        css_property="border-bottom-color",
        expected_value=NEUTRAL_ROW_BORDER_COLOR,
    )


def test_url_swipe_dismiss_twice_then_blur_leaves_no_stuck_goto_icon(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two rows that each committed a swipe-to-delete gesture and had the
        confirm modal dismissed
    WHEN focus subsequently leaves a dismissed row (e.g. the user taps
        elsewhere)
    THEN that row's .goToUrlIcon is not left permanently visible (regression
        coverage for a leaked `visible-on-focus` class: the pre-existing
        keyboard-focus handler in cards.ts only clears that class when the
        icon itself blurs — a check designed for real Tab navigation that
        never matches when the swipe module's WCAG focus-return blurs the
        row directly, so the class leaked forever once focus moved on)
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_urls = get_urls_in_utub(app, utub.id)
    assert len(utub_urls) >= 2, "Test premise violated: need 2+ URLs in the UTub"
    first_url, second_url = utub_urls[0], utub_urls[1]

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    first_row_selector = get_url_row_selector(utub_url_id=first_url.id)
    second_row_selector = get_url_row_selector(utub_url_id=second_url.id)

    for row_selector in (first_row_selector, second_row_selector):
        swipe_url_card_delete(page=page, url_row_selector=row_selector)
        wait_until_url_card_swipe_committed(page=page)
        assert_visible_css_selector(page=page, css_selector=ML.ELEMENT_MODAL)
        # assert_visible_css_selector only confirms the modal is attached and
        # visible, not that its Bootstrap fade-in transition has finished.
        # Clicking dismiss mid-transition causes Bootstrap to drop the
        # subsequent modal("hide") call, so the modal never becomes hidden.
        # Gate on the fade-in being fully settled (opacity == 1) before
        # clicking.
        wait_until_css_property(
            page=page,
            css_selector=HPL.HOME_MODAL,
            css_property="opacity",
            expected_value="1",
        )
        wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_DISMISS)
        wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
        wait_until_url_card_swipe_reset(page=page)

    # A tap elsewhere blurs whichever row the WCAG focus-return trigger last
    # focused, the same way a real user would move on after dismissing.
    wait_then_click_element(page=page, css_selector=HPL.MAIN_PANEL)

    for row_selector in (first_row_selector, second_row_selector):
        icon_selector = f"{row_selector} {HPL.GO_TO_URL_ICON}"
        assert_not_visible_css_selector(page=page, css_selector=icon_selector)
        icon = page.locator(icon_selector).first
        assert "visible-on-focus" not in (icon.get_attribute("class") or "")


def test_url_swipe_below_threshold_snaps_back_no_op(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a deletable URL
    WHEN they swipe the row left by a small amount well below the ~35% commit
        threshold (sub-threshold drag)
    THEN the row snaps back to its resting position and does not open the
        confirm modal, proving the real browser only commits once the
        threshold is crossed
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    init_num_url_rows = get_num_url_rows(page=page)

    swipe_url_card_below_threshold(page=page, url_row_selector=row_selector)
    wait_until_url_card_swipe_reset(page=page)

    assert_not_visible_css_selector(page=page, css_selector=ML.ELEMENT_MODAL)
    url_row = page.locator(row_selector).first
    row_class = url_row.get_attribute("class") or ""
    assert SWIPE_COMMITTED_CLASS not in row_class
    assert init_num_url_rows == get_num_url_rows(page=page)


def test_url_tap_to_select_delete_button_still_works(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a deletable URL
    WHEN they tap the row to select it, then tap the existing .urlBtnDelete
    THEN the confirm modal opens exactly as before the swipe gesture was added
        (non-regression of the existing tap-to-select delete flow)
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_url = get_url_in_utub(app, utub.id)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    wait_then_click_element(page=page, css_selector=row_selector)

    # The selected-row padding/transform transition must settle before the
    # delete button's post-select position is stable, otherwise the click
    # lands on a still-animating sibling (e.g. .urlTags) instead of the
    # button — mirrors login_select_utub_select_url_click_delete_get_modal_url.
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    delete_btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}"
    wait_then_click_element(page=page, css_selector=delete_btn_selector)

    assert_visible_css_selector(page=page, css_selector=ML.ELEMENT_MODAL)
    modal_body = page.locator(HPL.BODY_MODAL).first
    assert modal_body.inner_text() == DELETE_URL_WARNING


def test_url_swipe_inert_for_non_deletable_row(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with a URL they cannot delete
        (added by a different member, in a UTub they did not create)
    WHEN they attempt the same left-swipe gesture used to delete a row
    THEN the row is inert — no swipe reveal panel exists, no swipe class is
        applied, and no confirm modal opens
    """
    page = page_mobile_portrait
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
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_selector = get_url_row_selector(utub_url_id=utub_url.id)
    assert_visible_css_selector(page=page, css_selector=row_selector)
    url_row = page.locator(row_selector).first
    assert url_row.locator(".urlRowSwipeReveal").count() == 0

    swipe_url_card_delete(page=page, url_row_selector=row_selector)

    assert_not_visible_css_selector(page=page, css_selector=ML.ELEMENT_MODAL)
    url_row = page.locator(row_selector).first
    row_class = url_row.get_attribute("class") or ""
    assert SWIPE_COMMITTED_CLASS not in row_class
    assert SWIPE_DRAGGING_CLASS not in row_class
