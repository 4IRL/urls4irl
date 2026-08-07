from flask_sqlalchemy import SQLAlchemy

from backend.cli.mock_constants import EMAIL_SUFFIX, TEST_USER_COUNT, USERNAME_BASE
from backend.models.user_preferences import (
    DateFormat,
    Density,
    SortOrder,
    Theme,
    User_Preferences,
    ViewMode,
)
from backend.models.users import User_Role, Users

ADMIN_MOCK_USERNAME = f"{USERNAME_BASE}1"


def generate_mock_users(db: SQLAlchemy, silent: bool = False):
    """
    Generates mock Users, adds them to database if not already added.

    Args:
        db (SQLAlchemy): Database engine and connection for committing mock data
    """
    for user_index in range(TEST_USER_COUNT):
        username = f"{USERNAME_BASE}{user_index + 1}"
        email = f"{username}{EMAIL_SUFFIX}"

        new_user = Users(username=username, email=email, plaintext_password=email)

        if Users.query.filter(Users.username == username).first() is not None:
            if not silent:
                print(f"Already added user with username: {username} | email: {email} ")

        else:
            if not silent:
                print(f"Adding test user with username: {username} | email: {email} ")

            new_user.email_validated = True
            if username == ADMIN_MOCK_USERNAME:
                new_user.role = User_Role.ADMIN

            db.session.add(new_user)
            # Cycle enum values by user index so the seed isn't all-defaults,
            # making the migration-roundtrip test's column assertions meaningful.
            # The back_populates relationship resolves the FK on commit, so no
            # explicit flush for new_user.id is needed.
            new_user.preferences = User_Preferences(
                theme=list(Theme)[user_index % len(Theme)],
                default_view=list(ViewMode)[user_index % len(ViewMode)],
                default_sort=list(SortOrder)[user_index % len(SortOrder)],
                density=list(Density)[user_index % len(Density)],
                date_format=list(DateFormat)[user_index % len(DateFormat)],
            )

    admin_user = Users.query.filter(Users.username == ADMIN_MOCK_USERNAME).first()
    if admin_user is not None and admin_user.role != User_Role.ADMIN:
        admin_user.role = User_Role.ADMIN
        if not silent:
            print(f"Promoted existing user '{ADMIN_MOCK_USERNAME}' to admin role")

    db.session.commit()
