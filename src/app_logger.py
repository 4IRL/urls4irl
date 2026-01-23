from datetime import datetime
import json
import logging
import os
import re
import sys
import time
from typing import Optional
import uuid

from flask import Flask, Request, Response, current_app, g, has_request_context, request
from flask.logging import default_handler

from src.utils.all_routes import SYSTEM_ROUTES
from src.utils.strings.config_strs import CONFIG_ENVS

# ASCII Font color
END = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"

REQUEST_ID_PATTERN = re.compile(r"[^a-zA-Z0-9\-_]")


class RequestInfoFilter(logging.Filter):
    """Add request-specific information to log records."""

    def filter(self, record):
        record.request_id = getattr(g, "request_id", "-") if request else "-"
        record.remote_addr = getattr(g, "remote_addr", "-") if request else "-"
        record.user_agent = getattr(g, "user_agent", "-") if request else "-"
        record.module = request.endpoint if request and request.endpoint else "u4i"

        # Skip logging health endpoint
        return request.endpoint != SYSTEM_ROUTES.HEALTH


class StructuredJSONLoggingFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", "-"),
            "endpoint": request.endpoint if request and request.endpoint else "u4i",
        }

        # Add structured fields from extra dict
        excluded_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "stack_info",
            "request_id",
            "endpoint",
            "write_to_file",
        }

        for key, value in record.__dict__.items():
            if key not in excluded_attrs and not key.startswith("_"):
                log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


# Create a custom handler that creates new files daily
class DailyFileHandler(logging.FileHandler):
    def __init__(self, log_dir):
        self.log_dir = log_dir
        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)
        super().__init__(self._get_log_file_path(log_dir), mode="a")

    def _get_log_file_path(self, log_dir: str) -> str:
        """Generate log file path based on current date."""
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(log_dir, f"{today}_daily.log")

    def emit(self, record):
        current_file = self._get_log_file_path(self.log_dir)

        if self.baseFilename != current_file:
            self.close()
            self.baseFilename = current_file
            self.stream = self._open()

        super().emit(record)


def generate_request_id() -> str:
    return str(uuid.uuid4())[-12:]


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


def _setup_logger_for_cli(app: Flask):
    cli_logger = logging.getLogger("cli_logger")
    cli_logger.setLevel(logging.INFO)
    cli_logger.propagate = False  # Prevent going up to root logger

    cli_handler = logging.StreamHandler()
    cli_handler.setFormatter(
        logging.Formatter("%(message)s")
    )  # No timestamp, level, etc.
    cli_logger.addHandler(cli_handler)

    setattr(app, "cli_logger", cli_logger)


def configure_logging(app: Flask, is_production=False):
    """Configure the application's logging system with Flask-style text logs."""
    _setup_logger_for_cli(app)

    # First remove default handler
    app.logger.removeHandler(default_handler)

    # Set log level from config
    app.logger.setLevel(logging.INFO if app.config.get("PRODUCTION") else logging.DEBUG)

    # Create formatter for regular logs (everything besides initial request)
    regular_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(request_id)s] %(module)s: %(message)s"
    )

    # Create formatter for detailed logs on initial request (with user agent and remote addr)
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
        file_handler = DailyFileHandler(app.config.get(CONFIG_ENVS.LOG_DIR, "logs/"))
        file_handler.setFormatter(StructuredJSONLoggingFormatter())
        file_handler.addFilter(RequestInfoFilter())
        file_handler.addFilter(lambda record: getattr(record, "write_to_file", False))
        app.logger.addHandler(file_handler)

    # Store formatters for use in before_request logging
    setattr(app, "_detailed_formatter", detailed_formatter)

    # Set propagate to False since we're handling our own handlers
    app.logger.propagate = False

    # Disable Werkzeug's built-in logging to avoid duplication
    logging.getLogger("werkzeug").disabled = True

    # Silence gunicorn to avoid duplicates
    logging.getLogger("gunicorn.access").disabled = True


def _output_logs_for_ui_tests(level: int, message: str):
    request_id = getattr(g, "request_id", "-")
    remote_addr = getattr(request, "remote_addr", "-")
    module = request.endpoint if request.endpoint else "u4i"

    # Format exactly like your detailed formatter would
    level_name = logging.getLevelName(level)
    formatted = f"{level_name} [{request_id}] [{remote_addr}] {module}: {message}"

    # Write directly to stderr
    print(formatted, file=sys.stderr, flush=True)


def log_with_detailed_info(app: Flask, level: int, message: str):
    """Log a message with detailed request info (user agent and remote addr)."""
    # Temp swap formatters console handler

    handler = None
    for handler in app.logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            break

    if not handler:
        return

    original_formatter = handler.formatter
    handler.setFormatter(getattr(app, "_detailed_formatter"))
    app.logger.log(level, message)

    handler.setFormatter(original_formatter)


