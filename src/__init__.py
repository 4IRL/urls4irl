import os
import json
import secrets
from typing import Mapping

from flask import Flask, Response, abort, current_app, g, request, session, url_for
from flask_assets import Environment
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_session import Session
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from src import app_logger
from src.api_common.error_handler import (
    handle_403_response_from_csrf,
    handle_404_response,
    handle_429_response_default_ratelimit,
)
from src.db import db
from src.config import Config, ConfigProd
from src.extensions.email_sender.email_sender import EmailSender
from src.extensions.notifications.notifications import NotificationSender
from src.extensions.url_validation.url_validator import UrlValidator
from src.cli.short_urls import register_short_urls_cli
from src.cli.utils import register_utils_cli
from src.cli.mock_options import register_mocks_db_cli
from src.utils.bundle import prepare_bundler_for_js_files
from src.utils.strings.config_strs import CONFIG_ENVS

sess = Session()

migrate = Migrate(db=db, render_as_batch=True)

csrf = CSRFProtect()

login_manager = LoginManager()

email_sender = EmailSender()

url_validator = UrlValidator()

notification_sender = NotificationSender()

environment_assets = Environment()

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

    app_logger.init_app(app, show_test_logs)

    sess.init_app(app)
    db.init_app(app)

    csrf.init_app(app)
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

    from src.assets.routes import assets_bp
    from src.contact.routes import contact
    from src.members.routes import members
    from src.splash.routes import splash
    from src.system.routes import system
    from src.urls.routes import urls
    from src.users.routes import users
    from src.utubs.routes import utubs
    from src.tags.url_tag_routes import utub_url_tags
    from src.tags.utub_tag_routes import utub_tags

    @app.context_processor
    def asset_processor():
        return {CONFIG_ENVS.ASSET_VERSION: app.config[CONFIG_ENVS.ASSET_VERSION]}

    app.register_blueprint(assets_bp)
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
        from src.debug.routes import debug as debug_routes

        app.register_blueprint(debug_routes)

    register_mocks_db_cli(app)
    register_short_urls_cli(app)
    register_utils_cli(app)

    app.register_error_handler(404, handle_404_response)
    app.register_error_handler(CSRFError, handle_403_response_from_csrf)
    app.register_error_handler(429, handle_429_response_default_ratelimit)

    if not testing:
        # Import models to initialize migration scripts
        from src import models  # noqa: F401

        assert models
        migrate.init_app(app)

    relative_js_path = "static/scripts/components/**/*.js"
    js_path = os.path.join(app.root_path, relative_js_path)
    prepare_bundler_for_js_files(
        abs_js_path=js_path,
        relative_js_path=relative_js_path,
        app=app,
        assets=environment_assets,
        assets_url_prefix=assets_bp.url_prefix,
        is_testing_or_prod=(testing or production),
    )

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
        valid_fonts = "font-src 'self' " + f"{' '.join(valid_font_cdns)}; "
        valid_imgs = "img-src 'self' data:;"

        is_local = current_app.config.get("LOCAL", False)
        if is_local:
            vite_origin = "http://localhost:5173"
            vite_ws = "ws://localhost:5173"
            valid_script_cdns.append(vite_origin)
            valid_connect_sources.extend([vite_origin, vite_ws])

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
    @app.context_processor
    def vite_assets():
        def vite_asset(entrypoint):
            # 1. Local Mode: Point directly to the Vite container
            if app.config.get("LOCAL", False):
                return f"http://localhost:5173/{entrypoint}"

            # 2. Production/Dev Server: Read from the manifest.json
            if app.static_folder is None:
                return ""

            manifest_path = os.path.join(
                app.static_folder, "dist", ".vite", "manifest.json"
            )

            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                # Vite's manifest uses the relative path from the root
                file_path = manifest[entrypoint]["file"]
                return url_for("static", filename=f"dist/{file_path}")
            except (FileNotFoundError, KeyError):
                return ""  # Handle missing manifest gracefully

        return dict(vite_asset=vite_asset)
