from datetime import datetime
import logging
import os
import sys
import time
from typing import Optional
import uuid

from flask import Flask, Request, Response, current_app, g, has_request_context, request
from flask.logging import default_handler

from src.utils.strings.config_strs import CONFIG_ENVS

# ASCII Font color
END = "\033[0m"


class RequestInfoFilter(logging.Filter):
    """Add request-specific information to log records."""

    def filter(self, record):
        record.request_id = getattr(g, "request_id", "-") if request else "-"
        record.remote_addr = getattr(request, "remote_addr", "-") if request else "-"
        record.user_agent = getattr(request, "user_agent", "-") if request else "-"
        record.module = "u4i"
        if request and request.endpoint:
            record.module = request.endpoint
        return True


class DetailedRequestInfoFilter(logging.Filter):
    """Add detailed request-specific information to log records (includes user agent and remote addr)."""

    def filter(self, record):
        record.request_id = getattr(g, "request_id", "-") if request else "-"
        record.remote_addr = getattr(request, "remote_addr", "-") if request else "-"
        record.user_agent = getattr(request, "user_agent", "-") if request else "-"
        record.module = "u4i"
        if request and request.endpoint:
            record.module = request.endpoint
        return True


# Create a custom handler that creates new files daily
class DailyFileHandler(logging.FileHandler):
    def __init__(self, log_dir):
        self.log_dir = log_dir
        super().__init__(get_log_file_path(log_dir), mode="a")

    def emit(self, record):
        current_file = get_log_file_path(self.log_dir)

        if self.baseFilename != current_file:
            self.close()
            self.baseFilename = current_file
            self.stream = self._open()

        super().emit(record)


def generate_request_id() -> str:
    return str(uuid.uuid4())[-12:]


def get_log_file_path(log_dir: str) -> str:
    """Generate log file path based on current date."""
    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # Generate filename with current date
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(log_dir, f"{today}_daily.log")


def get_remote_addr(request: Request):
    # NOTE: Currently not in use as ProxyFix handles updating remote_addr, but could be useful
    if not has_request_context() or not request.headers:
        return "NOT-AVAILABLE"

    headers = {header.lower(): header_val for header, header_val in request.headers}
    cf_ip = headers.get(CONFIG_ENVS.CF_CONNECTING_IP.lower(), None)
    if cf_ip and isinstance(cf_ip, str):
        return cf_ip

    x_forwarded_for = headers.get(CONFIG_ENVS.X_FORWARDED_FOR.lower(), None)
    if x_forwarded_for and isinstance(x_forwarded_for, str):
        return x_forwarded_for.split(",")[0].strip()
    return request.remote_addr or "Unknown"


def configure_logging(app: Flask, is_production=False):
    """Configure the application's logging system with Flask-style text logs."""
    # First remove default handler
    app.logger.removeHandler(default_handler)

    # Set log level from config
    app.logger.setLevel(logging.INFO if app.config.get("PRODUCTION") else logging.DEBUG)

    # Create formatter with enhanced Flask style
    # Create formatter for regular logs (without user agent and remote addr)
    regular_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(request_id)s] %(module)s: %(message)s"
    )

    # Create formatter for detailed logs (with user agent and remote addr)
    detailed_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(request_id)s] [%(remote_addr)s] [%(user_agent)s] %(module)s: %(message)s"
    )

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.set_name(CONFIG_ENVS.U4I_LOGGER)
    console_handler.setFormatter(regular_formatter)
    console_handler.addFilter(RequestInfoFilter())
    app.logger.addHandler(console_handler)

    # Create file handler
    if not app.config.get("TESTING", False):
        log_dir = app.config.get(CONFIG_ENVS.LOG_DIR, "logs/")
        file_handler = DailyFileHandler(log_dir)
        file_handler.setFormatter(regular_formatter)
        file_handler.addFilter(RequestInfoFilter())
        app.logger.addHandler(file_handler)
        app._file_handler = file_handler  # type: ignore

    # Store formatters for use in before_request logging
    app._detailed_formatter = detailed_formatter  # type: ignore
    app._regular_formatter = regular_formatter  # type: ignore

    # Configure root logger for third-party libraries
    root_logger = logging.getLogger()
    root_logger.setLevel(app.config.get("LOG_LEVEL", logging.INFO))

    # Add file handler to root logger to catch all logs (all environments)
    if not app.config.get("TESTING", False):
        log_dir = app.config.get(CONFIG_ENVS.LOG_DIR, "logs")
        root_file_handler = DailyFileHandler(log_dir)
        root_file_handler.setFormatter(regular_formatter)
        root_file_handler.addFilter(RequestInfoFilter())
        root_logger.addHandler(root_file_handler)

    # Create unformatted logger
    raw_logger = logging.getLogger("raw_logger")
    raw_logger.setLevel(logging.INFO)
    raw_logger.propagate = False  # Prevent going up to root logger

    raw_handler = logging.StreamHandler()
    raw_handler.setFormatter(
        logging.Formatter("%(message)s")
    )  # No timestamp, level, etc.
    raw_logger.addHandler(raw_handler)

    if not app.config.get("TESTING", False):
        log_dir = app.config.get(CONFIG_ENVS.LOG_DIR, "logs")
        raw_file_handler = DailyFileHandler(log_dir)
        raw_file_handler.setFormatter(
            logging.Formatter("%(message)s")
        )  # No timestamp, level, etc.
        raw_file_handler.addFilter(RequestInfoFilter())
        raw_logger.addHandler(raw_file_handler)

    # Store in app context if needed later
    app.raw_logger = raw_logger  # type: ignore

    # Set propagate to False since we're handling our own handlers
    app.logger.propagate = False


