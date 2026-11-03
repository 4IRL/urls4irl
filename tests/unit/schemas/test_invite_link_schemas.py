"""Unit tests for the invite link request/response schemas and the status mapper."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from backend.invite_links.constants import (
    INVITE_LINK_EXPIRY_DAYS_VALUES,
    INVITE_LINK_MAX_USES_VALUES,
    InviteLinkErrorCodes,
    InviteLinkStatus,
    InviteState,
)
from backend.invite_links.validity import invite_state_to_link_status
from backend.schemas.invite_links import InviteLinkResponseSchema, InviteLinkSchema
from backend.schemas.requests.invite_links import (
    InviteLinkSettingsRequest,
    UpdateInviteLinkRequest,
)
from backend.utils.strings.invite_link_strs import INVITE_LINK_ERROR_MESSAGES

pytestmark = pytest.mark.unit


def _literal_values(model: type, field: str) -> set[Any]:
    annotation = model.model_fields[field].annotation
    values: set[Any] = set()
    for member in get_args(annotation):
        values.update(get_args(member) or ([] if member is type(None) else [member]))
    return values


def test_literals_match_constants() -> None:
    """
    GIVEN the DD-5 closed-set constants
    WHEN compared with the request schema Literals
    THEN they are identical
    """
    for model in (InviteLinkSettingsRequest, UpdateInviteLinkRequest):
        assert _literal_values(model, "expires_in_days") == set(
            INVITE_LINK_EXPIRY_DAYS_VALUES
        )
        assert _literal_values(model, "max_uses") == set(INVITE_LINK_MAX_USES_VALUES)


def test_error_messages_cover_every_error_code() -> None:
    """
    GIVEN the InviteLinkErrorCodes enum
    WHEN compared with INVITE_LINK_ERROR_MESSAGES
    THEN every code has exactly one message
    """
    assert set(INVITE_LINK_ERROR_MESSAGES) == set(InviteLinkErrorCodes)


@pytest.mark.parametrize(
    "body",
    [
        {"expires_in_days": 7, "max_uses": None},
        {"expires_in_days": 1, "max_uses": 25},
        {"expires_in_days": 30},
        {"max_uses": 10},
    ],
)
def test_update_accepts_valid_bodies(body: dict[str, Any]) -> None:
    """
    GIVEN valid single-field and two-field update bodies
    WHEN validated
    THEN they are accepted and only the supplied fields are marked set
    """
    request = UpdateInviteLinkRequest.model_validate(body)
    assert request.model_fields_set == set(body)


def test_update_null_expiry_alone_rejected() -> None:
    """
    GIVEN {"expires_in_days": null} alone
    WHEN validated
    THEN it is rejected
    """
    with pytest.raises(ValidationError):
        UpdateInviteLinkRequest.model_validate({"expires_in_days": None})


def test_settings_defaults() -> None:
    """
    GIVEN an empty settings body
    WHEN validated
    THEN expiry defaults to 7 days and max_uses to unlimited
    """
    request = InviteLinkSettingsRequest.model_validate({})
    assert request.expires_in_days == 7
    assert request.max_uses is None


@pytest.mark.parametrize("days", INVITE_LINK_EXPIRY_DAYS_VALUES)
@pytest.mark.parametrize("uses", [*INVITE_LINK_MAX_USES_VALUES, None])
def test_settings_accepts_closed_sets(days: int, uses: int | None) -> None:
    """
    GIVEN every allowed expiry and use-limit combination
    WHEN validated
    THEN the values are kept
    """
    request = InviteLinkSettingsRequest.model_validate(
        {"expires_in_days": days, "max_uses": uses}
    )
    assert (request.expires_in_days, request.max_uses) == (days, uses)


@pytest.mark.parametrize("bad", ["7", True, 2, 0, 7.0, None, -1, 365])
def test_settings_rejects_bad_expiry(bad: Any) -> None:
    """
    GIVEN an expiry outside the closed set or of the wrong type
    WHEN validated
    THEN it is rejected
    """
    with pytest.raises(ValidationError):
        InviteLinkSettingsRequest.model_validate({"expires_in_days": bad})


@pytest.mark.parametrize("bad", ["5", True, 2, 0, 5.0, -1, 100])
def test_settings_rejects_bad_max_uses(bad: Any) -> None:
    """
    GIVEN a use limit outside the closed set or of the wrong type
    WHEN validated
    THEN it is rejected
    """
    with pytest.raises(ValidationError):
        InviteLinkSettingsRequest.model_validate({"max_uses": bad})


def test_update_empty_body_rejected() -> None:
    """
    GIVEN an update body with neither field
    WHEN validated
    THEN it is rejected
    """
    with pytest.raises(ValidationError):
        UpdateInviteLinkRequest.model_validate({})


def test_update_explicit_null_max_uses_is_valid_and_distinct() -> None:
    """
    GIVEN {"max_uses": null} and a body that sets only expires_in_days
    WHEN validated
    THEN null max_uses is a set field, and an absent one is not
    """
    nulled = UpdateInviteLinkRequest.model_validate({"max_uses": None})
    assert "max_uses" in nulled.model_fields_set
    assert nulled.max_uses is None

    only_days = UpdateInviteLinkRequest.model_validate({"expires_in_days": 30})
    assert "max_uses" not in only_days.model_fields_set


def test_update_rejects_null_expiry() -> None:
    """
    GIVEN an explicit null expires_in_days
    WHEN validated
    THEN it is rejected, even alongside a valid max_uses
    """
    with pytest.raises(ValidationError):
        UpdateInviteLinkRequest.model_validate({"expires_in_days": None, "max_uses": 5})


@pytest.mark.parametrize(
    "body",
    [
        {"expires_in_days": "7"},
        {"expires_in_days": True},
        {"expires_in_days": 7.0},
        {"expires_in_days": 2},
        {"expires_in_days": 0},
        {"max_uses": 2},
        {"max_uses": "5"},
        {"max_uses": True},
        {"max_uses": 5.0},
    ],
)
def test_update_rejects_bad_values(body: dict[str, Any]) -> None:
    """
    GIVEN strings, booleans or values outside the sets
    WHEN validated as an update
    THEN they are rejected
    """
    with pytest.raises(ValidationError):
        UpdateInviteLinkRequest.model_validate(body)


def test_response_schema_keeps_null_invite_link() -> None:
    """
    GIVEN a response with no link
    WHEN serialized by alias
    THEN inviteLink is present and null
    """
    dumped = InviteLinkResponseSchema(status="Success", invite_link=None).model_dump(
        by_alias=True
    )
    assert dumped == {"status": "Success", "inviteLink": None}
    json_schema = InviteLinkResponseSchema.model_json_schema()
    assert set(json_schema["required"]) == {"status", "inviteLink"}
    assert {"type": "null"} in json_schema["properties"]["inviteLink"]["anyOf"]


def test_link_schema_camel_case_and_iso_dates() -> None:
    """
    GIVEN a populated link
    WHEN serialized by alias
    THEN keys are camelCase, dates ISO-8601 and a null creator is kept
    """
    moment = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    link = InviteLinkSchema(
        token="T" * 22,
        status=InviteLinkStatus.LIVE,
        expires_at=moment,
        max_uses=None,
        use_count=2,
        created_at=moment,
        creator_username=None,
    )
    dumped = link.model_dump(by_alias=True)
    assert dumped == {
        "token": "T" * 22,
        "status": "live",
        "expiresAt": moment.isoformat(),
        "maxUses": None,
        "useCount": 2,
        "createdAt": moment.isoformat(),
        "creatorUsername": None,
    }


_EXPECTED_STATUS: dict[InviteState, InviteLinkStatus | None] = {
    InviteState.LIVE: InviteLinkStatus.LIVE,
    InviteState.UTUB_LOCKED: InviteLinkStatus.LIVE,
    InviteState.EXPIRED: InviteLinkStatus.EXPIRED,
    InviteState.USED_UP: InviteLinkStatus.USED_UP,
    InviteState.CREATOR_NOT_MANAGER: InviteLinkStatus.CREATOR_DEMOTED,
    InviteState.REVOKED: None,
    InviteState.UTUB_TRASHED: None,
}


@pytest.mark.parametrize("state", list(InviteState))
def test_status_mapping_covers_every_state(state: InviteState) -> None:
    """
    GIVEN every InviteState member
    WHEN mapped to a link status
    THEN mappable ones match the contract and the rest raise ValueError
    """
    assert state in _EXPECTED_STATUS, "new InviteState needs an explicit decision"
    expected = _EXPECTED_STATUS[state]
    if expected is None:
        with pytest.raises(ValueError):
            invite_state_to_link_status(state)
    else:
        assert invite_state_to_link_status(state) is expected


def test_unknown_state_raises() -> None:
    """
    GIVEN a value that is not an InviteState
    WHEN mapped
    THEN it raises rather than mapping to live
    """
    with pytest.raises(ValueError):
        invite_state_to_link_status("future_state")  # type: ignore[arg-type]
