from flask import Flask
import pytest

from backend import db
from backend.models.utub_tags import Utub_Tags
from backend.models.urls import Urls
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.users import Users
from backend.models.utubs import Utubs
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls


@pytest.fixture
def add_first_user_to_second_utub_and_add_tags_remove_first_utub(
    app: Flask, add_one_url_to_each_utub_no_tags, add_tags_to_utubs
):
    """
    After each user has made their own UTub, with one URL added by that user to each UTub,
    now add first user to second UTub as UTub member, and add tags to all currently added URLs

    Remove the first UTub so first user is no longer creator of a UTub

    Utub with ID of 2, created by User ID of 2, with URL ID of 2, now has member 1
    All URLs have all tags associated with them

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_to_each_utub_no_tags (pytest fixture): Has each User make their own UTub, and has
            that user add a URL to their UTub
        add_tags_to_all_utubs (pytest.fixture): Adds all tags to the database for easy adding to URLs
    """
    with app.app_context():
        first_utub = Utubs.query.get(1)
        db.session.delete(first_utub)
        db.session.commit()
        second_utub = Utubs.query.get(2)
        all_tags = Utub_Tags.query.order_by(Utub_Tags.id).all()

        # Add a single missing users to this UTub
        new_user = Users.query.get(1)
        new_utub_user_association = Utub_Members()
        new_utub_user_association.to_user = new_user
        new_utub_user_association.utub_id = second_utub.id
        second_utub.members.append(new_utub_user_association)
        db.session.add(new_utub_user_association)

        urls_in_utub: list[Utub_Urls] = [utub_url for utub_url in second_utub.utub_urls]

        for url_in_utub in urls_in_utub:
            url_id = url_in_utub.id

            for tag in all_tags:
                new_tag_url_utub_association = Utub_Url_Tags()
                new_tag_url_utub_association.utub_containing_this_url_tag = second_utub
                new_tag_url_utub_association.tagged_url = url_in_utub
                new_tag_url_utub_association.utub_tag_item = tag
                new_tag_url_utub_association.utub_id = second_utub.id
                new_tag_url_utub_association.utub_url_id = url_id
                new_tag_url_utub_association.utub_tag_id = tag.id
                second_utub.utub_url_tags.append(new_tag_url_utub_association)

        db.session.commit()


@pytest.fixture
def add_two_url_and_all_users_to_each_utub_no_tags(
    app: Flask, add_one_url_and_all_users_to_each_utub_no_tags
):
    """
    After each user has made their own UTub, with one URL added by that user to each UTub,
    now add all other users as members to each UTub.

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has members 2 and 3 included,
    now had URL ID of 2 also included in it

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_to_each_utub_no_tags (pytest fixture): Has each User make their own UTub, and has
            that user add a URL to their UTub
    """
    with app.app_context():
        current_utubs = Utubs.query.order_by(Utubs.id).all()

        # Add all missing users to this UTub
        for utub in current_utubs:
            # Get URL in current UTUb
            current_utub_url: Utub_Urls = Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub.id
            ).first()
            current_utub_id = current_utub_url.url_id
            new_url: Urls = Urls.query.get(((current_utub_id % 3) + 1))

            new_utub_url_user_association = Utub_Urls()

            new_utub_url_user_association.standalone_url = new_url
            new_utub_url_user_association.url_id = new_url.id

            new_utub_url_user_association.utub = utub
            new_utub_url_user_association.utub_id = utub.id

            new_utub_url_user_association.user_id = new_url.id

            new_utub_url_user_association.url_title = f"This is {new_url.url_string}"

            db.session.add(new_utub_url_user_association)

        db.session.commit()


@pytest.fixture
def add_multi_dest_state_for_copy(
    app: Flask, add_one_url_and_all_users_to_each_utub_no_tags
):
    """
    Set up a source UTub plus two clean destination UTubs for multi-destination
    bulk-copy coverage.

    Starting from every user being a member of every UTub with UTub `i` holding
    URL `i`, this fixture adds URL 2 and URL 3 into the SOURCE UTub (id 1), so:

    - SOURCE = UTub 1: now holds URLs {1, 2, 3} (all attributed to User 1).
    - DEST   = UTub 2: still holds only URL 2.
    - DEST   = UTub 3: still holds only URL 3.

    URL 1 is net-new to BOTH destinations, so copying it into [2, 3] copies cleanly
    into each. The copier (User 1) is a member of all three UTubs.

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_and_all_users_to_each_utub_no_tags (pytest fixture): Adds all
            users to all UTubs, each UTub containing a single URL added by its creator
    """
    with app.app_context():
        source_utub: Utubs = Utubs.query.get(1)
        existing_url_ids = {utub_url.url_id for utub_url in source_utub.utub_urls}

        for url in Urls.query.filter(Urls.id.in_([2, 3])).all():
            if url.id in existing_url_ids:
                continue
            new_url_in_source = Utub_Urls()
            new_url_in_source.standalone_url = url
            new_url_in_source.url_id = url.id
            new_url_in_source.utub_id = source_utub.id
            new_url_in_source.user_id = source_utub.utub_creator
            new_url_in_source.url_title = f"This is {url.url_string}"
            db.session.add(new_url_in_source)

        db.session.commit()


