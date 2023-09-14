from dotenv import load_dotenv
from os import environ, path
from urls4irl.utils.strings import CONFIG_ENVS

basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(basedir, ".env"))


class Config:
    """Set Flask config variables."""

    FLASK_DEBUG = environ.get("FLASK_DEBUG")
    SECRET_KEY = environ.get(CONFIG_ENVS.SECRET_KEY)
    SESSION_PERMANENT = "False"
    SESSION_TYPE = "sqlalchemy"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = environ.get(CONFIG_ENVS.DATABASE_URL_DEV)
    BASE_EMAIL = environ.get(CONFIG_ENVS.BASE_EMAIL)
    MAILJET_API_KEY = environ.get(CONFIG_ENVS.MAILJET_API_KEY)
    MAILJET_SECRET_KEY = environ.get(CONFIG_ENVS.MAILJET_SECRET_KEY)
    TESTING = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = environ.get(CONFIG_ENVS.DATABASE_URL_TEST)
