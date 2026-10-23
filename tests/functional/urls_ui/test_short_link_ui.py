import re
from typing import NamedTuple

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.models.short_links import SHORT_LINK_CODE_LENGTH
from backend.utils.constants import STRINGS
from backend.utils.strings.url_strs import URL_REVIVED_FROM_TRASH
from tests.functional.db_utils import (
    add_url_to_utub_as_other_member,
    get_plain_members_excluding,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ShortLinkPageLocators as SLPL
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.playwright_utils import (
    current_base_url,
    open_update_url_title,
    wait_then_click_element,
)
from tests.functional.tags_ui.playwright_utils import open_tag_combobox
from tests.functional.urls_ui.db_utils import (
    get_short_link_code,
    mint_short_link_in_db,
)
from tests.functional.urls_ui.playwright_login_utils import (
    click_delete_on_selected_url_and_wait_for_toast,
)
from tests.functional.urls_ui.playwright_utils import ClipboardMockHelper

pytestmark = pytest.mark.urls_ui

SHORT_LINK_URL_STRING = "https://short-link.example.com/path"
SHORT_LINK_URL_TITLE = "Short link URL"

SELECTED_SHORT_LINK_BTN = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_SHORT_LINK}"
SELECTED_STATUS = f"{HPL.ROW_SELECTED_URL} {HPL.SHORT_LINK_STATUS}"
SELECTED_STATUS_ROW = f"{HPL.ROW_SELECTED_URL} {HPL.SHORT_LINK_STATUS_ROW}"
SELECTED_REVOKE_BTN = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_SHORT_LINK_REVOKE}"

# `<origin>/s/<code>`; the origin is whatever host the server builds URLs for.
SHORT_URL_PATTERN = re.compile(
    rf"^https?://[^/]+/s/[A-Za-z0-9]{{{SHORT_LINK_CODE_LENGTH}}}$"
)
COPIED_MESSAGE_PREFIX = STRINGS.SHORT_LINK_COPIED.split("{date}")[0]
EXPIRES_MESSAGE_PREFIX = STRINGS.SHORT_LINK_EXPIRES.split("{date}")[0]

TAB_PRESS_LIMIT = 20


class ShortLinkScenario(NamedTuple):
    utub_id: int
    utub_url_id: int
    creator_id: int
    # Two plain members: neither created the UTub nor added the URL.
    member_id: int
    other_member_id: int


def _seed_scenario(*, app: Flask) -> ShortLinkScenario:
    """A UTub user 1 created, holding one URL user 1 added. Requires
    ``create_test_utubmembers`` so every other user is a plain member."""
    utub = get_utub_this_user_created(app, 1)
    plain_members = get_plain_members_excluding(app, utub.id, [utub.utub_creator])
    assert len(plain_members) >= 2, "Test premise violated: need two plain members"
    utub_url_id = add_url_to_utub_as_other_member(
        app,
        utub.id,
        utub.utub_creator,
        SHORT_LINK_URL_STRING,
        SHORT_LINK_URL_TITLE,
    )
    return ShortLinkScenario(
        utub_id=utub.id,
        utub_url_id=utub_url_id,
        creator_id=utub.utub_creator,
        member_id=plain_members[0],
        other_member_id=plain_members[1],
    )


def _login_and_select(
    *, app: Flask, page: Page, user_id: int, scenario: ShortLinkScenario
) -> None:
    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id,
        utub_id=scenario.utub_id,
        utub_url_id=scenario.utub_url_id,
    )


def _short_link_page_url(*, page: Page, code: str) -> str:
    return f"{current_base_url(page=page)}/s/{code}"


def _expect_copied(*, page: Page, clipboard_mock: ClipboardMockHelper) -> None:
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_contain_text(
        COPIED_MESSAGE_PREFIX
    )
    assert clipboard_mock.get_mock_stats()["errors"] == []


