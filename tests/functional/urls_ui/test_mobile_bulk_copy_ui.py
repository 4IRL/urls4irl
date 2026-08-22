from __future__ import annotations

import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.urls import Urls
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.constants import STRINGS
from tests.functional.db_utils import (
    get_n_other_utubs_this_user_is_member_of,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_panel_visibility_mobile
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import Decks, wait_until_hidden
from tests.functional.urls_ui.playwright_utils import (
    enter_multi_select_and_select_urls,
    expect_copy_cue_on_row,
    expect_staged_destination_count,
    open_bulk_copy_picker,
    stage_copy_destination,
    submit_bulk_copy,
)

pytestmark = [pytest.mark.urls_ui, pytest.mark.mobile_ui]

USER_ID_FOR_TEST = 1

# Coarse-pointer 44px touch target minus a 1px rounding tolerance (2.75rem tall).
_MIN_TOUCH_TARGET_PX = 43


def _seed_source_url(
    *, app: Flask, utub_id: int, user_id: int, url_string: str, url_title: str
) -> tuple[int, int]:
    """Insert a globally-unique URL + `Utub_Urls` row into the source UTub (a URL
    absent from every other UTub, so a copy of it lands as new). Returns
    (utub_url_id, url_id)."""
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
        result = (new_utub_url.id, raw_url.id)
        db.session.commit()
        return result


def _count_dest_rows_for_url(*, app: Flask, utub_id: int, url_id: int) -> int:
    with app.app_context():
        return Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id, Utub_Urls.url_id == url_id
        ).count()


def test_mobile_bulk_copy_bottom_drawer_stage_two_and_confirm(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user with a source-only URL selected in multi-select mode
    WHEN they open the copy picker, stage TWO destinations by tapping their rows,
        and confirm
    THEN the picker mounts as a bottom drawer with 44px tappable rows/buttons,
        both rows stay staged (aria-selected="true"), the copy succeeds into BOTH
        destinations (multi-destination banner + "Copied" cue), and each
        destination gains the row.
    """
    page = page_mobile_portrait
    app = provide_app
    source: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    dest_a, dest_b = get_n_other_utubs_this_user_is_member_of(
        app, USER_ID_FOR_TEST, source.id, 2
    )
    dest_a_id, dest_a_name = dest_a.id, dest_a.name
    dest_b_id, dest_b_name = dest_b.id, dest_b.name

    utub_url_id_a, url_id_a = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-mobile-a.test/",
        url_title="Copy Mobile A",
    )

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=source.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    enter_multi_select_and_select_urls(page=page, url_ids=[utub_url_id_a])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")

    open_bulk_copy_picker(page=page)

    # The picker mounts as a bottom drawer docked to the viewport's bottom edge.
    picker = page.locator(HPL.BULK_COPY_PICKER_MOUNT)
    expect(picker).to_be_visible()
    picker_box = picker.bounding_box()
    viewport = page.viewport_size
    assert picker_box is not None and viewport is not None
    assert picker_box["y"] > viewport["height"] / 2
    assert picker_box["y"] + picker_box["height"] >= viewport["height"] - 5

    # 44px coarse-pointer targets on a destination row and the Cancel button.
    row_box = page.locator(
        f"{HPL.BULK_COPY_PICKER_MOUNT} {HPL.BULK_COPY_OPTION_ENABLED}"
    ).first.bounding_box()
    assert row_box is not None
    assert row_box["height"] >= _MIN_TOUCH_TARGET_PX
    cancel_box = page.locator(
        f"{HPL.BULK_COPY_PICKER_MOUNT} {HPL.BUTTON_BULK_COPY_CANCEL}"
    ).bounding_box()
    assert cancel_box is not None
    assert cancel_box["height"] >= _MIN_TOUCH_TARGET_PX

    # Stage BOTH destinations by tapping their rows; multi-select keeps each row
    # staged (aria-selected asserted per-row in the helper).
    stage_copy_destination(page=page, utub_name=dest_a_name, via_keyboard=False)
    stage_copy_destination(page=page, utub_name=dest_b_name, via_keyboard=False)
    expect_staged_destination_count(page=page, count=2)

    submit_bulk_copy(page=page)

    wait_until_hidden(page=page, css_selector=HPL.BULK_COPY_PICKER_MOUNT)

    # Transient per-card cue FIRST (DOM-removed ~3s after render), before the
    # persistent banner assertions.
    expect_copy_cue_on_row(page=page, utub_url_id=utub_url_id_a, kind="copied")

    banner = page.locator(HPL.BULK_COPY_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)success(\s|$)"))
    expect(page.locator(HPL.BULK_COPY_BANNER_BODY)).to_have_text(
        STRINGS.URLS_COPIED_MULTI.replace("{n}", "2")
    )

    # Both destinations gained the copied URL.
    assert _count_dest_rows_for_url(app=app, utub_id=dest_a_id, url_id=url_id_a) == 1
    assert _count_dest_rows_for_url(app=app, utub_id=dest_b_id, url_id=url_id_a) == 1
