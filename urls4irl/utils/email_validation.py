from os import environ, path
from dotenv import load_dotenv
from mailjet_rest import Client
from flask_login import login_required, current_user
from urls4irl.models import EmailValidation
from functools import wraps
from flask import session, url_for, redirect  
from urls4irl.utils.strings import STD_JSON_RESPONSE, EMAILS, EMAILS_FAILURE

basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(basedir, ".env"))

BASE_API_URL = "https://api.us.mailjet.com/"
EMAIL_SIGNATURE = "The urls4irl team"
MESSAGES, FROM, TO, EMAIL, NAME = "Messages", "From", "To", "Email", "Name"
SUBJECT, TEXTPART, HTMLPART =  "Subject", "TextPart", "HTMLPart"

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE

class EmailSender:
    def __init__(self):
        api_key = environ.get("MAILJET_API_KEY")
        api_secret = environ.get("MAILJET_SECRET_KEY")
        self._sender = environ.get("BASE_EMAIL")
        self._base =  BASE_API_URL       
        self._mailjet_client = Client(auth=(api_key, api_secret), version='v3.1')


    def send_account_email_confirmation(self, to_email: str, to_name: str):
        message = {
            MESSAGES: [
                self._message_builder(
                    to_email=to_email,
                    to_name=to_name,
                    subject="This is a Test Email from Python!",
                    textpart="Hello and welcome to a test email from Python!",
                    htmlpart="<p>Hello and welcome to a test email from Python!</p>"
                )
            ]
        }
        print()
        result = self._mailjet_client.send.create(data=message)
        print("Message sent.")

    def _to_builder(self, email: str, name: str) -> dict:
        return {
            EMAIL: email,
            NAME: name
        }

    def _from_builder(self) -> dict:
        return {
            EMAIL: self._sender,
            NAME: EMAIL_SIGNATURE
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
                FROM: from_block,
                TO: [to_block],
                SUBJECT: subject,
                TEXTPART: textpart,
                HTMLPART: htmlpart 
            }


def email_validation_required(func):
    @wraps(func)
    @login_required
    def decorated_view(*args, **kwargs):
        current_user_id = current_user.get_id()
        is_email_validated: bool = session.get(EMAILS.EMAIL_VALIDATED_SESS_KEY)

        if is_email_validated is None:
            # TODO: Instead of 404'ing, redirect for users who don't validate in case they don't have a row... maybe?
            current_user_email_validation: EmailValidation = EmailValidation.query.get_or_404(current_user_id)
            session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = current_user_email_validation.is_validated
            is_email_validated = session[EMAILS.EMAIL_VALIDATED_SESS_KEY]

        if not is_email_validated:
            return redirect(url_for("main.splash"))
        return func(*args, **kwargs)

    return decorated_view



if __name__ == "__main__":
    new_email_sender = EmailSender()
    new_email_sender.send_account_email_confirmation()
