import os
import json
import secrets
from typing import Mapping, NotRequired, TypedDict

from flask import Flask, Response, abort, current_app, g, request, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_session import Session
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from backend import app_logger
from backend.api_common.error_handler import (
    handle_403_response_from_csrf,
    handle_404_response,
    handle_429_response_default_ratelimit,
)
from backend.db import db
from backend.config import Config, ConfigProd
from backend.extensions.email_sender.email_sender import EmailSender
from backend.extensions.metrics.writer import MetricsWriter
from backend.extensions.notifications.notifications import NotificationSender
from backend.extensions.url_validation.url_validator import UrlValidator
from backend.cli.metrics import register_metrics_cli
from backend.cli.mock_options import register_mocks_db_cli
from backend.cli.openapi import register_openapi_cli
from backend.cli.short_urls import register_short_urls_cli
from backend.cli.utils import register_utils_cli
from backend.utils.strings.config_strs import CONFIG_ENVS


class ViteManifestEntry(TypedDict):
    file: str
    css: NotRequired[list[str]]
    imports: NotRequired[list[str]]


def _read_manifest(manifest_path: str) -> dict[str, ViteManifestEntry]:
    """Return parsed Vite manifest JSON, or {} on failure."""
    try:
        with open(manifest_path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _collect_css_from_manifest(
    manifest: dict[str, ViteManifestEntry], entrypoint: str
) -> list[str]:
    """Walk manifest from entrypoint, collecting all CSS paths (incl. shared chunks)."""
    css_files: list[str] = []
    visited: set[str] = set()

    def collect(key: str) -> None:
        if key in visited or key not in manifest:
            return
        visited.add(key)
        for imported in manifest[key].get("imports", []):
            collect(imported)
        css_files.extend(manifest[key].get("css", []))

    collect(entrypoint)
    return css_files


sess = Session()

migrate = Migrate(db=db, render_as_batch=True)

csrf = CSRFProtect()

login_manager = LoginManager()

email_sender = EmailSender()

url_validator = UrlValidator()

notification_sender = NotificationSender()

metrics_writer = MetricsWriter()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["20/second", "100/minute"],
    application_limits=["20000/hour", "5000/15minutes"],
)


def create_app(
    config_class: type[Config] = Config, show_test_logs: bool = False
) -> Flask | None:
    testing = config_class.TESTING
    production = config_class.PRODUCTION
    if testing and production:
        print("ERROR: Cannot be both production and testing environment")
        return

    app = Flask(__name__)
    app.config.from_object(ConfigProd if production else config_class)
    app.config[CONFIG_ENVS.TESTING_OR_PROD] = testing or production

    # Handle None objects to prevent Flask-SQLAlchemy 3 from crashing
    if app.config.get("SQLALCHEMY_ENGINE_OPTIONS") is None:
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}

    app_logger.init_app(app, show_test_logs)

    sess.init_app(app)
    db.init_app(app)

    csrf.init_app(app)
    metrics_writer.init_app(app)
    login_manager.init_app(app)

    # Configure limiter with app-specific settings
    storage_options: Mapping = {"socket_connect_timeout": 30}
    limiter._storage_uri = app.config[CONFIG_ENVS.REDIS_URI]
    limiter._storage_options = storage_options
    limiter.enabled = not testing
    limiter.init_app(app)

    if production or app.config.get(CONFIG_ENVS.DEV_SERVER, False):
        # NOTE: Handle both the nginx reverse proxy, and Cloudflare as a reverse proxy
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=2, x_proto=2, x_host=2, x_prefix=2)

    if testing:
        test_url_val = UrlValidator()
        test_notif_send = NotificationSender()
        test_email_sender = EmailSender()
        test_url_val.init_app(app)
        test_notif_send.init_app(app)
        test_email_sender.init_app(app)
        app_test_setup(app)
    else:
        url_validator.init_app(app)
        notification_sender.init_app(app)
        email_sender.init_app(app)

    if production:
        email_sender.in_production()

    from backend.contact.routes import contact
    from backend.members.routes import members
    from backend.splash.routes import splash
    from backend.system.routes import system
    from backend.urls.routes import urls
    from backend.users.routes import users
    from backend.utubs.routes import utubs
    from backend.tags.url_tag_routes import utub_url_tags
    from backend.tags.utub_tag_routes import utub_tags

    @app.context_processor
    def asset_processor():
        return {CONFIG_ENVS.ASSET_VERSION: app.config[CONFIG_ENVS.ASSET_VERSION]}

    app.register_blueprint(contact)
    app.register_blueprint(members)
    app.register_blueprint(splash)
    app.register_blueprint(system)
    app.register_blueprint(urls)
    app.register_blueprint(users)
    app.register_blueprint(utubs)
    app.register_blueprint(utub_url_tags)
    app.register_blueprint(utub_tags)

    if not (testing or production):
        from backend.debug.routes import debug as debug_routes

        app.register_blueprint(debug_routes)

    register_metrics_cli(app)
    register_mocks_db_cli(app)
    register_openapi_cli(app)
    register_short_urls_cli(app)
    register_utils_cli(app)

    app.register_error_handler(404, handle_404_response)
    app.register_error_handler(CSRFError, handle_403_response_from_csrf)
    app.register_error_handler(429, handle_429_response_default_ratelimit)

    if not testing:
        # Import models to initialize migration scripts
        from backend import models  # noqa: F401

        assert models
        migrate.init_app(app)

    add_security_headers(app)
    init_vite_app(app)
    return app


