import requests
from os import environ, path
from dotenv import load_dotenv
import json

basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(basedir, ".env"))

class EmailSender:
    def __init__(self, key: str, email: str):
        self._api_key = key
        self._email = email
        self._base = "https://api.brevo.com/v3/"
        self._headers = {
            "content-type": "application/json",
            "api-key": self._api_key
        }

    def get_contacts(self):
        uri = self._base + "contacts"
        response = requests.get(
            url=uri,
            headers=self._headers,
            data=json.dumps({
                "email": self._email
            })
        )

        print(response)

if __name__ == "__main__":
    new_email_sender = EmailSender(environ.get("BREVO_EMAIL_API_KEY"), environ.get("BASE_EMAIL"))
    new_email_sender.get_contacts()
