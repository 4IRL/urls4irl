"""Collapsed-state tag-filter indicator (#TagDeckFilterPill).

A collapsed Tag deck hides the tag chips and #unselectAllTagFilters, which are
what otherwise say "a filter is applied". Persisting the deck layout makes
"collapsed" an everyday state rather than a rare one, so the pill replaces
exactly that signal in the always-visible header band — and only there.
"""

from __future__ import annotations

import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.utils.strings.tag_strs import (
    TAG_FILTER_ANNOUNCEMENT_COUNT_ONE,
    TAG_FILTER_PILL_COUNT,
)
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_utubid
from tests.functional.playwright_utils import wait_then_click_element
from tests.functional.tags_ui.playwright_utils import apply_tag_filter_based_on_id

pytestmark = pytest.mark.tags_ui

_COLLAPSED_CLASS_RE = re.compile(r"(^|\s)collapsed(\s|$)")


def test_tag_filter_pill_shows_the_filter_count_only_while_the_deck_is_collapsed(
    page: Page,
    create_test_urls,
    provide_app: Flask,
):
    """
    GIVEN a UTub with one tag filter applied
    WHEN the user collapses the Tag deck, and then expands it again
    THEN the filter pill appears in the collapsed header band carrying the
         applied-filter count, and disappears again on expand

    [DD-13] The pill is a non-interactive indicator (Design Decision 4), so it
    is asserted purely on visibility and text. `playwright_utils.collapse_deck`
    is deliberately NOT used: its animation-settling wait assumes the animated
    user path, while the programmatic restore uses `.deck-snap`
    (`transition: none`) and lands instantly.

    Collapsing is a real header click rather than a seeded class, because the
    aria-live write below only happens in the collapse handler — the click
    emits no TAG_FILTER_CHANGED, so nothing else would fill it in.
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )
    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    # Before any filter is applied the pill is unmarked AND unlabeled, so a
    # stale count can never flash on a later re-show.
    expect(page.locator(HPL.TAG_DECK_FILTER_PILL)).to_be_hidden()

    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_in_utub.id)

    # Expanded, the chips themselves carry the filter state, so the pill stays
    # hidden even though a filter is now applied.
    expect(page.locator(HPL.TAG_DECK_FILTER_PILL)).to_be_hidden()

    wait_then_click_element(page=page, css_selector=HPL.HEADER_AND_CARET_TAG_DECK)
    expect(page.locator(HPL.TAG_DECK)).to_have_class(_COLLAPSED_CLASS_RE)

    expect(page.locator(HPL.TAG_DECK_FILTER_PILL)).to_be_visible()
    expect(page.locator(HPL.TAG_DECK_FILTER_PILL)).to_have_text(
        TAG_FILTER_PILL_COUNT.replace("{n}", "1")
    )

    # The spoken form is its own string ("1 tag filtered", not "1 filtered"),
    # written at the moment of collapse — the collapse click emits no
    # TAG_FILTER_CHANGED, so without that write a user who collapses an
    # already-filtered deck would hear nothing about the filters it just hid.
    announcement = page.locator(HPL.TAG_DECK_COLLAPSED_FILTER_ANNOUNCEMENT)
    expect(announcement).to_have_text(TAG_FILTER_ANNOUNCEMENT_COUNT_ONE)

    # The announcement region has to sit in the always-visible header band, not
    # inside `.content` — `.deck.collapsed .content { visibility: hidden }`
    # would prune it from the a11y tree in exactly the state it exists for.
    expect(
        page.locator(
            f"{HPL.TAG_DECK} .content {HPL.TAG_DECK_COLLAPSED_FILTER_ANNOUNCEMENT}"
        )
    ).to_have_count(0)
    expect(announcement).not_to_have_css("visibility", "hidden")

    wait_then_click_element(page=page, css_selector=HPL.HEADER_AND_CARET_TAG_DECK)
    expect(page.locator(HPL.TAG_DECK)).not_to_have_class(_COLLAPSED_CLASS_RE)

    expect(page.locator(HPL.TAG_DECK_FILTER_PILL)).to_be_hidden()
