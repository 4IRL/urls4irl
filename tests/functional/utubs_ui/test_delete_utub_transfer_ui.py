from flask import Flask
from playwright.sync_api import Page, expect
import pytest

from backend.utils.strings.user_strs import TRANSFER_INSTEAD_ACTION
from tests.functional.db_utils import (
    get_other_member_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.members_ui.playwright_utils import pick_new_owner
from tests.functional.playwright_login_utils import login_user_and_select_utub_by_name
from tests.functional.playwright_utils import (
    get_selected_utub_id,
    wait_then_click_element,
    wait_until_css_property,
    wait_until_hidden,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.utubs_ui


def _open_delete_modal_settled(*, page: Page) -> None:
    """Open the delete-UTub confirm modal and wait for its fade-in to settle.

    Gating subsequent clicks on opacity==1 avoids Bootstrap dropping an
    overlapping show/hide transition (mirrors the delete-UTub suite).
    """
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UTUB_DELETE)
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )


def _submit_confirm_modal(*, page: Page) -> None:
    """Gate on the modal fade-in settling (opacity==1) before clicking submit."""
    wait_until_css_property(
        page=page,
        css_selector=HPL.HOME_MODAL,
        css_property="opacity",
        expected_value="1",
    )
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_SUBMIT)


def test_delete_modal_shows_transfer_instead_for_owner_with_members(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner of a UTub that has at least one other member
    WHEN they open the delete-UTub confirm modal
    THEN the "Transfer instead" redirect button is shown, labeled accordingly
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    _open_delete_modal_settled(page=page)

    redirect_btn = page.locator(HPL.BUTTON_MODAL_REDIRECT)
    expect(redirect_btn).to_be_visible()
    expect(redirect_btn).to_have_text(TRANSFER_INSTEAD_ACTION)


def test_delete_modal_hides_transfer_instead_for_sole_owner(
    page: Page,
    create_test_utubs,
    provide_app: Flask,
):
    """
    GIVEN an owner of a UTub with no other members (sole owner)
    WHEN they open the delete-UTub confirm modal
    THEN the "Transfer instead" redirect button stays hidden
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    _open_delete_modal_settled(page=page)

    expect(page.locator(HPL.BUTTON_MODAL_REDIRECT)).to_be_hidden()


def test_transfer_instead_opens_picker_and_hides_delete_modal(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner has the delete-UTub modal open with "Transfer instead" available
    WHEN they click "Transfer instead"
    THEN the delete modal hides and the transfer picker opens in the members deck
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )

    _open_delete_modal_settled(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_REDIRECT)

    # The delete confirm modal hides, and the transfer picker renders its listbox.
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_until_visible_css_selector(page=page, css_selector=HPL.TRANSFER_PICKER_LISTBOX)


def test_transfer_instead_completes_transfer_utub_intact(
    page: Page,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN an owner reaches the transfer picker via the delete modal's "Transfer
        instead" button
    WHEN they pick a member, confirm, and submit
    THEN the UTub is NOT deleted (its selector remains) and ownership has moved to
        the chosen member (they become the diamond-fill owner)
    """
    app = provide_app

    user_id = 1
    utub_user_created = get_utub_this_user_created(app, user_id)
    other_member = get_other_member_in_utub(app, utub_user_created.id, user_id)
    with app.app_context():
        new_owner_id = other_member.id

    login_user_and_select_utub_by_name(
        app=app, page=page, user_id=user_id, utub_name=utub_user_created.name
    )
    utub_id = get_selected_utub_id(page=page)

    _open_delete_modal_settled(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_MODAL_REDIRECT)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)
    wait_until_visible_css_selector(page=page, css_selector=HPL.TRANSFER_PICKER_LISTBOX)

    # Pick the member + confirm (reopens the shared modal as the transfer confirm),
    # then submit.
    pick_new_owner(page=page, member_id=new_owner_id)
    _submit_confirm_modal(page=page)
    wait_until_hidden(page=page, css_selector=HPL.HOME_MODAL)

    # The UTub was NOT deleted — its selector is still present after the transfer.
    utub_selector = page.locator(f'{HPL.SELECTORS_UTUB}[utubid="{utub_id}"]')
    expect(utub_selector).to_be_visible()
    assert page.locator(f'{HPL.SELECTORS_UTUB}[utubid="{utub_id}"]').count() == 1

    # Ownership moved: the chosen member is now the diamond-fill owner.
    expect(
        page.locator(
            f'{HPL.BADGES_MEMBERS}[memberid="{new_owner_id}"] svg.bi-diamond-fill'
        )
    ).to_be_visible()
