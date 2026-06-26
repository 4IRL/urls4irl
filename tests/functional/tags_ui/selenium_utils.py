from typing import Tuple
from flask import Flask
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.selenium_utils import (
    clear_then_send_keys,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.assert_utils import assert_delete_utub_tag_modal_shown


def open_tag_combobox(browser: WebDriver, url_id: int) -> None:
    """
    Opens the per-URL tag combobox by clicking the Add Tag button, then waits for
    the combobox text input to be visible before any keys are sent (readiness
    wait, hardening the root cause of focus/send_keys races).

    When the URL is already at the tag cap, ``showTagCombobox`` disables the input
    on open, and a disabled input can never become ``document.activeElement`` — so
    the focus wait is skipped for the at-limit case rather than timing out.
    """
    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_id}']"

    open_combobox_selector = f"{url_selector} {HPL.BUTTON_TAG_CREATE}"
    wait_then_click_element(browser, open_combobox_selector, time=3)

    combobox_input_selector = f"{url_selector} {HPL.INPUT_TAG_COMBOBOX}"
    wait_until_visible_css_selector(browser, combobox_input_selector, timeout=3)

    combobox_input = browser.find_element(By.CSS_SELECTOR, combobox_input_selector)
    if combobox_input.is_enabled():
        wait_until_in_focus(browser, combobox_input_selector, timeout=3)


def type_in_tag_combobox(browser: WebDriver, text: str) -> WebElement:
    """
    Types into the currently-open combobox input on the selected URL. Clicking an
    option to stage a chip moves focus off the input, so this clicks the input
    first to deterministically restore focus before sending keys (the keydown
    filter handler must receive the keys on a focused input).
    """
    combobox_input_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_COMBOBOX}"
    wait_then_click_element(browser, combobox_input_selector, time=3)
    wait_until_in_focus(browser, combobox_input_selector, timeout=3)
    combobox_input = browser.find_element(By.CSS_SELECTOR, combobox_input_selector)
    assert combobox_input.is_displayed()
    clear_then_send_keys(combobox_input, text)
    return combobox_input


def _count_staged_chips(browser: WebDriver) -> int:
    chip_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_STAGED_CHIP}"
    return len(browser.find_elements(By.CSS_SELECTOR, chip_selector))


def _wait_for_staged_chip_count(browser: WebDriver, expected_count: int) -> None:
    """
    Confirms a chip was staged by waiting for the chip count to reach
    `expected_count`. Uses a count delta rather than a `[data-staged-tag-string]`
    attribute selector so it is robust for any tag text (including values with
    quotes/HTML that would form an invalid CSS selector).
    """
    WebDriverWait(browser, 3).until(
        lambda _: _count_staged_chips(browser) == expected_count
    )


def _click_matching_option_label(
    browser: WebDriver, options_selector: str, target_text: str
) -> bool:
    """
    Re-finds the option whose label text matches `target_text` and clicks it. Done
    atomically (find + click in one call) so the 200ms debounce re-render of the
    listbox between a separate find and click cannot make the element stale.
    Returns False (so the WebDriverWait poll retries) if the option is not yet
    present or goes stale mid-click.
    """
    try:
        options = browser.find_elements(By.CSS_SELECTOR, options_selector)
        matching_option = next(
            (
                option
                for option in options
                if option.text.strip() == target_text.strip()
            ),
            None,
        )
        if matching_option is None or not matching_option.is_displayed():
            return False
        matching_option.click()
        return True
    except StaleElementReferenceException:
        return False


def stage_tag_suggestion(browser: WebDriver, tag_text: str) -> None:
    """
    Types `tag_text` to filter the existing-tag suggestions, then stages the
    suggestion whose label matches exactly (an existing UTub tag becomes a chip).
    The debounced listbox re-render is tolerated via an atomic find-and-click that
    retries on a stale reference.
    """
    chips_before = _count_staged_chips(browser)
    type_in_tag_combobox(browser, tag_text)

    options_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.TAG_COMBOBOX_OPTION} .urlTagOptionLabel"
    )
    wait_then_get_element(browser, options_selector, time=3)
    WebDriverWait(browser, 3).until(
        lambda _: _click_matching_option_label(browser, options_selector, tag_text)
    )
    _wait_for_staged_chip_count(browser, chips_before + 1)


def stage_new_tag(browser: WebDriver, text: str) -> None:
    """
    Types `text` and stages it via the "Create tag" option (a brand-new tag that
    does not yet exist in the UTub becomes a chip).
    """
    chips_before = _count_staged_chips(browser)
    type_in_tag_combobox(browser, text)

    create_new_label_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.TAG_COMBOBOX_CREATE_NEW} .urlTagOptionLabel"
    )
    wait_then_click_element(browser, create_new_label_selector, time=3)
    _wait_for_staged_chip_count(browser, chips_before + 1)


def submit_staged_tags(browser: WebDriver) -> None:
    """
    Clicks the combobox batch-submit button to apply all currently-staged chips.
    """
    submit_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAGS_SUBMIT_BATCH}"
    wait_then_click_element(browser, submit_selector, time=3)


def add_tag_to_url(browser: WebDriver, selected_url_id: int, tag_string: str) -> None:
    """
    Setup helper for sibling tags_ui suites: opens the combobox on the selected
    URL and stages a single tag string as a chip, leaving it ready to submit (the
    caller clicks the submit button). Stages via the auto-activated option (an
    existing-tag suggestion or the "Create tag" option) by typing then pressing
    ENTER, so it works for both fresh and existing tag strings.
    """
    open_tag_combobox(browser, selected_url_id)
    combobox_input = type_in_tag_combobox(browser, tag_string)

    # An option (suggestion or create-new) auto-activates once a non-empty query
    # is typed; ENTER stages the active option as a chip.
    combobox_input.send_keys(Keys.ENTER)


