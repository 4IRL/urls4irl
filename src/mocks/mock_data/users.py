from flask_sqlalchemy import SQLAlchemy

from src.mocks.mock_constants import EMAIL_SUFFIX, TEST_USER_COUNT, USERNAME_BASE
from src.models.email_validations import Email_Validations
from src.models.users import Users


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

            db.session.add(new_user)

            new_email_validation = Email_Validations(
                validation_token=new_user.get_email_validation_token()
            )
            new_email_validation.is_validated = True
            new_email_validation.user = new_user

            db.session.add(new_email_validation)

    db.session.commit()
