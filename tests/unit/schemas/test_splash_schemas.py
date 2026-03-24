import pytest
from pydantic import ValidationError

from backend.utils.constants import USER_CONSTANTS
from backend.utils.strings.reset_password_strs import RESET_PASSWORD
from backend.utils.strings.splash_form_strs import EMAILS_NOT_IDENTICAL

pytestmark = pytest.mark.unit


class TestLoginRequest:
    def test_valid_login(self):
        from backend.schemas.requests.splash import LoginRequest

        req = LoginRequest.model_validate(
            {"username": "testuser", "password": "mypassword123"}
        )
        assert req.username == "testuser"
        assert req.password == "mypassword123"

    def test_missing_username_raises(self):
        from backend.schemas.requests.splash import LoginRequest

        with pytest.raises(ValidationError) as exc_info:
            LoginRequest.model_validate({"password": "mypassword123"})
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "username" for err in errors)

    def test_missing_password_raises(self):
        from backend.schemas.requests.splash import LoginRequest

        with pytest.raises(ValidationError) as exc_info:
            LoginRequest.model_validate({"username": "testuser"})
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "password" for err in errors)

    def test_username_too_short_raises(self):
        from backend.schemas.requests.splash import LoginRequest

        with pytest.raises(ValidationError) as exc_info:
            LoginRequest.model_validate({"username": "ab", "password": "mypassword123"})
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "username" for err in errors)

    def test_username_too_long_raises(self):
        from backend.schemas.requests.splash import LoginRequest

        with pytest.raises(ValidationError) as exc_info:
            LoginRequest.model_validate(
                {"username": "a" * 21, "password": "mypassword123"}
            )
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "username" for err in errors)

    def test_username_whitespace_stripped(self):
        from backend.schemas.requests.splash import LoginRequest

        req = LoginRequest.model_validate(
            {"username": "  testuser  ", "password": "mypassword123"}
        )
        assert req.username == "testuser"


class TestRegisterRequest:
    def _valid_payload(self, **overrides):
        payload = {
            "username": "testuser",
            "email": "test@example.com",
            "confirmEmail": "test@example.com",
            "password": "a" * USER_CONSTANTS.MIN_PASSWORD_LENGTH,
            "confirmPassword": "a" * USER_CONSTANTS.MIN_PASSWORD_LENGTH,
        }
        payload.update(overrides)
        return payload

    def test_valid_register(self):
        from backend.schemas.requests.splash import RegisterRequest

        req = RegisterRequest.model_validate(self._valid_payload())
        assert req.username == "testuser"
        assert req.email == "test@example.com"

    def test_username_whitespace_stripped(self):
        from backend.schemas.requests.splash import RegisterRequest

        req = RegisterRequest.model_validate(
            self._valid_payload(username="  testuser  ")
        )
        assert req.username == "testuser"

    def test_mismatched_email_raises(self):
        from backend.schemas.requests.splash import RegisterRequest

        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest.model_validate(
                self._valid_payload(confirmEmail="other@example.com")
            )
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "confirmEmail" for err in errors)
        assert any(EMAILS_NOT_IDENTICAL in str(err["msg"]) for err in errors)

    def test_mismatched_password_raises(self):
        from backend.schemas.requests.splash import RegisterRequest

        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest.model_validate(
                self._valid_payload(confirmPassword="differentpassword")
            )
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "confirmPassword" for err in errors)
        assert any(
            RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL in str(err["msg"]) for err in errors
        )

    def test_username_too_short_raises(self):
        from backend.schemas.requests.splash import RegisterRequest

        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest.model_validate(self._valid_payload(username="ab"))
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "username" for err in errors)

    def test_username_too_long_raises(self):
        from backend.schemas.requests.splash import RegisterRequest

        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest.model_validate(self._valid_payload(username="a" * 21))
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "username" for err in errors)

    def test_invalid_email_format_no_spurious_confirm_error(self):
        """When email is invalid format and confirmEmail matches it,
        only email format error should appear — no spurious confirmEmail mismatch."""
        from backend.schemas.requests.splash import RegisterRequest

        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest.model_validate(
                self._valid_payload(email="notanemail", confirmEmail="notanemail")
            )
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"][0] == "email"

    def test_password_too_short_raises(self):
        from backend.schemas.requests.splash import RegisterRequest

        short_pw = "a" * (USER_CONSTANTS.MIN_PASSWORD_LENGTH - 1)
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest.model_validate(
                self._valid_payload(password=short_pw, confirmPassword=short_pw)
            )
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "password" for err in errors)

    def test_password_too_long_raises(self):
        from backend.schemas.requests.splash import RegisterRequest

        long_pw = "a" * (USER_CONSTANTS.MAX_PASSWORD_LENGTH + 1)
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest.model_validate(
                self._valid_payload(password=long_pw, confirmPassword=long_pw)
            )
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "password" for err in errors)


class TestForgotPasswordRequest:
    def test_valid_email(self):
        from backend.schemas.requests.splash import ForgotPasswordRequest

        req = ForgotPasswordRequest.model_validate({"email": "user@example.com"})
        assert req.email == "user@example.com"

    def test_invalid_email_raises(self):
        from backend.schemas.requests.splash import ForgotPasswordRequest

        with pytest.raises(ValidationError) as exc_info:
            ForgotPasswordRequest.model_validate({"email": "Cat"})
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "email" for err in errors)

    def test_missing_email_raises(self):
        from backend.schemas.requests.splash import ForgotPasswordRequest

        with pytest.raises(ValidationError) as exc_info:
            ForgotPasswordRequest.model_validate({})
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "email" for err in errors)


class TestResetPasswordRequest:
    def test_valid_reset(self):
        from backend.schemas.requests.splash import ResetPasswordRequest

        req = ResetPasswordRequest.model_validate(
            {"newPassword": "a" * 12, "confirmNewPassword": "a" * 12}
        )
        assert req.newPassword == "a" * 12

    def test_mismatched_passwords_raises(self):
        from backend.schemas.requests.splash import ResetPasswordRequest

        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordRequest.model_validate(
                {"newPassword": "a" * 12, "confirmNewPassword": "b" * 12}
            )
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "confirmNewPassword" for err in errors)
        assert any(
            RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL in str(err["msg"]) for err in errors
        )

    def test_password_too_short_raises(self):
        from backend.schemas.requests.splash import ResetPasswordRequest

        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordRequest.model_validate(
                {"newPassword": "short", "confirmNewPassword": "short"}
            )
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "newPassword" for err in errors)

    def test_password_too_long_raises(self):
        from backend.schemas.requests.splash import ResetPasswordRequest

        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordRequest.model_validate(
                {"newPassword": "a" * 65, "confirmNewPassword": "a" * 65}
            )
        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "newPassword" for err in errors)

    def test_short_password_no_spurious_confirm_error(self):
        """When newPassword fails length validation and confirmNewPassword matches it,
        only length error should appear — no spurious confirmNewPassword mismatch."""
        from backend.schemas.requests.splash import ResetPasswordRequest

        with pytest.raises(ValidationError) as exc_info:
            ResetPasswordRequest.model_validate(
                {"newPassword": "short", "confirmNewPassword": "short"}
            )
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"][0] == "newPassword"
