from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, Route, expect

from backend.models.utub_members import Member_Role
from backend.utils.strings.trash_strs import TRASH_UI
from backend.utils.strings.url_strs import URL_REVIVED_FROM_TRASH
from backend.utils.strings.utub_strs import (
    MOBILE_PANEL_ANNOUNCEMENT_TRASH,
    UTUB_IS_LOCKED,
)
from tests.functional.db_utils import (
    get_utub_this_user_did_not_create,
    set_member_role_in_utub,
    set_utub_locked_state,
    trash_utub,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import TrashPanelLocators as TPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    current_base_url,
    login_user_to_home_page,
    wait_for_modal_ready,
)
from tests.functional.trash_ui.db_utils import (
    add_url_to_utub,
    create_utub_as_creator,
    purge_utub_url_row,
    seed_trashed_urls,
)
from tests.functional.trash_ui.playwright_utils import (
    MIN_TOUCH_TARGET_PX,
    NO_REQUEST_WAIT_MS,
    login_user_and_open_trash_mobile,
    open_trash_mobile,
    swipe_trash_row_below_threshold,
    swipe_trash_row_restore,
    tap_back_to_utubs,
    track_get_utub_info_requests,
    track_restore_requests,
    wait_for_trash_list_loaded,
    wait_until_trash_row_swipe_reset,
)

pytestmark = [pytest.mark.trash_ui, pytest.mark.mobile_ui]

USER_ID: int = 1
SWIPE_COMMITTED_CLASS = "swipe-committed"
SWIPE_DRAGGING_CLASS = "swipe-dragging"
SWIPE_FOCUS_RETURN_CLASS = "swipe-focus-return"
TRANSPARENT = "rgba(0, 0, 0, 0)"
RESTORE_ROUTE = re.compile(r"/utubs/\d+/urls/\d+/restore$")
ACTIVE_CLASS = re.compile(r"(^|\s)active(\s|$)")
HELD_ROUTE_POLL_MS = 25
HELD_ROUTE_MAX_POLLS = 400
# Longer than UTUB_REFRESH_MIN_INTERVAL_MS (30_000) so the next refocus is due.
REFRESH_INTERVAL_PASSED_MS = 31_000
CROSS_SEARCH_QUERY = "trash"
CROSS_SEARCH_FIELDS = ["url", "title", "tag"]


@pytest.fixture(autouse=True)
def seeded_users(page_mobile_portrait: Page, create_test_users):
    """Every test seeds its own UTubs and URLs, but needs the mock users to exist.

    Depends on ``page_mobile_portrait`` so it seeds AFTER the page fixture's
    database wipe."""


def _url_row(utub_url_id: int) -> str:
    return f"{TPL.ROWS_URLS}[data-utub-url-id='{utub_url_id}']"


def _confirm_in_modal(page: Page) -> None:
    wait_for_modal_ready(page=page, modal_selector=TPL.CONFIRM_MODAL)
    page.locator(TPL.CONFIRM_MODAL_SUBMIT).tap()
    expect(page.locator(TPL.CONFIRM_MODAL)).to_be_hidden()


def _assert_swipe_classes_absent(row: Locator) -> None:
    expect(row).not_to_have_class(re.compile(rf"\b{SWIPE_COMMITTED_CLASS}\b"))
    expect(row).not_to_have_class(re.compile(rf"\b{SWIPE_DRAGGING_CLASS}\b"))


def _assert_touch_target(locator: Locator) -> None:
    """Every element the locator matches is at least 44x44 CSS px."""
    elements = locator.all()
    assert elements, f"no element matched {locator}"
    for element in elements:
        box = element.bounding_box()
        assert box is not None, f"{locator} has no box"
        assert (
            box["width"] >= MIN_TOUCH_TARGET_PX and box["height"] >= MIN_TOUCH_TARGET_PX
        ), f"{locator} is {box['width']}x{box['height']}, under {MIN_TOUCH_TARGET_PX}px"


def _hold_restore_requests(page: Page) -> list[Route]:
    """Intercept restore POSTs and park them; the test resumes them explicitly."""
    held: list[Route] = []
    page.route(RESTORE_ROUTE, lambda route: held.append(route))
    return held


