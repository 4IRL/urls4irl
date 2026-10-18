from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend import db
from backend.models.urls import Urls
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_panel_visibility_mobile
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    get_num_url_rows,
    wait_for_element_to_be_removed,
    wait_then_click_element,
)
from tests.functional.urls_ui.playwright_utils import (
    bulk_delete_selected,
    enter_multi_select_and_select_urls,
)

pytestmark = [pytest.mark.urls_ui, pytest.mark.mobile_ui]

USER_ID_FOR_TEST = 1

# Coarse-pointer 44px touch target minus a 1px rounding tolerance (2.75rem tall).
_MIN_TOUCH_TARGET_PX = 43


def _seed_url_in_utub(
    *, app: Flask, utub_id: int, user_id: int, url_string: str, url_title: str
) -> int:
    """Insert a globally-unique URL + a `Utub_Urls` row (authored by `user_id`)
    into the given UTub. Returns the new utub_url_id."""
    with app.app_context():
        raw_url: Urls | None = Urls.query.filter(Urls.url_string == url_string).first()
        if raw_url is None:
            raw_url = Urls(normalized_url=url_string, current_user_id=user_id)
            db.session.add(raw_url)
            db.session.flush()
        new_utub_url = Utub_Urls(
            utub_id=utub_id,
            url_id=raw_url.id,
            user_id=user_id,
            url_title=url_title,
        )
        db.session.add(new_utub_url)
        db.session.flush()
        new_id = new_utub_url.id
        db.session.commit()
        return new_id


def _utub_url_row_is_live(*, app: Flask, utub_url_id: int) -> bool:
    """True when the row exists and has not been trashed (deleted_at is NULL)."""
    with app.app_context():
        row = Utub_Urls.query.get(utub_url_id)
        return row is not None and not row.is_trashed


def test_mobile_bulk_delete_bottom_drawer_deletes_and_shows_toast(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user with two deletable URLs selected in multi-select mode
    WHEN they tap the bottom drawer's Delete action (no confirm step)
    THEN the drawer Delete action meets the 44px touch target, both rows are
        removed, the Undo toast is visible with no confirm modal, and the DB rows
        are gone.
    """
    page = page_mobile_portrait
    app = provide_app
    source: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = source.id

    utub_url_id_a = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-mobile-a.test/",
        url_title="Bulk Delete Mobile A",
    )
    utub_url_id_b = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-mobile-b.test/",
        url_title="Bulk Delete Mobile B",
    )

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_a = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_a}']")
    row_b = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_b}']")

    enter_multi_select_and_select_urls(
        page=page, url_ids=[utub_url_id_a, utub_url_id_b]
    )
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    # Mobile drawer slot swap: the destructive Delete action pairs up on the top
    # row (~half width) while Copy to UTub takes its own full-width row BELOW it.
    # Delete is still a 44px-tall coarse-pointer touch target.
    delete_btn = page.locator(HPL.BUTTON_BULK_DELETE_URLS)
    copy_btn = page.locator(HPL.BUTTON_BULK_COPY_URLS)
    expect(delete_btn).to_be_visible()
    expect(copy_btn).to_be_visible()
    delete_box = delete_btn.bounding_box()
    copy_box = copy_btn.bounding_box()
    assert delete_box is not None and copy_box is not None
    assert delete_box["height"] >= _MIN_TOUCH_TARGET_PX
    # Delete is paired (half-width), Copy is the full-width row: Copy is clearly
    # wider than the paired Delete.
    assert copy_box["width"] > delete_box["width"]
    # Copy sits on the row BELOW Delete (Delete pairs with Add tags on top).
    assert copy_box["y"] > delete_box["y"]

    bulk_delete_selected(page=page)

    # No confirm modal: the tap deletes at once.
    expect(page.locator(HPL.HOME_MODAL)).to_be_hidden()
    wait_for_element_to_be_removed(page=page, locator=row_a)
    wait_for_element_to_be_removed(page=page, locator=row_b)

    banner = page.locator(HPL.URL_OUTCOME_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)success(\s|$)"))
    expect(page.locator(HPL.URL_OUTCOME_BANNER_UNDO)).to_be_visible()

    assert not _utub_url_row_is_live(app=app, utub_url_id=utub_url_id_a)
    assert not _utub_url_row_is_live(app=app, utub_url_id=utub_url_id_b)


def test_mobile_bulk_delete_undo_restores(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user who just bulk-deleted two URLs from the bottom drawer
    WHEN they tap the toast's Undo
    THEN both rows are back in the deck and the DB rows are live again.
    """
    page = page_mobile_portrait
    app = provide_app
    source: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = source.id

    utub_url_id_a = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-mobile-cancel-a.test/",
        url_title="Bulk Delete Mobile Cancel A",
    )
    utub_url_id_b = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-mobile-cancel-b.test/",
        url_title="Bulk Delete Mobile Cancel B",
    )

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    row_a = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_a}']")
    row_b = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_b}']")
    initial_rows = get_num_url_rows(page=page)

    enter_multi_select_and_select_urls(
        page=page, url_ids=[utub_url_id_a, utub_url_id_b]
    )
    bulk_delete_selected(page=page)
    wait_for_element_to_be_removed(page=page, locator=row_a)
    wait_for_element_to_be_removed(page=page, locator=row_b)
    assert not _utub_url_row_is_live(app=app, utub_url_id=utub_url_id_a)

    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)

    expect(row_a).to_have_count(1)
    expect(row_b).to_have_count(1)
    assert get_num_url_rows(page=page) == initial_rows
    assert _utub_url_row_is_live(app=app, utub_url_id=utub_url_id_a)
    assert _utub_url_row_is_live(app=app, utub_url_id=utub_url_id_b)
