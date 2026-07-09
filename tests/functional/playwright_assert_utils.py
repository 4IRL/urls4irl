import re

from flask import Flask
from playwright.sync_api import Locator, Page, expect

from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_utils import (
    Decks,
    click_on_navbar,
    wait_then_click_element,
    wait_until_visible_css_selector,
)

INVALID_REQUEST_PAGE_TITLE = "Invalid Request - URLS4IRL"


def assert_not_visible_css_selector(*, page: Page, css_selector: str) -> None:
    expect(page.locator(css_selector).first).to_be_hidden()


def assert_visible_css_selector(*, page: Page, css_selector: str) -> None:
    expect(page.locator(css_selector).first).to_be_visible()


def assert_panel_visibility_mobile(*, page: Page, visible_deck: Decks) -> None:
    wait_until_visible_css_selector(page=page, css_selector=HPL.MAIN_PANEL)

    for deck in Decks:
        if visible_deck == deck:
            continue
        assert_not_visible_css_selector(page=page, css_selector=deck.value)

    assert_visible_css_selector(page=page, css_selector=visible_deck.value)


def assert_tooltip_animates(
    *,
    page: Page,
    parent_css_selector: str,
    tooltip_parent_class: str,
    tooltip_text: str,
    outside_elem: str = HPL.U4I_LOGO,
) -> None:
    """Assert that a tooltip (by U4I convention `{parent-class}-tooltip`):
    1) is hidden before hovering the parent element,
    2) shows with the expected text while hovering it,
    3) hides again after the mouse moves to an outside element."""
    tooltip_selector = f"{tooltip_parent_class}{HPL.TOOLTIP_SUFFIX}"
    assert_not_visible_css_selector(page=page, css_selector=tooltip_selector)

    parent_element = page.locator(parent_css_selector).first
    expect(parent_element).to_be_visible()
    parent_element.hover()

    tooltip = page.locator(tooltip_selector).first
    expect(tooltip).to_be_visible()
    expect(tooltip).to_have_text(tooltip_text)

    outside_element = page.locator(outside_elem).first
    expect(outside_element).to_be_visible()
    outside_element.hover()
    assert_not_visible_css_selector(page=page, css_selector=tooltip_selector)


def assert_on_404_page(*, page: Page) -> None:
    error_header = page.locator("h2").first
    expect(error_header).to_be_visible()
    expect(error_header).to_have_text(IDENTIFIERS.HTML_404)
    expect(page).to_have_title(INVALID_REQUEST_PAGE_TITLE)


def assert_on_429_page(*, page: Page) -> None:
    error_header = page.locator(f"{HPL.ERROR_PAGE_HANDLER} h2").first
    expect(error_header).to_be_visible()
    expect(error_header).to_have_text(IDENTIFIERS.HTML_429)
    expect(page).to_have_title(INVALID_REQUEST_PAGE_TITLE)


def assert_login(*, page: Page) -> None:
    """Confirm a user is logged in as the default test user."""
    assert_login_with_username(page=page, username=UTS.TEST_USERNAME_1)


def assert_login_with_username(*, page: Page, username: str) -> None:
    """Confirm a user is logged in: the hamburger toggler is present (the
    logout action lives inside its dropdown) and the desktop bar shows the
    logged-in username inline."""
    expect(page.locator(HPL.NAVBAR_TOGGLER).first).to_be_visible()
    expect(page.locator(HPL.LOGGED_IN_USERNAME_DESKTOP).first).to_have_text(
        "Logged in as " + username
    )


def assert_logged_in_on_mobile(*, page: Page) -> None:
    click_on_navbar(page=page)

    assert_visible_css_selector(page=page, css_selector=HPL.LOGGED_IN_USERNAME_READ)
    assert_visible_css_selector(page=page, css_selector=HPL.NAVBAR_LOGOUT)


