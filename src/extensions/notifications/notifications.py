import requests
import threading
import logging

from flask import Flask

from src.app_logger import safe_get_request_id
from src.utils.strings.config_strs import CONFIG_ENVS


def _send_msg(url: str, msg: str, timeout: int, request_id: str):
    payload = {"content": msg}
    headers = {"Content-Type": "application/json"}
    response = None
    try:
        response = requests.post(
            url=url, json=payload, headers=headers, timeout=timeout
        )
        logging.info(
            f"[{request_id}] Successfully sent notification: {response.status_code=}"
        )
    except requests.exceptions.RequestException as e:
        if response:
            logging.warning(
                f"[{request_id}] Failed sending notification: {response.status_code=} | {e}"
            )
            return
        logging.warning(
            f"[{request_id}] Received no response from notification request after RequestException | {e}"
        )
    except Exception as e:
        if response:
            logging.warning(
                f"[{request_id}] Failed sending notification: {response.status_code=} | {e}"
            )
            return
        logging.warning(
            f"[{request_id}] Received no response from notification request after Exception | {e}"
        )


class NotificationSender:
    def __init__(self):
        self._testing = False
        self._in_production = False
        self._in_development = False
        self._notification_url = ""
        self.timeout = 20

    def init_app(self, app: Flask) -> None:
        app.extensions[CONFIG_ENVS.NOTIFICATION_MODULE] = self
        is_testing: bool = app.config.get("TESTING", False)
        is_production: bool = app.config.get("PRODUCTION", False)
        is_ui_testing: bool = app.config.get("UI_TESTING", False)
        self._notification_url = app.config.get(CONFIG_ENVS.NOTIFICATION_URL, "")
        self._is_testing = is_testing
        self._in_development = not is_testing and not is_production
        self._in_production = (
            is_production and not is_testing and not self._in_development
        )
        self._is_ui_testing = is_ui_testing

    def send_notification(
        self,
        msg: str = "",
    ) -> None:
        """Fire-and-forget POST request to send notification to Discord bot."""
        if self._is_ui_testing:
            return

        url = self._notification_url
        request_id = safe_get_request_id()
        if self._in_development or not self._in_production:
            msg = (
                "\n--------------- TESTING NOTIFICATION - DISREGARD---------------\n"
                + msg
                + "\n--------------- TESTING NOTIFICATION - DISREGARD---------------"
            )

        args = [url, msg, self.timeout, request_id]

        thread = threading.Thread(target=_send_msg, args=args, daemon=True)
        thread.start()
