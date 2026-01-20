from os import environ, path
from time import time
from urllib.parse import quote

from cachelib import FileSystemCache
from dotenv import load_dotenv
from redis import Redis

from src.utils.constants import CONFIG_CONSTANTS
from src.utils.db_uri_builder import build_db_uri
from src.utils.strings.config_strs import CONFIG_ENVS as ENV

# Must store .env file in base folder of project
basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(path.dirname(basedir), ".env"))

IS_DOCKER = environ.get(ENV.DOCKER, default="false").lower() == "true"
IS_PRODUCTION = environ.get(ENV.PRODUCTION, default="false").lower() == "true"
IS_DEV_SERVER = environ.get(ENV.DEV_SERVER, default="false").lower() == "true"
NOTIFICATION_URL = environ.get(ENV.NOTIFICATION_URL, default="")
CONTACT_US_URL = environ.get(ENV.CONTACT_US_URL, default="")

POSTGRES_USER = environ.get(ENV.POSTGRES_USER)
POSTGRES_PASSWORD = environ.get(ENV.POSTGRES_PASSWORD)
POSTGRES_DB = environ.get(ENV.POSTGRES_DB)
POSTGRES_TEST_DB = environ.get(ENV.POSTGRES_TEST_DB, default=None)

ASSET_VERSION = environ.get(ENV.ASSET_VERSION, default=str(int(time())))

DEV_DB_URI = build_db_uri(
    username=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    database=POSTGRES_DB,
    database_host="db" if IS_DOCKER else "localhost",
)

PROD_DB_URI = (
    build_db_uri(
        username=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        database=POSTGRES_DB,
        database_host="db",
    )
    if IS_PRODUCTION
    else DEV_DB_URI
)


TEST_DB_URI = build_db_uri(
    username=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    database=POSTGRES_TEST_DB,
    database_host="test-db" if IS_DOCKER else "localhost",
)


TEST_REDIS_URI = environ.get(ENV.TEST_REDIS_URI, default="memory://")
TEST_SELENIUM_URI = environ.get(ENV.SELENIUM_URL, default=None)

LOG_DIR = environ.get(ENV.LOG_DIR, default="logs")

if IS_PRODUCTION:
    redis_password = environ.get("REDIS_PASSWORD", "")
    encoded_password = quote(redis_password)
    REDIS_URI = "redis://:" + encoded_password + "@redis:6379/0"
else:
    REDIS_URI = environ.get(ENV.REDIS_URI, default="memory://")


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
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = CONFIG_CONSTANTS.SESSION_LIFETIME
    if REDIS_URI == "memory://" or REDIS_URI is None:
        SESSION_TYPE = "cachelib"
        SESSION_CACHELIB = FileSystemCache(
            threshold=10, cache_dir=f"{path.dirname(__file__)}/sessions"
        )
    else:
        SESSION_TYPE = "redis"
        SESSION_REDIS = Redis.from_url(REDIS_URI)
    SESSION_SERIALIZATION_FORMAT = "json"
    SESSION_COOKIE_SAMESITE = "lax"
    SESSION_COOKIE_SECURE = (
        True  # TODO: Implement Remember Me feature and set this to default False
    )
    WTF_CSRF_TIME_LIMIT = (
        CONFIG_CONSTANTS.SESSION_LIFETIME
    )  # Same as session lifetime to avoid CSRF token expiring in middle of user's session
    BASE_EMAIL = environ.get(ENV.BASE_EMAIL)
    MAILJET_API_KEY = environ.get(ENV.MAILJET_API_KEY)
    MAILJET_SECRET_KEY = environ.get(ENV.MAILJET_SECRET_KEY)
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = DEV_DB_URI
    SQLALCHEMY_BINDS = {
        "dev": DEV_DB_URI if DEV_DB_URI else "sqlite://",
        "test": TEST_DB_URI if TEST_DB_URI else "sqlite://",
    }
    REDIS_URI = REDIS_URI
    DOCKER = IS_DOCKER
    ASSET_VERSION = ASSET_VERSION
    DEV_SERVER = IS_DEV_SERVER
    NOTIFICATION_URL = NOTIFICATION_URL
    LOG_DIR = LOG_DIR
    CONTACT_US_URL = CONTACT_US_URL

    def __init__(self) -> None:
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY not found in environment variables")

        if not any(
            (
                environ.get(ENV.POSTGRES_USER, default=None),
                environ.get(ENV.POSTGRES_DB, default=None),
                environ.get(ENV.POSTGRES_PASSWORD, default=None),
            )
        ):
            raise ValueError(
                "One of POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSSWORD not properly set as environment variables"
            )

        if environ.get(ENV.MAILJET_API_KEY, default=None) is None:
            raise ValueError("MAILJET_API_KEY environment variable is missing.")

        if environ.get(ENV.MAILJET_SECRET_KEY, default=None) is None:
            raise ValueError("MAILJET_SECRET_KEY environment variable is missing.")


class ConfigProd(Config):
    SQLALCHEMY_BINDS = {
        "prod": PROD_DB_URI,
    }
    SQLALCHEMY_DATABASE_URI = PROD_DB_URI
    SESSION_TYPE = "redis"
    SESSION_REDIS = (
        Redis.from_url(
            REDIS_URI if (REDIS_URI is not None and REDIS_URI != "memory://") else ""
        )
        if (REDIS_URI is not None and REDIS_URI != "memory://")
        else ""
    )


class ConfigTest(Config):
    TESTING = True
    SQLALCHEMY_BINDS = {"test": TEST_DB_URI}
    SQLALCHEMY_DATABASE_URI = TEST_DB_URI
    UI_TESTING = False

    SESSION_TYPE = (
        "redis"
        if (TEST_REDIS_URI is not None and TEST_REDIS_URI != "memory://")
        else "cachelib"
    )

    SESSION_REDIS = (
        Redis.from_url(TEST_REDIS_URI)
        if (TEST_REDIS_URI is not None and TEST_REDIS_URI != "memory://")
        else ""
    )
    if isinstance(TEST_SELENIUM_URI, str):
        TEST_SELENIUM_URI = TEST_SELENIUM_URI

    def __init__(self) -> None:
        super().__init__()
        if environ.get(ENV.POSTGRES_TEST_DB, default=None) is None:
            raise ValueError("Missing POSTGRES_TEST_DB database name for test")


class ConfigTestUI(ConfigTest):
    UI_TESTING = True
    SESSION_COOKIE_SECURE = False
