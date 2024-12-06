import jwt
from flask import current_app
from jwt import exceptions as JWTExceptions

from src.models.users import Users
from src.utils.strings.config_strs import CONFIG_ENVS
from src.utils.strings.email_validation_strs import EMAILS


def verify_token(token: str, token_key: str) -> tuple[Users | None, bool]:
    """
    Returns a valid user if one found, or None.
    Boolean indicates whether the token is expired or not.

    Args:
        token (str): The token to check
        token_key (str): The key of the token

    Returns:
        tuple[Users | None, bool]: Returns a User/None and Boolean
    """
    try:
        username_to_validate = jwt.decode(
            jwt=token,
            key=current_app.config[CONFIG_ENVS.SECRET_KEY],
            algorithms=[EMAILS.ALGORITHM],
        )

    except JWTExceptions.ExpiredSignatureError:
        return None, True

    except (
        RuntimeError,
        TypeError,
        JWTExceptions.DecodeError,
    ):
        return None, False

    return (
        Users.query.filter(
            Users.username == username_to_validate[token_key]
        ).first_or_404(),
        False,
    )
