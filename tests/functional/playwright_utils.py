from dataclasses import dataclass
from enum import Enum
import re
import secrets
from urllib.parse import urlencode, urlsplit, urlunsplit

from flask import Flask, session
from playwright.sync_api import BrowserContext, Locator, Page, expect

from backend.models.users import Users
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.locators import GenericPageLocator
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as MP
from tests.functional.locators import SplashPageLocators as SPL

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


def wait_until_visible(*, locator: Locator) -> Locator:
    """Wait until an already-located element is visible and return it."""
    expect(locator).to_be_visible()
    return locator


def wait_until_css_property(
    *, page: Page, css_selector: str, css_property: str, expected_value: str
) -> Locator:
    """Wait until an element's computed CSS property equals expected_value.

    Use for elements transitioning via CSS (opacity, width) rather than
    display:none, where visibility checks are unreliable.
    """
    page.wait_for_function(
        """({ cssSelector, cssProperty, expectedValue }) => {
            const element = document.querySelector(cssSelector);
            if (!element) return false;
            return (
                window.getComputedStyle(element).getPropertyValue(cssProperty) ===
                expectedValue
            );
        }""",
        arg={
            "cssSelector": css_selector,
            "cssProperty": css_property,
            "expectedValue": expected_value,
        },
    )
    return page.locator(css_selector).first


def wait_for_animation_to_end_check_height(*, page: Page, css_selector: str) -> None:
    """Wait until an element's rendered height is identical across two
    consecutive animation-frame polls (the element has stopped animating)."""
    page.wait_for_function(
        """(cssSelector) => {
            const element = document.querySelector(cssSelector);
            if (!element) return false;
            const currentHeight = element.getBoundingClientRect().height;
            const previousHeight = element.__u4iPreviousHeight;
            element.__u4iPreviousHeight = currentHeight;
            return previousHeight !== undefined && previousHeight === currentHeight;
        }""",
        arg=css_selector,
    )


def wait_for_animation_to_end_check_top_lhs_corner(
    *, page: Page, css_selector: str
) -> None:
    """Wait until an element's top-left corner is identical across two
    consecutive animation-frame polls (the element has stopped moving)."""
    page.wait_for_function(
        """(cssSelector) => {
            const element = document.querySelector(cssSelector);
            if (!element) return false;
            const boundingRect = element.getBoundingClientRect();
            const currentCorner = boundingRect.left + "," + boundingRect.top;
            const previousCorner = element.__u4iPreviousCorner;
            element.__u4iPreviousCorner = currentCorner;
            return previousCorner !== undefined && previousCorner === currentCorner;
        }""",
        arg=css_selector,
    )


def wait_for_page_complete_and_dom_stable(*, page: Page) -> None:
    """Twin of the Selenium page-complete + jQuery-idle + no-animation gate.

    Playwright auto-waits for most interactions, but some tests still need
    an explicit barrier for in-flight jQuery XHRs/animations after a
    navigation or refresh."""
    page.wait_for_load_state("load")
    page.wait_for_function(
        "() => (typeof jQuery !== 'undefined') ? jQuery.active === 0 : true"
    )
    page.wait_for_function(
        "() => (typeof jQuery !== 'undefined') ? jQuery(':animated').length === 0 : true"
    )


# Splash footer pages
def scroll_footer_link_into_view(*, page: Page, css_selector: str) -> Locator:
    """Scroll a below-the-fold footer link into the viewport before clicking.

    Playwright's click auto-scrolls, but the explicit scroll keeps parity
    with the Selenium helper's contract of returning a viewport-visible link.
    """
    link = page.locator(css_selector).first
    expect(link).to_be_attached()
    link.scroll_into_view_if_needed()
    return link


def visit_privacy_page(*, page: Page) -> None:
    scroll_footer_link_into_view(page=page, css_selector=HPL.PRIVACY_BTN)
    wait_then_click_element(page=page, css_selector=HPL.PRIVACY_BTN)
    expect(page.locator(HPL.PRIVACY_HEADER).first).to_have_text("Privacy Policy")


