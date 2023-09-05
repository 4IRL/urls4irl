from dotenv import load_dotenv
from os import environ, path
from urls4irl.utils import strings as U4I_STRINGS

basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(basedir, ".env"))


class Config:
    """Set Flask config variables."""

    FLASK_DEBUG = environ.get("FLASK_DEBUG")
    SECRET_KEY = environ.get(U4I_STRINGS.CONFIG_ENVS.SECRET_KEY)
    SESSION_PERMANENT = "False"
    SESSION_TYPE = "sqlalchemy"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = environ.get(U4I_STRINGS.CONFIG_ENVS.DATABASE_URL_DEV)
    TESTING = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = environ.get(U4I_STRINGS.CONFIG_ENVS.DATABASE_URL_TEST)
