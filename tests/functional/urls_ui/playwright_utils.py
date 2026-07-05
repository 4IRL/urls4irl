import re

from playwright.sync_api import BrowserContext, Locator, Page, Route, expect

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_visible_css_selector
from tests.functional.playwright_utils import (
    clear_then_send_keys,
    dispatch_pointer_drag,
    open_update_url_title,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_page_complete_and_dom_stable,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)

# Drag distance (px) chosen to exceed the 35% commit threshold. At the 420px-wide
# page_mobile_portrait fixture, .urlRow (and its .urlRowSwipeReveal backing
# panel) render edge-to-edge at 420px, so the threshold is ~147px; 300px commits
# with a safe margin while staying within the row's [0, 420] drag range.
SWIPE_COMMIT_PX = 300

# Drag distance (px) chosen to stay well below the 35% commit threshold so the
# gesture snaps back to its prior state instead of committing. At the 420px-wide
# page_mobile_portrait fixture the threshold is ~147px (see SWIPE_COMMIT_PX),
# so 60px is comfortably sub-threshold and the row must snap back closed.
SWIPE_SNAP_BACK_PX = 60

# Non-zero per-step delay (ms) so the sub-threshold drag doesn't also commit via
# velocity (FLING_VELOCITY_PX_PER_MS = 0.5 px/ms). Spreading 60px over 6 steps at
# 40ms/step is ~0.25 px/ms — below the fling threshold — so only the (uncrossed)
# distance threshold governs, and the row correctly snaps back.
SWIPE_SNAP_BACK_STEP_DELAY_MS = 40


def _fulfill_with_stub_page(route: Route) -> None:
    route.fulfill(
        status=200,
        content_type="text/html",
        body="<html><body>mock external page</body></html>",
    )


def stub_mock_url_responses(*, context: BrowserContext) -> None:
    """Fulfill navigations to the fake mock URL domain (`https://www.u4i.test/N`)
    so popup navigations commit with their target URL. The `.test` TLD is
    unresolvable; without this stub the popup lands on a net-error page whose
    committed URL never matches the mock URL strings."""
    context.route(
        re.compile(r"^https://www\.u4i\.test/.*$"),
        _fulfill_with_stub_page,
    )


def install_window_open_spy(*, page: Page) -> None:
    """Wraps `window.open` so tests can assert the app requested a new tab
    (URL + target) even when headless Chromium refuses to materialize a page
    for the scheme — e.g. `mailto:` popups never fire Playwright's `page`
    event, unlike the Selenium window-handle behavior."""
    page.evaluate("""() => {
        window.__windowOpenCalls = [];
        const originalWindowOpen = window.open.bind(window);
        window.open = function (url, target, features) {
            window.__windowOpenCalls.push({
                url: String(url),
                target: target === undefined ? null : target,
            });
            return originalWindowOpen(url, target, features);
        };
    }""")


def wait_for_window_open_call(*, page: Page) -> list[dict]:
    """Blocks until the `install_window_open_spy` wrapper has recorded at
    least one `window.open` call, then returns the recorded calls."""
    page.wait_for_function("() => (window.__windowOpenCalls || []).length > 0")
    return page.evaluate("() => window.__windowOpenCalls")


def get_url_row_selector(*, utub_url_id: int) -> str:
    """Builds the CSS selector for the URL row with the given ``utuburlid``."""
    return f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']"


def open_url_search_box(*, page: Page) -> None:
    """Opens the URL search box via the toggle icon (mobile/tablet flow)."""
    wait_until_visible_css_selector(page=page, css_selector=HPL.URL_OPEN_SEARCH_ICON)
    assert_visible_css_selector(page=page, css_selector=HPL.URL_OPEN_SEARCH_ICON)

    wait_then_click_element(page=page, css_selector=HPL.URL_OPEN_SEARCH_ICON)
    wait_for_animation_to_end_check_top_lhs_corner(
        page=page, css_selector=HPL.URL_SEARCH_INPUT
    )
    wait_until_in_focus(page=page, css_selector=HPL.URL_SEARCH_INPUT)

    assert_visible_css_selector(page=page, css_selector=HPL.URL_CLOSE_SEARCH_ICON)


