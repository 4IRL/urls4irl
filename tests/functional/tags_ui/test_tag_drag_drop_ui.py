"""Playwright UI tests for dragging a Tag Deck chip onto a URL card.

Spike result (recorded per the plan): Playwright's mouse-driven
`Locator.drag_to` makes Chromium over the remote browser server fire genuine
native `dragstart`/`dragover`/`drop` events, so `drag_tag_onto_url` is a real
drag and no `DragEvent` fallback was needed for the happy path. Cases that need
to pause between the phases of a drag (assert the ring during a `dragover`, hold
the POST, cancel with a `dragend`) use the synthetic `dispatch_tag_*` helpers in
`playwright_utils.py`, which fire the same events with a real `DataTransfer`.

Manual check (not automated): native browser auto-scroll of the URL deck while
a chip is dragged near the deck edge. Playwright's intercepted drag session is
driven by synthetic mouse events and does not run the browser's own drag
auto-scroll, so that behavior is covered by a manual check; a drop on a card that
has scrolled into view is covered by `test_drop_on_card_scrolled_into_view`.

"No request" is asserted by counting the `.../tags/batch` POSTs with a
`TagBatchRoute` after a deterministic post-drop signal (no `tagDragging` chip, no
`tagDropTarget`/`tagDropInvalid`/`data-drop-hint` anywhere), never a bare poll
and never `time.sleep`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pytest
from flask import Flask
from playwright.sync_api import Locator, Page, expect

from backend.utils.constants import STRINGS, TAG_CONSTANTS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    count_urls_with_tag_applied_by_tag_string,
    get_other_utub_this_user_is_member_of,
    get_utub_this_user_created,
    set_utub_locked_state,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid_mobile,
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.playwright_utils import (
    open_update_url_title,
    select_utub_by_id,
    wait_for_css_transitions_to_finish,
    wait_then_click_element,
)
from tests.functional.tags_ui.db_utils import (
    apply_tag_to_url_in_db,
    count_tags_on_url,
    create_utub_tag,
    fill_url_to_tag_limit,
    get_url_ids_in_utub_ordered,
    get_url_title,
)
from tests.functional.tags_ui.playwright_utils import (
    TagBatchRoute,
    apply_tag_filter_based_on_id,
    click_open_update_utub_tags_btn,
    dispatch_link_dragstart,
    dispatch_tag_drag_and_drop,
    dispatch_tag_drag_event,
    dispatch_tag_dragend,
    dispatch_tag_dragover_on_url,
    dispatch_tag_dragstart,
    dispatch_tag_drop_on_url,
    drag_tag_onto_url,
    expect_badge_count_on_url_row,
    expect_no_drag_marks_left,
    get_card_height,
    get_computed_style,
    get_url_card_selector,
    get_utub_tag_filter_selector,
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
    open_tag_combobox,
    stage_new_tag,
    submit_staged_tags,
    type_in_tag_combobox,
)
from tests.functional.urls_ui.playwright_utils import enter_multi_select_mode

pytestmark = pytest.mark.tags_ui

USER_ID_FOR_TEST = 1
DRAG_TAG = "DragTag"
SECOND_TAG = "SecondDragTag"
OTHER_TAG = "OtherFilterTag"
ERROR_SHOWN_CLASS = "URLDeckErrorIndicatorShow"
DROP_OPACITY = "0.6"
DRAGGING_OPACITY = "0.45"
NO_RING_SELECTOR = ".tagDropTarget, .tagDropInvalid, [data-drop-hint]"


@dataclass(frozen=True)
class Scene:
    utub_id: int
    url_ids: list[int]
    tag_id: int


def _seed_scene(app: Flask) -> Scene:
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_ids = get_url_ids_in_utub_ordered(app=app, utub_id=utub.id)
    assert len(url_ids) >= 2
    tag_id = create_utub_tag(
        app=app, utub_id=utub.id, user_id=USER_ID_FOR_TEST, tag_string=DRAG_TAG
    )
    return Scene(utub_id=utub.id, url_ids=url_ids, tag_id=tag_id)


def _login(*, app: Flask, page: Page) -> None:
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_name=UTS.TEST_UTUB_NAME_1
    )
    expect(page.locator(HPL.TAG_FILTERS).first).to_be_attached()


def _login_with_url_selected(
    *, app: Flask, page: Page, scene: Scene, url_id: int
) -> None:
    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=USER_ID_FOR_TEST,
        utub_id=scene.utub_id,
        utub_url_id=url_id,
    )
    expect(page.locator(HPL.TAG_FILTERS).first).to_be_attached()


def _hint_add(tag: str) -> str:
    return STRINGS.TAG_DROP_HINT_ADD.replace("{tag}", tag)


def _hint_has(tag: str) -> str:
    return STRINGS.TAG_DROP_HINT_HAS.replace("{tag}", tag)


def _hint_limit() -> str:
    return STRINGS.TAGS_LIMIT_REACHED.replace("{max}", str(TAG_CONSTANTS.MAX_URL_TAGS))


def _added_message(*, tag: str, title: str) -> str:
    return STRINGS.TAG_DROP_ADDED.replace("{tag}", tag).replace("{title}", title)


def _noop_message(*, tag: str, title: str) -> str:
    return STRINGS.TAG_DROP_NOOP.replace("{tag}", tag).replace("{title}", title)


def _card(*, page: Page, url_id: int) -> Locator:
    return page.locator(get_url_card_selector(utub_url_id=url_id))


def _expect_card_selected(*, page: Page, url_id: int, selected: bool = True) -> None:
    card = _card(page=page, url_id=url_id)
    if selected:
        expect(card).to_have_attribute("urlselected", "true")
    else:
        expect(card).not_to_have_attribute("urlselected", "true")


def _expect_error_banner(*, page: Page, message: str) -> None:
    indicator = page.locator(HPL.URL_DECK_ERROR_INDICATOR)
    expect(indicator).to_have_text(message)
    expect(indicator).to_have_class(re.compile(ERROR_SHOWN_CLASS))


def _expect_no_error_banner(page: Page) -> None:
    expect(page.locator(HPL.URL_DECK_ERROR_INDICATOR)).not_to_have_class(
        re.compile(ERROR_SHOWN_CLASS)
    )


def _expect_success_banner(*, page: Page, message: str) -> None:
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(message)


def _expect_no_outcome_banner(*, page: Page) -> None:
    expect(page.locator(HPL.URL_OUTCOME_BANNER)).to_be_hidden()


def _refused_drag_and_drop(
    *, page: Page, utub_tag_id: int, utub_url_id: int, route: TagBatchRoute
) -> None:
    """Drag a chip over and drop it on a card that must refuse: the dragover is
    not accepted, shows no ring or hint, and the drop sends no request."""
    data_transfer = dispatch_tag_dragstart(page=page, utub_tag_id=utub_tag_id)
    card_selector = get_url_card_selector(utub_url_id=utub_url_id)
    for event_type in ("dragenter", "dragover"):
        not_prevented = dispatch_tag_drag_event(
            page=page,
            data_transfer=data_transfer,
            event_type=event_type,
            css_selector=card_selector,
        )
        assert not_prevented, f"{event_type} was accepted on a card that must refuse"
        expect(page.locator(NO_RING_SELECTOR)).to_have_count(0)
    dispatch_tag_drop_on_url(
        page=page, data_transfer=data_transfer, utub_url_id=utub_url_id
    )
    dispatch_tag_dragend(
        page=page, data_transfer=data_transfer, utub_tag_id=utub_tag_id
    )
    expect_no_drag_marks_left(page=page)
    route.expect_nothing_sent()


# --- Happy path ---------------------------------------------------------------


def test_drop_on_unselected_card_adds_tag_selects_card_and_shows_banner(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub with a tag applied to no URL
    WHEN the user natively drags the tag chip onto an unselected URL card
    THEN the card gains the badge and is selected, the success banner names the
        tag and the URL, the deck count increments and the DB row exists.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login(app=app, page=page)
    assert get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=scene.tag_id
    ) == (0, 0)
    _expect_card_selected(page=page, url_id=url_id, selected=False)

    drag_tag_onto_url(page=page, utub_tag_id=scene.tag_id, utub_url_id=url_id)

    expect_badge_count_on_url_row(page=page, utub_url_id=url_id, expected=1)
    _expect_card_selected(page=page, url_id=url_id)
    _expect_success_banner(
        page=page,
        message=_added_message(
            tag=DRAG_TAG, title=get_url_title(app=app, utub_url_id=url_id)
        ),
    )
    expect(
        page.locator(
            f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{scene.tag_id}'] {HPL.TAG_COUNT}"
        )
    ).to_have_text("1 / 1")
    assert (
        count_urls_with_tag_applied_by_tag_string(
            app=app, utub_id=scene.utub_id, tag_text=DRAG_TAG
        )
        == 1
    )
    expect_no_drag_marks_left(page=page)


def test_drop_on_another_card_collapses_the_open_card_and_leaves_one_selected(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN URL card A is selected (expanded) and the tag is on no URL
    WHEN the user natively drags the tag chip onto a different URL card B
    THEN B is selected and A is collapsed: exactly one card has urlSelected=true.
    """
    app = provide_app
    scene = _seed_scene(app)
    open_url_id, dropped_url_id = scene.url_ids[1], scene.url_ids[0]
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=open_url_id)
    _expect_card_selected(page=page, url_id=open_url_id)
    wait_for_css_transitions_to_finish(locator=_card(page=page, url_id=open_url_id))
    expanded_height = get_card_height(page=page, utub_url_id=open_url_id)

    drag_tag_onto_url(page=page, utub_tag_id=scene.tag_id, utub_url_id=dropped_url_id)

    expect_badge_count_on_url_row(page=page, utub_url_id=dropped_url_id, expected=1)
    _expect_card_selected(page=page, url_id=dropped_url_id)
    _expect_card_selected(page=page, url_id=open_url_id, selected=False)
    expect(page.locator(f"{HPL.ROWS_URLS}[urlselected='true']")).to_have_count(1)
    wait_for_css_transitions_to_finish(locator=_card(page=page, url_id=open_url_id))
    assert get_card_height(page=page, utub_url_id=open_url_id) < expanded_height
    expect_no_drag_marks_left(page=page)