def assert_no_utub_selected(*, page: Page) -> None:
    assert page.locator(f"#UTubOwner {HPL.BADGES_MEMBERS}").count() == 0
    assert page.locator(HPL.BADGES_MEMBERS).count() == 0
    assert page.locator(HPL.TAG_FILTERS).count() == 0
    assert page.locator(f"{HPL.ROWS_URLS}:visible").count() == 0


def assert_utub_selected(*, page: Page, app: Flask, utub_id: int) -> None:
    with app.app_context():
        members_in_utub: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id
        ).all()
        member_ids: list[int] = [utub_member.user_id for utub_member in members_in_utub]
        assert_members_exist_in_member_deck(page=page, member_ids=member_ids)

        urls_in_utub: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).all()
        utub_url_ids: list[int] = [utub_url.id for utub_url in urls_in_utub]
        assert_utub_url_exists_in_url_deck(page=page, utub_url_ids=utub_url_ids)
        assert_url_coloring_is_correct(page=page)

        tags_in_utub: list[Utub_Tags] = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_id
        ).all()
        utub_tag_ids: list[int] = [utub_tag.id for utub_tag in tags_in_utub]
        assert_tags_exist_in_tag_deck(page=page, utub_tag_ids=utub_tag_ids)


def assert_utub_icon(*, page: Page, app: Flask, user_id: int, utub_id: int) -> None:
    with app.app_context():
        membership: Utub_Members = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id, Utub_Members.user_id == user_id
        ).first()

    icon_selector = f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}'] "
    if membership.member_role == Member_Role.CREATOR.value:
        icon_selector += HPL.CREATOR_ICON

    elif membership.member_role == Member_Role.CO_CREATOR.value:
        icon_selector += HPL.CO_CREATOR_ICON

    elif membership.member_role == Member_Role.MEMBER.value:
        icon_selector += HPL.MEMBER_ICON

    expect(page.locator(icon_selector).first).to_be_visible()


def assert_members_exist_in_member_deck(*, page: Page, member_ids: list[int]) -> None:
    for member_id in member_ids:
        member_selector = f"{HPL.BADGES_MEMBERS}[memberid='{member_id}']"
        expect(page.locator(member_selector).first).to_be_visible()


def assert_utub_url_exists_in_url_deck(*, page: Page, utub_url_ids: list[int]) -> None:
    for utub_url_id in utub_url_ids:
        utub_url_selector = f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"
        expect(page.locator(utub_url_selector).first).to_be_visible()


def assert_elem_with_url_string_exists(*, page: Page, url_string: str) -> None:
    """If a UTub is selected and contains URLs, assert a URL row whose
    anchor href equals the given string exists."""
    matching_row = page.locator(
        f"{HPL.ROWS_URLS}:has({HPL.URL_STRING_READ}[href='{url_string}'])"
    )
    expect(matching_row.first).to_be_attached()


def assert_url_coloring_is_correct(*, page: Page) -> None:
    url_cards = page.locator(HPL.ROW_VISIBLE_URL)
    expect(url_cards.first).to_be_visible()

    cards_with_positions: list[tuple[float, str]] = []
    for url_card in url_cards.all():
        bounding_box = url_card.bounding_box()
        assert bounding_box is not None
        class_attribute = url_card.get_attribute("class")
        assert class_attribute is not None
        cards_with_positions.append((bounding_box["y"], class_attribute))

    cards_in_order = sorted(cards_with_positions, key=lambda card: card[0])
    for idx, (_, class_attribute) in enumerate(cards_in_order):
        if idx % 2 == 0:
            assert "even" in class_attribute
        else:
            assert "odd" in class_attribute


def assert_tags_exist_in_tag_deck(*, page: Page, utub_tag_ids: list[int]) -> None:
    for utub_tag_id in utub_tag_ids:
        utub_tag_selector = (
            f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{utub_tag_id}']"
        )
        expect(page.locator(utub_tag_selector).first).to_be_visible()


