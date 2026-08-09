from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend import db
from backend.config import ConfigTestUI
from backend.models.urls import Urls
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.strings.user_settings_strs import USER_SETTINGS_STRINGS
from backend.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import SettingsPageLocators as SPL
from tests.functional.playwright_utils import (
    current_base_url,
    wait_then_click_element,
    wait_until_visible_css_selector,
)
from tests.functional.settings_ui.playwright_utils import login_user_and_open_settings

pytestmark = pytest.mark.settings_ui

DEFAULT_USER_ID: int = 1
_PREFERENCES_SAVED: str = USER_SETTINGS_STRINGS.PREFERENCES_SAVED

# Three URLs whose title order deliberately differs from their insertion /
# added_at order, so the TITLE_AZ sort produces a permutation distinct from the
# NEWEST default — proving the chosen sort actually took effect (not a
# coincidental match with insertion order). Insertion order is A, B, C:
#   NEWEST (added_at desc): Charlie(day2), Bravo(day1), alpha(day0)  -> A, C, B
#   TITLE_AZ (case-insensitive): alpha, Bravo, Charlie               -> B, C, A
_BASE_TIME = datetime(2020, 1, 1, tzinfo=timezone.utc)
_SEED_URLS: list[tuple[str, str, timedelta]] = [
    ("Charlie", "https://charlie.example.com", timedelta(days=2)),
    ("alpha", "https://alpha.example.com", timedelta(days=0)),
    ("Bravo", "https://bravo.example.com", timedelta(days=1)),
]


def _seed_utub_with_sorted_urls(app: Flask, user_id: int) -> tuple[int, list[int]]:
    """Create a UTub owned by ``user_id`` holding three URLs with distinct
    ``added_at`` timestamps and ``url_title`` values (see ``_SEED_URLS``), and
    return ``(utub_id, expected_title_az_order)`` where the second element is the
    list of ``Utub_Urls`` ids in case-insensitive title order — the order the
    server must render the deck in once the user's ``default_sort`` is TITLE_AZ.
    """
    with app.app_context():
        new_utub = Utubs(
            name="Display Prefs Sort UTub",
            utub_description="",
            utub_creator=user_id,
        )
        db.session.add(new_utub)
        db.session.commit()

        creator_membership = Utub_Members()
        creator_membership.utub_id = new_utub.id
        creator_membership.user_id = user_id
        creator_membership.member_role = Member_Role.CREATOR
        db.session.add(creator_membership)
        db.session.commit()

        title_to_utub_url_id: dict[str, int] = {}
        for url_title, url_string, added_offset in _SEED_URLS:
            url = Urls(normalized_url=url_string, current_user_id=user_id)
            db.session.add(url)
            db.session.flush()

            utub_url = Utub_Urls()
            utub_url.utub_id = new_utub.id
            utub_url.url_id = url.id
            utub_url.user_id = user_id
            utub_url.url_title = url_title
            utub_url.added_at = _BASE_TIME + added_offset
            db.session.add(utub_url)
            db.session.flush()

            title_to_utub_url_id[url_title] = utub_url.id

        db.session.commit()

        utub_id = new_utub.id

    expected_title_az_order = [
        title_to_utub_url_id[url_title]
        for url_title, _, _ in sorted(_SEED_URLS, key=lambda seed: seed[0].lower())
    ]
    return utub_id, expected_title_az_order


def _open_display_tab(page: Page) -> None:
    """Click the Display tab and wait for its panel to be shown."""
    wait_then_click_element(page=page, css_selector=SPL.TAB_UI_SETTINGS_BUTTON)
    wait_until_visible_css_selector(page=page, css_selector=SPL.PANEL_UI_SETTINGS)


def test_select_dark_theme_applies_app_wide_and_persists(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings page Display tab
    WHEN the user selects the Dark theme
    THEN the <html data-theme> flips to "dark" and the success toast shows;
        the choice applies app-wide (server-stamped on /home's initial render,
        no flash) and persists across a reload of /settings (round-tripping
        through the DB: the Dark radio stays aria-checked and the root stays
        dark).
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )
    origin = current_base_url(page=page)

    _open_display_tab(page)

    # Selecting Dark fires the debounced PUT; on success the controller echoes
    # the server-authoritative theme onto <html> and announces via the toast.
    wait_then_click_element(page=page, css_selector=SPL.THEME_RADIO_DARK)
    expect(page.locator(SPL.GLOBAL_STATUS_TOAST)).to_have_text(_PREFERENCES_SAVED)
    expect(page.locator(SPL.HTML_ROOT)).to_have_attribute("data-theme", "dark")

    # App-wide proof: /home is a different page in the same context; its initial
    # server render must already carry data-theme="dark" (pre-paint stamp), NOT
    # resolve it after paint. Playwright's default color_scheme is light, so an
    # explicit "dark" (non-"system") preference proves the server stamp — not the
    # OS media query — is what set it.
    page.goto(f"{origin}/home")
    expect(page.locator(SPL.HTML_ROOT)).to_have_attribute("data-theme", "dark")

    # Persistence: a fresh load of /settings still shows Dark selected and the
    # root dark — the preference survived the request boundary via the DB.
    page.goto(f"{origin}/settings")
    _open_display_tab(page)
    expect(page.locator(SPL.THEME_RADIO_DARK)).to_have_attribute("aria-checked", "true")
    expect(page.locator(SPL.HTML_ROOT)).to_have_attribute("data-theme", "dark")