def _code_from_clipboard(*, clipboard_mock: ClipboardMockHelper) -> str:
    copied = clipboard_mock.get_clipboard_content()
    assert SHORT_URL_PATTERN.match(copied), copied
    return copied.rsplit("/s/", 1)[1]


def _tab_until_focused(*, page: Page, css_selector: str) -> None:
    """Press Tab until the active element matches ``css_selector``."""
    for _ in range(TAB_PRESS_LIMIT):
        if page.evaluate(
            "(sel) => !!document.activeElement && document.activeElement.matches(sel)",
            css_selector,
        ):
            return
        page.keyboard.press("Tab")
    raise AssertionError(f"Never focused {css_selector} in {TAB_PRESS_LIMIT} Tabs")


def _wait_for_modal_transition_end(*, page: Page) -> None:
    """Bootstrap ignores `hide()` while the show transition runs, so a key press
    that lands mid-fade (Cancel can already hold focus) would be silently dropped."""
    page.wait_for_function(
        "(sel) => document.querySelector(sel)"
        ".getAnimations({subtree: true}).length === 0",
        arg=HPL.HOME_MODAL,
    )


def test_copy_short_link_copies_same_link_on_second_click(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
    clipboard_mock: ClipboardMockHelper,
):
    """
    GIVEN a plain member viewing a URL card with no short link
    WHEN the member selects the card and clicks Copy short link, then clicks it again
    THEN the clipboard holds `<host>/s/<code>` (written through the ClipboardItem
        path), the second click copies the same value, and only one link exists
    """
    app = provide_app
    scenario = _seed_scenario(app=app)
    _login_and_select(app=app, page=page, user_id=scenario.member_id, scenario=scenario)
    assert get_short_link_code(app=app, utub_url_id=scenario.utub_url_id) is None

    clipboard_mock.setup_clipboard_mock()
    assert clipboard_mock.verify_mock_setup()

    wait_then_click_element(page=page, css_selector=SELECTED_SHORT_LINK_BTN)
    clipboard_mock.wait_for_write_count(count=1)
    _expect_copied(page=page, clipboard_mock=clipboard_mock)

    code = get_short_link_code(app=app, utub_url_id=scenario.utub_url_id)
    assert code is not None
    first_copy = clipboard_mock.get_clipboard_content()
    assert SHORT_URL_PATTERN.match(first_copy), first_copy
    assert first_copy.endswith(f"/s/{code}")
    assert clipboard_mock.get_clipboard_item_write_count() == 1
    expect(page.locator(HPL.URL_OUTCOME_BANNER_DETAIL)).to_have_text(first_copy)

    wait_then_click_element(page=page, css_selector=SELECTED_SHORT_LINK_BTN)
    clipboard_mock.wait_for_write_count(count=2)

    assert clipboard_mock.get_clipboard_content() == first_copy
    assert clipboard_mock.get_clipboard_item_write_count() == 2
    assert get_short_link_code(app=app, utub_url_id=scenario.utub_url_id) == code
    expect(page.locator(SELECTED_STATUS)).to_have_count(1)


def test_clipboard_item_path_failure_shows_partial_banner_with_link(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
    clipboard_mock: ClipboardMockHelper,
):
    """
    GIVEN a clipboard that rejects writes
    WHEN a member clicks Copy short link (ClipboardItem path)
    THEN the link is still made and the partial banner shows it for manual copying
    """
    app = provide_app
    scenario = _seed_scenario(app=app)
    _login_and_select(app=app, page=page, user_id=scenario.member_id, scenario=scenario)

    clipboard_mock.setup_clipboard_failure()
    assert clipboard_mock.verify_mock_setup()

    wait_then_click_element(page=page, css_selector=SELECTED_SHORT_LINK_BTN)

    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        STRINGS.SHORT_LINK_CLIPBOARD_FALLBACK
    )
    code = get_short_link_code(app=app, utub_url_id=scenario.utub_url_id)
    assert code is not None
    detail = page.locator(HPL.URL_OUTCOME_BANNER_DETAIL)
    expect(detail).to_have_text(SHORT_URL_PATTERN)
    expect(detail).to_contain_text(f"/s/{code}")

    stats = clipboard_mock.get_mock_stats()
    assert stats["writeCount"] == 0
    assert [error["operation"] for error in stats["errors"]] == ["write"]


