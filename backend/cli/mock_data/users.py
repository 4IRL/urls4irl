from flask_sqlalchemy import SQLAlchemy

from backend.cli.mock_constants import EMAIL_SUFFIX, TEST_USER_COUNT, USERNAME_BASE
from backend.models.users import User_Role, Users

ADMIN_MOCK_USERNAME = f"{USERNAME_BASE}1"


def generate_mock_users(db: SQLAlchemy, silent: bool = False):
    """
    Generates mock Users, adds them to database if not already added.

    Args:
        db (SQLAlchemy): Database engine and connection for committing mock data
    """
    for i in range(TEST_USER_COUNT):
        username = f"{USERNAME_BASE}{i + 1}"
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

    admin_user = Users.query.filter(Users.username == ADMIN_MOCK_USERNAME).first()
    if admin_user is not None and admin_user.role != User_Role.ADMIN:
        admin_user.role = User_Role.ADMIN
        if not silent:
            print(f"Promoted existing user '{ADMIN_MOCK_USERNAME}' to admin role")

    db.session.commit()
