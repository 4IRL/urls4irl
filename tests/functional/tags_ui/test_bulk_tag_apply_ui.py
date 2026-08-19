from __future__ import annotations

import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.constants import STRINGS, TAG_CONSTANTS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    count_urls_with_tag_applied_by_tag_string,
    get_tag_in_utub_by_tag_string,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    wait_then_click_element,
    wait_until_hidden,
    wait_until_in_focus,
)
from tests.functional.tags_ui.playwright_utils import (
    enter_multi_select_and_select_urls,
    expect_badge_count_on_url_row,
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
    open_bulk_tag_picker,
    stage_bulk_new_tag,
    stage_bulk_tag_suggestion,
    submit_bulk_tags,
    type_in_bulk_tag_combobox,
)

pytestmark = pytest.mark.tags_ui

USER_ID_FOR_TEST = 1
FRESH_TAG_ALPHA = "BulkAlpha"
FRESH_TAG_BETA = "BulkBeta"
FRESH_TAG_SINGLE = "BulkFresh"
SHARED_TAG = "SharedTag"


def _get_url_ids_ordered(*, app: Flask, utub_id: int) -> list[int]:
    """Return every URL id in a UTub ordered by primary key (stable across runs)."""
    with app.app_context():
        return [
            utub_url.id
            for utub_url in Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id)
            .order_by(Utub_Urls.id)
            .all()
        ]


def _get_url_title(*, app: Flask, utub_url_id: int) -> str:
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        return utub_url.url_title


def _seed_tag_on_url(
    *, app: Flask, utub_id: int, user_id: int, utub_url_id: int, tag_string: str
) -> int:
    """Create a UTub tag and apply it to exactly one URL. Returns the new tag id."""
    with app.app_context():
        new_tag = Utub_Tags(utub_id=utub_id, tag_string=tag_string, created_by=user_id)
        db.session.add(new_tag)
        db.session.flush()
        tag_id = new_tag.id
        db.session.add(
            Utub_Url_Tags(
                utub_id=utub_id,
                utub_url_id=utub_url_id,
                utub_tag_id=tag_id,
                user_id=user_id,
            )
        )
        db.session.commit()
        return tag_id


def _seed_url_at_tag_limit(
    *, app: Flask, utub_id: int, user_id: int, utub_url_id: int
) -> None:
    """Apply MAX_URL_TAGS distinct tags to a single URL so it sits exactly at the
    per-URL tag limit — any further tag applied in a bulk request is skipped."""
    with app.app_context():
        for index in range(TAG_CONSTANTS.MAX_URL_TAGS):
            new_tag = Utub_Tags(
                utub_id=utub_id,
                tag_string=f"limit-tag-{index}",
                created_by=user_id,
            )
            db.session.add(new_tag)
            db.session.flush()
            db.session.add(
                Utub_Url_Tags(
                    utub_id=utub_id,
                    utub_url_id=utub_url_id,
                    utub_tag_id=new_tag.id,
                    user_id=user_id,
                )
            )
        db.session.commit()