def sanitize_request_id(request_id: Optional[str], max_length: int = 12) -> str:
    """
    Sanitize request ID to prevent log injection.

    Returns a safe request ID or generates a new one if invalid.
    """
    if not request_id:
        return generate_request_id()

    # Remove any characters that aren't alphanumeric, hyphens, or underscores
    sanitized = REQUEST_ID_PATTERN.sub("", request_id)

    # Enforce length limits
    sanitized = sanitized[:max_length]

    # If sanitization left us with nothing useful, generate a new one
    if len(sanitized) < max_length:
        return generate_request_id()

    return sanitized


def setup_before_after_request_logging(app: Flask, show_ui_flask_logs: bool = False):
    @app.before_request
    def before_request():
        request_id = request.headers.get(CONFIG_ENVS.X_REQUEST_ID, None)
        g.request_id = sanitize_request_id(request_id)
        g.request_start_time = time.time()

        g.http_method = request.method
        g.query_params = (
            {k: v for k, v in request.args.items()} if request.args else None
        )
        g.remote_addr = getattr(request, "remote_addr", "-") if request else "-"
        g.content_type = request.content_type
        g.user_agent = getattr(request, "user_agent", "-") if request else "-"

        g.log_messages = []

        path = request.path
        g.path = path

        full_path = path + (
            f"?{request.query_string.decode()}" if request.query_string else ""
        )
        g.full_path = full_path

        method_colors = {
            "GET": f"{GREEN}",  # green
            "POST": f"{BLUE}",  # blue
            "DELETE": f"{RED}",  # red
            "PATCH": f"{YELLOW}",  # yellow
            "PUT": f"{YELLOW}",  # yellow
        }
        message = f"Request: {method_colors.get(request.method, '')}{request.method}{END} {full_path} "

        g._pre_log_message = f"Request: {request.method} {full_path} "

        if show_ui_flask_logs:
            _output_logs_for_ui_tests(logging.INFO, message)
            return

        log_with_detailed_info(app, logging.INFO, message)

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
            f"{GREEN}"
            if status_code < 400
            else f"{RED}" if status_code >= 500 else f"{YELLOW}"
        )

        additional_messages = safe_retrieve_logs()
        if additional_messages:
            app.logger.info(f"[BEGIN] {additional_messages} [END]")

        log_message = f"Response: {status_color}{status_code}{END} completed in {duration_ms:.2f}ms"

        if show_ui_flask_logs:
            _output_logs_for_ui_tests(level=logging.INFO, message=log_message)

        file_msg = f"{getattr(g, '_pre_log_message', '')}"
        file_msg += f" | {additional_messages} " if additional_messages else ""
        file_msg += f"| Response: {status_code} completed in {duration_ms:.2f}ms"

        app.logger.info(
            f"{log_message}",
            extra={
                "write_to_file": True,
                "log_type": "http_transaction",  # Mark this as the complete transaction
                "http_method": g.http_method,
                "path": g.path,
                "full_path": g.full_path,
                "query_params": g.query_params,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "remote_addr": g.remote_addr if g.remote_addr != "-" else None,
                "user_agent": g.user_agent if g.user_agent != "-" else None,
                "content_length": response.content_length,
                "content_type": g.content_type,
                "console": file_msg,
            },
        )

        return response

    @app.teardown_request
    def teardown_request(exception=None):
        if exception:
            app.logger.error(
                f"Request failed with error: {str(exception)}",
                exc_info=True,
                extra={
                    "write_to_file": True,
                    "error_type": type(exception).__name__,
                    "http_method": request.method if request else None,
                    "path": request.path if request else None,
                },
            )


def init_app(app: Flask, show_ui_test_logs: bool = False):
    configure_logging(app)
    setup_before_after_request_logging(app, show_ui_test_logs)


def safe_get_detailed_formatter(app: Flask) -> logging.Formatter | None:
    if not hasattr(app, "_detailed_formatter"):
        return
    detailed_formatter: logging.Formatter = getattr(app, "_detailed_formatter")
    return detailed_formatter


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


def info_log(log: str, extra: dict | None = None):
    if extra is None:
        extra = {}
    current_app.logger.info(msg=log, extra=extra)


def warning_log(log: str, extra: dict | None = None):
    if extra is None:
        extra = {}
    current_app.logger.warning(msg=log, extra=extra)


def critical_log(log: str, extra: dict | None = None):
    if extra is None:
        extra = {}
    current_app.logger.critical(msg=log, extra=extra)


def error_log(log: str, extra: dict | None = None):
    if extra is None:
        extra = {}
    current_app.logger.error(msg=log, extra=extra)


def turn_form_into_str_for_log(form_errors: dict[str, list[str]]) -> str:
    try:
        return " | ".join([f"{key}={val}" for key, val in form_errors.items()])
    except Exception:
        current_app.logger.exception("Unable to parse form data")
        return "Unable to parse form data"
