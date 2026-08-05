"""Integration tests for the guard-free user-data-export core.

Exercises the extractable-core serializer that walks every UTub the acting
user belongs to (created + joined) and emits a purpose-built export schema —
mirroring the guard-free-core pattern in ``test_account_removal_core.py`` so it
is unit/integration-testable without any HTTP/route/guard concern:

    backend.users.services.data_export_service.build_user_data_export_core

The rich seed (``seed_distinct_stats_for_user_one`` via the
``login_first_user_with_distinct_stats`` fixture) gives user 1 two created and
four member-of UTubs, so the role casing, membership breadth, and URL/tag/member
nesting can all be asserted against known counts.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend.models.users import Users
from backend.users.services.data_export_service import build_user_data_export_core
from backend.utils.datetime_utils import utc_now

pytestmark = pytest.mark.account_and_support


def test_data_export_core_serializes_all_memberships(
    login_first_user_with_distinct_stats: Tuple[FlaskClient, Users, Flask],
) -> None:
    """The core returns the account block plus every UTub the user is a member
    of (created + joined), with lowercase ``Member_Role.value`` roles, nested
    URLs/tags/members, and no secret or session fields anywhere."""
    _logged_in_client, seeded_user, app = login_first_user_with_distinct_stats

    with app.app_context():
        acting_user: Users = Users.query.get(seeded_user.id)
        generated_at: datetime = utc_now()
        export = build_user_data_export_core(
            user=acting_user, generated_at=generated_at
        )

    # ---- Account block ----
    assert export.account.id == 1
    assert export.account.username == seeded_user.username
    assert export.account.email == seeded_user.email
    assert isinstance(export.account.member_since, datetime)
    assert export.exported_at == generated_at

    # ---- Membership breadth: 2 created + 4 member-of = 6 total ----
    assert len(export.utubs) == 6
    roles = [utub.role for utub in export.utubs]
    # Roles use the lowercase Member_Role.value form, not the enum-member name.
    assert roles.count("creator") == 2
    assert roles.count("member") == 3
    assert roles.count("cocreator") == 1

    # ---- The created "home" UTub carries the URLs, tag vocab, and members ----
    created_utubs = [utub for utub in export.utubs if utub.role == "creator"]
    home_export = max(created_utubs, key=lambda utub: len(utub.urls))
    assert len(home_export.urls) >= 5
    first_url = home_export.urls[0]
    assert first_url.url.startswith("https://")
    # Applied tags on a URL are a plain list of strings (subscript-accessed
    # from ``associated_tags``, which is list[dict], not model objects).
    assert all(
        isinstance(tag_string, str)
        for url in home_export.urls
        for tag_string in url.tags
    )
    tagged_urls = [url for url in home_export.urls if url.tags]
    assert tagged_urls, "expected at least one URL with applied tags"
    # Tag vocabulary present (>= the 7 user-1 tags seeded).
    assert len(home_export.tags) >= 7
    # Members present.
    assert any(member.user_id == 1 for member in home_export.members)

    # ---- The CO_CREATOR membership surfaces as lowercase "cocreator" ----
    cocreator_utubs = [utub for utub in export.utubs if utub.role == "cocreator"]
    assert len(cocreator_utubs) == 1

    # ---- No secrets / session fields anywhere in the serialized payload ----
    serialized = json.dumps(export.model_dump(by_alias=True, mode="json"))
    assert "password" not in serialized
    assert "sessionsInvalidatedAt" not in serialized
    assert "pendingEmail" not in serialized