def test_default_sort_preference_orders_url_deck_server_side(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user with a UTub whose URLs have distinct added_at/title
    WHEN the user sets Default sort to "Title A-Z" and then opens /home
    THEN the URL deck renders on its very first render in case-insensitive title
        order — proving DD-36's server-side ordering round-trips through the DB
        into the rendered DOM with no client-side re-sort involved.
    """
    utub_id, expected_title_az_order = _seed_utub_with_sorted_urls(
        provide_app, DEFAULT_USER_ID
    )

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )
    origin = current_base_url(page=page)

    _open_display_tab(page)

    page.locator(SPL.DEFAULT_SORT_SELECT).select_option("title_az")
    expect(page.locator(SPL.GLOBAL_STATUS_TOAST)).to_have_text(_PREFERENCES_SAVED)

    # Preselect the seeded UTub so the deck renders from the server's response
    # for GET /utubs/<utub_id> — which DD-36 now orders by default_sort.
    page.goto(f"{origin}/home?{UTUB_ID_QUERY_PARAM}={utub_id}")

    url_rows = page.locator(HPL.ROWS_URLS)
    expect(url_rows).to_have_count(len(expected_title_az_order))
    rendered_order = [
        int(url_rows.nth(index).get_attribute("utuburlid"))
        for index in range(len(expected_title_az_order))
    ]
    assert rendered_order == expected_title_az_order, (
        "URL deck first-render order should match the server-side TITLE_AZ sort; "
        f"expected {expected_title_az_order}, rendered {rendered_order}"
    )


def test_density_preference_applies_to_home_body_on_reload(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings page Display tab
    WHEN the user sets Density to "Compact" and then opens /home
    THEN the home <body> carries data-density="compact" on load — proving the
        stored view preference round-trips through the DB into the home runtime.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )
    origin = current_base_url(page=page)

    _open_display_tab(page)

    page.locator(SPL.DENSITY_SELECT).select_option("compact")
    expect(page.locator(SPL.GLOBAL_STATUS_TOAST)).to_have_text(_PREFERENCES_SAVED)

    page.goto(f"{origin}/home")
    expect(page.locator("body")).to_have_attribute("data-density", "compact")


def test_default_view_preference_applies_to_home_body_on_reload(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings page Display tab
    WHEN the user sets Default view to "Cards" and then opens /home
    THEN the home <body> carries data-view="cards" on load — proving the stored
        view-mode preference round-trips through the DB into the home runtime.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )
    origin = current_base_url(page=page)

    _open_display_tab(page)

    page.locator(SPL.DEFAULT_VIEW_SELECT).select_option("cards")
    expect(page.locator(SPL.GLOBAL_STATUS_TOAST)).to_have_text(_PREFERENCES_SAVED)

    page.goto(f"{origin}/home")
    expect(page.locator("body")).to_have_attribute("data-view", "cards")


def test_splash_hero_title_visible_in_forced_light_mode(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN an anonymous visitor with the OS in light mode
    WHEN they load the splash page (/)
    THEN the pre-paint stamp resolves the anonymous "system" default to "light"
        and the gradient-clipped hero wordmark renders its light-theme
        dark->green gradient (not the default white->green gradient, which is
        invisible on a light background).

    NOTE: the hero title uses `background-clip: text` with a transparent text
    fill, so its computed `color`/`-webkit-text-fill-color` is `transparent` in
    BOTH themes by design — the visible color comes from the clipped gradient
    background. Asserting the fill is non-transparent (as an earlier draft of the
    plan phrased it) would therefore fail even with the fix applied. The correct
    regression check is that the computed `background-image` carries the light
    variant's dark gradient start (#1f2424 = rgb(31, 36, 36)), proving the
    `:root[data-theme="light"] .splash-hero-title` override is what painted it.
    """
    # Force the OS preference BEFORE (re)loading so the pre-paint <head> script's
    # matchMedia('(prefers-color-scheme: dark)') resolves the anonymous "system"
    # stamp to "light".
    page.emulate_media(color_scheme="light")
    origin = current_base_url(page=page)
    page.goto(f"{origin}/")

    expect(page.locator(SPL.HTML_ROOT)).to_have_attribute("data-theme", "light")

    hero_title = page.locator(".splash-hero-title")
    expect(hero_title).to_be_visible()

    background_image = hero_title.evaluate(
        "element => window.getComputedStyle(element).backgroundImage"
    )
    assert "rgb(31, 36, 36)" in background_image, (
        "Splash hero wordmark should use the light-theme dark->green gradient "
        f"(dark start #1f2424 / rgb(31, 36, 36)); got: {background_image}"
    )
