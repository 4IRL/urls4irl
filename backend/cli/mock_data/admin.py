from flask_sqlalchemy import SQLAlchemy

from backend.cli.mock_constants import (
    EMAIL_SUFFIX,
    MOCK_ADMIN_USERNAME,
    MOCK_ADMIN_UTUB_NAME,
)
from backend.cli.mock_data.tags import generate_mock_tags
from backend.cli.mock_data.urls import generate_mock_urls
from backend.cli.mock_data.utubmembers import generate_mock_utubmembers
from backend.models.users import User_Role, Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs


def generate_mock_admin(db: SQLAlchemy, silent: bool = False):
    """Seed a dedicated, full-participant admin mock user (``u4i_admin1``).

    Opt-in only: this is never part of the default ``addmock``/``addmock all``
    seed, so the shared test seed (which the UI suite relies on) is left
    byte-for-byte unchanged. Intended to be run after ``flask addmock all`` on a
    local dev database.

    Creates the admin user and its own UTub, then reuses the existing dynamic
    (all-UTub, idempotent) member/URL/tag generators so the admin joins every
    existing UTub, every other mock user joins the admin's UTub, and the admin's
    UTub is populated with URLs and tags exactly like the other mock UTubs.

    Args:
        db (SQLAlchemy): Database engine and connection for committing mock data.
        silent (bool): Suppress per-row progress output when True.
    """
    email = f"{MOCK_ADMIN_USERNAME}{EMAIL_SUFFIX}"

    admin_user: Users = Users.query.filter(
        Users.username == MOCK_ADMIN_USERNAME
    ).first()
    if admin_user is None:
        admin_user = Users(
            username=MOCK_ADMIN_USERNAME, email=email, plaintext_password=email
        )
        admin_user.email_validated = True
        admin_user.role = User_Role.ADMIN
        db.session.add(admin_user)
        db.session.flush()
        if not silent:
            print(f"Adding admin mock user: {MOCK_ADMIN_USERNAME} | email: {email}")
    else:
        # Keep the role authoritative on a re-run in case it was changed.
        if admin_user.role != User_Role.ADMIN:
            admin_user.role = User_Role.ADMIN
        if not silent:
            print(f"Already added admin mock user: {MOCK_ADMIN_USERNAME}")

    admin_utub: Utubs = Utubs.query.filter(
        Utubs.name == MOCK_ADMIN_UTUB_NAME,
        Utubs.utub_creator == admin_user.id,
    ).first()
    if admin_utub is None:
        admin_utub = Utubs(
            name=MOCK_ADMIN_UTUB_NAME,
            utub_creator=admin_user.id,
            utub_description=f"Made by {admin_user.username}",
        )
        creator_member = Utub_Members()
        creator_member.member_role = Member_Role.CREATOR
        creator_member.user_id = admin_user.id
        creator_member.to_utub = admin_utub
        db.session.add(admin_utub)
        db.session.add(creator_member)
        if not silent:
            print(f"Adding admin UTub: {MOCK_ADMIN_UTUB_NAME}")
    elif not silent:
        print(f"Already added admin UTub: {MOCK_ADMIN_UTUB_NAME}")
    db.session.commit()

    # Reuse the dynamic generators (each iterates every UTub and is idempotent):
    # the admin joins every existing UTub, every user joins the admin's UTub, and
    # the admin's UTub receives the standard mock URLs and tags.
    generate_mock_utubmembers(db)
    generate_mock_urls(db)
    generate_mock_tags(db)
