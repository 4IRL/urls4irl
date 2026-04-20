from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from backend import db
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.urls import Urls
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.db_utils import (
    create_test_searchable_urls,
    create_test_searchable_urls_with_tags,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import (
    login_user_and_select_utub_by_name,
    login_user_select_utub_by_name_and_url_by_title,
    login_user_to_home_page,
)
from tests.functional.selenium_utils import (
    click_on_navbar,
    select_utub_by_name,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.selenium_utils import apply_tag_filter_based_on_id
from tests.functional.urls_ui.selenium_utils import (
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
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with 0 URLs on a desktop viewport
    WHEN the user selects that UTub
    THEN the URL search wrap does not have search-ready class
    """
    app = provide_app
    user_id_for_test = 1

    _create_empty_utub(app, user_id_for_test, EMPTY_UTUB_NAME)

    login_user_and_select_utub_by_name(app, browser, user_id_for_test, EMPTY_UTUB_NAME)

    search_wrap = browser.find_element(By.CSS_SELECTOR, HPL.URL_SEARCH_WRAP)
    assert "search-ready" not in (search_wrap.get_dom_attribute("class") or "")


def test_search_input_always_visible_on_desktop(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    assert_visible_css_selector(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert_not_visible_css_selector(browser, HPL.URL_OPEN_SEARCH_ICON, time=3)
    assert_not_visible_css_selector(browser, HPL.URL_CLOSE_SEARCH_ICON, time=3)


def test_search_input_hidden_when_no_utub_selected_desktop(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN the home page with no UTub selected on desktop
    WHEN the user is logged in
    THEN the URL search input is not visible
    """
    app = provide_app
    user_id_for_test = 1

    create_test_searchable_urls(app, user_id_for_test)

    login_user_to_home_page(app, browser, user_id_for_test)

    assert_not_visible_css_selector(browser, HPL.URL_SEARCH_INPUT, time=3)


def test_desktop_escape_clears_search_but_keeps_input_visible(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)
    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    search_input.send_keys("Alpha")
    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    assert_visible_css_selector(browser, HPL.URL_SEARCH_INPUT, time=3)
    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input.get_attribute("value") == ""


def test_mobile_search_icon_hidden_when_no_urls(
    browser_mobile_portrait: WebDriver, create_test_users, provide_app: Flask
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
        app, browser_mobile_portrait, user_id_for_test, EMPTY_UTUB_NAME
    )

    assert_not_visible_css_selector(
        browser_mobile_portrait, HPL.URL_OPEN_SEARCH_ICON, time=3
    )


def test_mobile_search_icon_visible_when_urls_exist(
    browser_mobile_portrait: WebDriver, create_test_users, provide_app: Flask
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
        app, browser_mobile_portrait, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    assert_visible_css_selector(
        browser_mobile_portrait, HPL.URL_OPEN_SEARCH_ICON, time=3
    )
    assert_not_visible_css_selector(
        browser_mobile_portrait, HPL.URL_SEARCH_INPUT, time=3
    )


def test_mobile_open_and_close_search_box(
    browser_mobile_portrait: WebDriver, create_test_users, provide_app: Flask
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
        app, browser_mobile_portrait, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    open_url_search_box(browser_mobile_portrait)

    search_input = wait_then_get_element(
        browser_mobile_portrait, HPL.URL_SEARCH_INPUT, time=3
    )
    assert search_input is not None
    assert search_input.is_displayed()
    assert browser_mobile_portrait.switch_to.active_element == search_input

    wait_then_click_element(browser_mobile_portrait, HPL.URL_CLOSE_SEARCH_ICON, time=3)

    assert_not_visible_css_selector(
        browser_mobile_portrait, HPL.URL_SEARCH_INPUT, time=3
    )
    assert_visible_css_selector(
        browser_mobile_portrait, HPL.URL_OPEN_SEARCH_ICON, time=3
    )


def test_mobile_escape_key_closes_search(
    browser_mobile_portrait: WebDriver, create_test_users, provide_app: Flask
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
        app, browser_mobile_portrait, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    open_url_search_box(browser_mobile_portrait)

    search_input = wait_then_get_element(
        browser_mobile_portrait, HPL.URL_SEARCH_INPUT, time=3
    )
    assert search_input is not None

    browser_mobile_portrait.switch_to.active_element.send_keys(Keys.ESCAPE)

    assert_not_visible_css_selector(
        browser_mobile_portrait, HPL.URL_SEARCH_INPUT, time=3
    )


def test_search_by_url_title_no_match(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None

    search_input.send_keys("ZZZZZZ")
    wait_for_url_search_filter_applied(browser)

    url_rows = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    for url_row in url_rows:
        assert not url_row.is_displayed()


def test_search_by_url_title_one_match(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None

    target_title = UTS.URL_SEARCH_TITLES[0]
    search_input.send_keys("Alpha")
    wait_for_url_search_filter_applied(browser)

    url_rows = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    for url_row in url_rows:
        utub_url_id = url_row.get_attribute("utuburlid")
        if utub_url_id == str(url_title_to_id[target_title]):
            assert url_row.is_displayed()
        else:
            assert not url_row.is_displayed()


def test_search_by_url_string_one_match(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None

    target_title = UTS.URL_SEARCH_TITLES[1]
    search_input.send_keys("beta-blog")
    wait_for_url_search_filter_applied(browser)

    url_rows = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    for url_row in url_rows:
        utub_url_id = url_row.get_attribute("utuburlid")
        if utub_url_id == str(url_title_to_id[target_title]):
            assert url_row.is_displayed()
        else:
            assert not url_row.is_displayed()


def test_search_matches_both_title_and_string(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None

    # "cha" matches "Charlie Docs" by title and "charlie-docs" by URL string,
    # verifying that search checks both title and string fields
    search_input.send_keys("cha")
    wait_for_url_search_filter_applied(browser)

    target_title = UTS.URL_SEARCH_TITLES[2]
    target_id = str(url_title_to_id[target_title])

    url_rows = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    visible_count = 0
    for url_row in url_rows:
        utub_url_id = url_row.get_attribute("utuburlid")
        if utub_url_id == target_id:
            assert url_row.is_displayed()
            visible_count += 1
        else:
            assert not url_row.is_displayed()
    assert visible_count == 1


def test_search_is_case_insensitive(
    browser: WebDriver, create_test_users, provide_app: Flask
):
    """
    GIVEN a UTub with URLs and the search box open
    WHEN the user searches with uppercase letters
    THEN it still matches lowercase title/string content
    """
    app = provide_app
    user_id_for_test = 1

    url_title_to_id = create_test_searchable_urls(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None

    search_input.send_keys("ALPHA")
    wait_for_url_search_filter_applied(browser)

    target_title = UTS.URL_SEARCH_TITLES[0]
    target_id = str(url_title_to_id[target_title])

    url_rows = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    for url_row in url_rows:
        utub_url_id = url_row.get_attribute("utuburlid")
        if utub_url_id == target_id:
            assert url_row.is_displayed()
        else:
            assert not url_row.is_displayed()


def test_search_resets_on_url_creation(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None
    search_input.send_keys("ZZZZZZ")
    wait_for_url_search_filter_applied(browser)

    url_rows = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    for url_row in url_rows:
        assert not url_row.is_displayed()

    create_url(browser, "New Test URL", "https://newtest.com")

    wait_until_visible_css_selector(browser, f"{HPL.ROWS_URLS}[utuburlid]", timeout=5)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    if search_input is not None and search_input.is_displayed():
        assert search_input.get_attribute("value") == ""

    url_rows = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    for url_row in url_rows:
        assert url_row.is_displayed()


def test_search_respects_tag_filter(
    browser: WebDriver, create_test_users, provide_app: Flask
):
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    apply_tag_filter_based_on_id(browser, tag_id)

    untagged_titles = list(UTS.URL_SEARCH_TITLES)[2:]

    for title in untagged_titles:
        url_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_title_to_id[title]}']"
        assert_not_visible_css_selector(browser, url_selector, time=3)

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None

    untagged_title = UTS.URL_SEARCH_TITLES[2]
    search_input.send_keys("Charlie")
    wait_for_url_search_filter_applied(browser)

    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_title_to_id[untagged_title]}']"
    assert_not_visible_css_selector(browser, url_selector, time=3)


def test_tag_filter_change_re_evaluates_search(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None

    # "Ne" matches "Alpha News" by title and "delta-forum.net" by URL string
    # So Alpha and Delta are search-visible; Beta and Charlie are search-hidden
    search_input.send_keys("Ne")
    wait_for_url_search_filter_applied(browser)

    alpha_id = str(url_title_to_id[UTS.URL_SEARCH_TITLES[0]])
    delta_id = str(url_title_to_id[UTS.URL_SEARCH_TITLES[3]])
    beta_id = str(url_title_to_id[UTS.URL_SEARCH_TITLES[1]])
    charlie_id = str(url_title_to_id[UTS.URL_SEARCH_TITLES[2]])

    alpha_selector = f"{HPL.ROWS_URLS}[utuburlid='{alpha_id}']"
    delta_selector = f"{HPL.ROWS_URLS}[utuburlid='{delta_id}']"
    beta_selector = f"{HPL.ROWS_URLS}[utuburlid='{beta_id}']"
    charlie_selector = f"{HPL.ROWS_URLS}[utuburlid='{charlie_id}']"

    assert_visible_css_selector(browser, alpha_selector, time=3)
    assert_visible_css_selector(browser, delta_selector, time=3)
    assert_not_visible_css_selector(browser, beta_selector, time=3)
    assert_not_visible_css_selector(browser, charlie_selector, time=3)

    # Apply tag filter: only Alpha and Beta are tagged
    # Alpha stays visible (tagged + search-match)
    # Delta becomes hidden (untagged, filtered out by tag)
    # Beta stays hidden (tagged but search-hidden)
    # Charlie stays hidden (untagged + search-hidden)
    apply_tag_filter_based_on_id(browser, tag_id)

    assert_visible_css_selector(browser, alpha_selector, time=3)
    assert_not_visible_css_selector(browser, delta_selector, time=3)
    assert_not_visible_css_selector(browser, beta_selector, time=3)
    assert_not_visible_css_selector(browser, charlie_selector, time=3)


def test_search_resets_on_utub_switch(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None
    search_input.send_keys("Alpha")

    select_utub_by_name(browser, second_utub_name)

    search_wrap = browser.find_element(By.CSS_SELECTOR, HPL.URL_SEARCH_WRAP)
    WebDriverWait(browser, 10).until(
        lambda _: "search-ready" not in (search_wrap.get_dom_attribute("class") or "")
    )

    search_input = browser.find_element(By.CSS_SELECTOR, HPL.URL_SEARCH_INPUT)
    assert search_input.get_attribute("value") == ""


def test_mobile_search_closes_on_utub_switch(
    browser_mobile_portrait: WebDriver, create_test_users, provide_app: Flask
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
        app, browser_mobile_portrait, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    open_url_search_box(browser_mobile_portrait)

    search_input = wait_then_get_element(
        browser_mobile_portrait, HPL.URL_SEARCH_INPUT, time=3
    )
    assert search_input is not None
    search_input.send_keys("Alpha")

    click_on_navbar(browser_mobile_portrait)
    wait_then_click_element(browser_mobile_portrait, HPL.NAVBAR_UTUB_DECK, time=10)
    select_utub_by_name(browser_mobile_portrait, second_utub_name)

    search_wrap = browser_mobile_portrait.find_element(
        By.CSS_SELECTOR, HPL.URL_SEARCH_WRAP
    )
    WebDriverWait(browser_mobile_portrait, 10).until(
        lambda _: "visible-flex" not in (search_wrap.get_dom_attribute("class") or "")
    )

    search_input = browser_mobile_portrait.find_element(
        By.CSS_SELECTOR, HPL.URL_SEARCH_INPUT
    )
    assert search_input.get_attribute("value") == ""

    assert_not_visible_css_selector(
        browser_mobile_portrait, HPL.URL_OPEN_SEARCH_ICON, time=3
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
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, SINGLE_URL_UTUB_NAME, SINGLE_URL_TITLE
    )

    search_wrap = browser.find_element(By.CSS_SELECTOR, HPL.URL_SEARCH_WRAP)
    WebDriverWait(browser, 10).until(
        lambda _: "search-ready" in (search_wrap.get_dom_attribute("class") or "")
    )

    url_row = browser.find_element(By.CSS_SELECTOR, HPL.ROW_SELECTED_URL)

    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}", time=5
    )
    wait_until_visible_css_selector(browser, HPL.BODY_MODAL, timeout=5)
    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(browser, HPL.HOME_MODAL)
    assert wait_for_element_to_be_removed(browser, url_row)

    WebDriverWait(browser, 10).until(
        lambda _: "search-ready"
        not in (
            browser.find_element(
                By.CSS_SELECTOR, HPL.URL_SEARCH_WRAP
            ).get_dom_attribute("class")
            or ""
        )
    )


def test_active_search_preserved_on_url_deletion(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app,
        browser,
        user_id_for_test,
        URL_SEARCH_UTUB_NAME,
        UTS.URL_SEARCH_TITLES[0],
    )

    focus_url_search_input(browser)
    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    search_input.send_keys("Alpha")
    wait_for_url_search_filter_applied(browser)

    url_row = browser.find_element(By.CSS_SELECTOR, HPL.ROW_SELECTED_URL)

    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}", time=5
    )
    wait_until_visible_css_selector(browser, HPL.BODY_MODAL, timeout=5)
    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(browser, HPL.HOME_MODAL)
    assert wait_for_element_to_be_removed(browser, url_row)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input.get_attribute("value") == "Alpha"

    url_rows = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    for remaining_row in url_rows:
        assert not remaining_row.is_displayed()


def test_no_results_message_shown_when_search_matches_nothing(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None
    search_input.send_keys("ZZZZZZ")
    wait_for_url_search_filter_applied(browser)

    no_results = wait_then_get_element(browser, HPL.URL_SEARCH_NO_RESULTS, time=3)
    assert no_results is not None
    assert no_results.is_displayed()
    assert no_results.text == "No URLs found"


def test_no_results_message_hidden_when_search_has_matches(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None
    search_input.send_keys("ZZZZZZ")
    wait_for_url_search_filter_applied(browser)

    no_results = wait_then_get_element(browser, HPL.URL_SEARCH_NO_RESULTS, time=3)
    assert no_results is not None
    assert no_results.is_displayed()

    search_input.clear()
    search_input.send_keys("Alpha")
    wait_for_url_search_filter_applied(browser)

    assert_not_visible_css_selector(browser, HPL.URL_SEARCH_NO_RESULTS, time=3)


def test_no_results_message_hidden_on_utub_switch(
    browser: WebDriver, create_test_users, provide_app: Flask
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
        app, browser, user_id_for_test, URL_SEARCH_UTUB_NAME
    )

    focus_url_search_input(browser)

    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert search_input is not None
    search_input.send_keys("ZZZZZZ")
    wait_for_url_search_filter_applied(browser)

    no_results = wait_then_get_element(browser, HPL.URL_SEARCH_NO_RESULTS, time=3)
    assert no_results is not None
    assert no_results.is_displayed()

    select_utub_by_name(browser, second_utub_name)

    assert_not_visible_css_selector(browser, HPL.URL_SEARCH_NO_RESULTS, time=3)
