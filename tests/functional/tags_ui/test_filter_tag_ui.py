import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    add_two_tags_across_urls_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as ML
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid,
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.playwright_utils import (
    get_css_selector_for_url_by_id,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.playwright_utils import (
    add_tag_to_url,
    apply_tag_filter_by_id_and_get_shown_urls,
    get_delete_tag_button_on_hover,
    get_tag_badge_selector_on_selected_url_by_tag_id,
    get_utub_tag_filter_selector,
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
)

pytestmark = pytest.mark.tags_ui


def test_filter_tag_with_all_urls_filtered(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )
    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_in_utub.id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    url_row_elements = page.locator(HPL.ROWS_URLS).all()
    for url_row in url_row_elements:
        assert not url_row.is_visible()


def test_filter_tag_with_some_urls_filtered(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )
    tag_id = tag_in_utub.id

    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        urls_tag_applied_to = len(utub_urls) - 2
        for idx in range(urls_tag_applied_to):
            utub_url = utub_urls[idx]
            new_url_tag = Utub_Url_Tags(
                utub_id=utub_user_created.id,
                utub_url_id=utub_url.id,
                utub_tag_id=tag_id,
            )
            db.session.add(new_url_tag)
        db.session.commit()

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )
    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(
        page=page, utub_tag_id=tag_id
    )
    assert len(displayed_urls) == urls_tag_applied_to


def test_filter_tag_with_no_urls_filtered(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )
    tag_id = tag_in_utub.id

    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        urls_tag_applied_to = len(utub_urls)
        for utub_url in utub_urls:
            new_url_tag = Utub_Url_Tags(
                utub_id=utub_user_created.id,
                utub_url_id=utub_url.id,
                utub_tag_id=tag_id,
            )
            db.session.add(new_url_tag)
        db.session.commit()

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )
    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(
        page=page, utub_tag_id=tag_id
    )
    assert len(displayed_urls) == urls_tag_applied_to


def test_filter_multiple_tags_with_some_urls_filtered(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    first_tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag1"
    )
    first_tag_id = first_tag_in_utub.id
    second_tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag2"
    )
    second_tag_id = second_tag_in_utub.id

    _, num_urls_for_first_tag, num_urls_for_second_tag = (
        add_two_tags_across_urls_in_utub(
            app, utub_user_created.id, first_tag_id, second_tag_id
        )
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    displayed_urls_for_first_tag = apply_tag_filter_by_id_and_get_shown_urls(
        page=page, utub_tag_id=first_tag_id
    )
    assert len(displayed_urls_for_first_tag) == num_urls_for_first_tag

    displayed_urls_for_second_tag = apply_tag_filter_by_id_and_get_shown_urls(
        page=page, utub_tag_id=second_tag_id
    )
    assert len(displayed_urls_for_second_tag) == num_urls_for_second_tag


def test_unselect_button_toggle_when_filter_selected(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    unselect_filters_btn = page.locator(HPL.BUTTON_UNSELECT_ALL).first
    # The unselect-all button uses the CSS class "red-icon-disabled" to signal
    # the "nothing selected" state — not the HTML disabled attribute — so
    # to_have_class is the correct assertion here, not to_be_disabled().
    expect(unselect_filters_btn).to_have_class(re.compile(r"red-icon-disabled"))

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_in_utub.id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UNSELECT_ALL)


def test_unselect_button_unselects_all_tags_when_clicked(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    with app.app_context():
        utub_tags: list[Utub_Tags] = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_created.id
        ).all()
        utub_tag_ids = [utub_tag.id for utub_tag in utub_tags]

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )
    wait_until_visible_css_selector(
        page=page, css_selector=f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}"
    )

    for utub_tag_id in utub_tag_ids:
        utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=utub_tag_id)
        wait_then_click_element(page=page, css_selector=utub_tag_filter)

    # All tags now selected — no unselected elements exist. Use to_have_count(0)
    # rather than wait_then_get_elements, which times out waiting for ≥1 visible match.
    expect(page.locator(f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}")).to_have_count(0)

    selected_tags = wait_then_get_elements(
        page=page, css_selector=f"{HPL.TAG_FILTERS}{HPL.SELECTED}"
    )
    assert len(selected_tags) == len(utub_tag_ids)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UNSELECT_ALL)

    # All tags now unselected — no selected elements exist.
    expect(page.locator(f"{HPL.TAG_FILTERS}{HPL.SELECTED}")).to_have_count(0)

    unselected_tags = wait_then_get_elements(
        page=page, css_selector=f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}"
    )
    assert len(unselected_tags) == len(utub_tag_ids)