def assert_visited_403_on_invalid_csrf_and_reload(*, page: Page) -> None:
    error_page_subheader = page.locator(f"{SPL.ERROR_PAGE_HANDLER} h2").first
    expect(error_page_subheader).to_have_text(IDENTIFIERS.HTML_403)

    # The refresh button's click listener is attached by error.ts inside
    # $(document).ready(...), which only runs once that module script has
    # executed. The button is DOM-visible before then, so waiting on
    # visibility alone lets the click land before the listener is bound,
    # silently no-op-ing. Module scripts block "load", so this wait
    # guarantees the listener is attached before the click is issued.
    page.wait_for_load_state("load")
    wait_until_visible_css_selector(page=page, css_selector=SPL.ERROR_PAGE_REFRESH_BTN)
    wait_then_click_element(page=page, css_selector=SPL.ERROR_PAGE_REFRESH_BTN)


def assert_element_in_focus(*, page: Page, locator: Locator) -> None:
    expect(locator).to_be_focused()


def assert_active_utub(*, page: Page, utub_name: str) -> None:
    """Confirm the UTub named utub_name is the active selector and its name
    is displayed as the URL Deck header."""
    selected_utub = page.locator(HPL.SELECTOR_SELECTED_UTUB).first
    expect(selected_utub).to_be_visible()
    expect(selected_utub).to_have_class(re.compile(r"(^|\s)active(\s|$)"))
    expect(selected_utub).to_have_text(utub_name)

    url_deck_header = page.locator(HPL.HEADER_URL_DECK).first
    expect(url_deck_header).to_be_visible()
    expect(url_deck_header).to_have_text(utub_name)


def assert_update_url_state_is_shown(*, page: Page, url_row: Locator) -> None:
    hidden_btns = (
        HPL.BUTTON_URL_DELETE,
        HPL.BUTTON_TAG_CREATE,
        HPL.BUTTON_URL_ACCESS,
    )

    for btn_selector in hidden_btns:
        css_selector = f"{HPL.ROW_SELECTED_URL} {btn_selector}"
        assert_not_visible_css_selector(page=page, css_selector=css_selector)

    expect(url_row.locator(HPL.BUTTON_URL_STRING_UPDATE)).to_have_count(0)

    visible_btns = (
        HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE,
        HPL.BUTTON_URL_STRING_SUBMIT_UPDATE,
        HPL.BUTTON_URL_STRING_CANCEL_UPDATE,
    )

    for btn_selector in visible_btns:
        css_selector = f"{HPL.ROW_SELECTED_URL} {btn_selector}"
        assert_visible_css_selector(page=page, css_selector=css_selector)

    assert_visible_css_selector(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}"
    )

    assert_not_visible_css_selector(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.URL_STRING_READ}"
    )
    assert_not_visible_css_selector(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.GO_TO_URL_ICON}"
    )


def assert_update_url_state_is_hidden(*, url_row: Locator) -> None:
    visible_btns = (
        HPL.BUTTON_URL_DELETE,
        HPL.BUTTON_TAG_CREATE,
        HPL.BUTTON_URL_ACCESS,
        HPL.BUTTON_URL_STRING_UPDATE,
    )

    for btn_selector in visible_btns:
        expect(url_row.locator(btn_selector)).to_be_visible()

    expect(url_row.locator(HPL.BUTTON_BIG_URL_STRING_CANCEL_UPDATE)).to_have_count(0)

    hidden_btns = (
        HPL.BUTTON_URL_STRING_SUBMIT_UPDATE,
        HPL.BUTTON_URL_STRING_CANCEL_UPDATE,
    )

    for btn_selector in hidden_btns:
        expect(url_row.locator(btn_selector)).to_be_hidden()

    expect(url_row.locator(HPL.INPUT_URL_STRING_UPDATE)).to_be_hidden()

    expect(url_row.locator(HPL.URL_STRING_READ)).to_be_visible()
    expect(url_row.locator(HPL.GO_TO_URL_ICON)).to_be_visible()