def test_drag_does_not_toggle_the_tag_filter(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a tag chip in the Tag Deck
    WHEN the user drags it onto a card
    THEN the drag does not behave as a click on the chip: no filter is applied.
    """
    app = provide_app
    scene = _seed_scene(app)
    _login(app=app, page=page)

    drag_tag_onto_url(page=page, utub_tag_id=scene.tag_id, utub_url_id=scene.url_ids[0])

    expect_badge_count_on_url_row(page=page, utub_url_id=scene.url_ids[0], expected=1)
    expect(page.locator(".tagFilter.selected")).to_have_count(0)
    expect(page.locator(f"{HPL.ROWS_URLS}[filterable='false']")).to_have_count(0)


# --- Cards that must show the invalid state / refuse ---------------------------


def test_drop_on_card_that_already_has_the_tag_is_dimmed_and_sends_no_request(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a URL that already has the dragged tag
    WHEN the chip is dragged over and dropped on it
    THEN during the dragover the card is `tagDropInvalid` with the "already has"
        hint at opacity 0.6, and the drop sends no request and adds no duplicate.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    apply_tag_to_url_in_db(
        app=app,
        utub_id=scene.utub_id,
        user_id=USER_ID_FOR_TEST,
        utub_url_id=url_id,
        utub_tag_id=scene.tag_id,
    )
    _login(app=app, page=page)
    route = TagBatchRoute(page=page)
    expect_badge_count_on_url_row(page=page, utub_url_id=url_id, expected=1)

    data_transfer = dispatch_tag_dragstart(page=page, utub_tag_id=scene.tag_id)
    not_prevented = dispatch_tag_dragover_on_url(
        page=page, data_transfer=data_transfer, utub_url_id=url_id
    )

    assert not_prevented
    card = _card(page=page, url_id=url_id)
    expect(card).to_have_class(re.compile(r"(^|\s)tagDropInvalid(\s|$)"))
    expect(card).to_have_attribute("data-drop-hint", _hint_has(DRAG_TAG))
    expect(card).to_have_css("opacity", DROP_OPACITY)

    dispatch_tag_drop_on_url(page=page, data_transfer=data_transfer, utub_url_id=url_id)
    dispatch_tag_dragend(
        page=page, data_transfer=data_transfer, utub_tag_id=scene.tag_id
    )
    expect_no_drag_marks_left(page=page)
    route.expect_nothing_sent()
    expect_badge_count_on_url_row(page=page, utub_url_id=url_id, expected=1)
    assert (
        count_urls_with_tag_applied_by_tag_string(
            app=app, utub_id=scene.utub_id, tag_text=DRAG_TAG
        )
        == 1
    )
    _expect_no_outcome_banner(page=page)


def test_drop_on_card_at_the_tag_limit_is_dimmed_and_refused(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a URL carrying TAG_CONSTANTS.MAX_URL_TAGS tags
    WHEN the chip is dragged over and dropped on it
    THEN the card is `tagDropInvalid` with the limit hint at opacity 0.6 during
        the dragover, and the drop sends no request.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[1]
    fill_url_to_tag_limit(
        app=app, utub_id=scene.utub_id, user_id=USER_ID_FOR_TEST, utub_url_id=url_id
    )
    _login(app=app, page=page)
    route = TagBatchRoute(page=page)
    expect_badge_count_on_url_row(
        page=page, utub_url_id=url_id, expected=TAG_CONSTANTS.MAX_URL_TAGS
    )

    data_transfer = dispatch_tag_dragstart(page=page, utub_tag_id=scene.tag_id)
    not_prevented = dispatch_tag_dragover_on_url(
        page=page, data_transfer=data_transfer, utub_url_id=url_id
    )

    assert not_prevented
    card = _card(page=page, url_id=url_id)
    expect(card).to_have_class(re.compile(r"(^|\s)tagDropInvalid(\s|$)"))
    expect(card).to_have_attribute("data-drop-hint", _hint_limit())
    expect(card).to_have_css("opacity", DROP_OPACITY)

    dispatch_tag_drop_on_url(page=page, data_transfer=data_transfer, utub_url_id=url_id)
    dispatch_tag_dragend(
        page=page, data_transfer=data_transfer, utub_tag_id=scene.tag_id
    )
    expect_no_drag_marks_left(page=page)
    route.expect_nothing_sent()
    assert count_tags_on_url(app=app, utub_url_id=url_id) == TAG_CONSTANTS.MAX_URL_TAGS


def test_drop_in_locked_utub_shows_no_ring_and_sends_no_request(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub that is already locked when the page loads
    WHEN the chip is dragged over and dropped on a card
    THEN there is no ring or hint, the dragover is not accepted and no POST is
        sent.
    """
    app = provide_app
    scene = _seed_scene(app)
    set_utub_locked_state(app, scene.utub_id, True)
    _login(app=app, page=page)
    route = TagBatchRoute(page=page)

    _refused_drag_and_drop(
        page=page,
        utub_tag_id=scene.tag_id,
        utub_url_id=scene.url_ids[0],
        route=route,
    )

    expect_badge_count_on_url_row(page=page, utub_url_id=scene.url_ids[0], expected=0)
    assert (
        count_urls_with_tag_applied_by_tag_string(
            app=app, utub_id=scene.utub_id, tag_text=DRAG_TAG
        )
        == 0
    )


def test_drop_with_stale_lock_shows_lock_banner_and_does_not_redirect(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a UTub the client believes is unlocked
    WHEN a drop's POST is answered with the locked-UTub 403
    THEN the deck shows the lock message and the page does not leave the home page.
    """
    app = provide_app
    scene = _seed_scene(app)
    _login(app=app, page=page)
    url_before = page.url
    TagBatchRoute(page=page, status=403, body={"message": STRINGS.UTUB_IS_LOCKED})

    dispatch_tag_drag_and_drop(
        page=page, utub_tag_id=scene.tag_id, utub_url_id=scene.url_ids[0]
    )

    _expect_error_banner(page=page, message=STRINGS.UTUB_IS_LOCKED)
    assert page.url == url_before
    expect_badge_count_on_url_row(page=page, utub_url_id=scene.url_ids[0], expected=0)


def test_drop_refused_on_card_with_open_combobox(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a card whose Add Tag combobox is open
    WHEN the chip is dragged over and dropped on that card
    THEN the drop is refused (no ring, no request) and the combobox stays open.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=url_id)
    open_tag_combobox(page=page, url_id=url_id)
    route = TagBatchRoute(page=page)

    _refused_drag_and_drop(
        page=page, utub_tag_id=scene.tag_id, utub_url_id=url_id, route=route
    )

    expect(
        page.locator(
            f"{get_url_card_selector(utub_url_id=url_id)} {HPL.INPUT_TAG_COMBOBOX}"
        )
    ).to_be_visible()


def test_drop_refused_on_card_in_title_edit(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a selected card whose title edit form is open
    WHEN the chip is dragged over and dropped on it
    THEN the drop is refused and the edit form is intact.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=url_id)
    open_update_url_title(
        page=page, selected_url_row=page.locator(HPL.ROW_SELECTED_URL)
    )
    route = TagBatchRoute(page=page)

    _refused_drag_and_drop(
        page=page, utub_tag_id=scene.tag_id, utub_url_id=url_id, route=route
    )

    expect(
        page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}")
    ).to_be_visible()


def test_open_form_on_one_card_makes_every_other_card_refuse(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN an open title edit form on one card
    WHEN the chip is dragged over and dropped on a different card
    THEN that card refuses it (no ring, no request) and the open form is intact.
    """
    app = provide_app
    scene = _seed_scene(app)
    open_url_id, other_url_id = scene.url_ids[0], scene.url_ids[1]
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=open_url_id)
    open_update_url_title(
        page=page, selected_url_row=page.locator(HPL.ROW_SELECTED_URL)
    )
    route = TagBatchRoute(page=page)

    _refused_drag_and_drop(
        page=page, utub_tag_id=scene.tag_id, utub_url_id=other_url_id, route=route
    )

    expect(
        page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}")
    ).to_be_visible()
    _expect_card_selected(page=page, url_id=open_url_id)
    _expect_card_selected(page=page, url_id=other_url_id, selected=False)


