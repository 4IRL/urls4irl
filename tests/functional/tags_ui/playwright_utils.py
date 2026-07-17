import re

from flask import Flask
from playwright.sync_api import Locator, Page, expect

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_visible_css_selector,
)
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    dispatch_pointer_drag,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_element_presence,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_then_get_element,
    wait_then_get_elements,
    wait_until_css_property,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.playwright_assert_utils import (
    assert_delete_utub_tag_modal_shown,
)

SWIPE_COMMIT_PX = 220
SWIPE_SNAP_BACK_PX = 60
SWIPE_SNAP_BACK_STEP_DELAY_MS = 40


def open_tag_combobox(*, page: Page, url_id: int) -> None:
    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{url_id}']"
    open_combobox_selector = f"{url_selector} {HPL.BUTTON_TAG_CREATE}"
    wait_then_click_element(page=page, css_selector=open_combobox_selector)
    combobox_input_selector = f"{url_selector} {HPL.INPUT_TAG_COMBOBOX}"
    wait_until_visible_css_selector(page=page, css_selector=combobox_input_selector)
    combobox_input = page.locator(combobox_input_selector).first
    if combobox_input.is_enabled():
        wait_until_in_focus(page=page, css_selector=combobox_input_selector)


def type_in_tag_combobox(*, page: Page, text: str) -> Locator:
    combobox_input_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_COMBOBOX}"
    wait_then_click_element(page=page, css_selector=combobox_input_selector)
    wait_until_in_focus(page=page, css_selector=combobox_input_selector)
    combobox_input = page.locator(combobox_input_selector).first
    expect(combobox_input).to_be_visible()
    clear_then_send_keys(locator=combobox_input, input_text=text)
    return combobox_input


def _count_staged_chips(*, page: Page) -> int:
    chip_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_STAGED_CHIP}"
    return page.locator(chip_selector).count()


def _wait_for_staged_chip_count(*, page: Page, expected_count: int) -> None:
    chip_selector = f"{HPL.ROW_SELECTED_URL} {HPL.TAG_STAGED_CHIP}"
    expect(page.locator(chip_selector)).to_have_count(expected_count)


def _click_matching_option_label(
    *, page: Page, options_selector: str, target_text: str
) -> bool:
    options = page.locator(options_selector).all()
    matching_option = next(
        (
            option
            for option in options
            if option.inner_text().strip() == target_text.strip()
        ),
        None,
    )
    if matching_option is None or not matching_option.is_visible():
        return False
    matching_option.click()
    return True


def stage_tag_suggestion(*, page: Page, tag_text: str) -> None:
    chips_before = _count_staged_chips(page=page)
    type_in_tag_combobox(page=page, text=tag_text)
    options_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.TAG_COMBOBOX_OPTION} .urlTagOptionLabel"
    )
    wait_then_get_element(page=page, css_selector=options_selector)
    page.wait_for_function(
        """({ selector, targetText }) => {
            const options = Array.from(document.querySelectorAll(selector));
            const match = options.find(
                (option) => option.textContent.trim() === targetText.trim()
            );
            if (!match || !match.offsetParent) return false;
            match.click();
            return true;
        }""",
        arg={"selector": options_selector, "targetText": tag_text},
    )
    _wait_for_staged_chip_count(page=page, expected_count=chips_before + 1)


def stage_new_tag(*, page: Page, text: str) -> None:
    chips_before = _count_staged_chips(page=page)
    type_in_tag_combobox(page=page, text=text)
    create_new_label_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.TAG_COMBOBOX_CREATE_NEW} .urlTagOptionLabel"
    )
    wait_then_click_element(page=page, css_selector=create_new_label_selector)
    _wait_for_staged_chip_count(page=page, expected_count=chips_before + 1)


def submit_staged_tags(*, page: Page) -> None:
    submit_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAGS_SUBMIT_BATCH}"
    wait_then_click_element(page=page, css_selector=submit_selector)


def add_tag_to_url(*, page: Page, selected_url_id: int, tag_string: str) -> None:
    open_tag_combobox(page=page, url_id=selected_url_id)
    combobox_input = type_in_tag_combobox(page=page, text=tag_string)
    combobox_input.press("Enter")


