from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend import db
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.constants import STRINGS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    get_other_member_in_utub,
    get_other_utub_this_user_is_member_of,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import TrashPanelLocators as TrashPL
from tests.functional.playwright_assert_utils import (
    assert_active_utub,
    assert_login_with_username,
    assert_on_429_page,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    force_next_bulk_delete_ajax_failure_no_navigate,
    invalidate_csrf_token_on_page,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_until_hidden,
)
from tests.functional.tags_ui.playwright_utils import get_utub_tag_filter_selector
from tests.functional.trash_ui.db_utils import purge_utub_url_row
from tests.functional.urls_ui.playwright_utils import (
    bulk_delete_selected,
    enter_multi_select_and_select_urls,
    enter_multi_select_mode,
    expect_cant_delete_cue_on_row,
    tap_url_checkbox,
)

pytestmark = pytest.mark.urls_ui

USER_ID_FOR_TEST = 1
HIDDEN_BY_FILTER_TAG_STRING = "bulk-delete-filter-tag"


# --- Seed helpers -------------------------------------------------------------
# Seed globally-unique URLs with a deliberate author (`user_id`) so each test can
# control the per-URL delete permission it exercises: a row authored by the acting
# user (or created by the UTub creator) is deletable; a row authored by another
# member — in a UTub the acting user did not create — is NOT.


def _seed_url_in_utub(
    *, app: Flask, utub_id: int, user_id: int, url_string: str, url_title: str
) -> tuple[int, int]:
    """Insert a globally-unique URL + a `Utub_Urls` row (authored by `user_id`)
    into the given UTub. Returns (utub_url_id, url_id)."""
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


def _count_url_rows_in_utub(*, app: Flask, utub_id: int) -> int:
    """Count the live (non-trashed) URL rows in a UTub."""
    with app.app_context():
        return Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id, Utub_Urls.deleted_at.is_(None)
        ).count()


def _utub_url_row_is_live(*, app: Flask, utub_url_id: int) -> bool:
    """True when the row exists and has not been trashed (deleted_at is NULL)."""
    with app.app_context():
        row = Utub_Urls.query.get(utub_url_id)
        return row is not None and not row.is_trashed


def _get_trash_count(*, page: Page) -> int:
    text = page.locator(TrashPL.SELECTOR_COUNT).inner_text()
    return int(text.strip("()"))


def _moved_to_trash_text(*, count: int) -> str:
    return STRINGS.URL_MOVED_TO_TRASH.replace("{n}", str(count))


# --- Tests --------------------------------------------------------------------


def test_bulk_delete_happy_removes_selected_and_shows_undo_toast(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two deletable URLs selected in multi-select mode (creator deck)
    WHEN the user clicks the bar's Delete (no confirm step)
    THEN both selected rows are removed, the success toast reads "Moved 2 URLs to
        Trash." with an Undo, the DB row count drops by two, other URLs survive
        (deck not empty), and focus returns to the header Exit control
        (#bulkSelectExit).
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub.id

    initial_count = _count_url_rows_in_utub(app=app, utub_id=utub_id)

    utub_url_id_a, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-happy-a.test/",
        url_title="Bulk Delete Happy A",
    )
    utub_url_id_b, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-happy-b.test/",
        url_title="Bulk Delete Happy B",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    row_a = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_a}']")
    row_b = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_b}']")

    enter_multi_select_and_select_urls(
        page=page, url_ids=[utub_url_id_a, utub_url_id_b]
    )
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    # No confirm modal: the Delete click deletes at once and the toast appears.
    bulk_delete_selected(page=page)

    wait_for_element_to_be_removed(page=page, locator=row_a)
    wait_for_element_to_be_removed(page=page, locator=row_b)

    # Success toast with Undo (deck not empty → survivors remain).
    banner = page.locator(HPL.URL_OUTCOME_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)success(\s|$)"))
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        _moved_to_trash_text(count=2)
    )
    expect(page.locator(HPL.URL_OUTCOME_BANNER_UNDO)).to_be_visible()
    expect(page.locator(HPL.HOME_MODAL)).to_be_hidden()

    # Focus returns to the header Exit control on a non-deck-emptying path.
    expect(page.locator(HPL.BULK_SELECT_EXIT)).to_be_focused()

    # DB: exactly the two selected rows are gone.
    assert not _utub_url_row_is_live(app=app, utub_url_id=utub_url_id_a)
    assert not _utub_url_row_is_live(app=app, utub_url_id=utub_url_id_b)
    assert _count_url_rows_in_utub(app=app, utub_id=utub_id) == initial_count


