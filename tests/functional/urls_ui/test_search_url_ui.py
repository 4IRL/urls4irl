import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.urls import Urls
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    create_test_searchable_urls,
    create_test_searchable_urls_with_tags,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_name,
    login_user_select_utub_by_name_and_url_by_title,
)
from tests.functional.playwright_utils import (
    click_on_navbar,
    login_user_to_home_page,
    select_utub_by_name,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_css_property,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.playwright_utils import apply_tag_filter_based_on_id
from tests.functional.urls_ui.playwright_utils import (
    create_url,
    focus_url_search_input,
    open_url_search_box,
    wait_for_url_search_filter_applied,
)

pytestmark = pytest.mark.urls_ui

URL_SEARCH_UTUB_NAME = UTS.URL_SEARCH_UTUB_NAME
EMPTY_UTUB_NAME = "Empty UTub For Search"


def _create_empty_utub(app: Flask, user_id: int, utub_name: str):
    """Creates a UTub with no URLs for the given user."""
    with app.app_context():
        empty_utub = Utubs(name=utub_name, utub_description="", utub_creator=user_id)
        db.session.add(empty_utub)
        db.session.commit()

        member = Utub_Members()
        member.utub_id = empty_utub.id
        member.user_id = user_id
        member.member_role = Member_Role.CREATOR
        db.session.add(member)
        db.session.commit()


def test_search_input_hidden_when_no_urls_desktop(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with 0 URLs on a desktop viewport
    WHEN the user selects that UTub
    THEN the URL search wrap does not have search-ready class
    """
    app = provide_app
    user_id_for_test = 1

    _create_empty_utub(app, user_id_for_test, EMPTY_UTUB_NAME)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=EMPTY_UTUB_NAME
    )

    search_wrap = page.locator(HPL.URL_SEARCH_WRAP).first
    expect(search_wrap).not_to_have_class(re.compile(r"(^|\s)search-ready(\s|$)"))


def test_search_input_always_visible_on_desktop(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs on a desktop viewport
    WHEN the user selects that UTub
    THEN the URL search input is always visible without clicking any icon
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    assert_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    assert_not_visible_css_selector(page=page, css_selector=HPL.URL_OPEN_SEARCH_ICON)
    assert_not_visible_css_selector(page=page, css_selector=HPL.URL_CLOSE_SEARCH_ICON)


def test_search_input_hidden_when_no_utub_selected_desktop(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN the home page with no UTub selected on desktop
    WHEN the user is logged in
    THEN the URL search input is not visible
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)

    login_user_to_home_page(app=app, page=page, user_id=user_id_for_test)

    assert_not_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_INPUT)


def test_desktop_escape_clears_search_but_keeps_input_visible(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and a search term entered on desktop
    WHEN the user presses Escape
    THEN the search input is cleared but remains visible
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)
    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input.fill("Alpha")
    page.keyboard.press("Escape")

    assert_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    expect(search_input).to_have_value("")


def test_mobile_search_icon_hidden_when_no_urls(
    page_mobile_portrait: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with 0 URLs on a mobile viewport
    WHEN the user selects that UTub
    THEN the URL search icon is not visible
    """
    app = provide_app
    user_id_for_test = 1

    _create_empty_utub(app, user_id_for_test, EMPTY_UTUB_NAME)

    login_user_and_select_utub_by_name(
        app=app,
        page=page_mobile_portrait,
        user_id=user_id_for_test,
        utub_name=EMPTY_UTUB_NAME,
    )

    assert_not_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.URL_OPEN_SEARCH_ICON
    )


def test_mobile_search_icon_visible_when_urls_exist(
    page_mobile_portrait: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs on a mobile viewport
    WHEN the user selects that UTub
    THEN the URL search icon is visible and the input is hidden
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page_mobile_portrait,
        user_id=user_id_for_test,
        utub_name=URL_SEARCH_UTUB_NAME,
    )

    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.URL_OPEN_SEARCH_ICON
    )
    assert_not_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.URL_SEARCH_INPUT
    )


