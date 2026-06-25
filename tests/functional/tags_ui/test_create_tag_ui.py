from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from backend.models.users import Users
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.constants import CONSTANTS, STRINGS, TAG_CONSTANTS
from tests.functional.assert_utils import (
    assert_login_with_username,
    assert_on_429_page,
    assert_tooltip_animates,
    assert_visited_403_on_invalid_csrf_and_reload,
)
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    count_urls_with_tag_applied_by_tag_string,
    get_tag_in_utub_by_tag_string,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    get_url_in_utub,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_select_utub_by_id_and_url_by_id
from tests.functional.tags_ui.selenium_utils import (
    get_visible_urls_and_urls_with_tag_text_by_tag_id,
    open_tag_combobox,
    stage_new_tag,
    stage_tag_suggestion,
    submit_staged_tags,
    type_in_tag_combobox,
)
from tests.functional.selenium_utils import (
    add_forced_rate_limit_header,
    invalidate_csrf_token_on_page,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.tags_ui

USER_ID_FOR_TEST = 1
EXISTING_TAG_ALPHA = "Alpha"
EXISTING_TAG_BETA = "Beta"
FRESH_TAG = "Fresh"
DUPLICATE_TAG = "Another"


def _badge_count_on_selected_url(browser: WebDriver) -> int:
    badge_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}"
    return len(browser.find_elements(By.CSS_SELECTOR, badge_selector))


def test_create_tag_btn_tooltip_animates(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a member's ability to see the tooltip animate when hovering over the add URL tag button.

    GIVEN a user in a UTub with URLs
    WHEN the user selects a URL, and hovers over the add URL tag button
    THEN ensure the tooltip for the add URL tag button is animated properly
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_user_created.id, url_in_utub.id
    )

    assert_tooltip_animates(
        browser=browser,
        parent_css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}",
        tooltip_parent_class=HPL.BUTTON_TAG_CREATE,
        tooltip_text=STRINGS.ADD_URL_TAG_TOOLTIP,
    )


def test_open_combobox_creator(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub creator's ability to open the tag combobox on a given URL.

    GIVEN a user is a UTub creator with the UTub selected
    WHEN the user selects a URL, and clicks the 'Add Tag' button
    THEN ensure the combobox is opened and focused, URL buttons are hidden, and
         the Add Tag button becomes the big cancel button.
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_user_created.id, url_in_utub.id
    )

    open_tag_combobox(browser, url_in_utub.id)
    combobox_input_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_COMBOBOX}"

    combobox_input = wait_then_get_element(browser, combobox_input_selector, time=3)
    assert combobox_input is not None
    assert combobox_input.is_displayed()
    assert browser.switch_to.active_element == browser.find_element(
        By.CSS_SELECTOR, combobox_input_selector
    )

    hidden_elements = (
        HPL.BUTTON_URL_ACCESS,
        HPL.BUTTON_URL_STRING_UPDATE,
        HPL.BUTTON_URL_DELETE,
    )
    for elem_selector in hidden_elements:
        hidden_btn = browser.find_element(
            By.CSS_SELECTOR, f"{HPL.ROW_SELECTED_URL} {elem_selector}"
        )
        assert not hidden_btn.is_displayed()

    add_tag_btn = browser.find_element(
        By.CSS_SELECTOR, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}"
    )
    assert add_tag_btn.is_displayed()
    classes = add_tag_btn.get_attribute("class")
    assert classes and HPL.BUTTON_BIG_TAG_CANCEL_CREATE.replace(".", "") in classes