def focus_url_search_input(*, page: Page) -> None:
    """Focuses the always-visible URL search input (desktop flow)."""
    expect(page.locator(HPL.URL_SEARCH_WRAP).first).to_have_class(
        re.compile(r"(^|\s)search-ready(\s|$)")
    )
    wait_until_visible_css_selector(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input = wait_then_get_element(page=page, css_selector=HPL.URL_SEARCH_INPUT)
    search_input.click()
    wait_until_in_focus(page=page, css_selector=HPL.URL_SEARCH_INPUT)


def create_url(
    *,
    page: Page,
    url_title: str,
    url_string: str,
    tag_strings: list[str] | None = None,
) -> None:
    """
    Streamlines actions required to create a URL in the selected UTub.

    Args:
        page: Page open to a selected UTub
        url_title: URL title
        url_string: URL
        tag_strings: Optional list of tag strings to stage as chips in the
            inline create-form combobox before submitting (URL + tags are
            created atomically).
    """
    fill_create_url_form(
        page=page, url_title=url_title, url_string=url_string, tag_strings=tag_strings
    )

    wait_then_click_element(page=page, css_selector=HPL.BUTTON_URL_SUBMIT_CREATE)


def fill_create_url_form(
    *,
    page: Page,
    url_title: str,
    url_string: str,
    tag_strings: list[str] | None = None,
) -> None:
    """
    Streamlines actions required to fill the create-URL form in the selected UTub.

    Args:
        page: Page open to a selected UTub
        url_title: URL title
        url_string: URL
        tag_strings: Optional list of tag strings to stage as chips in the
            inline create-form combobox before the form is submitted.
    """
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_CORNER_URL_CREATE)
    url_creation_row = wait_then_get_element(
        page=page, css_selector=HPL.WRAP_URL_CREATE
    )
    expect(url_creation_row).to_be_visible()

    url_title_input_field = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_URL_TITLE_CREATE
    )
    clear_then_send_keys(locator=url_title_input_field, input_text=url_title)

    url_string_input_field = wait_then_get_element(
        page=page, css_selector=HPL.INPUT_URL_STRING_CREATE
    )
    clear_then_send_keys(locator=url_string_input_field, input_text=url_string)

    for tag_string in tag_strings or []:
        stage_new_tag_in_create_form(page=page, text=tag_string)


def _count_staged_chips_in_create_form(*, page: Page) -> int:
    return page.locator(HPL.CREATE_FORM_TAG_STAGED_CHIP).count()


def _wait_for_staged_chip_count_in_create_form(
    *, page: Page, expected_count: int
) -> None:
    """
    Confirms a chip was staged in the create form by waiting for the chip count
    to reach `expected_count`. A count delta (rather than a
    `[data-staged-tag-string]` attribute selector) is robust for any tag text.
    """
    expect(page.locator(HPL.CREATE_FORM_TAG_STAGED_CHIP)).to_have_count(expected_count)


def type_in_create_form_tag_combobox(*, page: Page, text: str) -> Locator:
    """
    Types into the create-form combobox input (scoped to `#createURLWrap`).
    Clicking an option to stage a chip moves focus off the input, so this clicks
    the input first to deterministically restore focus before sending keys.
    """
    combobox_input_selector = HPL.CREATE_FORM_TAG_COMBOBOX_INPUT
    wait_then_click_element(page=page, css_selector=combobox_input_selector)
    wait_until_in_focus(page=page, css_selector=combobox_input_selector)
    combobox_input = page.locator(combobox_input_selector).first
    expect(combobox_input).to_be_visible()
    clear_then_send_keys(locator=combobox_input, input_text=text)
    return combobox_input