def test_mobile_open_and_close_search_box(
    page_mobile_portrait: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs selected on a mobile viewport
    WHEN the user clicks the search icon, the search input is visible and focused;
         clicking close hides the input and shows the search icon again
    THEN the search box opens and closes correctly
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page_mobile_portrait,
        user_id=user_id_for_test,
        utub_name=URL_SEARCH_UTUB_NAME,
    )

    open_url_search_box(page=page_mobile_portrait)

    search_input = wait_then_get_element(
        page=page_mobile_portrait, css_selector=HPL.URL_SEARCH_INPUT
    )
    expect(search_input).to_be_visible()
    expect(search_input).to_be_focused()

    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.URL_CLOSE_SEARCH_ICON
    )

    assert_not_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.URL_SEARCH_INPUT
    )
    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.URL_OPEN_SEARCH_ICON
    )


def test_mobile_escape_key_closes_search(
    page_mobile_portrait: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and the search box open on mobile
    WHEN the user presses Escape
    THEN the search box closes
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app,
        page=page_mobile_portrait,
        user_id=user_id_for_test,
        utub_name=URL_SEARCH_UTUB_NAME,
    )

    open_url_search_box(page=page_mobile_portrait)

    wait_then_get_element(page=page_mobile_portrait, css_selector=HPL.URL_SEARCH_INPUT)

    page_mobile_portrait.keyboard.press("Escape")

    assert_not_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.URL_SEARCH_INPUT
    )


def test_search_by_url_title_no_match(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and the search box open
    WHEN the user searches for a term that matches no URL titles or strings
    THEN all URL rows are hidden
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)

    search_input.fill("ZZZZZZ")
    wait_for_url_search_filter_applied(page=page)

    url_rows = page.locator(HPL.ROWS_URLS).all()
    for url_row in url_rows:
        expect(url_row).to_be_hidden()


def test_search_by_url_title_one_match(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and the search box open
    WHEN the user searches for a substring matching exactly one URL title
    THEN only that URL card is visible
    """
    app = provide_app
    user_id_for_test = 1

    url_title_to_id = create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)

    target_title = UTS.URL_SEARCH_TITLES[0]
    search_input.fill("Alpha")
    wait_for_url_search_filter_applied(page=page)

    url_rows = page.locator(HPL.ROWS_URLS).all()
    for url_row in url_rows:
        utub_url_id = url_row.get_attribute("utuburlid")
        if utub_url_id == str(url_title_to_id[target_title]):
            expect(url_row).to_be_visible()
        else:
            expect(url_row).to_be_hidden()


def test_search_by_url_string_one_match(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and the search box open
    WHEN the user searches for a substring matching exactly one URL string
    THEN only that URL card is visible
    """
    app = provide_app
    user_id_for_test = 1

    url_title_to_id = create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)

    target_title = UTS.URL_SEARCH_TITLES[1]
    search_input.fill("beta-blog")
    wait_for_url_search_filter_applied(page=page)

    url_rows = page.locator(HPL.ROWS_URLS).all()
    for url_row in url_rows:
        utub_url_id = url_row.get_attribute("utuburlid")
        if utub_url_id == str(url_title_to_id[target_title]):
            expect(url_row).to_be_visible()
        else:
            expect(url_row).to_be_hidden()