def add_security_headers(app: Flask):
    @app.context_processor
    def nonce_processor():
        if "nonce" not in session:
            session["nonce"] = secrets.token_urlsafe(16)
        g.nonce = session["nonce"]
        return {"nonce": g.nonce}

    # Keep the before_request for the CSP headers
    @app.before_request
    def set_nonce():
        if "nonce" not in session:
            session["nonce"] = secrets.token_urlsafe(16)
        g.nonce = session["nonce"]

    @app.after_request
    def _add_security_headers(response: Response):
        if "nonce" not in session:
            session["nonce"] = secrets.token_urlsafe(16)
        g.nonce = session["nonce"]

        valid_script_cdns = [
            "https://code.jquery.com",
            "https://cdn.jsdelivr.net",
            "https://static.cloudflareinsights.com",
        ]

        valid_connect_sources = ["'self'", "https://cloudflareinsights.com"]

        valid_style_cdns = (
            "https://code.jquery.com",
            "https://cdn.jsdelivr.net",
            "https://maxcdn.bootstrapcdn.com",
            "https://fonts.googleapis.com",
            "https://stackpath.bootstrapcdn.com",
        )

        valid_font_cdns = (
            "https://fonts.gstatic.com",
            "https://maxcdn.bootstrapcdn.com",
        )

        # Check for Vite dev server and add to CSP before constructing CSP strings
        use_vite_dev = current_app.config.get("VITE_DEV_SERVER", False)
        if use_vite_dev:
            vite_url = current_app.config.get("VITE_URL", "http://localhost:5173")
            # Parse URL to construct WebSocket URL
            from urllib.parse import urlparse

            parsed = urlparse(vite_url)
            vite_origin = f"{parsed.scheme}://{parsed.netloc}"
            # Use wss:// for HTTPS, ws:// for HTTP
            ws_scheme = "wss" if parsed.scheme == "https" else "ws"
            vite_ws = f"{ws_scheme}://{parsed.netloc}"
            valid_script_cdns.append(vite_origin)
            valid_connect_sources.extend([vite_origin, vite_ws])
            # Vite dev server injects CSS as <style> elements via HMR
            valid_style_cdns = valid_style_cdns + (vite_origin,)
            valid_font_cdns = valid_font_cdns + (vite_origin,)

        # Construct CSP strings after Vite URL is added
        valid_scripts = (
            "script-src 'self' "
            + f"'nonce-{g.nonce}' "
            + f"{' '.join(valid_script_cdns)}; "
        )
        valid_styles = (
            "style-src 'self' "
            + f"'nonce-{g.nonce}' "
            + f"{' '.join(valid_style_cdns)}; "
        )
        valid_style_elems = "style-src-attr 'unsafe-inline'; "
        if use_vite_dev:
            # style-src has a nonce which causes browsers to ignore 'unsafe-inline'.
            # style-src-elem overrides style-src for <style> elements AND <link> stylesheets,
            # so it must include all allowed origins plus 'unsafe-inline' for Vite's
            # dynamically injected <style> tags in dev mode.
            valid_style_elems += (
                "style-src-elem 'self' 'unsafe-inline' "
                + f"{' '.join(valid_style_cdns)}; "
            )
        valid_fonts = "font-src 'self' " + f"{' '.join(valid_font_cdns)}; "
        valid_imgs = "img-src 'self' data:;"
        valid_connects = f"connect-src {' '.join(valid_connect_sources)}; "

        response.headers[CONFIG_ENVS.CONTENT_SECURITY_POLICY] = (
            "default-src 'none'; "
            + valid_connects
            + "manifest-src 'self'; "
            + valid_scripts
            + valid_styles
            + valid_style_elems
            + valid_fonts
            + valid_imgs
            + "form-action 'self'; "
            + "base-uri 'none'; "
            + "frame-ancestors 'none'; "
        )

        response.headers[CONFIG_ENVS.X_CONTENT_TYPE_OPTIONS] = "nosniff"
        response.headers[CONFIG_ENVS.X_FRAME_OPTIONS] = "DENY"
        response.headers[CONFIG_ENVS.REFERRER_POLICY] = (
            "strict-origin-when-cross-origin"
        )
        response.headers[CONFIG_ENVS.CROSS_ORIGIN_RESOURCE_POLICY] = "same-origin"
        return response


