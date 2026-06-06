from __future__ import annotations

import pytest
from flask import Flask, url_for
from redis import Redis

from backend import db
from backend.extensions.metrics.registry_sync import sync_event_registry
from backend.metrics.events import EVENT_CATEGORY, EventCategory, EventName
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.form_strs import ADD_USER_FORM, TAG_FORM, URL_FORM, UTUB_FORM
from scripts.flush_metrics import run_flush
from tests.conftest import AjaxFlaskLoginClient
from tests.integration.system.conftest import reset_postgres_enum_to_lowercase_values
from tests.integration.system.metrics_helpers import (
    build_pg_conn,
    truncate_metrics_tables,
)
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.cli


def test_domain_events_flush_with_intact_fk_joins(
    metrics_enabled_runner_app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a freshly-synced `EventRegistry` (one row per `EventName`), the
        metrics_writer extension enabled with the per-worker metrics-DB
        Redis client, and the test DB seeded with a single user, UTub,
        URL, URL-UTub association, UTub tag, and a second user — all
        inserted via the ORM bypassing the service layer so no
        `record_event` fires during setup
    WHEN each of the 11 instrumented DOMAIN routes is hit exactly once
        through an authenticated Flask client (non-destructive routes
        first, the destructive UTUB_DELETED last and targeting a freshly
        created UTub so cascade cannot wipe the resources earlier routes
        depend on), then `run_flush(...)` drains Redis into Postgres
    THEN every DOMAIN event appears in `AnonymousMetrics` after
        an INNER JOIN against `EventRegistry` — proving the FK relation
        holds and no event was silently dropped between
        `record_event(...)`, the writer's batch dispatch, and the flush.

    End-to-end regression guard for the DOMAIN instrumentation pipeline.
    Auto-extends to any future DOMAIN event by iterating
    `EVENT_CATEGORY` (excluding the deferred `URL_ACCESSED`).
    """
    app = metrics_enabled_runner_app

    setup_conn = build_pg_conn(app)
    try:
        reset_postgres_enum_to_lowercase_values(setup_conn)
    finally:
        setup_conn.close()

    with app.app_context():
        sync_event_registry(app)

        first_user = Users(
            username="DomainE2EUser1234",
            email="domaine2e1234@email.com",
            plaintext_password="DomainE2EPassword1234",
        )
        first_user.email_validated = True
        db.session.add(first_user)
        db.session.commit()
        first_user_id = first_user.id

        seeded_utub = Utubs(
            name="Domain E2E UTub",
            utub_creator=first_user_id,
            utub_description="Initial e2e description",
        )
        creator_membership = Utub_Members(member_role=Member_Role.CREATOR)
        creator_membership.to_user = first_user
        seeded_utub.members.append(creator_membership)
        db.session.add(seeded_utub)
        db.session.commit()
        seeded_utub_id = seeded_utub.id

        url_row = Urls(
            normalized_url="https://www.domain-e2e-example.com",
            current_user_id=first_user_id,
        )
        db.session.add(url_row)
        db.session.commit()

        utub_url = Utub_Urls()
        utub_url.utub_id = seeded_utub_id
        utub_url.url_id = url_row.id
        utub_url.user_id = first_user_id
        utub_url.url_title = "E2E URL Title"
        db.session.add(utub_url)
        db.session.commit()
        utub_url_id = utub_url.id

        tag_row = Utub_Tags(
            utub_id=seeded_utub_id,
            tag_string="e2e-tag",
            created_by=first_user_id,
        )
        db.session.add(tag_row)
        db.session.commit()
        tag_id = tag_row.id

        second_user = Users(
            username="DomainE2EOther1234",
            email="domaine2eother1234@email.com",
            plaintext_password="OtherE2EPassword1234",
        )
        second_user.email_validated = True
        db.session.add(second_user)
        db.session.commit()
        second_user_id = second_user.id

    app.test_client_class = AjaxFlaskLoginClient
    # Re-fetch the creator inside the same app context that opens the test
    # client. `runner` uses `clear_database` teardown (no SAVEPOINT and no
    # session-remove no-op), so the prior context's commits expire the
    # original instance; `flask_login.test_client` lazy-loads `user.id`
    # when stamping the session and would raise `DetachedInstanceError`
    # if the user lives outside an active session.
    with app.app_context():
        creator_for_login = Users.query.get(first_user_id)
        with app.test_client(user=creator_for_login) as authenticated_client:
            home_response = authenticated_client.get("/home")
            csrf_token = get_csrf_token(home_response.get_data(), meta_tag=True)

            # UTUB_OPENED — read-only.
            utub_open_response = authenticated_client.get(
                url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=seeded_utub_id),
                headers={"X-CSRFToken": csrf_token},
            )
            assert utub_open_response.status_code == 200

            # UTUB_TITLE_UPDATED.
            utub_name_response = authenticated_client.patch(
                url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=seeded_utub_id),
                json={UTUB_FORM.UTUB_NAME: "Renamed E2E UTub"},
                headers={"X-CSRFToken": csrf_token},
            )
            assert utub_name_response.status_code == 200

            # UTUB_DESC_UPDATED.
            utub_desc_response = authenticated_client.patch(
                url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=seeded_utub_id),
                json={UTUB_FORM.UTUB_DESCRIPTION: "Updated e2e description"},
                headers={"X-CSRFToken": csrf_token},
            )
            assert utub_desc_response.status_code == 200

            # URL_TITLE_UPDATED.
            url_title_response = authenticated_client.patch(
                url_for(
                    ROUTES.URLS.UPDATE_URL_TITLE,
                    utub_id=seeded_utub_id,
                    utub_url_id=utub_url_id,
                ),
                json={URL_FORM.URL_TITLE: "Renamed E2E URL Title"},
                headers={"X-CSRFToken": csrf_token},
            )
            assert url_title_response.status_code == 200

            # TAG_APPLIED — creates the `Utub_Url_Tags` association.
            tag_apply_response = authenticated_client.post(
                url_for(
                    ROUTES.URL_TAGS.CREATE_URL_TAG,
                    utub_id=seeded_utub_id,
                    utub_url_id=utub_url_id,
                ),
                json={TAG_FORM.TAG_STRING: "e2e-tag"},
                headers={"X-CSRFToken": csrf_token},
            )
            assert tag_apply_response.status_code == 200

            # TAG_REMOVED — removes the `Utub_Url_Tags` association; the
            # `Utub_Tags` row persists for TAG_DELETED next.
            tag_remove_response = authenticated_client.delete(
                url_for(
                    ROUTES.URL_TAGS.DELETE_URL_TAG,
                    utub_id=seeded_utub_id,
                    utub_url_id=utub_url_id,
                    utub_tag_id=tag_id,
                ),
                headers={"X-CSRFToken": csrf_token},
            )
            assert tag_remove_response.status_code == 200

            # TAG_DELETED — removes the `Utub_Tags` definition row.
            tag_delete_response = authenticated_client.delete(
                url_for(
                    ROUTES.UTUB_TAGS.DELETE_UTUB_TAG,
                    utub_id=seeded_utub_id,
                    utub_tag_id=tag_id,
                ),
                headers={"X-CSRFToken": csrf_token},
            )
            assert tag_delete_response.status_code == 200

            # MEMBER_ADDED.
            member_add_response = authenticated_client.post(
                url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=seeded_utub_id),
                json={ADD_USER_FORM.USERNAME: "DomainE2EOther1234"},
                headers={"X-CSRFToken": csrf_token},
            )
            assert member_add_response.status_code == 200

            # MEMBER_REMOVED.
            member_remove_response = authenticated_client.delete(
                url_for(
                    ROUTES.MEMBERS.REMOVE_MEMBER,
                    utub_id=seeded_utub_id,
                    user_id=second_user_id,
                ),
                headers={"X-CSRFToken": csrf_token},
            )
            assert member_remove_response.status_code == 200

            # UTUB_CREATED — fresh UTub solely to fire this event; isolated
            # from the seeded UTub so the next UTUB_DELETED call does not
            # cascade-wipe state earlier assertions depended on.
            utub_create_response = authenticated_client.post(
                url_for(ROUTES.UTUBS.CREATE_UTUB),
                json={
                    UTUB_FORM.UTUB_NAME: "Fresh E2E UTub",
                    UTUB_FORM.UTUB_DESCRIPTION: "",
                },
                headers={"X-CSRFToken": csrf_token},
            )
            assert utub_create_response.status_code == 200
            new_utub_id = int(utub_create_response.json["utubID"])

            # UTUB_DELETED — only the freshly created UTub.
            utub_delete_response = authenticated_client.delete(
                url_for(ROUTES.UTUBS.DELETE_UTUB, utub_id=new_utub_id),
                headers={"X-CSRFToken": csrf_token},
            )
            assert utub_delete_response.status_code == 200

    # Auto-extending set of expected DOMAIN events (excluding deferred
    # URL_ACCESSED). Any future DOMAIN event added to `EventName` is
    # picked up here automatically.
    expected_event_values = [
        event.value
        for event in EventName
        if EVENT_CATEGORY[event] is EventCategory.DOMAIN
        and event is not EventName.URL_ACCESSED
    ]

    flush_conn = build_pg_conn(app)
    try:
        run_flush(redis_client=provide_metrics_redis, pg_conn=flush_conn)

        with flush_conn.cursor() as cursor:
            cursor.execute(
                'SELECT am."eventName" FROM "AnonymousMetrics" am'
                ' JOIN "EventRegistry" er ON am."eventName" = er."name"'
                ' WHERE am."eventName" = ANY(%s)',
                (expected_event_values,),
            )
            joined_event_names = {row[0] for row in cursor.fetchall()}

        assert joined_event_names == set(expected_event_values), (
            "FK join broke or DOMAIN events missing from AnonymousMetrics: "
            f"missing={set(expected_event_values) - joined_event_names}"
        )
    finally:
        truncate_metrics_tables(flush_conn)
        flush_conn.close()