def test_unfilter_tag_with_all_urls_filtered(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )
    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_in_utub.id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    url_row_elements = page.locator(HPL.ROWS_URLS).all()
    for url_row in url_row_elements:
        assert url_row.is_visible()


def test_unfilter_multiple_tags_with_some_urls_filtered(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    first_tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag1"
    )
    first_tag_id = first_tag_in_utub.id
    second_tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, "TestTag2"
    )
    second_tag_id = second_tag_in_utub.id

    num_utub_urls, num_urls_for_first_tag, num_urls_for_second_tag = (
        add_two_tags_across_urls_in_utub(
            app, utub_user_created.id, first_tag_id, second_tag_id
        )
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )

    apply_tag_filter_by_id_and_get_shown_urls(page=page, utub_tag_id=first_tag_id)
    filtered_urls = apply_tag_filter_by_id_and_get_shown_urls(
        page=page, utub_tag_id=second_tag_id
    )

    assert len(filtered_urls) == num_urls_for_second_tag

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=second_tag_id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    url_row_elements = page.locator(HPL.ROWS_URLS).all()
    assert (
        len([url_row for url_row in url_row_elements if url_row.is_visible()])
        == num_urls_for_first_tag
    )

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=first_tag_id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    url_row_elements = page.locator(HPL.ROWS_URLS).all()
    assert (
        len([url_row for url_row in url_row_elements if url_row.is_visible()])
        == num_utub_urls
    )


def test_filter_tag_attempt_with_tag_limit_reached(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )
    wait_until_visible_css_selector(
        page=page, css_selector=f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}"
    )

    with app.app_context():
        utub_tags: list[Utub_Tags] = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_created.id
        ).all()
        utub_tag_ids = [utub_tag.id for utub_tag in utub_tags]

    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )
    wait_until_visible_css_selector(
        page=page, css_selector=f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}"
    )

    for utub_tag_id in utub_tag_ids:
        utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=utub_tag_id)
        wait_then_click_element(page=page, css_selector=utub_tag_filter)

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_in_utub.id)

    utub_tag_badge = page.locator(utub_tag_filter).first
    # Tag filter badges are <div> elements — they cannot carry the HTML
    # disabled attribute.  The "limit reached" state is indicated by the
    # CSS class "disabled", so to_have_class is the correct check here.
    expect(utub_tag_badge).to_have_class(re.compile(r"(^|\s)disabled(\s|$)"))


def test_filter_tag_clickable_after_unclicking_from_tag_limit(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )
    wait_until_visible_css_selector(
        page=page, css_selector=f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}"
    )

    with app.app_context():
        utub_tags: list[Utub_Tags] = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_created.id
        ).all()
        utub_tag_ids = [utub_tag.id for utub_tag in utub_tags]

    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_user_created.id
    )
    wait_until_visible_css_selector(
        page=page, css_selector=f"{HPL.TAG_FILTERS}{HPL.UNSELECTED}"
    )

    last_utub_tag_id = -1
    for last_utub_tag_id in utub_tag_ids:
        utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=last_utub_tag_id)
        wait_then_click_element(page=page, css_selector=utub_tag_filter)

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=last_utub_tag_id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)

    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=tag_in_utub.id)

    page.locator(utub_tag_filter).first.click()