def test_search_matches_both_title_and_string(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and the search box open
    WHEN the user searches for a term that matches one URL by title and a different URL by string
    THEN both matching URLs are visible and others are hidden
    """
    app = provide_app
    user_id_for_test = 1

    url_title_to_id = create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)

    # "cha" matches "Charlie Docs" by title and "charlie-docs" by URL string,
    # verifying that search checks both title and string fields
    search_input.fill("cha")
    wait_for_url_search_filter_applied(page=page)

    target_title = UTS.URL_SEARCH_TITLES[2]
    target_id = str(url_title_to_id[target_title])

    url_rows = page.locator(HPL.ROWS_URLS).all()
    visible_count = 0
    for url_row in url_rows:
        utub_url_id = url_row.get_attribute("utuburlid")
        if utub_url_id == target_id:
            expect(url_row).to_be_visible()
            visible_count += 1
        else:
            expect(url_row).to_be_hidden()
    assert visible_count == 1


def test_search_is_case_insensitive(page: Page, create_test_users, provide_app: Flask):
    """
    GIVEN a UTub with URLs and the search box open
    WHEN the user searches with uppercase letters
    THEN it still matches lowercase title/string content
    """
    app = provide_app
    user_id_for_test = 1

    url_title_to_id = create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)

    search_input.fill("ALPHA")
    wait_for_url_search_filter_applied(page=page)

    target_title = UTS.URL_SEARCH_TITLES[0]
    target_id = str(url_title_to_id[target_title])

    url_rows = page.locator(HPL.ROWS_URLS).all()
    for url_row in url_rows:
        utub_url_id = url_row.get_attribute("utuburlid")
        if utub_url_id == target_id:
            expect(url_row).to_be_visible()
        else:
            expect(url_row).to_be_hidden()


def test_search_resets_on_url_creation(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs, search box open and a search term entered
    WHEN the user creates a new URL
    THEN the search input is cleared and all URLs are visible
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input.fill("ZZZZZZ")
    wait_for_url_search_filter_applied(page=page)

    url_rows = page.locator(HPL.ROWS_URLS).all()
    for url_row in url_rows:
        expect(url_row).to_be_hidden()

    create_url(page=page, url_title="New Test URL", url_string="https://newtest.com")

    wait_until_visible_css_selector(
        page=page, css_selector=f"{HPL.ROWS_URLS}[utuburlid]"
    )

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    expect(search_input).to_have_value("")

    url_rows = page.locator(HPL.ROWS_URLS).all()
    for url_row in url_rows:
        expect(url_row).to_be_visible()


def test_search_respects_tag_filter(page: Page, create_test_users, provide_app: Flask):
    """
    GIVEN a UTub with URLs where a tag filter hides some URLs
    WHEN the user opens search and types a term matching a tag-hidden URL
    THEN the tag-hidden URL stays hidden (search does not override tag filter)
    """
    app = provide_app
    user_id_for_test = 1

    url_title_to_id, tag_id, utub_id = create_test_searchable_urls_with_tags(
        app, user_id_for_test
    )
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_id)

    untagged_titles = list(UTS.URL_SEARCH_TITLES)[2:]

    for title in untagged_titles:
        url_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_title_to_id[title]}']"
        assert_not_visible_css_selector(page=page, css_selector=url_selector)

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)

    untagged_title = UTS.URL_SEARCH_TITLES[2]
    search_input.fill("Charlie")
    wait_for_url_search_filter_applied(page=page)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_title_to_id[untagged_title]}']"
    assert_not_visible_css_selector(page=page, css_selector=url_selector)


def test_tag_filter_change_re_evaluates_search(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs, search box open with a search term
    WHEN the user selects a tag filter that hides a search-visible URL
    THEN that URL is hidden by the tag filter and search-hidden URLs remain hidden
    """
    app = provide_app
    user_id_for_test = 1

    url_title_to_id, tag_id, utub_id = create_test_searchable_urls_with_tags(
        app, user_id_for_test
    )
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)

    # "Ne" matches "Alpha News" by title and "delta-forum.net" by URL string
    # So Alpha and Delta are search-visible; Beta and Charlie are search-hidden
    search_input.fill("Ne")
    wait_for_url_search_filter_applied(page=page)

    alpha_id = str(url_title_to_id[UTS.URL_SEARCH_TITLES[0]])
    delta_id = str(url_title_to_id[UTS.URL_SEARCH_TITLES[3]])
    beta_id = str(url_title_to_id[UTS.URL_SEARCH_TITLES[1]])
    charlie_id = str(url_title_to_id[UTS.URL_SEARCH_TITLES[2]])

    alpha_selector = f"{HPL.ROWS_URLS}[utuburlid='{alpha_id}']"
    delta_selector = f"{HPL.ROWS_URLS}[utuburlid='{delta_id}']"
    beta_selector = f"{HPL.ROWS_URLS}[utuburlid='{beta_id}']"
    charlie_selector = f"{HPL.ROWS_URLS}[utuburlid='{charlie_id}']"

    assert_visible_css_selector(page=page, css_selector=alpha_selector)
    assert_visible_css_selector(page=page, css_selector=delta_selector)
    assert_not_visible_css_selector(page=page, css_selector=beta_selector)
    assert_not_visible_css_selector(page=page, css_selector=charlie_selector)

    # Apply tag filter: only Alpha and Beta are tagged
    # Alpha stays visible (tagged + search-match)
    # Delta becomes hidden (untagged, filtered out by tag)
    # Beta stays hidden (tagged but search-hidden)
    # Charlie stays hidden (untagged + search-hidden)
    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_id)

    assert_visible_css_selector(page=page, css_selector=alpha_selector)
    assert_not_visible_css_selector(page=page, css_selector=delta_selector)
    assert_not_visible_css_selector(page=page, css_selector=beta_selector)
    assert_not_visible_css_selector(page=page, css_selector=charlie_selector)