def stage_tag_suggestion_in_create_form(*, page: Page, tag_text: str) -> None:
    """
    Types `tag_text` to filter the existing-tag suggestions in the create-form
    combobox, then stages the suggestion whose label matches exactly (an existing
    UTub tag becomes a chip). The find + click happens atomically inside the
    browser so the 200ms debounce re-render of the listbox cannot invalidate the
    matched option between finding and clicking it.
    """
    chips_before = _count_staged_chips_in_create_form(page=page)
    type_in_create_form_tag_combobox(page=page, text=tag_text)

    options_selector = (
        f"{HPL.CREATE_FORM_TAG_COMBOBOX_OPTION} {HPL.TAG_COMBOBOX_OPTION_LABEL}"
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
    _wait_for_staged_chip_count_in_create_form(
        page=page, expected_count=chips_before + 1
    )


def stage_new_tag_in_create_form(*, page: Page, text: str) -> None:
    """
    Types `text` into the create-form combobox and stages it via the "Create tag"
    option (a brand-new tag that does not yet exist in the UTub becomes a chip).
    """
    chips_before = _count_staged_chips_in_create_form(page=page)
    type_in_create_form_tag_combobox(page=page, text=text)

    create_new_label_selector = (
        f"{HPL.CREATE_FORM_TAG_COMBOBOX_CREATE_NEW} {HPL.TAG_COMBOBOX_OPTION_LABEL}"
    )
    wait_then_click_element(page=page, css_selector=create_new_label_selector)
    _wait_for_staged_chip_count_in_create_form(
        page=page, expected_count=chips_before + 1
    )


def update_url_string(*, page: Page, url_string: str) -> None:
    """
    Streamlines actions required to update the selected URL's string.
    """
    wait_for_page_complete_and_dom_stable(page=page)

    btn_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}"
    wait_then_click_element(page=page, css_selector=btn_css_selector)

    update_url_string_input_css_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}"
    )
    wait_until_visible_css_selector(
        page=page, css_selector=update_url_string_input_css_selector
    )

    update_url_string_input = wait_then_get_element(
        page=page, css_selector=update_url_string_input_css_selector
    )
    clear_then_send_keys(locator=update_url_string_input, input_text=url_string)


def update_url_title(*, page: Page, selected_url_row: Locator, url_title: str) -> None:
    """
    Streamlines actions required to update the selected URL's title.
    """
    open_update_url_title(page=page, selected_url_row=selected_url_row)

    url_title_input_field = selected_url_row.locator(HPL.INPUT_URL_TITLE_UPDATE)
    clear_then_send_keys(locator=url_title_input_field, input_text=url_title)


