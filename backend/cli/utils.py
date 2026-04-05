import sys
from datetime import datetime

import click
import flask_migrate
from flask import Flask, current_app
from flask.cli import AppGroup, with_appcontext
from flask_limiter import Limiter
from flask_session.redis.redis import RedisSessionInterface
from flask_sqlalchemy.extension import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.engine.base import Engine

from backend.db import db, get_missing_tables
from backend.utils.strings.config_strs import CONFIG_ENVS

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
    current_app.cli_logger.info(  # type: ignore
        """
    !!------------------------------------------------------------------------------------------------------!!\n
    !!-------------------------------------------- STARTING U4I --------------------------------------------!!\n
    !!------------------------------------------------------------------------------------------------------!!\n
    """
        + f"!!----------------------------------------{start_time}----------------------------------------!!\n"
    )
    current_app.cli_logger.info(  # type: ignore
        "Redis successfully attached to U4I"
        if isinstance(current_app.session_interface, RedisSessionInterface)
        else "Redis instance not found"
    )

    sqlalchemy = "sqlalchemy"
    has_db_extension = (
        sqlalchemy in current_app.extensions
        and isinstance(current_app.extensions[sqlalchemy], SQLAlchemy)
        and isinstance(current_app.extensions[sqlalchemy].get_engine(), Engine)
    )

    if not has_db_extension:
        current_app.cli_logger.info("PostgreSQL instance not found")  # type: ignore
    else:
        missing_tables = get_missing_tables()
        if missing_tables:
            current_app.cli_logger.warning(  # type: ignore
                f"PostgreSQL connected but missing tables: {', '.join(missing_tables)}"
            )
        else:
            current_app.cli_logger.info(  # type: ignore
                "PostgreSQL successfully attached to U4I"
            )


@utils_cli.command("reset-limiter", help="Reset rate limiter for development")
@with_appcontext
def reset_limiter():
    # Cannot reset in production
    if current_app.config.get(CONFIG_ENVS.PRODUCTION, False):
        current_app.cli_logger.info("Cannot reset rate limits in production")  # type: ignore
        return

    limiter_extensions: set[Limiter] | None = current_app.extensions.get(
        "limiter", None
    )

    def _get_limiter(s: set | None) -> Limiter | None:
        if not s:
            return

        for val in s:
            if isinstance(val, Limiter):
                return val
        return

    limiter = _get_limiter(limiter_extensions)

    if not isinstance(limiter, Limiter):
        current_app.cli_logger.info("Could not find a valid limiter")  # type: ignore
        return

    limiter.reset()
    current_app.cli_logger.info("Reset limits!")  # type: ignore


VERIFY_TABLES_ALL_OK = "All database tables verified"
VERIFY_TABLES_FATAL_DEPLOYED = "FATAL: Missing database tables in deployed environment"
VERIFY_TABLES_FATAL_REPAIR_FAILED = "FATAL: Tables still missing after migration repair"
VERIFY_TABLES_REPAIRED = "Database repaired — all tables verified after re-migration"


@utils_cli.command(
    "verify-tables",
    help="Verify all model tables exist; auto-repair corrupted alembic state",
)
@with_appcontext
def verify_tables():
    missing_tables = get_missing_tables()
    if not missing_tables:
        click.echo(VERIFY_TABLES_ALL_OK)
        current_app.cli_logger.info(VERIFY_TABLES_ALL_OK)  # type: ignore
        return

    is_deployed = current_app.config.get(
        CONFIG_ENVS.PRODUCTION, False
    ) or current_app.config.get(CONFIG_ENVS.DEV_SERVER, False)
    if is_deployed:
        message = (
            f"{VERIFY_TABLES_FATAL_DEPLOYED}: {', '.join(missing_tables)}. "
            "Manual intervention required — refusing to auto-repair."
        )
        click.echo(message, err=True)
        current_app.cli_logger.error(message)  # type: ignore
        sys.exit(1)

    repair_message = (
        f"Missing database tables: {', '.join(missing_tables)}. "
        "Dropping public schema and re-running migrations..."
    )
    click.echo(repair_message)
    current_app.cli_logger.warning(repair_message)  # type: ignore
    autocommit_engine = db.engine.execution_options(isolation_level="AUTOCOMMIT")
    with autocommit_engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    flask_migrate.upgrade()
    remaining = get_missing_tables()
    if remaining:
        fail_message = f"{VERIFY_TABLES_FATAL_REPAIR_FAILED}: {', '.join(remaining)}"
        click.echo(fail_message, err=True)
        current_app.cli_logger.error(fail_message)  # type: ignore
        sys.exit(1)
    click.echo(VERIFY_TABLES_REPAIRED)
    current_app.cli_logger.info(VERIFY_TABLES_REPAIRED)  # type: ignore


def register_utils_cli(app: Flask):
    app.cli.add_command(utils_cli)
