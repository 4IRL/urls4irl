from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from src.config import Config
from src.utils.email_sender import EmailSender

sess = Session()

db = SQLAlchemy()
migrate = Migrate(db=db, render_as_batch=True)

csrf = CSRFProtect()

login_manager = LoginManager()

cors_sess = CORS()

email_sender = EmailSender()


def create_app(
    config_class: Config = Config,
    testing: bool = False,
    production: bool = False,
    use_local_js_bundles: bool = False,
):
    config_class.must_use_local_js_bundles() if use_local_js_bundles else None
    app = Flask(__name__)
    app.config.from_object(config_class)

    sess.init_app(app)
    db.init_app(app)

    csrf.init_app(app)
    login_manager.init_app(app)

    cors_sess.init_app(app)

    email_sender.init_app(app)
    if production:
        email_sender.in_production()

    from src.main.routes import main
    from src.utubs.routes import utubs
    from src.users.routes import users
    from src.urls.routes import urls
    from src.tags.routes import tags

    app.register_blueprint(main)
    app.register_blueprint(utubs)
    app.register_blueprint(users)
    app.register_blueprint(urls)
    app.register_blueprint(tags)

    if not testing:
        migrate.init_app(app)

    with app.app_context():
        db.create_all()
        app.session_interface.db.create_all()

    return app
