"""Playwright UI tests for content-moderation admin actions.

Covers the Lock/Unlock UTub controls, the URL-purge control, and the
tag-moderation controls (remove a tag from a URL, delete a UTub tag), all
hosted on the aggregated UTub-detail page (``/admin/utubs/<id>``), plus the
UTub Actions list → detail navigation.
"""

from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.config import ConfigTestUI
from backend.models.urls import Urls
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.admin_ui.playwright_utils import (
    login_admin_and_open_utub_actions,
    login_admin_and_open_utub_detail,
)
from tests.functional.locators import AdminPortalLocators as APL
from tests.functional.playwright_utils import wait_then_get_element

pytestmark = pytest.mark.admin_ui

DEFAULT_ADMIN_USER_ID: int = 1

TEST_REASON_TEXT: str = "automated moderation test"


def test_admin_mod_utub_lock_happy_path(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing an unlocked UTub's detail page
    WHEN the admin clicks the Lock button, enters a reason, and confirms
    THEN the page reloads, a locked badge appears in the header, and the Unlock
         button replaces the Lock button in the action bar.
    """
    with provide_app.app_context():
        first_utub = Utubs.query.order_by(Utubs.id.asc()).first()
        assert first_utub is not None, "No UTubs seeded — fixture may have failed"
        utub_id = first_utub.id

    login_admin_and_open_utub_detail(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        utub_id=utub_id,
    )

    detail_title = wait_then_get_element(page=page, css_selector=APL.UTUB_DETAIL_TITLE)
    expect(detail_title).to_be_visible()

    # Assert no locked badge before the action
    assert page.locator(APL.UTUB_DETAIL_LOCKED_BADGE).count() == 0

    # Click the Lock button
    lock_btn = wait_then_get_element(
        page=page, css_selector=APL.UTUB_DETAIL_MOD_LOCK_BTN
    )
    lock_btn.click()

    modal_title = wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    expect(modal_title).to_have_text(UI_TEST_STRINGS.ADMIN_MOD_UTUB_LOCK_CONFIRM_TITLE)

    reason_input = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    # data-reload-on-success triggers a full page reload; wait for it to settle
    page.wait_for_load_state("networkidle")

    # After reload the locked badge must be visible in the header
    locked_badge = wait_then_get_element(
        page=page, css_selector=APL.UTUB_DETAIL_LOCKED_BADGE
    )
    expect(locked_badge).to_be_visible()
    expect(locked_badge).to_have_text(UI_TEST_STRINGS.ADMIN_MOD_LOCKED_BADGE)

    # The Unlock button should now be present and Lock button absent
    assert page.locator(APL.UTUB_DETAIL_MOD_UNLOCK_BTN).count() == 1
    assert page.locator(APL.UTUB_DETAIL_MOD_LOCK_BTN).count() == 0


def test_admin_mod_utub_lock_reason_required(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing an unlocked UTub's detail page
    WHEN the admin opens the Lock modal and submits without entering a reason
    THEN the modal alert banner shows the reason-required message and the UTub
         remains unlocked (no locked badge appears on the page).
    """
    with provide_app.app_context():
        first_utub = Utubs.query.order_by(Utubs.id.asc()).first()
        assert first_utub is not None, "No UTubs seeded — fixture may have failed"
        utub_id = first_utub.id

    login_admin_and_open_utub_detail(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        utub_id=utub_id,
    )

    wait_then_get_element(page=page, css_selector=APL.UTUB_DETAIL_TITLE)

    lock_btn = wait_then_get_element(
        page=page, css_selector=APL.UTUB_DETAIL_MOD_LOCK_BTN
    )
    lock_btn.click()

    wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)

    # Submit without providing a reason
    page.click(APL.ACTION_MODAL_SUBMIT)

    # The modal alert banner must appear with the reason-required message
    alert_banner = wait_then_get_element(
        page=page, css_selector=APL.ACTION_MODAL_ALERT_BANNER
    )
    expect(alert_banner).to_be_visible()
    expect(alert_banner).to_have_text(UI_TEST_STRINGS.ADMIN_ACTION_REASON_REQUIRED)

    # Modal stays open; no reload has occurred so the locked badge must be absent
    assert page.locator(APL.UTUB_DETAIL_LOCKED_BADGE).count() == 0