def open_url_tag_input(*, page: Page, selected_url_id: int) -> None:
    open_tag_combobox(page=page, url_id=selected_url_id)


def get_delete_tag_button_on_hover(
    *, page: Page, tag_badge_selector: str, assert_visible: bool = True
) -> Locator:
    tag_badge = page.locator(tag_badge_selector).first
    tag_badge.hover()
    delete_button = tag_badge.locator(HPL.BUTTON_TAG_DELETE)
    if assert_visible:
        expect(delete_button).to_be_visible()
    return delete_button


def get_tag_badge_selector_on_selected_url_by_tag_id(*, url_tag_id: int) -> str:
    return (
        f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}"
        f"[{HPL.TAG_BADGE_ID_ATTRIB}='{url_tag_id}']"
    )


def get_utub_tag_filter_selector(*, utub_tag_id: int) -> str:
    return f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{utub_tag_id}']"


def apply_tag_filter_based_on_id(*, page: Page, utub_tag_id: int) -> None:
    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id=utub_tag_id)
    wait_then_click_element(page=page, css_selector=utub_tag_filter)


def open_tag_name_filter(*, page: Page) -> Locator:
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_TAG_NAME_FILTER)
    wait_until_visible_css_selector(page=page, css_selector=HPL.TAG_SEARCH_INPUT)
    wait_until_in_focus(page=page, css_selector=HPL.TAG_SEARCH_INPUT)
    return wait_then_get_element(page=page, css_selector=HPL.TAG_SEARCH_INPUT)


def swipe_tag_sheet_open(*, page: Page) -> None:
    handle = page.locator(HPL.TAG_SHEET_HANDLE).first
    bounding_box = handle.bounding_box()
    assert bounding_box is not None
    start_y = bounding_box["y"] + bounding_box["height"] / 2
    end_y = start_y - SWIPE_COMMIT_PX
    dispatch_pointer_drag(
        page=page, css_selector=HPL.TAG_SHEET_HANDLE, start_y=start_y, end_y=end_y
    )


def swipe_tag_sheet_up_below_threshold(*, page: Page) -> None:
    handle = page.locator(HPL.TAG_SHEET_HANDLE).first
    bounding_box = handle.bounding_box()
    assert bounding_box is not None
    start_y = bounding_box["y"] + bounding_box["height"] / 2
    end_y = start_y - SWIPE_SNAP_BACK_PX
    dispatch_pointer_drag(
        page=page,
        css_selector=HPL.TAG_SHEET_HANDLE,
        start_y=start_y,
        end_y=end_y,
        step_delay_ms=SWIPE_SNAP_BACK_STEP_DELAY_MS,
    )


def swipe_tag_sheet_closed(*, page: Page) -> None:
    handle = page.locator(HPL.TAG_SHEET_HANDLE).first
    bounding_box = handle.bounding_box()
    assert bounding_box is not None
    start_y = bounding_box["y"] + bounding_box["height"] / 2
    end_y = start_y + SWIPE_COMMIT_PX
    dispatch_pointer_drag(
        page=page, css_selector=HPL.TAG_SHEET_HANDLE, start_y=start_y, end_y=end_y
    )


def wait_until_tag_sheet_open(*, page: Page, timeout: int = 10) -> None:
    expect(page.locator(HPL.TAG_SHEET).first).to_have_class(
        re.compile(rf"(^|\s){re.escape(HPL.TAG_SHEET_OPEN_CLASS)}(\s|$)"),
        timeout=timeout * 1000,
    )
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=HPL.TAG_SHEET
    )


def wait_until_tag_sheet_collapsed(*, page: Page, timeout: int = 10) -> None:
    expect(page.locator(HPL.TAG_SHEET).first).not_to_have_class(
        re.compile(rf"(^|\s){re.escape(HPL.TAG_SHEET_OPEN_CLASS)}(\s|$)"),
        timeout=timeout * 1000,
    )
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=HPL.TAG_SHEET
    )