def test_minter_revoke_from_banner_cancel_keeps_link_confirm_revokes(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
    clipboard_mock: ClipboardMockHelper,
):
    """
    GIVEN a plain member (not the adder) who just made a short link
    WHEN they open Revoke from the copied banner and Cancel
    THEN the code still resolves (200); and when they Revoke again and Confirm,
        opening the code shows the 404 page
    """
    app = provide_app
    scenario = _seed_scenario(app=app)
    _login_and_select(app=app, page=page, user_id=scenario.member_id, scenario=scenario)
    clipboard_mock.setup_clipboard_mock()

    wait_then_click_element(page=page, css_selector=SELECTED_SHORT_LINK_BTN)
    clipboard_mock.wait_for_write_count(count=1)
    code = _code_from_clipboard(clipboard_mock=clipboard_mock)
    short_page_url = _short_link_page_url(page=page, code=code)
    expect(page.locator(HPL.URL_OUTCOME_BANNER_UNDO)).to_have_text(
        STRINGS.SHORT_LINK_REVOKE_LABEL
    )

    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)
    expect(page.locator(HPL.HOME_MODAL)).to_be_visible()
    expect(page.locator(HPL.HEADER_MODAL)).to_have_text(
        STRINGS.SHORT_LINK_REVOKE_CONFIRM_TITLE
    )
    _wait_for_modal_transition_end(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_DISMISS)
    expect(page.locator(HPL.HOME_MODAL)).to_be_hidden()

    assert page.request.get(short_page_url).status == 200
    assert get_short_link_code(app=app, utub_url_id=scenario.utub_url_id) == code
    expect(page.locator(SELECTED_STATUS)).to_have_count(1)

    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)
    expect(page.locator(HPL.HOME_MODAL)).to_be_visible()
    _wait_for_modal_transition_end(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        STRINGS.SHORT_LINK_REVOKED
    )
    expect(page.locator(SELECTED_STATUS)).to_have_count(0)
    assert get_short_link_code(app=app, utub_url_id=scenario.utub_url_id) is None

    gone_page = page.context.new_page()
    response = gone_page.goto(short_page_url)
    assert response is not None
    assert response.status == 404
    expect(gone_page.locator(SLPL.DEAD_LINK_HEADING)).to_be_visible()
    expect(gone_page.locator(SLPL.BUTTON_CONTINUE)).to_have_text(
        re.compile("Go to URLS4IRL")
    )
    gone_page.close()