def open_url_tag_input(browser: WebDriver, selected_url_id: int):
    """Backwards-compatible alias retained for sibling suites; opens the combobox."""
    open_tag_combobox(browser, selected_url_id)


def get_delete_tag_button_on_hover(browser: WebDriver, tag_badge_selector: str):
    """
    Args:
        WebDriver open to a selected URL
        Tag badge element to remove from the selected URL

    Returns:
        Boolean confirmation of successful deletion of tag
        WebDriver handoff to member tests
    """
    tag_badge = browser.find_element(By.CSS_SELECTOR, tag_badge_selector)

    actions = ActionChains(browser)

    actions.move_to_element(tag_badge)

    # Pause to make sure deleteTag button is visible
    actions.pause(3).perform()

    actions.move_to_element(tag_badge).pause(2).perform()

    return tag_badge.find_element(By.CSS_SELECTOR, HPL.BUTTON_TAG_DELETE)


def get_tag_badge_selector_on_selected_url_by_tag_id(url_tag_id: int) -> str:
    return f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}[{HPL.TAG_BADGE_ID_ATTRIB}='{url_tag_id}']"


def get_utub_tag_filter_selector(utub_tag_id: int) -> str:
    return f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{utub_tag_id}']"


def apply_tag_filter_based_on_id(browser: WebDriver, utub_tag_id: int):
    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id)
    wait_then_click_element(browser, utub_tag_filter, time=3)


def apply_tag_filter_by_id_and_get_shown_urls(
    browser: WebDriver, utub_tag_id: int
) -> list[WebElement]:
    apply_tag_filter_based_on_id(browser, utub_tag_id)
    url_row_elements = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    return [url_row for url_row in url_row_elements if url_row.is_displayed()]


def get_visible_urls_and_urls_with_tag_text_by_tag_id(
    browser: WebDriver, tag_id: int
) -> Tuple[int, int]:
    """
    Extracts the visible URLs and total count of URLs that have a specific tag from the Tag Deck associated with the tag filter based on the tag ID.
    """
    utub_tag_selector = (
        f'{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}="{tag_id}"] {HPL.TAG_COUNT}'
    )
    tag_filter_count_elem = wait_then_get_element(browser, utub_tag_selector)
    assert tag_filter_count_elem
    visible, total = tag_filter_count_elem.text.split(" / ")
    return int(visible), int(total)


def click_open_update_utub_tags_btn(driver: WebDriver):
    assert_visible_css_selector(
        driver, css_selector=HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS
    )
    assert_visible_css_selector(driver, css_selector=HPL.UTUB_TAG_COUNT_WRAP)
    assert_visible_css_selector(driver, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN)
    assert_not_visible_css_selector(driver, css_selector=HPL.UTUB_TAG_MENU_WRAP)
    assert_not_visible_css_selector(
        driver, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )
    assert_not_visible_css_selector(driver, css_selector=HPL.BUTTON_UTUB_TAG_DELETE)
    assert_not_visible_css_selector(
        driver, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_CLOSE
    )

    wait_then_click_element(driver, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN)

    assert_visible_css_selector(driver, css_selector=HPL.UTUB_TAG_MENU_WRAP)
    assert_visible_css_selector(
        driver, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )
    assert_not_visible_css_selector(driver, css_selector=HPL.UTUB_TAG_COUNT_WRAP)
    assert_not_visible_css_selector(
        driver, css_selector=HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS
    )
    assert_not_visible_css_selector(
        driver, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN
    )
    assert_visible_css_selector(driver, css_selector=HPL.BUTTON_UTUB_TAG_DELETE)
    assert_visible_css_selector(
        driver, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_CLOSE
    )


def get_first_visible_tag_in_utub(browser: WebDriver) -> WebElement:
    tags = wait_then_get_elements(browser, HPL.TAG_FILTERS, time=3)
    first_tag = tags[0]
    assert first_tag.is_displayed()

    return first_tag


def get_all_utub_tags_ids_in_utub(browser: WebDriver) -> list[str]:
    return [
        tag_elem.get_attribute(f"{HPL.TAG_BADGE_ID_ATTRIB}") or ""
        for tag_elem in wait_then_get_elements(browser, HPL.TAG_FILTERS)
    ]


def open_delete_utub_tag_confirm_modal_for_tag(
    browser: WebDriver, tag_id: str, app: Flask
):
    click_open_update_utub_tags_btn(browser)
    delete_utub_tag_css_selector = f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}'] > {HPL.UTUB_TAG_MENU_WRAP} > {HPL.BUTTON_UTUB_TAG_DELETE}"

    assert_visible_css_selector(browser, delete_utub_tag_css_selector)
    delete_tag_btn = wait_then_get_element(
        browser, delete_utub_tag_css_selector, time=3
    )
    assert delete_tag_btn

    delete_tag_btn.send_keys(Keys.ENTER)
    assert_delete_utub_tag_modal_shown(browser, int(tag_id), app)


def delete_utub_tag_elem(browser: WebDriver, tag_id: str, app):
    open_delete_utub_tag_confirm_modal_for_tag(browser, tag_id, app)
    wait_then_click_element(browser, HPL.BUTTON_MODAL_SUBMIT)

    # Assert submit button is disabled immediately after click to prevent double-submit
    modal_submit_btn = browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_MODAL_SUBMIT)
    assert modal_submit_btn.get_property("disabled") is True

    delete_utub_tag_css_selector = (
        f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}']"
    )
    utub_tag_elem = browser.find_element(By.CSS_SELECTOR, delete_utub_tag_css_selector)
    wait_until_hidden(browser, HPL.HOME_MODAL)
    wait_for_element_to_be_removed(browser, utub_tag_elem)
