from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    get_all_url_ids_in_selected_utub,
    select_utub_by_name,
    wait_then_click_element,
)
from tests.functional.tags_ui.playwright_utils import get_utub_tag_filter_selector
from tests.functional.urls_ui.playwright_assert_utils import (
    assert_urls_are_multi_selected,
)
from tests.functional.urls_ui.playwright_utils import (
    enter_multi_select_mode,
    focus_url_search_input,
    tap_url_checkbox,
    wait_for_url_search_filter_applied,
)
from tests.functional.utubs_ui.playwright_utils import open_update_utub_name_input

pytestmark = pytest.mark.urls_ui

USER_ID_FOR_TEST = 1
UNMATCHED_TAG_STRING = "multi-select-filter-tag"


def _expected_announcement(*, selected_count: int, hidden_count: int = 0) -> str:
    """Mirror bulk-bar.ts's composeAnnouncement() using the real backend copy
    re-exported through UI_TEST_STRINGS, so the assertion is locked to the same
    string bridge the production announcement is composed from."""
    if selected_count == 0:
        return UTS.URL_BULK_NONE_SELECTED
    if selected_count == 1:
        count_text = UTS.URL_BULK_SELECTED_COUNT_ONE
    else:
        count_text = UTS.URL_BULK_SELECTED_COUNT.replace("{n}", str(selected_count))
    if hidden_count == 0:
        return count_text
    hidden_text = UTS.URL_BULK_N_HIDDEN.replace("{n}", str(hidden_count))
    return f"{count_text}, {hidden_text}"


