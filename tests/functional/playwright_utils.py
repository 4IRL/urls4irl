from dataclasses import dataclass
from enum import Enum
import re
from urllib.parse import urlsplit

from flask import Flask
from playwright.sync_api import BrowserContext, Locator, Page, expect

from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import GenericPageLocator
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as MP
from tests.functional.login_utils import create_user_session_and_provide_session_id

# Baseline auto-retrying assertion timeout for all Playwright `expect()` calls.
# Matches the existing Selenium `wait_for_element_presence(timeout=10)` baseline
# under n=8 parallel load — a documented suite-wide baseline, not a per-test pad.
DEFAULT_EXPECT_TIMEOUT_MS = 10_000

expect.set_options(timeout=DEFAULT_EXPECT_TIMEOUT_MS)


@dataclass
class PageBundle:
    page: Page
    context: BrowserContext
    base_url: str


class Decks(Enum):
    UTUBS = HPL.UTUB_DECK
    MEMBERS = HPL.MEMBER_DECK
    TAGS = HPL.TAG_DECK
    URLS = HPL.URL_DECK


def wait_then_click_element(*, page: Page, css_selector: str) -> None:
    """Click the first element matching the selector, auto-waiting for
    actionability (visible, stable, enabled, not obscured)."""
    page.locator(css_selector).first.click()


def wait_then_get_element(*, page: Page, css_selector: str):
    """Return a locator for the first selector match after asserting it is
    visible (Playwright twin of the Selenium visibility-gated getter)."""
    locator = page.locator(css_selector).first
    expect(locator).to_be_visible()
    return locator


def wait_for_element_presence(*, page: Page, css_selector: str):
    """Return a locator for the first selector match after asserting DOM
    presence (attached), NOT visibility — e.g. links inside a collapsed
    navbar dropdown."""
    locator = page.locator(css_selector).first
    expect(locator).to_be_attached()
    return locator


def wait_then_get_elements(*, page: Page, css_selector: str) -> list:
    """Return per-element locators for every selector match after asserting
    at least the first match is visible (Playwright twin of the Selenium
    multi-element visibility-gated getter)."""
    locator = page.locator(css_selector)
    expect(locator.first).to_be_visible()
    return locator.all()


def wait_then_get_at_least_n_elements(
    *, page: Page, css_selector: str, minimum_count: int
) -> list:
    """Wait until at least ``minimum_count`` elements matching the selector
    are attached to the DOM, then return per-element locators for every
    match. Use when a known number of elements fill in asynchronously (e.g.
    one card per independent XHR) so the sample is only taken once the
    expected number has settled."""
    locator = page.locator(css_selector)
    expect(locator.nth(minimum_count - 1)).to_be_attached()
    return locator.all()


def clear_then_send_keys(*, locator, input_text: str) -> None:
    """Clear an input field then fill it with the provided text."""
    locator.fill("")
    locator.fill(input_text)


def wait_until_in_focus(*, page: Page, css_selector: str) -> None:
    expect(page.locator(css_selector)).to_be_focused()


def wait_until_visible_css_selector(*, page: Page, css_selector: str) -> None:
    expect(page.locator(css_selector).first).to_be_visible()


def wait_until_hidden(*, page: Page, css_selector: str) -> None:
    """Wait until the selector's first match is hidden. Passes when the
    element is invisible OR absent from the DOM (mirrors the Selenium
    invisibility semantics)."""
    expect(page.locator(css_selector).first).to_be_hidden()


def wait_for_element_to_be_removed(*, page: Page, locator: Locator) -> None:
    """Wait until the given locator matches nothing — the Playwright twin of
    Selenium's staleness wait (callers pass a uniquely-selecting locator)."""
    expect(locator).to_have_count(0)


def wait_for_selector_to_be_removed(*, page: Page, css_selector: str) -> None:
    """Wait until no element matching the selector remains in the DOM."""
    expect(page.locator(css_selector)).to_have_count(0)


