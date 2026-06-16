from typing import Tuple
from urllib.parse import urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.models.users import Users
from backend.search.constants import SearchErrorCodes, SearchFailureMessages
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME

pytestmark = pytest.mark.urls

_SEARCH_PATH = "/search"
_HOME_PATH = "/home"
_HTTPS_QUERY = "https"
_NO_MATCH_QUERY = "zzzznomatch"


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