def test_open_combobox_member(browser: WebDriver, create_test_urls, provide_app: Flask):
    """
    Tests a UTub member's ability to open the tag combobox on a given URL.

    GIVEN a user is a UTub member with the UTub selected and a URL they did not add
    WHEN the user clicks the 'Add Tag' button
    THEN ensure the combobox is opened and focused.
    """
    app = provide_app
    utub_user_did_not_create = get_utub_this_user_did_not_create(app, USER_ID_FOR_TEST)

    with app.app_context():
        utub_url_user_did_not_add: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_did_not_create.id,
            Utub_Urls.user_id != USER_ID_FOR_TEST,
        ).first()

    login_user_select_utub_by_id_and_url_by_id(
        app,
        browser,
        USER_ID_FOR_TEST,
        utub_user_did_not_create.id,
        utub_url_user_did_not_add.id,
    )

    open_tag_combobox(browser, utub_url_user_did_not_add.id)
    combobox_input_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_COMBOBOX}"

    combobox_input = wait_then_get_element(browser, combobox_input_selector, time=3)
    assert combobox_input is not None
    assert combobox_input.is_displayed()
    assert browser.switch_to.active_element == browser.find_element(
        By.CSS_SELECTOR, combobox_input_selector
    )

    hidden_btn = browser.find_element(
        By.CSS_SELECTOR, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )
    assert not hidden_btn.is_displayed()


def test_cancel_combobox_btn_creator(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub owner's ability to close the tag combobox via the cancel button.

    GIVEN a user is the UTub owner with the UTub and URL selected
    WHEN the user opens the combobox, then clicks the cancel button
    THEN ensure the combobox is hidden.
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_user_created.id, url_in_utub.id
    )

    open_tag_combobox(browser, url_in_utub.id)

    wait_then_click_element(browser, HPL.BUTTON_TAGS_CANCEL_BATCH, time=3)

    combobox_input = wait_until_hidden(browser, HPL.INPUT_TAG_COMBOBOX, timeout=3)
    assert combobox_input is not None
    assert not combobox_input.is_displayed()


def test_cancel_combobox_key_creator(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a UTub owner's ability to close the tag combobox via the Escape key.

    GIVEN a user is the UTub owner with the UTub and URL selected
    WHEN the user opens the combobox (no dropdown open), then presses Escape
    THEN ensure the combobox is hidden.
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_user_created.id, url_in_utub.id
    )

    open_tag_combobox(browser, url_in_utub.id)

    # The listbox is hidden on a freshly opened combobox, so a single Escape
    # cancels the whole combobox (the second-Escape branch).
    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    combobox_input = wait_until_hidden(browser, HPL.INPUT_TAG_COMBOBOX, timeout=3)
    assert combobox_input is not None
    assert not combobox_input.is_displayed()


def test_create_multiple_tags_batch(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests applying multiple tags to a URL in one batch via the combobox.

    GIVEN a user has access to a UTub with URLs and two existing tags not on the URL
    WHEN the user opens the combobox, stages two existing-tag chips and one
         brand-new chip, then submits
    THEN ensure 3 new badges appear on the URL, their texts are present, and the
         tag deck counters and #listTags reflect the new + existing tags.
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)

    add_tag_to_utub_user_created(app, utub_id, USER_ID_FOR_TEST, EXISTING_TAG_ALPHA)
    add_tag_to_utub_user_created(app, utub_id, USER_ID_FOR_TEST, EXISTING_TAG_BETA)

    with app.app_context():
        init_tag_count_on_url: int = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_utub.id,
        ).count()
        init_fresh_tag_count_in_utub: int = count_urls_with_tag_applied_by_tag_string(
            app, utub_id, FRESH_TAG
        )
    assert init_tag_count_on_url == 0
    assert init_fresh_tag_count_in_utub == 0

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_id, url_in_utub.id
    )

    assert _badge_count_on_selected_url(browser) == init_tag_count_on_url

    open_tag_combobox(browser, url_in_utub.id)
    stage_tag_suggestion(browser, EXISTING_TAG_ALPHA)
    stage_tag_suggestion(browser, EXISTING_TAG_BETA)
    stage_new_tag(browser, FRESH_TAG)

    staged_chips = browser.find_elements(
        By.CSS_SELECTOR, f"{HPL.ROW_SELECTED_URL} {HPL.TAG_STAGED_CHIP}"
    )
    assert len(staged_chips) == 3

    submit_staged_tags(browser)

    submit_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAGS_SUBMIT_BATCH}"
    wait_until_hidden(browser, submit_selector, timeout=3)

    badge_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}"
    badge_elems = wait_then_get_elements(browser, badge_selector, time=3)
    assert badge_elems
    assert len(badge_elems) == init_tag_count_on_url + 3
    assert all([badge.is_displayed() for badge in badge_elems])

    badge_text_elems_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGE_NAME_READ}"
    badge_text_elems: list[WebElement] = wait_then_get_elements(
        browser, badge_text_elems_selector, time=3
    )
    badge_texts = [elem.text for elem in badge_text_elems]
    for expected_tag in (EXISTING_TAG_ALPHA, EXISTING_TAG_BETA, FRESH_TAG):
        assert expected_tag in badge_texts

    # The brand-new tag must appear in the tag deck (#listTags) with count 1.
    fresh_tag = get_tag_in_utub_by_tag_string(app, utub_id, FRESH_TAG)
    fresh_tag_selector = (
        f'{HPL.LIST_TAGS} {HPL.TAG_FILTERS}[data-utub-tag-id="{fresh_tag.id}"]'
    )
    fresh_tag_elem = wait_then_get_element(browser, fresh_tag_selector, time=3)
    assert fresh_tag_elem is not None

    visible_urls, total_urls = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, fresh_tag.id
    )
    assert visible_urls == 1
    assert total_urls == init_fresh_tag_count_in_utub + 1

    # Existing tags' deck counters were incremented to 1 on this URL.
    alpha_tag = get_tag_in_utub_by_tag_string(app, utub_id, EXISTING_TAG_ALPHA)
    alpha_visible, alpha_total = get_visible_urls_and_urls_with_tag_text_by_tag_id(
        browser, alpha_tag.id
    )
    assert alpha_visible == 1
    assert alpha_total == 1