def test_bulk_apply_tags_to_multiple_urls_shows_badges_and_success_banner(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with untagged URLs
    WHEN the user enters multi-select mode, selects two URLs, opens the bulk tag
        picker, stages two fresh tags, and submits
    THEN both selected URLs gain both tag badges, the success banner renders, and
        the two new tags appear in the tag deck.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_ids = _get_url_ids_ordered(app=app, utub_id=utub.id)
    assert len(url_ids) >= 2
    url_a, url_b = url_ids[0], url_ids[1]

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[url_a, url_b])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    open_bulk_tag_picker(page=page)
    stage_bulk_new_tag(page=page, text=FRESH_TAG_ALPHA)
    stage_bulk_new_tag(page=page, text=FRESH_TAG_BETA)
    submit_bulk_tags(page=page)

    # Picker closes on success.
    wait_until_hidden(page=page, css_selector=HPL.BULK_TAG_PICKER_MOUNT)

    # Both selected URLs gained both badges.
    expect_badge_count_on_url_row(page=page, utub_url_id=url_a, expected=2)
    expect_badge_count_on_url_row(page=page, utub_url_id=url_b, expected=2)

    # Success banner shows the applied-to-2 copy.
    banner = page.locator(HPL.BULK_TAG_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)success(\s|$)"))
    expect(banner.locator(".bulkTagBannerBody")).to_have_text(
        STRINGS.URL_BULK_TAGS_APPLIED.replace("{n}", "2")
    )

    # Both new tags are now filters in the tag deck.
    for tag_string in (FRESH_TAG_ALPHA, FRESH_TAG_BETA):
        tag = get_tag_in_utub_by_tag_string(app, utub.id, tag_string)
        tag_filter = (
            f'{HPL.LIST_TAGS} {HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}="{tag.id}"]'
        )
        expect(page.locator(tag_filter)).to_be_visible()


def test_bulk_apply_shared_tag_syncs_deck_count_once_per_tag(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Once-per-tag deck count (DD-23), end-to-end.

    GIVEN a UTub where one URL already carries a tag shared with two other URLs
    WHEN the user bulk-applies that same tag across all three selected URLs in one
        request (re-applying it to the two that lack it)
    THEN the tag-deck count's total digit equals the actual post-batch UTub-wide
        count of URLs carrying that tag — proving the deck sync ran once per
        distinct tag rather than a redundant per-card increment.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_ids = _get_url_ids_ordered(app=app, utub_id=utub.id)
    assert len(url_ids) >= 3
    url_a, url_b, url_c = url_ids[0], url_ids[1], url_ids[2]

    # URL A already carries the shared tag (deck shows it applied to 1 URL).
    shared_tag_id = _seed_tag_on_url(
        app=app,
        utub_id=utub.id,
        user_id=USER_ID_FOR_TEST,
        utub_url_id=url_a,
        tag_string=SHARED_TAG,
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[url_a, url_b, url_c])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("3")

    open_bulk_tag_picker(page=page)
    # Stage the existing shared tag (BULK mode does not exclude already-applied
    # tags), so it is applied to URLs B and C in this one request; A no-ops it.
    stage_bulk_tag_suggestion(page=page, tag_text=SHARED_TAG)
    submit_bulk_tags(page=page)

    wait_until_hidden(page=page, css_selector=HPL.BULK_TAG_PICKER_MOUNT)

    # The two URLs that lacked the tag gained a badge; the one that had it did not
    # gain a second copy.
    expect_badge_count_on_url_row(page=page, utub_url_id=url_b, expected=1)
    expect_badge_count_on_url_row(page=page, utub_url_id=url_c, expected=1)
    expect_badge_count_on_url_row(page=page, utub_url_id=url_a, expected=1)

    # The deck count's total digit tracks the real post-batch UTub-wide count (3),
    # written once for the whole batch — not incremented once per applied card.
    post_batch_total = count_urls_with_tag_applied_by_tag_string(
        app, utub.id, SHARED_TAG
    )
    assert post_batch_total == 3
    visible, total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=shared_tag_id
    )
    assert total == post_batch_total
    assert visible == post_batch_total


