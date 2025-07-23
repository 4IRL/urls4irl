from flask import Flask

from src.extensions.email_sender.email_sender import EmailSender
from src.extensions.notifications.notifications import NotificationSender
from src.extensions.url_validation.url_validator import UrlValidator
from src.utils.strings.config_strs import CONFIG_ENVS
from src.utils.strings.email_validation_strs import EMAILS
from src.utils.strings.url_validation_strs import URL_VALIDATION


def safe_get_notif_sender(app: Flask) -> NotificationSender:
    notif_sender: NotificationSender | None = app.extensions.get(
        CONFIG_ENVS.NOTIFICATION_MODULE, None
    )
    if notif_sender is None:
        notif_sender = NotificationSender()
        notif_sender.init_app(app)
    return notif_sender


def safe_get_email_sender(app: Flask) -> EmailSender:
    email_sender: EmailSender | None = app.extensions.get(EMAILS.EMAIL, None)
    if email_sender is None:
        email_sender = EmailSender()
        email_sender.init_app(app)
    return email_sender


def safe_get_url_validator(app: Flask) -> UrlValidator:
    url_validator: UrlValidator | None = app.extensions.get(
        URL_VALIDATION.URL_VALIDATION_MODULE, None
    )
    if url_validator is None:
        url_validator = UrlValidator()
        url_validator.init_app(app)
    return url_validator