def test_toggle_enters_and_exits_multi_select_mode(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with URLs
    WHEN the user toggles multi-select mode on, then off
    THEN entering shows checkboxes + the bulk bar and disables the two DD-20
        entry points (#urlBtnCreate, #toCrossUtubSearch), and exiting restores
        single-select affordances
    """
    app = provide_app
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    # Mode off: no checkboxes, bar hidden, entry points available.
    expect(page.locator(HPL.URL_SELECT_CHECKBOX).first).to_be_hidden()
    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_CORNER_URL_CREATE)).to_be_visible()
    expect(page.locator(HPL.CROSS_SEARCH_TRIGGER)).to_be_visible()

    enter_multi_select_mode(page=page)

    # Mode on: checkboxes revealed, DD-20 entry points disabled. The toggle
    # itself is hidden in mode (the header Exit ✕ is the way out now), so no
    # solid green pressed-state block sits beside the icon-only controls.
    expect(page.locator(HPL.URL_SELECT_CHECKBOX).first).to_be_visible()
    expect(page.locator(HPL.BUTTON_CORNER_URL_CREATE)).to_be_hidden()
    expect(page.locator(HPL.CROSS_SEARCH_TRIGGER)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_be_hidden()

    # Exit via the header Exit ✕ (the toggle is hidden in mode).
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_EXIT)
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()
    expect(page.locator(HPL.URL_SELECT_CHECKBOX).first).to_be_hidden()
    # The toggle reappears (unpressed) on exit.
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_be_visible()
    expect(page.locator(HPL.BUTTON_CORNER_URL_CREATE)).to_be_visible()
    expect(page.locator(HPL.CROSS_SEARCH_TRIGGER)).to_be_visible()


def test_tapping_rows_updates_count_marks_and_announcement(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN multi-select mode active
    WHEN the user taps N row checkboxes, then taps a selected one again
    THEN the count, .multiSelected marks, and the SR announcement track the
        selection, and re-tapping toggles that row off
    """
    app = provide_app
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 3

    enter_multi_select_mode(page=page)

    tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    tap_url_checkbox(page=page, utub_url_id=url_ids[1])

    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(2)
    assert_urls_are_multi_selected(page=page, utub_url_ids=[url_ids[0], url_ids[1]])
    expect(page.locator(HPL.BULK_SELECTION_ANNOUNCEMENT)).to_have_text(
        _expected_announcement(selected_count=2)
    )

    # Re-tap the first selected row to toggle it off.
    tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(1)
    expect(page.locator(HPL.BULK_SELECTION_ANNOUNCEMENT)).to_have_text(
        _expected_announcement(selected_count=1)
    )


def test_select_all_selects_every_visible_row(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN multi-select mode active with all rows visible
    WHEN the user clicks Select All
    THEN every visible row is marked and the count equals the visible row count
    """
    app = provide_app
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    visible_count = len(url_ids)

    enter_multi_select_mode(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_ALL)

    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text(str(visible_count))
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(visible_count)
    assert_urls_are_multi_selected(page=page, utub_url_ids=url_ids)


def test_selection_survives_tag_filter(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN 3 selected URLs where a tag applies to only 2 of them
    WHEN a tag filter hides the untagged (still-selected) row
    THEN the count stays 3, the row keeps its .multiSelected mark, the hidden
        hint shows, and the announcement carries the "N hidden by filter"
        clause — and clearing the filter restores full visibility with the
        selection intact.

    Note: this exercises survival across a filter apply/clear (a show/hide of
    existing rows). Survival across a genuine deck-diff card *rebuild*
    (reapplyMultiSelectMark on build / pruneRemovedFromSelection on removal) has
    no deterministic UI trigger here — a UTub switch clears selection by design
    and a stale-data diff needs a backend race — so that reconcile path is
    covered by the Vitest deck / bulk-selection suites (Steps 4, 6, 7).
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    tag = add_tag_to_utub_user_created(
        app, utub.id, USER_ID_FOR_TEST, UNMATCHED_TAG_STRING
    )
    tag_id = tag.id

    # Apply the tag to the first two URLs so a filter on it hides the third.
    with app.app_context():
        utub_urls: list[Utub_Urls] = (
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub.id)
            .order_by(Utub_Urls.id)
            .all()
        )
        assert len(utub_urls) >= 3
        tagged_ids = [utub_urls[0].id, utub_urls[1].id]
        untagged_id = utub_urls[2].id
        for utub_url_id in tagged_ids:
            db.session.add(
                Utub_Url_Tags(
                    utub_id=utub.id, utub_url_id=utub_url_id, utub_tag_id=tag_id
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

    # Apply the tag filter — the untagged (still-selected) row is hidden.
    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    untagged_row = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{untagged_id}']").first
    expect(untagged_row).to_be_hidden()

    # Count stays 3 (hidden rows stay selected); the mark survives on the
    # hidden row; the visible hidden hint + announcement reflect the 1 hidden
    # selection.
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("3")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(3)
    assert_urls_are_multi_selected(page=page, utub_url_ids=selected_ids)
    hidden_hint = page.locator(HPL.BULK_SELECT_HIDDEN_HINT)
    expect(hidden_hint).to_be_visible()
    expect(hidden_hint).to_have_text(UTS.URL_BULK_N_HIDDEN.replace("{n}", "1"))
    expect(page.locator(HPL.BULK_SELECTION_ANNOUNCEMENT)).to_have_text(
        _expected_announcement(selected_count=3, hidden_count=1)
    )

    # Clear the filter — the previously hidden row returns, selection intact,
    # hidden hint gone.
    wait_then_click_element(page=page, css_selector=utub_tag_filter)
    expect(untagged_row).to_be_visible()
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("3")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(3)
    assert_urls_are_multi_selected(page=page, utub_url_ids=selected_ids)
    expect(hidden_hint).to_be_hidden()
    expect(page.locator(HPL.BULK_SELECTION_ANNOUNCEMENT)).to_have_text(
        _expected_announcement(selected_count=3)
    )


def test_clear_zeroes_and_exit_restores_single_select(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a live multi-selection
    WHEN the user clicks Clear, then Exit
    THEN Clear empties the selection and Exit leaves mode, restoring the
        single-select tap-to-expand behavior
    """
    app = provide_app
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 2

    enter_multi_select_mode(page=page)
    tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    tap_url_checkbox(page=page, utub_url_id=url_ids[1])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    # Clear empties the selection but stays in mode.
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_CLEAR)
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("0")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(0)

    # Exit leaves mode.
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_EXIT)
    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(page.locator(HPL.URL_SELECT_CHECKBOX).first).to_be_hidden()

    # Single-select tap-to-expand is restored.
    row_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_ids[0]}']"
    wait_then_click_element(page=page, css_selector=row_selector)
    expect(page.locator(HPL.ROW_SELECTED_URL)).to_have_count(1)
    expect(page.locator(HPL.ROW_SELECTED_URL).first).to_have_attribute(
        "utuburlid", str(url_ids[0])
    )


