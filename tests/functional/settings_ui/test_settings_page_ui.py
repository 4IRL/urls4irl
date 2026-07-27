from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend import db
from backend.config import ConfigTestUI
from backend.models.urls import Urls
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.locators import SettingsPageLocators as SPL
from tests.functional.playwright_utils import (
    click_on_navbar,
    wait_for_element_presence,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_in_focus,
)
from tests.functional.settings_ui.playwright_utils import (
    login_user_and_open_home,
    login_user_and_open_settings,
)

pytestmark = pytest.mark.settings_ui

DEFAULT_USER_ID: int = 1


def _seed_distinct_stats_for_user_one(app: Flask) -> None:
    """Seed mutually-distinct per-user activity counts for user 1 so each
    Stats card renders a unique value (2/3/5/7/11) and a swapped card is
    caught. Users 1-5 already exist (seeded by the `seeded_users` autouse
    fixture via `flask addmock users`)."""
    with app.app_context():
        # 2 UTubs created by user 1 (each with a CREATOR membership row).
        user_one_utubs: list[Utubs] = []
        for utub_index in range(2):
            created_utub = Utubs(
                name=f"User1 UTub {utub_index}",
                utub_creator=DEFAULT_USER_ID,
                utub_description="",
            )
            db.session.add(created_utub)
            db.session.flush()
            db.session.add(
                Utub_Members(
                    utub_id=created_utub.id,
                    user_id=DEFAULT_USER_ID,
                    member_role=Member_Role.CREATOR,
                )
            )
            user_one_utubs.append(created_utub)

        # 3 UTubs created by others (2 by user 2, 1 by user 3); user 1 is MEMBER.
        for creator_id in (2, 2, 3):
            others_utub = Utubs(
                name=f"User{creator_id} UTub",
                utub_creator=creator_id,
                utub_description="",
            )
            db.session.add(others_utub)
            db.session.flush()
            db.session.add(
                Utub_Members(
                    utub_id=others_utub.id,
                    user_id=creator_id,
                    member_role=Member_Role.CREATOR,
                )
            )
            db.session.add(
                Utub_Members(
                    utub_id=others_utub.id,
                    user_id=DEFAULT_USER_ID,
                    member_role=Member_Role.MEMBER,
                )
            )

        home_utub = user_one_utubs[0]

        # 5 Utub_Urls added by user 1, each backed by a unique Urls row.
        user_one_utub_urls: list[Utub_Urls] = []
        for url_index in range(5):
            backing_url = Urls(
                normalized_url=f"https://user1-ui-url-{url_index}.example.com",
                current_user_id=DEFAULT_USER_ID,
            )
            db.session.add(backing_url)
            db.session.flush()
            utub_url = Utub_Urls()
            utub_url.utub_id = home_utub.id
            utub_url.url_id = backing_url.id
            utub_url.user_id = DEFAULT_USER_ID
            utub_url.url_title = f"User1 URL {url_index}"
            db.session.add(utub_url)
            db.session.flush()
            user_one_utub_urls.append(utub_url)

        # 7 Utub_Tags created by user 1.
        user_one_tags: list[Utub_Tags] = []
        for tag_index in range(7):
            created_tag = Utub_Tags(
                utub_id=home_utub.id,
                tag_string=f"user1-ui-tag-{tag_index}",
                created_by=DEFAULT_USER_ID,
            )
            db.session.add(created_tag)
            db.session.flush()
            user_one_tags.append(created_tag)

        # 11 Utub_Url_Tags applied by user 1 (distinct url/tag pairs).
        applied_pairs = [
            (url_index, tag_index) for url_index in range(5) for tag_index in range(7)
        ][:11]
        for url_index, tag_index in applied_pairs:
            db.session.add(
                Utub_Url_Tags(
                    utub_id=home_utub.id,
                    utub_url_id=user_one_utub_urls[url_index].id,
                    utub_tag_id=user_one_tags[tag_index].id,
                    user_id=DEFAULT_USER_ID,
                )
            )

        db.session.commit()


