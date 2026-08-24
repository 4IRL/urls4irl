from __future__ import annotations

import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_urls import Utub_Urls
from backend.utils.constants import STRINGS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    get_other_member_in_utub,
    get_other_utub_this_user_is_member_of,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
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
    dismiss_modal_with_click_out,
    force_next_bulk_delete_ajax_failure_no_navigate,
    get_num_url_rows,
    invalidate_csrf_token_on_page,
    wait_for_element_to_be_removed,
    wait_for_modal_ready,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_in_focus,
)
from tests.functional.urls_ui.playwright_utils import (
    enter_multi_select_and_select_urls,
    expect_cant_delete_cue_on_row,
    open_bulk_delete_confirm,
    submit_bulk_delete,
    tap_url_checkbox,
)

pytestmark = pytest.mark.urls_ui

USER_ID_FOR_TEST = 1


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
    with app.app_context():
        return Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).count()


def _utub_url_row_exists(*, app: Flask, utub_url_id: int) -> bool:
    with app.app_context():
        return Utub_Urls.query.get(utub_url_id) is not None


# --- Tests --------------------------------------------------------------------


def test_bulk_delete_happy_removes_selected_and_shows_banner(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two deletable URLs selected in multi-select mode (creator deck)
    WHEN the user opens the confirm, sees the count-aware title, and confirms
    THEN both selected rows are removed, the success banner shows, the DB row
        count drops by two, other URLs survive (deck not empty), and focus
        returns to the header Exit control (#bulkSelectExit).
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

    open_bulk_delete_confirm(page=page)

    # Count-aware title: both selected URLs are deletable.
    expect(page.locator(HPL.HEADER_MODAL)).to_have_text(
        STRINGS.URL_BULK_DELETE_CONFIRM_TITLE.replace("{n}", "2")
    )
    # The submit label reflects the deletable count.
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_have_text(
        STRINGS.URL_BULK_DELETE_SUBMIT.replace("{n}", "2")
    )

    submit_bulk_delete(page=page)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_element_to_be_removed(page=page, locator=row_a)
    wait_for_element_to_be_removed(page=page, locator=row_b)

    # Persistent success banner (deck not empty → survivors remain).
    banner = page.locator(HPL.BULK_DELETE_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)success(\s|$)"))

    # Focus returns to the header Exit control on a non-deck-emptying close path.
    expect(page.locator(HPL.BULK_SELECT_EXIT)).to_be_focused()

    # DB: exactly the two selected rows are gone.
    assert not _utub_url_row_exists(app=app, utub_url_id=utub_url_id_a)
    assert not _utub_url_row_exists(app=app, utub_url_id=utub_url_id_b)
    assert _count_url_rows_in_utub(app=app, utub_id=utub_id) == initial_count


@pytest.mark.parametrize(
    "cancel_method",
    ["dismiss", "x_close", "escape", "click_outside"],
)
def test_bulk_delete_cancel_paths_leave_urls_intact(
    page: Page, create_test_urls, provide_app: Flask, cancel_method: str
):
    """
    GIVEN two deletable URLs selected and the confirm modal open
    WHEN the user cancels via the Just-kidding button / X / Escape / backdrop
    THEN no request fires, every URL stays, the modal hides, and focus returns to
        the header Exit control (#bulkSelectExit) on every non-empty close path.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub.id

    utub_url_id_a, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string=f"https://bulk-delete-cancel-{cancel_method}-a.test/",
        url_title="Bulk Delete Cancel A",
    )
    utub_url_id_b, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub_id,
        user_id=USER_ID_FOR_TEST,
        url_string=f"https://bulk-delete-cancel-{cancel_method}-b.test/",
        url_title="Bulk Delete Cancel B",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    initial_rows = get_num_url_rows(page=page)

    enter_multi_select_and_select_urls(
        page=page, url_ids=[utub_url_id_a, utub_url_id_b]
    )
    open_bulk_delete_confirm(page=page)

    if cancel_method == "dismiss":
        wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
        wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_DISMISS)
    elif cancel_method == "x_close":
        wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
        wait_then_click_element(page=page, css_selector=HPL.BUTTON_X_CLOSE)
    elif cancel_method == "escape":
        # Gate on the fade-in transition being complete (like the other cancel
        # paths) AND the modal holding focus, so Escape is never dropped
        # mid-transition by Bootstrap.
        wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
        wait_until_in_focus(page=page, css_selector=HPL.HOME_MODAL)
        page.keyboard.press("Escape")
    else:  # click_outside
        wait_for_modal_ready(page=page, modal_selector=HPL.HOME_MODAL)
        dismiss_modal_with_click_out(page=page, modal_selector=HPL.HOME_MODAL)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    # No deletion, no result banner, focus back on the header Exit control.
    assert get_num_url_rows(page=page) == initial_rows
    expect(
        page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_a}']")
    ).to_be_visible()
    expect(
        page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id_b}']")
    ).to_be_visible()
    assert _utub_url_row_exists(app=app, utub_url_id=utub_url_id_a)
    assert _utub_url_row_exists(app=app, utub_url_id=utub_url_id_b)
    expect(page.locator(HPL.BULK_SELECT_EXIT)).to_be_focused()


def test_bulk_delete_partial_permission_skips_others_url(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN, in a UTub the acting user did NOT create, one URL they authored
        (deletable) and one authored by another member (not deletable), both
        selected
    WHEN the user confirms the delete
    THEN the confirm warns a URL will be skipped, the deletable URL is removed,
        the other member's URL survives with an amber "Can't delete" cue, and the
        result banner is the assertive partial variant.
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

    open_bulk_delete_confirm(page=page)

    # Title counts the full selection; the body warns one URL will be skipped;
    # the submit label reflects the single deletable URL.
    expect(page.locator(HPL.HEADER_MODAL)).to_have_text(
        STRINGS.URL_BULK_DELETE_CONFIRM_TITLE.replace("{n}", "2")
    )
    expect(page.locator(HPL.BODY_MODAL)).to_contain_text(
        STRINGS.URL_BULK_DELETE_SKIPPED_WARNING_ONE
    )
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_have_text(
        STRINGS.URL_BULK_DELETE_SUBMIT_ONE
    )

    submit_bulk_delete(page=page)

    # Assert the transient amber "Can't delete" cue on the survivor FIRST — it is
    # removed a few seconds after the delete renders, so poll for it before the
    # (slower) modal-hide + row-fade-removal waits can eat into that budget.
    expect_cant_delete_cue_on_row(page=page, utub_url_id=non_deletable_id)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_element_to_be_removed(page=page, locator=deletable_row)

    # The other member's URL survives.
    expect(
        page.locator(f"{HPL.ROWS_URLS}[utuburlid='{non_deletable_id}']")
    ).to_be_visible()

    # Assertive partial result banner.
    banner = page.locator(HPL.BULK_DELETE_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)partial(\s|$)"))

    # DB: only the acting user's URL was deleted.
    assert not _utub_url_row_exists(app=app, utub_url_id=deletable_id)
    assert _utub_url_row_exists(app=app, utub_url_id=non_deletable_id)


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
    THEN the deck-level outcome announcer shows the deleted-count message,
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

    open_bulk_delete_confirm(page=page)
    submit_bulk_delete(page=page)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_element_to_be_removed(page=page, locator=row_a)
    wait_for_element_to_be_removed(page=page, locator=row_b)

    # Deck-level outcome announcer holds the deleted-count message (survives the
    # bulk-bar teardown on mode exit).
    expect(page.locator(HPL.URL_DECK_OUTCOME_ANNOUNCEMENT)).to_have_text(
        STRINGS.URL_BULK_DELETED.replace("{n}", "2")
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


def test_bulk_delete_confirm_modal_has_correct_aria_labelledby(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Authoritative regression coverage for the homeModalBase.html a11y fix: with
    the confirm modal open on the REAL rendered template, aria-labelledby points
    at the real #confirmModalTitle (not the historical non-existent FormModal id).
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    utub_url_id, _ = _seed_url_in_utub(
        app=app,
        utub_id=utub.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://bulk-delete-aria.test/",
        url_title="Bulk Delete Aria",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[utub_url_id])
    open_bulk_delete_confirm(page=page)

    assert (
        page.locator(HPL.HOME_MODAL).get_attribute("aria-labelledby")
        == "confirmModalTitle"
    )


def test_bulk_delete_invalid_csrf_token_reloads(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a deletable URL selected and the confirm modal open
    WHEN the confirm is submitted with an invalidated CSRF token
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
    open_bulk_delete_confirm(page=page)

    invalidate_csrf_token_on_page(page=page)
    submit_bulk_delete(page=page)

    assert_visited_403_on_invalid_csrf_and_reload(page=page)

    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    assert_login_with_username(page=page, username=username)
    assert_active_utub(page=page, utub_name=utub.name)

    assert _utub_url_row_exists(app=app, utub_url_id=utub_url_id)


def test_bulk_delete_rate_limited_shows_429(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a deletable URL selected and the confirm modal open, user rate-limited
    WHEN the confirm is submitted
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
    open_bulk_delete_confirm(page=page)

    add_forced_rate_limit_header(page=page)
    submit_bulk_delete(page=page)

    assert_on_429_page(page=page)
    assert _utub_url_row_exists(app=app, utub_url_id=utub_url_id)


def test_bulk_delete_submit_reenables_on_server_error(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a deletable URL selected and the confirm modal open
    WHEN the delete POST fails and the failure handler short-circuits without
        navigating (the forced fake failure reads as already-handled, mirroring
        the single-URL delete precedent in test_delete_url_ui)
    THEN the request's .always() re-enables #modalSubmit so the user can retry,
        and nothing is deleted.
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
    open_bulk_delete_confirm(page=page)

    force_next_bulk_delete_ajax_failure_no_navigate(page=page)
    submit_bulk_delete(page=page)

    # The always() handler re-enables the submit button after the failure.
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_enabled()
    assert _utub_url_row_exists(app=app, utub_url_id=utub_url_id)