def test_filtered_url_hides_when_filter_tag_deleted(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )
    tag_id = tag_in_utub.id

    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        urls_tag_applied_to = len(utub_urls) - 2
        for idx in range(urls_tag_applied_to):
            utub_url = utub_urls[idx]
            new_url_tag = Utub_Url_Tags(
                utub_id=utub_user_created.id,
                utub_url_id=utub_url.id,
                utub_tag_id=tag_id,
            )
            db.session.add(new_url_tag)
        db.session.commit()
        url_id_to_hide = utub_urls[0].id

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_id_to_hide,
    )
    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(
        page=page, utub_tag_id=tag_id
    )
    assert len(displayed_urls) == urls_tag_applied_to

    selected_url_selector = get_css_selector_for_url_by_id(url_id=url_id_to_hide)
    init_vis, init_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=tag_id
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=tag_id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )
    delete_tag_button.click()

    wait_until_hidden(page=page, css_selector=selected_url_selector)
    final_vis, final_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=tag_id
    )
    assert final_vis == init_vis - 1
    assert final_total == init_total - 1


def test_filtered_url_count_decrements_when_url_deleted(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )
    tag_id = tag_in_utub.id

    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        urls_tag_applied_to = len(utub_urls) - 2
        for idx in range(urls_tag_applied_to):
            utub_url = utub_urls[idx]
            new_url_tag = Utub_Url_Tags(
                utub_id=utub_user_created.id,
                utub_url_id=utub_url.id,
                utub_tag_id=tag_id,
            )
            db.session.add(new_url_tag)
        db.session.commit()
        url_id_to_hide = utub_urls[0].id

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_id_to_hide,
    )
    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(
        page=page, utub_tag_id=tag_id
    )
    assert len(displayed_urls) == urls_tag_applied_to

    selected_url_selector = get_css_selector_for_url_by_id(url_id=url_id_to_hide)
    init_vis, init_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=tag_id
    )

    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )
    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}"
    )
    wait_until_visible_css_selector(page=page, css_selector=ML.ELEMENT_MODAL)
    modal = wait_then_get_element(page=page, css_selector=HPL.BODY_MODAL)
    assert modal is not None

    url_elem_locator = page.locator(selected_url_selector)

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    wait_for_element_to_be_removed(page=page, locator=url_elem_locator)
    final_vis, final_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=tag_id
    )
    assert final_vis == init_vis - 1
    assert final_total == init_total - 1


def test_filtered_url_count_increments_for_another_tag_while_filtered_when_added(
    page: Page, create_test_urls, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    new_tag_str = "Another"
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    tag_in_utub = add_tag_to_utub_user_created(
        app, utub_user_created.id, user_id_for_test, UTS.TEST_TAG_NAME_1
    )
    tag_id = tag_in_utub.id

    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).all()
        urls_tag_applied_to = len(utub_urls) - 2
        for idx in range(urls_tag_applied_to):
            utub_url = utub_urls[idx]
            new_url_tag = Utub_Url_Tags(
                utub_id=utub_user_created.id,
                utub_url_id=utub_url.id,
                utub_tag_id=tag_id,
            )
            db.session.add(new_url_tag)
        db.session.commit()
        url_id_to_add_tag = utub_urls[0].id

        add_tag_to_utub_user_created(
            app=app,
            tag_string=new_tag_str,
            utub_id=utub_user_created.id,
            user_id=user_id_for_test,
        )

        new_tag = Utub_Tags.query.filter(Utub_Tags.tag_string == new_tag_str).first()
        new_tag_id = new_tag.id

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_id_to_add_tag,
    )
    displayed_urls = apply_tag_filter_by_id_and_get_shown_urls(
        page=page, utub_tag_id=tag_id
    )
    assert len(displayed_urls) == urls_tag_applied_to

    init_vis, init_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=new_tag_id
    )

    add_tag_to_url(page=page, selected_url_id=url_id_to_add_tag, tag_string=new_tag_str)
    btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_SUBMIT_CREATE}"
    wait_then_click_element(page=page, css_selector=btn_selector)

    wait_until_hidden(page=page, css_selector=btn_selector)

    final_vis, final_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=new_tag_id
    )
    assert final_vis == init_vis + 1
    assert final_total == init_total + 1