def app_test_setup(app: Flask):
    @app.before_request
    def force_rate_limit():
        if app.config.get("TESTING") and request.headers.get(
            "X-Force-Rate-Limit", None
        ):
            app_logger.error_log(log="RATE LIMITED")
            abort(429)

        if app.config.get("TESTING") and request.args.get("force_rate_limit", None):
            abort(429)


def init_vite_app(app: Flask):
    manifest_path = os.path.join(app.static_folder, "dist", ".vite", "manifest.json")

    @app.context_processor
    def vite_assets():
        def vite_asset(entrypoint: str) -> str:
            # 1. Vite Dev Server Mode: Point directly to the Vite dev server
            if app.config.get("VITE_DEV_SERVER", False):
                vite_url = app.config.get("VITE_URL", "https://localhost:5173")
                return f"{vite_url}/{entrypoint}"

            # 2. Production/Dev Server: Read from the manifest.json
            manifest = _read_manifest(manifest_path)
            try:
                file_path = manifest[entrypoint]["file"]
                return url_for("static", filename=f"dist/{file_path}")
            except KeyError:
                return ""

        def vite_asset_static(entrypoint: str) -> str:
            """
            Always use manifest-based assets, never Vite dev server.
            Use for error pages that must work in all contexts (e.g., Selenium tests).
            """
            manifest = _read_manifest(manifest_path)
            try:
                file_path = manifest[entrypoint]["file"]
                return url_for("static", filename=f"dist/{file_path}")
            except KeyError:
                return ""

        def vite_css_assets(entrypoint: str) -> list[str]:
            """Return CSS URLs for an entry point (production only; dev server injects via JS)."""
            if app.config.get("VITE_DEV_SERVER", False):
                return []  # Vite HMR injects CSS via JS in dev mode
            manifest = _read_manifest(manifest_path)
            css_paths = _collect_css_from_manifest(manifest, entrypoint)
            return [url_for("static", filename=f"dist/{f}") for f in css_paths]

        return dict(
            vite_asset=vite_asset,
            vite_asset_static=vite_asset_static,
            vite_css_assets=vite_css_assets,
        )