def test_admin_mod_url_purge_control_and_happy_path(
    page: Page,
    create_test_urls,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing the detail page of a UTub whose URL list contains a
         seeded URL
    WHEN the admin clicks that URL's Purge button, enters a reason, and confirms
    THEN the inline result beneath the purge button shows a success message
         containing "URL purged from" and the DB contains no UtubUrls rows for
         that URL.
    """
    # Resolve the first seeded URL and a UTub that contains it.
    with provide_app.app_context():
        first_url = Urls.query.order_by(Urls.id.asc()).first()
        assert first_url is not None, "No URLs seeded — fixture may have failed"
        url_id = first_url.id
        association = Utub_Urls.query.filter_by(url_id=url_id).first()
        assert association is not None, "Seeded URL is not in any UTub"
        utub_id = association.utub_id

    login_admin_and_open_utub_detail(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        utub_id=utub_id,
    )

    # The URLs table must render for a UTub that contains at least one URL.
    wait_then_get_element(page=page, css_selector=APL.UTUB_DETAIL_URLS_TABLE)

    # Scope the purge button to the seeded URL's row (multiple URL rows may
    # exist) via its action-url suffix.
    purge_selector = (
        f"{APL.UTUB_DETAIL_MOD_URL_PURGE_BTN}"
        f'[data-action-url$="/urls/{url_id}/purge"]'
    )
    purge_result_selector = f"{purge_selector} + .admin-action-inline-result"

    purge_btn = wait_then_get_element(page=page, css_selector=purge_selector)
    expect(purge_btn).to_be_visible()
    expect(purge_btn).to_have_text(UI_TEST_STRINGS.ADMIN_MOD_URL_PURGE_LABEL)

    # Click the purge button, fill reason, confirm
    purge_btn.click()

    modal_title = wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    expect(modal_title).to_have_text(UI_TEST_STRINGS.ADMIN_MOD_URL_PURGE_CONFIRM_TITLE)

    reason_input = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    # No reload-on-success for url-purge; success renders inline beneath the button
    result_region = wait_then_get_element(page=page, css_selector=purge_result_selector)
    expect(result_region).to_be_visible()
    expect(result_region).to_contain_text(
        UI_TEST_STRINGS.ADMIN_MOD_URL_PURGE_SUCCESS_PREFIX
    )

    # Verify via DB that no UtubUrls rows remain for this URL
    with provide_app.app_context():
        remaining_associations = Utub_Urls.query.filter_by(url_id=url_id).count()
    assert remaining_associations == 0, (
        f"Expected 0 UtubUrls rows for url_id={url_id} after purge, "
        f"found {remaining_associations}"
    )


def test_admin_mod_utub_tag_delete_happy_path(
    page: Page,
    create_test_tags,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing the detail page of a UTub whose UTub Tags panel lists
         a vocabulary tag
    WHEN the admin clicks that tag's Delete button, enters a reason, and confirms
    THEN the page reloads, the tag's delete control is gone, and the Utub_Tags
         vocabulary row (with its URL applications) is deleted.
    """
    with provide_app.app_context():
        utub_tag = Utub_Tags.query.order_by(Utub_Tags.id.asc()).first()
        assert utub_tag is not None, "No UTub tags seeded — fixture may have failed"
        utub_id = utub_tag.utub_id
        utub_tag_id = utub_tag.id

    login_admin_and_open_utub_detail(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        utub_id=utub_id,
    )

    wait_then_get_element(page=page, css_selector=APL.UTUB_DETAIL_TAGS_TABLE)

    delete_selector = (
        f"{APL.UTUB_DETAIL_MOD_UTUB_TAG_DELETE_BTN}"
        f'[data-action-url$="/tags/{utub_tag_id}/delete"]'
    )
    delete_btn = wait_then_get_element(page=page, css_selector=delete_selector)
    expect(delete_btn).to_be_visible()

    delete_btn.click()

    modal_title = wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)
    expect(modal_title).to_have_text(
        UI_TEST_STRINGS.ADMIN_MOD_UTUB_TAG_DELETE_CONFIRM_TITLE
    )

    reason_input = wait_then_get_element(
        page=page, css_selector=APL.ACTION_REASON_INPUT
    )
    reason_input.fill(TEST_REASON_TEXT)

    page.click(APL.ACTION_MODAL_SUBMIT)

    # data-reload-on-success calls window.location.reload() inside the AJAX done
    # handler; poll the reloaded DOM (auto-retry) rather than racing a bare
    # networkidle wait against the navigation start.
    expect(page.locator(delete_selector)).to_have_count(0)

    with provide_app.app_context():
        assert Utub_Tags.query.get(utub_tag_id) is None
        assert Utub_Url_Tags.query.filter_by(utub_tag_id=utub_tag_id).count() == 0