def test_create_tag_key_submits_batch(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests submitting a staged tag via the Enter key.

    GIVEN a user has access to a UTub with URLs
    WHEN the user stages a brand-new tag, clears the input, and presses Enter
    THEN ensure the tag is applied and a badge appears on the URL.
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)

    with app.app_context():
        init_tag_count_on_url: int = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_utub.id,
        ).count()
    assert init_tag_count_on_url == 0

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_id, url_in_utub.id
    )

    open_tag_combobox(browser, url_in_utub.id)
    stage_new_tag(browser, FRESH_TAG)

    # Staging via an option click moves focus off the input; click it to restore
    # focus so the Enter keydown reaches the combobox handler. Input is empty after
    # staging, so Enter with a staged chip and no active option submits the batch.
    combobox_input_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_COMBOBOX}"
    wait_then_click_element(browser, combobox_input_selector, time=3)
    browser.find_element(By.CSS_SELECTOR, combobox_input_selector).send_keys(Keys.ENTER)

    submit_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAGS_SUBMIT_BATCH}"
    wait_until_hidden(browser, submit_selector, timeout=3)

    badge_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}"
    badge_elems = wait_then_get_elements(browser, badge_selector, time=3)
    assert len(badge_elems) == init_tag_count_on_url + 1

    badge_text_elems_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGE_NAME_READ}"
    badge_text_elems = wait_then_get_elements(
        browser, badge_text_elems_selector, time=3
    )
    assert any([elem.text == FRESH_TAG for elem in badge_text_elems])