def visit_terms_page(*, page: Page) -> None:
    scroll_footer_link_into_view(page=page, css_selector=HPL.TERMS_BTN)
    wait_then_click_element(page=page, css_selector=HPL.TERMS_BTN)
    expect(page.locator(HPL.TERMS_HEADER).first).to_have_text("Terms & Conditions")


def visit_contact_us_page(*, page: Page) -> None:
    scroll_footer_link_into_view(page=page, css_selector=HPL.CONTACT_BTN)
    wait_then_click_element(page=page, css_selector=HPL.CONTACT_BTN)
    expect(page.locator(HPL.CONTACT_US_HEADER).first).to_have_text(
        IDENTIFIERS.CONTACT_US_PAGE
    )


def contact_form_entry(*, page: Page, subject: str, content: str) -> None:
    subject_input = wait_then_get_element(
        page=page, css_selector=HPL.CONTACT_SUBJECT_INPUT
    )
    clear_then_send_keys(locator=subject_input, input_text=subject)

    content_input = wait_then_get_element(
        page=page, css_selector=HPL.CONTACT_CONTENT_INPUT
    )
    clear_then_send_keys(locator=content_input, input_text=content)


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


def wait_for_element_visible(*, page: Page, css_selector: str) -> None:
    expect(page.locator(css_selector).first).to_be_visible()


def wait_for_web_element_and_click(*, locator: Locator) -> None:
    """Wait for an already-located element to be visible and enabled, then
    click it (Playwright's click auto-waits for actionability)."""
    expect(locator).to_be_visible()
    expect(locator).to_be_enabled()
    locator.click()


# Splash login/register flows
def login_user_ui(
    *,
    page: Page,
    username: str = UTS.TEST_USERNAME_1,
    password: str = UTS.TEST_PASSWORD_1,
) -> Locator:
    """Open the login modal from the splash page and fill in credentials.

    Returns the password input locator so callers can press Enter on it.
    """
    wait_then_click_element(page=page, css_selector=SPL.BUTTON_LOGIN)

    wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)

    wait_for_element_presence(page=page, css_selector=SPL.LOGIN_INPUT_USERNAME)
    wait_until_visible_css_selector(page=page, css_selector=SPL.LOGIN_INPUT_USERNAME)

    return input_login_fields(page=page, username=username, password=password)


def input_login_fields(
    *,
    page: Page,
    username: str = UTS.TEST_USERNAME_1,
    password: str = UTS.TEST_PASSWORD_1,
) -> Locator:
    username_input = wait_then_get_element(
        page=page, css_selector=SPL.LOGIN_INPUT_USERNAME
    )
    clear_then_send_keys(locator=username_input, input_text=username)

    password_input = wait_then_get_element(
        page=page, css_selector=SPL.LOGIN_INPUT_PASSWORD
    )
    clear_then_send_keys(locator=password_input, input_text=password)

    return password_input


def login_with_google_ui(
    *,
    page: Page,
    subject: str = UTS.OAUTH_RETURNING_USER_SUBJECT,
    email: str = UTS.OAUTH_RETURNING_USER_EMAIL,
    name: str = UTS.OAUTH_RETURNING_USER_NAME,
    from_register: bool = False,
) -> None:
    """Sign in (or register) via the fake Google OAuth provider
    (backend/testing/fake_oauth_provider.py).

    Seeding the identity is its own navigation (the fake provider has no
    session-shared way to receive it otherwise), so return to the splash
    page afterward before opening the login/register modal.
    """
    splash_url = page.url
    split_splash_url = urlsplit(splash_url)
    set_identity_url = urlunsplit(
        (
            split_splash_url.scheme,
            split_splash_url.netloc,
            "/fake-oauth/set-identity",
            urlencode({"subject": subject, "email": email, "name": name}),
            "",
        )
    )

    page.goto(set_identity_url)
    page.goto(splash_url)

    if from_register:
        wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER)
        wait_for_modal_ready(page=page, modal_selector=SPL.REGISTER_MODAL)
        wait_then_click_element(
            page=page, css_selector=SPL.REGISTER_BUTTON_GOOGLE_OAUTH
        )
    else:
        wait_then_click_element(page=page, css_selector=SPL.BUTTON_LOGIN)
        wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)
        wait_then_click_element(page=page, css_selector=SPL.LOGIN_BUTTON_GOOGLE_OAUTH)


