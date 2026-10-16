"""Unit coverage tying the Trash purge admin copy to the retention constant.

The card description and confirm body keep the retention window as a literal in the
copy (like the audit-purge card). This test fails when ``TRASH_RETENTION_DAYS`` changes
without the copy being updated, so the UI cannot silently disagree with the sweep.
"""

from __future__ import annotations

import pytest

from backend.utils.strings.admin_portal_strs import ADMIN_PORTAL_STRINGS
from scripts.trash_retention import TRASH_RETENTION_DAYS

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "copy",
    [
        ADMIN_PORTAL_STRINGS.OPS_TRASH_PURGE_DESC,
        ADMIN_PORTAL_STRINGS.OPS_TRASH_PURGE_CONFIRM_BODY,
    ],
    ids=["card_description", "confirm_body"],
)
def test_trash_purge_copy_embeds_the_retention_days(copy: str) -> None:
    """
    GIVEN the Trash purge card description and confirm-modal body
    WHEN they are compared with TRASH_RETENTION_DAYS
    THEN each states the retention window as "<TRASH_RETENTION_DAYS> days"
    """
    assert f"{TRASH_RETENTION_DAYS} days" in copy
