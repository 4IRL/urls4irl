from flask import Flask
import pytest

from backend import db
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.search.constants import MatchedField
from backend.search.services.cross_utub_search import search_across_user_utubs
from tests.models_for_test import all_tag_strings

pytestmark = pytest.mark.urls

FIRST_USER_ID = 1
SECOND_USER_ID = 2


def _seed_single_utub_with_one_url(
    *,
    user_id: int,
    utub_name: str,
    url_string: str,
    url_title: str,
    tag_strings: list[str] | None = None,
) -> int:
    """Create one UTub owned by and including `user_id`, with one URL (and optional tags).

    Example:
        _seed_single_utub_with_one_url(
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


def test_search_matches_on_url_string(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    _, _, _, app = login_first_user_without_register
    query = "abc"

    with app.app_context():
        matching_count = (
            Utub_Urls.query.join(Urls, Utub_Urls.url_id == Urls.id)
            .filter(Urls.url_string.ilike(f"%{query}%"))
            .count()
        )
        assert matching_count >= 1

        results = search_across_user_utubs(query=query, user_id=FIRST_USER_ID)

        assert len(results.results) >= 1
        all_hits = [hit for group in results.results for hit in group.urls]
        url_string_hits = [hit for hit in all_hits if query in hit.url_string.lower()]
        assert len(url_string_hits) >= 1


def test_search_matches_on_url_title(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    _, _, _, app = login_first_user_without_register
    query = "This is"

    with app.app_context():
        matching_count = Utub_Urls.query.filter(
            Utub_Urls.url_title.ilike(f"%{query}%")
        ).count()
        assert matching_count >= 1

        results = search_across_user_utubs(query=query, user_id=FIRST_USER_ID)

        all_hits = [hit for group in results.results for hit in group.urls]
        assert len(all_hits) >= 1
        assert all(query.lower() in hit.url_title.lower() for hit in all_hits)


def test_search_matches_on_tag_string_case_insensitive(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    _, _, _, app = login_first_user_without_register
    query = "funny"

    with app.app_context():
        matching_tag_count = Utub_Tags.query.filter(
            Utub_Tags.tag_string.ilike(f"%{query}%")
        ).count()
        assert matching_tag_count >= 1

        results = search_across_user_utubs(query=query, user_id=FIRST_USER_ID)

        all_hits = [hit for group in results.results for hit in group.urls]
        assert len(all_hits) >= 1
        hits_carrying_tag = [
            hit
            for hit in all_hits
            if any(query in tag.tag_string.lower() for tag in hit.url_tags)
        ]
        assert len(hits_carrying_tag) >= 1


def test_search_excludes_non_member_utubs(
    add_first_user_to_second_utub_and_add_tags_remove_first_utub,
    login_first_user_without_register,
):
    _, _, _, app = login_first_user_without_register
    query = all_tag_strings[1].lower()

    with app.app_context():
        member_utub_ids = {
            membership.utub_id
            for membership in Utub_Members.query.filter(
                Utub_Members.user_id == SECOND_USER_ID
            ).all()
        }
        non_member_utub_ids = {
            utub.id for utub in Utubs.query.all() if utub.id not in member_utub_ids
        }

        results = search_across_user_utubs(query=query, user_id=SECOND_USER_ID)

        returned_utub_ids = {group.utub_id for group in results.results}
        assert returned_utub_ids.isdisjoint(non_member_utub_ids)


def test_search_groups_by_source_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    _, _, _, app = login_first_user_without_register
    query = "https"

    with app.app_context():
        results = search_across_user_utubs(query=query, user_id=FIRST_USER_ID)

        returned_utub_ids = [group.utub_id for group in results.results]
        assert len(returned_utub_ids) == len(set(returned_utub_ids))
        assert len(results.results) >= 2
        for group in results.results:
            source_utub: Utubs = Utubs.query.get(group.utub_id)
            assert group.utub_name == source_utub.name


def test_search_no_match_returns_empty(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        results = search_across_user_utubs(query="zzzznomatch", user_id=FIRST_USER_ID)
        assert results.results == []


def test_search_escapes_percent_wildcard(
    register_multiple_users,
    app: Flask,
):
    with app.app_context():
        seeded_utub_id = _seed_single_utub_with_one_url(
            user_id=FIRST_USER_ID,
            utub_name="Percent UTub",
            url_string="50% off",
            url_title="Discount",
        )
        seeded_count = Utub_Urls.query.filter(
            Utub_Urls.utub_id == seeded_utub_id
        ).count()
        assert seeded_count == 1

        results = search_across_user_utubs(query="%", user_id=FIRST_USER_ID)

        all_hits = [hit for group in results.results for hit in group.urls]
        assert len(all_hits) == 1
        assert all_hits[0].url_string == "50% off"


def test_search_escapes_underscore_wildcard(
    register_multiple_users,
    app: Flask,
):
    with app.app_context():
        seeded_utub_id = _seed_single_utub_with_one_url(
            user_id=FIRST_USER_ID,
            utub_name="Underscore UTub",
            url_string="foo_bar",
            url_title="Snake",
        )
        seeded_count = Utub_Urls.query.filter(
            Utub_Urls.utub_id == seeded_utub_id
        ).count()
        assert seeded_count == 1

        results = search_across_user_utubs(query="_", user_id=FIRST_USER_ID)

        all_hits = [hit for group in results.results for hit in group.urls]
        assert len(all_hits) == 1
        assert all_hits[0].url_string == "foo_bar"


@pytest.mark.parametrize(
    "url_string, url_title, tag_strings, query, expected_fields",
    [
        pytest.param(
            "https://nomatch.com/",
            "matchword title",
            None,
            "matchword",
            [MatchedField.URL_TITLE],
            id="title-only",
        ),
        pytest.param(
            "https://matchword.com/",
            "unrelated title",
            None,
            "matchword",
            [MatchedField.URL_STRING],
            id="url-only",
        ),
        pytest.param(
            "https://nomatch.com/",
            "unrelated title",
            ["matchword"],
            "matchword",
            [MatchedField.TAG],
            id="tag-only",
        ),
    ],
)
def test_search_matched_fields_single_field(
    register_multiple_users,
    app: Flask,
    url_string,
    url_title,
    tag_strings,
    query,
    expected_fields,
):
    with app.app_context():
        seeded_utub_id = _seed_single_utub_with_one_url(
            user_id=FIRST_USER_ID,
            utub_name="Single Field UTub",
            url_string=url_string,
            url_title=url_title,
            tag_strings=tag_strings,
        )
        seeded_count = Utub_Urls.query.filter(
            Utub_Urls.utub_id == seeded_utub_id
        ).count()
        assert seeded_count == 1

        results = search_across_user_utubs(query=query, user_id=FIRST_USER_ID)

        all_hits = [hit for group in results.results for hit in group.urls]
        assert len(all_hits) == 1
        assert all_hits[0].matched_fields == expected_fields


def test_search_matched_fields_multi_field_stable_order(
    register_multiple_users,
    app: Flask,
):
    with app.app_context():
        seeded_utub_id = _seed_single_utub_with_one_url(
            user_id=FIRST_USER_ID,
            utub_name="Multi Field UTub",
            url_string="https://nomatch.com/",
            url_title="multimatch title",
            tag_strings=["multimatch"],
        )
        seeded_count = Utub_Urls.query.filter(
            Utub_Urls.utub_id == seeded_utub_id
        ).count()
        assert seeded_count == 1

        results = search_across_user_utubs(query="multimatch", user_id=FIRST_USER_ID)

        all_hits = [hit for group in results.results for hit in group.urls]
        assert len(all_hits) == 1
        assert all_hits[0].matched_fields == [
            MatchedField.URL_TITLE,
            MatchedField.TAG,
        ]


def test_search_ranks_within_group_by_score(
    register_multiple_users,
    app: Flask,
):
    with app.app_context():
        creating_user: Users = Users.query.get(FIRST_USER_ID)
        new_utub = Utubs(
            name="Within Rank UTub",
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

        url_a = Urls(
            normalized_url="https://nomatch.com/", current_user_id=creating_user.id
        )
        url_b = Urls(
            normalized_url="https://alsonomatch.com/",
            current_user_id=creating_user.id,
        )
        db.session.add(url_a)
        db.session.add(url_b)
        db.session.commit()

        utub_url_a = Utub_Urls()
        utub_url_a.url_id = url_a.id
        utub_url_a.utub_id = new_utub.id
        utub_url_a.user_id = creating_user.id
        utub_url_a.url_title = "titlequery title"
        db.session.add(utub_url_a)

        utub_url_b = Utub_Urls()
        utub_url_b.url_id = url_b.id
        utub_url_b.utub_id = new_utub.id
        utub_url_b.user_id = creating_user.id
        utub_url_b.url_title = "unrelated title"
        db.session.add(utub_url_b)
        db.session.commit()

        tag_b = Utub_Tags(
            utub_id=new_utub.id,
            tag_string="titlequery tag",
            created_by=creating_user.id,
        )
        db.session.add(tag_b)
        db.session.commit()

        url_tag_b = Utub_Url_Tags()
        url_tag_b.utub_id = new_utub.id
        url_tag_b.utub_url_id = utub_url_b.id
        url_tag_b.utub_tag_id = tag_b.id
        db.session.add(url_tag_b)
        db.session.commit()

        assert Utub_Urls.query.filter(Utub_Urls.utub_id == new_utub.id).count() == 2

        results = search_across_user_utubs(query="titlequery", user_id=FIRST_USER_ID)

        group = next(group for group in results.results if group.utub_id == new_utub.id)
        assert group.urls[0].url_title == "titlequery title"


def test_search_ranks_across_groups_by_score(
    register_multiple_users,
    app: Flask,
):
    with app.app_context():
        utub_a_id = _seed_single_utub_with_one_url(
            user_id=FIRST_USER_ID,
            utub_name="Across A",
            url_string="https://nomatch-a.com/",
            url_title="unrelated a",
            tag_strings=["rankquery"],
        )
        utub_b_id = _seed_single_utub_with_one_url(
            user_id=FIRST_USER_ID,
            utub_name="Across B",
            url_string="https://nomatch-b.com/",
            url_title="rankquery title",
        )
        assert Utub_Urls.query.filter(Utub_Urls.utub_id == utub_a_id).count() == 1
        assert Utub_Urls.query.filter(Utub_Urls.utub_id == utub_b_id).count() == 1

        results = search_across_user_utubs(query="rankquery", user_id=FIRST_USER_ID)

        assert results.results[0].utub_id == utub_b_id


def test_search_tiebreak_within_group_by_title_asc(
    register_multiple_users,
    app: Flask,
):
    with app.app_context():
        creating_user: Users = Users.query.get(FIRST_USER_ID)
        new_utub = Utubs(
            name="Tiebreak Within UTub",
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

        url_a = Urls(
            normalized_url="https://nomatch-tie-a.com/",
            current_user_id=creating_user.id,
        )
        url_b = Urls(
            normalized_url="https://nomatch-tie-b.com/",
            current_user_id=creating_user.id,
        )
        db.session.add(url_a)
        db.session.add(url_b)
        db.session.commit()

        utub_url_a = Utub_Urls()
        utub_url_a.url_id = url_a.id
        utub_url_a.utub_id = new_utub.id
        utub_url_a.user_id = creating_user.id
        utub_url_a.url_title = "alpha tiequery"
        db.session.add(utub_url_a)

        utub_url_b = Utub_Urls()
        utub_url_b.url_id = url_b.id
        utub_url_b.utub_id = new_utub.id
        utub_url_b.user_id = creating_user.id
        utub_url_b.url_title = "beta tiequery"
        db.session.add(utub_url_b)
        db.session.commit()

        assert Utub_Urls.query.filter(Utub_Urls.utub_id == new_utub.id).count() == 2

        results = search_across_user_utubs(query="tiequery", user_id=FIRST_USER_ID)

        group = next(group for group in results.results if group.utub_id == new_utub.id)
        assert group.urls[0].url_title == "alpha tiequery"
        assert group.urls[1].url_title == "beta tiequery"


def test_search_tiebreak_across_groups_by_match_count_desc(
    register_multiple_users,
    app: Flask,
):
    with app.app_context():
        creating_user: Users = Users.query.get(FIRST_USER_ID)

        utub_alfa = Utubs(
            name="Alfa UTub",
            utub_creator=creating_user.id,
            utub_description="",
        )
        utub_beta = Utubs(
            name="Beta UTub",
            utub_creator=creating_user.id,
            utub_description="",
        )
        db.session.add(utub_alfa)
        db.session.add(utub_beta)
        db.session.commit()

        for utub in (utub_alfa, utub_beta):
            membership = Utub_Members()
            membership.utub_id = utub.id
            membership.user_id = creating_user.id
            db.session.add(membership)
        db.session.commit()

        def _add_url_with_title(utub: Utubs, url_string: str, url_title: str) -> None:
            new_url = Urls(normalized_url=url_string, current_user_id=creating_user.id)
            db.session.add(new_url)
            db.session.commit()

            new_utub_url = Utub_Urls()
            new_utub_url.url_id = new_url.id
            new_utub_url.utub_id = utub.id
            new_utub_url.user_id = creating_user.id
            new_utub_url.url_title = url_title
            db.session.add(new_utub_url)
            db.session.commit()

        _add_url_with_title(utub_alfa, "https://nomatch-alfa-1.com/", "countquery one")
        _add_url_with_title(utub_alfa, "https://nomatch-alfa-2.com/", "countquery two")
        _add_url_with_title(utub_beta, "https://nomatch-beta-1.com/", "countquery solo")

        assert Utub_Urls.query.filter(Utub_Urls.utub_id == utub_alfa.id).count() == 2
        assert Utub_Urls.query.filter(Utub_Urls.utub_id == utub_beta.id).count() == 1

        results = search_across_user_utubs(query="countquery", user_id=FIRST_USER_ID)

        assert results.results[0].utub_id == utub_alfa.id