class ClipboardMockHelper:
    """Injects a JS clipboard mock into the page so headless tests can observe
    and fail clipboard operations deterministically (Playwright port of the
    Selenium `execute_script` clipboard mock)."""

    def __init__(self, page: Page):
        self.page: Page = page

    def setup_clipboard_mock(self):
        """Setup a comprehensive clipboard mock with logging and verification"""
        self.page.evaluate("""() => {
            // Enhanced mock for headless environments
            window.mockClipboard = {
                data: '',
                writeCount: 0,
                readCount: 0,
                lastWriteTime: null,
                lastReadTime: null,
                errors: [],
                isHeadless: true,
                // Failure simulation configuration
                failureConfig: {
                    writeText: {
                        shouldFail: false,
                        failureType: 'generic', // 'generic', 'permission', 'network', 'timeout'
                        failureRate: 0, // 0-1, probability of failure
                        failureDelay: 0, // delay before failure in ms
                        customError: null
                    },
                    readText: {
                        shouldFail: false,
                        failureType: 'generic',
                        failureRate: 0,
                        failureDelay: 0,
                        customError: null
                    },
                    execCommand: {
                        shouldFail: false,
                        failureRate: 0
                    }
                },
                // Helper to generate appropriate error based on failure type
                generateError: function(failureType, operation) {
                    const errorMessages = {
                        generic: `Failed to ${operation} clipboard data`,
                        permission: 'Document is not focused',
                        network: 'Network error during clipboard operation',
                        timeout: 'Clipboard operation timed out',
                        security: 'Clipboard access denied due to security policy'
                    };
                    const errorName = {
                        generic: 'Error',
                        permission: 'NotAllowedError',
                        network: 'NetworkError',
                        timeout: 'TimeoutError',
                        security: 'SecurityError'
                    };
                    const error = new Error(errorMessages[failureType] || errorMessages.generic);
                    error.name = errorName[failureType] || errorName.generic;
                    return error;
                },
                // Check if operation should fail based on configuration
                shouldOperationFail: function(operation) {
                    const config = this.failureConfig[operation];
                    if (!config) return false;
                    if (config.shouldFail) return true;
                    if (config.failureRate > 0 && Math.random() < config.failureRate) return true;
                    return false;
                },
                writeText: function(text) {
                    console.log('Mock clipboard writeText called with:', text);
                    const self = this;
                    return new Promise(function(resolve, reject) {
                        const config = self.failureConfig.writeText;
                        const delay = Math.max(config.failureDelay, 1);
                        setTimeout(function() {
                            if (self.shouldOperationFail('writeText')) {
                                const error = config.customError ||
                                            self.generateError(config.failureType, 'write to');
                                self.errors.push({
                                    operation: 'writeText',
                                    error: error.message,
                                    timestamp: Date.now(),
                                    data: text
                                });
                                console.error('Mock clipboard writeText failed:', error.message);
                                reject(error);
                            } else {
                                self.data = text;
                                self.writeCount++;
                                self.lastWriteTime = Date.now();
                                console.log('Mock clipboard writeText succeeded');
                                resolve();
                            }
                        }, delay);
                    });
                },
                readText: function() {
                    console.log('Mock clipboard readText called, current data:', this.data);
                    const self = this;
                    return new Promise(function(resolve, reject) {
                        const config = self.failureConfig.readText;
                        const delay = Math.max(config.failureDelay, 1);
                        setTimeout(function() {
                            if (self.shouldOperationFail('readText')) {
                                const error = config.customError ||
                                            self.generateError(config.failureType, 'read from');
                                self.errors.push({
                                    operation: 'readText',
                                    error: error.message,
                                    timestamp: Date.now()
                                });
                                console.error('Mock clipboard readText failed:', error.message);
                                reject(error);
                            } else {
                                self.readCount++;
                                self.lastReadTime = Date.now();
                                console.log('Mock clipboard readText succeeded, returning:', self.data);
                                resolve(self.data);
                            }
                        }, delay);
                    });
                },
                getStats: function() {
                    return {
                        data: this.data,
                        writeCount: this.writeCount,
                        readCount: this.readCount,
                        lastWriteTime: this.lastWriteTime,
                        lastReadTime: this.lastReadTime,
                        errors: this.errors,
                        isHeadless: this.isHeadless,
                        failureConfig: this.failureConfig
                    };
                },
                // Configuration methods
                setWriteFailure: function(options) {
                    Object.assign(this.failureConfig.writeText, options);
                },
                setReadFailure: function(options) {
                    Object.assign(this.failureConfig.readText, options);
                },
                setExecCommandFailure: function(options) {
                    Object.assign(this.failureConfig.execCommand, options);
                },
                clearFailures: function() {
                    this.failureConfig.writeText.shouldFail = false;
                    this.failureConfig.readText.shouldFail = false;
                    this.failureConfig.execCommand.shouldFail = false;
                    this.failureConfig.writeText.failureRate = 0;
                    this.failureConfig.readText.failureRate = 0;
                    this.failureConfig.execCommand.failureRate = 0;
                }
            };
            // Store original clipboard if it exists
            window.originalClipboard = navigator.clipboard;
            // In headless, navigator.clipboard might not exist at all
            if (typeof navigator.clipboard === 'undefined') {
                navigator.clipboard = {};
            }
            // Replace with our mock
            navigator.clipboard.writeText = window.mockClipboard.writeText.bind(window.mockClipboard);
            navigator.clipboard.readText = window.mockClipboard.readText.bind(window.mockClipboard);
            // Enhanced execCommand mock for headless
            window.originalExecCommand = document.execCommand;
            document.execCommand = function(command, showUI, value) {
                console.log('Mock execCommand called with:', command, showUI, value);
                if (command === 'copy') {
                    // Check if execCommand should fail
                    if (window.mockClipboard.shouldOperationFail('execCommand')) {
                        console.error('Mock execCommand failed');
                        window.mockClipboard.errors.push({
                            operation: 'execCommand',
                            error: 'execCommand copy failed',
                            timestamp: Date.now(),
                            command: command
                        });
                        return false;
                    }
                    var textToCopy = '';
                    // Try multiple methods to get text in headless
                    var selection = window.getSelection();
                    if (selection.rangeCount > 0) {
                        textToCopy = selection.toString();
                    }
                    // If no selection, check active element
                    if (!textToCopy && document.activeElement) {
                        if (document.activeElement.tagName === 'INPUT' ||
                            document.activeElement.tagName === 'TEXTAREA') {
                            textToCopy = document.activeElement.value;
                        } else if (document.activeElement.innerText) {
                            textToCopy = document.activeElement.innerText;
                        } else if (document.activeElement.textContent) {
                            textToCopy = document.activeElement.textContent;
                        }
                    }
                    // Store in mock
                    window.mockClipboard.data = textToCopy;
                    window.mockClipboard.writeCount++;
                    window.mockClipboard.lastWriteTime = Date.now();
                    console.log('Mock execCommand copied:', textToCopy);
                    return true;
                }
                return false;
            };
            // Additional headless-specific clipboard simulation
            window.simulateClipboardWrite = function(text) {
                window.mockClipboard.data = text;
                window.mockClipboard.writeCount++;
                window.mockClipboard.lastWriteTime = Date.now();
                console.log('Simulated clipboard write:', text);
                return true;
            };
            console.log('Enhanced headless clipboard mock setup complete');
            return true;
        }""")

    def setup_clipboard_failure(self):
        """Setup clipboard to fail on write operations"""
        self.setup_clipboard_mock()
        self.page.evaluate("""() => {
            window.mockClipboard.setWriteFailure({
                shouldFail: true,
                failureType: 'permission',
                failureRate: 0,
                failureDelay: 1,
                customError: null
            });
            window.mockClipboard.setExecCommandFailure({
                shouldFail: true,
                failureRate: 0
            });
        }""")
        return True

    def wait_for_async_clipboard(self):
        """Wait for async clipboard operations to complete in headless"""
        self.page.evaluate("""() => {
            return new Promise(function(resolve) {
                setTimeout(resolve, 100);
            });
        }""")

    def verify_mock_setup(self):
        """Verify the mock was set up correctly"""
        result = self.page.evaluate("""() => {
            return {
                hasMockClipboard: typeof window.mockClipboard !== 'undefined',
                hasNavigatorClipboard: typeof navigator.clipboard !== 'undefined',
                hasWriteText: typeof navigator.clipboard.writeText === 'function',
                hasReadText: typeof navigator.clipboard.readText === 'function',
                hasFailureConfig: typeof window.mockClipboard.failureConfig !== 'undefined',
                mockStats: window.mockClipboard ? window.mockClipboard.getStats() : null
            };
        }""")
        return result["hasMockClipboard"] and result["hasNavigatorClipboard"]

    def test_mock_directly(self, test_text="Hello Mock Test"):
        """Test the mock directly to ensure it works"""
        write_result = self.page.evaluate(
            """(testText) => {
            return navigator.clipboard.writeText(testText).then(function() {
                return {success: true, error: null};
            }).catch(function(err) {
                return {success: false, error: err.toString()};
            });
        }""",
            test_text,
        )

        read_result = self.page.evaluate("""() => {
            return navigator.clipboard.readText().then(function(text) {
                return {success: true, text: text, error: null};
            }).catch(function(err) {
                return {success: false, text: null, error: err.toString()};
            });
        }""")
        return write_result and read_result and read_result.get("text") == test_text

    def get_mock_stats(self):
        """Get current mock statistics"""
        return self.page.evaluate("() => window.mockClipboard.getStats()")

    def get_clipboard_content(self):
        """Get current clipboard content from mock"""
        return self.page.evaluate("() => window.mockClipboard.data")

    def reset_mock(self):
        """Reset the mock to initial state"""
        self.page.evaluate("""() => {
            window.mockClipboard.data = '';
            window.mockClipboard.writeCount = 0;
            window.mockClipboard.readCount = 0;
            window.mockClipboard.lastWriteTime = null;
            window.mockClipboard.lastReadTime = null;
            window.mockClipboard.errors = [];
        }""")

    def cleanup_mock(self):
        """Restore original clipboard functionality"""
        self.page.evaluate("""() => {
            if (window.originalClipboard) {
                navigator.clipboard = window.originalClipboard;
            }
            if (window.originalExecCommand) {
                document.execCommand = window.originalExecCommand;
            }
        }""")