def test_owner_sees_lasting_revoke_on_link_another_member_made(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a short link a plain member made
    WHEN the UTub owner selects the card
    THEN the status line and the lasting Revoke are shown
    """
    app = provide_app
    scenario = _seed_scenario(app=app)
    mint_short_link_in_db(
        app=app, utub_url_id=scenario.utub_url_id, created_by=scenario.member_id
    )

    _login_and_select(
        app=app, page=page, user_id=scenario.creator_id, scenario=scenario
    )

    expect(page.locator(SELECTED_STATUS)).to_contain_text(EXPIRES_MESSAGE_PREFIX)
    expect(page.locator(SELECTED_REVOKE_BTN)).to_have_count(1)
    expect(page.locator(SELECTED_REVOKE_BTN)).to_be_visible()


def test_plain_member_who_did_not_make_link_sees_status_without_revoke(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a short link one plain member made on a URL the owner added
    WHEN a different plain member selects the card
    THEN the status line shows but there is no Revoke
    """
    app = provide_app
    scenario = _seed_scenario(app=app)
    mint_short_link_in_db(
        app=app, utub_url_id=scenario.utub_url_id, created_by=scenario.member_id
    )

    _login_and_select(
        app=app, page=page, user_id=scenario.other_member_id, scenario=scenario
    )

    expect(page.locator(SELECTED_STATUS)).to_contain_text(EXPIRES_MESSAGE_PREFIX)
    expect(page.locator(SELECTED_REVOKE_BTN)).to_have_count(0)


@pytest.mark.parametrize("confirm", [False, True], ids=["cancel", "confirm"])
def test_keyboard_only_revoke_returns_focus_to_short_link_btn(
    page: Page, create_test_utubmembers, provide_app: Flask, confirm: bool
):
    """
    GIVEN a selected card showing the lasting Revoke
    WHEN a keyboard user Tabs to Revoke, presses Enter, then Tabs to and presses
        Enter on Cancel (or, separately, Confirm)
    THEN focus returns to the card's Copy short link button
    """
    app = provide_app
    scenario = _seed_scenario(app=app)
    mint_short_link_in_db(
        app=app, utub_url_id=scenario.utub_url_id, created_by=scenario.member_id
    )
    _login_and_select(
        app=app, page=page, user_id=scenario.creator_id, scenario=scenario
    )
    expect(page.locator(SELECTED_REVOKE_BTN)).to_be_visible()

    _tab_until_focused(page=page, css_selector=HPL.BUTTON_SHORT_LINK_REVOKE)
    page.keyboard.press("Enter")
    expect(page.locator(HPL.HOME_MODAL)).to_be_visible()
    _wait_for_modal_transition_end(page=page)

    _tab_until_focused(
        page=page,
        css_selector=HPL.BUTTON_MODAL_SUBMIT if confirm else HPL.BUTTON_MODAL_DISMISS,
    )
    page.keyboard.press("Enter")
    expect(page.locator(HPL.HOME_MODAL)).to_be_hidden()

    expect(page.locator(SELECTED_SHORT_LINK_BTN)).to_be_focused()
    code = get_short_link_code(app=app, utub_url_id=scenario.utub_url_id)
    if confirm:
        expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
            STRINGS.SHORT_LINK_REVOKED
        )
        assert code is None
    else:
        assert code is not None


def test_status_row_hides_while_url_string_edit_panel_is_open(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a selected card with an active short link
    WHEN the URL edit panel opens and is then cancelled
    THEN the status row is hidden while it is open and back after
    """
    app = provide_app
    scenario = _seed_scenario(app=app)
    mint_short_link_in_db(
        app=app, utub_url_id=scenario.utub_url_id, created_by=scenario.member_id
    )
    _login_and_select(
        app=app, page=page, user_id=scenario.creator_id, scenario=scenario
    )
    expect(page.locator(SELECTED_STATUS_ROW)).to_be_visible()

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}",
    )
    expect(
        page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}")
    ).to_be_visible()
    expect(page.locator(SELECTED_STATUS_ROW)).to_be_hidden()

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_CANCEL_UPDATE}",
    )
    expect(page.locator(SELECTED_STATUS_ROW)).to_be_visible()


def test_status_row_hides_while_url_title_edit_panel_is_open(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a selected card with an active short link
    WHEN the title edit panel opens and is then cancelled
    THEN the status row is hidden while it is open and back after
    """
    app = provide_app
    scenario = _seed_scenario(app=app)
    mint_short_link_in_db(
        app=app, utub_url_id=scenario.utub_url_id, created_by=scenario.member_id
    )
    _login_and_select(
        app=app, page=page, user_id=scenario.creator_id, scenario=scenario
    )
    expect(page.locator(SELECTED_STATUS_ROW)).to_be_visible()

    open_update_url_title(
        page=page, selected_url_row=page.locator(HPL.ROW_SELECTED_URL)
    )
    expect(page.locator(SELECTED_STATUS_ROW)).to_be_hidden()

    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_CANCEL_UPDATE}",
    )
    expect(page.locator(SELECTED_STATUS_ROW)).to_be_visible()


