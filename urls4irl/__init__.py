from flask import Flask
from flask_session import Session, SqlAlchemySessionInterface
from flask_sqlalchemy import SQLAlchemy
from urls4irl.config import Config
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_cors import CORS

sess = Session()

<<<<<<< HEAD
if app.config["FLASK_ENV"] == "development":
    app.config["DEBUG"] = True
=======
db = SQLAlchemy()
migrate = Migrate(db=db, render_as_batch=True)
>>>>>>> backend

csrf = CSRFProtect()

<<<<<<< HEAD
"""
To get Flask-Migrate / alembic to work with SQLite, need to perform the following
steps as clarified in this answer:

https://stackoverflow.com/a/62651160/17951680

Because SQLite does not support ALTER tables.
"""

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(app, metadata=metadata)
migrate = Migrate(app, db, render_as_batch=True)

csrf = CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"  # Where to send user if they aren't logged in but try to access a logged in page
login_manager.login_message_category = "info"
=======
login_manager = LoginManager()
login_manager.login_view = 'users.login'  # Where to send user if they aren't logged in but try to access a logged in page
login_manager.login_message_category = 'info'
>>>>>>> backend

cors_sess = CORS()

<<<<<<< HEAD
from urls4irl import routes
=======
def create_app(config_class: Config = Config, testing:bool = False):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    sess.init_app(app)
    db.init_app(app)

    csrf.init_app(app)
    login_manager.init_app(app)

    cors_sess.init_app(app)

    from urls4irl.main.routes import main
    from urls4irl.utubs.routes import utubs
    from urls4irl.users.routes import users
    from urls4irl.urls.routes import urls
    from urls4irl.tags.routes import tags

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
>>>>>>> backend