def test_account_tab_is_default(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in, email-validated user
    WHEN the user opens `/settings`
    THEN the Account tab is selected by default and its panel is displayed.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    expect(page.locator(SPL.TAB_ACCOUNT_BUTTON)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.locator(SPL.PANEL_ACCOUNT)).to_be_visible()


def test_click_stats_tab_switches_panel(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings page with the Account tab active
    WHEN the user clicks the Stats tab
    THEN the Stats tab becomes selected, the Stats panel is shown, the
        Account panel gains the `hidden` attribute, and the Stats panel
        heading renders the localized Stats label.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.TAB_STATS_BUTTON)

    expect(page.locator(SPL.TAB_STATS_BUTTON)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.locator(SPL.PANEL_STATS)).to_be_visible()

    # Attribute-exact check mirroring the Selenium
    # `get_attribute("hidden") is not None` assertion — a present-but-
    # valueless HTML attribute reads as "".
    expect(page.locator(SPL.PANEL_ACCOUNT)).to_have_attribute("hidden", "")

    stats_heading = page.locator(SPL.PANEL_STATS).locator("h2")
    expect(stats_heading).to_have_text(UI_TEST_STRINGS.SETTINGS_TAB_STATS)


def test_page_title_renders(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user
    WHEN the user opens `/settings`
    THEN the page `<h1>` renders the localized Settings page title.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    page_title = wait_then_get_element(page=page, css_selector=f"{SPL.PAGE_ROOT} h1")
    expect(page_title).to_have_text(UI_TEST_STRINGS.SETTINGS_PAGE_TITLE)


def test_back_home_btn_navigates_to_home(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings page
    WHEN the user clicks the Back-to-Home control
    THEN the browser navigates to the authenticated home page.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    # The back-home button lives inside the always-collapsed navbar
    # dropdown; open the hamburger before the button is clickable.
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=SPL.BACK_HOME_BTN)

    expect(page).to_have_url(re.compile(r"/home$"))


def test_settings_nav_link_present_on_home(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the authenticated home page
    WHEN the navbar renders
    THEN the Settings nav link (`#userSettingsLink`) rendered in the home
        navbar dropdown is present — proving it is reachable from the home page.

    Cross-page dependency note: this test exercises the home page nav,
    not the settings page.
    """
    login_user_and_open_home(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    # DOM presence, not visibility — the link is in a collapsed dropdown.
    wait_for_element_presence(page=page, css_selector=SPL.SETTINGS_NAV_LINK)


def test_arrow_key_navigates_tabs(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings page with the Account tab focused
    WHEN the user presses ArrowRight
    THEN the Stats tab becomes selected (roving-tabindex keyboard nav).
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    account_tab = page.locator(SPL.TAB_ACCOUNT_BUTTON)
    expect(account_tab).to_have_attribute("aria-selected", "true")
    # Click activates the Account tab; the controller focuses the Account
    # panel on mouse activation. Wait for that focus to land as a barrier
    # confirming the click handler ran before sending the key. press()
    # then re-focuses the tab button itself, delivering the keydown to the
    # bound listener.
    account_tab.click()
    wait_until_in_focus(page=page, css_selector=SPL.PANEL_ACCOUNT)
    account_tab.press("ArrowRight")

    expect(page.locator(SPL.TAB_STATS_BUTTON)).to_have_attribute(
        "aria-selected", "true"
    )


def test_stats_panel_renders_seeded_counts(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user with mutually-distinct seeded activity counts
        (2 UTubs created / member of 3 / 5 URLs / 7 tags created / 11 applied)
    WHEN the user opens `/settings` and clicks the Stats tab
    THEN each stat card renders its own seeded value — so a swapped or
        mislabeled card is caught by the per-card assertions.
    """
    _seed_distinct_stats_for_user_one(provide_app)

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.TAB_STATS_BUTTON)
    expect(page.locator(SPL.PANEL_STATS)).to_be_visible()

    expect(page.locator(SPL.STAT_UTUBS_CREATED)).to_have_text("2")
    expect(page.locator(SPL.STAT_MEMBER_OF)).to_have_text("3")
    expect(page.locator(SPL.STAT_URLS_ADDED)).to_have_text("5")
    expect(page.locator(SPL.STAT_TAGS_CREATED)).to_have_text("7")
    expect(page.locator(SPL.STAT_TAGS_APPLIED)).to_have_text("11")