def test_status_row_hides_while_tag_panel_is_open(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a selected card with an active short link
    WHEN the add-tag panel opens and is then closed with Escape
    THEN the status row is hidden while it is open and back after
    """
    app = provide_app
    scenario = _seed_scenario(app=app)
    mint_short_link_in_db(
        app=app, utub_url_id=scenario.utub_url_id, created_by=scenario.member_id
    )
    _login_and_select(
        app=app, page=page, user_id=scenario.creator_id, scenario=scenario
    )
    expect(page.locator(SELECTED_STATUS_ROW)).to_be_visible()

    open_tag_combobox(page=page, url_id=scenario.utub_url_id)
    expect(page.locator(SELECTED_STATUS_ROW)).to_be_hidden()

    page.keyboard.press("Escape")
    expect(page.locator(SELECTED_STATUS_ROW)).to_be_visible()


def test_trash_then_restore_url_leaves_no_link(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
    clipboard_mock: ClipboardMockHelper,
):
    """
    GIVEN a URL with an active short link
    WHEN the URL is moved to Trash and then restored
    THEN the card shows no status line and the old code shows the 404 page
    """
    app = provide_app
    scenario = _seed_scenario(app=app)
    _login_and_select(
        app=app, page=page, user_id=scenario.creator_id, scenario=scenario
    )
    clipboard_mock.setup_clipboard_mock()
    wait_then_click_element(page=page, css_selector=SELECTED_SHORT_LINK_BTN)
    clipboard_mock.wait_for_write_count(count=1)
    code = _code_from_clipboard(clipboard_mock=clipboard_mock)
    expect(page.locator(SELECTED_STATUS)).to_have_count(1)

    click_delete_on_selected_url_and_wait_for_toast(page=page)
    wait_then_click_element(page=page, css_selector=HPL.URL_OUTCOME_BANNER_UNDO)
    expect(page.locator(HPL.URL_OUTCOME_BANNER_MESSAGE)).to_have_text(
        URL_REVIVED_FROM_TRASH
    )

    row_selector = f"{HPL.ROWS_URLS}[utuburlid='{scenario.utub_url_id}']"
    expect(page.locator(row_selector)).to_have_count(1)
    # The status line is rendered into the card whether or not it is selected.
    expect(page.locator(f"{row_selector} {HPL.SHORT_LINK_STATUS_ROW}")).to_have_count(0)
    expect(page.locator(f"{row_selector} {HPL.SHORT_LINK_STATUS}")).to_have_count(0)
    assert get_short_link_code(app=app, utub_url_id=scenario.utub_url_id) is None

    gone_page = page.context.new_page()
    response = gone_page.goto(_short_link_page_url(page=page, code=code))
    assert response is not None
    assert response.status == 404
    expect(gone_page.locator(SLPL.DEAD_LINK_HEADING)).to_be_visible()
    gone_page.close()


_CARD_LAYOUT_JS = """
(utubUrlId) => {
    const card = document.querySelector(`.urlRow[utuburlid='${utubUrlId}']`);
    const options = card.querySelector('.urlOptions');
    const row = card.querySelector('.shortLinkStatusRow');
    const box = (el) => {
        const rect = el.getBoundingClientRect();
        return {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
                width: rect.width, height: rect.height};
    };
    const isShown = (el) => {
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' &&
               rect.width > 0 && rect.height > 0;
    };
    const intersects = (a, b, tolerance) =>
        a.left < b.right - tolerance && b.left < a.right - tolerance &&
        a.top < b.bottom - tolerance && b.top < a.bottom - tolerance;

    const optionsBox = box(options);
    const buttons = Array.from(options.children).filter(
        (child) => child.matches('button, a') && isShown(child));
    const buttonBoxes = buttons.map(box);
    const rowBox = box(row);
    const rowParts = Array.from(row.children).filter(isShown).map(box);

    const overlapping = [];
    card.querySelectorAll('*').forEach((el) => {
        if (row.contains(el) || el.contains(row) || el.contains(options) ||
            options.contains(el)) return;
        if (el.children.length > 0 && !el.matches('button, a')) return;
        if (!isShown(el)) return;
        // Only the visible parts (status text, Revoke) can collide: the row
        // itself spans the card, so a sibling sharing its band is not overlap.
        if (rowParts.some((part) => intersects(part, box(el), 1))) {
            const name = typeof el.className === 'string'
                ? el.className : el.className.baseVal;
            overlapping.push(`${el.tagName}.${name} ${JSON.stringify(box(el))}`);
        }
    });

    return {
        buttonCount: buttons.length,
        optionsOverflowX: options.scrollWidth - options.clientWidth,
        buttonsOutsideOptions: buttonBoxes.filter(
            (b) => b.left < optionsBox.left - 1 || b.right > optionsBox.right + 1
        ).length,
        buttonsOverlapping: buttonBoxes.filter((b, i) =>
            buttonBoxes.some((o, j) => j > i && intersects(b, o, 1))).length,
        rowBelowOptions: rowBox.top >= optionsBox.bottom - 1,
        rowPartsInsideCard: rowParts.every(
            (p) => p.left >= box(card).left - 1 && p.right <= box(card).right + 1),
        rowPartsOverlapEachOther: rowParts.length > 1 &&
            intersects(rowParts[0], rowParts[1], 1),
        overlappingContent: overlapping,
        cardOverflowX: card.scrollWidth - card.clientWidth,
        pageOverflowX:
            document.documentElement.scrollWidth -
            document.documentElement.clientWidth,
    };
}
"""


def _assert_card_layout_clean(*, page: Page, utub_url_id: int) -> None:
    expect(page.locator(SELECTED_STATUS_ROW)).to_be_visible()
    expect(page.locator(SELECTED_REVOKE_BTN)).to_be_visible()
    layout = page.evaluate(_CARD_LAYOUT_JS, utub_url_id)

    assert layout["buttonCount"] == 6, layout
    assert layout["optionsOverflowX"] <= 0, layout
    assert layout["buttonsOutsideOptions"] == 0, layout
    assert layout["buttonsOverlapping"] == 0, layout
    assert layout["rowBelowOptions"], layout
    assert layout["rowPartsInsideCard"], layout
    assert not layout["rowPartsOverlapEachOther"], layout
    assert layout["overlappingContent"] == [], layout
    assert layout["cardOverflowX"] <= 0, layout
    assert layout["pageOverflowX"] <= 0, layout


def test_card_layout_has_no_overflow_or_overlap_at_1280(
    page: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a selected card (owner view: six buttons) with an active short link
    WHEN it renders at a 1280px viewport
    THEN the button row does not overflow and the status + Revoke row overlaps
        neither `.urlOptions` nor other card content
    """
    app = provide_app
    scenario = _seed_scenario(app=app)
    mint_short_link_in_db(
        app=app, utub_url_id=scenario.utub_url_id, created_by=scenario.member_id
    )
    page.set_viewport_size({"width": 1280, "height": 900})
    _login_and_select(
        app=app, page=page, user_id=scenario.creator_id, scenario=scenario
    )

    _assert_card_layout_clean(page=page, utub_url_id=scenario.utub_url_id)


def test_card_layout_has_no_overflow_or_overlap_at_420(
    page_mobile_portrait: Page, create_test_utubmembers, provide_app: Flask
):
    """
    GIVEN a selected card (owner view: six buttons) with an active short link
    WHEN it renders at a 420px viewport
    THEN the six-button row has no horizontal overflow and the status + Revoke row
        overlaps neither `.urlOptions` nor other card content
    """
    page = page_mobile_portrait
    app = provide_app
    scenario = _seed_scenario(app=app)
    mint_short_link_in_db(
        app=app, utub_url_id=scenario.utub_url_id, created_by=scenario.member_id
    )
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=scenario.creator_id, utub_id=scenario.utub_id
    )
    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROWS_URLS}[utuburlid='{scenario.utub_url_id}']"
    )

    _assert_card_layout_clean(page=page, utub_url_id=scenario.utub_url_id)