def _wait_for_held_route(page: Page, held: list[Route]) -> Route:
    for _ in range(HELD_ROUTE_MAX_POLLS):
        if held:
            return held[0]
        page.wait_for_timeout(HELD_ROUTE_POLL_MS)
    raise AssertionError("the restore request was never sent")


def _seed_orphan_row(app: Flask, name: str, url_string: str) -> int:
    """A URL whose origin UTub is itself in Trash; returns its ``Utub_Urls`` id."""
    utub_id = create_utub_as_creator(app, USER_ID, name)
    utub_url_id = add_url_to_utub(app, utub_id, USER_ID, url_string, f"{name} URL")
    trash_utub(app, utub_id, USER_ID)
    return utub_url_id


def test_tapping_pinned_row_opens_trash_and_hides_decks(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN a mobile user on the UTubs list with something in Trash
    WHEN they tap the pinned Trash row
    THEN the Trash panel replaces the UTub and URL decks and the URL is /home?view=trash
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile open utub")
    seed_trashed_urls(app, utub_id, 1, "open")
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)
    expect(page.locator(TPL.LEFT_PANEL)).to_be_visible()

    open_trash_mobile(page=page)

    expect(page.locator(TPL.PANEL)).to_be_visible()
    expect(page.locator(TPL.LEFT_PANEL)).to_be_hidden()
    expect(page.locator(HPL.URL_DECK)).to_be_hidden()
    expect(page.locator(TPL.MEMBER_DECK)).to_be_hidden()
    expect(page.locator(TPL.SELECTOR)).to_have_attribute("aria-current", "page")
    expect(page).to_have_url(
        re.compile(rf"/home\?{TRASH_UI.VIEW_QUERY_PARAM}={TRASH_UI.TRASH_VIEW}$")
    )


def test_back_to_utubs_shows_list_and_browser_back_returns_to_trash(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN Trash is open on mobile
    WHEN the user taps Back to UTubs, then presses the browser Back
    THEN the UTubs list shows (Trash closed, plain /home), and Back reopens Trash
        and announces "Now showing Trash"
    """
    page = page_mobile_portrait
    app = provide_app
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)

    tap_back_to_utubs(page=page)

    expect(page.locator(TPL.PANEL)).to_be_hidden()
    expect(page.locator(TPL.LEFT_PANEL)).to_be_visible()
    expect(page.locator(TPL.SELECTOR)).not_to_have_class(ACTIVE_CLASS)
    expect(page).to_have_url(re.compile(r"/home$"))

    page.go_back()

    wait_for_trash_list_loaded(page=page)
    expect(page.locator(TPL.LEFT_PANEL)).to_be_hidden()
    expect(page.locator(HPL.MOBILE_PANEL_ANNOUNCEMENT)).to_have_text(
        MOBILE_PANEL_ANNOUNCEMENT_TRASH
    )


def test_back_to_utubs_then_pinned_row_reopens_trash(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN the user left Trash with Back to UTubs
    WHEN they tap the pinned Trash row again
    THEN Trash reopens (the entry is not stuck active)
    """
    page = page_mobile_portrait
    app = provide_app
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)
    tap_back_to_utubs(page=page)
    expect(page.locator(TPL.PANEL)).to_be_hidden()

    open_trash_mobile(page=page)

    expect(page.locator(TPL.LEFT_PANEL)).to_be_hidden()
    expect(page.locator(TPL.SELECTOR)).to_have_class(ACTIVE_CLASS)