def test_bulk_delete_undo_restores_all(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two URLs just bulk-deleted (toast showing)
    WHEN the toast's Undo is clicked
    THEN one restore brings every row back, the toast reports "Restored 2 URLs
        from trash.", the Trash count returns to its starting value, and both
        DB rows are live again.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub.id

    utub_url_id_a, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-undo-a.test/",
        url_title="Bulk Delete Undo A",
    )
    utub_url_id_b, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-undo-b.test/",
        url_title="Bulk Delete Undo B",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    row_a = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_a}']")
    row_b = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_b}']")
    initial_trash_count = _get_trash_count(page=page)

    enter_multi_select_and_select_urls(
        page=page, url_ids=[utub_url_id_a, utub_url_id_b]
    )
    bulk_delete_selected(page=page)
    wait_for_element_to_be_removed(page=page, locator=row_a)
    wait_for_element_to_be_removed(page=page, locator=row_b)

    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)

    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        STRINGS.URL_UNDO_RESTORED.replace("{n}", "2")
    )
    expect(row_a).to_have_count(1)
    expect(row_b).to_have_count(1)
    expect(page.locator(TrashPL.SELECTOR_COUNT)).to_have_text(
        f"({initial_trash_count})"
    )

    assert _utub_url_row_is_live(app=app, utub_url_id=utub_url_id_a)
    assert _utub_url_row_is_live(app=app, utub_url_id=utub_url_id_b)


def test_bulk_delete_dismiss_keeps_urls_in_trash(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two URLs just bulk-deleted (toast showing)
    WHEN the toast's dismiss button is clicked
    THEN the toast hides, the rows stay gone and the Trash count stays incremented.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub.id

    utub_url_id_a, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-dismiss-a.test/",
        url_title="Bulk Delete Dismiss A",
    )
    utub_url_id_b, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-dismiss-b.test/",
        url_title="Bulk Delete Dismiss B",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    row_a = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_a}']")
    row_b = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_b}']")
    initial_trash_count = _get_trash_count(page=page)

    enter_multi_select_and_select_urls(
        page=page, url_ids=[utub_url_id_a, utub_url_id_b]
    )
    bulk_delete_selected(page=page)

    # Dismiss right away: the success toast auto-hides after ~10s.
    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_DISMISS)
    wait_until_hidden(page=page, css_selector=HPL.URL_OUTCOME_BANNER)

    wait_for_element_to_be_removed(page=page, locator=row_a)
    wait_for_element_to_be_removed(page=page, locator=row_b)

    expect(row_a).to_have_count(0)
    expect(row_b).to_have_count(0)
    expect(page.locator(TrashPL.SELECTOR_COUNT)).to_have_text(
        f"({initial_trash_count + 2})"
    )
    assert not _utub_url_row_is_live(app=app, utub_url_id=utub_url_id_a)
    assert not _utub_url_row_is_live(app=app, utub_url_id=utub_url_id_b)