def test_bulk_apply_partial_success_skips_over_limit_url(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two selected URLs, one already at the per-URL tag limit
    WHEN the user bulk-applies a fresh tag to both
    THEN the under-limit URL gains the badge, the at-limit URL gains none, and the
        partial banner names the skipped URL.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_ids = _get_url_ids_ordered(app=app, utub_id=utub.id)
    assert len(url_ids) >= 2
    url_under_limit = url_ids[0]
    url_at_limit = url_ids[-1]
    skipped_title = _get_url_title(app=app, utub_url_id=url_at_limit)

    _seed_url_at_tag_limit(
        app=app,
        utub_id=utub.id,
        user_id=USER_ID_FOR_TEST,
        utub_url_id=url_at_limit,
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    # Wait for all seeded badges to render before proceeding (auto-retrying).
    expect_badge_count_on_url_row(
        page=page, utub_url_id=url_at_limit, expected=TAG_CONSTANTS.MAX_URL_TAGS
    )

    enter_multi_select_and_select_urls(
        page=page, url_ids=[url_under_limit, url_at_limit]
    )
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    open_bulk_tag_picker(page=page)
    stage_bulk_new_tag(page=page, text=FRESH_TAG_SINGLE)
    submit_bulk_tags(page=page)

    wait_until_hidden(page=page, css_selector=HPL.BULK_TAG_PICKER_MOUNT)

    # Per-card cues flag each outcome in place (transient — assert before the
    # ~3s fade): the under-limit card shows the applied cue, the at-limit card
    # the skipped cue.
    expect(
        page.locator(
            f'.urlRow[utuburlid="{url_under_limit}"] .bulkCardResultCue--applied'
        )
    ).to_be_visible()
    expect(
        page.locator(f'.urlRow[utuburlid="{url_at_limit}"] .bulkCardResultCue--skipped')
    ).to_be_visible()

    # Concise partial banner — it no longer enumerates the skipped URL by title.
    banner = page.locator(HPL.BULK_TAG_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)partial(\s|$)"))
    expect(banner.locator(".bulkTagBannerBody")).not_to_contain_text(skipped_title)

    # The under-limit URL gained the fresh tag; the at-limit URL gained nothing.
    expect_badge_count_on_url_row(page=page, utub_url_id=url_under_limit, expected=1)
    expect_badge_count_on_url_row(
        page=page, utub_url_id=url_at_limit, expected=TAG_CONSTANTS.MAX_URL_TAGS
    )


def test_bulk_apply_some_skipped_rest_already_tagged_does_not_claim_all_at_limit(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN two selected URLs — one at the per-URL tag limit, the other already
        carrying the tag being applied
    WHEN the user bulk-applies that existing tag to both
    THEN nothing new is applied and the banner names only the skipped at-limit
        URL — it must NOT claim every selected URL is at the limit (regression:
        the all-over-limit failure copy fired here once "modified" excluded the
        already-tagged URL).
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_ids = _get_url_ids_ordered(app=app, utub_id=utub.id)
    assert len(url_ids) >= 2
    url_already_tagged = url_ids[0]
    url_at_limit = url_ids[-1]
    skipped_title = _get_url_title(app=app, utub_url_id=url_at_limit)

    already_present_tag = "AlreadyPresentTag"
    _seed_tag_on_url(
        app=app,
        utub_id=utub.id,
        user_id=USER_ID_FOR_TEST,
        utub_url_id=url_already_tagged,
        tag_string=already_present_tag,
    )
    _seed_url_at_tag_limit(
        app=app,
        utub_id=utub.id,
        user_id=USER_ID_FOR_TEST,
        utub_url_id=url_at_limit,
    )

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    expect_badge_count_on_url_row(
        page=page, utub_url_id=url_at_limit, expected=TAG_CONSTANTS.MAX_URL_TAGS
    )
    expect_badge_count_on_url_row(page=page, utub_url_id=url_already_tagged, expected=1)

    enter_multi_select_and_select_urls(
        page=page, url_ids=[url_already_tagged, url_at_limit]
    )
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    open_bulk_tag_picker(page=page)
    stage_bulk_tag_suggestion(page=page, tag_text=already_present_tag)
    submit_bulk_tags(page=page)

    wait_until_hidden(page=page, css_selector=HPL.BULK_TAG_PICKER_MOUNT)

    # Per-card cues (transient — assert before the ~3s fade): the at-limit card
    # is flagged skipped; the already-tagged card gets NO cue (nothing changed).
    expect(
        page.locator(f'.urlRow[utuburlid="{url_at_limit}"] .bulkCardResultCue--skipped')
    ).to_be_visible()
    expect(
        page.locator(f'.urlRow[utuburlid="{url_already_tagged}"] .bulkCardResultCue')
    ).to_have_count(0)

    # Honest, concise banner: partial styling, no title list, and NEVER the
    # all-over-limit failure phrasing.
    banner = page.locator(HPL.BULK_TAG_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)partial(\s|$)"))
    body = banner.locator(".bulkTagBannerBody")
    expect(body).to_contain_text("No new tags added")
    expect(body).not_to_contain_text(skipped_title)
    expect(body).not_to_contain_text("selected URLs are at")

    # No badge counts change — nothing new was applied to either URL.
    expect_badge_count_on_url_row(page=page, utub_url_id=url_already_tagged, expected=1)
    expect_badge_count_on_url_row(
        page=page, utub_url_id=url_at_limit, expected=TAG_CONSTANTS.MAX_URL_TAGS
    )


def test_bulk_picker_submit_disabled_without_staged_tags(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the bulk tag picker is open with a live selection
    WHEN the user has typed a query but staged no tags
    THEN the submit button is gated disabled (updateSubmitState runs on every
        listbox render), and staging the first chip enables it.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_ids = _get_url_ids_ordered(app=app, utub_id=utub.id)
    assert len(url_ids) >= 2

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=url_ids[:2])
    open_bulk_tag_picker(page=page)

    submit_btn = page.locator(
        f"{HPL.BULK_TAG_PICKER_MOUNT} {HPL.BUTTON_TAGS_SUBMIT_BATCH}"
    )

    # Typing renders the listbox (updateSubmitState) but stages nothing, so submit
    # is gated disabled while no chip is staged.
    type_in_bulk_tag_combobox(page=page, text=FRESH_TAG_SINGLE)
    expect(submit_btn).to_be_disabled()

    # Staging the first chip re-renders and enables submit.
    stage_bulk_new_tag(page=page, text=FRESH_TAG_SINGLE)
    expect(submit_btn).to_be_enabled()


def test_escape_closes_picker_without_exiting_multi_select(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the bulk tag picker is open (listbox closed) with two URLs selected
    WHEN the user presses Escape
    THEN the picker closes but multi-select mode stays active with the selection
        intact (the container Escape owns close, not the document exit handler).
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_ids = _get_url_ids_ordered(app=app, utub_id=utub.id)
    assert len(url_ids) >= 2

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=url_ids[:2])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    open_bulk_tag_picker(page=page)

    # A freshly-opened picker has a hidden listbox, so a single Escape is the
    # second-Escape branch that closes the whole picker.
    page.locator(f"{HPL.BULK_TAG_PICKER_MOUNT} {HPL.INPUT_TAG_COMBOBOX}").first.press(
        "Escape"
    )

    wait_until_hidden(page=page, css_selector=HPL.BULK_TAG_PICKER_MOUNT)

    # Still in multi-select mode with the same selection.
    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_visible()
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(2)


def test_bulk_picker_cancel_discards_and_preserves_selection(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    Cancel button, end-to-end.

    GIVEN the bulk tag picker is open with a staged tag and two URLs selected
    WHEN the user clicks Cancel
    THEN the staged chips are discarded, the picker closes, focus returns to the
        stable in-mode anchor (never the ephemeral action button), the selection
        is preserved, and no tags are applied.
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_ids = _get_url_ids_ordered(app=app, utub_id=utub.id)
    assert len(url_ids) >= 2
    url_a, url_b = url_ids[0], url_ids[1]

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[url_a, url_b])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    open_bulk_tag_picker(page=page)
    stage_bulk_new_tag(page=page, text=FRESH_TAG_SINGLE)
    expect(
        page.locator(f"{HPL.BULK_TAG_PICKER_MOUNT} {HPL.TAG_STAGED_CHIP}")
    ).to_have_count(1)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_BULK_TAG_CANCEL)

    # Picker closed; focus returned to the stable header Exit anchor.
    wait_until_hidden(page=page, css_selector=HPL.BULK_TAG_PICKER_MOUNT)
    wait_until_in_focus(page=page, css_selector=HPL.BULK_SELECT_EXIT)

    # Selection preserved, still in mode, and no tags were applied.
    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_visible()
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(2)
    expect_badge_count_on_url_row(page=page, utub_url_id=url_a, expected=0)
    expect_badge_count_on_url_row(page=page, utub_url_id=url_b, expected=0)


@pytest.mark.mobile_ui
def test_mobile_bulk_tag_apply_ui(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user with two URLs selected in multi-select mode
    WHEN they open the bulk tag picker
    THEN it mounts as a bottom drawer with 44px touch targets; tapping the mobile
        tag-filter icon while it is open is a no-op (the tag sheet does not open,
        the picker stays open); and staging + submitting applies the tag to both
        selected URLs with a success banner.
    """
    page = page_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_ids = _get_url_ids_ordered(app=app, utub_id=utub.id)
    assert len(url_ids) >= 2
    url_a, url_b = url_ids[0], url_ids[1]

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )

    enter_multi_select_and_select_urls(page=page, url_ids=[url_a, url_b])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("2")

    open_bulk_tag_picker(page=page)

    # The picker mounts as a bottom drawer docked to the viewport's bottom edge.
    picker = page.locator(HPL.BULK_TAG_PICKER_MOUNT)
    expect(picker).to_be_visible()
    picker_box = picker.bounding_box()
    viewport = page.viewport_size
    assert picker_box is not None and viewport is not None
    assert picker_box["y"] > viewport["height"] / 2
    assert picker_box["y"] + picker_box["height"] >= viewport["height"] - 5

    # 44px coarse-pointer target on the Cancel button (2.75rem tall).
    cancel_box = page.locator(HPL.BUTTON_BULK_TAG_CANCEL).bounding_box()
    assert cancel_box is not None
    assert cancel_box["height"] >= 43

    # Mobile tag-filter-icon guard: tapping it while the picker is open is a no-op.
    # The click handler flips the icon's aria-expanded + the sheet's open class
    # synchronously when it opens the sheet, so if the guard failed both would be
    # set by the time the click resolves. Assert the inverse of the open state the
    # mobile multi-select suite checks: aria-expanded stays "false", the sheet
    # lacks its open class, and the picker is unaffected.
    tag_filter_icon = page.locator(HPL.BULK_TAG_FILTER_ICON)
    expect(tag_filter_icon).to_be_visible()
    wait_then_click_element(page=page, css_selector=HPL.BULK_TAG_FILTER_ICON)
    expect(tag_filter_icon).to_have_attribute("aria-expanded", "false")
    expect(page.locator(HPL.TAG_SHEET)).not_to_have_class(
        re.compile(rf"(^|\s){re.escape(HPL.TAG_SHEET_OPEN_CLASS)}(\s|$)")
    )
    # The backdrop is `display:block; opacity:0` when closed (never display-hidden),
    # so assert it lacks its dimming `tag-sheet-backdrop-show` class rather than
    # Playwright visibility, which ignores opacity.
    expect(page.locator(HPL.TAG_SHEET_BACKDROP)).not_to_have_class(
        re.compile(r"(^|\s)tag-sheet-backdrop-show(\s|$)")
    )
    expect(picker).to_be_visible()

    # Submit still applies to both selected URLs.
    stage_bulk_new_tag(page=page, text=FRESH_TAG_SINGLE)
    submit_bulk_tags(page=page)

    wait_until_hidden(page=page, css_selector=HPL.BULK_TAG_PICKER_MOUNT)
    expect_badge_count_on_url_row(page=page, utub_url_id=url_a, expected=1)
    expect_badge_count_on_url_row(page=page, utub_url_id=url_b, expected=1)

    banner = page.locator(HPL.BULK_TAG_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_class(re.compile(r"(^|\s)success(\s|$)"))