def test_reload_stays_in_trash_and_forward_announces_it(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN Trash is open on mobile
    WHEN the page reloads, then the user goes Back and Forward
    THEN the reload stays in Trash, Back shows the UTubs list, and Forward onto the
        {trash:true} entry reopens Trash and announces "Now showing Trash"
    """
    page = page_mobile_portrait
    app = provide_app
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)

    page.reload()
    wait_for_trash_list_loaded(page=page)
    expect(page.locator(TPL.LEFT_PANEL)).to_be_hidden()

    page.go_back()
    expect(page.locator(TPL.PANEL)).to_be_hidden()
    expect(page.locator(TPL.LEFT_PANEL)).to_be_visible()

    page.go_forward()
    wait_for_trash_list_loaded(page=page)
    expect(page.locator(TPL.LEFT_PANEL)).to_be_hidden()
    expect(page.locator(HPL.MOBILE_PANEL_ANNOUNCEMENT)).to_have_text(
        MOBILE_PANEL_ANNOUNCEMENT_TRASH
    )


@pytest.mark.parametrize(
    "query",
    [
        "view=trash",
        "panel=trash",
        "UTubID={utub_id}&panel=trash",
        "UTubID={utub_id}&view=trash",
    ],
)
def test_deep_links_normalize_to_trash_view_without_loading_a_utub(
    page_mobile_portrait: Page, provide_app: Flask, query: str
):
    """
    GIVEN a logged-in mobile user
    WHEN they cold-load a Trash deep link (with or without a UTubID)
    THEN they end at /home?view=trash with Trash open, no UTub selected and no
        getUTubInfo request sent
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash deep link utub")
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)
    base_url = current_base_url(page=page)

    with track_get_utub_info_requests(page=page) as info_requests:
        page.goto(f"{base_url}/home?{query.format(utub_id=utub_id)}")
        wait_for_trash_list_loaded(page=page)

        expect(page).to_have_url(
            re.compile(rf"/home\?{TRASH_UI.VIEW_QUERY_PARAM}={TRASH_UI.TRASH_VIEW}$")
        )
        expect(page.locator(TPL.LEFT_PANEL)).to_be_hidden()
        expect(page.locator(f"{HPL.SELECTORS_UTUB}.active")).to_have_count(0)
        assert info_requests == []


