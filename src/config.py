from os import environ, path

from dotenv import load_dotenv

from src.utils.constants import CONFIG_CONSTANTS
from src.utils.strings.config_strs import CONFIG_ENVS as ENV

# Must store .env file in base folder of project
basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(path.dirname(basedir), ".env"))

IS_DOCKER = environ.get(ENV.DOCKER, default="false").lower() == "true"
IS_PRODUCTION = environ.get(ENV.PRODUCTION, default="false").lower() == "true"


def _build_db_uri(
    username: str | None, password: str | None, database: str | None, database_host: str
) -> str | None:
    if not all(
        (
            username,
            password,
            database,
        )
    ):
        return None
    return f"postgresql://{username}:{password}@{database_host}:5432/{database}"


POSTGRES_USER = environ.get(ENV.POSTGRES_USER)
POSTGRES_PASSWORD = environ.get(ENV.POSTGRES_PASSWORD)
POSTGRES_DB = environ.get(ENV.POSTGRES_DB)
POSTGRES_TEST_DB = environ.get(ENV.POSTGRES_TEST_DB, default=None)

PROD_DB_URI = (
    None
    if not IS_PRODUCTION
    else _build_db_uri(
        username=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB,
        database_host="db",
    )
)

TEST_DB_URI = _build_db_uri(
    username=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    database=POSTGRES_TEST_DB,
    database_host="localhost",
)

DEV_DB_URI = _build_db_uri(
    username=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    database=POSTGRES_DB,
    database_host="db" if IS_DOCKER else "localhost",
)


class Config:
    """Set Flask config variables."""

    PRODUCTION = environ.get("PRODUCTION", default="false").lower() == "true"
    USE_LOCAL_JS_BUNDLES = (
        environ.get("USE_LOCAL_BUNDLES", default="false").lower() == "true"
    )
    FLASK_RUN_PORT = environ.get("FLASK_RUN_PORT", default="5000")
    FLASK_RUN_HOST = environ.get("FLASK_RUN_HOST", default=None)
    FLASK_DEBUG = environ.get("FLASK_DEBUG")
    SECRET_KEY = environ.get(ENV.SECRET_KEY)
    SESSION_PERMANENT = "False"
    SESSION_TYPE = "sqlalchemy"
    WTF_CSRF_TIME_LIMIT = (
        CONFIG_CONSTANTS.CSRF_EXPIRATION_SECONDS
    )  # Six hours until CSRF expiration
    BASE_EMAIL = environ.get(ENV.BASE_EMAIL)
    MAILJET_API_KEY = environ.get(ENV.MAILJET_API_KEY)
    MAILJET_SECRET_KEY = environ.get(ENV.MAILJET_SECRET_KEY)
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = DEV_DB_URI
    SQLALCHEMY_BINDS = {
        "dev": (
            "sqlite://" if TESTING else DEV_DB_URI
        ),  # When testing, give dev an in-memory database
        "test": (
            "sqlite://" if IS_DOCKER else TEST_DB_URI
        ),  # Currently, not testing in local docker containers
    }
    REDIS_URI = environ.get(ENV.REDIS_URI, default="memory://")


class ConfigProd(Config):
    SQLALCHEMY_BINDS = {
        "prod": PROD_DB_URI,
    }
    SQLALCHEMY_DATABASE_URI = PROD_DB_URI
    REDIS_URI = environ.get(ENV.REDIS_URI)


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_BINDS = {"test": TEST_DB_URI}
    SQLALCHEMY_DATABASE_URI = TEST_DB_URI
