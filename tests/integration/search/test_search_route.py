from typing import Tuple
from urllib.parse import urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.search.constants import SearchErrorCodes, SearchFailureMessages
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME
from tests.integration.search.helpers import seed_single_utub_with_one_url

pytestmark = pytest.mark.urls

FIRST_USER_ID = 1

_SEARCH_PATH = "/search"
_HOME_PATH = "/home"
_HTTPS_QUERY = "https"
_NO_MATCH_QUERY = "zzzznomatch"


def _seed_utub_with_title_and_tag_match(
    *, user_id: int, utub_name: str, query_term: str
) -> int:
    """Seed one UTub with URL-A (title-only match) and URL-B (tag-only match).

    Both URLs match `query_term`, but only via different fields, so field
    ordering decides which ranks first. Returns the created UTub id.
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

    url_a = Urls(
        normalized_url="https://nomatch-order-a.com/",
        current_user_id=creating_user.id,
    )
    url_b = Urls(
        normalized_url="https://nomatch-order-b.com/",
        current_user_id=creating_user.id,
    )
    db.session.add(url_a)
    db.session.add(url_b)
    db.session.commit()

    utub_url_a = Utub_Urls()
    utub_url_a.url_id = url_a.id
    utub_url_a.utub_id = new_utub.id
    utub_url_a.user_id = creating_user.id
    utub_url_a.url_title = f"{query_term} title"
    db.session.add(utub_url_a)

    utub_url_b = Utub_Urls()
    utub_url_b.url_id = url_b.id
    utub_url_b.utub_id = new_utub.id
    utub_url_b.user_id = creating_user.id
    utub_url_b.url_title = "unrelated b"
    db.session.add(utub_url_b)
    db.session.commit()

    tag_b = Utub_Tags(
        utub_id=new_utub.id,
        tag_string=query_term,
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

    return new_utub.id


def test_search_returns_grouped_ranked_results(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Happy path: 200 + success envelope with grouped, best-ranked results.

    Seeded titles are ``f"This is {url_string}"`` and url strings begin with
    ``https://`` — so ``"https"`` matches title + url on every URL but no tag.
    """
    logged_in_client, _, _, _ = login_first_user_without_register

    response = logged_in_client.get(
        url_for(ROUTES.SEARCH.SEARCH) + f"?q={_HTTPS_QUERY}"
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS

    groups = body[M.SEARCH_RESULTS]
    assert isinstance(groups, list)
    assert len(groups) > 0

    all_titles_at_max_score: list[str] = []
    for group in groups:
        assert UTUB_ID in group
        assert UTUB_NAME in group
        assert M.URLS in group
        for hit in group[M.URLS]:
            assert M.UTUB_URL_ID in hit
            assert M.URL_STRING in hit
            assert M.URL_TITLE in hit
            assert M.URL_TAGS in hit
            assert M.MATCHED_FIELDS in hit
            # Every hit here matches title + url, the maximum score for "https".
            all_titles_at_max_score.append(hit[M.URL_TITLE])

    best_ranked_title = min(all_titles_at_max_score)
    assert groups[0][M.URLS][0][M.URL_TITLE] == best_ranked_title
    assert groups[0][M.URLS][0][M.MATCHED_FIELDS] == ["title", "url"]


def test_search_excludes_non_member_utubs(
    add_first_user_to_second_utub_and_add_tags_remove_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """User 2 is not a member of UTub 1, so a match there never surfaces."""
    logged_in_client, _, _, _ = login_second_user_without_register

    response = logged_in_client.get(
        url_for(ROUTES.SEARCH.SEARCH) + f"?q={_HTTPS_QUERY}"
    )

    assert response.status_code == 200
    body = response.get_json()
    returned_utub_ids = {group[UTUB_ID] for group in body[M.SEARCH_RESULTS]}
    assert 1 not in returned_utub_ids


def test_search_blank_query_returns_400(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A whitespace-only ``q`` strips to empty and fails ``min_length`` → 400."""
    logged_in_client, _, _, _ = login_first_user_without_register

    response = logged_in_client.get(_SEARCH_PATH + "?q=%20%20")

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == SearchFailureMessages.INVALID_QUERY
    assert body[STD_JSON.ERROR_CODE] == SearchErrorCodes.INVALID_QUERY_PARAM


def test_search_missing_query_returns_400(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """``q`` is a required field — its absence fails validation → 400."""
    logged_in_client, _, _, _ = login_first_user_without_register

    response = logged_in_client.get(_SEARCH_PATH)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == SearchFailureMessages.INVALID_QUERY
    assert body[STD_JSON.ERROR_CODE] == SearchErrorCodes.INVALID_QUERY_PARAM


def test_search_no_match_returns_empty_list(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A query present nowhere returns 200 with an empty results list."""
    logged_in_client, _, _, _ = login_first_user_without_register

    response = logged_in_client.get(
        url_for(ROUTES.SEARCH.SEARCH) + f"?q={_NO_MATCH_QUERY}"
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[M.SEARCH_RESULTS] == []


def test_search_unauthenticated_redirects(client: FlaskClient) -> None:
    """Anonymous request 302-redirects (auth decorator), not a JSON 401."""
    response = client.get(_SEARCH_PATH + f"?q={_HTTPS_QUERY}")

    assert response.status_code == 302


def test_search_non_ajax_redirects_to_home(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A non-AJAX request (``ajax_required=True``) 302-redirects to home."""
    logged_in_client, _, _, _ = login_first_user_without_register

    response = logged_in_client.get(
        _SEARCH_PATH + f"?q={_HTTPS_QUERY}",
        headers={URL_VALIDATION.X_REQUESTED_WITH: "not-ajax"},
    )

    assert response.status_code == 302
    assert response.location is not None
    assert urlsplit(response.location).path == _HOME_PATH


def test_search_route_honors_fields_subset(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A `fields` subset excluding the only matching field filters the hit out."""
    logged_in_client, _, _, app = login_first_user_without_register
    query_term = "subsetrouteterm"

    with app.app_context():
        seed_single_utub_with_one_url(
            user_id=FIRST_USER_ID,
            utub_name="SubsetRoute UTub",
            url_string="https://nomatch-subsetroute.com/",
            url_title="unrelated",
            tag_strings=[query_term],
        )

    base_url = url_for(ROUTES.SEARCH.SEARCH) + f"?q={query_term}"

    default_response = logged_in_client.get(base_url)
    assert default_response.status_code == 200
    default_body = default_response.get_json()
    default_groups = default_body[M.SEARCH_RESULTS]
    assert len(default_groups) >= 1
    assert sum(len(group[M.URLS]) for group in default_groups) >= 1

    filtered_response = logged_in_client.get(base_url + "&fields=title,url")
    assert filtered_response.status_code == 200
    filtered_body = filtered_response.get_json()
    filtered_hits = sum(len(group[M.URLS]) for group in filtered_body[M.SEARCH_RESULTS])
    assert filtered_hits == 0


def test_search_route_honors_fields_order(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Field ordering flips which URL ranks first within a group at the HTTP layer."""
    logged_in_client, _, _, app = login_first_user_without_register
    query_term = "orderrouteterm"

    with app.app_context():
        seeded_utub_id = _seed_utub_with_title_and_tag_match(
            user_id=FIRST_USER_ID,
            utub_name="OrderRoute UTub",
            query_term=query_term,
        )

    base_url = url_for(ROUTES.SEARCH.SEARCH) + f"?q={query_term}"

    default_response = logged_in_client.get(base_url)
    assert default_response.status_code == 200
    default_body = default_response.get_json()
    default_group = next(
        group
        for group in default_body[M.SEARCH_RESULTS]
        if group[UTUB_ID] == seeded_utub_id
    )
    assert default_group[M.URLS][0][M.URL_TITLE] == f"{query_term} title"

    flipped_response = logged_in_client.get(base_url + "&fields=tag,title")
    assert flipped_response.status_code == 200
    flipped_body = flipped_response.get_json()
    flipped_group = next(
        group
        for group in flipped_body[M.SEARCH_RESULTS]
        if group[UTUB_ID] == seeded_utub_id
    )
    assert flipped_group[M.URLS][0][M.URL_TITLE] == "unrelated b"


def test_search_route_rejects_invalid_fields_token(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """An unknown `fields` token fails enum validation → 400 with the error envelope."""
    logged_in_client, _, _, _ = login_first_user_without_register

    response = logged_in_client.get(_SEARCH_PATH + "?q=x&fields=author")

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == SearchFailureMessages.INVALID_QUERY
    assert body[STD_JSON.ERROR_CODE] == SearchErrorCodes.INVALID_QUERY_PARAM


def test_search_route_rejects_duplicate_fields_token(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A duplicated `fields` token in the comma list fails validation → 400."""
    logged_in_client, _, _, _ = login_first_user_without_register

    response = logged_in_client.get(_SEARCH_PATH + "?q=x&fields=title,title")

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == SearchFailureMessages.INVALID_QUERY
    assert body[STD_JSON.ERROR_CODE] == SearchErrorCodes.INVALID_QUERY_PARAM


def test_search_route_omitted_fields_searches_all(
    register_multiple_users,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Omitting `fields` preserves the all-fields default behavior."""
    logged_in_client, _, _, app = login_first_user_without_register
    query_term = "omittedrouteterm"

    with app.app_context():
        seed_single_utub_with_one_url(
            user_id=FIRST_USER_ID,
            utub_name="OmittedRoute UTub",
            url_string="https://nomatch-omittedroute.com/",
            url_title="unrelated",
            tag_strings=[query_term],
        )

    response = logged_in_client.get(url_for(ROUTES.SEARCH.SEARCH) + f"?q={query_term}")

    assert response.status_code == 200
    body = response.get_json()
    groups = body[M.SEARCH_RESULTS]
    assert len(groups) >= 1
    total_hits = sum(len(group[M.URLS]) for group in groups)
    assert total_hits >= 1