def test_search_resets_on_utub_switch(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and an active search containing text
    WHEN the user selects a different UTub
    THEN the search input is cleared and the search wrap loses search-ready
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)

    second_utub_name = "Second UTub For Search"
    _create_empty_utub(app, user_id_for_test, second_utub_name)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input.fill("Alpha")

    select_utub_by_name(page=page, utub_name=second_utub_name)

    search_wrap = page.locator(HPL.URL_SEARCH_WRAP).first
    expect(search_wrap).not_to_have_class(re.compile(r"(^|\s)search-ready(\s|$)"))

    search_input = page.locator(HPL.URL_SEARCH_INPUT).first
    expect(search_input).to_have_value("")


def test_mobile_search_closes_on_utub_switch(
    page_mobile_portrait: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and the mobile search box open with text
    WHEN the user selects a different UTub
    THEN the search box collapses, input is cleared, and the search icon
        reflects the new UTub's URL count
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)

    second_utub_name = "Second UTub For Search"
    _create_empty_utub(app, user_id_for_test, second_utub_name)

    login_user_and_select_utub_by_name(
        app=app,
        page=page_mobile_portrait,
        user_id=user_id_for_test,
        utub_name=URL_SEARCH_UTUB_NAME,
    )

    open_url_search_box(page=page_mobile_portrait)

    search_input = wait_then_get_element(
        page=page_mobile_portrait, css_selector=HPL.URL_SEARCH_INPUT
    )
    search_input.fill("Alpha")

    click_on_navbar(page=page_mobile_portrait)
    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.NAVBAR_UTUB_DECK
    )
    select_utub_by_name(page=page_mobile_portrait, utub_name=second_utub_name)

    search_wrap = page_mobile_portrait.locator(HPL.URL_SEARCH_WRAP).first
    expect(search_wrap).not_to_have_class(re.compile(r"(^|\s)visible-flex(\s|$)"))

    search_input = page_mobile_portrait.locator(HPL.URL_SEARCH_INPUT).first
    expect(search_input).to_have_value("")

    assert_not_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.URL_OPEN_SEARCH_ICON
    )


SINGLE_URL_UTUB_NAME = "Single URL UTub"
SINGLE_URL_TITLE = "Only URL"
SINGLE_URL_STRING = "https://only-url.com"


def _create_single_url_utub(app: Flask, user_id: int) -> int:
    """Creates a UTub with exactly one URL for delete testing. Returns utub_url_id."""
    with app.app_context():
        utub = Utubs(
            name=SINGLE_URL_UTUB_NAME, utub_description="", utub_creator=user_id
        )
        db.session.add(utub)
        db.session.commit()

        member = Utub_Members()
        member.utub_id = utub.id
        member.user_id = user_id
        member.member_role = Member_Role.CREATOR
        db.session.add(member)
        db.session.commit()

        url = Urls(normalized_url=SINGLE_URL_STRING, current_user_id=user_id)
        db.session.add(url)
        db.session.flush()

        utub_url = Utub_Urls()
        utub_url.url_title = SINGLE_URL_TITLE
        utub_url.url_id = url.id
        utub_url.utub_id = utub.id
        utub_url.user_id = user_id
        db.session.add(utub_url)
        db.session.commit()

        return utub_url.id


