from __future__ import annotations

import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.urls import Urls
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.constants import STRINGS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    get_n_other_utubs_this_user_is_member_of,
    get_other_utub_this_user_is_member_of,
    get_utub_this_user_created,
    set_utub_locked_state,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
)
from tests.functional.playwright_utils import (
    get_all_url_ids_in_selected_utub,
    wait_until_hidden,
)
from tests.functional.urls_ui.playwright_utils import (
    bulk_copy_option_by_name,
    enter_multi_select_and_select_urls,
    expect_copy_cue_on_row,
    expect_staged_destination_count,
    open_bulk_copy_picker,
    stage_copy_destination,
    stage_copy_destinations,
    submit_bulk_copy,
)

pytestmark = pytest.mark.urls_ui

USER_ID_FOR_TEST = 1


# --- Seed helpers -------------------------------------------------------------
# The default mock seeds the SAME five URL strings into every UTub, and
# `Urls.url_string` is globally UNIQUE — so every mock URL already exists (same
# `url_id`) in every UTub. Copying a mock URL would therefore always be a
# duplicate-skip. These helpers seed URL strings that exist NOWHERE else, so a
# copy of them lands in the destination as genuinely new.


def _seed_source_url(
    *,
    app: Flask,
    utub_id: int,
    user_id: int,
    url_string: str,
    url_title: str,
    tag_string: str | None = None,
) -> tuple[int, int]:
    """Insert a globally-unique URL + a `Utub_Urls` row into the source UTub.
    Optionally apply one tag to it. Returns (utub_url_id, url_id)."""
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
        utub_url_id = new_utub_url.id
        url_id = raw_url.id

        if tag_string is not None:
            tag = Utub_Tags(utub_id=utub_id, tag_string=tag_string, created_by=user_id)
            db.session.add(tag)
            db.session.flush()
            db.session.add(
                Utub_Url_Tags(
                    utub_id=utub_id,
                    utub_url_id=utub_url_id,
                    utub_tag_id=tag.id,
                )
            )
        db.session.commit()
        return utub_url_id, url_id


def _add_existing_url_to_utub(
    *, app: Flask, utub_id: int, user_id: int, url_id: int, url_title: str
) -> None:
    """Insert an existing (already-created) URL into another UTub — used to
    pre-seed a duplicate in the destination for the partial-success case."""
    with app.app_context():
        db.session.add(
            Utub_Urls(
                utub_id=utub_id,
                url_id=url_id,
                user_id=user_id,
                url_title=url_title,
            )
        )
        db.session.commit()


def _count_dest_rows_for_url(*, app: Flask, utub_id: int, url_id: int) -> int:
    with app.app_context():
        return Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id, Utub_Urls.url_id == url_id
        ).count()


def _count_tags_on_dest_url(*, app: Flask, utub_id: int, url_id: int) -> int:
    """Count the tags carried by the destination UTub's copy of `url_id`."""
    with app.app_context():
        return (
            Utub_Url_Tags.query.join(
                Utub_Urls, Utub_Url_Tags.utub_url_id == Utub_Urls.id
            )
            .filter(Utub_Urls.utub_id == utub_id, Utub_Urls.url_id == url_id)
            .count()
        )


def _lock_all_other_utubs(*, app: Flask, source_utub_id: int) -> None:
    """Lock every UTub except the source, so the copy picker has zero enabled
    destination rows (DD-23 all-locked state)."""
    with app.app_context():
        other_utub_ids = [
            utub.id for utub in Utubs.query.filter(Utubs.id != source_utub_id).all()
        ]
    for utub_id in other_utub_ids:
        set_utub_locked_state(app, utub_id, True)


def _delete_all_other_utubs(*, app: Flask, source_utub_id: int) -> None:
    """Delete every UTub except the source (Utubs cascades to members/urls/tags)
    so the logged-in user is left in exactly one UTub — no copy destination."""
    with app.app_context():
        others = Utubs.query.filter(Utubs.id != source_utub_id).all()
        for utub in others:
            db.session.delete(utub)
        db.session.commit()


