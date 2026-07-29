from typing import Generator, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend import db
from backend.models.urls import Urls
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from tests.conftest import AjaxFlaskLoginClient
from tests.utils_for_test import get_csrf_token, seed_distinct_stats_for_user_one

# Shared across account_and_settings tests (settings-link OAuth-only proof path
# and the change-password OAuth-only guard). Moved here from test_oauth_linking.py
# (Decision #7 / DD-11) so test_change_password.py can consume the fixture too.
_OAUTH_ONLY_USERNAME = "settingslinkoauthonly"
_OAUTH_ONLY_EMAIL = "settingslinkoauthonly@example.com"
_OAUTH_ONLY_GOOGLE_SUBJECT = "sub_settings_link_oauth_only_google"


def _seed_oauth_only_user(
    app: Flask, *, username: str, email: str, provider: str, subject: str
) -> None:
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password=None)
        user.oauth_identities.append(
            UserOAuthIdentity(provider=provider, provider_subject=subject)
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()


@pytest.fixture
def oauth_only_google_user_logged_in(
    app: Flask,
) -> Generator[Tuple[FlaskClient, str, Users, Flask], None, None]:
    """Seeds an email-validated, password-less user with a linked google
    identity, then logs them in via Flask-Login's test-client shortcut
    (mirrors ``tests/conftest.py:login_first_user_with_register``) — how the
    session was originally established is orthogonal to the endpoints under
    test."""
    _seed_oauth_only_user(
        app,
        username=_OAUTH_ONLY_USERNAME,
        email=_OAUTH_ONLY_EMAIL,
        provider="google",
        subject=_OAUTH_ONLY_GOOGLE_SUBJECT,
    )

    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user_to_login: Users = Users.query.filter_by(email=_OAUTH_ONLY_EMAIL).first()

    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_response = logged_in_client.get("/home")
        csrf_token_string = get_csrf_token(logged_in_response.get_data(), meta_tag=True)
        yield logged_in_client, csrf_token_string, user_to_login, app


@pytest.fixture
def logged_out_app(app_with_server_name: Flask) -> Generator[Flask, None, None]:
    with app_with_server_name.app_context():
        yield app_with_server_name


@pytest.fixture
def login_unvalidated_user(
    app: Flask, register_first_user
) -> Generator[Tuple[FlaskClient, Users, Flask], None, None]:
    """
    Registers the user with ID == 1, flips ``email_validated`` to ``False``,
    then logs them in via flask_login. Used to exercise the
    ``email_validation_required`` gate's redirect for authenticated-but-
    unvalidated users.
    """
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        unvalidated_user: Users = Users.query.get(1)
        unvalidated_user.email_validated = False
        db.session.commit()

    with app.test_client(user=unvalidated_user) as logged_in_client:
        yield logged_in_client, unvalidated_user, app


@pytest.fixture
def login_first_user_with_distinct_stats(
    app: Flask, register_multiple_users
) -> Generator[Tuple[FlaskClient, Users, Flask], None, None]:
    """Register users 1, 2, 3 and seed *mutually-distinct* per-user counts for
    user 1 so the Stats panel's cards can be asserted individually and a
    swapped/mislabeled card is caught:

      - **2** ``Utubs`` created by user 1 (each with a CREATOR membership row)
      - **3** ``Utubs`` created by others (2 by user 2, 1 by user 3) that user 1
        is a MEMBER of — keeps "member of" disjoint from "created"
      - **5** ``Utub_Urls`` added by user 1 (each backed by a unique ``Urls`` row)
      - **7** ``Utub_Tags`` created by user 1
      - **11** ``Utub_Url_Tags`` applied by user 1

    Plus three noise rows owned by user 2 / NULL to prove the per-user filter
    and the NULL-attributed exclusion (not merely the raw counts):

      - 1 ``Utub_Tags`` ``created_by=2``
      - 1 ``Utub_Urls`` ``user_id=2``
      - 1 ``Utub_Url_Tags`` ``user_id=None`` (legacy NULL attribution)

    Plus one ``CO_CREATOR`` membership on a UTub owned by user 2: the "member
    of" filter excludes only ``Member_Role.CREATOR``, so a ``CO_CREATOR``
    membership must still count — this row locks in that behavior and bumps
    "member of" from 3 to **4**.

    Logs user 1 in and yields the authenticated client.
    """
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        # Shared 2/3/5/7/11 seed block (mirrored by the settings UI test).
        distinct_stats_seed = seed_distinct_stats_for_user_one(label_prefix="user1")
        home_utub = distinct_stats_seed.home_utub
        user_one_utub_urls = distinct_stats_seed.user_one_utub_urls
        user_one_tags = distinct_stats_seed.user_one_tags

        # ---- Noise rows: prove the per-user filter + NULL exclusion ----
        # Tag created by user 2 — must not count toward user 1's tags_created.
        db.session.add(
            Utub_Tags(
                utub_id=home_utub.id,
                tag_string="user2-noise-tag",
                created_by=2,
            )
        )

        # URL added by user 2 — must not count toward user 1's urls_added.
        noise_url = Urls(
            normalized_url="https://user2-noise-url.example.com",
            current_user_id=2,
        )
        db.session.add(noise_url)
        db.session.flush()
        noise_utub_url = Utub_Urls()
        noise_utub_url.utub_id = home_utub.id
        noise_utub_url.url_id = noise_url.id
        noise_utub_url.user_id = 2
        noise_utub_url.url_title = "User2 noise URL"
        db.session.add(noise_utub_url)

        # Legacy NULL-attributed applied-tag row — must stay excluded from
        # user 1's tags_applied (proves NULL rows are excluded, not just
        # uncounted). Otherwise identical to a real user-1 application.
        db.session.add(
            Utub_Url_Tags(
                utub_id=home_utub.id,
                utub_url_id=user_one_utub_urls[0].id,
                utub_tag_id=user_one_tags[0].id,
                user_id=None,
            )
        )

        # CO_CREATOR membership on a UTub owned by user 2. The "member of"
        # filter excludes only Member_Role.CREATOR, so this co-ownership must
        # still count toward user 1's "member of" — bumping it from 3 to 4 and
        # locking in that the CREATOR-only exclusion is intentional.
        co_created_utub = Utubs(
            name="User2 co-created UTub",
            utub_creator=2,
            utub_description="",
        )
        db.session.add(co_created_utub)
        db.session.flush()
        db.session.add(
            Utub_Members(
                utub_id=co_created_utub.id,
                user_id=2,
                member_role=Member_Role.CREATOR,
            )
        )
        db.session.add(
            Utub_Members(
                utub_id=co_created_utub.id,
                user_id=1,
                member_role=Member_Role.CO_CREATOR,
            )
        )

        db.session.commit()

        user_to_login: Users = Users.query.get(1)

    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_client.get("/home")
        yield logged_in_client, user_to_login, app