def wait_for_url_search_filter_applied(*, page: Page) -> None:
    """Wait until the URL search handler has updated the DOM.

    After typing into the search input, the handler (possibly debounced)
    sets a ``searchable`` attribute on every visible filterable URL row;
    block until all such rows carry the attribute, confirming the search
    filter cycle has completed."""
    page.wait_for_function(
        """(visibleRowSelector) => {
            const rows = Array.from(document.querySelectorAll(visibleRowSelector));
            if (rows.length === 0) return false;
            return rows.every((row) => row.getAttribute("searchable") !== null);
        }""",
        arg=HPL.ROW_VISIBLE_URL,
    )


def swipe_url_card_delete(*, page: Page, url_row_selector: str) -> None:
    """
    Drags the given URL row leftward by ``SWIPE_COMMIT_PX`` to commit the
    swipe-to-delete gesture. The drag starts near the row's right edge and ends
    ``SWIPE_COMMIT_PX`` to the left of it, exceeding the snap threshold so the
    row commits (revealing the delete panel and opening the confirm modal)
    rather than snapping back closed.
    """
    row = page.locator(url_row_selector).first
    bounding_box = row.bounding_box()
    assert bounding_box is not None
    start_x = bounding_box["x"] + bounding_box["width"] - 5
    start_y = bounding_box["y"] + bounding_box["height"] / 2
    end_x = start_x - SWIPE_COMMIT_PX
    dispatch_pointer_drag(
        page=page,
        css_selector=url_row_selector,
        start_x=start_x,
        end_x=end_x,
        start_y=start_y,
        end_y=start_y,
    )


