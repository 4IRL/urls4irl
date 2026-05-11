from __future__ import annotations

import json
from typing import NamedTuple

import pytest
from flask import Flask, url_for
from redis import Redis

from backend import db
from backend.metrics.events import EVENT_CATEGORY, EventCategory, EventName
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.form_strs import ADD_USER_FORM, TAG_FORM, URL_FORM, UTUB_FORM
from backend.utils.strings.metrics_strs import METRICS_REDIS

pytestmark = pytest.mark.cli


class _NoPiiSeedState(NamedTuple):
    extra_user_id: int
    seeded_utub_id: int
    utub_url_id: int
    tag_id: int


def _seed_no_pii_test_state(app: Flask, creator_user: Users) -> _NoPiiSeedState:
    """
    Seeds the minimum ORM state needed for the PII non-leak guard test without
    invoking any service-layer call sites, which would emit metrics events and
    pollute the Redis counter space before the assertions run.
    """
    with app.app_context():
        extra_user = Users(
            username="MemberRecipient1234",
            email="memberrecipient1234@email.com",
            plaintext_password="Recipient1234Password",
        )
        extra_user.email_validated = True
        db.session.add(extra_user)
        db.session.commit()
        extra_user_id = extra_user.id

        seeded_utub = Utubs(
            name="Seed UTub",
            utub_creator=creator_user.id,
            utub_description="Initial seed description",
        )
        creator_membership = Utub_Members(member_role=Member_Role.CREATOR)
        creator_membership.to_user = creator_user
        seeded_utub.members.append(creator_membership)
        db.session.add(seeded_utub)
        db.session.commit()
        seeded_utub_id = seeded_utub.id

        url_row = Urls(
            normalized_url="https://www.no-pii-seed-example.com",
            current_user_id=creator_user.id,
        )
        db.session.add(url_row)
        db.session.commit()

        utub_url = Utub_Urls()
        utub_url.utub_id = seeded_utub_id
        utub_url.url_id = url_row.id
        utub_url.user_id = creator_user.id
        utub_url.url_title = "Seed URL Title"
        db.session.add(utub_url)
        db.session.commit()
        utub_url_id = utub_url.id

        # `Utub_Tags` definition row only — no `Utub_Url_Tags` association;
        # the TAG_APPLIED route call creates the association during the test.
        tag_row = Utub_Tags(
            utub_id=seeded_utub_id,
            tag_string="seed-tag",
            created_by=creator_user.id,
        )
        db.session.add(tag_row)
        db.session.commit()
        tag_id = tag_row.id

    return _NoPiiSeedState(
        extra_user_id=extra_user_id,
        seeded_utub_id=seeded_utub_id,
        utub_url_id=utub_url_id,
        tag_id=tag_id,
    )


