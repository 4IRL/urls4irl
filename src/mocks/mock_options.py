import click
from flask import Flask
from flask.cli import AppGroup, with_appcontext
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData

from src.db import db
from src.mocks.mock_data.tags import generate_mock_tags
from src.mocks.mock_data.urls import generate_mock_urls
from src.mocks.mock_data.users import generate_mock_users
from src.mocks.mock_data.utubmembers import generate_mock_utubmembers
from src.mocks.mock_data.utubs import generate_mock_utubs

HELP_SUMMARY_MOCKS = """Add mock data to the dev database."""

HELP_SUMMARY_DB = """Clear or drop the dev database. Pass `test` as an argument to perform actions on the test database.\nFor example:\n\n`flask managedb clear test`
    """

mocks_cli = AppGroup(
    "addmock",
    context_settings={"ignore_unknown_options": True},
    help=HELP_SUMMARY_MOCKS,
)
db_manage_cli = AppGroup(
    "managedb", context_settings={"ignore_unknown_options": True}, help=HELP_SUMMARY_DB
)


@mocks_cli.command("users", help="Add test users to the database.")
def mock_users():
    print("\n\n--- Adding mock users ---\n")
    generate_mock_users(db)
    print("\n--- Finished adding mock users ---\n\n")


@mocks_cli.command("utubs", help="Adds all users, and has them make UTubs.")
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_utubs(no_dupes: bool):
    print("\n\n--- Adding mock UTubs ---\n")
    generate_mock_users(db)
    generate_mock_utubs(db, no_dupes)
    print("\n--- Finished adding mock UTubs ---\n\n")


@mocks_cli.command(
    "utubmembers", help="Adds all users to each UTub. Does all of users/utubs."
)
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_members(no_dupes: bool):
    print("\n\n--- Adding mock UTub members ---\n")
    generate_mock_users(db)
    generate_mock_utubs(db, no_dupes)
    generate_mock_utubmembers(db)
    print("\n--- Finished adding mock UTub members ---\n\n")


@mocks_cli.command(
    "urls", help="Adds URLs to each UTub. Does all of users/utubs/utubmembers."
)
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_urls(no_dupes: bool):
    print("\n\n--- Adding mock URLs to each UTub  ---\n")
    generate_mock_users(db)
    generate_mock_utubs(db, no_dupes)
    generate_mock_utubmembers(db)
    generate_mock_urls(db)
    print("\n--- Finished adding mock URLs to each UTub ---\n\n")


@mocks_cli.command(
    "tags", help="Adds tags to each URL. Does all of users/utubs/utubmembers/urls."
)
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_tags(no_dupes: bool):
    _add_all(db, no_dupes)


@mocks_cli.command("all", help="Adds all mock data to the database.")
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_all(no_dupes: bool):
    _add_all(db, no_dupes)


def _add_all(db: SQLAlchemy, no_dupes: bool):
    print("\n\n--- Adding all mock users, UTubs, members, urls, and tags  ---\n")
    generate_mock_users(db)
    generate_mock_utubs(db, no_dupes)
    generate_mock_utubmembers(db)
    generate_mock_urls(db)
    generate_mock_tags(db)
    print(
        "\n--- Finished adding all mock users, UTubs, members, urls, and tags ---\n\n"
    )


@db_manage_cli.command(
    "clear", help="Clear the tables in the database - same schema, empty tables."
)
@click.argument(
    "db_type",
    type=click.Choice(
        (
            "dev",
            "test",
        ),
        case_sensitive=False,
    ),
    default="dev",
)
def clear_db(db_type: str):
    print(f"\n\n--- Emptying each table in {db_type} database ---\n")
    engine = db.engines[db_type]
    con = engine.connect()
    meta = MetaData(engine)
    meta.reflect()
    meta.drop_all()
    meta.create_all()
    con.close()
    print(f"\n--- Finished emptying each table in {db_type} database ---\n\n")


@db_manage_cli.command("drop", help="Drop the tables from the database.")
@click.argument(
    "db_type",
    type=click.Choice(
        (
            "dev",
            "test",
        ),
        case_sensitive=False,
    ),
    default="dev",
)
@with_appcontext
def drop_db(db_type: str):
    print(f"\n\n--- Dropping each table in {db_type} database ---\n")
    engine = db.engines[db_type]
    con = engine.connect()
    meta = MetaData(engine)
    meta.reflect()
    meta.drop_all()
    con.close()
    print(f"\n--- Dropped each table in {db_type} database ---\n\n")


def register_mocks_db_cli(app: Flask):
    app.cli.add_command(mocks_cli)
    app.cli.add_command(db_manage_cli)