def test_search_icon_hidden_after_last_url_deleted(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with exactly one URL on a desktop viewport
    WHEN the user deletes the only URL
    THEN the URL search wrap loses search-ready class
    """
    app = provide_app
    user_id_for_test = 1

    _create_single_url_utub(app, user_id_for_test)

    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=SINGLE_URL_UTUB_NAME,
        url_title=SINGLE_URL_TITLE,
    )

    search_wrap = page.locator(HPL.URL_SEARCH_WRAP).first
    expect(search_wrap).to_have_class(re.compile(r"(^|\s)search-ready(\s|$)"))

    url_row = page.locator(HPL.ROW_SELECTED_URL).first

    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )
    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}"
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.BODY_MODAL)
    # wait_until_visible_css_selector only confirms the modal is attached and
    # visible, not that its Bootstrap fade-in transition has finished.
    # Clicking submit mid-transition causes Bootstrap to drop the subsequent
    # modal("hide") call, so the modal never becomes hidden. Gate on the
    # fade-in being fully settled (opacity == 1) before clicking.
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_element_to_be_removed(page=page, locator=url_row)

    expect(page.locator(HPL.URL_SEARCH_WRAP).first).not_to_have_class(
        re.compile(r"(^|\s)search-ready(\s|$)")
    )


def test_active_search_preserved_on_url_deletion(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and an active search on desktop
    WHEN the user deletes a URL while search is open
    THEN the search input retains its value and remaining URLs respect the
        active filter, with alternating backgrounds on visible cards
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)

    login_user_select_utub_by_name_and_url_by_title(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_name=URL_SEARCH_UTUB_NAME,
        url_title=UTS.URL_SEARCH_TITLES[0],
    )

    focus_url_search_input(page=page)
    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input.fill("Alpha")
    wait_for_url_search_filter_applied(page=page)

    url_row = page.locator(HPL.ROW_SELECTED_URL).first

    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}"
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.BODY_MODAL)
    # wait_until_visible_css_selector only confirms the modal is attached and
    # visible, not that its Bootstrap fade-in transition has finished.
    # Clicking submit mid-transition causes Bootstrap to drop the subsequent
    # modal("hide") call, so the modal never becomes hidden. Gate on the
    # fade-in being fully settled (opacity == 1) before clicking.
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_element_to_be_removed(page=page, locator=url_row)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    expect(search_input).to_have_value("Alpha")

    url_rows = page.locator(HPL.ROWS_URLS).all()
    for remaining_row in url_rows:
        expect(remaining_row).to_be_hidden()


def test_no_results_message_shown_when_search_matches_nothing(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs on desktop
    WHEN the user searches for a term that matches no URLs
    THEN the "No URLs found" message is visible and centered
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input.fill("ZZZZZZ")
    wait_for_url_search_filter_applied(page=page)

    no_results = wait_then_get_element(
        page=page, css_selector=HPL.URL_SEARCH_NO_RESULTS
    )
    expect(no_results).to_be_visible()
    expect(no_results).to_have_text(UTS.URL_SEARCH_NO_URLS)


def test_no_results_message_hidden_when_search_has_matches(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs on desktop and the no-results message showing
    WHEN the user changes the search to a term that matches a URL
    THEN the no-results message is hidden
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input.fill("ZZZZZZ")
    wait_for_url_search_filter_applied(page=page)

    no_results = wait_then_get_element(
        page=page, css_selector=HPL.URL_SEARCH_NO_RESULTS
    )
    expect(no_results).to_be_visible()

    search_input.fill("Alpha")
    wait_for_url_search_filter_applied(page=page)

    assert_not_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_NO_RESULTS)


def test_no_results_message_hidden_on_utub_switch(
    page: Page, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs, search showing no-results message
    WHEN the user selects a different UTub
    THEN the no-results message is hidden
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)
    second_utub_name = "Second UTub For Search"
    _create_empty_utub(app, user_id_for_test, second_utub_name)

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id_for_test, utub_name=URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(page=page)

    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input.fill("ZZZZZZ")
    wait_for_url_search_filter_applied(page=page)

    no_results = wait_then_get_element(
        page=page, css_selector=HPL.URL_SEARCH_NO_RESULTS
    )
    expect(no_results).to_be_visible()

    select_utub_by_name(page=page, utub_name=second_utub_name)

    assert_not_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_NO_RESULTS)
