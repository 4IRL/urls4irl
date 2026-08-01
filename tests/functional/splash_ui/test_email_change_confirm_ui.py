"""Playwright UI tests for the change-email confirm-link outcome banner
(Phase 3, DD-11 / DD-14).

Covers both DD-9 render paths of the ``EmailChangeStatusBanner``:

* a **logged-out** browser opening a real confirm link lands on the splash page
  with the success banner (login-clause copy), and the pending email is actually
  swapped into the live column; and
* an **already-logged-in** browser that lands on splash carrying the
  confirm-outcome param is forwarded to ``/home`` (DD-9), where the banner
  renders with the login-clause-free (authenticated) copy (DD-15).

Tokens are minted directly via the Step-1 model helpers rather than driving the
full settings START endpoint, mirroring how ``test_oauth_confirm_link_ui.py``
seeds its own users instead of replaying an upstream flow.
"""

from __future__ import annotations

import re

from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.users import Users
from backend.splash.services.change_email import (
    EMAIL_CHANGE_STATUS_QUERY_PARAM,
    EMAIL_CHANGE_STATUS_SUCCESS,
)
from backend.utils.strings.user_strs import (
    EMAIL_CHANGE_SUCCESS,
    EMAIL_CHANGE_SUCCESS_AUTHENTICATED,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import SplashPageLocators as SPL
from tests.functional.playwright_utils import (
    current_base_url,
    login_user_to_home_page,
)

pytestmark = pytest.mark.splash_ui

_PASSWORD = "P@ssword123!"

_LOGGED_OUT_USERNAME = "changeemailconfirmuser"
_LOGGED_OUT_EMAIL = "changeemailconfirmuser@example.com"
_LOGGED_OUT_PENDING = "changeemailconfirmuser.new@example.com"

_VIEWER_USERNAME = "changeemailhomeviewer"
_VIEWER_EMAIL = "changeemailhomeviewer@example.com"

_SUBJECT_USERNAME = "changeemailhomesubject"
_SUBJECT_EMAIL = "changeemailhomesubject@example.com"
_SUBJECT_PENDING = "changeemailhomesubject.new@example.com"


def _seed_validated_user(
    app: Flask, *, username: str, email: str, password: str
) -> int:
    """Create a committed, email-validated password user and return its id."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=password)
        user.email_validated = True
        db.session.add(user)
        db.session.commit()
        return user.id


def _seed_user_with_pending_email_and_token(
    app: Flask, *, username: str, email: str, pending_email: str, password: str
) -> str:
    """Create a validated user, stage ``pending_email`` on it, and return a real
    change-email confirm token minted from that staged value (Step-1 helpers).

    Minted with the shared app's SECRET_KEY / test DB, which the in-process built
    server also uses, so the token verifies and the swap persists.
    """
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=password)
        user.email_validated = True
        db.session.add(user)
        db.session.commit()
        user.stage_email_change(pending_email)
        db.session.commit()
        return user.get_email_change_token()


def test_confirm_link_logged_out_lands_on_splash_with_success_banner(
    page: Page, provide_app: Flask
):
    """
    GIVEN a user with a staged pending email and a real confirm token, and a
        logged-out browser
    WHEN the browser opens ``/confirm-email-change/<token>``
    THEN it lands on the splash page carrying the success outcome code, the
        ``EmailChangeStatusBanner`` shows the DD-12 success copy with
        ``alert-success``, and the pending email has been swapped into the live
        ``Users.email`` column (pending cleared).
    """
    token = _seed_user_with_pending_email_and_token(
        provide_app,
        username=_LOGGED_OUT_USERNAME,
        email=_LOGGED_OUT_EMAIL,
        pending_email=_LOGGED_OUT_PENDING,
        password=_PASSWORD,
    )

    base_url = current_base_url(page=page)
    page.goto(f"{base_url}/confirm-email-change/{token}")

    expect(page).to_have_url(
        re.compile(
            rf"/\?{EMAIL_CHANGE_STATUS_QUERY_PARAM}={EMAIL_CHANGE_STATUS_SUCCESS}$"
        )
    )
    banner = page.locator(SPL.EMAIL_CHANGE_STATUS_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_text(EMAIL_CHANGE_SUCCESS)
    expect(banner).to_have_class(re.compile(r"alert-success"))

    with provide_app.app_context():
        confirmed = Users.query.filter_by(username=_LOGGED_OUT_USERNAME).first()
        assert confirmed is not None
        assert confirmed.email == _LOGGED_OUT_PENDING
        assert confirmed.pending_email is None


def test_confirm_link_forwards_logged_in_browser_to_home_banner(
    page: Page, provide_app: Flask
):
    """
    GIVEN an already-logged-in browser and a real confirm token for a change (DD-9/DD-14)
    WHEN the browser opens the confirm link and the confirm route redirects to
        splash carrying the success param
    THEN splash_page() forwards the still-authenticated browser to ``/home``
        (DD-9), where the banner renders with the login-clause-free authenticated
        copy (DD-15) and ``alert-success``.

    Why the viewing session belongs to a DIFFERENT user than the token's subject:
    the confirm route invalidates every web session of the token's OWN user
    (DD-3, ``sessions_invalidated_at``) and always redirects to splash, so a user
    confirming THEIR OWN change is logged out and lands on splash — never /home.
    Using a separate, untouched logged-in viewer keeps a session alive across the
    confirm redirect so the splash->home forward (the behavior under test) is
    actually reachable. This is a mechanism test of the forward, not a realistic
    end-user journey.
    """
    viewer_id = _seed_validated_user(
        provide_app,
        username=_VIEWER_USERNAME,
        email=_VIEWER_EMAIL,
        password=_PASSWORD,
    )
    token = _seed_user_with_pending_email_and_token(
        provide_app,
        username=_SUBJECT_USERNAME,
        email=_SUBJECT_EMAIL,
        pending_email=_SUBJECT_PENDING,
        password=_PASSWORD,
    )

    login_user_to_home_page(app=provide_app, page=page, user_id=viewer_id)
    base_url = current_base_url(page=page)
    page.goto(f"{base_url}/confirm-email-change/{token}")

    expect(page).to_have_url(
        re.compile(
            rf"/home\?{EMAIL_CHANGE_STATUS_QUERY_PARAM}={EMAIL_CHANGE_STATUS_SUCCESS}$"
        )
    )
    banner = page.locator(HPL.EMAIL_CHANGE_STATUS_BANNER)
    expect(banner).to_be_visible()
    expect(banner).to_have_text(EMAIL_CHANGE_SUCCESS_AUTHENTICATED)
    expect(banner).to_have_class(re.compile(r"alert-success"))