@pytest.fixture
def add_multi_dest_with_one_dup(app: Flask, add_multi_dest_state_for_copy):
    """
    Pre-seed source URL 1 into DEST UTub 3, so copying URL 1 into destinations
    [2, 3] copies cleanly into UTub 2 but is a DUPLICATE skip in UTub 3.

    Args:
        app (Flask): The Flask client providing an app context
        add_multi_dest_state_for_copy (pytest fixture): Source UTub 1 holds URLs
            {1, 2, 3}; destinations 2 and 3 hold only their own base URL
    """
    with app.app_context():
        dest_utub: Utubs = Utubs.query.get(3)
        already_present = {utub_url.url_id for utub_url in dest_utub.utub_urls}
        if 1 not in already_present:
            url = Urls.query.get(1)
            duplicate_in_dest = Utub_Urls()
            duplicate_in_dest.standalone_url = url
            duplicate_in_dest.url_id = url.id
            duplicate_in_dest.utub_id = dest_utub.id
            duplicate_in_dest.user_id = dest_utub.utub_creator
            duplicate_in_dest.url_title = f"This is {url.url_string}"
            db.session.add(duplicate_in_dest)
            db.session.commit()


@pytest.fixture
def add_multi_dest_with_one_locked(app: Flask, add_multi_dest_state_for_copy):
    """
    Mark DEST UTub 3 locked, so a copy into destinations [2, 3] copies into UTub 2
    and is skipped-and-reported (`status="locked"`) for UTub 3.

    Args:
        app (Flask): The Flask client providing an app context
        add_multi_dest_state_for_copy (pytest fixture): Source UTub 1 holds URLs
            {1, 2, 3}; destinations 2 and 3 hold only their own base URL
    """
    with app.app_context():
        dest_utub: Utubs = Utubs.query.get(3)
        dest_utub.is_locked = True
        db.session.commit()


@pytest.fixture
def add_multi_dest_with_one_nonmember(app: Flask, add_multi_dest_state_for_copy):
    """
    Remove the copier (User 1) from DEST UTub 3, making it a genuine non-membership
    destination (masked 404) while User 1 remains a member of source UTub 1 and
    destination UTub 2.

    Args:
        app (Flask): The Flask client providing an app context
        add_multi_dest_state_for_copy (pytest fixture): Source UTub 1 holds URLs
            {1, 2, 3}; destinations 2 and 3 hold only their own base URL
    """
    with app.app_context():
        membership = Utub_Members.query.get((3, 1))
        db.session.delete(membership)
        db.session.commit()


@pytest.fixture
def add_mixed_delete_permission_urls_in_first_utub(
    app: Flask, add_tags_to_utubs, add_one_url_and_all_users_to_each_utub_no_tags
):
    """
    Seed the FIRST UTub (id 1, created by user 1) with a mix of URLs the acting user
    may or may not delete, plus tags arranged to exercise the bulk-delete tag-count
    recompute (shared-tag aggregate + zero-count backfill).

    Starting from every user being a member of every UTub with UTub 1 holding URL 1
    (added by user 1), this fixture adds:

    - URL 2 into UTub 1, added by MEMBER user 2 (user_id=2)
    - URL 3 into UTub 1, added by MEMBER user 3 (user_id=3)

    So UTub 1 holds three URL rows attributed to users 1, 2, and 3 respectively:

    - The literal creator (user 1) may delete ALL three (creator predicate).
    - A plain member (e.g. user 2) may delete only their own URL (URL 2) and is
      FORBIDDEN from the other two.

    Tags in UTub 1 (three ``Utub_Tags`` seeded by ``add_tags_to_utubs``):

    - ``shared`` tag (first UTub-1 tag) applied to URL 1, URL 2, AND URL 3 — deleting
      URL 1 + URL 2 leaves it on URL 3, so its recomputed count is the aggregate 1,
      not a naive per-URL double-decrement.
    - ``solo`` tag (second UTub-1 tag) applied to URL 1 ONLY — deleting URL 1 empties
      it, so the recompute must return count 0 (present in the map, not omitted).

    Args:
        app (Flask): The Flask client providing an app context
        add_tags_to_utubs (pytest fixture): Seeds UTub tags for every UTub
        add_one_url_and_all_users_to_each_utub_no_tags (pytest fixture): Adds all users
            to all UTubs, each UTub containing a single URL added by its creator
    """
    with app.app_context():
        first_utub: Utubs = Utubs.query.get(1)

        added_url_rows: dict[int, Utub_Urls] = {}
        for url_id_and_adder in (2, 3):
            url: Urls = Urls.query.get(url_id_and_adder)
            new_utub_url = Utub_Urls()
            new_utub_url.standalone_url = url
            new_utub_url.url_id = url.id
            new_utub_url.utub_id = first_utub.id
            new_utub_url.user_id = url_id_and_adder
            new_utub_url.url_title = f"This is {url.url_string}"
            db.session.add(new_utub_url)
            added_url_rows[url_id_and_adder] = new_utub_url

        db.session.flush()

        first_url_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == first_utub.id,
            Utub_Urls.url_id == 1,
        ).first()

        first_utub_tags = (
            Utub_Tags.query.filter(Utub_Tags.utub_id == first_utub.id)
            .order_by(Utub_Tags.id)
            .all()
        )
        shared_tag = first_utub_tags[0]
        solo_tag = first_utub_tags[1]

        # Shared tag on URL 1, URL 2, and URL 3.
        for url_row in (first_url_row, added_url_rows[2], added_url_rows[3]):
            db.session.add(
                Utub_Url_Tags(
                    utub_id=first_utub.id,
                    utub_url_id=url_row.id,
                    utub_tag_id=shared_tag.id,
                    user_id=first_utub.utub_creator,
                )
            )

        # Solo tag on URL 1 only.
        db.session.add(
            Utub_Url_Tags(
                utub_id=first_utub.id,
                utub_url_id=first_url_row.id,
                utub_tag_id=solo_tag.id,
                user_id=first_utub.utub_creator,
            )
        )

        db.session.commit()


