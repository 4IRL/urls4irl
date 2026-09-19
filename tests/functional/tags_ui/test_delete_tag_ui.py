from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.models.users import Users
from backend.utils.constants import STRINGS
from tests.functional.db_utils import (
    get_tag_on_url_in_utub,
    get_url_in_utub,
    get_url_tag_id_and_tag_string_on_url_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_login_with_username,
    assert_no_page_errors,
    assert_on_429_page,
    assert_tooltip_animates,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.playwright_login_utils import (
    login_user_select_utub_by_id_and_url_by_id,
)
from tests.functional.playwright_utils import (
    add_forced_rate_limit_header,
    collect_page_errors,
    get_selected_url,
    invalidate_csrf_token_on_page,
    open_update_url_title,
    wait_for_element_to_be_removed,
    wait_for_selector_to_be_removed,
    wait_then_click_element,
    wait_until_css_property,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.playwright_utils import (
    get_delete_tag_button_on_hover,
    get_tag_badge_selector_on_selected_url_by_tag_id,
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
)

pytestmark = pytest.mark.tags_ui

# The dispose-during-fade throw is queued, not synchronous: Bootstrap's hide()
# schedules its teardown behind the 150ms fade, and TOOLTIP_DISPOSE_DELAY_MS
# (frontend/lib/tooltips.ts) defers the badge's dispose 200ms past the click.
# Both windows outlast the badge removal the test waits on, so the page-error
# assertion needs this settle or it would run before the race could fire. Not a
# flake pad -- it is the code-defined window the assertion has to outlast.
TOOLTIP_TEARDOWN_SETTLE_MS = 1000


def test_get_delete_tag_button_on_hover(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )

    expect(delete_tag_button).to_be_visible()


def test_hide_delete_tag_button_after_hover(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )

    expect(delete_tag_button).to_be_visible()

    url_title_selector = f"{HPL.ROW_SELECTED_URL} {HPL.URL_TITLE_READ}"
    page.locator(url_title_selector).first.hover()

    delete_tag_btn_selector = f"{tag_badge_selector} > {HPL.BUTTON_TAG_DELETE}"
    wait_until_css_property(
        page=page,
        css_selector=delete_tag_btn_selector,
        css_property="opacity",
        expected_value="0",
    )
    assert (
        page.locator(delete_tag_btn_selector).first.evaluate(
            "element => window.getComputedStyle(element).getPropertyValue('opacity')"
        )
        == "0"
    )


def test_delete_tag(page: Page, create_test_tags, provide_app: Flask):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    url_id = url_in_utub.id
    url_tag = get_tag_on_url_in_utub(app, utub_id, url_id)
    tag_id = url_tag.utub_tag_id

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_id,
        utub_url_id=url_id,
    )

    init_vis, init_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=tag_id
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )

    tag_badge_locator = page.locator(tag_badge_selector)
    delete_tag_button.click()

    wait_for_element_to_be_removed(page=page, locator=tag_badge_locator)

    assert page.locator(tag_badge_selector).count() == 0

    final_vis, final_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        page=page, tag_id=tag_id
    )
    assert final_vis == init_vis - 1
    assert final_total == init_total - 1


def test_delete_tag_rate_limits(page: Page, create_test_tags, provide_app: Flask):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    url_id = url_in_utub.id

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_id,
        utub_url_id=url_id,
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_id
    )
    # The delete button is revealed only while its tag badge is :hover-ed.
    # Register the forced rate-limit header BEFORE revealing the button so no
    # page work happens between the hover-reveal and the click — mirroring the
    # reliable happy-path test_delete_tag ordering. An intervening call could
    # drop the :hover state under CI load, hiding the button and timing the
    # click out. Re-hover immediately before clicking as a belt-and-suspenders
    # guard against a re-render dropping the hover between reveal and click.
    add_forced_rate_limit_header(page=page)
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )
    page.locator(tag_badge_selector).first.hover()
    delete_tag_button.click()

    assert_on_429_page(page=page)


def test_no_get_delete_tag_button_on_hover_update_url_title(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    open_update_url_title(page=page, selected_url_row=get_selected_url(page=page))

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector, assert_visible=False
    )
    assert not delete_tag_button.is_visible()


def test_no_get_delete_tag_button_on_hover_update_url_string(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    edit_url_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}"
    wait_then_click_element(page=page, css_selector=edit_url_selector)

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector, assert_visible=False
    )
    assert not delete_tag_button.is_visible()


def test_no_get_delete_tag_button_on_hover_add_tag(
    page: Page, create_test_tags, provide_app: Flask
):
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    add_tag_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}"
    wait_then_click_element(page=page, css_selector=add_tag_selector)

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector, assert_visible=False
    )
    assert not delete_tag_button.is_visible()


