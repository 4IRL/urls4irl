from json import dumps

from flask import render_template
from requests import Response
from mailjet_rest import Client
from mailjet_rest.client import ApiError, TimeoutError

from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.email_validation_strs import EMAILS
from src.utils.strings.config_strs import CONFIG_ENVS


# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


class EmailSender:
    def __init__(self):
        self._base = EMAILS.BASE_API_URL
        self._testing = False
        self._in_production = False

    def init_app(self, app):
        self._testing = app.testing
        app.extensions[EMAILS.EMAIL] = self
        self._sender = app.config[CONFIG_ENVS.BASE_EMAIL]

        api_key = app.config[CONFIG_ENVS.MAILJET_API_KEY]
        api_secret = app.config[CONFIG_ENVS.MAILJET_SECRET_KEY]
        self._mailjet_client = Client(auth=(api_key, api_secret), version="v3.1")

    def is_testing(self):
        return self._testing

    def in_production(self):
        self._in_production = True

    def is_production(self):
        return self._in_production

    def send_account_email_confirmation(
        self, to_email: str, to_name: str, confirmation_url: str
    ):
        message = {
            EMAILS.MESSAGES: [
                self._message_builder(
                    to_email=to_email,
                    to_name=to_name,
                    subject=EMAILS.ACCOUNT_CONFIRMATION_SUBJECT,
                    textpart=render_template(
                        "email_validation/email_confirmation.txt",
                        email_confirmation_url=confirmation_url,
                    ),
                    htmlpart=render_template(
                        "email_validation/email_confirmation.html",
                        email_confirmation_url=confirmation_url,
                    ),
                )
            ]
        }

        if self._testing:
            message[EMAILS.SANDBOXMODE] = True

        return self._mailjet_client.send.create(data=message)

    def send_password_reset_email(self, to_email: str, to_name: str, reset_url: str):
        message = {
            EMAILS.MESSAGES: [
                self._message_builder(
                    to_email=to_email,
                    to_name=to_name,
                    subject=EMAILS.PASSWORD_RESET_SUBJECT,
                    textpart=render_template(
                        "password_reset/reset_password_text_email.txt",
                        password_reset_url=reset_url,
                    ),
                    htmlpart=render_template(
                        "password_reset/reset_password_html_email.html",
                        password_reset_url=reset_url,
                    ),
                )
            ]
        }

        if self._testing:
            message[EMAILS.SANDBOXMODE] = True

        return self._send_or_fail(message)

    def _to_builder(self, email: str, name: str) -> dict:
        return {EMAILS.EMAIL: email, EMAILS.NAME: name}

    def _from_builder(self) -> dict:
        return {EMAILS.EMAIL: self._sender, EMAILS.NAME: EMAILS.EMAIL_SIGNATURE}

    def _message_builder(
        self, to_email: str, to_name: str, subject: str, textpart: str, htmlpart: str
    ) -> dict:
        to_block = self._to_builder(to_email, to_name)
        from_block = self._from_builder()

        return {
            EMAILS.FROM: from_block,
            EMAILS.TO: [to_block],
            EMAILS.SUBJECT: subject,
            EMAILS.TEXTPART: textpart,
            EMAILS.HTMLPART: htmlpart,
        }

    def _send_or_fail(self, message: dict[str, list[dict]]) -> Response:
        try:
            return self._mailjet_client.send.create(data=message)

        except (ApiError, TimeoutError) as e:
            # Can occur if not connected to internet, or on a limited service
            # TODO: Include the error output for logging but just return error here
            return self._mock_response_builder(500)

        except Exception as e:
            # TODO: Include the error output for logging but just return error here
            return self._mock_response_builder(500)

    @staticmethod
    def _mock_response_builder(status_code: int = 500) -> Response:
        mock_response = Response()
        mock_response.status_code = status_code
        mock_response.encoding = "utf-8"
        json_include = {
            EMAILS.MESSAGES: {EMAILS.MAILJET_ERRORS: EMAILS.ERROR_WITH_MAILJET}
        }
        mock_response._content = bytes(
            dumps(json_include, allow_nan=False), encoding="utf-8"
        )
        return mock_response
