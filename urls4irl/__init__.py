from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from urls4irl.config import Config
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_cors import CORS

app = Flask(__name__)
app.config.from_object(Config)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///urls4irl_db.db"
Session(app)

"""
To get Flask-Migrate / alembic to work with SQLite, need to perform the following
steps as clarified in this answer:

https://stackoverflow.com/a/62651160/17951680

Because SQLite does not support ALTER tables.
"""

convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(app, metadata=metadata)
migrate = Migrate(app, db, render_as_batch=True)

csrf = CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Where to send user if they aren't logged in but try to access a logged in page
login_manager.login_message_category = 'info'

CORS(app)

from urls4irl import routes
