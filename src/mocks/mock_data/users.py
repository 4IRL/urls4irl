from flask_sqlalchemy import SQLAlchemy

from src.mocks.mock_constants import EMAIL_SUFFIX, TEST_USER_COUNT, USERNAME_BASE
from src.models.email_validations import Email_Validations
from src.models.users import Users


def generate_mock_users(db: SQLAlchemy):

    for i in range(TEST_USER_COUNT):
        username = f"{USERNAME_BASE}{i + 1}"
        email = f"{username}{EMAIL_SUFFIX}"

        new_user = Users(username=username, email=email, plaintext_password=email)

        if Users.query.filter(Users.username == username).first() is not None:
            print(f"Already added user with username: {username} | email: {email} ")

        else:
            print(f"Adding test user with username: {username} | email: {email} ")

            db.session.add(new_user)

            new_email_validation = Email_Validations(
                validation_token=new_user.get_email_validation_token()
            )
            new_email_validation.is_validated = True

            db.session.add(new_email_validation)

    db.session.commit()
