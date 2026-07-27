from typing import Generator, List, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend import db
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from tests.conftest import AjaxFlaskLoginClient


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

    Logs user 1 in and yields the authenticated client.
    """
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        # 2 UTubs created by user 1, each with its own CREATOR membership row.
        user_one_utubs: List[Utubs] = []
        for utub_index in range(2):
            created_utub = Utubs(
                name=f"User1 UTub {utub_index}",
                utub_creator=1,
                utub_description="",
            )
            db.session.add(created_utub)
            db.session.flush()
            db.session.add(
                Utub_Members(
                    utub_id=created_utub.id,
                    user_id=1,
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
                    user_id=1,
                    member_role=Member_Role.MEMBER,
                )
            )

        # Everything below hangs off user 1's first created UTub.
        home_utub = user_one_utubs[0]

        # 5 Utub_Urls added by user 1, each backed by a unique Urls row (per the
        # standalone_url/url_id construction pattern at tests/conftest.py).
        user_one_utub_urls: List[Utub_Urls] = []
        for url_index in range(5):
            backing_url = Urls(
                normalized_url=f"https://user1-url-{url_index}.example.com",
                current_user_id=1,
            )
            db.session.add(backing_url)
            db.session.flush()
            utub_url = Utub_Urls()
            utub_url.utub_id = home_utub.id
            utub_url.url_id = backing_url.id
            utub_url.user_id = 1
            utub_url.url_title = f"User1 URL {url_index}"
            db.session.add(utub_url)
            db.session.flush()
            user_one_utub_urls.append(utub_url)

        # 7 Utub_Tags created by user 1.
        user_one_tags: List[Utub_Tags] = []
        for tag_index in range(7):
            created_tag = Utub_Tags(
                utub_id=home_utub.id,
                tag_string=f"user1-tag-{tag_index}",
                created_by=1,
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
                    user_id=1,
                )
            )

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

        db.session.commit()

        user_to_login: Users = Users.query.get(1)

    with app.test_client(user=user_to_login) as logged_in_client:
        logged_in_client.get("/home")
        yield logged_in_client, user_to_login, app