def test_tap_restore_removes_row_announces_and_focuses_next_row(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN two trashed URLs on mobile
    WHEN the user taps Restore on the first
    THEN the row leaves, the Trash banner announces it, focus lands on the next
        row with a visible ring, and the badge drops
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile restore utub")
    first_id, second_id = seed_trashed_urls(app, utub_id, 2, "mrestore")
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(2)

    page.locator(f"{_url_row(first_id)} {TPL.BUTTON_RESTORE}").tap()

    expect(page.locator(_url_row(first_id))).to_have_count(0)
    expect(page.locator(TPL.OUTCOME_BANNER)).to_be_visible()
    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(URL_REVIVED_FROM_TRASH)
    next_row = page.locator(_url_row(second_id))
    expect(next_row).to_be_focused()
    expect(next_row).not_to_have_class(re.compile(rf"\b{SWIPE_FOCUS_RETURN_CLASS}\b"))
    expect(next_row).not_to_have_css("border-top-color", TRANSPARENT)
    expect(page.locator(TPL.SELECTOR_COUNT)).to_have_text("(1)")


def test_tap_delete_forever_confirms_in_modal_and_removes_row(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN two trashed URLs on mobile
    WHEN the user taps Delete forever and confirms in the modal
    THEN the row is purged, the banner says so and focus moves to the next row
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile purge utub")
    first_id, second_id = seed_trashed_urls(app, utub_id, 2, "mpurge")
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)

    page.locator(f"{_url_row(first_id)} {TPL.BUTTON_PURGE}").tap()
    _confirm_in_modal(page)

    expect(page.locator(_url_row(first_id))).to_have_count(0)
    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(TRASH_UI.URL_PURGED)
    expect(page.locator(_url_row(second_id))).to_be_focused()


def test_swipe_right_commit_restores_row_without_ring_on_next_row(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN two armed trashed URL rows on mobile
    WHEN the user swipes the first right past the commit threshold
    THEN it is restored (no modal): the row leaves, the Trash banner announces it,
        the badge drops, and the next row takes focus with the focus ring hidden
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile swipe utub")
    first_id, second_id = seed_trashed_urls(app, utub_id, 2, "mswipe")
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)
    expect(page.locator(f"{_url_row(first_id)}{TPL.ROW_SWIPEABLE}")).to_have_count(1)

    swipe_trash_row_restore(page=page, row_selector=_url_row(first_id))

    expect(page.locator(_url_row(first_id))).to_have_count(0)
    expect(page.locator(TPL.CONFIRM_MODAL)).to_be_hidden()
    expect(page.locator(TPL.OUTCOME_BANNER)).to_be_visible()
    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(URL_REVIVED_FROM_TRASH)
    expect(page.locator(TPL.SELECTOR_COUNT)).to_have_text("(1)")
    next_row = page.locator(_url_row(second_id))
    expect(next_row).to_be_focused()
    expect(next_row).to_have_class(re.compile(rf"\b{SWIPE_FOCUS_RETURN_CLASS}\b"))
    expect(next_row).to_have_css("border-top-color", TRANSPARENT)
    wait_until_trash_row_swipe_reset(page=page)


def test_below_threshold_swipe_snaps_back_without_a_request(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN an armed trashed URL row on mobile
    WHEN the user drags it right by less than the commit threshold
    THEN the row snaps back unchanged and no restore request is sent
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile snap utub")
    (url_id,) = seed_trashed_urls(app, utub_id, 1, "msnap")
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)
    row = page.locator(_url_row(url_id))

    with track_restore_requests(page=page) as restore_requests:
        swipe_trash_row_below_threshold(page=page, row_selector=_url_row(url_id))
        wait_until_trash_row_swipe_reset(page=page)
        page.wait_for_timeout(NO_REQUEST_WAIT_MS)
        assert restore_requests == []

    expect(row).to_have_count(1)
    _assert_swipe_classes_absent(row)
    expect(page.locator(TPL.OUTCOME_BANNER)).to_be_hidden()


def test_swipe_on_locked_origin_row_does_nothing(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN a trashed URL whose origin UTub is locked
    WHEN the user swipes the row right
    THEN the "Origin UTub locked" chip stays, the row is unarmed and unchanged, and
        no restore request is sent
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile locked utub")
    (url_id,) = seed_trashed_urls(app, utub_id, 1, "mlocked")
    set_utub_locked_state(app, utub_id, True)
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)
    row = page.locator(_url_row(url_id))
    expect(row.locator(TPL.CHIP_ORIGIN)).to_have_text(TRASH_UI.ORIGIN_LOCKED)
    expect(row.locator(TPL.ROW_SWIPE_REVEAL)).to_have_count(0)

    with track_restore_requests(page=page) as restore_requests:
        swipe_trash_row_restore(page=page, row_selector=_url_row(url_id))
        page.wait_for_timeout(NO_REQUEST_WAIT_MS)
        assert restore_requests == []

    expect(row).to_have_count(1)
    expect(row.locator(TPL.CHIP_ORIGIN)).to_be_visible()
    _assert_swipe_classes_absent(row)
    expect(page.locator(TPL.OUTCOME_BANNER)).to_be_hidden()


def test_swipe_on_orphan_row_has_no_reveal_and_sends_nothing(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN a trashed URL whose origin UTub is itself in Trash (an orphan row)
    WHEN the user swipes the row right
    THEN there is no reveal layer and no restore request is sent
    """
    page = page_mobile_portrait
    app = provide_app
    url_id = _seed_orphan_row(
        app, "Trash mobile orphan swipe", "https://orphan.example/"
    )
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)
    row = page.locator(_url_row(url_id))
    expect(row).to_have_count(1)
    expect(row.locator(TPL.ROW_SWIPE_REVEAL)).to_have_count(0)

    with track_restore_requests(page=page) as restore_requests:
        swipe_trash_row_restore(page=page, row_selector=_url_row(url_id))
        page.wait_for_timeout(NO_REQUEST_WAIT_MS)
        assert restore_requests == []

    expect(row).to_have_count(1)
    _assert_swipe_classes_absent(row)


def test_orphan_row_restore_opens_destination_picker(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN an orphan trashed URL and a live UTub
    WHEN the user taps "Restore to…" on it
    THEN the destination picker opens
    """
    page = page_mobile_portrait
    app = provide_app
    url_id = _seed_orphan_row(
        app, "Trash mobile orphan picker", "https://pick.example/"
    )
    create_utub_as_creator(app, USER_ID, "Trash mobile picker dest")
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)

    restore_button = page.locator(f"{_url_row(url_id)} {TPL.BUTTON_RESTORE}")
    expect(restore_button).to_have_text(TRASH_UI.RESTORE_TO)
    restore_button.tap()

    expect(page.locator(TPL.DESTINATION_PICKER)).to_be_visible()
    expect(page.locator(TPL.DESTINATION_OPTION)).to_have_count(1)


def test_touch_targets_are_at_least_44px(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN the mobile UTubs list and Trash panel with a live row and an orphan row
    WHEN their controls are measured
    THEN the pinned row, both tabs, both row buttons on each row, Empty trash and the
        destination options are all at least 44x44 px
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile target utub")
    seed_trashed_urls(app, utub_id, 1, "mtarget")
    orphan_id = _seed_orphan_row(
        app, "Trash mobile target orphan", "https://t.example/"
    )
    create_utub_as_creator(app, USER_ID, "Trash mobile target dest")
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)
    _assert_touch_target(page.locator(TPL.SELECTOR))

    open_trash_mobile(page=page)

    _assert_touch_target(page.locator(TPL.TAB_URLS))
    _assert_touch_target(page.locator(TPL.TAB_UTUBS))
    _assert_touch_target(page.locator(TPL.BUTTON_EMPTY))
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(2)
    _assert_touch_target(page.locator(f"{TPL.ROWS_URLS} {TPL.BUTTON_RESTORE}"))
    _assert_touch_target(page.locator(f"{TPL.ROWS_URLS} {TPL.BUTTON_PURGE}"))

    page.locator(f"{_url_row(orphan_id)} {TPL.BUTTON_RESTORE}").tap()
    expect(page.locator(TPL.DESTINATION_PICKER)).to_be_visible()
    _assert_touch_target(page.locator(TPL.DESTINATION_OPTION_ANY))


def test_tab_row_does_not_overflow_at_320px(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN the Trash panel with a populated URLs tab on mobile
    WHEN the viewport narrows to 320px
    THEN the tab row does not scroll horizontally
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile narrow utub")
    seed_trashed_urls(app, utub_id, 12, "mnarrow")
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)

    page.set_viewport_size({"width": 320, "height": 700})

    expect(page.locator(TPL.PANEL)).to_be_visible()
    scroll_width, client_width = page.locator(TPL.TAB_ROW).evaluate(
        "(el) => [el.scrollWidth, el.clientWidth]"
    )
    assert scroll_width <= client_width, (
        f"tab row scrolls: {scroll_width}>{client_width}"
    )


def test_resizing_into_mobile_keeps_trash_and_its_banner(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN a restore done at desktop width so a banner shows
    WHEN the viewport narrows to 420px with Trash open
    THEN Trash stays visible (the mobile panel switch applies) with the same banner
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile resize utub")
    first_id, _ = seed_trashed_urls(app, utub_id, 2, "mresize")
    page.set_viewport_size({"width": 1280, "height": 900})
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)
    page.locator(TPL.SELECTOR).click()
    wait_for_trash_list_loaded(page=page)
    page.locator(f"{_url_row(first_id)} {TPL.BUTTON_RESTORE}").click()
    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(URL_REVIVED_FROM_TRASH)

    page.set_viewport_size({"width": 420, "height": 900})

    expect(page.locator(TPL.PANEL)).to_be_visible()
    expect(page.locator(TPL.LEFT_PANEL)).to_be_hidden()
    expect(page.locator(HPL.URL_DECK)).to_be_hidden()
    expect(page.locator(TPL.OUTCOME_BANNER)).to_be_visible()
    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(URL_REVIVED_FROM_TRASH)


def test_armed_row_keeps_desktop_layout_and_behaviour_at_1280px(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN an armed trashed URL row at a 1280px viewport
    WHEN it is inspected, tabbed through, swiped and its Restore is clicked
    THEN the content layer sits untransformed over the row, Tab goes Restore then
        Delete forever, both buttons carry an icon and label, a swipe sends nothing,
        and the click restores the row
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash desktop layout utub")
    (url_id,) = seed_trashed_urls(app, utub_id, 1, "mdesk")
    page.set_viewport_size({"width": 1280, "height": 900})
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)
    page.locator(TPL.SELECTOR).click()
    wait_for_trash_list_loaded(page=page)
    row = page.locator(_url_row(url_id))
    content = row.locator(TPL.ROW_SWIPE_CONTENT)
    restore_button = row.locator(TPL.BUTTON_RESTORE)
    purge_button = row.locator(TPL.BUTTON_PURGE)

    row_box = row.bounding_box()
    content_box = content.bounding_box()
    assert row_box is not None and content_box is not None
    assert row_box["x"] <= content_box["x"] <= row_box["x"] + 6
    assert content_box["width"] >= row_box["width"] - 12
    expect(content).to_have_css("transform", "none")
    for button, label in (
        (restore_button, TRASH_UI.RESTORE),
        (purge_button, TRASH_UI.DELETE_FOREVER),
    ):
        expect(button.locator("svg")).to_have_count(1)
        expect(button).to_have_text(label)

    restore_button.focus()
    page.keyboard.press("Tab")
    expect(purge_button).to_be_focused()

    with track_restore_requests(page=page) as restore_requests:
        swipe_trash_row_restore(page=page, row_selector=_url_row(url_id))
        page.wait_for_timeout(NO_REQUEST_WAIT_MS)
        assert restore_requests == []
    expect(row).to_have_count(1)

    restore_button.click()
    expect(row).to_have_count(0)
    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(URL_REVIVED_FROM_TRASH)


def test_failed_swipe_restore_shows_partial_banner_and_unsticks_row(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN armed rows and a restore request that fails with a locked-UTub 403
    WHEN the user swipe-commits a row
    THEN the partial "locked" banner shows and no row is left translated or committed
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile failed swipe utub")
    first_id, _ = seed_trashed_urls(app, utub_id, 2, "mfail")
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)
    page.route(
        RESTORE_ROUTE,
        lambda route: route.fulfill(
            status=403,
            content_type="application/json",
            body=json.dumps({"message": UTUB_IS_LOCKED, "status": "Failure"}),
        ),
    )

    swipe_trash_row_restore(page=page, row_selector=_url_row(first_id))

    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(TRASH_UI.LOCKED)
    wait_until_trash_row_swipe_reset(page=page)
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(2)
    _assert_swipe_classes_absent(page.locator(_url_row(first_id)))


def test_swipe_restore_of_row_purged_elsewhere_reports_not_in_trash(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN a listed armed row that was purged server-side afterwards
    WHEN the user swipe-commits it (the real 404 comes back)
    THEN the banner says it is no longer in Trash and the list refreshes without it
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile stale swipe utub")
    stale_id, other_id = seed_trashed_urls(app, utub_id, 2, "mstale")
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)
    expect(page.locator(TPL.ROWS_URLS)).to_have_count(2)
    purge_utub_url_row(app, stale_id)

    swipe_trash_row_restore(page=page, row_selector=_url_row(stale_id))

    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(TRASH_UI.NOT_IN_TRASH)
    expect(page.locator(_url_row(stale_id))).to_have_count(0)
    expect(page.locator(_url_row(other_id))).to_have_count(1)
    wait_until_trash_row_swipe_reset(page=page)


@pytest.mark.parametrize("via_swipe", [True, False], ids=["swipe", "tap"])
def test_stale_armed_row_whose_origin_was_trashed_becomes_orphan(
    page_mobile_portrait: Page, provide_app: Flask, via_swipe: bool
):
    """
    GIVEN a listed armed row whose origin UTub is then trashed server-side
    WHEN the user swipe-restores it (or taps its Restore button)
    THEN the 400 does not navigate to the error page; a partial "origin unavailable"
        banner shows, the list reloads and the row is now an orphan whose Restore
        opens the destination picker, with no swipe-dragging left
    """
    page = page_mobile_portrait
    app = provide_app
    origin_id = create_utub_as_creator(app, USER_ID, "Trash mobile stale origin")
    (url_id,) = seed_trashed_urls(app, origin_id, 1, "morigin")
    create_utub_as_creator(app, USER_ID, "Trash mobile stale destination")
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)
    row = page.locator(_url_row(url_id))
    restore_button = row.locator(TPL.BUTTON_RESTORE)
    expect(restore_button).to_have_text(TRASH_UI.RESTORE)
    trash_utub(app, origin_id, USER_ID)

    if via_swipe:
        swipe_trash_row_restore(page=page, row_selector=_url_row(url_id))
    else:
        restore_button.tap()

    expect(page.locator(TPL.OUTCOME_BANNER)).to_contain_text(
        TRASH_UI.ORIGIN_UNAVAILABLE
    )
    expect(page).to_have_url(
        re.compile(rf"/home\?{TRASH_UI.VIEW_QUERY_PARAM}={TRASH_UI.TRASH_VIEW}$")
    )
    expect(restore_button).to_have_text(TRASH_UI.RESTORE_TO)
    expect(row.locator(TPL.ROW_SWIPE_REVEAL)).to_have_count(0)
    expect(page.locator(f"{TPL.ROWS_URLS}.{SWIPE_DRAGGING_CLASS}")).to_have_count(0)
    _assert_swipe_classes_absent(row)

    restore_button.tap()
    expect(page.locator(TPL.DESTINATION_PICKER)).to_be_visible()


