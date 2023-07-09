from dotenv import load_dotenv
from os import environ, path

basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(basedir, ".env"))


class Config:
    """Set Flask config variables."""

    FLASK_ENV = environ.get("FLASK_ENV")
    SECRET_KEY = environ.get("SECRET_KEY")
    SESSION_PERMANENT = "False"
    SESSION_TYPE = "sqlalchemy"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    if FLASK_ENV == "development":
        SQLALCHEMY_DATABASE_URI = environ.get("DATABASE_URL")
    else:
        postgres_uri = environ.get("DATABASE_URL")
        if postgres_uri.startswith("postgres://"):
            postgres_uri = postgres_uri.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = postgres_uri
