from flask_sqlalchemy import SQLAlchemy

from src.cli.mock_constants import TEST_USER_COUNT, MOCK_UTUB_NAME_BASE
from src.models.users import Users
from src.models.utubs import Utubs
from src.models.utub_members import Member_Role, Utub_Members


def generate_mock_utubs(db: SQLAlchemy, no_dupes: bool):
    """
    Generates UTubs and adds them to the database. Multiple UTubs can have the same name,
    so the option is given whether or not to create UTubs if one is found with the same name.

    Args:
        db (SQLAlchemy): Database engine and connection for committing mock data
        no_dupes (bool): True if wanting to avoid creating duplicate UTubs, else will create UTubs with duplicate names
    """
    for i in range(TEST_USER_COUNT):
        creator_id = i + 1
        utub_name = f"{MOCK_UTUB_NAME_BASE}{creator_id}"
        creator: Users = Users.query.get(creator_id)

        if (
            Utubs.query.filter(
                Utubs.name == utub_name, Utubs.utub_creator == creator_id
            ).count()
            > 0
        ):
            if no_dupes:
                print(
                    f"Already added UTub with name {utub_name}, made by {creator.username}"
                )
                continue
            print(
                f"Adding DUPLICATE UTub with name {utub_name} made by {creator.username}"
            )
        else:
            print(f"Adding UTub with name {utub_name}, made by {creator.username}")

        new_utub = Utubs(
            name=utub_name,
            utub_creator=creator_id,
            utub_description=f"Made by {creator.username}",
        )

        new_member: Utub_Members = Utub_Members()
        new_member.member_role = Member_Role.CREATOR
        new_member.user_id = creator_id
        new_member.to_utub = new_utub
        db.session.add(new_utub)
        db.session.add(new_member)

    db.session.commit()