def test_create_tag_above_limit_blocks_staging(
    browser: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests that a URL already at the tag limit surfaces the limit message and the
    URL stays unchanged.

    GIVEN a user has access to a URL already at the maximum number of tags
    WHEN the user opens the combobox
    THEN ensure the limit-reached message is shown, the input is disabled, and the
         URL's badge count is unchanged.
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    with app.app_context():
        init_tag_count_on_url: int = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_created.id,
            Utub_Url_Tags.utub_url_id == url_in_utub.id,
        ).count()
    assert init_tag_count_on_url == TAG_CONSTANTS.MAX_URL_TAGS

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_user_created.id, url_in_utub.id
    )

    badge_count_before = _badge_count_on_selected_url(browser)
    assert badge_count_before == TAG_CONSTANTS.MAX_URL_TAGS

    open_tag_combobox(browser, url_in_utub.id)
    # Typing triggers the listbox render, which applies the limit-reached state.
    type_in_tag_combobox(browser, "x")

    message_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_COMBOBOX_MSG}"
    message_elem = wait_then_get_element(browser, message_selector, time=3)
    assert message_elem is not None
    expected_message = STRINGS.TAGS_LIMIT_REACHED.replace(
        "{max}", str(TAG_CONSTANTS.MAX_URL_TAGS)
    )
    assert message_elem.text == expected_message

    combobox_input = browser.find_element(
        By.CSS_SELECTOR, f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_COMBOBOX}"
    )
    assert not combobox_input.is_enabled()

    # No chip could be staged and the URL is unchanged.
    staged_chips = browser.find_elements(
        By.CSS_SELECTOR, f"{HPL.ROW_SELECTED_URL} {HPL.TAG_STAGED_CHIP}"
    )
    assert len(staged_chips) == 0
    assert _badge_count_on_selected_url(browser) == badge_count_before


def test_create_tag_duplicate_on_url_skipped(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests that staging a tag already applied to the URL is silently skipped.

    GIVEN a user has access to a URL that already has a tag applied
    WHEN the user stages that same tag again and submits
    THEN ensure no error is shown and no extra badge is added.
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)

    add_tag_to_utub_user_created(app, utub_id, USER_ID_FOR_TEST, DUPLICATE_TAG)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_id, url_in_utub.id
    )

    assert _badge_count_on_selected_url(browser) == 0

    # Apply the tag once.
    open_tag_combobox(browser, url_in_utub.id)
    stage_tag_suggestion(browser, DUPLICATE_TAG)
    submit_staged_tags(browser)
    submit_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAGS_SUBMIT_BATCH}"
    wait_until_hidden(browser, submit_selector, timeout=3)
    assert _badge_count_on_selected_url(browser) == 1

    # Reopen and try to stage the same tag — it is excluded from suggestions as
    # already-applied, so it cannot be re-staged and the badge count is unchanged.
    open_tag_combobox(browser, url_in_utub.id)
    type_in_tag_combobox(browser, DUPLICATE_TAG)

    options_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_COMBOBOX_OPTION}"
    options = browser.find_elements(By.CSS_SELECTOR, options_selector)
    assert all(option.text.strip() != DUPLICATE_TAG for option in options)

    staged_chips = browser.find_elements(
        By.CSS_SELECTOR, f"{HPL.ROW_SELECTED_URL} {HPL.TAG_STAGED_CHIP}"
    )
    assert len(staged_chips) == 0
    assert _badge_count_on_selected_url(browser) == 1


def test_create_tag_text_length_exceeded(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests that the combobox input truncates a tag value exceeding the char limit.

    GIVEN a user has access to a UTub with URLs
    WHEN the user types a tag value longer than the maximum length
    THEN ensure the input value is truncated to the maximum length.
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_user_created.id, url_in_utub.id
    )

    open_tag_combobox(browser, url_in_utub.id)
    type_in_tag_combobox(browser, "a" * (CONSTANTS.TAGS.MAX_TAG_LENGTH + 1))

    combobox_input = wait_then_get_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_COMBOBOX}", time=3
    )
    assert combobox_input is not None
    new_url_tag = combobox_input.get_attribute("value")
    assert new_url_tag is not None
    assert len(new_url_tag) == CONSTANTS.TAGS.MAX_TAG_LENGTH


def test_create_tag_text_sanitized(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests that a sanitized/HTML tag value cannot be staged.

    GIVEN a user has access to a UTub with URLs
    WHEN the user stages an HTML/script tag value and submits
    THEN ensure the backend sanitizer rejects it: an inline error is shown and no
         badge is applied to the URL.
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_user_created.id, url_in_utub.id
    )

    assert _badge_count_on_selected_url(browser) == 0

    open_tag_combobox(browser, url_in_utub.id)
    # The combobox does not sanitize client-side, so the raw string stages; the
    # backend rejects it on submit.
    stage_new_tag(browser, '<img src="evl.jpg">')
    submit_staged_tags(browser)

    message_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_COMBOBOX_MSG}"
    message_elem = wait_then_get_element(browser, message_selector, time=3)
    assert message_elem is not None
    assert message_elem.text

    assert _badge_count_on_selected_url(browser) == 0