# --- Tests --------------------------------------------------------------------


def test_bulk_copy_happy_copies_selected_urls_into_two_destinations(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two source-only URLs selected in multi-select mode
    WHEN the user opens the copy picker, stages TWO destinations, and confirms
    THEN both URLs land in BOTH destinations (multi-destination success banner +
        "Copied" cues), each staged row carried aria-selected simultaneously, and
        both destinations gained both rows.
    """
    app = provide_app
    source = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    dest_a, dest_b = get_n_other_utubs_this_user_is_member_of(
        app, USER_ID_FOR_TEST, source.id, 2
    )
    dest_a_id, dest_a_name = dest_a.id, dest_a.name
    dest_b_id, dest_b_name = dest_b.id, dest_b.name

    utub_url_id_a, url_id_a = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-happy-a.test/",
        url_title="Copy Happy A",
    )
    utub_url_id_b, url_id_b = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-happy-b.test/",
        url_title="Copy Happy B",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(
        page=page, url_ids=[utub_url_id_a, utub_url_id_b]
    )
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    open_bulk_copy_picker(page=page)
    # Stage BOTH destinations; multi-select keeps every staged row selected.
    staged_rows = stage_copy_destinations(
        page=page, utub_names=[dest_a_name, dest_b_name]
    )
    expect_staged_destination_count(page=page, count=2)
    # Multi-select moves the roving tabindex to whichever row was toggled LAST
    # (each toggle calls setActiveRow first), so real DOM focus + tabindex 0 land
    # on the second-staged row while the first-staged row drops to -1 — both stay
    # aria-selected (DD-7 real focus, never aria-activedescendant).
    expect(staged_rows[-1]).to_have_attribute("tabindex", "0")
    expect(staged_rows[0]).to_have_attribute("tabindex", "-1")

    submit_bulk_copy(page=page)

    # Picker closes on success.
    wait_until_hidden(page=page, css_selector=HPL.BULK_COPY_PICKER_MOUNT)

    # Per-card "Copied" cues on both source rows FIRST — they are transient
    # (DOM-removed ~3s after the copy renders), so assert them at the start of the
    # fade budget, before the (persistent) banner assertions.
    expect_copy_cue_on_row(page=page, utub_url_id=utub_url_id_a, kind="copied")
    expect_copy_cue_on_row(page=page, utub_url_id=utub_url_id_b, kind="copied")

    # Success banner — all destinations copied cleanly → success/polite, the
    # multi-destination "Copied to 2 UTubs." wording (count-only, no names).
    banner = page.locator(HPL.BULK_COPY_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)success(\s|$)"))
    expect(page.locator(HPL.BULK_COPY_BANNER_BODY)).to_have_text(
        STRINGS.URLS_COPIED_MULTI.replace("{n}", "2")
    )

    # BOTH destination UTubs now hold both copied URLs.
    for dest_id in (dest_a_id, dest_b_id):
        assert _count_dest_rows_for_url(app=app, utub_id=dest_id, url_id=url_id_a) == 1
        assert _count_dest_rows_for_url(app=app, utub_id=dest_id, url_id=url_id_b) == 1


def test_bulk_copy_partial_across_two_destinations_greens_any_hit(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two source URLs copied into two destinations, one URL already present
        in ONE of the destinations
    WHEN the user copies both into both destinations
    THEN both destinations still receive a copy (destsSucceeded == 2), so the
        aggregate multi-destination PARTIAL banner shows (count-only, no title/
        name), and the pre-existing URL still earns a GREEN "copied" cue because
        it landed in the OTHER destination (green-if-any, DD-8).
    """
    app = provide_app
    source = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    dest_a, dest_b = get_n_other_utubs_this_user_is_member_of(
        app, USER_ID_FOR_TEST, source.id, 2
    )
    dest_a_id, dest_a_name = dest_a.id, dest_a.name
    dest_b_id, dest_b_name = dest_b.id, dest_b.name

    dup_title = "Copy Multi Partial Dup"
    utub_url_id_dup, url_id_dup = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-multi-partial-dup.test/",
        url_title=dup_title,
    )
    utub_url_id_new, url_id_new = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-multi-partial-new.test/",
        url_title="Copy Multi Partial New",
    )
    # Pre-seed the duplicate into ONLY dest A — so dest A skips it (duplicate) but
    # dest B copies it, keeping BOTH destinations "succeeded" and the dup URL
    # green-if-any across destinations.
    _add_existing_url_to_utub(
        app=app,
        utub_id=dest_a_id,
        user_id=USER_ID_FOR_TEST,
        url_id=url_id_dup,
        url_title=dup_title,
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(
        page=page, url_ids=[utub_url_id_dup, utub_url_id_new]
    )
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    open_bulk_copy_picker(page=page)
    stage_copy_destinations(page=page, utub_names=[dest_a_name, dest_b_name])
    expect_staged_destination_count(page=page, count=2)
    submit_bulk_copy(page=page)

    wait_until_hidden(page=page, css_selector=HPL.BULK_COPY_PICKER_MOUNT)

    # Per-card cues FIRST (transient): BOTH source rows are green — the "new" URL
    # copied everywhere, and the "dup" URL copied into dest B even though dest A
    # skipped it (green-if-any, DD-8).
    expect_copy_cue_on_row(page=page, utub_url_id=utub_url_id_new, kind="copied")
    expect_copy_cue_on_row(page=page, utub_url_id=utub_url_id_dup, kind="copied")

    # Aggregate multi-destination partial banner — concise count only, never a URL
    # title or a UTub name.
    banner = page.locator(HPL.BULK_COPY_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)partial(\s|$)"))
    body = page.locator(HPL.BULK_COPY_BANNER_BODY)
    expect(body).not_to_contain_text(dup_title)
    expect(body).not_to_contain_text(dest_a_name)
    expect(body).not_to_contain_text(dest_b_name)

    # Dest A: gained only the new URL (dup already there, single row);
    # Dest B: gained BOTH the new and the (not-yet-present) dup URL.
    assert _count_dest_rows_for_url(app=app, utub_id=dest_a_id, url_id=url_id_new) == 1
    assert _count_dest_rows_for_url(app=app, utub_id=dest_a_id, url_id=url_id_dup) == 1
    assert _count_dest_rows_for_url(app=app, utub_id=dest_b_id, url_id=url_id_new) == 1
    assert _count_dest_rows_for_url(app=app, utub_id=dest_b_id, url_id=url_id_dup) == 1


def test_bulk_copy_locked_destination_row_is_disabled_and_labeled(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    DD-3/DD-4/DD-10/DD-12: a locked destination is skipped-and-reported at the
    service layer, but the picker never lets the user stage it in the first place.

    GIVEN one of the user's other UTubs is locked
    WHEN the user opens the copy picker
    THEN the locked row is present-but-disabled (aria-disabled), shows the
        "🔒 locked" text label and NOT the role badge; an enabled row instead
        shows its role badge and NOT the locked label; and staging a clean
        destination + confirming still copies successfully.
    """
    app = provide_app
    source = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    locked_dest, clean_dest = get_n_other_utubs_this_user_is_member_of(
        app, USER_ID_FOR_TEST, source.id, 2
    )
    locked_dest_name = locked_dest.name
    clean_dest_id, clean_dest_name = clean_dest.id, clean_dest.name
    set_utub_locked_state(app, locked_dest.id, True)

    utub_url_id, url_id = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-locked-dest.test/",
        url_title="Copy Locked Dest",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[utub_url_id])
    open_bulk_copy_picker(page=page)

    # The locked row is present, disabled, unstageable, and labeled "🔒 locked"
    # WITHOUT a role badge (DD-12 mutual exclusivity).
    locked_row = bulk_copy_option_by_name(page=page, utub_name=locked_dest_name)
    expect(locked_row).to_have_attribute("aria-disabled", "true")
    expect(locked_row.locator(HPL.BULK_COPY_LOCKED_LABEL)).to_have_text(
        STRINGS.URL_BULK_COPY_LOCKED_LABEL
    )
    expect(locked_row.locator(HPL.BULK_COPY_ROLE_BADGE)).to_have_count(0)
    # Clicking the locked row never stages it: the row carries aria-disabled, so
    # Playwright treats it as not-enabled — force the click past actionability to
    # exercise the picker's own `if (row.hasClass("disabled")) return;` guard and
    # prove it stays unstaged.
    locked_row.click(force=True)
    expect(locked_row).to_have_attribute("aria-selected", "false")

    # An enabled row instead shows its role badge (member/creator/cocreator) and
    # NOT the locked label.
    clean_row = bulk_copy_option_by_name(page=page, utub_name=clean_dest_name)
    role_badge = clean_row.locator(HPL.BULK_COPY_ROLE_BADGE)
    expect(role_badge).to_have_count(1)
    expect(role_badge).not_to_be_empty()
    expect(clean_row.locator(HPL.BULK_COPY_LOCKED_LABEL)).to_have_count(0)

    # Staging the clean destination + confirming copies successfully.
    stage_copy_destination(page=page, utub_name=clean_dest_name)
    submit_bulk_copy(page=page)
    wait_until_hidden(page=page, css_selector=HPL.BULK_COPY_PICKER_MOUNT)
    expect(page.locator(HPL.BULK_COPY_BANNER)).to_be_visible()
    assert _count_dest_rows_for_url(app=app, utub_id=clean_dest_id, url_id=url_id) == 1


def test_bulk_copy_filter_narrows_destinations_then_copies(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the copy picker open with several destination rows
    WHEN the user types in the filter box
    THEN a non-matching query hides every row + shows the no-results message (Copy
        stays disabled), and filtering to a destination's name reveals it so it can
        be staged and copied.
    """
    app = provide_app
    source = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    dest = get_other_utub_this_user_is_member_of(app, USER_ID_FOR_TEST, source.id)
    dest_id, dest_name = dest.id, dest.name

    utub_url_id, url_id = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-filter.test/",
        url_title="Copy Filter",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )
    enter_multi_select_and_select_urls(page=page, url_ids=[utub_url_id])
    open_bulk_copy_picker(page=page)

    # The filter box is focused on open.
    filter_input = page.locator(HPL.BULK_COPY_FILTER_INPUT)
    expect(filter_input).to_be_focused()

    mount = HPL.BULK_COPY_PICKER_MOUNT
    # A non-matching query hides every row and announces the no-results message;
    # Copy stays disabled (nothing staged).
    filter_input.fill("zzq-no-such-utub-zzq")
    expect(page.locator(f"{mount} {HPL.BULK_COPY_NO_MATCHES}")).to_be_visible()
    expect(page.locator(f"{mount} {HPL.BULK_COPY_OPTION_VISIBLE}")).to_have_count(0)
    expect(page.locator(f"{mount} {HPL.BUTTON_BULK_COPY_CONFIRM}")).to_be_disabled()

    # Filtering to the destination's name reveals it; stage + confirm the copy.
    filter_input.fill(dest_name)
    dest_row = bulk_copy_option_by_name(page=page, utub_name=dest_name)
    expect(dest_row).to_be_visible()
    dest_row.click()
    expect(dest_row).to_have_attribute("aria-selected", "true")

    submit_bulk_copy(page=page)
    wait_until_hidden(page=page, css_selector=HPL.BULK_COPY_PICKER_MOUNT)

    banner = page.locator(HPL.BULK_COPY_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)success(\s|$)"))
    assert _count_dest_rows_for_url(app=app, utub_id=dest_id, url_id=url_id) == 1


def test_bulk_copy_arrow_key_navigation_moves_focus_and_tabindex(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the copy picker open with several enabled destination rows
    WHEN the user roves with ArrowDown/ArrowUp
    THEN real DOM focus and the roving tabindex move together (no staging), and
        the focused row can then be staged with Enter.
    """
    app = provide_app
    source = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    utub_url_id_a, _ = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-nav-a.test/",
        url_title="Copy Nav A",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[utub_url_id_a])
    open_bulk_copy_picker(page=page)

    rows = page.locator(f"{HPL.BULK_COPY_PICKER_MOUNT} {HPL.BULK_COPY_OPTION_ENABLED}")
    expect(rows).to_have_count(4)  # UTubs 2-5 (all unlocked) for a member of 5
    first_row = rows.nth(0)
    second_row = rows.nth(1)

    # On open, real focus is on the FILTER INPUT (so the user can type to narrow
    # immediately); the first enabled row holds tabindex 0 as the roving entry.
    expect(page.locator(HPL.BULK_COPY_FILTER_INPUT)).to_be_focused()
    expect(first_row).to_have_attribute("tabindex", "0")

    # ArrowDown from the input enters the list at the first enabled row.
    page.keyboard.press("ArrowDown")
    expect(first_row).to_be_focused()
    expect(first_row).to_have_attribute("tabindex", "0")

    # ArrowDown roves focus + tabindex to the second row (no staging).
    page.keyboard.press("ArrowDown")
    expect(second_row).to_be_focused()
    expect(second_row).to_have_attribute("tabindex", "0")
    expect(first_row).to_have_attribute("tabindex", "-1")
    expect(second_row).to_have_attribute("aria-selected", "false")

    # ArrowUp roves back to the first row.
    page.keyboard.press("ArrowUp")
    expect(first_row).to_be_focused()
    expect(first_row).to_have_attribute("tabindex", "0")

    # Enter on the focused row stages it (keyup path).
    first_row.press("Enter")
    expect(first_row).to_have_attribute("aria-selected", "true")
    expect(
        page.locator(f"{HPL.BULK_COPY_PICKER_MOUNT} {HPL.BUTTON_BULK_COPY_CONFIRM}")
    ).to_be_enabled()


def test_bulk_copy_partial_skips_duplicate_with_already_there_cue(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two selected source URLs, one already present in the destination
    WHEN the user copies both
    THEN the new URL is copied ("Copied") and the duplicate is skipped ("Already
        there"), and the partial banner carries no URL title.
    """
    app = provide_app
    source = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    dest = get_other_utub_this_user_is_member_of(app, USER_ID_FOR_TEST, source.id)
    dest_id, dest_name = dest.id, dest.name

    dup_title = "Copy Partial Dup"
    utub_url_id_dup, url_id_dup = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-partial-dup.test/",
        url_title=dup_title,
    )
    utub_url_id_new, url_id_new = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-partial-new.test/",
        url_title="Copy Partial New",
    )
    # Pre-seed the duplicate into the destination so copying it is skipped.
    _add_existing_url_to_utub(
        app=app,
        utub_id=dest_id,
        user_id=USER_ID_FOR_TEST,
        url_id=url_id_dup,
        url_title=dup_title,
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(
        page=page, url_ids=[utub_url_id_dup, utub_url_id_new]
    )
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    open_bulk_copy_picker(page=page)
    stage_copy_destination(page=page, utub_name=dest_name)
    submit_bulk_copy(page=page)

    wait_until_hidden(page=page, css_selector=HPL.BULK_COPY_PICKER_MOUNT)

    # Per-card cues FIRST (transient): the new URL copied, the duplicate flagged
    # "already there".
    expect_copy_cue_on_row(page=page, utub_url_id=utub_url_id_new, kind="copied")
    expect_copy_cue_on_row(page=page, utub_url_id=utub_url_id_dup, kind="skipped")

    # Partial banner — concise count only, never a URL title.
    banner = page.locator(HPL.BULK_COPY_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)partial(\s|$)"))
    body = page.locator(HPL.BULK_COPY_BANNER_BODY)
    expect(body).not_to_contain_text(dup_title)

    # Destination gained only the new URL; the duplicate stayed a single row.
    assert _count_dest_rows_for_url(app=app, utub_id=dest_id, url_id=url_id_new) == 1
    assert _count_dest_rows_for_url(app=app, utub_id=dest_id, url_id=url_id_dup) == 1


def test_bulk_copy_button_absent_when_user_in_only_one_utub(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user who belongs to exactly one UTub (no copy destination exists)
    WHEN they enter multi-select mode and select a URL
    THEN the copy bulk-action button is absent from the bar (isAvailable gate).
    """
    app = provide_app
    source = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    _delete_all_other_utubs(app=app, source_utub_id=source.id)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 1

    enter_multi_select_and_select_urls(page=page, url_ids=[url_ids[0]])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")

    # The tag action still renders (single-UTub is fine for tagging), proving the
    # action bar built successfully — so the copy action's absence is the
    # isAvailable gate (no other UTub to copy to), not a broken bar.
    expect(page.locator(HPL.BUTTON_BULK_ADD_TAGS)).to_have_count(1)
    expect(page.locator(HPL.BUTTON_BULK_COPY_URLS)).to_have_count(0)


def test_bulk_copy_does_not_carry_tags(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a tagged source URL selected for copy
    WHEN it is copied into the destination
    THEN the destination's copy carries zero tags (URL string + title only).
    """
    app = provide_app
    source = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    dest = get_other_utub_this_user_is_member_of(app, USER_ID_FOR_TEST, source.id)
    dest_id, dest_name = dest.id, dest.name

    utub_url_id_tagged, url_id_tagged = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-tagged.test/",
        url_title="Copy Tagged",
        tag_string="CopyTag",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[utub_url_id_tagged])
    open_bulk_copy_picker(page=page)
    stage_copy_destination(page=page, utub_name=dest_name)
    submit_bulk_copy(page=page)

    wait_until_hidden(page=page, css_selector=HPL.BULK_COPY_PICKER_MOUNT)
    expect(page.locator(HPL.BULK_COPY_BANNER)).to_be_visible()

    assert _count_dest_rows_for_url(app=app, utub_id=dest_id, url_id=url_id_tagged) == 1
    assert _count_tags_on_dest_url(app=app, utub_id=dest_id, url_id=url_id_tagged) == 0


def test_bulk_copy_all_other_utubs_locked_shows_message_and_disables_copy(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    DD-23: every other UTub is locked.

    GIVEN a source URL selected with every other UTub locked
    WHEN the user opens the copy picker
    THEN the all-locked message renders (role=status, aria-live=polite) and the
        Copy button stays disabled — no focusable destination row.
    """
    app = provide_app
    source = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    _lock_all_other_utubs(app=app, source_utub_id=source.id)

    utub_url_id_a, _ = _seed_source_url(
        app=app,
        utub_id=source.id,
        user_id=USER_ID_FOR_TEST,
        url_string="https://copy-locked.test/",
        url_title="Copy Locked",
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[utub_url_id_a])
    open_bulk_copy_picker(page=page)

    all_locked = page.locator(HPL.BULK_COPY_ALL_LOCKED)
    expect(all_locked).to_be_visible()
    expect(all_locked).to_have_text(STRINGS.URL_BULK_COPY_ALL_LOCKED)
    expect(all_locked).to_have_attribute("role", "status")
    expect(all_locked).to_have_attribute("aria-live", "polite")

    # No enabled destination rows, and Copy stays disabled (DD-18).
    expect(
        page.locator(f"{HPL.BULK_COPY_PICKER_MOUNT} {HPL.BULK_COPY_OPTION_ENABLED}")
    ).to_have_count(0)
    expect(
        page.locator(f"{HPL.BULK_COPY_PICKER_MOUNT} {HPL.BUTTON_BULK_COPY_CONFIRM}")
    ).to_be_disabled()