def test_drop_refused_in_multi_select_mode(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN multi-select mode
    WHEN a drag of a chip is attempted onto a card
    THEN `dragstart` is cancelled, nothing is highlighted and no request is sent.
    """
    app = provide_app
    scene = _seed_scene(app)
    _login(app=app, page=page)
    enter_multi_select_mode(page=page)
    route = TagBatchRoute(page=page)

    _refused_drag_and_drop(
        page=page,
        utub_tag_id=scene.tag_id,
        utub_url_id=scene.url_ids[0],
        route=route,
    )

    expect_badge_count_on_url_row(page=page, utub_url_id=scene.url_ids[0], expected=0)


def test_drop_refused_on_card_hidden_by_a_filter(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a tag filter that hides a URL card
    WHEN the chip is dragged over and dropped on the hidden card
    THEN the card refuses it: no ring, no request.
    """
    app = provide_app
    scene = _seed_scene(app)
    shown_url_id, hidden_url_id = scene.url_ids[0], scene.url_ids[1]
    other_tag_id = create_utub_tag(
        app=app, utub_id=scene.utub_id, user_id=USER_ID_FOR_TEST, tag_string=OTHER_TAG
    )
    apply_tag_to_url_in_db(
        app=app,
        utub_id=scene.utub_id,
        user_id=USER_ID_FOR_TEST,
        utub_url_id=shown_url_id,
        utub_tag_id=other_tag_id,
    )
    _login(app=app, page=page)
    apply_tag_filter_based_on_id(page=page, utub_tag_id=other_tag_id)
    expect(_card(page=page, url_id=hidden_url_id)).to_have_attribute(
        "filterable", "false"
    )
    route = TagBatchRoute(page=page)

    _refused_drag_and_drop(
        page=page, utub_tag_id=scene.tag_id, utub_url_id=hidden_url_id, route=route
    )

    assert (
        count_urls_with_tag_applied_by_tag_string(
            app=app, utub_id=scene.utub_id, tag_text=DRAG_TAG
        )
        == 0
    )


def test_non_tag_drag_over_a_card_shows_no_ring(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a drag that carries a link (not a tag)
    WHEN it is dragged over a card and dropped
    THEN nothing is highlighted, the dragover is not accepted and no POST is sent.
    """
    app = provide_app
    scene = _seed_scene(app)
    _login(app=app, page=page)
    route = TagBatchRoute(page=page)
    target_url_id = scene.url_ids[1]
    data_transfer = dispatch_link_dragstart(page=page, utub_url_id=scene.url_ids[0])

    for event_type in ("dragenter", "dragover"):
        not_prevented = dispatch_tag_drag_event(
            page=page,
            data_transfer=data_transfer,
            event_type=event_type,
            css_selector=get_url_card_selector(utub_url_id=target_url_id),
        )
        assert not_prevented
        expect(page.locator(NO_RING_SELECTOR)).to_have_count(0)
    dispatch_tag_drop_on_url(
        page=page, data_transfer=data_transfer, utub_url_id=target_url_id
    )

    expect_no_drag_marks_left(page=page)
    route.expect_nothing_sent()


# --- Cancel / stray drop cleanup ------------------------------------------------


def test_cancelled_drag_leaves_no_marks_and_sends_no_request(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a drag in progress over a valid card (ring shown)
    WHEN the drag is cancelled with `dragend` (Escape is not delivered to a native
        or dispatched drag, so the cancel is simulated)
    THEN no `tagDragging`/`tagDropTarget`/`tagDropInvalid`/hint remains and no
        request was sent.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login(app=app, page=page)
    route = TagBatchRoute(page=page)

    data_transfer = dispatch_tag_dragstart(page=page, utub_tag_id=scene.tag_id)
    expect(
        page.locator(get_utub_tag_filter_selector(utub_tag_id=scene.tag_id))
    ).to_have_class(re.compile(r"(^|\s)tagDragging(\s|$)"))
    dispatch_tag_dragover_on_url(
        page=page, data_transfer=data_transfer, utub_url_id=url_id
    )
    card = _card(page=page, url_id=url_id)
    expect(card).to_have_class(re.compile(r"(^|\s)tagDropTarget(\s|$)"))
    expect(card).to_have_attribute("data-drop-hint", _hint_add(DRAG_TAG))

    dispatch_tag_dragend(
        page=page, data_transfer=data_transfer, utub_tag_id=scene.tag_id
    )

    expect_no_drag_marks_left(page=page)
    route.expect_nothing_sent()
    expect_badge_count_on_url_row(page=page, utub_url_id=url_id, expected=0)


def test_drop_outside_any_card_leaves_no_stale_highlight(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a drag that highlighted a card
    WHEN it is dropped outside any card
    THEN the highlight is cleared and no request is sent.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login(app=app, page=page)
    route = TagBatchRoute(page=page)

    data_transfer = dispatch_tag_dragstart(page=page, utub_tag_id=scene.tag_id)
    dispatch_tag_dragover_on_url(
        page=page, data_transfer=data_transfer, utub_url_id=url_id
    )
    expect(_card(page=page, url_id=url_id)).to_have_class(
        re.compile(r"(^|\s)tagDropTarget(\s|$)")
    )

    dispatch_tag_drag_event(
        page=page, data_transfer=data_transfer, event_type="drop", css_selector="body"
    )

    expect_no_drag_marks_left(page=page)
    route.expect_nothing_sent()


# --- Chip draggability ----------------------------------------------------------


def test_chip_is_draggable_while_twenty_filters_are_selected(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN 20 selected tag filters (the unselected chip gets the gray `disabled`
        look and `pointer-events: none` by default)
    WHEN the page is inspected and a drag is started on the unselected chip
    THEN the chip is still `draggable`, shows the grab cursor, has
        `pointer-events: auto`, and a dragstart marks it as dragging.
    """
    app = provide_app
    scene = _seed_scene(app)
    limit_tag_ids = fill_url_to_tag_limit(
        app=app,
        utub_id=scene.utub_id,
        user_id=USER_ID_FOR_TEST,
        utub_url_id=scene.url_ids[0],
    )
    _login(app=app, page=page)
    for limit_tag_id in limit_tag_ids:
        apply_tag_filter_based_on_id(page=page, utub_tag_id=limit_tag_id)
    chip_selector = get_utub_tag_filter_selector(utub_tag_id=scene.tag_id)
    chip = page.locator(chip_selector)
    expect(chip).to_have_class(re.compile(r"(^|\s)disabled(\s|$)"))

    expect(chip).to_have_attribute("draggable", "true")
    style = get_computed_style(
        page=page, css_selector=chip_selector, properties=["cursor", "pointerEvents"]
    )
    assert style["cursor"] == "grab"
    assert style["pointerEvents"] == "auto"

    # The gray disabled look is unchanged when the pointer is over the chip.
    look_properties = ["backgroundColor", "color", "borderTopColor", "borderLeftWidth"]
    look_before = get_computed_style(
        page=page, css_selector=chip_selector, properties=look_properties
    )
    chip.hover()
    wait_for_css_transitions_to_finish(locator=chip)
    assert (
        get_computed_style(
            page=page, css_selector=chip_selector, properties=look_properties
        )
        == look_before
    )

    dispatch_tag_dragstart(page=page, utub_tag_id=scene.tag_id)
    expect(chip).to_have_class(re.compile(r"(^|\s)tagDragging(\s|$)"))


def test_chips_are_not_draggable_in_edit_all_tags_mode(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the Tag Deck in edit-all-tags mode
    WHEN the chips are inspected
    THEN none is draggable, and they become draggable again on leaving the mode.
    """
    app = provide_app
    _seed_scene(app)
    _login(app=app, page=page)
    chips = page.locator(HPL.TAG_FILTERS)
    expect(chips.first).to_have_attribute("draggable", "true")

    click_open_update_utub_tags_btn(page=page)
    expect(page.locator(f"{HPL.TAG_FILTERS}[draggable]")).to_have_count(0)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_CLOSE)
    expect(chips.first).to_have_attribute("draggable", "true")


# --- Outcomes of a real drop ----------------------------------------------------


def test_drop_of_a_tag_the_url_already_has_server_side_shows_noop_banner(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a tag applied to a URL by someone else after this page loaded
    WHEN the user drops that tag on the URL (the client does not know yet)
    THEN the server answers 200 with no applied tags, the card expands and the
        no-op banner names both the tag and the URL title.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login(app=app, page=page)
    apply_tag_to_url_in_db(
        app=app,
        utub_id=scene.utub_id,
        user_id=USER_ID_FOR_TEST,
        utub_url_id=url_id,
        utub_tag_id=scene.tag_id,
    )

    dispatch_tag_drag_and_drop(page=page, utub_tag_id=scene.tag_id, utub_url_id=url_id)

    _expect_card_selected(page=page, url_id=url_id)
    _expect_success_banner(
        page=page,
        message=_noop_message(
            tag=DRAG_TAG, title=get_url_title(app=app, utub_url_id=url_id)
        ),
    )
    assert count_tags_on_url(app=app, utub_url_id=url_id) == 1


@pytest.mark.parametrize(
    ("status", "body", "expected_message"),
    [
        pytest.param(
            400,
            {"message": "Too many tags on this URL"},
            "Too many tags on this URL",
            id="message-only-400",
        ),
        pytest.param(
            400,
            {"errors": {"tagStrings": ["Tag field error text"]}},
            "Tag field error text",
            id="field-error-400",
        ),
        pytest.param(400, {}, STRINGS.TAG_DROP_FAILED, id="400-without-message"),
        pytest.param(500, "", STRINGS.TAG_DROP_FAILED, id="500"),
    ],
)
def test_failed_drop_shows_deck_banner_and_never_redirects(
    page: Page,
    create_test_urls,
    provide_app: Flask,
    status: int,
    body: dict | str,
    expected_message: str,
):
    """
    GIVEN a drop whose POST fails
    WHEN the response arrives
    THEN a deck banner shows the message (or the generic failure text), the page
        does not leave the home page and no tag is added.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login(app=app, page=page)
    url_before = page.url
    TagBatchRoute(page=page, status=status, body=body)

    dispatch_tag_drag_and_drop(page=page, utub_tag_id=scene.tag_id, utub_url_id=url_id)

    _expect_error_banner(page=page, message=expected_message)
    assert page.url == url_before
    expect_badge_count_on_url_row(page=page, utub_url_id=url_id, expected=0)


def test_drop_answered_with_404_shows_deleted_banner_and_removes_the_card(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a drop whose POST is answered with a JSON 404
    WHEN the response arrives
    THEN the "Another user has deleted this URL" banner shows and the card is gone.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login(app=app, page=page)
    TagBatchRoute(page=page, status=404, body={"message": "URL not found"})

    dispatch_tag_drag_and_drop(page=page, utub_tag_id=scene.tag_id, utub_url_id=url_id)

    _expect_error_banner(page=page, message=STRINGS.URL_DELETED_BY_OTHER_USER)
    expect(_card(page=page, url_id=url_id)).to_have_count(0)


def test_failed_drop_after_a_successful_drop_shows_only_the_error_banner(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a successful drop whose success banner is showing
    WHEN a second drop on the same card fails
    THEN only the error banner shows; the earlier success banner is gone.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    second_tag_id = create_utub_tag(
        app=app, utub_id=scene.utub_id, user_id=USER_ID_FOR_TEST, tag_string=SECOND_TAG
    )
    added_message = _added_message(
        tag=DRAG_TAG, title=get_url_title(app=app, utub_url_id=url_id)
    )
    _login(app=app, page=page)
    # The first POST passes through, every later one fails; set up before the
    # first drop so the second drop follows the success banner immediately.
    TagBatchRoute(page=page, status=500, body="", pass_through_first=1)
    dispatch_tag_drag_and_drop(page=page, utub_tag_id=scene.tag_id, utub_url_id=url_id)
    _expect_success_banner(page=page, message=added_message)

    dispatch_tag_drag_and_drop(page=page, utub_tag_id=second_tag_id, utub_url_id=url_id)

    _expect_error_banner(page=page, message=STRINGS.TAG_DROP_FAILED)
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_count(0)
    _expect_no_outcome_banner(page=page)


def test_failed_drop_on_a_selected_card_still_lets_a_click_deselect_it(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a selected card
    WHEN a drop on it is rejected by the server
    THEN the message shows, the card stays selected, and a later click on the
        card still deselects it (click-to-hide is handed back).
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=url_id)
    TagBatchRoute(page=page, status=400, body={"message": "Tag limit race"})

    dispatch_tag_drag_and_drop(page=page, utub_tag_id=scene.tag_id, utub_url_id=url_id)

    _expect_error_banner(page=page, message="Tag limit race")
    _expect_card_selected(page=page, url_id=url_id)
    _card(page=page, url_id=url_id).click(position={"x": 4, "y": 4})
    _expect_card_selected(page=page, url_id=url_id, selected=False)


# --- Concurrency and source-keyed handling ---------------------------------------


def test_second_drop_while_first_is_pending_is_rejected(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a drop whose POST is held
    WHEN a second drop is made on a different card
    THEN exactly one POST was sent and the second card gets no ring or selection;
        after the first completes only the first card is selected with the banner.
    """
    app = provide_app
    scene = _seed_scene(app)
    first_url_id, second_url_id = scene.url_ids[0], scene.url_ids[1]
    _login(app=app, page=page)
    route = TagBatchRoute(page=page, hold=True)

    dispatch_tag_drag_and_drop(
        page=page, utub_tag_id=scene.tag_id, utub_url_id=first_url_id
    )
    route.wait_until_held(count=1)
    data_transfer = dispatch_tag_dragstart(page=page, utub_tag_id=scene.tag_id)
    dispatch_tag_dragover_on_url(
        page=page, data_transfer=data_transfer, utub_url_id=second_url_id
    )
    expect(page.locator(NO_RING_SELECTOR)).to_have_count(0)
    dispatch_tag_drop_on_url(
        page=page, data_transfer=data_transfer, utub_url_id=second_url_id
    )
    expect_no_drag_marks_left(page=page)

    route.expect_post_count(1)
    _expect_card_selected(page=page, url_id=second_url_id, selected=False)
    route.release_and_wait()

    _expect_card_selected(page=page, url_id=first_url_id)
    _expect_card_selected(page=page, url_id=second_url_id, selected=False)
    _expect_success_banner(
        page=page,
        message=_added_message(
            tag=DRAG_TAG, title=get_url_title(app=app, utub_url_id=first_url_id)
        ),
    )
    expect_badge_count_on_url_row(page=page, utub_url_id=first_url_id, expected=1)
    expect_badge_count_on_url_row(page=page, utub_url_id=second_url_id, expected=0)
    route.expect_post_count(1)
    assert (
        count_urls_with_tag_applied_by_tag_string(
            app=app, utub_id=scene.utub_id, tag_text=DRAG_TAG
        )
        == 1
    )


def _drop_hold_and_open_combobox(
    *, page: Page, scene: Scene, url_id: int, route: TagBatchRoute
) -> None:
    dispatch_tag_drag_and_drop(page=page, utub_tag_id=scene.tag_id, utub_url_id=url_id)
    route.wait_until_held(count=1)
    open_tag_combobox(page=page, url_id=url_id)
    type_in_tag_combobox(page=page, text="StagedText")


def test_message_400_after_combobox_opened_mid_drop_uses_banner_not_combobox(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a drop on a selected card whose POST is held, and the user then opens
        the Add Tag combobox on that card
    WHEN a message-only 400 is released
    THEN the deck banner shows, `.urlTagComboboxMsg` stays empty and the
        combobox stays open.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=url_id)
    route = TagBatchRoute(page=page, hold=True)
    _drop_hold_and_open_combobox(page=page, scene=scene, url_id=url_id, route=route)

    route.release(status=400, body={"message": "Held message-only 400"})

    _expect_error_banner(page=page, message="Held message-only 400")
    card_selector = get_url_card_selector(utub_url_id=url_id)
    expect(page.locator(f"{card_selector} {HPL.TAG_COMBOBOX_MSG}")).to_have_text("")
    expect(page.locator(f"{card_selector} {HPL.INPUT_TAG_COMBOBOX}")).to_be_visible()


def test_success_after_combobox_opened_mid_drop_does_not_reset_the_combobox(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a drop on a selected card whose POST is held, and the user then opens
        the Add Tag combobox on that card and types into it
    WHEN the real 200 is released
    THEN the tag is applied but the combobox is not reset: still open, with the
        staged input intact.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=url_id)
    route = TagBatchRoute(page=page, hold=True)
    _drop_hold_and_open_combobox(page=page, scene=scene, url_id=url_id, route=route)

    route.release_and_wait()

    expect_badge_count_on_url_row(page=page, utub_url_id=url_id, expected=1)
    combobox_input = page.locator(
        f"{get_url_card_selector(utub_url_id=url_id)} {HPL.INPUT_TAG_COMBOBOX}"
    )
    expect(combobox_input).to_be_visible()
    expect(combobox_input).to_have_value("StagedText")


@pytest.mark.parametrize(
    ("status", "body"),
    [
        pytest.param(None, None, id="200"),
        pytest.param(500, "", id="500"),
    ],
)
def test_utub_switch_while_drop_pending_shows_no_banner_or_selection(
    page: Page,
    create_test_urls,
    provide_app: Flask,
    status: int | None,
    body: dict | str | None,
):
    """
    GIVEN a drop whose POST is held and the user then switches to another UTub
    WHEN the response (200 or 500) is released
    THEN the new UTub's deck shows no banner and has no selected card.
    """
    app = provide_app
    scene = _seed_scene(app)
    other_utub = get_other_utub_this_user_is_member_of(
        app, USER_ID_FOR_TEST, scene.utub_id
    )
    _login(app=app, page=page)
    route = TagBatchRoute(page=page, hold=True)
    dispatch_tag_drag_and_drop(
        page=page, utub_tag_id=scene.tag_id, utub_url_id=scene.url_ids[0]
    )
    route.wait_until_held(count=1)
    select_utub_by_id(page=page, utub_id=other_utub.id)

    route.release_and_wait(status=status, body=body)

    _expect_no_outcome_banner(page=page)
    _expect_no_error_banner(page)
    expect(page.locator(HPL.ROW_SELECTED_URL)).to_have_count(0)
    # The held request did complete as intended (200 applied it, 500 did not).
    assert count_urls_with_tag_applied_by_tag_string(
        app=app, utub_id=scene.utub_id, tag_text=DRAG_TAG
    ) == (1 if status is None else 0)


def test_outcome_does_not_select_dropped_card_when_another_combobox_is_open(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a drop on card A whose POST is held, and the user opens card B's combobox
    WHEN the response is released
    THEN the banner shows but card A is not selected and B's combobox stays open.
    """
    app = provide_app
    scene = _seed_scene(app)
    dropped_url_id, other_url_id = scene.url_ids[0], scene.url_ids[1]
    _login(app=app, page=page)
    route = TagBatchRoute(page=page, hold=True)
    dispatch_tag_drag_and_drop(
        page=page, utub_tag_id=scene.tag_id, utub_url_id=dropped_url_id
    )
    route.wait_until_held(count=1)
    _card(page=page, url_id=other_url_id).click(position={"x": 4, "y": 4})
    _expect_card_selected(page=page, url_id=other_url_id)
    open_tag_combobox(page=page, url_id=other_url_id)

    route.release_and_wait()

    _expect_success_banner(
        page=page,
        message=_added_message(
            tag=DRAG_TAG, title=get_url_title(app=app, utub_url_id=dropped_url_id)
        ),
    )
    _expect_card_selected(page=page, url_id=dropped_url_id, selected=False)
    expect(
        page.locator(
            f"{get_url_card_selector(utub_url_id=other_url_id)} {HPL.INPUT_TAG_COMBOBOX}"
        )
    ).to_be_visible()
    expect_badge_count_on_url_row(page=page, utub_url_id=dropped_url_id, expected=1)


def test_drop_on_card_scrolled_into_view(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a short viewport so the URL deck scrolls
    WHEN a card below the fold is scrolled into view and the chip dropped on it
    THEN the tag is added. (Native edge auto-scroll while dragging is a manual
        check; see the module docstring.)
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[-1]
    page.set_viewport_size({"width": 1400, "height": 500})
    _login(app=app, page=page)
    _card(page=page, url_id=url_id).scroll_into_view_if_needed()

    drag_tag_onto_url(page=page, utub_tag_id=scene.tag_id, utub_url_id=url_id)

    expect_badge_count_on_url_row(page=page, utub_url_id=url_id, expected=1)
    assert (
        count_urls_with_tag_applied_by_tag_string(
            app=app, utub_id=scene.utub_id, tag_text=DRAG_TAG
        )
        == 1
    )


# --- Combobox-open regression ------------------------------------------------------


def test_combobox_message_400_still_shows_inside_the_combobox(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the Add Tag combobox open on a card
    WHEN a staged tag's submit gets a message-only 400
    THEN the message shows in `.urlTagComboboxMsg` and not in the deck banner.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=url_id)
    open_tag_combobox(page=page, url_id=url_id)
    stage_new_tag(page=page, text="ComboboxRegression")
    TagBatchRoute(page=page, status=400, body={"message": "Combobox 400 message"})

    submit_staged_tags(page=page)

    expect(page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.TAG_COMBOBOX_MSG}")).to_have_text(
        "Combobox 400 message"
    )
    _expect_no_error_banner(page)


def test_combobox_locked_403_shows_lock_banner_and_does_not_redirect(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the Add Tag combobox open on a card
    WHEN a staged tag's submit gets the locked-UTub 403
    THEN the lock banner shows and the page does not redirect to the error page.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=url_id)
    url_before = page.url
    open_tag_combobox(page=page, url_id=url_id)
    stage_new_tag(page=page, text="ComboboxLocked")
    TagBatchRoute(page=page, status=403, body={"message": STRINGS.UTUB_IS_LOCKED})

    submit_staged_tags(page=page)

    _expect_error_banner(page=page, message=STRINGS.UTUB_IS_LOCKED)
    assert page.url == url_before


# --- Computed styles -------------------------------------------------------------


def test_drag_styles_cursor_opacity_tint_hint_and_height(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the desktop viewport and an unselected draggable chip
    THEN the chip shows `grab` (also hovered) and, during a dragstart, `grabbing`
        at reduced opacity; the drop tint is identical on an odd and an even row;
        the hint `::after` carries the hint text, is absolutely positioned and does
        not change the card's row height.
    """
    app = provide_app
    scene = _seed_scene(app)
    _login(app=app, page=page)
    chip_selector = get_utub_tag_filter_selector(utub_tag_id=scene.tag_id)
    chip = page.locator(chip_selector)
    expect(chip).to_have_attribute("draggable", "true")

    assert (
        get_computed_style(
            page=page, css_selector=chip_selector, properties=["cursor"]
        )["cursor"]
        == "grab"
    )
    chip.hover()
    assert (
        get_computed_style(
            page=page, css_selector=chip_selector, properties=["cursor"]
        )["cursor"]
        == "grab"
    )

    data_transfer = dispatch_tag_dragstart(page=page, utub_tag_id=scene.tag_id)
    expect(chip).to_have_class(re.compile(r"(^|\s)tagDragging(\s|$)"))
    expect(chip).to_have_css("cursor", "grabbing")
    expect(chip).to_have_css("opacity", DRAGGING_OPACITY)

    even_url_id = int(
        page.locator(f"{HPL.ROWS_URLS}.even").first.get_attribute("utuburlid")
    )
    odd_url_id = int(
        page.locator(f"{HPL.ROWS_URLS}:not(.even)").first.get_attribute("utuburlid")
    )
    idle_height = get_card_height(page=page, utub_url_id=odd_url_id)

    idle_backgrounds = [
        get_computed_style(
            page=page,
            css_selector=get_url_card_selector(utub_url_id=url_id),
            properties=["backgroundColor"],
        )["backgroundColor"]
        for url_id in (even_url_id, odd_url_id)
    ]
    tints: list[str] = []
    for url_id in (even_url_id, odd_url_id):
        dispatch_tag_dragover_on_url(
            page=page, data_transfer=data_transfer, utub_url_id=url_id
        )
        card_selector = get_url_card_selector(utub_url_id=url_id)
        expect(page.locator(card_selector)).to_have_class(
            re.compile(r"(^|\s)tagDropTarget(\s|$)")
        )
        # The card animates its background (0.15s); read the settled tint.
        wait_for_css_transitions_to_finish(locator=page.locator(card_selector))
        tints.append(
            get_computed_style(
                page=page, css_selector=card_selector, properties=["backgroundColor"]
            )["backgroundColor"]
        )
    assert tints[0] == tints[1]
    assert tints[0] not in idle_backgrounds

    hint_style = get_computed_style(
        page=page,
        css_selector=get_url_card_selector(utub_url_id=odd_url_id),
        properties=["content", "position"],
        pseudo="::after",
    )
    rendered_content = hint_style["content"][1:-1].replace('\\"', '"')
    assert rendered_content == _hint_add(DRAG_TAG)
    assert hint_style["position"] == "absolute"
    assert get_card_height(page=page, utub_url_id=odd_url_id) == idle_height


# --- Ghost pill on a selected (expanded) card -------------------------------------

GHOST_SELECTOR = ".tagDropGhost"


def _after_content(*, page: Page, url_id: int) -> str:
    return get_computed_style(
        page=page,
        css_selector=get_url_card_selector(utub_url_id=url_id),
        properties=["content"],
        pseudo="::after",
    )["content"]


def test_selected_card_shows_one_distinct_ghost_pill_and_no_corner_text(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a selected card that already has a real tag
    WHEN a tag is dragged over it (repeated dragovers)
    THEN exactly one aria-hidden ghost pill labelled with the tag sits after the
        real pill, styled dashed unlike the real pill, the corner `::after` text is
        gone while `data-drop-hint` remains, no tag is added, and a dragend removes
        the ghost.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    other_tag_id = create_utub_tag(
        app=app, utub_id=scene.utub_id, user_id=USER_ID_FOR_TEST, tag_string=SECOND_TAG
    )
    apply_tag_to_url_in_db(
        app=app,
        utub_id=scene.utub_id,
        user_id=USER_ID_FOR_TEST,
        utub_url_id=url_id,
        utub_tag_id=other_tag_id,
    )
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=url_id)
    expect_badge_count_on_url_row(page=page, utub_url_id=url_id, expected=1)
    card = _card(page=page, url_id=url_id)
    tag_ids_before = card.get_attribute("data-utub-url-tag-ids")

    data_transfer = dispatch_tag_dragstart(page=page, utub_tag_id=scene.tag_id)
    for _ in range(2):
        # False means a listener called preventDefault, i.e. the drop is accepted.
        not_prevented = dispatch_tag_dragover_on_url(
            page=page, data_transfer=data_transfer, utub_url_id=url_id
        )
        assert not not_prevented

    ghost = card.locator(GHOST_SELECTOR)
    expect(ghost).to_have_count(1)
    expect(ghost).to_have_text(DRAG_TAG)
    expect(ghost).to_have_attribute("aria-hidden", "true")
    expect(ghost).to_have_css("border-top-style", "dashed")
    expect(ghost).to_have_css("pointer-events", "none")
    real_pill = card.locator(HPL.TAG_BADGES)
    expect(real_pill).to_have_count(1)
    expect(real_pill).to_have_css("border-top-style", "solid")
    expect(card.locator(f"{HPL.TAG_BADGES} ~ {GHOST_SELECTOR}")).to_have_count(1)
    expect(card).to_have_attribute("data-drop-hint", _hint_add(DRAG_TAG))
    assert _after_content(page=page, url_id=url_id) == "none"
    assert card.get_attribute("data-utub-url-tag-ids") == tag_ids_before

    dispatch_tag_dragend(
        page=page, data_transfer=data_transfer, utub_tag_id=scene.tag_id
    )
    expect_no_drag_marks_left(page=page)
    expect_badge_count_on_url_row(page=page, utub_url_id=url_id, expected=1)


def test_dragenter_on_next_card_before_dragleave_on_old_keeps_new_marks(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a tag dragged over card A, with card B selected (so it shows a ghost)
    WHEN the browser fires `dragenter` on B BEFORE `dragleave` on A
        (relatedTarget B), as real drags do
    THEN B keeps its ring, hint and ghost and A has none; a later leave to
        outside every card clears everything.
    """
    app = provide_app
    scene = _seed_scene(app)
    card_a_id, card_b_id = scene.url_ids[0], scene.url_ids[1]
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=card_b_id)
    card_a, card_b = (
        _card(page=page, url_id=card_a_id),
        _card(page=page, url_id=card_b_id),
    )
    selector_a = get_url_card_selector(utub_url_id=card_a_id)
    selector_b = get_url_card_selector(utub_url_id=card_b_id)
    ring = re.compile(r"(^|\s)tagDropTarget(\s|$)")

    data_transfer = dispatch_tag_dragstart(page=page, utub_tag_id=scene.tag_id)
    dispatch_tag_drag_event(
        page=page,
        data_transfer=data_transfer,
        event_type="dragenter",
        css_selector=selector_a,
    )
    expect(card_a).to_have_class(ring)

    dispatch_tag_drag_event(
        page=page,
        data_transfer=data_transfer,
        event_type="dragenter",
        css_selector=selector_b,
    )
    dispatch_tag_drag_event(
        page=page,
        data_transfer=data_transfer,
        event_type="dragleave",
        css_selector=selector_a,
        related_css_selector=selector_b,
    )

    expect(card_b).to_have_class(ring)
    expect(card_b).to_have_attribute("data-drop-hint", _hint_add(DRAG_TAG))
    expect(card_b.locator(GHOST_SELECTOR)).to_have_count(1)
    expect(card_a).not_to_have_class(ring)
    expect(card_a).not_to_have_attribute("data-drop-hint", _hint_add(DRAG_TAG))
    expect(card_a.locator(GHOST_SELECTOR)).to_have_count(0)

    dispatch_tag_drag_event(
        page=page,
        data_transfer=data_transfer,
        event_type="dragleave",
        css_selector=selector_b,
    )
    expect(card_b).not_to_have_class(ring)
    expect(card_b).not_to_have_attribute("data-drop-hint", _hint_add(DRAG_TAG))
    expect(card_b.locator(GHOST_SELECTOR)).to_have_count(0)

    dispatch_tag_dragend(
        page=page, data_transfer=data_transfer, utub_tag_id=scene.tag_id
    )
    expect_no_drag_marks_left(page=page)


def test_ghost_pill_on_card_without_tags_does_not_make_the_card_flicker(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a selected card with no tags
    WHEN a tag is dragged over it twice
    THEN one ghost pill is shown and the card height is identical between the two
        dragovers (the pointer cannot flip in and out of the card).
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=url_id)
    card = _card(page=page, url_id=url_id)
    wait_for_css_transitions_to_finish(locator=card)

    data_transfer = dispatch_tag_dragstart(page=page, utub_tag_id=scene.tag_id)
    dispatch_tag_dragover_on_url(
        page=page, data_transfer=data_transfer, utub_url_id=url_id
    )
    expect(card.locator(GHOST_SELECTOR)).to_have_count(1)
    wait_for_css_transitions_to_finish(locator=card)
    height_first = get_card_height(page=page, utub_url_id=url_id)

    dispatch_tag_dragover_on_url(
        page=page, data_transfer=data_transfer, utub_url_id=url_id
    )
    wait_for_css_transitions_to_finish(locator=card)
    assert get_card_height(page=page, utub_url_id=url_id) == height_first
    expect(card.locator(GHOST_SELECTOR)).to_have_count(1)

    dispatch_tag_dragend(
        page=page, data_transfer=data_transfer, utub_tag_id=scene.tag_id
    )
    expect_no_drag_marks_left(page=page)


def test_selected_card_with_the_tag_emphasizes_the_existing_pill(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a selected card that already has the dragged tag
    WHEN the tag is dragged over it
    THEN no ghost is added, the existing pill is emphasized, the corner text is
        suppressed and everything is cleared by the dragend.
    """
    app = provide_app
    scene = _seed_scene(app)
    url_id = scene.url_ids[0]
    apply_tag_to_url_in_db(
        app=app,
        utub_id=scene.utub_id,
        user_id=USER_ID_FOR_TEST,
        utub_url_id=url_id,
        utub_tag_id=scene.tag_id,
    )
    _login_with_url_selected(app=app, page=page, scene=scene, url_id=url_id)
    card = _card(page=page, url_id=url_id)

    data_transfer = dispatch_tag_dragstart(page=page, utub_tag_id=scene.tag_id)
    dispatch_tag_dragover_on_url(
        page=page, data_transfer=data_transfer, utub_url_id=url_id
    )

    expect(card.locator(GHOST_SELECTOR)).to_have_count(0)
    expect(card.locator(f"{HPL.TAG_BADGES}.tagDropExisting")).to_have_count(1)
    expect(card).to_have_attribute("data-drop-hint", _hint_has(DRAG_TAG))
    assert _after_content(page=page, url_id=url_id) == "none"

    dispatch_tag_dragend(
        page=page, data_transfer=data_transfer, utub_tag_id=scene.tag_id
    )
    expect_no_drag_marks_left(page=page)
    expect_badge_count_on_url_row(page=page, utub_url_id=url_id, expected=1)


# --- Mobile and the width boundary ------------------------------------------------


def test_mobile_portrait_has_no_draggable_chips(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a touch phone-sized viewport
    WHEN a UTub with tags is open
    THEN no tag chip is draggable.
    """
    app = provide_app
    scene = _seed_scene(app)
    login_user_and_select_utub_by_utubid_mobile(
        app=app,
        page=page_mobile_portrait,
        user_id=USER_ID_FOR_TEST,
        utub_id=scene.utub_id,
    )

    expect(page_mobile_portrait.locator(HPL.TAG_FILTERS).first).to_be_attached()
    expect(page_mobile_portrait.locator(f"{HPL.TAG_FILTERS}[draggable]")).to_have_count(
        0
    )


def test_draggable_flips_with_viewport_width_without_reload(
    page: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the desktop viewport
    WHEN it is resized clearly below and then above the 992px boundary
    THEN chips lose and regain `draggable` without a reload. (900 vs 1100, not
        991 vs 992: the CSS media query and the jQuery `isMobile()` switch measure
        the width differently by the scrollbar width.)
    """
    app = provide_app
    _seed_scene(app)
    _login(app=app, page=page)
    chips = page.locator(HPL.TAG_FILTERS)
    chip_count = chips.count()
    assert chip_count >= 1
    expect(page.locator(f"{HPL.TAG_FILTERS}[draggable='true']")).to_have_count(
        chip_count
    )

    page.set_viewport_size({"width": 900, "height": 1080})
    expect(page.locator(f"{HPL.TAG_FILTERS}[draggable]")).to_have_count(0)

    page.set_viewport_size({"width": 1100, "height": 1080})
    expect(page.locator(f"{HPL.TAG_FILTERS}[draggable='true']")).to_have_count(
        chip_count
    )
