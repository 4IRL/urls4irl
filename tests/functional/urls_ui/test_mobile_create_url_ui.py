from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.utub_urls import Utub_Urls
from backend.utils.strings.url_strs import URL_REVIVED_FROM_TRASH
from tests.functional.db_utils import (
    add_tags_to_utub_url,
    get_utub_this_user_created,
    trash_utub_url,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_panel_visibility_mobile
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import Decks, get_url_row_by_id
from tests.functional.urls_ui.playwright_utils import create_url

pytestmark = [pytest.mark.urls_ui, pytest.mark.mobile_ui]

USER_ID_FOR_TEST = 1


def test_mobile_readd_trashed_url_shows_restored_banner(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub holding a trashed URL that carried two tags, at a mobile viewport
    WHEN the user adds the same URL string through the create form
    THEN the trashed card is revived in place with both tag badges, and the
        success outcome banner reporting the restore is visible and fits inside
        the viewport width (no horizontal overflow)
    """
    page = page_mobile_portrait
    app = provide_app
    utub_id = get_utub_this_user_created(app, USER_ID_FOR_TEST).id
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).first()
        utub_url_id = utub_url.id
        url_string = utub_url.standalone_url.url_string

    tag_ids = add_tags_to_utub_url(
        app, utub_id, utub_url_id, USER_ID_FOR_TEST, ["mrevivea", "mreviveb"]
    )
    trash_utub_url(app, utub_url_id, USER_ID_FOR_TEST, tag_ids)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub_id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)
    expect(page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']")).to_have_count(0)

    create_url(page=page, url_title="Mobile Revived", url_string=url_string)

    # Revived in place under the trashed row's id, tags intact.
    url_row = get_url_row_by_id(page=page, utub_url_id=utub_url_id)
    expect(page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']")).to_have_count(1)
    expect(url_row.locator(HPL.TAG_BADGES)).to_have_count(2)

    banner = page.locator(HPL.URL_OUTCOME_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)success(\s|$)"))
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_REVIVED_FROM_TRASH
    )

    # The banner must sit fully inside the mobile viewport horizontally.
    viewport = page.viewport_size
    assert viewport is not None
    box = banner.bounding_box()
    assert box is not None
    assert box["x"] >= 0
    assert box["x"] + box["width"] <= viewport["width"]
