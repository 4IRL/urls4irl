from backend import db
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs


def seed_single_utub_with_one_url(
    *,
    user_id: int,
    utub_name: str,
    url_string: str,
    url_title: str,
    tag_strings: list[str] | None = None,
) -> int:
    """Create one UTub owned by and including `user_id`, with one URL (and optional tags).

    Example:
        seed_single_utub_with_one_url(
            user_id=1, utub_name="Solo", url_string="50% off",
            url_title="Deal", tag_strings=["sale"],
        )
        -> creates UTub "Solo" with member user 1 and a single URL "50% off"
           tagged "sale"; returns the new UTub id.

    Returns:
        The id of the created UTub.
    """
    creating_user: Users = Users.query.get(user_id)

    new_utub = Utubs(
        name=utub_name,
        utub_creator=creating_user.id,
        utub_description="",
    )
    db.session.add(new_utub)
    db.session.commit()

    membership = Utub_Members()
    membership.utub_id = new_utub.id
    membership.user_id = creating_user.id
    db.session.add(membership)
    db.session.commit()

    new_url = Urls(normalized_url=url_string, current_user_id=creating_user.id)
    db.session.add(new_url)
    db.session.commit()

    new_utub_url = Utub_Urls()
    new_utub_url.url_id = new_url.id
    new_utub_url.utub_id = new_utub.id
    new_utub_url.user_id = creating_user.id
    new_utub_url.url_title = url_title
    db.session.add(new_utub_url)
    db.session.commit()

    for tag_string in tag_strings or []:
        new_tag = Utub_Tags(
            utub_id=new_utub.id,
            tag_string=tag_string,
            created_by=creating_user.id,
        )
        db.session.add(new_tag)
        db.session.commit()

        new_url_tag = Utub_Url_Tags()
        new_url_tag.utub_id = new_utub.id
        new_url_tag.utub_url_id = new_utub_url.id
        new_url_tag.utub_tag_id = new_tag.id
        db.session.add(new_url_tag)
        db.session.commit()

    return new_utub.id
