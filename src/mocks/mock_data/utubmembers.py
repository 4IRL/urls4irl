from flask_sqlalchemy import SQLAlchemy

from src.models.users import Users
from src.models.utubs import Utubs
from src.models.utub_members import Member_Role, Utub_Members


def generate_mock_utubmembers(db: SQLAlchemy):
    all_utubs: list[Utubs] = Utubs.query.all()
    all_users: list[Users] = Users.query.all()
    for utub in all_utubs:
        for user in all_users:
            if Utub_Members.query.get((utub.id, user.id)) is not None:
                print(f"Already added {user.username} to {utub.name} with ID={utub.id}")
                continue

            new_member = Utub_Members()
            new_member.user_id = user.id
            new_member.utub_id = utub.id
            new_member.member_role = Member_Role.MEMBER
            db.session.add(new_member)

            print(f"Adding {user.username} to {utub.name} with ID={utub.id}")

    db.session.commit()