@pytest.fixture
def add_co_creator_and_mixed_delete_permission_urls(
    app: Flask, add_one_url_and_all_users_to_each_utub_no_tags
):
    """
    Seed the FIRST UTub (id 1, created by user 1) with user 2 promoted to a
    ``Member_Role.CO_CREATOR`` membership plus a mix of URLs, to exercise the co-owner
    URL-delete right (a co-creator is a manager and may delete any URL in the UTub).

    Starting from every user being a member of every UTub with UTub 1 holding URL 1
    (added by creator user 1), this fixture:

    - Promotes user 2's UTub-1 membership to ``Member_Role.CO_CREATOR``.
    - Adds URL 2 into UTub 1, added by the CO_CREATOR (user 2).
    - Adds URL 3 into UTub 1, added by a THIRD member (user 3).

    Acting as the co-creator (user 2, NOT the literal ``utub.utub_creator``): URL 1
    (creator's), URL 2 (co-creator's own), and URL 3 (third member's) are ALL deletable,
    because a co-owner holds the manager delete right.

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_and_all_users_to_each_utub_no_tags (pytest fixture): Adds all users
            to all UTubs, each UTub containing a single URL added by its creator
    """
    with app.app_context():
        first_utub: Utubs = Utubs.query.get(1)

        co_creator_membership: Utub_Members = Utub_Members.query.get((first_utub.id, 2))
        co_creator_membership.member_role = Member_Role.CO_CREATOR

        for url_id_and_adder in (2, 3):
            url: Urls = Urls.query.get(url_id_and_adder)
            new_utub_url = Utub_Urls()
            new_utub_url.standalone_url = url
            new_utub_url.url_id = url.id
            new_utub_url.utub_id = first_utub.id
            new_utub_url.user_id = url_id_and_adder
            new_utub_url.url_title = f"This is {url.url_string}"
            db.session.add(new_utub_url)

        db.session.commit()


@pytest.fixture
def add_one_url_and_all_users_to_each_utub_with_all_tags(
    app: Flask, add_one_url_and_all_users_to_each_utub_no_tags, add_tags_to_utubs
):
    """
    After each user has made their own UTub, with one URL added by that user to each UTub,
    now add all other users as members to each UTub.

    Utub with ID of 1, created by User ID of 1, with URL ID of 1, now has members 2 and 3 included

    Args:
        app (Flask): The Flask client providing an app context
        add_one_url_to_each_utub_no_tags (pytest fixture): Has each User make their own UTub, and has
            that user add a URL to their UTub
    """
    with app.app_context():
        current_utubs = Utubs.query.order_by(Utubs.id).all()
        current_tags = Utub_Tags.query.order_by(Utub_Tags.id).all()

        # Add all missing tags to this UTub
        for utub in current_utubs:
            current_utub_url = [utub_url for utub_url in utub.utub_urls].pop()

            for tag in current_tags:
                new_tag_url_utub_association = Utub_Url_Tags()
                new_tag_url_utub_association.utub_containing_this_url_tag = utub
                new_tag_url_utub_association.tagged_url = current_utub_url
                new_tag_url_utub_association.utub_tag_item = tag
                new_tag_url_utub_association.utub_id = utub.id
                new_tag_url_utub_association.utub_url_id = current_utub_url.id
                new_tag_url_utub_association.utub_tag_id = tag.id
                utub.utub_url_tags.append(new_tag_url_utub_association)

        db.session.commit()
