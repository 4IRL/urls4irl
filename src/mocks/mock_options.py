import click
from flask import Flask, current_app, session
from flask.cli import AppGroup, with_appcontext
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_user
from sqlalchemy import MetaData

from src.db import db
from src.mocks.mock_data.tags import generate_mock_tags
from src.mocks.mock_data.urls import generate_mock_urls, generate_custom_mock_url
from src.mocks.mock_data.users import generate_mock_users
from src.mocks.mock_data.utubmembers import generate_mock_utubmembers
from src.mocks.mock_data.utubs import generate_mock_utubs
from src.models.users import Users

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
    "url",
    help="Adds a URL to each UTub, added by UTub creator. Does all of users/utubs/utubmembers.",
)
@click.argument("urls", nargs=-1, required=True)
@click.option(
    "--no-dupes", is_flag=True, help="Prevent UTubs being created with the same name"
)
def mock_url(urls: list[str], no_dupes: bool):
    print(f"\n\n--- Adding mock URLs: {urls} to each UTub  ---\n")
    generate_mock_users(db)
    generate_mock_utubs(db, no_dupes)
    generate_mock_utubmembers(db)
    generate_custom_mock_url(db, urls)
    print("\n--- Finished adding mock URLs to each UTub ---\n\n")


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


@mocks_cli.command(
    "login",
    help="Logs in user with user_id. Adds all mock users first. Default ID is 1.",
)
@click.argument("user_id", nargs=1, required=True, default=1, type=int)
@with_appcontext
def login_mock_user(user_id: int):
    generate_mock_users(db, silent=True)
    user: Users = Users.query.get(user_id)
    if not user:
        click.echo("User not found to login", err=True)
        return

    with current_app.test_request_context("/"):
        if login_user(user):
            session.modified = True
            click.echo(f"{session.sid}")
            current_app.session_interface.save_session(
                current_app, session, response=current_app.make_response("Testing")
            )

        else:
            click.echo("N/A")


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


@db_manage_cli.command(
    "create", help="Create the tables in the database. Only for dev database"
)
@click.argument(
    "db_type",
    type=click.Choice(
        ("dev",),
        case_sensitive=False,
    ),
    default="dev",
)
@with_appcontext
def create_db(db_type: str):
    print(f"\n\n--- Creating each table in {db_type} database ---\n")
    db.create_all()
    print(f"\n--- Finished creating each table in {db_type} database ---\n\n")


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