def wait_for_class_to_be_removed(
    *, page: Page, css_selector: str, class_name: str
) -> None:
    expect(page.locator(css_selector).first).not_to_have_class(
        re.compile(rf"(^|\s){re.escape(class_name)}(\s|$)")
    )


def wait_for_element_with_text(
    *, page: Page, css_selector: str, expected_text: str
) -> None:
    """Wait for the first element matching the selector to contain the text."""
    expect(page.locator(css_selector).first).to_contain_text(expected_text)


def wait_for_any_element_with_text(
    *, page: Page, css_selector: str, expected_text: str
) -> Locator:
    """Wait for any element matching the selector to contain the text and
    return a locator narrowed to the matching element(s)."""
    matching = page.locator(css_selector).filter(has_text=expected_text)
    expect(matching.first).to_be_attached()
    return matching.first


# Modal
def wait_for_modal_ready(*, page: Page, modal_selector: str) -> Locator:
    """Wait for a Bootstrap modal to be fully shown and interactive.

    Bootstrap 5's Modal.hide() returns early while _isTransitioning is
    true, so clicking a close control mid-show silently no-ops. Block until
    Bootstrap reports the show animation has finished.
    """
    modal = page.locator(modal_selector)
    expect(modal).to_be_visible()
    expect(modal).to_have_class(re.compile(r"(^|\s)show(\s|$)"))
    page.wait_for_function(
        """(modalSelector) => {
            const modalElement = document.querySelector(modalSelector);
            if (!modalElement) return false;
            const instance = bootstrap.Modal.getInstance(modalElement);
            return !instance || instance._isTransitioning === false;
        }""",
        arg=modal_selector,
    )
    return modal


def wait_for_modal_hidden(*, page: Page, modal_selector: str) -> None:
    """Wait for a Bootstrap modal to be fully hidden (or removed)."""
    expect(page.locator(modal_selector)).to_be_hidden()


def dismiss_modal_with_click_out(
    *, page: Page, modal_selector: str = MP.ELEMENT_MODAL
) -> None:
    """Click 15px inside the top-left corner of the modal overlay — outside
    the dialog box — to dismiss the modal (twin of the Selenium
    ActionChains offset click)."""
    page.locator(modal_selector).click(position={"x": 15, "y": 15})


# UTub Deck
def select_utub_by_name(*, page: Page, utub_name: str) -> None:
    """Click the first UTub selector whose name matches exactly, then wait
    for the URL-deck header to show the selected UTub's name."""
    utub_selector = page.locator(
        f"{HPL.SELECTORS_UTUB}:has({HPL.SELECTORS_UTUB_NAME}:text-is('{utub_name}'))"
    ).first
    utub_selector.click()
    wait_until_utub_name_appears(page=page, utub_name=utub_name)


