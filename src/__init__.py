from flask import Flask
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_session import Session
from flask_wtf.csrf import CSRFProtect

from src.db import db
from src.config import Config, ConfigProd
from src.mocks.mock_options import register_mocks_db_cli
from src.utils.email_sender import EmailSender
from src.utils.error_handler import (
    handle_404_response,
    handle_429_response_default_ratelimit,
)

sess = Session()

migrate = Migrate(db=db, render_as_batch=True)

csrf = CSRFProtect()

login_manager = LoginManager()

cors_sess = CORS()

email_sender = EmailSender()


def create_app(config_class: Config = Config):
    testing = config_class.TESTING
    production = config_class.PRODUCTION
    config_class = ConfigProd if production else config_class
    app = Flask(__name__)
    app.config.from_object(config_class)

    sess.init_app(app)
    db.init_app(app)

    csrf.init_app(app)
    login_manager.init_app(app)

    cors_sess.init_app(app)

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["2/second", "100/minute"],
        default_limits_exempt_when=lambda: True if testing else False,
        on_breach=handle_429_response_default_ratelimit,
        storage_uri="redis://localhost:6379" if production else "memory://",
        storage_options={"socket_connect_timeout": 30},
    )

    limiter.init_app(app)

    email_sender.init_app(app)
    if production:
        email_sender.in_production()

    from src.splash.routes import splash
    from src.utubs.routes import utubs
    from src.users.routes import users
    from src.members.routes import members
    from src.urls.routes import urls
    from src.tags.routes import tags

    app.register_blueprint(splash)
    app.register_blueprint(utubs)
    app.register_blueprint(users)
    app.register_blueprint(members)
    app.register_blueprint(urls)
    app.register_blueprint(tags)
    register_mocks_db_cli(app)

    app.register_error_handler(404, handle_404_response)

    if not testing:
        migrate.init_app(app)

    with app.app_context():
        db.create_all()
        app.session_interface.db.create_all()

    return app