def _output_logs_for_ui_tests(level: int, message: str):
    request_id = getattr(g, "request_id", "-")
    remote_addr = getattr(request, "remote_addr", "-")
    module = request.endpoint if request.endpoint else "u4i"

    # Format exactly like your detailed formatter would
    level_name = logging.getLevelName(level)
    formatted = f"{level_name} [{request_id}] [{remote_addr}] {module}: {message}"

    # Write directly to stderr
    print(formatted, file=sys.stderr, flush=True)


def log_with_detailed_info(
    app: Flask, level: int, message: str, show_ui_flask_logs: bool = False
):
    """Log a message with detailed request info (user agent and remote addr)."""
    # Check if we're in a test environment by seeing if the app logger has any StreamHandlers
    # If not, it means they've been removed for testing, so just use the regular logger

    has_stream_handlers = any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.NullHandler)
        for handler in app.logger.handlers
    )

    if not has_stream_handlers:
        # In integration test mode, just use the regular logger (which will be captured by caplog)
        app.logger.log(level, message)
        if show_ui_flask_logs:
            _output_logs_for_ui_tests(level, message)
        return

    # Create a temporary handler with detailed formatter
    temp_handler = logging.StreamHandler()
    temp_handler.setFormatter(app._detailed_formatter)  # type: ignore
    temp_handler.addFilter(DetailedRequestInfoFilter())

    # Create a temporary logger to avoid affecting the main logger
    temp_logger = logging.getLogger(f"temp_{generate_request_id()}")
    temp_logger.setLevel(app.logger.level)
    temp_logger.addHandler(temp_handler)

    # Create temporary file handler with detailed formatter (all environments)
    temp_file_handler = None
    if not app.config.get("TESTING", False):
        log_dir = app.config.get(CONFIG_ENVS.LOG_DIR, "logs")
        temp_file_handler = DailyFileHandler(log_dir)
        temp_file_handler.setFormatter(app._detailed_formatter)  # type: ignore
        temp_file_handler.addFilter(DetailedRequestInfoFilter())
        temp_logger.addHandler(temp_file_handler)

    temp_logger.propagate = False

    # Log the message
    temp_logger.log(level, message)

    # Clean up
    temp_handler.close()
    temp_logger.removeHandler(temp_handler)

    if temp_file_handler and not app.config.get("TESTING", False):
        temp_file_handler.close()
        temp_logger.removeHandler(temp_file_handler)


def setup_before_after_request_logging(app: Flask, show_ui_flask_logs: bool = False):
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
        message = f"Request: {method_colors.get(request.method, '')}{request.method}{END} {path} "
        log_with_detailed_info(app, logging.INFO, message, show_ui_flask_logs)

    @app.after_request
    def after_request(response: Optional[Response]):
        if response is None:
            warning_log("Received no response object")
            return response

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
        if show_ui_flask_logs:
            _output_logs_for_ui_tests(level=logging.INFO, message=log_message)

        return response

    @app.teardown_request
    def teardown_request(exception=None):
        if exception:
            app.logger.error(
                f"Request failed with error: {str(exception)}", exc_info=True
            )


def init_app(app: Flask, show_ui_test_logs: bool = False):
    configure_logging(app)
    setup_before_after_request_logging(app, show_ui_test_logs)

    # Disable Werkzeug's built-in logging to avoid duplication
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.disabled = True

    is_production = app.config.get(CONFIG_ENVS.PRODUCTION, False)
    is_dev_server = app.config.get(CONFIG_ENVS.DEV_SERVER, False)

    if is_production or is_dev_server:
        gunicorn_access_logger = logging.getLogger("gunicorn.access")
        gunicorn_access_logger.disabled = True
        return


def safe_get_request_id() -> str:
    if not g or not hasattr(g, "request_id"):
        return ""
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


def info_log(log: str):
    current_app.logger.info(msg=log)


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