def test_admin_mod_utub_tag_delete_reason_required(
    page: Page,
    create_test_tags,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing a UTub-detail page with a vocabulary tag
    WHEN the admin opens the tag's Delete modal and submits without a reason
    THEN the modal alert banner shows the reason-required message and the
         Utub_Tags row remains in the database.
    """
    with provide_app.app_context():
        utub_tag = Utub_Tags.query.order_by(Utub_Tags.id.asc()).first()
        assert utub_tag is not None, "No UTub tags seeded — fixture may have failed"
        utub_id = utub_tag.utub_id
        utub_tag_id = utub_tag.id

    login_admin_and_open_utub_detail(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        utub_id=utub_id,
    )

    wait_then_get_element(page=page, css_selector=APL.UTUB_DETAIL_TAGS_TABLE)

    delete_selector = (
        f"{APL.UTUB_DETAIL_MOD_UTUB_TAG_DELETE_BTN}"
        f'[data-action-url$="/tags/{utub_tag_id}/delete"]'
    )
    delete_btn = wait_then_get_element(page=page, css_selector=delete_selector)
    delete_btn.click()

    wait_then_get_element(page=page, css_selector=APL.ACTION_MODAL_TITLE)

    # Submit without providing a reason.
    page.click(APL.ACTION_MODAL_SUBMIT)

    alert_banner = wait_then_get_element(
        page=page, css_selector=APL.ACTION_MODAL_ALERT_BANNER
    )
    expect(alert_banner).to_be_visible()
    expect(alert_banner).to_have_text(UI_TEST_STRINGS.ADMIN_ACTION_REASON_REQUIRED)

    with provide_app.app_context():
        assert Utub_Tags.query.get(utub_tag_id) is not None


def test_admin_utub_detail_urls_search_filters_rows(
    page: Page,
    create_test_urls,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN an admin viewing the detail page of a UTub containing a seeded URL
    WHEN the admin types that URL's (globally unique) string into the URLs search
         box and submits with Enter
    THEN the page reloads filtered by ``urls_q``, the search box retains the term,
         and exactly one URL row (the match) renders.
    """
    with provide_app.app_context():
        association = (
            Utub_Urls.query.join(Urls, Utub_Urls.url_id == Urls.id)
            .order_by(Utub_Urls.id.asc())
            .first()
        )
        assert association is not None, "No UtubUrls seeded — fixture may have failed"
        utub_id = association.utub_id
        target_url_string = association.standalone_url.url_string

    login_admin_and_open_utub_detail(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
        utub_id=utub_id,
    )

    search_input = wait_then_get_element(
        page=page, css_selector=APL.UTUB_DETAIL_URLS_SEARCH
    )
    search_input.fill(target_url_string)
    search_input.press("Enter")

    # The GET reload lands on the filtered URL with the term echoed back.
    expect(page).to_have_url(re.compile(r"urls_q="))
    expect(
        wait_then_get_element(page=page, css_selector=APL.UTUB_DETAIL_URLS_SEARCH)
    ).to_have_value(target_url_string)

    # Exactly the matching URL row renders (its string is globally unique).
    expect(page.locator(APL.UTUB_DETAIL_MOD_URL_DELETE_BTN)).to_have_count(1)
    expect(page.locator(APL.UTUB_DETAIL_URLS_TABLE)).to_contain_text(target_url_string)


def test_admin_utub_list_and_open_detail(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin viewing the UTub Actions list with seeded UTubs
    WHEN the admin clicks the first grid row link
    THEN the URL becomes /admin/utubs/<id> and the UTub-detail title renders.
    """
    login_admin_and_open_utub_actions(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    # The list grid and at least one row link must render.
    wait_then_get_element(page=page, css_selector=APL.UTUB_TABLE_GRID)
    row_link_locator = page.locator(APL.UTUB_ROW_LINK)
    expect(row_link_locator.first).to_be_visible()

    # Click the first row link to navigate to the detail page.
    row_link_locator.first.click()

    expect(page).to_have_url(re.compile(r"/admin/utubs/\d+$"))

    detail_title = wait_then_get_element(page=page, css_selector=APL.UTUB_DETAIL_TITLE)
    expect(detail_title).to_be_visible()
    expect(detail_title).to_contain_text(UI_TEST_STRINGS.ADMIN_UTUB_DETAIL_TITLE)


def test_admin_utub_list_clicking_non_id_cell_opens_detail(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
) -> None:
    """
    GIVEN a logged-in admin viewing the UTub Actions list with seeded UTubs
    WHEN the admin clicks a NON-ID cell (e.g. the Name/Created cell) of a row
    THEN the whole-row enhancement navigates to /admin/utubs/<id> and the
         UTub-detail title renders.
    """
    login_admin_and_open_utub_actions(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_get_element(page=page, css_selector=APL.UTUB_TABLE_GRID)
    first_row = page.locator(APL.UTUB_CLICKABLE_ROW).first
    expect(first_row).to_be_visible()

    # Click a cell that is NOT the first (ID) cell — the ID link lives in
    # td:nth-child(1), so td:nth-child(2) is a plain, non-interactive cell.
    non_id_cell = first_row.locator("td:nth-child(2)")
    expect(non_id_cell).to_be_visible()
    non_id_cell.click()

    expect(page).to_have_url(re.compile(r"/admin/utubs/\d+$"))

    detail_title = wait_then_get_element(page=page, css_selector=APL.UTUB_DETAIL_TITLE)
    expect(detail_title).to_be_visible()
    expect(detail_title).to_contain_text(UI_TEST_STRINGS.ADMIN_UTUB_DETAIL_TITLE)
