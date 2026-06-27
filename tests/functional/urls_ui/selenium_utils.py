from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from tests.functional.assert_utils import assert_visible_css_selector
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.selenium_utils import (
    clear_then_send_keys,
    open_update_url_title,
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_for_page_complete_and_dom_stable,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)


def open_url_search_box(browser: WebDriver):
    """Opens the URL search box via the toggle icon (mobile/tablet flow)."""
    wait_until_visible_css_selector(browser, HPL.URL_OPEN_SEARCH_ICON, timeout=3)
    assert_visible_css_selector(browser, HPL.URL_OPEN_SEARCH_ICON)

    wait_then_click_element(browser, HPL.URL_OPEN_SEARCH_ICON, time=3)
    wait_for_animation_to_end_check_top_lhs_corner(
        browser, HPL.URL_SEARCH_INPUT, timeout=3
    )
    wait_until_in_focus(browser, HPL.URL_SEARCH_INPUT)

    assert_visible_css_selector(browser, HPL.URL_CLOSE_SEARCH_ICON, time=3)
    url_search_elem = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=3)
    assert browser.switch_to.active_element == url_search_elem


def focus_url_search_input(browser: WebDriver):
    """Focuses the always-visible URL search input (desktop flow)."""
    search_wrap = browser.find_element(By.CSS_SELECTOR, HPL.URL_SEARCH_WRAP)
    WebDriverWait(browser, 10).until(
        lambda _: "search-ready" in (search_wrap.get_dom_attribute("class") or "")
    )
    wait_until_visible_css_selector(browser, HPL.URL_SEARCH_INPUT, timeout=10)
    search_input = wait_then_get_element(browser, HPL.URL_SEARCH_INPUT, time=10)
    assert search_input is not None
    search_input.click()
    wait_until_in_focus(browser, HPL.URL_SEARCH_INPUT)


def create_url(
    browser: WebDriver,
    url_title: str,
    url_string: str,
    tag_strings: list[str] | None = None,
):
    """
    Streamlines actions required to create a URL in the selected UTub.

    Args:
        WebDriver open to a selected UTub
        URL title
        URL
        Optional list of tag strings to stage as chips in the inline create-form
            combobox before submitting (URL + tags are created atomically).
    """
    fill_create_url_form(browser, url_title, url_string, tag_strings)

    # Submit
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE)


def fill_create_url_form(
    browser: WebDriver,
    url_title: str,
    url_string: str,
    tag_strings: list[str] | None = None,
):
    """
    Streamlines actions required to create a URL in the selected UTub.

    Args:
        WebDriver open to a selected UTub
        URL title
        URL
        Optional list of tag strings to stage as chips in the inline create-form
            combobox before the form is submitted.
    """

    # Select createURL button
    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)
    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    # Input new URL Title
    url_title_input_field = wait_then_get_element(browser, HPL.INPUT_URL_TITLE_CREATE)
    assert url_title_input_field is not None
    clear_then_send_keys(url_title_input_field, url_title)

    # Input new URL String
    url_string_input_field = wait_then_get_element(browser, HPL.INPUT_URL_STRING_CREATE)
    assert url_string_input_field is not None
    clear_then_send_keys(url_string_input_field, url_string)

    # Stage any requested tags as chips in the inline create-form combobox.
    for tag_string in tag_strings or []:
        stage_new_tag_in_create_form(browser, tag_string)


def _count_staged_chips_in_create_form(browser: WebDriver) -> int:
    return len(browser.find_elements(By.CSS_SELECTOR, HPL.CREATE_FORM_TAG_STAGED_CHIP))


def _wait_for_staged_chip_count_in_create_form(
    browser: WebDriver, expected_count: int
) -> None:
    """
    Confirms a chip was staged in the create form by waiting for the chip count
    to reach `expected_count`. A count delta (rather than a
    `[data-staged-tag-string]` attribute selector) is robust for any tag text.
    """
    WebDriverWait(browser, 3).until(
        lambda _: _count_staged_chips_in_create_form(browser) == expected_count
    )