def select_utub_by_id(*, page: Page, utub_id: int) -> None:
    utub_selector = page.locator(f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']")
    expect(utub_selector).to_be_visible()
    utub_name_locator = utub_selector.locator(HPL.SELECTORS_UTUB_NAME)
    utub_name = utub_name_locator.inner_text()
    utub_selector.click()
    wait_until_utub_name_appears(page=page, utub_name=utub_name)


def select_utub_by_id_mobile(*, page: Page, utub_id: int) -> None:
    utub_selector = page.locator(f"{HPL.SELECTORS_UTUB}[utubid='{utub_id}']")
    expect(utub_selector).to_be_attached()
    utub_selector.click()


def wait_until_utub_name_appears(*, page: Page, utub_name: str) -> None:
    url_deck_header = page.locator(HPL.HEADER_URL_DECK).first
    expect(url_deck_header).to_be_visible()
    expect(url_deck_header).to_have_text(utub_name)


def get_selected_utub_id(*, page: Page) -> int:
    selected_utub = page.locator(HPL.SELECTOR_SELECTED_UTUB)
    expect(selected_utub).to_be_attached()
    utub_id = selected_utub.get_attribute("utubid")
    assert utub_id is not None
    return int(utub_id)


def get_num_utubs(*, page: Page) -> int:
    return page.locator(HPL.SELECTORS_UTUB).count()


def get_all_utub_selector_names(*, page: Page) -> list[str]:
    return page.locator(HPL.SELECTORS_UTUB).all_inner_texts()


def get_selected_utub_name(*, page: Page) -> str:
    selected_utub = page.locator(HPL.SELECTOR_SELECTED_UTUB)
    expect(selected_utub).to_be_attached()
    return selected_utub.inner_text()


# URL Deck
def get_css_selector_for_url_by_id(*, url_id: int) -> str:
    return f"{HPL.ROWS_URLS}[utuburlid='{url_id}']"


def select_url_by_title(*, page: Page, url_title: str) -> None:
    """Select the URL row whose title matches exactly."""
    url_row = page.locator(
        f"{HPL.ROWS_URLS}:has({HPL.URL_TITLE_READ}:text-is('{url_title}'))"
    ).first
    url_row.click()


def select_url_by_url_string(*, page: Page, url_string: str) -> None:
    """Select the URL row whose anchor href matches, then wait until the
    selected row reflects that URL string."""
    url_row = page.locator(
        f"{HPL.ROWS_URLS}:has({HPL.URL_STRING_READ}[href='{url_string}'])"
    ).first
    url_row.click()
    selected_url_string = page.locator(
        f"{HPL.ROW_SELECTED_URL} {HPL.URL_STRING_READ}"
    ).first
    expect(selected_url_string).to_have_attribute("href", url_string)


def get_num_url_rows(*, page: Page) -> int:
    return page.locator(HPL.ROWS_URLS).count()


def get_all_url_ids_in_selected_utub(*, page: Page) -> list[int]:
    url_ids: list[int] = []
    for url_row in page.locator(HPL.ROWS_URLS).all():
        url_id = url_row.get_attribute("utuburlid")
        assert url_id is not None
        assert url_id.isdecimal()
        url_ids.append(int(url_id))
    return url_ids


def get_selected_url(*, page: Page) -> Locator:
    selected_url = page.locator(HPL.ROW_SELECTED_URL).first
    expect(selected_url).to_be_visible()
    return selected_url


def get_url_row_by_id(*, page: Page, utub_url_id: int) -> Locator:
    url_row = page.locator(f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}']")
    expect(url_row).to_be_visible()
    return url_row


# JS-injection helpers (twin the Selenium execute_script bodies verbatim)
def invalidate_csrf_token_on_page(*, page: Page) -> None:
    page.evaluate("""() => {
    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
          if (
            !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) &&
            !this.crossDomain
          ) {
            xhr.setRequestHeader("X-CSRFToken", "invalid-csrf-token");
          }
          return true;
        }
    });
    }""")


def add_forced_rate_limit_header(*, page: Page) -> None:
    page.evaluate("""() => {
        var settings = $.ajaxSettings;
        var oldBeforeSend = settings.beforeSend;
        $.ajaxSetup({
            beforeSend: function (xhr, ajaxSettings) {
                if (oldBeforeSend) {
                    oldBeforeSend.call(this, xhr, ajaxSettings);
                }
                xhr.setRequestHeader("X-Force-Rate-Limit", "true");
                return true;
            }
        });
    }""")


def modify_navigational_link_for_rate_limit(*, page: Page, element_id: str) -> None:
    page.evaluate(
        """(elementId) => {
        const link = document.getElementById(elementId);
        if (!link) {
            throw new Error('Element with ID "' + elementId + '" not found');
        }
        const url = new URL(link.href, window.location.origin);
        url.searchParams.set('force_rate_limit', 'true');
        link.href = url.toString();
    }""",
        element_id,
    )


def force_next_delete_ajax_failure_no_navigate(*, page: Page) -> None:
    """Monkey-patches $.ajax so the next DELETE request fails with a fake
    error whose _429Handled getter always reads true — the failure handler
    then returns early after re-enabling the submit button, without
    attempting any page navigation."""
    page.evaluate("""() => {
        var originalAjax = $.ajax;
        $.ajax = function(options) {
            if (options && options.type && options.type.toLowerCase() === 'delete') {
                $.ajax = originalAjax;
                var deferred = $.Deferred();
                var fakeXhr = {
                    status: 500,
                    getResponseHeader: function() { return 'application/json'; },
                    responseText: '{"error": "forced test failure"}'
                };
                Object.defineProperty(fakeXhr, '_429Handled', {
                    get: function() { return true; },
                    set: function() { /* no-op: ignore writes from ajaxCall */ },
                    configurable: true
                });
                setTimeout(function() {
                    deferred.reject(fakeXhr, 'error', 'Internal Server Error');
                }, 0);
                deferred.promise(fakeXhr);
                return fakeXhr;
            }
            return originalAjax.apply(this, arguments);
        };
    }""")


def set_focus_on_element(*, page: Page, locator: Locator) -> None:
    locator.focus()
    expect(locator).to_be_focused()


def current_base_url(*, page: Page) -> str:
    """Return the scheme://host:port origin of the page's current URL —
    Playwright twin of deriving the app origin from `browser.current_url`
    (the fixtures land every page on the app's splash path first)."""
    split_url = urlsplit(page.url)
    return f"{split_url.scheme}://{split_url.netloc}"


def login_user_to_home_page(*, app: Flask, page: Page, user_id: int) -> None:
    """Log `user_id` in via a pre-built server-side session cookie, then
    navigate to the authenticated home page.

    The Selenium version relied on the driver already sitting on the app
    domain and refreshed to trigger the splash->home redirect; here the
    origin is derived from the page's current URL and the navigation goes
    straight to /home.
    """
    session_id = create_user_session_and_provide_session_id(app, user_id)
    base_url = current_base_url(page=page)
    login_user_with_cookie_from_session(
        context=page.context, session_id=session_id, base_url=base_url
    )
    page.goto(f"{base_url}/home")


def click_on_navbar(*, page: Page) -> None:
    """Open the collapsed Bootstrap navbar dropdown, settling any in-progress
    collapse transition before and after the toggler click. Bootstrap ignores
    a toggle click while `collapsing` is active, so clicking mid-transition
    silently no-ops and the dropdown never opens."""
    navbar_dropdown = page.locator(GenericPageLocator.NAVBAR_DROPDOWN)
    expect(navbar_dropdown).not_to_have_class(re.compile(r"collapsing"))
    page.locator(GenericPageLocator.NAVBAR_TOGGLER).click()
    expect(navbar_dropdown).not_to_have_class(re.compile(r"collapsing"))


def close_navbar(*, page: Page) -> None:
    """Collapse an already-open mobile navbar by tapping the toggler again,
    waiting for Bootstrap's hide animation (`show` class removal) to finish."""
    page.locator(GenericPageLocator.NAVBAR_TOGGLER).click()
    expect(page.locator(GenericPageLocator.NAVBAR_DROPDOWN)).not_to_have_class(
        re.compile(r"(^|\s)show(\s|$)")
    )


def add_cookie_banner_cookie(*, context: BrowserContext, base_url: str) -> None:
    """Add the consent cookie so the cookie banner never intercepts clicks.

    Unlike Selenium, Playwright's `add_cookies` requires either `url` or
    `domain`+`path`, and works before any navigation (domain+path are
    inferred from the `url` argument).
    """
    context.add_cookies(
        [
            {
                "name": UTS.COOKIE_NAME,
                "value": UTS.COOKIE_VALUE,
                "url": base_url,
            }
        ]
    )


def login_user_with_cookie_from_session(
    *, context: BrowserContext, session_id: str, base_url: str
) -> None:
    """Playwright analog of `login_utils.login_user_with_cookie_from_session`:
    installs the pre-built server-side session's cookie on the browser context.

    The Selenium version calls `browser.refresh()` after adding the cookie;
    here the caller's subsequent `page.goto()` navigates directly to the
    target page, making a reload redundant.
    """
    context.add_cookies(
        [
            {
                "name": "session",
                "value": session_id,
                "url": base_url,
                "httpOnly": True,
            }
        ]
    )