@pytest.mark.parametrize("failure", ["inaccessible", "rejected"])
def test_popstate_onto_unusable_utub_entry_closes_trash(
    page_mobile_portrait: Page, provide_app: Flask, failure: str
):
    """
    GIVEN a {UTubID, mobilePanel:"utubs"} history entry the user cannot use (a UTub
        since moved to Trash, or one whose getUTubInfo is rejected), with Trash open
        on top of it
    WHEN the user goes Back
    THEN Trash is closed (not stuck active), the UTubs list shows, and tapping the
        pinned Trash row reopens it
    """
    page = page_mobile_portrait
    app = provide_app
    if failure == "inaccessible":
        target_id = create_utub_as_creator(app, USER_ID, "Trash mobile gone utub")
        trash_utub(app, target_id, USER_ID)
    else:
        target_id = create_utub_as_creator(app, USER_ID, "Trash mobile broken utub")
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)
    expect(page.locator(TPL.LEFT_PANEL)).to_be_visible()
    page.evaluate(
        """(utubID) => window.history.pushState(
            { UTubID: utubID, mobilePanel: "utubs" }, "", "/home")""",
        target_id,
    )
    open_trash_mobile(page=page)
    if failure == "rejected":
        page.route(
            lambda url: urlsplit(url).path == f"/utubs/{target_id}",
            lambda route: route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"status": "Failure", "message": "boom"}),
            ),
        )

    page.go_back()

    expect(page.locator(TPL.PANEL)).to_be_hidden()
    expect(page.locator(TPL.SELECTOR)).not_to_have_class(ACTIVE_CLASS)
    expect(page.locator(TPL.LEFT_PANEL)).to_be_visible()

    open_trash_mobile(page=page)
    expect(page.locator(TPL.LEFT_PANEL)).to_be_hidden()


