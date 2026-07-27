from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from dateutil.relativedelta import relativedelta
from flask import Flask

from backend import db
from backend.models.users import Users
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.users.services.stats_service import (
    _humanize_account_age,
    build_user_stats_context,
)
from tests.utils_for_test import seed_distinct_stats_for_user_one

pytestmark = pytest.mark.unit

# Where build_user_stats_context reads the acting user from; patched per-case
# to a seeded password user so the counting queries resolve against real rows.
_CURRENT_USER_TARGET = "backend.users.services.stats_service.current_user"

# A fixed "now" the humanizer measures against (patched in per-case below), so
# the parametrized offsets below produce deterministic phrases regardless of
# when the suite runs.
_FIXED_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "created_offset, expected_phrase",
    [
        (relativedelta(years=1), "1 year"),
        (relativedelta(years=2), "2 years"),
        (relativedelta(months=2), "2 months"),
        (relativedelta(months=1), "1 month"),
        (relativedelta(days=1), "1 day"),
        (relativedelta(days=3), "3 days"),
        (relativedelta(), "Joined today"),
        # One unit below a year rollover: still months, proving unit selection
        # rides relativedelta's own calendar rollover, not manual day-count math.
        (relativedelta(months=11, days=29), "11 months"),
    ],
)
def test_humanize_account_age(created_offset, expected_phrase):
    """
    GIVEN an account created a fixed relativedelta before a fixed "now"
    WHEN _humanize_account_age renders the age
    THEN it returns the largest-unit phrase with correct pluralization
    """
    created_at = _FIXED_NOW - created_offset
    with patch("backend.users.services.stats_service.utc_now", return_value=_FIXED_NOW):
        assert _humanize_account_age(created_at) == expected_phrase


def _create_sequential_users(count: int) -> list[Users]:
    """Create ``count`` password users with sequential ids starting at 1 (the
    ``app`` fixture resets DB sequences per test) and commit, so the stats
    queries and the FK-bound seed rows can reference them by literal id."""
    created_users: list[Users] = []
    for user_index in range(1, count + 1):
        user = Users(
            username=f"statsuser{user_index}",
            email=f"statsuser{user_index}@example.com",
            plaintext_password="a-strong-password",
        )
        db.session.add(user)
        created_users.append(user)
    db.session.commit()
    return created_users


def test_build_user_stats_context_zero_state(app: Flask):
    """
    GIVEN an authenticated user with no created UTubs, memberships, URLs, or tags
    WHEN build_user_stats_context builds the Stats panel context
    THEN every personal count is 0 and the member-since values are still populated
    """
    with app.app_context():
        (user_one,) = _create_sequential_users(1)
        with patch(_CURRENT_USER_TARGET, user_one):
            context = build_user_stats_context()

        assert context["stats_utubs_created"] == 0
        assert context["stats_member_of"] == 0
        assert context["stats_urls_added"] == 0
        assert context["stats_tags_created"] == 0
        assert context["stats_tags_applied"] == 0
        # Member-since values derive from created_at regardless of activity.
        assert context["stats_member_since_relative"]
        assert (
            context["stats_member_since_iso"] == user_one.created_at.date().isoformat()
        )


def test_build_user_stats_context_member_of_excludes_created(app: Flask):
    """
    GIVEN user 1 is CREATOR of 2 UTubs and MEMBER of 3 UTubs created by others
    WHEN build_user_stats_context builds the Stats panel context
    THEN "member of" counts only the 3 non-CREATOR memberships, disjoint from
        the 2 self-created UTubs (so a swapped/mislabeled card is caught)
    """
    with app.app_context():
        user_one, _user_two, _user_three = _create_sequential_users(3)
        seed_distinct_stats_for_user_one()
        db.session.commit()

        with patch(_CURRENT_USER_TARGET, user_one):
            context = build_user_stats_context()

        assert context["stats_utubs_created"] == 2
        # Excludes user 1's own CREATOR memberships; counts only the 3 as MEMBER.
        assert context["stats_member_of"] == 3


def test_build_user_stats_context_excludes_null_attributed_tags(app: Flask):
    """
    GIVEN user 1 has 11 attributed Utub_Url_Tags plus one legacy NULL-attributed
        row (user_id=None) on the same url/tag pair
    WHEN build_user_stats_context builds the Stats panel context
    THEN "tags applied" counts only the 11 attributed rows, excluding the NULL
        row (proving NULL-attributed rows are excluded, not merely uncounted)
    """
    with app.app_context():
        user_one, _user_two, _user_three = _create_sequential_users(3)
        distinct_stats_seed = seed_distinct_stats_for_user_one()
        db.session.add(
            Utub_Url_Tags(
                utub_id=distinct_stats_seed.home_utub.id,
                utub_url_id=distinct_stats_seed.user_one_utub_urls[0].id,
                utub_tag_id=distinct_stats_seed.user_one_tags[0].id,
                user_id=None,
            )
        )
        db.session.commit()

        with patch(_CURRENT_USER_TARGET, user_one):
            context = build_user_stats_context()

        # 11 real user-1 applications; the NULL-attributed row is excluded.
        assert context["stats_tags_applied"] == 11
        # Sanity: the other per-user distinct counts hold under this seed.
        assert context["stats_tags_created"] == 7
        assert context["stats_urls_added"] == 5
