import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend.models.utub_members import Member_Role, Utub_Members
from tests.functional.db_utils import (
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
    set_utub_locked_state,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_utub_selected
from tests.functional.playwright_utils import (
    login_user_to_home_page,
    select_utub_by_id,
    wait_for_element_presence,
    wait_until_css_property,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.utubs_ui


def _role_icon_for_member(*, app: Flask, utub_id: int, user_id: int) -> str:
    """Return the deck role-icon locator for a user's membership in a UTub,
    mirroring the mapping in test_select_utub_ui.test_utub_member_icon."""
    with app.app_context():
        membership: Utub_Members = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id, Utub_Members.user_id == user_id
        ).first()
        member_role = membership.member_role

    if member_role == Member_Role.CREATOR.value:
        return HPL.CREATOR_ICON
    if member_role == Member_Role.CO_CREATOR.value:
        return HPL.CO_CREATOR_ICON
    return HPL.MEMBER_ICON


def test_locked_utub_shows_lock_affordances(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user in multiple UTubs where one UTub they belong to is locked
    WHEN the user loads the home page and selects the locked UTub
    THEN the deck selector shows the padlock in place of the role icon, the URL
        deck title padlock becomes visible, <body> gains the `utub-locked` class,
        and both the corner add-URL button AND the per-URL delete button on the
        SELECTED (expanded) URL card are disabled via CSS. The selected-card
        delete button is the regression case: urls.css re-enables per-URL option
        buttons on `[urlSelected="true"]` cards (specificity 0-4-1), so only the
        `!important` lock declarations keep it disabled.
    """
    app = provide_app
    user_id = 1
    locked_utub = get_utub_this_user_created(app, user_id)
    role_icon = _role_icon_for_member(app=app, utub_id=locked_utub.id, user_id=user_id)

    set_utub_locked_state(app, locked_utub.id, True)
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    locked_selector = f"{HPL.SELECTORS_UTUB}[utubid='{locked_utub.id}']"
    wait_for_element_presence(page=page, css_selector=locked_selector)

    # The deck selector shows the padlock and NOT the member-role icon.
    wait_until_visible_css_selector(
        page=page, css_selector=f"{locked_selector} {HPL.UTUB_LOCKED_ICON}"
    )
    expect(page.locator(f"{locked_selector} {role_icon}")).to_have_count(0)

    # Assert-before-state: nothing is selected yet, so the lock affordances in
    # the URL deck are not present until the locked UTub is chosen.
    expect(page.locator("body")).not_to_have_class(
        re.compile(rf"(^|\s){HPL.BODY_LOCKED_CLASS}(\s|$)")
    )
    expect(page.locator(HPL.URL_DECK_LOCK_ICON)).to_be_hidden()

    select_utub_by_id(page=page, utub_id=locked_utub.id)
    assert_utub_selected(page=page, app=app, utub_id=locked_utub.id)

    # The URL deck title padlock becomes visible and the body class flips on.
    wait_until_visible_css_selector(page=page, css_selector=HPL.URL_DECK_LOCK_ICON)
    expect(page.locator("body")).to_have_class(
        re.compile(rf"(^|\s){HPL.BODY_LOCKED_CLASS}(\s|$)")
    )

    # A representative mutation button is disabled by the `utub-locked` CSS.
    wait_until_css_property(
        page=page,
        css_selector=HPL.BUTTON_CORNER_URL_CREATE,
        css_property="pointer-events",
        expected_value="none",
    )

    # Inline edit hints are HIDDEN (not merely greyed) on a locked UTub — the
    # padlock already communicates the state. This also guards a regression: the
    # locked opacity rule previously forced the normally-invisible "Add a
    # description?" button (opacity:0 on a UTub that HAS a description) visible.
    expect(page.locator(HPL.PENCIL_ICON_NAME)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_ADD_UTUB_DESC_ON_EMPTY)).to_be_hidden()

    # The locked UTub is seeded with URLs (create_test_tags -> addmock tags
    # seeds a URL into every UTub), so expand the first card into
    # urlSelected="true" — the exact state where urls.css re-enables the
    # per-URL option buttons and would out-specify the lock rule.
    first_url_row = page.locator(HPL.ROWS_URLS).first
    expect(first_url_row).to_be_visible()
    first_url_row.click()
    wait_until_visible_css_selector(page=page, css_selector=HPL.ROW_SELECTED_URL)

    # The per-URL DELETE button on the SELECTED card stays disabled. Without the
    # `!important` declarations in utub-locked.css, urls.css re-enables it
    # (pointer-events: initial) because its attribute-scoped selector
    # out-specifies the class-scoped lock rule — this assertion fails there.
    wait_until_css_property(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}",
        css_property="pointer-events",
        expected_value="none",
    )


def test_unlocked_utub_shows_role_icon_and_clears_lock_state(
    page: Page, create_test_tags, provide_app: Flask
):
    """
    GIVEN a user with one locked UTub and one unlocked UTub, with the locked
        UTub currently selected
    WHEN the user selects the unlocked UTub
    THEN the unlocked deck selector shows its normal role icon (no padlock),
        <body> loses the `utub-locked` class, and the URL deck title padlock hides
    """
    app = provide_app
    user_id = 1
    locked_utub = get_utub_this_user_created(app, user_id)
    unlocked_utub = get_utub_this_user_did_not_create(app, user_id)
    unlocked_role_icon = _role_icon_for_member(
        app=app, utub_id=unlocked_utub.id, user_id=user_id
    )

    set_utub_locked_state(app, locked_utub.id, True)
    login_user_to_home_page(app=app, page=page, user_id=user_id)

    unlocked_selector = f"{HPL.SELECTORS_UTUB}[utubid='{unlocked_utub.id}']"
    wait_for_element_presence(page=page, css_selector=unlocked_selector)

    # The unlocked deck selector shows its normal role icon and NOT the padlock.
    wait_until_visible_css_selector(
        page=page, css_selector=f"{unlocked_selector} {unlocked_role_icon}"
    )
    expect(page.locator(f"{unlocked_selector} {HPL.UTUB_LOCKED_ICON}")).to_have_count(0)

    # Establish the locked precondition: select the locked UTub first.
    select_utub_by_id(page=page, utub_id=locked_utub.id)
    assert_utub_selected(page=page, app=app, utub_id=locked_utub.id)
    expect(page.locator("body")).to_have_class(
        re.compile(rf"(^|\s){HPL.BODY_LOCKED_CLASS}(\s|$)")
    )

    # Selecting the unlocked UTub clears the locked affordances.
    select_utub_by_id(page=page, utub_id=unlocked_utub.id)
    assert_utub_selected(page=page, app=app, utub_id=unlocked_utub.id)
    expect(page.locator("body")).not_to_have_class(
        re.compile(rf"(^|\s){HPL.BODY_LOCKED_CLASS}(\s|$)")
    )
    expect(page.locator(HPL.URL_DECK_LOCK_ICON)).to_be_hidden()
