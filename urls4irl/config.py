from dotenv import load_dotenv
from os import environ, path

basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(basedir, ".env"))

class Config:
    """Set Flask config variables."""

    FLASK_ENV = environ.get("FLASK_ENV")
    DEBUG = "True"
    SECRET_KEY = environ.get("SECRET_KEY")
    SESSION_PERMANENT = "False"
    SESSION_TYPE = "filesystem"