def test_domain_events_emit_no_pii_dimensions(
    metrics_enabled_app,
    provide_metrics_redis: Redis,
    login_first_user_with_register,
):
    """
    GIVEN every DOMAIN event is wired into a service-layer call site
        and metrics are enabled
    WHEN each instrumented route is hit exactly once via the authenticated
        client (after seeding the minimum required state inline so no
        services run during setup)
    THEN every `metrics:counter:*` key written to Redis (excluding the
        incidental API_HIT counters) has an empty canonical-dims segment —
        no `user_id`, `email`, `username`, `utub_id`, `tag_id`, etc. leaks
        into the dimensions payload.

    Structural PII non-leak guard. Auto-extends to any future DOMAIN
    event by iterating `EventCategory.DOMAIN` members (excluding
    `URL_ACCESSED`, which is currently deferred).
    """
    client, csrf_token, user, app = login_first_user_with_register

    seed = _seed_no_pii_test_state(app, user)
    extra_user_id = seed.extra_user_id
    seeded_utub_id = seed.seeded_utub_id
    utub_url_id = seed.utub_url_id
    tag_id = seed.tag_id

    # TAG_APPLIED — creates the `Utub_Url_Tags` row intentionally absent from seed.
    tag_apply_response = client.post(
        url_for(
            ROUTES.URL_TAGS.CREATE_URL_TAG,
            utub_id=seeded_utub_id,
            utub_url_id=utub_url_id,
        ),
        json={TAG_FORM.TAG_STRING: "seed-tag"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert tag_apply_response.status_code == 200

    # TAG_REMOVED — removes the association just created; `Utub_Tags` row persists.
    tag_remove_response = client.delete(
        url_for(
            ROUTES.URL_TAGS.DELETE_URL_TAG,
            utub_id=seeded_utub_id,
            utub_url_id=utub_url_id,
            utub_tag_id=tag_id,
        ),
        headers={"X-CSRFToken": csrf_token},
    )
    assert tag_remove_response.status_code == 200

    # UTUB_OPENED — read-only.
    utub_open_response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=seeded_utub_id),
        headers={"X-CSRFToken": csrf_token},
    )
    assert utub_open_response.status_code == 200

    # UTUB_TITLE_UPDATED — changed name.
    utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=seeded_utub_id),
        json={UTUB_FORM.UTUB_NAME: "Renamed Seed UTub"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert utub_name_response.status_code == 200

    # UTUB_DESC_UPDATED — changed description.
    utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=seeded_utub_id),
        json={UTUB_FORM.UTUB_DESCRIPTION: "Updated seed description"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert utub_desc_response.status_code == 200

    # URL_TITLE_UPDATED — changed title.
    url_title_response = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=seeded_utub_id,
            utub_url_id=utub_url_id,
        ),
        json={URL_FORM.URL_TITLE: "Renamed Seed URL Title"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert url_title_response.status_code == 200

    # MEMBER_ADDED — extra user.
    member_add_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=seeded_utub_id),
        json={ADD_USER_FORM.USERNAME: "MemberRecipient1234"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert member_add_response.status_code == 200

    # MEMBER_REMOVED — extra user just added.
    member_remove_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=seeded_utub_id,
            user_id=extra_user_id,
        ),
        headers={"X-CSRFToken": csrf_token},
    )
    assert member_remove_response.status_code == 200

    # TAG_DELETED — removes seeded `Utub_Tags` row. TAG_REMOVED already
    # detached the `Utub_Url_Tags` association, so no FK dependency remains.
    tag_delete_response = client.delete(
        url_for(
            ROUTES.UTUB_TAGS.DELETE_UTUB_TAG,
            utub_id=seeded_utub_id,
            utub_tag_id=tag_id,
        ),
        headers={"X-CSRFToken": csrf_token},
    )
    assert tag_delete_response.status_code == 200

    # UTUB_CREATED — fresh UTub solely to fire this event; isolated from the
    # seeded UTub so the next call (UTUB_DELETED) does not cascade-wipe the
    # seeded URL/tag context the preceding assertions depended on.
    utub_create_response = client.post(
        url_for(ROUTES.UTUBS.CREATE_UTUB),
        json={
            UTUB_FORM.UTUB_NAME: "Fresh UTub for Create/Delete",
            UTUB_FORM.UTUB_DESCRIPTION: "",
        },
        headers={"X-CSRFToken": csrf_token},
    )
    assert utub_create_response.status_code == 200
    new_utub_id = int(utub_create_response.json["utubID"])

    # UTUB_DELETED — only the freshly created UTub.
    utub_delete_response = client.delete(
        url_for(ROUTES.UTUBS.DELETE_UTUB, utub_id=new_utub_id),
        headers={"X-CSRFToken": csrf_token},
    )
    assert utub_delete_response.status_code == 200

    # Strip incidental API_HIT counter keys before the dims scan — API_HIT
    # emits non-empty dims (`endpoint`, `method`, `status_code`) for every
    # route call, which is by design, not a PII leak.
    api_hit_pattern = f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{EventName.API_HIT.value}:*"
    api_hit_keys = list(provide_metrics_redis.scan_iter(match=api_hit_pattern))
    if api_hit_keys:
        provide_metrics_redis.delete(*api_hit_keys)

    # Auto-extending set of expected DOMAIN events (excluding the deferred
    # URL_ACCESSED). Any future DOMAIN event added to `EventName` will be
    # picked up here automatically.
    expected_domain_events = {
        event
        for event in EventName
        if EVENT_CATEGORY[event] is EventCategory.DOMAIN
        and event is not EventName.URL_ACCESSED
    }

    counter_keys = list(
        provide_metrics_redis.scan_iter(match=f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*")
    )
    observed_event_values: set[str] = set()
    for counter_key in counter_keys:
        # Key shape: metrics:counter:<bucket>:<event_name>:<dims_json>
        decoded = counter_key.decode("utf-8")
        parts = decoded.split(":", 4)
        event_value = parts[3]
        dims = json.loads(parts[4])
        assert dims == {}, f"DOMAIN counter leaked PII dims: key={decoded}, dims={dims}"
        observed_event_values.add(event_value)

    expected_event_values = {event.value for event in expected_domain_events}
    assert expected_event_values.issubset(observed_event_values), (
        "Missing DOMAIN events in Redis counters: "
        f"{expected_event_values - observed_event_values}"
    )