def test_permission_refresh_with_trash_open_does_not_reshow_trash(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a member's refresh-on-focus request carrying a role change is in flight
        while they open Trash on mobile (opening Trash clears the active UTub, so
        the permission fallback can never run over it)
    WHEN the refresh response lands
    THEN the permission fallback is not applied and Trash stays open, not
        re-shown or replaced by a UTub panel
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_did_not_create(app, USER_ID)
    set_member_role_in_utub(app, USER_ID, utub.id, Member_Role.MEMBER)
    page.clock.install()
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID, utub_id=utub.id
    )
    # The mobile login helper only clicks the UTub. Wait for it to render: a late
    # UTUB_SELECTED resets the refresh debounce clock after the fast-forward below.
    expect(page.locator(HPL.SELECTOR_SELECTED_UTUB)).to_have_count(1)
    expect(page.locator(HPL.URL_DECK)).to_be_visible()
    held: list[Route] = []
    page.route(
        re.compile(rf"/utubs/{utub.id}/refresh$"), lambda route: held.append(route)
    )

    set_member_role_in_utub(app, USER_ID, utub.id, Member_Role.CO_CREATOR)
    page.clock.fast_forward(REFRESH_INTERVAL_PASSED_MS)
    # A synthetic visibilitychange keeps visibilityState "visible" in headless
    # Chromium, so the window blur -> focus pair is the portable trigger.
    page.evaluate(
        """() => {
            window.dispatchEvent(new Event('blur'));
            window.dispatchEvent(new Event('focus'));
        }"""
    )
    route = _wait_for_held_route(page, held)
    tap_back_to_utubs(page=page)
    open_trash_mobile(page=page)

    with page.expect_response(re.compile(rf"/utubs/{utub.id}/refresh$")):
        route.continue_()

    expect(page.locator(TPL.PANEL)).to_be_visible()
    expect(page.locator(TPL.SELECTOR)).to_have_class(ACTIVE_CLASS)
    expect(page.locator(TPL.LEFT_PANEL)).to_be_hidden()
    expect(page.locator(HPL.URL_DECK)).to_be_hidden()
    expect(page.locator(HPL.SELECTOR_SELECTED_UTUB)).to_have_count(0)


