import re
from contextlib import contextmanager
from typing import Iterator, List
from urllib.parse import urlsplit

from flask import Flask
from playwright.sync_api import Page, Request, expect

from tests.functional.locators import GenericPageLocator
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import TrashPanelLocators as TPL
from tests.functional.playwright_utils import (
    click_on_navbar,
    dispatch_pointer_drag,
    login_user_to_home_page,
)

# Drag distance (px) for a committing swipe-right. The armed row's reveal layer
# spans the row (~390px at the 420px page_mobile_portrait viewport), so its 35%
# commit threshold is ~137px; 300px clears it even at the narrowest row.
SWIPE_COMMIT_PX = 300

# Drag distance (px) well below the 35% commit threshold, so the row snaps back.
SWIPE_SNAP_BACK_PX = 60

# Non-zero per-step delay (ms) so the sub-threshold drag stays under the
# 0.5 px/ms fling velocity (60px over 6 steps at 40ms/step is ~0.25 px/ms) and
# only the uncrossed distance threshold governs.
SWIPE_SNAP_BACK_STEP_DELAY_MS = 40

# The swipe yields to the OS back-swipe within this many px of the viewport's
# left edge, so a drag must start further in.
LEFT_EDGE_GUARD_PX = 16
SWIPE_START_INSET_PX = 8

# How long a negative "no request is sent" check waits for a request.
NO_REQUEST_WAIT_MS = 2000

MIN_TOUCH_TARGET_PX = 44

# POST /utubs/<utub_id>/urls/<utub_url_id>/restore (the in-place and destination
# restore; the bulk /urls/restore route never matches).
_RESTORE_URL_PATH = re.compile(r"/utubs/\d+/urls/\d+/restore/?$")
# GET /utubs/<utub_id>: the select-a-UTub fetch (/refresh and sub-routes never match).
_GET_UTUB_INFO_PATH = re.compile(r"/utubs/\d+/?$")


def wait_for_trash_list_loaded(*, page: Page) -> None:
    """Block until the Trash list response has been rendered. The retention notice
    is only revealed by `renderTrashList()`, so it marks "rows are in the DOM"."""
    expect(page.locator(TPL.PANEL)).to_be_visible()
    expect(page.locator("#TrashRetentionNotice")).to_be_visible()


def open_trash(*, page: Page) -> None:
    """Click the deck's Trash entry and wait for the panel and its list."""
    page.locator(TPL.SELECTOR).click()
    wait_for_trash_list_loaded(page=page)


def login_user_and_open_trash(*, app: Flask, page: Page, user_id: int) -> None:
    """Log `user_id` in via session cookie, land on /home, then open Trash."""
    login_user_to_home_page(app=app, page=page, user_id=user_id)
    open_trash(page=page)


def open_trash_mobile(*, page: Page) -> None:
    """Tap the pinned Trash row in the mobile UTubs list and wait for the list."""
    expect(page.locator(TPL.SELECTOR)).to_be_visible()
    page.locator(TPL.SELECTOR).tap()
    wait_for_trash_list_loaded(page=page)


def login_user_and_open_trash_mobile(*, app: Flask, page: Page, user_id: int) -> None:
    """Log `user_id` in on a mobile page (UTubs list first), then tap into Trash."""
    login_user_to_home_page(app=app, page=page, user_id=user_id)
    open_trash_mobile(page=page)


def tap_back_to_utubs(*, page: Page) -> None:
    """Open the hamburger and tap `Back to UTubs`, settling the collapse."""
    click_on_navbar(page=page)
    page.locator(HPL.NAVBAR_UTUB_DECK).tap()
    expect(page.locator(GenericPageLocator.NAVBAR_DROPDOWN)).not_to_have_class(
        re.compile(r"collapsing")
    )


def open_utubs_tab(*, page: Page) -> None:
    """Switch the Trash panel to its UTubs tab."""
    page.locator(TPL.TAB_UTUBS).click()
    expect(page.locator(TPL.TAB_UTUBS)).to_have_attribute("aria-selected", "true")
    expect(page.locator(TPL.PANEL_UTUBS)).to_be_visible()


