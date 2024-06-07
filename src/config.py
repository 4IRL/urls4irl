from os import environ, path

from dotenv import load_dotenv

from src.utils.strings.config_strs import CONFIG_ENVS

# Must store .env file in base folder of project
basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(path.dirname(basedir), ".env"))


class Config:
    """Set Flask config variables."""

    FLASK_DEBUG = environ.get("FLASK_DEBUG")
    SECRET_KEY = environ.get(CONFIG_ENVS.SECRET_KEY)
    SESSION_PERMANENT = "False"
    SESSION_TYPE = "sqlalchemy"
    BASE_EMAIL = environ.get(CONFIG_ENVS.BASE_EMAIL)
    MAILJET_API_KEY = environ.get(CONFIG_ENVS.MAILJET_API_KEY)
    MAILJET_SECRET_KEY = environ.get(CONFIG_ENVS.MAILJET_SECRET_KEY)
    TESTING = False
    USE_LOCAL_JS_BUNDLES = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = environ.get(CONFIG_ENVS.DATABASE_URL_DEV)
    SQLALCHEMY_BINDS = {
        "dev": environ.get(
            CONFIG_ENVS.DATABASE_URL_DEV, default="sqlite://"
        ),  # When testing, give dev an in-memory database
        "test": environ.get(CONFIG_ENVS.DATABASE_URL_TEST),
    }

    def must_use_local_js_bundles():
        Config.USE_LOCAL_JS_BUNDLES = True


class ConfigProd(Config):
    SQLALCHEMY_BINDS = None


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = environ.get(CONFIG_ENVS.DATABASE_URL_TEST)
