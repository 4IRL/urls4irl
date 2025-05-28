import logging
import time
import uuid

from flask import Flask, Response, current_app, g, request
from flask.logging import default_handler

from src.utils.strings.config_strs import CONFIG_ENVS

# ASCII Font color
END = "\033[0m"


class RequestInfoFilter(logging.Filter):
    """Add request-specific information to log records."""

    def filter(self, record):
        record.request_id = getattr(g, "request_id", "-")
        record.remote_addr = getattr(request, "remote_addr", "-") if request else "-"
        record.module = "u4i"
        if request and request.endpoint:
            record.module = request.endpoint
        return True


def generate_request_id() -> str:
    return str(uuid.uuid4())[-12:]


def configure_logging(app: Flask, is_production=False):
    """Configure the application's logging system with Flask-style text logs."""
    # First remove default handler
    app.logger.removeHandler(default_handler)

    # Set log level from config
    app.logger.setLevel(logging.INFO if app.config.get("PRODUCTION") else logging.DEBUG)

    # Create formatter with enhanced Flask style
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(request_id)s] [%(remote_addr)s] %(module)s: %(message)s"
    )

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.set_name(CONFIG_ENVS.U4I_LOGGER)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RequestInfoFilter())
    app.logger.addHandler(console_handler)

    # Configure root logger for third-party libraries
    root_logger = logging.getLogger()
    root_logger.setLevel(app.config.get("LOG_LEVEL", logging.INFO))

    # Set propagate to False since we're handling our own handlers
    app.logger.propagate = False


def setup_before_request_logging(app: Flask):
    @app.before_request
    def before_request():
        g.request_id = request.headers.get(
            CONFIG_ENVS.X_REQUEST_ID, generate_request_id()
        )
        g.request_start_time = time.time()
        g.log_messages = []

        path = request.path
        path += f"?{request.query_string.decode()}" if request.query_string else ""

        method_colors = {
            "GET": "\033[92m",  # green
            "POST": "\033[94m",  # blue
            "DELETE": "\033[91m",  # red
            "PATCH": "\033[93m",  # yellow
            "PUT": "\033[93m",  # yellow
        }
        app.logger.info(
            f"Request: {method_colors.get(request.method, '')}{request.method}{END} {path} "
        )

    @app.after_request
    def after_request(response: Response):
        duration_ms = (
            (time.time() - g.request_start_time) * 1000
            if hasattr(g, "request_start_time")
            else -1
        )

        g_request_id = g.request_id if hasattr(g, "request_id") else "-1"
        response.headers[CONFIG_ENVS.X_REQUEST_ID] = g_request_id

        status_code = response.status_code
        status_color = (
            "\033[92m"
            if status_code < 400
            else "\033[91m" if status_code >= 500 else "\033[93m"
        )

        additional_messages = safe_retrieve_logs()
        if additional_messages:
            app.logger.info(f"[BEGIN] {additional_messages} [END]")

        log_message = f"Response: {status_color}{status_code}{END} completed in {duration_ms:.2f}ms"

        app.logger.info(f"{log_message}")

        return response

    @app.teardown_request
    def teardown_request(exception=None):
        if exception:
            app.logger.error(
                f"Request failed with error: {str(exception)}", exc_info=True
            )


def init_app(app: Flask):
    configure_logging(app)
    setup_before_request_logging(app)

    # Disable Werkzeug's built-in logging to avoid duplication
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.disabled = True


def safe_get_request_id():
    if not g or not hasattr(g, "request_id"):
        return
    return g.request_id


def safe_add_log(log: str):
    if not g or not hasattr(g, "log_messages"):
        return
    g.log_messages.append(log)


def safe_add_many_logs(logs: list[str]):
    if not g or not hasattr(g, "log_messages"):
        return
    g.log_messages += logs


def safe_retrieve_logs() -> str:
    if not g or not hasattr(g, "log_messages"):
        return ""
    return " | ".join([val for val in g.log_messages])


def warning_log(log: str):
    current_app.logger.warning(msg=log)


def critical_log(log: str):
    current_app.logger.critical(msg=log)


def error_log(log: str):
    current_app.logger.error(msg=log)


def turn_form_into_str_for_log(form_errors: dict[str, list[str]]) -> str:
    try:
        return " | ".join([f"{key}={val}" for key, val in form_errors.items()])
    except Exception:
        current_app.logger.exception("Unable to parse form data")
        return "Unable to parse form data"