def login_with_github_ui(
    *,
    page: Page,
    subject: str = UTS.OAUTH_GITHUB_RETURNING_USER_SUBJECT,
    email: str = UTS.OAUTH_GITHUB_RETURNING_USER_EMAIL,
    login: str = UTS.OAUTH_GITHUB_RETURNING_USER_LOGIN,
    from_register: bool = False,
) -> None:
    """Sign in (or register) via the fake GitHub OAuth provider
    (backend/testing/fake_oauth_provider.py).

    Mirrors `login_with_google_ui` exactly, with GitHub's `login` query param
    (its `GET user` resource's preferred-username seed) added in place of
    Google's `name`.
    """
    splash_url = page.url
    split_splash_url = urlsplit(splash_url)
    set_identity_url = urlunsplit(
        (
            split_splash_url.scheme,
            split_splash_url.netloc,
            "/fake-oauth/set-identity",
            urlencode({"subject": subject, "email": email, "login": login}),
            "",
        )
    )

    page.goto(set_identity_url)
    page.goto(splash_url)

    if from_register:
        wait_then_click_element(page=page, css_selector=SPL.BUTTON_REGISTER)
        wait_for_modal_ready(page=page, modal_selector=SPL.REGISTER_MODAL)
        wait_then_click_element(
            page=page, css_selector=SPL.REGISTER_BUTTON_GITHUB_OAUTH
        )
    else:
        wait_then_click_element(page=page, css_selector=SPL.BUTTON_LOGIN)
        wait_for_modal_ready(page=page, modal_selector=SPL.LOGIN_MODAL)
        wait_then_click_element(page=page, css_selector=SPL.LOGIN_BUTTON_GITHUB_OAUTH)


def invalidate_csrf_token_in_form(*, page: Page) -> None:
    invalidate_csrf_token_on_page(page=page)


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


def open_update_url_title(*, page: Page, selected_url_row: Locator) -> None:
    """Hover the selected URL's title to reveal the edit button, click it,
    and wait for the title-update input to become visible."""
    url_title_text = page.locator(f"{HPL.ROW_SELECTED_URL} {HPL.URL_TITLE_READ}").first
    expect(url_title_text).to_be_visible()
    url_title_text.hover()

    update_url_title_button = selected_url_row.locator(HPL.BUTTON_URL_TITLE_UPDATE)
    update_url_title_button.click()

    update_url_title_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}"
    wait_until_visible_css_selector(page=page, css_selector=update_url_title_selector)


_DISPATCH_POINTER_DRAG_JS = """
    async ({ cssSelector, startX, startY, endX, endY, steps, stepDelayMs }) => {
        const element = document.querySelector(cssSelector);
        if (!element) {
            throw new Error('No element found for selector "' + cssSelector + '"');
        }

        function dispatchPointer(type, clientX, clientY) {
            const event = new PointerEvent(type, {
                bubbles: true,
                cancelable: true,
                pointerId: 1,
                pointerType: "touch",
                button: 0,
                clientX: clientX,
                clientY: clientY,
            });
            element.dispatchEvent(event);
        }

        function sleep(milliseconds) {
            return new Promise((resolve) => setTimeout(resolve, milliseconds));
        }

        dispatchPointer("pointerdown", startX, startY);
        for (let step = 1; step <= steps; step++) {
            if (stepDelayMs > 0) {
                await sleep(stepDelayMs);
            }
            const interpolatedX = startX + ((endX - startX) * step) / steps;
            const interpolatedY = startY + ((endY - startY) * step) / steps;
            dispatchPointer("pointermove", interpolatedX, interpolatedY);
        }
        if (stepDelayMs > 0) {
            await sleep(stepDelayMs);
        }
        dispatchPointer("pointerup", endX, endY);
    }
"""