def type_in_create_form_tag_combobox(browser: WebDriver, text: str) -> WebElement:
    """
    Types into the create-form combobox input (scoped to `#createURLWrap`).
    Clicking an option to stage a chip moves focus off the input, so this clicks
    the input first to deterministically restore focus before sending keys.
    """
    combobox_input_selector = HPL.CREATE_FORM_TAG_COMBOBOX_INPUT
    wait_then_click_element(browser, combobox_input_selector, time=3)
    wait_until_in_focus(browser, combobox_input_selector, timeout=3)
    combobox_input = browser.find_element(By.CSS_SELECTOR, combobox_input_selector)
    assert combobox_input.is_displayed()
    clear_then_send_keys(combobox_input, text)
    return combobox_input


def _click_matching_create_form_option(
    browser: WebDriver, options_selector: str, target_text: str
) -> bool:
    """
    Re-finds the option whose label text matches `target_text` and clicks it,
    atomically (find + click in one call) so the 200ms debounce re-render of the
    listbox cannot make the element stale. Returns False (so the WebDriverWait
    poll retries) if the option is not yet present or goes stale mid-click.
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


def stage_tag_suggestion_in_create_form(browser: WebDriver, tag_text: str) -> None:
    """
    Types `tag_text` to filter the existing-tag suggestions in the create-form
    combobox, then stages the suggestion whose label matches exactly (an existing
    UTub tag becomes a chip).
    """
    chips_before = _count_staged_chips_in_create_form(browser)
    type_in_create_form_tag_combobox(browser, tag_text)

    options_selector = (
        f"{HPL.CREATE_FORM_TAG_COMBOBOX_OPTION} {HPL.TAG_COMBOBOX_OPTION_LABEL}"
    )
    wait_then_get_element(browser, options_selector, time=3)
    WebDriverWait(browser, 3).until(
        lambda _: _click_matching_create_form_option(
            browser, options_selector, tag_text
        )
    )
    _wait_for_staged_chip_count_in_create_form(browser, chips_before + 1)


def stage_new_tag_in_create_form(browser: WebDriver, text: str) -> None:
    """
    Types `text` into the create-form combobox and stages it via the "Create tag"
    option (a brand-new tag that does not yet exist in the UTub becomes a chip).
    """
    chips_before = _count_staged_chips_in_create_form(browser)
    type_in_create_form_tag_combobox(browser, text)

    create_new_label_selector = (
        f"{HPL.CREATE_FORM_TAG_COMBOBOX_CREATE_NEW} " f"{HPL.TAG_COMBOBOX_OPTION_LABEL}"
    )
    wait_then_click_element(browser, create_new_label_selector, time=3)
    _wait_for_staged_chip_count_in_create_form(browser, chips_before + 1)


def update_url_string(browser: WebDriver, url_row: WebElement, url_string: str):
    """
    Streamlines actions required to update a URL in the selected URL.
    """
    wait_for_page_complete_and_dom_stable(browser)

    # Select editURL button
    btn_css_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}"
    wait_then_click_element(browser, btn_css_selector)

    # Input new URL string
    update_url_string_input_css_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_STRING_UPDATE}"
    )
    wait_until_visible_css_selector(browser, update_url_string_input_css_selector)

    update_url_string_input = wait_then_get_element(
        browser, update_url_string_input_css_selector
    )
    assert update_url_string_input
    clear_then_send_keys(update_url_string_input, url_string)


def update_url_title(browser: WebDriver, selected_url_row: WebElement, url_title: str):
    """
    Streamlines actions required to updated a URL in the selected URL.

    Args:
        WebDriver open to a selected URL
        New URL title

    Returns:
        Yields WebDriver to tests
    """
    open_update_url_title(browser, selected_url_row)

    # Input new URL Title
    url_title_input_field = selected_url_row.find_element(
        By.CSS_SELECTOR, HPL.INPUT_URL_TITLE_UPDATE
    )
    clear_then_send_keys(url_title_input_field, url_title)


class ClipboardMockHelper:
    def __init__(self, driver: WebDriver):
        self.driver: WebDriver = driver

    def setup_clipboard_mock(self):
        """Setup a comprehensive clipboard mock with logging and verification"""
        self.driver.execute_script("""
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
        """)

    def setup_clipboard_failure(self):
        """Setup clipboard to fail on write operations"""
        self.setup_clipboard_mock()
        self.driver.execute_script("""
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
        """)
        return True

    def wait_for_async_clipboard(self, timeout=5):
        """Wait for async clipboard operations to complete in headless"""
        self.driver.execute_script("""
            return new Promise(function(resolve) {
                setTimeout(resolve, 100);
            });
        """)

    def verify_mock_setup(self):
        """Verify the mock was set up correctly"""
        result = self.driver.execute_script("""
            return {
                hasMockClipboard: typeof window.mockClipboard !== 'undefined',
                hasNavigatorClipboard: typeof navigator.clipboard !== 'undefined',
                hasWriteText: typeof navigator.clipboard.writeText === 'function',
                hasReadText: typeof navigator.clipboard.readText === 'function',
                hasFailureConfig: typeof window.mockClipboard.failureConfig !== 'undefined',
                mockStats: window.mockClipboard ? window.mockClipboard.getStats() : null
            };
        """)
        return result["hasMockClipboard"] and result["hasNavigatorClipboard"]

    def test_mock_directly(self, test_text="Hello Mock Test"):
        """Test the mock directly to ensure it works"""
        # Test writeText
        write_result = self.driver.execute_script(
            """
            var testText = arguments[0];
            return navigator.clipboard.writeText(testText).then(function() {
                return {success: true, error: null};
            }).catch(function(err) {
                return {success: false, error: err.toString()};
            });
        """,
            test_text,
        )

        # Test readText
        read_result = self.driver.execute_script("""
            return navigator.clipboard.readText().then(function(text) {
                return {success: true, text: text, error: null};
            }).catch(function(err) {
                return {success: false, text: null, error: err.toString()};
            });
        """)
        return write_result and read_result and read_result.get("text") == test_text

    def get_mock_stats(self):
        """Get current mock statistics"""
        return self.driver.execute_script("return window.mockClipboard.getStats();")

    def get_clipboard_content(self):
        """Get current clipboard content from mock"""
        return self.driver.execute_script("return window.mockClipboard.data;")

    def reset_mock(self):
        """Reset the mock to initial state"""
        self.driver.execute_script("""
            window.mockClipboard.data = '';
            window.mockClipboard.writeCount = 0;
            window.mockClipboard.readCount = 0;
            window.mockClipboard.lastWriteTime = null;
            window.mockClipboard.lastReadTime = null;
            window.mockClipboard.errors = [];
        """)

    def cleanup_mock(self):
        """Restore original clipboard functionality"""
        self.driver.execute_script("""
            if (window.originalClipboard) {
                navigator.clipboard = window.originalClipboard;
            }
            if (window.originalExecCommand) {
                document.execCommand = window.originalExecCommand;
            }
        """)


def wait_for_url_search_filter_applied(browser: WebDriver, timeout: int = 3):
    """Wait until the URL search handler has updated the DOM.

    After typing into the search input, the handler (possibly debounced) sets a
    ``searchable`` attribute on every ``.urlRow[filterable='true']`` element. This
    function blocks until all such rows carry the attribute, confirming that the
    search filter cycle has completed.
    """

    def all_filterable_rows_have_searchable_attr(driver: WebDriver) -> bool:
        rows = driver.find_elements(By.CSS_SELECTOR, HPL.ROW_VISIBLE_URL)
        if not rows:
            return False
        return all(row.get_attribute("searchable") is not None for row in rows)

    WebDriverWait(browser, timeout).until(all_filterable_rows_have_searchable_attr)
