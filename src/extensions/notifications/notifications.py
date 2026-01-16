from enum import IntEnum
import requests
import threading
import logging

from flask import Flask

from src.app_logger import error_log, safe_add_log, safe_get_request_id, warning_log
from src.utils.strings.config_strs import CONFIG_ENVS


class NotificationType(IntEnum):
    THREADED_NOTIFICATIONS = 0
    CONTACT_FORM = 1


def _send_msg(
    url: str, msg: str, timeout: int, request_id: str, notif_type: NotificationType
) -> requests.Response | None:
    payload = {"content": msg}
    headers = {"Content-Type": "application/json"}
    response = None

    if notif_type == NotificationType.THREADED_NOTIFICATIONS:
        info_log = logging.info
        warn_log = logging.warning
        prefix = f"[{request_id}] "
    else:
        info_log = safe_add_log
        warn_log = warning_log
        prefix = ""

    try:
        response = requests.post(
            url=url, json=payload, headers=headers, timeout=timeout
        )
        info_log(f"{prefix}Successfully sent notification: {response.status_code=}")
        return response
    except requests.exceptions.RequestException as e:
        if response:
            warn_log(
                f"{prefix}Failed sending notification: {response.status_code=} | {e}"
            )
            return
        warn_log(
            f"{prefix}Received no response from notification request after RequestException | {e}"
        )
        return
    except Exception as e:
        if response:
            warn_log(
                f"{prefix}Failed sending notification: {response.status_code=} | {e}"
            )
            return
        warn_log(
            f"{prefix}Received no response from notification request after Exception | {e}"
        )
        return


class NotificationSender:
    def __init__(self):
        self._testing = False
        self._in_production = False
        self._in_development = False
        self._notification_url = ""
        self._contact_form_url = ""
        self.timeout = 20

    def init_app(self, app: Flask) -> None:
        app.extensions[CONFIG_ENVS.NOTIFICATION_MODULE] = self
        is_testing: bool = app.config.get("TESTING", False)
        is_production: bool = app.config.get("PRODUCTION", False)
        is_ui_testing: bool = app.config.get("UI_TESTING", False)
        self._notification_url = app.config.get(CONFIG_ENVS.NOTIFICATION_URL, "")
        self._contact_form_url = app.config.get(CONFIG_ENVS.CONTACT_US_URL, "")
        self._is_testing = is_testing
        self._in_development = not is_testing and not is_production
        self._in_production = (
            is_production and not is_testing and not self._in_development
        )
        self._is_ui_testing = is_ui_testing

    def _modify_msg_if_not_in_production(self, msg: str) -> str:
        if self._in_development or not self._in_production:
            return (
                "\n--------------- TESTING NOTIFICATION - DISREGARD ---------------\n"
                + msg
                + "\n--------------- TESTING NOTIFICATION - DISREGARD ---------------"
            )

        return msg

    def send_notification(
        self,
        msg: str = "",
    ) -> None:
        """Fire-and-forget POST request to send notification to Discord bot."""
        if self._is_ui_testing:
            return

        url = self._notification_url
        request_id = safe_get_request_id()
        final_msg = self._modify_msg_if_not_in_production(msg)

        args = [
            url,
            final_msg,
            self.timeout,
            request_id,
            NotificationType.THREADED_NOTIFICATIONS,
        ]

        thread = threading.Thread(target=_send_msg, args=args, daemon=True)
        thread.start()

    def send_contact_form_details(
        self, subject: str, content: str, contact_id: int, username: str | None
    ) -> bool:
        if self._is_ui_testing:
            return True

        url = self._contact_form_url
        request_id = safe_get_request_id()
        head_and_tail = ("=-=" * 15) + "\n"
        msg = (
            f"{head_and_tail}"
            + f"**SUBJECT**\n{subject}\n\n**CONTENT**\n{content}\n"
            + f"\n----------\n*Contact ID*: {contact_id}\n"
        )

        msg += (
            f"*Username*: {username}\n"
            if username is not None
            else "*Anonymous User*\n"
        )
        msg += f"{head_and_tail}"

        final_msg = self._modify_msg_if_not_in_production(msg)

        response = _send_msg(
            url,
            final_msg,
            self.timeout,
            request_id,
            notif_type=NotificationType.CONTACT_FORM,
        )

        if not response or response.status_code != 204 or response.text:
            log_msg = "Could not send contact form notification."

            if not response or not isinstance(response, requests.Response):
                log_msg += f" | {type(response)=}"
                error_log(log_msg)
                return False

            log_msg += f" | {response.status_code=}"
            log_msg += f" | {response.text=}"

            error_log(log_msg)
            return False

        safe_add_log("Sent contact form notification.")
        return True
