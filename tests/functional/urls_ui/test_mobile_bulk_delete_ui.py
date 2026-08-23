from __future__ import annotations

import re

from flask import Flask
import pytest
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
    wait_for_modal_ready,
    wait_then_click_element,
    wait_until_hidden,
)
from tests.functional.urls_ui.playwright_utils import (
    enter_multi_select_and_select_urls,
    open_bulk_delete_confirm,
    submit_bulk_delete,
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


def _utub_url_row_exists(*, app: Flask, utub_url_id: int) -> bool:
    with app.app_context():
        return Utub_Urls.query.get(utub_url_id) is not None


def _computed_z_index(*, page: Page, css_selector: str) -> int:
    value = page.evaluate(
        """(selector) => {
            const el = document.querySelector(selector);
            if (!el) return null;
            return window.getComputedStyle(el).zIndex;
        }""",
        css_selector,
    )
    assert (
        value is not None and value != "auto"
    ), f"Expected a numeric z-index on {css_selector}, got {value!r}"
    return int(value)


def test_mobile_bulk_delete_bottom_drawer_confirm_stacks_and_deletes(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user with two deletable URLs selected in multi-select mode
    WHEN they open the destructive confirm from the bottom drawer and confirm
    THEN the drawer Delete action meets the 44px touch target, the confirm modal
        stacks ABOVE the z-1035 drawer, both rows are removed, the result banner
        shows, and the DB rows are gone.
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

    # The destructive Delete action renders as a full-width, 44px-tall row in the
    # bottom drawer.
    delete_btn = page.locator(HPL.BUTTON_BULK_DELETE_URLS)
    expect(delete_btn).to_be_visible()
    delete_box = delete_btn.bounding_box()
    assert delete_box is not None
    assert delete_box["height"] >= _MIN_TOUCH_TARGET_PX

    open_bulk_delete_confirm(page=page)

    # The confirm modal stacks ABOVE the z-1035 bottom drawer.
    modal_z = _computed_z_index(page=page, css_selector=HPL.HOME_MODAL)
    drawer_z = _computed_z_index(page=page, css_selector=HPL.BULK_ACTION_BAR)
    assert (
        modal_z > drawer_z
    ), f"Confirm modal (z={modal_z}) must stack above the drawer (z={drawer_z})"

    submit_bulk_delete(page=page)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_element_to_be_removed(page=page, locator=row_a)
    wait_for_element_to_be_removed(page=page, locator=row_b)

    banner = page.locator(HPL.BULK_DELETE_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)success(\s|$)"))

    assert not _utub_url_row_exists(app=app, utub_url_id=utub_url_id_a)
    assert not _utub_url_row_exists(app=app, utub_url_id=utub_url_id_b)


def test_mobile_bulk_delete_cancel_leaves_urls_intact(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user with two deletable URLs selected and the confirm open
    WHEN they cancel (Just kidding)
    THEN no request fires, the modal hides, and every URL stays.
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

    enter_multi_select_and_select_urls(
        page=page, url_ids=[utub_url_id_a, utub_url_id_b]
    )
    initial_rows = get_num_url_rows(page=page)

    open_bulk_delete_confirm(page=page)
    wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_DISMISS)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    assert get_num_url_rows(page=page) == initial_rows
    assert _utub_url_row_exists(app=app, utub_url_id=utub_url_id_a)
    assert _utub_url_row_exists(app=app, utub_url_id=utub_url_id_b)
