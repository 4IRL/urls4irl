from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.metrics.events import EventName
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.model_strs import MODELS as M
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)

pytestmark = pytest.mark.urls

_HAS_RESULTS_DIM_KEY = "has_results"
_MATCHING_QUERY = "https"
_NO_MATCH_QUERY = "zzzznomatch"


def test_search_with_results_records_metric_with_has_results_true(
    metrics_enabled_app,
    provide_metrics_redis,
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in user with seeded member UTubs and metrics enabled
    WHEN they GET "/search?q=https" (a query that matches at least one group)
    THEN the request succeeds AND exactly one CROSS_UTUB_SEARCH_PERFORMED counter
        key is written with has_results="true".
    """
    logged_in_client, _, _, _ = login_first_user_without_register

    # Before-state: no CROSS_UTUB_SEARCH_PERFORMED counter exists yet
    assert (
        count_counter_keys(provide_metrics_redis, EventName.CROSS_UTUB_SEARCH_PERFORMED)
        == 0
    )

    response = logged_in_client.get(
        url_for(ROUTES.SEARCH.SEARCH) + f"?q={_MATCHING_QUERY}"
    )

    assert response.status_code == 200
    assert len(response.get_json()[M.SEARCH_RESULTS]) > 0

    counter_keys = find_counter_keys(
        provide_metrics_redis, EventName.CROSS_UTUB_SEARCH_PERFORMED
    )
    assert len(counter_keys) == 1
    assert parse_dims(counter_keys[0])[_HAS_RESULTS_DIM_KEY] == "true"


def test_search_with_no_results_records_metric_with_has_results_false(
    metrics_enabled_app,
    provide_metrics_redis,
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in user with seeded member UTubs and metrics enabled
    WHEN they GET "/search?q=zzzznomatch" (a query that matches nothing)
    THEN the request succeeds with an empty results list AND exactly one
        CROSS_UTUB_SEARCH_PERFORMED counter key is written with has_results="false".
    """
    logged_in_client, _, _, _ = login_first_user_without_register

    # Before-state: no CROSS_UTUB_SEARCH_PERFORMED counter exists yet
    assert (
        count_counter_keys(provide_metrics_redis, EventName.CROSS_UTUB_SEARCH_PERFORMED)
        == 0
    )

    response = logged_in_client.get(
        url_for(ROUTES.SEARCH.SEARCH) + f"?q={_NO_MATCH_QUERY}"
    )

    assert response.status_code == 200
    assert response.get_json()[M.SEARCH_RESULTS] == []

    counter_keys = find_counter_keys(
        provide_metrics_redis, EventName.CROSS_UTUB_SEARCH_PERFORMED
    )
    assert len(counter_keys) == 1
    assert parse_dims(counter_keys[0])[_HAS_RESULTS_DIM_KEY] == "false"