def apply_tag_filter_by_id_and_get_shown_urls(
    *, page: Page, utub_tag_id: int
) -> list[Locator]:
    apply_tag_filter_based_on_id(page=page, utub_tag_id=utub_tag_id)
    url_row_locators = page.locator(HPL.ROWS_URLS).all()
    return [url_row for url_row in url_row_locators if url_row.is_visible()]


def get_visible_urls_and_urls_with_tag_text_by_tag_id(
    *, page: Page, tag_id: int
) -> tuple[int, int]:
    utub_tag_selector = (
        f'{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}="{tag_id}"] {HPL.TAG_COUNT}'
    )
    tag_filter_count_elem = wait_then_get_element(
        page=page, css_selector=utub_tag_selector
    )
    assert tag_filter_count_elem
    count_text = tag_filter_count_elem.inner_text()
    visible, total = count_text.split(" / ")
    return int(visible), int(total)


def click_open_update_utub_tags_btn(*, page: Page) -> None:
    assert_visible_css_selector(
        page=page, css_selector=HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS
    )
    assert_visible_css_selector(page=page, css_selector=HPL.UTUB_TAG_COUNT_WRAP)
    assert_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN
    )
    assert_not_visible_css_selector(page=page, css_selector=HPL.UTUB_TAG_MENU_WRAP)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )
    assert_not_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_TAG_DELETE)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_CLOSE
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN)
    assert_visible_css_selector(page=page, css_selector=HPL.UTUB_TAG_MENU_WRAP)
    assert_visible_css_selector(
        page=page, css_selector=HPL.WRAP_BUTTON_UPDATE_TAG_ALL_CLOSE
    )
    assert_not_visible_css_selector(page=page, css_selector=HPL.UTUB_TAG_COUNT_WRAP)
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS
    )
    assert_not_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN
    )
    assert_visible_css_selector(page=page, css_selector=HPL.BUTTON_UTUB_TAG_DELETE)
    assert_visible_css_selector(
        page=page, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_CLOSE
    )


def get_first_visible_tag_in_utub(*, page: Page) -> Locator:
    tags = wait_then_get_elements(page=page, css_selector=HPL.TAG_FILTERS)
    first_tag = tags[0]
    expect(first_tag).to_be_visible()
    return first_tag


def get_all_utub_tags_ids_in_utub(*, page: Page) -> list[str]:
    return [
        tag_locator.get_attribute(HPL.TAG_BADGE_ID_ATTRIB) or ""
        for tag_locator in wait_then_get_elements(
            page=page, css_selector=HPL.TAG_FILTERS
        )
    ]


def open_delete_utub_tag_confirm_modal_for_tag(
    *, page: Page, tag_id: str, app: Flask
) -> None:
    click_open_update_utub_tags_btn(page=page)
    delete_utub_tag_css_selector = (
        f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}']"
        f" > {HPL.UTUB_TAG_MENU_WRAP}"
        f" > {HPL.BUTTON_UTUB_TAG_DELETE}"
    )
    assert_visible_css_selector(page=page, css_selector=delete_utub_tag_css_selector)
    delete_tag_btn = wait_then_get_element(
        page=page, css_selector=delete_utub_tag_css_selector
    )
    assert delete_tag_btn
    delete_tag_btn.press("Enter")
    assert_delete_utub_tag_modal_shown(page=page, tag_id=int(tag_id), app=app)


def delete_utub_tag_elem(*, page: Page, tag_id: str, app: Flask) -> None:
    open_delete_utub_tag_confirm_modal_for_tag(page=page, tag_id=tag_id, app=app)
    # Wait for Bootstrap's show transition to complete before clicking submit.
    # Clicking mid-fade-in drops the click handler's modal.hide() call
    # (BS5 _isTransitioning guard), so the modal never becomes hidden.
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)
    expect(page.locator(HPL.BUTTON_MODAL_SUBMIT)).to_be_disabled()
    delete_utub_tag_css_selector = (
        f"{HPL.TAG_FILTERS}[{HPL.TAG_BADGE_ID_ATTRIB}='{tag_id}']"
    )
    utub_tag_locator = wait_for_element_presence(
        page=page, css_selector=delete_utub_tag_css_selector
    )
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_for_element_to_be_removed(page=page, locator=utub_tag_locator)