def swipe_url_card_below_threshold(*, page: Page, url_row_selector: str) -> None:
    """
    Drags the given URL row leftward by ``SWIPE_SNAP_BACK_PX`` — well below the
    35% commit threshold — so the row snaps back to its resting position rather
    than committing the swipe-to-delete gesture.
    """
    row = page.locator(url_row_selector).first
    bounding_box = row.bounding_box()
    assert bounding_box is not None
    start_x = bounding_box["x"] + bounding_box["width"] - 5
    start_y = bounding_box["y"] + bounding_box["height"] / 2
    end_x = start_x - SWIPE_SNAP_BACK_PX
    dispatch_pointer_drag(
        page=page,
        css_selector=url_row_selector,
        start_x=start_x,
        end_x=end_x,
        start_y=start_y,
        end_y=start_y,
        step_delay_ms=SWIPE_SNAP_BACK_STEP_DELAY_MS,
    )


def wait_until_url_card_swipe_committed(*, page: Page, timeout: int = 10) -> None:
    """
    Waits until a ``.urlRow`` carries the ``swipe-committed`` class, confirming
    the swipe-to-delete gesture has committed. Only one row can be mid-gesture at
    a time (the drag state is a single module-local object in ``swipe.ts``), so
    this checks across all rows rather than a specific selector.
    """
    page.wait_for_function(
        """(rowSelector) => {
            const rows = Array.from(document.querySelectorAll(rowSelector));
            return rows.some((row) => row.classList.contains("swipe-committed"));
        }""",
        arg=HPL.ROWS_URLS,
        timeout=timeout * 1000,
    )


def wait_until_url_card_swipe_reset(*, page: Page, timeout: int = 10) -> None:
    """
    Waits until no ``.urlRow`` carries the ``swipe-dragging`` or
    ``swipe-committed`` class, confirming the swipe gesture has fully reset
    (either snapped back below threshold, or its confirm modal was dismissed).
    """
    page.wait_for_function(
        """(rowSelector) => {
            const rows = Array.from(document.querySelectorAll(rowSelector));
            return rows.every(
                (row) =>
                    !row.classList.contains("swipe-dragging") &&
                    !row.classList.contains("swipe-committed")
            );
        }""",
        arg=HPL.ROWS_URLS,
        timeout=timeout * 1000,
    )