def dispatch_pointer_drag(
    *,
    page: Page,
    css_selector: str,
    start_y: float,
    end_y: float,
    start_x: float | None = None,
    end_x: float | None = None,
    steps: int = 6,
    step_delay_ms: int = 0,
) -> None:
    """Drives a synthetic pointer drag on the element matched by
    ``css_selector`` — pointerdown at the start point, ``steps`` interpolated
    pointermoves, and a final pointerup at the end point.

    ``start_x``/``end_x`` default to 0 (purely vertical drag). Every event is
    a real PointerEvent (pointerType "touch", primary button) dispatched
    directly on the target element (gesture listeners bind via
    element.addEventListener; document-dispatched synthetics never reach
    them). ``step_delay_ms`` inserts real wall-clock pauses between moves so
    a sub-threshold drag's velocity sample stays below the fling threshold —
    an instantaneous synthetic drag otherwise computes a huge velocity and
    commits regardless of distance.

    @example dispatch_pointer_drag(page=page, css_selector="#tagSheetHandle",
        start_y=780, end_y=560)  # 220px up (open gesture)
    @example dispatch_pointer_drag(page=page, css_selector="#tagSheetHandle",
        start_y=780, end_y=720, step_delay_ms=40)  # slow sub-threshold drag
    """
    resolved_start_x = start_x if start_x is not None else 0
    resolved_end_x = end_x if end_x is not None else 0

    page.evaluate(
        _DISPATCH_POINTER_DRAG_JS,
        {
            "cssSelector": css_selector,
            "startX": resolved_start_x,
            "startY": start_y,
            "endX": resolved_end_x,
            "endY": end_y,
            "steps": steps,
            "stepDelayMs": step_delay_ms,
        },
    )


def set_focus_on_element(*, page: Page, locator: Locator) -> None:
    locator.focus()
    expect(locator).to_be_focused()


def current_base_url(*, page: Page) -> str:
    """Return the scheme://host:port origin of the page's current URL —
    Playwright twin of deriving the app origin from `browser.current_url`
    (the fixtures land every page on the app's splash path first)."""
    split_url = urlsplit(page.url)
    return f"{split_url.scheme}://{split_url.netloc}"


def _create_random_identifier() -> str:
    return secrets.token_hex(64)


def _create_random_sid() -> str:
    return secrets.token_urlsafe(32)


def create_user_session_and_provide_session_id(*, app: Flask, user_id: int) -> str:
    """
    Manually creates a user session to allow user to be logged in
    without needing UI interaction.

    Args:
        app (Flask): The Flask application is necessary to generate a request context in order to insert the session into the appropriate session engine
        user_id (int): The user ID wanting to be logged in as

    Returns:
        (str): The session ID of the user that can be used to log the user in
    """
    random_sid = _create_random_sid()
    with app.test_request_context("/"):
        user: Users = Users.query.get(user_id)
        session["_user_id"] = user.get_id()
        session["_fresh"] = True
        session["_id"] = _create_random_identifier()
        session.sid = random_sid
        session.modified = True

        app.session_interface.save_session(
            app, session, response=app.make_response("Testing")
        )
    return random_sid


def login_user_to_home_page(*, app: Flask, page: Page, user_id: int) -> None:
    """Log `user_id` in via a pre-built server-side session cookie, then
    navigate to the authenticated home page.

    The Selenium version relied on the driver already sitting on the app
    domain and refreshed to trigger the splash->home redirect; here the
    origin is derived from the page's current URL and the navigation goes
    straight to /home.
    """
    session_id = create_user_session_and_provide_session_id(app=app, user_id=user_id)
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