def test_popstate_onto_cross_search_entry_closes_trash_and_restores_search(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN a {crossSearch} history entry beneath an open Trash panel on mobile
    WHEN the user goes Back onto it
    THEN Trash closes and the cross-UTub search view is restored with its query
    """
    page = page_mobile_portrait
    app = provide_app
    create_utub_as_creator(app, USER_ID, "Trash mobile search utub")
    login_user_to_home_page(app=app, page=page, user_id=USER_ID)
    expect(page.locator(TPL.LEFT_PANEL)).to_be_visible()
    page.evaluate(
        """({ query, fields }) => window.history.pushState(
            { crossSearch: { query, fields } }, "", "/home")""",
        {"query": CROSS_SEARCH_QUERY, "fields": CROSS_SEARCH_FIELDS},
    )
    open_trash_mobile(page=page)

    page.go_back()

    expect(page.locator(TPL.PANEL)).to_be_hidden()
    expect(page.locator(TPL.SELECTOR)).not_to_have_class(ACTIVE_CLASS)
    expect(page.locator(HPL.CROSS_SEARCH_MODE).first).to_be_visible()
    expect(page.locator(HPL.CROSS_SEARCH_INPUT)).to_have_value(CROSS_SEARCH_QUERY)


def test_restore_response_after_leaving_trash_writes_no_banner_or_focus(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN a swipe-committed restore whose response is still in flight
    WHEN the user taps Back to UTubs and the response then lands
    THEN no banner is written, focus stays on the pinned Trash row, and reopening
        Trash shows no banner
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile late utub")
    first_id, _ = seed_trashed_urls(app, utub_id, 2, "mlate")
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)
    held = _hold_restore_requests(page)

    swipe_trash_row_restore(page=page, row_selector=_url_row(first_id))
    route = _wait_for_held_route(page, held)
    # `ajaxCall` times out after 1s, so leave Trash programmatically (the hamburger
    # tap path is covered above) to land the late response inside that window.
    page.evaluate(
        "(selector) => document.querySelector(selector).click()", HPL.NAVBAR_UTUB_DECK
    )
    expect(page.locator(TPL.PANEL)).to_be_hidden()

    # The follow-up count refresh (GET /utubs) runs after the banner/focus code,
    # so its response marks the restore completion handler as done.
    with page.expect_response(
        lambda response: (
            response.request.method == "GET" and urlsplit(response.url).path == "/utubs"
        )
    ):
        route.continue_()

    expect(page.locator(TPL.SELECTOR)).to_be_focused()
    expect(page.locator(TPL.PANEL)).to_be_hidden()

    open_trash_mobile(page=page)
    expect(page.locator(TPL.OUTCOME_BANNER)).to_be_hidden()


def test_trailing_click_after_committed_swipe_fires_no_row_action(
    page_mobile_portrait: Page, provide_app: Flask
):
    """
    GIVEN two armed rows and a click on the second row's Delete forever delivered
        right after the first row's swipe commits (the finger-lift click)
    WHEN the swipe's restore completes
    THEN that click was swallowed (no confirm modal), and the next real tap opens it
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = create_utub_as_creator(app, USER_ID, "Trash mobile trailing utub")
    first_id, second_id = seed_trashed_urls(app, utub_id, 2, "mtrail")
    login_user_and_open_trash_mobile(app=app, page=page, user_id=USER_ID)
    # Fires inside the same pointerup dispatch that commits the swipe, so it lands
    # well within the trailing-click suppression window.
    page.evaluate(
        """(purgeSelector) => document.addEventListener(
            "pointerup",
            () => document.querySelector(purgeSelector).click(),
            { once: true }
        )""",
        f"{_url_row(second_id)} {TPL.BUTTON_PURGE}",
    )

    swipe_trash_row_restore(page=page, row_selector=_url_row(first_id))

    expect(page.locator(_url_row(first_id))).to_have_count(0)
    expect(page.locator(TPL.CONFIRM_MODAL)).to_be_hidden()
    expect(page.locator(_url_row(second_id))).to_have_count(1)

    page.locator(f"{_url_row(second_id)} {TPL.BUTTON_PURGE}").tap()
    wait_for_modal_ready(page=page, modal_selector=TPL.CONFIRM_MODAL)
