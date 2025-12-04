from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from src import db
from src.models.users import Users
from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from tests.functional.assert_utils import (
    assert_active_utub,
    assert_login_with_username,
    assert_not_visible_css_selector,
    assert_visible_css_selector,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.db_utils import get_utub_this_user_created
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_and_select_utub_by_utubid
from tests.functional.selenium_utils import (
    dismiss_modal_with_click_out,
    invalidate_csrf_token_on_page,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_hidden,
)
from tests.functional.tags_ui.assert_utils import assert_delete_utub_tag_modal_shown
from tests.functional.tags_ui.selenium_utils import (
    apply_tag_filter_by_id_and_get_shown_urls,
    click_open_update_utub_tags_btn,
    delete_utub_tag_elem,
    get_all_utub_tags_ids_in_utub,
    get_first_visible_tag_in_utub,
    open_delete_utub_tag_confirm_modal_for_tag,
)

pytestmark = pytest.mark.tags_ui


def test_open_delete_utub_tag_modal_click(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user in a UTub with Tags
    WHEN they click on the delete UTub Tag button
    THEN ensure the modal to confirm deleting a tag is shown
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    tag_id = get_first_visible_tag_in_utub(browser).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    click_open_update_utub_tags_btn(browser)
    delete_utub_tag_css_selector = f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}'] > {HPL.UTUB_TAG_MENU_WRAP} > {HPL.BUTTON_UTUB_TAG_DELETE}"

    assert_visible_css_selector(browser, delete_utub_tag_css_selector)
    wait_then_click_element(browser, delete_utub_tag_css_selector, time=3)

    assert_delete_utub_tag_modal_shown(browser, int(tag_id), app)


def test_open_delete_utub_tag_modal_key(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user in a UTub with Tags
    WHEN they focus on the delete UTub Tag button and press the enter key
    THEN ensure the modal to confirm deleting a tag is shown
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    tag_id = get_first_visible_tag_in_utub(browser).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    click_open_update_utub_tags_btn(browser)
    delete_utub_tag_css_selector = f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}'] > {HPL.UTUB_TAG_MENU_WRAP} > {HPL.BUTTON_UTUB_TAG_DELETE}"

    assert_visible_css_selector(browser, delete_utub_tag_css_selector)
    delete_tag_btn = wait_then_get_element(
        browser, delete_utub_tag_css_selector, time=3
    )
    assert delete_tag_btn

    delete_tag_btn.send_keys(Keys.ENTER)
    assert_delete_utub_tag_modal_shown(browser, int(tag_id), app)


def test_dismiss_delete_utub_tag_modal_btn_click(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user in a UTub with Tags
    WHEN they open the confirm delete UTub Tag modal and then click on the cancel button
    THEN ensure the modal is closed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    tag_id = get_first_visible_tag_in_utub(browser).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    open_delete_utub_tag_confirm_modal_for_tag(browser, tag_id, app)

    wait_then_click_element(browser, HPL.BUTTON_MODAL_DISMISS)

    confirm_utub_tag_del_modal = wait_until_hidden(browser, HPL.HOME_MODAL)

    # Assert warning modal appears with appropriate text
    assert not confirm_utub_tag_del_modal.is_displayed()


def test_dismiss_delete_utub_tag_modal_btn_key(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user in a UTub with Tags
    WHEN they open the confirm delete UTub Tag modal and then focus on the cancel button
    and press the enter key
    THEN ensure the modal is closed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    tag_id = get_first_visible_tag_in_utub(browser).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    open_delete_utub_tag_confirm_modal_for_tag(browser, tag_id, app)

    close_btn = wait_then_get_element(browser, HPL.BUTTON_MODAL_DISMISS)
    assert close_btn

    close_btn.send_keys(Keys.ENTER)

    confirm_utub_tag_del_modal = wait_until_hidden(browser, HPL.HOME_MODAL)

    # Assert warning modal appears with appropriate text
    assert not confirm_utub_tag_del_modal.is_displayed()


def test_dismiss_delete_utub_tag_modal_x(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user in a UTub with Tags
    WHEN they open the confirm delete UTub Tag modal and then click on the X button
    THEN ensure the modal is closed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    tag_id = get_first_visible_tag_in_utub(browser).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    open_delete_utub_tag_confirm_modal_for_tag(browser, tag_id, app)

    wait_then_click_element(browser, HPL.BUTTON_X_CLOSE)

    confirm_utub_tag_del_modal = wait_until_hidden(browser, HPL.HOME_MODAL)

    # Assert warning modal appears with appropriate text
    assert not confirm_utub_tag_del_modal.is_displayed()


def test_dismiss_delete_utub_tag_modal_click_outside_modal(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user in a UTub with Tags
    WHEN they open the confirm delete UTub Tag modal and then click outside the modal
    THEN ensure the modal is closed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    tag_id = get_first_visible_tag_in_utub(browser).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    open_delete_utub_tag_confirm_modal_for_tag(browser, tag_id, app)
    dismiss_modal_with_click_out(browser)

    confirm_utub_tag_del_modal = wait_until_hidden(browser, HPL.HOME_MODAL)

    # Assert warning modal appears with appropriate text
    assert not confirm_utub_tag_del_modal.is_displayed()


def test_delete_utub_tag_removes_utub_tag_elem(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user in a UTub with Tags
    WHEN they delete a UTub tag
    THEN ensure the UTub Tag element is removed from the Tags deck
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    tag_id = get_first_visible_tag_in_utub(browser).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    delete_utub_tag_elem(browser, tag_id, app)

    # Assert utub tag no longer exists
    assert tag_id not in get_all_utub_tags_ids_in_utub(browser)


def test_delete_utub_tag_removes_url_tag_elems(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user in a UTub with Tags
    WHEN they delete a UTub tag
    THEN ensure associated URL Tag elements are removed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    tag_id = get_first_visible_tag_in_utub(browser).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    url_tag_badge_selector = f"{HPL.TAG_BADGES}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}']"
    assert browser.find_elements(By.CSS_SELECTOR, url_tag_badge_selector)

    delete_utub_tag_elem(browser, tag_id, app)

    assert not browser.find_elements(By.CSS_SELECTOR, url_tag_badge_selector)


def test_delete_utub_tag_while_selected_unfilters_url_and_updates_text(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user in a UTub with Tags
    WHEN they delete a UTub tag that is currently selected and filtering
    THEN ensure filtering is reset and the tag deck text is updated
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    # Add two tags to the UTub, and then add each to a single different URL
    with app.app_context():
        utub_urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        first_url, second_url = utub_urls[0], utub_urls[1]
        for tag_string, url in zip(("tag_1", "tag_2"), (first_url, second_url)):
            new_tag = Utub_Tags(
                utub_id=utub_user_created.id, tag_string=tag_string, created_by=user_id
            )
            db.session.add(new_tag)
            db.session.commit()

            new_utub_url_tag = Utub_Url_Tags(
                utub_id=utub_user_created.id, utub_tag_id=new_tag.id, utub_url_id=url.id
            )
            db.session.add(new_utub_url_tag)
            db.session.commit()

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    tag_id = get_first_visible_tag_in_utub(browser).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    displayed_urls_with_tag = apply_tag_filter_by_id_and_get_shown_urls(
        browser, int(tag_id)
    )

    tag_deck_subheader = wait_then_get_element(browser, HPL.SUBHEADER_TAG_DECK, time=3)
    assert tag_deck_subheader

    tag_deck_subheader_txt = tag_deck_subheader.text
    assert "1 of 5" in tag_deck_subheader_txt

    delete_utub_tag_elem(browser, tag_id, app)

    url_row_elements = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    visible_urls = [url_row for url_row in url_row_elements if url_row.is_displayed()]

    assert len(visible_urls) > len(displayed_urls_with_tag)

    tag_deck_subheader = wait_then_get_element(browser, HPL.SUBHEADER_TAG_DECK, time=3)
    assert tag_deck_subheader

    tag_deck_subheader_txt = tag_deck_subheader.text
    assert "0 of 5" in tag_deck_subheader_txt


def test_delete_last_utub_tag_closes_utub_tag_menu(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a user in a UTub with Tags
    WHEN they delete the last UTub tag in the deck
    THEN ensure the UTub Tag menu is closed
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    # Add two tags to the UTub, and then add each to a single different URL
    with app.app_context():
        new_tag = Utub_Tags(
            utub_id=utub_user_created.id, tag_string="tag_1", created_by=user_id
        )
        db.session.add(new_tag)
        db.session.commit()

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    tag_id = get_first_visible_tag_in_utub(browser).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    delete_utub_tag_elem(browser, tag_id, app)

    assert_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS
    )
    assert_not_visible_css_selector(browser, css_selector=HPL.UTUB_TAG_MENU_WRAP)
    assert_not_visible_css_selector(
        browser, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )
    assert_not_visible_css_selector(browser, css_selector=HPL.BUTTON_UTUB_TAG_DELETE)


def test_delete_utub_tag_invalid_csrf_token(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user in a UTub with Tags
    WHEN they delete a UTub tag in the deck with an invalid CSRF token
    THEN ensure U4I responds with a proper error message
    """

    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)

    # Add two tags to the UTub, and then add each to a single different URL
    with app.app_context():
        user: Users = Users.query.get(1)
        username = user.username

    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_user_created.id)

    tag_id = get_first_visible_tag_in_utub(browser).get_attribute(
        HPL.TAG_BADGE_ID_ATTRIB
    )
    assert tag_id

    invalidate_csrf_token_on_page(browser)
    open_delete_utub_tag_confirm_modal_for_tag(browser, tag_id, app)
    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    assert_login_with_username(browser, username)

    # Reload will bring user back to the UTub they were in before
    assert_active_utub(browser, utub_user_created.name)

    delete_utub_submit_btn_modal = wait_until_hidden(
        browser, HPL.BUTTON_MODAL_SUBMIT, timeout=3
    )
    assert not delete_utub_submit_btn_modal.is_displayed()