def _swipe_start_x(*, left: float) -> float:
    """A drag start near the row's left edge but clear of the OS back-swipe zone."""
    return max(left + SWIPE_START_INSET_PX, LEFT_EDGE_GUARD_PX + SWIPE_START_INSET_PX)


def _swipe_trash_row(
    *,
    page: Page,
    row_selector: str,
    distance_px: float,
    step_delay_ms: int | None = None,
) -> None:
    """Drag the row rightward by ``distance_px`` from a safe start point."""
    bounding_box = page.locator(row_selector).first.bounding_box()
    assert bounding_box is not None
    start_x = _swipe_start_x(left=bounding_box["x"])
    start_y = bounding_box["y"] + bounding_box["height"] / 2
    drag_kwargs = {} if step_delay_ms is None else {"step_delay_ms": step_delay_ms}
    dispatch_pointer_drag(
        page=page,
        css_selector=row_selector,
        start_x=start_x,
        end_x=start_x + distance_px,
        start_y=start_y,
        end_y=start_y,
        **drag_kwargs,
    )


def swipe_trash_row_restore(*, page: Page, row_selector: str) -> None:
    """Drag the row rightward by ``SWIPE_COMMIT_PX``, past the commit threshold."""
    _swipe_trash_row(page=page, row_selector=row_selector, distance_px=SWIPE_COMMIT_PX)


def swipe_trash_row_below_threshold(*, page: Page, row_selector: str) -> None:
    """Drag the row rightward by ``SWIPE_SNAP_BACK_PX`` slowly enough that neither
    the distance nor the fling threshold is crossed, so it snaps back."""
    _swipe_trash_row(
        page=page,
        row_selector=row_selector,
        distance_px=SWIPE_SNAP_BACK_PX,
        step_delay_ms=SWIPE_SNAP_BACK_STEP_DELAY_MS,
    )


def wait_until_trash_row_swipe_reset(*, page: Page, timeout: int = 10) -> None:
    """Wait until no `.trashRow` carries `swipe-dragging` / `swipe-committed` and
    no row content keeps an inline transform (snapped back, removed or replaced)."""
    page.wait_for_function(
        """(rowSelector) => Array.from(document.querySelectorAll(rowSelector)).every(
            (row) =>
                !row.classList.contains("swipe-dragging") &&
                !row.classList.contains("swipe-committed") &&
                Array.from(row.querySelectorAll(".trashRowContent")).every(
                    (content) => content.style.transform === ""
                )
        )""",
        arg=TPL.ROWS_URLS,
        timeout=timeout * 1000,
    )


@contextmanager
def _track_requests(
    *, page: Page, method: str, path_pattern: re.Pattern[str]
) -> Iterator[List[Request]]:
    """Collect the requests with ``method`` whose URL path matches ``path_pattern``
    while the context is active (other traffic is ignored)."""
    collected: List[Request] = []

    def collect(request: Request) -> None:
        if request.method == method and path_pattern.search(urlsplit(request.url).path):
            collected.append(request)

    page.on("request", collect)
    try:
        yield collected
    finally:
        page.remove_listener("request", collect)


@contextmanager
def track_restore_requests(*, page: Page) -> Iterator[List[Request]]:
    """Track the single-URL restore POSTs the page sends. A negative check reads:
    act, ``page.wait_for_timeout(NO_REQUEST_WAIT_MS)``, assert the list is empty."""
    with _track_requests(
        page=page, method="POST", path_pattern=_RESTORE_URL_PATH
    ) as restore_requests:
        yield restore_requests


@contextmanager
def track_get_utub_info_requests(*, page: Page) -> Iterator[List[Request]]:
    """Track the `getUTubInfo` GETs (`/utubs/<id>`) the page sends."""
    with _track_requests(
        page=page, method="GET", path_pattern=_GET_UTUB_INFO_PATH
    ) as info_requests:
        yield info_requests