def test_bulk_delete_partial_permission_skips_others_url(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN, in a UTub the acting user did NOT create, one URL they authored
        (deletable) and one authored by another member (not deletable), both
        selected
    WHEN the user clicks Delete
    THEN the deletable URL is removed, the other member's URL survives with an
        amber "Can't delete" cue, and the toast is the partial variant with the
        skipped detail line.
    """
    app = provide_app
    source = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    other_utub = get_other_utub_this_user_is_member_of(app, USER_ID_FOR_TEST, source.id)
    other_utub_id = other_utub.id
    # The acting user must be a non-creator here for the permission skip to apply.
    assert other_utub.utub_creator != USER_ID_FOR_TEST

    other_member: Users = get_other_member_in_utub(app, other_utub_id, USER_ID_FOR_TEST)
    other_member_id = other_member.id

    deletable_id, _ = _seed_url_in_utub(
        app=app,
        utub_id=other_utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-partial-mine.test/",
        url_title="Bulk Delete Partial Mine",
    )
    non_deletable_id, _ = _seed_url_in_utub(
        app=app,
        utub_id=other_utub_id,
        user_id=other_member_id,
        url_string="https://bulk-delete-partial-theirs.test/",
        url_title="Bulk Delete Partial Theirs",
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=other_utub_id
    )

    deletable_row = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{deletable_id}']")

    enter_multi_select_and_select_urls(
        page=page, url_ids=[deletable_id, non_deletable_id]
    )
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    bulk_delete_selected(page=page)

    # Assert the transient amber "Can't delete" cue on the survivor FIRST — it is
    # removed a few seconds after the delete renders, so poll for it before the
    # (slower) row-fade-removal wait can eat into that budget.
    expect_cant_delete_cue_on_row(page=page, utub_url_id=non_deletable_id)

    wait_for_element_to_be_removed(page=page, locator=deletable_row)

    # The other member's URL survives.
    expect(
        page.locator(f"{HPL.ROWS_URLS}[utuburlid='{non_deletable_id}']")
    ).to_be_visible()

    # Partial toast: one URL moved, the skipped count in the detail.
    banner = page.locator(HPL.URL_OUTCOME_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)partial(\s|$)"))
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        STRINGS.URL_MOVED_TO_TRASH_ONE
    )
    expect(page.locator(HPL.URL_OUTCOME_BANNER_DETAIL)).to_contain_text(
        STRINGS.URL_BULK_DELETE_SKIPPED_SUFFIX_ONE
    )

    # DB: only the acting user's URL was deleted.
    assert not _utub_url_row_is_live(app=app, utub_url_id=deletable_id)
    assert _utub_url_row_is_live(app=app, utub_url_id=non_deletable_id)


def test_bulk_delete_hidden_selection_detail(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN three selected URLs where a tag filter hides one of them
    WHEN the user clicks Delete
    THEN all three selected URLs (including the hidden one) are moved to Trash and
        the toast detail reports the one URL hidden by the filter.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub.id
    tag = add_tag_to_utub_user_created(
        app, utub_id, USER_ID_FOR_TEST, HIDDEN_BY_FILTER_TAG_STRING
    )
    tag_id = tag.id

    # Tag the first two URLs so a filter on the tag hides the third.
    with app.app_context():
        utub_urls: list[Utub_Urls] = (
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id)
            .order_by(Utub_Urls.id)
            .all()
        )
        assert len(utub_urls) >= 3
        tagged_ids = [utub_urls[0].id, utub_urls[1].id]
        untagged_id = utub_urls[2].id
        for utub_url_id in tagged_ids:
            db.session.add(
                Utub_Url_Tags(
                    utub_id=utub_id, utub_url_id=utub_url_id, utub_tag_id=tag_id
                )
            )
        db.session.commit()

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    selected_ids = [tagged_ids[0], tagged_ids[1], untagged_id]
    enter_multi_select_mode(page=page)
    for utub_url_id in selected_ids:
        tap_url_checkbox(page=page, utub_url_id=utub_url_id)
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("3")

    # Filter by the tag — the untagged (still-selected) row is hidden.
    wait_then_click_element(
        page=page, css_selector=get_utub_tag_filter_selector(utub_tag_id=tag_id)
    )
    untagged_row = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{untagged_id}']").first
    expect(untagged_row).to_be_hidden()
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("3")

    bulk_delete_selected(page=page)

    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        _moved_to_trash_text(count=3)
    )
    expect(page.locator(HPL.URL_OUTCOME_BANNER_DETAIL)).to_contain_text(
        STRINGS.URL_DELETE_HIDDEN_DETAIL_ONE
    )
    for utub_url_id in selected_ids:
        assert not _utub_url_row_is_live(app=app, utub_url_id=utub_url_id)


def test_bulk_delete_button_disabled_until_deletable_url_selected(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN, in a UTub the acting user did NOT create, one URL authored by another
        member (not deletable) and one authored by the acting user (deletable)
    WHEN only the other member's URL is selected in multi-select mode
    THEN the bulk Delete button is VISIBLE but disabled (aria-disabled=true) with
        the explanatory tooltip, and it ENABLES only once a URL the user can
        delete joins the selection — re-disabling when that URL is deselected.
    """
    app = provide_app
    source = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    other_utub = get_other_utub_this_user_is_member_of(app, USER_ID_FOR_TEST, source.id)
    other_utub_id = other_utub.id
    # The acting user must be a non-creator here so the other member's URL is
    # genuinely non-deletable by them.
    assert other_utub.utub_creator != USER_ID_FOR_TEST

    other_member: Users = get_other_member_in_utub(app, other_utub_id, USER_ID_FOR_TEST)
    other_member_id = other_member.id

    non_deletable_id, _ = _seed_url_in_utub(
        app=app,
        utub_id=other_utub_id,
        user_id=other_member_id,
        url_string="https://bulk-delete-disabled-theirs.test/",
        url_title="Bulk Delete Disabled Theirs",
    )
    deletable_id, _ = _seed_url_in_utub(
        app=app,
        utub_id=other_utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-disabled-mine.test/",
        url_title="Bulk Delete Disabled Mine",
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=other_utub_id
    )

    # Select ONLY the other member's (non-deletable) URL.
    enter_multi_select_and_select_urls(page=page, url_ids=[non_deletable_id])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")

    delete_button = page.locator(HPL.BUTTON_BULK_DELETE_URLS)
    # Visible-but-disabled: the prior behavior hid the button entirely here.
    expect(delete_button).to_be_visible()
    expect(delete_button).to_have_attribute("aria-disabled", "true")
    expect(delete_button).to_have_attribute(
        "title", STRINGS.URL_BULK_DELETE_DISABLED_REASON
    )

    # Add a URL the acting user CAN delete → the button enables (rebuilt without
    # the aria-disabled flag).
    tap_url_checkbox(page=page, utub_url_id=deletable_id)
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")
    expect(delete_button).not_to_have_attribute("aria-disabled", "true")

    # Deselect it → back to a non-deletable-only selection → disabled again.
    tap_url_checkbox(page=page, utub_url_id=deletable_id)
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")
    expect(delete_button).to_have_attribute("aria-disabled", "true")


def test_bulk_delete_deck_empties_announces_and_exits(
    page: Page, create_test_utubs, provide_app: Flask
):
    """
    GIVEN a small UTub whose every URL is deletable by the acting user
    WHEN the user selects and deletes them all
    THEN the deck-level outcome announcer shows the moved-to-Trash message,
        multi-select mode has exited, the empty-state renders, and focus lands on
        the multi-select toggle (toggleBar(false)'s visible-case fallback).
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub.id

    utub_url_id_a, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-empties-a.test/",
        url_title="Bulk Delete Empties A",
    )
    utub_url_id_b, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-empties-b.test/",
        url_title="Bulk Delete Empties B",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    row_a = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_a}']")
    row_b = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_b}']")

    enter_multi_select_and_select_urls(
        page=page, url_ids=[utub_url_id_a, utub_url_id_b]
    )
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    bulk_delete_selected(page=page)

    wait_for_element_to_be_removed(page=page, locator=row_a)
    wait_for_element_to_be_removed(page=page, locator=row_b)

    # Deck-level outcome announcer holds the moved-to-Trash message (survives the
    # bulk-bar teardown on mode exit).
    expect(page.locator(HPL.URL_DECK_OUTCOME_ANNOUNCEMENT)).to_have_text(
        _moved_to_trash_text(count=2)
    )

    # Multi-select mode has exited (deck no longer marked active).
    expect(page.locator(HPL.URL_DECK)).not_to_have_class(
        re.compile(r"(^|\s)multiSelectActive(\s|$)")
    )

    # Empty-state renders + focus lands on the (still-visible) multi-select toggle.
    empty_subheader = page.locator(HPL.SUBHEADER_NO_URLS)
    expect(empty_subheader).to_be_visible()
    expect(empty_subheader).to_have_text(UTS.UTUB_NO_URLS)
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_be_focused()

    assert _count_url_rows_in_utub(app=app, utub_id=utub_id) == 0


def test_bulk_delete_invalid_csrf_token_reloads(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a deletable URL selected
    WHEN Delete is clicked with an invalidated CSRF token
    THEN the server returns the 403 page (body-swapped in), the reload restores
        the session, and the URL is NOT deleted.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    with app.app_context():
        user: Users = Users.query.get(USER_ID_FOR_TEST)
        username = user.username

    utub_url_id, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-csrf.test/",
        url_title="Bulk Delete CSRF",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[utub_url_id])

    invalidate_csrf_token_on_page(page=page)
    bulk_delete_selected(page=page, expect_toast=False)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    assert_login_with_username(page=page, username=username)
    assert_active_utub(page=page, utub_name=utub.name)

    assert _utub_url_row_is_live(app=app, utub_url_id=utub_url_id)


def test_bulk_delete_rate_limited_shows_429(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a deletable URL selected, user rate-limited
    WHEN Delete is clicked
    THEN the 429 error page is shown and the URL is NOT deleted.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    utub_url_id, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-429.test/",
        url_title="Bulk Delete 429",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[utub_url_id])

    add_forced_rate_limit_header(page=page)
    bulk_delete_selected(page=page, expect_toast=False)

    assert_on_429_page(page=page)
    assert _utub_url_row_is_live(app=app, utub_url_id=utub_url_id)


def test_bulk_delete_reenables_on_server_error(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a deletable URL selected
    WHEN the delete POST fails and the failure handler short-circuits without
        navigating (the forced fake failure reads as already-handled, mirroring
        the single-URL delete precedent in test_delete_url_ui)
    THEN the request's .always() re-enables the bar's Delete button so the user
        can retry, no toast shows, and nothing is deleted.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    utub_url_id, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-500.test/",
        url_title="Bulk Delete 500",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[utub_url_id])

    force_next_bulk_delete_ajax_failure_no_navigate(page=page)
    bulk_delete_selected(page=page, expect_toast=False)

    # The always() handler re-enables the Delete button after the failure.
    delete_button = page.locator(HPL.BUTTON_BULK_DELETE_URLS)
    expect(delete_button).to_be_visible()
    expect(delete_button).not_to_have_attribute("aria-disabled", "true")
    expect(page.locator(HPL.URL_OUTCOME_BANNER)).to_be_hidden()
    assert _utub_url_row_is_live(app=app, utub_url_id=utub_url_id)


def test_bulk_undo_partial_reports_not_in_trash(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN three URLs bulk-deleted and one of them then purged from Trash
    WHEN the toast's Undo is clicked
    THEN the other two are restored, the toast reads "Restored 2 of 3 URLs from
        trash." with the "1 is no longer in Trash." detail, and the purged URL
        stays gone.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub.id

    seeded_ids: list[int] = []
    for suffix in ("a", "b", "c"):
        seeded_id, _ = _seed_url_in_utub(
            app=app,
            utub_id=utub_id,
            user_id=USER_ID_FOR_TEST,
            url_string=f"https://bulk-undo-partial-{suffix}.test/",
            url_title=f"Bulk Undo Partial {suffix.upper()}",
        )
        seeded_ids.append(seeded_id)
    purged_id = seeded_ids[1]
    survivors = [seeded_ids[0], seeded_ids[2]]

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=seeded_ids)
    bulk_delete_selected(page=page)

    # The delete is committed before the toast renders; purge one trashed row
    # (as the purge job would) so its restore is skipped.
    purge_utub_url_row(app, purged_id)

    for seeded_id in seeded_ids:
        wait_for_element_to_be_removed(
            page=page, locator=page.locator(f"{HPL.ROWS_URLS}[utuburlid='{seeded_id}']")
        )

    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)

    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        STRINGS.URL_UNDO_RESTORED_SOME.replace("{restored}", "2").replace(
            "{total}", "3"
        )
    )
    expect(page.locator(HPL.URL_OUTCOME_BANNER_DETAIL)).to_contain_text(
        STRINGS.URL_UNDO_NOT_IN_TRASH_ONE
    )
    for restored_id in survivors:
        expect(
            page.locator(f"{HPL.ROWS_URLS}[utuburlid='{restored_id}']")
        ).to_have_count(1)
        assert _utub_url_row_is_live(app=app, utub_url_id=restored_id)
    expect(page.locator(f"{HPL.ROWS_URLS}[utuburlid='{purged_id}']")).to_have_count(0)
