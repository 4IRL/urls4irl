
from flask import render_template
from mailjet_rest import Client
from urls4irl.utils.strings import STD_JSON_RESPONSE, EMAILS, CONFIG_ENVS


# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


class EmailSender:
    def __init__(self):
        self._base = EMAILS.BASE_API_URL      
        self._testing = False


    def init_app(self, app):
        self._testing = app.testing
        app.extensions[EMAILS.EMAIL] = self
        self._sender = app.config[CONFIG_ENVS.BASE_EMAIL]

        api_key = app.config[CONFIG_ENVS.MAILJET_API_KEY]
        api_secret = app.config[CONFIG_ENVS.MAILJET_SECRET_KEY]
        self._mailjet_client = Client(auth=(api_key, api_secret), version='v3.1')


    def send_account_email_confirmation(self, to_email: str, to_name: str, confirmation_url: str):
        message = {
            EMAILS.MESSAGES: [
                self._message_builder(
                    to_email=to_email,
                    to_name=to_name,
                    subject=EMAILS.ACCOUNT_CONFIRMATION_SUBJECT,
                    textpart=render_template("emails/email_confirmation.txt", email_confirmation_url=confirmation_url),
                    htmlpart=render_template("emails/email_confirmation.html", email_confirmation_url=confirmation_url)
                )
            ]
        }

        if self._testing:
            message[EMAILS.SANDBOXMODE] = True
            
        return self._mailjet_client.send.create(data=message)


    def _to_builder(self, email: str, name: str) -> dict:
        return {
            EMAILS.EMAIL: email,
            EMAILS.NAME: name
        }


    def _from_builder(self) -> dict:
        return {
            EMAILS.EMAIL: self._sender,
            EMAILS.NAME: EMAILS.EMAIL_SIGNATURE
        }


    def _message_builder(
            self, 
            to_email: str, 
            to_name: str, 
            subject: str, 
            textpart: str, 
            htmlpart: str
        ) -> dict:
        
        to_block = self._to_builder(to_email, to_name)
        from_block = self._from_builder()
        
        return {
                EMAILS.FROM: from_block,
                EMAILS.TO: [to_block],
                EMAILS.SUBJECT: subject,
                EMAILS.TEXTPART: textpart,
                EMAILS.HTMLPART: htmlpart 
            }