def test_create_tag_rate_limits(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests a user's ability to apply a tag when they are rate limited.

    GIVEN a user has access to UTubs with URLs and is rate limited
    WHEN the user stages a fresh tag and submits
    THEN ensure the 429 error page is shown.
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_user_created.id, url_in_utub.id
    )

    open_tag_combobox(browser, url_in_utub.id)
    stage_new_tag(browser, FRESH_TAG)

    add_forced_rate_limit_header(browser)
    submit_staged_tags(browser)

    assert_on_429_page(browser)


def test_create_tag_invalid_csrf_token(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Tests the site error response to applying a tag with an invalid CSRF token.

    GIVEN a user has access to UTubs with URLs
    WHEN the user stages a tag and submits with an invalid CSRF token
    THEN ensure the 403 page is shown then reloads to the logged-in home page.
    """
    app = provide_app
    with app.app_context():
        user: Users = Users.query.get(USER_ID_FOR_TEST)
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    url_in_utub = get_url_in_utub(app, utub_user_created.id)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_user_created.id, url_in_utub.id
    )

    open_tag_combobox(browser, url_in_utub.id)
    stage_new_tag(browser, FRESH_TAG)

    invalidate_csrf_token_on_page(browser)
    submit_staged_tags(browser)

    assert_visited_403_on_invalid_csrf_and_reload(browser)

    # Page reloads after user clicks button in CSRF 403 error page
    wait_then_get_element(browser, HPL.ROW_SELECTED_URL, time=3)
    assert_login_with_username(browser, user.username)


def test_card_stays_selected_during_combobox_interaction(
    browser: WebDriver, create_test_urls, provide_app: Flask
):
    """
    Card-stays-selected regression (DD-5).

    GIVEN a user has access to a UTub with URLs and one existing tag
    WHEN the user opens the combobox and clicks inside the listbox, on a staged
         chip, then the cancel button
    THEN ensure the URL card retains urlSelected=true after each click (interacting
         with combobox elements never deselects the card).
    """
    app = provide_app
    utub_user_created = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)

    add_tag_to_utub_user_created(app, utub_id, USER_ID_FOR_TEST, EXISTING_TAG_ALPHA)

    login_user_select_utub_by_id_and_url_by_id(
        app, browser, USER_ID_FOR_TEST, utub_id, url_in_utub.id
    )

    def assert_card_still_selected() -> None:
        selected_url = browser.find_element(By.CSS_SELECTOR, HPL.ROW_SELECTED_URL)
        assert selected_url.get_attribute("urlselected") == "true"

    open_tag_combobox(browser, url_in_utub.id)
    assert_card_still_selected()

    # Click inside the listbox (after typing to populate it). Clicking a listbox
    # option stages it as a chip; either way the card must stay selected.
    type_in_tag_combobox(browser, EXISTING_TAG_ALPHA)
    listbox_selector = f"{HPL.ROW_SELECTED_URL} .urlTagListbox"
    wait_until_visible_css_selector(browser, listbox_selector, timeout=3)
    browser.find_element(By.CSS_SELECTOR, listbox_selector).click()
    assert_card_still_selected()

    # Ensure a staged chip exists, then click it — clicking a chip must not
    # deselect the card.
    chip_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_STAGED_CHIP}"
    if not browser.find_elements(By.CSS_SELECTOR, chip_selector):
        stage_new_tag(browser, FRESH_TAG)
    staged_chip = wait_then_get_element(browser, chip_selector, time=3)
    assert staged_chip is not None
    staged_chip.click()
    assert_card_still_selected()

    # Click the cancel button — the card must remain selected after close.
    wait_then_click_element(browser, HPL.BUTTON_TAGS_CANCEL_BATCH, time=3)
    wait_until_hidden(browser, HPL.INPUT_TAG_COMBOBOX, timeout=3)
    assert_card_still_selected()