def test_go_to_icon_suppressed_in_mode_and_does_not_leak_after_exit(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN multi-select mode active
    WHEN the user taps a URL row (a selection target, not an interactive URL)
    THEN the per-row "go-to URL" icon (.goToUrlIcon) stays hidden — the tap
        handler leaves the row's .visible-on-focus class on, but the deck-level
        #URLDeck.multiSelectActive suppression keeps the icon hidden; AND after
        Clear/Exit the icon does NOT leak back onto that previously-tapped row in
        restored single-select mode.
    """
    app = provide_app
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 1
    tapped_row = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{url_ids[0]}']").first
    go_to_icon = tapped_row.locator(HPL.GO_TO_URL_ICON)

    enter_multi_select_mode(page=page)

    # Tap the row (via its checkbox) to select it — the tap handler focuses the
    # row and adds .visible-on-focus, which would otherwise reveal the icon.
    tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")

    # In mode the go-to icon is suppressed on the tapped row despite the focus.
    expect(go_to_icon).to_be_hidden()

    # Clear the selection and Exit back to single-select.
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_CLEAR)
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_EXIT)
    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()

    # The icon does not leak back onto the previously-tapped row in single-select.
    expect(go_to_icon).to_be_hidden()


def test_switching_utub_clears_selection_and_hides_bar(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a live multi-selection in one UTub
    WHEN the user switches to a different UTub
    THEN multi-select mode exits: the bar hides, the toggle un-presses, and no
        rows remain marked
    """
    app = provide_app
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 2

    enter_multi_select_mode(page=page)
    tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    tap_url_checkbox(page=page, utub_url_id=url_ids[1])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    select_utub_by_name(page=page, utub_name=UTS.TEST_UTUB_NAME_2)

    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(0)


def test_header_hosts_selection_context_desktop_hides_tag_icon(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with URLs on desktop
    WHEN the user enters multi-select mode
    THEN the relocated selection context (#bulkSelectContext with #bulkSelectCount)
        plus the header Exit ✕ render in the HEADER (not the bottom bar), the
        mobile-only #bulkTagFilterIcon stays hidden on desktop, and the header ✕
        leaves mode.
    """
    app = provide_app
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    # Mode off: the selection context is hidden.
    expect(page.locator(HPL.BULK_SELECT_CONTEXT)).to_be_hidden()

    enter_multi_select_mode(page=page)

    # The context + its count + the header Exit are visible; the
    # #bulkTagFilterIcon is the mobile-only affordance and stays hidden on desktop.
    context = page.locator(HPL.BULK_SELECT_CONTEXT)
    expect(context).to_be_visible()
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_be_visible()
    expect(page.locator(HPL.BULK_SELECT_EXIT)).to_be_visible()
    expect(page.locator(HPL.BULK_TAG_FILTER_ICON)).to_be_hidden()

    # The count/Exit are NOT in the bottom bar anymore (only actions live there).
    bar = page.locator(HPL.BULK_ACTION_BAR)
    expect(bar.locator(HPL.BULK_SELECT_COUNT)).to_have_count(0)
    expect(bar.locator(HPL.BULK_SELECT_EXIT)).to_have_count(0)

    # The header ✕ leaves mode.
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_EXIT)
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()
    expect(context).to_be_hidden()


def test_utub_name_edit_blocked_in_mode_and_restored_after_exit(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN an owned UTub whose name is normally inline-editable
    WHEN the user enters multi-select mode
    THEN the UTub name zone is replaced by the selection context and its editor
        cannot be opened (name wrap hidden, edit input never shown); AND after
        Exit the name zone returns and clicking it opens the editor again.
    """
    app = provide_app
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    # Baseline: the name wrap is present and the editor opens on a wrap click.
    expect(page.locator(HPL.WRAP_UTUB_NAME_UPDATE)).to_be_visible()

    enter_multi_select_mode(page=page)

    # In mode the name zone is hidden (selection context takes over) and the
    # editor is unreachable — the input stays hidden.
    expect(page.locator(HPL.WRAP_UTUB_NAME_UPDATE)).to_be_hidden()
    expect(page.locator(HPL.HEADER_URL_DECK)).to_be_hidden()
    expect(page.locator(HPL.INPUT_UTUB_NAME_UPDATE)).to_be_hidden()
    expect(page.locator(HPL.BULK_SELECT_CONTEXT)).to_be_visible()

    # Exit restores the name zone; clicking it opens the editor again.
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_EXIT)
    expect(page.locator(HPL.WRAP_UTUB_NAME_UPDATE)).to_be_visible()
    open_update_utub_name_input(page=page)
    expect(page.locator(HPL.INPUT_UTUB_NAME_UPDATE)).to_be_visible()
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_NAME_CANCEL_UPDATE)
    expect(page.locator(HPL.INPUT_UTUB_NAME_UPDATE)).to_be_hidden()


def test_text_filter_narrows_rows_with_selection_surviving(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN every visible row selected in multi-select mode
    WHEN the funnel text-filter narrows the deck to a single URL
    THEN the hidden (still-selected) rows keep their marks, the count is
        unchanged, and the hidden hint surfaces the newly-hidden selection count
        — mirroring test_selection_survives_tag_filter for the text filter.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    # Collect (id, url_string) for every URL so a full-url-string search term
    # deterministically matches exactly one row (mock strings are distinct).
    with app.app_context():
        utub_urls: list[Utub_Urls] = (
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub.id)
            .order_by(Utub_Urls.id)
            .all()
        )
        assert len(utub_urls) >= 2
        total_urls = len(utub_urls)
        search_term = utub_urls[0].standalone_url.url_string
        matching = [
            utub_url
            for utub_url in utub_urls
            if search_term.lower() in (utub_url.url_title or "").lower()
            or search_term.lower() in utub_url.standalone_url.url_string.lower()
        ]
        expected_visible = len(matching)
    # The full URL string is unique to its own row.
    assert expected_visible == 1
    expected_hidden = total_urls - expected_visible

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_mode(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_ALL)
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text(str(total_urls))

    # Apply the funnel text filter (always-visible input on desktop).
    focus_url_search_input(page=page)
    page.locator(HPL.URL_SEARCH_INPUT).fill(search_term)
    wait_for_url_search_filter_applied(page=page)

    # Only the matching row stays visible; the rest are search-hidden but still
    # selected. The text filter toggles `searchable` (not `filterable`), so count
    # the rows bulk-bar treats as visible: filterable AND not search-hidden.
    search_visible = f"{HPL.ROWS_URLS}[filterable='true'][searchable='true']"
    expect(page.locator(search_visible)).to_have_count(expected_visible)
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text(str(total_urls))
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(total_urls)
    hidden_hint = page.locator(HPL.BULK_SELECT_HIDDEN_HINT)
    expect(hidden_hint).to_be_visible()
    expect(hidden_hint).to_have_text(
        UTS.URL_BULK_N_HIDDEN.replace("{n}", str(expected_hidden))
    )
    expect(page.locator(HPL.BULK_SELECTION_ANNOUNCEMENT)).to_have_text(
        _expected_announcement(selected_count=total_urls, hidden_count=expected_hidden)
    )