def test_delete_tag_invalid_csrf(page: Page, create_test_tags, provide_app: Flask):
    app = provide_app
    user_id_for_test = 1
    with app.app_context():
        user: Users = Users.query.get(user_id_for_test)

    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag = get_tag_on_url_in_utub(app, utub_user_created.id, url_in_utub.id)

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag.id
    )
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )

    invalidate_csrf_token_on_page(page=page)
    # invalidate_csrf_token_on_page runs a page.evaluate between the hover-reveal
    # and the click; under CI load that intervening call can drop the tag badge's
    # :hover state, collapsing the width:0/opacity:0 delete button and timing the
    # click out. Re-hover immediately before clicking — same guard as
    # test_delete_tag_rate_limits, which has the identical page.evaluate ordering.
    page.locator(tag_badge_selector).first.hover()
    delete_tag_button.click()

    assert_visited_403_on_invalid_csrf_and_reload(page=page)
    assert_login_with_username(page=page, username=user.username)

    assert page.locator(tag_badge_selector).count() == 0


def test_url_tag_btn_delete_tooltip_animates(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests the hover tooltip on a URL card's per-tag delete "x" button.

    GIVEN a user has selected a URL carrying a tag
    WHEN the user hovers the tag badge (the real reveal path for the "x") and
         then the "x" itself
    THEN ensure the tooltip animates in with the shared "Remove tag" copy, while
         the accessible name stays tag-specific so a card full of badges does not
         announce the same name repeatedly
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag_id, tag_string = get_url_tag_id_and_tag_string_on_url_in_utub(
        app, utub_user_created.id, url_in_utub.id
    )

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag_id
    )
    # The "x" is width: 0 / opacity: 0 until its .tagBadgeHoverable parent is
    # hovered — drive that real reveal path rather than force-showing it.
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )

    assert_tooltip_animates(
        page=page,
        parent_css_selector=f"{tag_badge_selector} {HPL.BUTTON_TAG_DELETE}",
        tooltip_parent_class=HPL.BUTTON_TAG_DELETE,
        tooltip_text=STRINGS.REMOVE_URL_TAG_TOOLTIP,
    )

    assert (
        delete_tag_button.get_attribute("aria-label")
        == f"{STRINGS.REMOVE_URL_TAG_TOOLTIP} {tag_string}"
    )


def test_delete_tag_while_btn_delete_tooltip_shown_raises_no_page_error(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    Tests that deleting a URL tag while its delete "x" tooltip is shown tears the
    badge down without throwing.

    The click handler hides the tooltip synchronously and the delete succeeds
    inside Bootstrap's 150ms fade, so a synchronous dispose would null the
    instance out from under the hide's queued callback, which then reads
    `_activeTrigger` and throws "Cannot convert undefined or null to object" --
    the exact failure disposeTooltipsWithinAfterHide() was introduced to fix.
    This is the live-browser counterpart to the fake-timer unit tests, which
    mock the Tooltip class and so cannot exercise that race at all.

    GIVEN a user has selected a URL carrying a tag and hovers that tag badge's
          delete "x" until its tooltip is shown
    WHEN the user clicks the "x" without moving the pointer off it
    THEN ensure the badge and its bubble are both removed and no uncaught page
         error fires
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)
    url_tag_id, _ = get_url_tag_id_and_tag_string_on_url_in_utub(
        app, utub_user_created.id, url_in_utub.id
    )

    login_user_select_utub_by_id_and_url_by_id(
        app=app,
        page=page,
        user_id=user_id_for_test,
        utub_id=utub_user_created.id,
        utub_url_id=url_in_utub.id,
    )

    # Registered before any interaction: the throw escapes to window.onerror from
    # inside a Bootstrap transition callback, not from the click handler driven
    # below, so only a pageerror listener can observe it.
    page_errors = collect_page_errors(page=page)

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag_id
    )
    # The "x" is width: 0 / opacity: 0 until its .tagBadgeHoverable parent is
    # hovered -- drive that real reveal path rather than force-showing it.
    delete_tag_button = get_delete_tag_button_on_hover(
        page=page, tag_badge_selector=tag_badge_selector
    )

    # The bubble has to be up before the click, or the hide -> success -> dispose
    # sequence this test guards never happens and the assertion is vacuous.
    # `.show` distinguishes a live bubble from a mid-fade one, which Playwright
    # still counts as visible until Bootstrap removes it.
    tooltip_selector = f"{HPL.BUTTON_TAG_DELETE}{HPL.TOOLTIP_SUFFIX}"
    delete_tag_button.hover()
    wait_until_visible_css_selector(
        page=page, css_selector=f"{tooltip_selector}{HPL.TOOLTIP_SHOWN_SUFFIX}"
    )

    tag_badge_locator = page.locator(tag_badge_selector)
    # Click the locator already under the pointer -- Playwright clicks the
    # element's center, so the pointer never leaves the "x" and the bubble is
    # still shown when the click handler hides it.
    delete_tag_button.click()

    # The real round trip: the badge only goes away on a 200 from the server.
    wait_for_element_to_be_removed(page=page, locator=tag_badge_locator)
    assert page.locator(tag_badge_selector).count() == 0
    # The bubble goes with it -- nothing is stranded over the card.
    wait_for_selector_to_be_removed(page=page, css_selector=tooltip_selector)

    page.wait_for_timeout(TOOLTIP_TEARDOWN_SETTLE_MS)

    assert_no_page_errors(page_errors=page_errors)
