"""Coarse-pointer (mobile) negative coverage for the desktop hover tooltips.

Desktop hover tooltips are gated on ``isCoarsePointer()`` in two independent
places, and this is the only automated proof that BOTH gates hold:

* ``initTooltips()`` (``frontend/lib/tooltips.ts``) returns before creating any
  instance for the static Jinja-rendered deck/create-form buttons.
* ``applyHoverTooltip()`` returns before stamping any ``data-bs-*`` attribute or
  creating an instance for the TS-rendered, per-card/per-badge buttons.

The accessible name is deliberately NOT gated — an icon-only button needs a name
on touch too — so each case asserts the exact ``aria-label`` survives while no
Bootstrap Tooltip instance is ever created.
"""

from flask import Flask
import pytest
from playwright.sync_api import Page

from backend.utils.constants import STRINGS
from tests.functional.db_utils import (
    get_url_in_utub,
    get_url_tag_id_and_tag_string_on_url_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    get_selected_url,
    wait_for_element_presence,
    wait_then_click_element,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.playwright_utils import (
    get_tag_badge_selector_on_selected_url_by_tag_id,
)

pytestmark = pytest.mark.mobile_ui

# Truthy only when Bootstrap actually holds a Tooltip instance for the element —
# the same probe the desktop twin of this check uses in
# test_create_utub_ui.py::test_utub_submit_btn_tooltip_instance_before_form_opened.
_HAS_TOOLTIP_INSTANCE_JS = "element => !!window.bootstrap.Tooltip.getInstance(element)"


def test_hover_tooltips_suppressed_on_coarse_pointer(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
):
    """
    Tests that no hover tooltip is created on a coarse-pointer device.

    GIVEN a user on a coarse-pointer (mobile) device viewing a URL with a tag
    WHEN the static create-form button, a per-tag delete "x", and a URL-card
         update button are inspected and hovered
    THEN no Bootstrap Tooltip instance exists, no ``data-bs-toggle`` is stamped,
         and no tooltip bubble appears — while every one of those buttons keeps
         its exact ``aria-label``
    """
    page = page_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    url_id = url_in_utub.id
    url_tag_id, tag_string = get_url_tag_id_and_tag_string_on_url_in_utub(
        app, utub_id, url_id
    )

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=user_id_for_test, utub_id=utub_id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    # --- initTooltips() gate ------------------------------------------------
    # On a fine pointer the ready-time sweep gives this still-hidden create-form
    # button a live instance (see
    # test_create_utub_ui.py::test_utub_submit_btn_tooltip_instance_before_form_opened).
    # On coarse pointer the gate returns before creating anything.
    utub_submit_btn = wait_for_element_presence(
        page=page, css_selector=HPL.BUTTON_UTUB_SUBMIT_CREATE
    )
    assert utub_submit_btn.evaluate(_HAS_TOOLTIP_INSTANCE_JS) is False
    assert utub_submit_btn.get_attribute("aria-label") == STRINGS.CREATE_UTUB_TOOLTIP

    # --- applyHoverTooltip() gate: Group D (per-tag delete "x") -------------
    wait_then_click_element(
        page=page, css_selector=f"{HPL.ROWS_URLS}[utuburlid='{url_id}']"
    )
    assert get_selected_url(page=page) is not None

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=url_tag_id
    )
    delete_tag_selector = f"{tag_badge_selector} {HPL.BUTTON_TAG_DELETE}"

    # Tapping the tag is the touch equivalent of the desktop hover reveal.
    wait_then_click_element(page=page, css_selector=tag_badge_selector)
    wait_until_visible_css_selector(page=page, css_selector=delete_tag_selector)

    delete_tag_btn = page.locator(delete_tag_selector).first
    assert delete_tag_btn.get_attribute("data-bs-toggle") is None
    # The per-tag accessible name diverges from the shared bubble copy, and that
    # divergence must survive on touch too.
    assert (
        delete_tag_btn.get_attribute("aria-label")
        == f"{STRINGS.REMOVE_URL_TAG_TOOLTIP} {tag_string}"
    )
    delete_tag_btn.hover()
    assert delete_tag_btn.evaluate(_HAS_TOOLTIP_INSTANCE_JS) is False
    assert_not_visible_css_selector(
        page=page, css_selector=f"{HPL.BUTTON_TAG_DELETE}{HPL.TOOLTIP_SUFFIX}"
    )

    # --- applyHoverTooltip() gate: Group C (URL-card update confirm) --------
    # The consolidated mobile edit button opens both the title and string forms.
    wait_then_click_element(
        page=page,
        css_selector=f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_UPDATE}",
    )
    string_submit_selector = (
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}"
    )
    wait_until_visible_css_selector(page=page, css_selector=string_submit_selector)

    string_submit_btn = page.locator(string_submit_selector).first
    assert string_submit_btn.get_attribute("data-bs-toggle") is None
    assert (
        string_submit_btn.get_attribute("aria-label")
        == STRINGS.CONFIRM_URL_EDIT_TOOLTIP
    )
    string_submit_btn.hover()
    assert string_submit_btn.evaluate(_HAS_TOOLTIP_INSTANCE_JS) is False
    assert_not_visible_css_selector(
        page=page,
        css_selector=f"{HPL.BUTTON_URL_STRING_SUBMIT_UPDATE}{HPL.TOOLTIP_SUFFIX}",
    )
