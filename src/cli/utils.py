from datetime import datetime
from flask_session.redis.redis import RedisSessionInterface
from flask_sqlalchemy.extension import SQLAlchemy

from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext
from sqlalchemy.engine.base import Engine

HELP_SUMMARY_UTILS = """General CLI Utils for U4I."""

utils_cli = AppGroup(
    "utils",
    context_settings={"ignore_unknown_options": True},
    help=HELP_SUMMARY_UTILS,
)


@utils_cli.command("start-log", help="Log to indicate application start")
@with_appcontext
def starting_log_for_u4i():
    now = datetime.now()
    start_time = now.strftime("[%Y-%m-%d  %H:%M:%S]")
    current_app.raw_logger.info(  # type: ignore
        """
    !!------------------------------------------------------------------------------------------------------!!\n
    !!-------------------------------------------- STARTING U4I --------------------------------------------!!\n
    !!------------------------------------------------------------------------------------------------------!!\n
    """
        + f"!!----------------------------------------{start_time}----------------------------------------!!\n"
    )
    current_app.raw_logger.info(  # type: ignore
        "Redis successfully attached to U4I"
        if isinstance(current_app.session_interface, RedisSessionInterface)
        else "Redis instance not found"
    )

    sqlalchemy = "sqlalchemy"
    has_db_connection = (
        sqlalchemy in current_app.extensions
        and isinstance(current_app.extensions[sqlalchemy], SQLAlchemy)
        and isinstance(current_app.extensions[sqlalchemy].get_engine(), Engine)
        and hasattr(current_app.extensions[sqlalchemy].get_engine(), "has_table")
        and current_app.extensions[sqlalchemy]
        .get_engine()
        .has_table(table_name="Utubs")
    )

    current_app.raw_logger.info(  # type: ignore
        "PostgreSQL successfully attached to U4I"
        if has_db_connection
        else "PostgreSQL instance not found"
    )


def register_utils_cli(app: Flask):
    app.cli.add_command(utils_cli)
