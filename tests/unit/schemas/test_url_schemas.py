from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.schemas.requests.urls import (
    CopyUrlsRequest,
    CreateURLRequest,
    UpdateURLTitleRequest,
)
from backend.schemas.urls import UtubUrlSchema
from backend.utils.constants import TAG_CONSTANTS, URL_CONSTANTS
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_strs import URL_FAILURE

pytestmark = pytest.mark.unit


class _MockUrl:
    id = 1
    url_string = "https://example.com"


class _MockUtubUrl:
    id = 10
    url_title = "Example Site"
    user_id = 2
    added_at = datetime(2024, 3, 9, 12, 0, tzinfo=timezone.utc)
    standalone_url = _MockUrl()
    short_link = None
    associated_tag_ids = [3, 5]
    associated_tags = [
        {MODELS.UTUB_TAG_ID: 3, MODELS.TAG_STRING: "python"},
        {MODELS.UTUB_TAG_ID: 5, MODELS.TAG_STRING: "web"},
    ]


def test_utub_url_schema_dump():
    from backend.schemas.urls import UtubUrlSchema

    schema = UtubUrlSchema.from_orm_url(
        _MockUtubUrl(),
        current_user_id=2,
        viewer_is_manager=True,
        member_ids=frozenset({2}),
    )
    dumped = schema.model_dump(by_alias=True)
    assert dumped[MODELS.UTUB_URL_ID] == 10
    assert dumped[MODELS.URL_STRING] == "https://example.com"
    assert dumped[MODELS.URL_TAG_IDS] == [3, 5]
    assert dumped[MODELS.URL_TITLE] == "Example Site"
    assert dumped[MODELS.CAN_DELETE] is True
    # added_at is serialized to an ISO-8601 string via field_serializer.
    assert dumped["addedAt"] == "2024-03-09T12:00:00+00:00"
    # No short link: null expiry, nobody can revoke.
    assert dumped[MODELS.SHORT_LINK_EXPIRES_AT] is None
    assert dumped[MODELS.CAN_REVOKE_SHORT_LINK] is False


class _MockShortLink:
    def __init__(self, *, expires_at: datetime, created_by: int | None) -> None:
        self.expires_at = expires_at
        self.created_by = created_by

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


def _utub_url_with_link(*, expires_at: datetime, created_by: int | None):
    utub_url = _MockUtubUrl()
    utub_url.short_link = _MockShortLink(expires_at=expires_at, created_by=created_by)
    return utub_url


def test_utub_url_schema_active_short_link_serializes_expiry_iso():
    """
    GIVEN a URL with an unexpired short link
    WHEN a manager serializes it
    THEN shortLinkExpiresAt is the ISO expiry and canRevokeShortLink is true
    """
    expires_at = datetime.now(timezone.utc) + timedelta(days=1)
    schema = UtubUrlSchema.from_orm_url(
        _utub_url_with_link(expires_at=expires_at, created_by=3),
        current_user_id=99,
        viewer_is_manager=True,
        member_ids=frozenset({2, 3, 99}),
    )
    dumped = schema.model_dump(by_alias=True)
    assert dumped[MODELS.SHORT_LINK_EXPIRES_AT] == expires_at.isoformat()
    assert dumped[MODELS.CAN_REVOKE_SHORT_LINK] is True


def test_utub_url_schema_expired_short_link_is_reported_as_none():
    """
    GIVEN a URL whose short link has expired
    WHEN a manager serializes it
    THEN shortLinkExpiresAt is null and canRevokeShortLink is false
    """
    schema = UtubUrlSchema.from_orm_url(
        _utub_url_with_link(
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            created_by=99,
        ),
        current_user_id=99,
        viewer_is_manager=True,
        member_ids=frozenset({2, 99}),
    )
    dumped = schema.model_dump(by_alias=True)
    assert dumped[MODELS.SHORT_LINK_EXPIRES_AT] is None
    assert dumped[MODELS.CAN_REVOKE_SHORT_LINK] is False


@pytest.mark.parametrize(
    "viewer_id, viewer_is_manager, minter_id, member_ids, expected",
    [
        (2, False, 3, {2, 3, 99}, True),  # adder (user 2)
        (99, True, 3, {2, 3, 99}, True),  # manager
        (3, False, 3, {2, 3, 99}, True),  # minter
        (99, False, 3, {2, 3, 99}, False),  # other plain member
        (3, False, 3, {2, 99}, False),  # minter who left the UTub
        (99, False, None, {2, 99}, False),  # minter deleted, plain member
    ],
    ids=["adder", "manager", "minter", "other", "minter-left", "minter-deleted"],
)
def test_utub_url_schema_can_revoke_short_link_matrix(
    viewer_id, viewer_is_manager, minter_id, member_ids, expected
):
    schema = UtubUrlSchema.from_orm_url(
        _utub_url_with_link(
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            created_by=minter_id,
        ),
        current_user_id=viewer_id,
        viewer_is_manager=viewer_is_manager,
        member_ids=frozenset(member_ids),
    )
    assert schema.can_revoke_short_link is expected


def test_utub_url_schema_can_delete_false():
    from backend.schemas.urls import UtubUrlSchema

    schema = UtubUrlSchema.from_orm_url(
        _MockUtubUrl(),
        current_user_id=99,
        viewer_is_manager=False,
        member_ids=frozenset({2, 99}),
    )
    assert schema.can_delete is False


def test_utub_url_schema_can_delete_true_for_orphaned_url_plain_viewer():
    """
    GIVEN a URL whose adder (user 2) is not a current member
    WHEN a plain member (user 99) serializes it
    THEN canDelete is True and addedByUserID keeps the departed adder
    """
    schema = UtubUrlSchema.from_orm_url(
        _MockUtubUrl(),
        current_user_id=99,
        viewer_is_manager=False,
        member_ids=frozenset({99}),
    )
    assert schema.can_delete is True
    assert schema.added_by_user_id == 2


def test_utub_url_schema_can_delete_true_for_manager_with_member_adder():
    """
    GIVEN a URL whose adder is still a member
    WHEN a manager serializes it
    THEN canDelete is True
    """
    schema = UtubUrlSchema.from_orm_url(
        _MockUtubUrl(),
        current_user_id=99,
        viewer_is_manager=True,
        member_ids=frozenset({2, 99}),
    )
    assert schema.can_delete is True


def test_utub_url_schema_missing_required_fields():
    from backend.schemas.urls import UtubUrlSchema

    with pytest.raises(ValidationError):
        UtubUrlSchema()


def test_utub_url_detail_schema_dump():
    from backend.schemas.urls import UtubUrlDetailSchema

    schema = UtubUrlDetailSchema.from_orm_url(_MockUtubUrl())
    dumped = schema.model_dump(by_alias=True)
    assert dumped[MODELS.UTUB_URL_ID] == 10
    assert dumped[MODELS.URL_TITLE] == "Example Site"
    assert dumped[MODELS.URL_STRING] == "https://example.com"
    assert len(dumped[MODELS.URL_TAGS]) == 2
    assert dumped[MODELS.URL_TAGS][0] == {
        MODELS.UTUB_TAG_ID: 3,
        MODELS.TAG_STRING: "python",
    }
    assert dumped[MODELS.URL_TAGS][1] == {
        MODELS.UTUB_TAG_ID: 5,
        MODELS.TAG_STRING: "web",
    }


def test_utub_url_detail_schema_missing_required_fields():
    from backend.schemas.urls import UtubUrlDetailSchema

    with pytest.raises(ValidationError):
        UtubUrlDetailSchema()


def test_utub_url_detail_schema_validate_from_dict():
    from backend.schemas.urls import UtubUrlDetailSchema

    data = {
        MODELS.UTUB_URL_ID: 10,
        MODELS.URL_TITLE: "Example Site",
        MODELS.URL_STRING: "https://example.com",
        MODELS.URL_TAGS: [
            {MODELS.UTUB_TAG_ID: 3, MODELS.TAG_STRING: "python"},
        ],
    }
    schema = UtubUrlDetailSchema.model_validate(data)
    assert schema.utub_url_id == 10
    assert schema.url_title == "Example Site"
    assert len(schema.url_tags) == 1


def test_utub_url_delete_schema_dump():
    from backend.schemas.urls import UtubUrlDeleteSchema

    schema = UtubUrlDeleteSchema(
        utub_url_id=10, url_string="https://example.com", url_title="Example Site"
    )
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {
        MODELS.UTUB_URL_ID: 10,
        MODELS.URL_STRING: "https://example.com",
        MODELS.URL_TITLE: "Example Site",
    }


def test_utub_url_delete_schema_missing_required_fields():
    from backend.schemas.urls import UtubUrlDeleteSchema

    with pytest.raises(ValidationError):
        UtubUrlDeleteSchema()


class TestCreateURLRequestWhitespaceStripping:
    """Tests that CreateURLRequest strips leading/trailing whitespace from urlTitle."""

    def test_strips_leading_and_trailing_whitespace(self):
        request = CreateURLRequest(
            urlString="https://example.com", urlTitle="  hello  "
        )
        assert request.urlTitle == "hello"

    def test_strips_tabs_and_newlines(self):
        request = CreateURLRequest(
            urlString="https://example.com", urlTitle="\t\n title here \n\t"
        )
        assert request.urlTitle == "title here"

    def test_all_whitespace_title_raises_validation_error(self):
        with pytest.raises(ValidationError):
            CreateURLRequest(urlString="https://example.com", urlTitle="   ")


class TestCreateURLRequestTagStrings:
    """Tests that CreateURLRequest accepts an optional, validated tagStrings list."""

    def test_tag_strings_absent_defaults_to_empty_list(self):
        request = CreateURLRequest(urlString="https://example.com", urlTitle="title")
        assert request.tagStrings == []

    def test_tag_strings_empty_list_allowed(self):
        request = CreateURLRequest(
            urlString="https://example.com", urlTitle="title", tagStrings=[]
        )
        assert request.tagStrings == []

    def test_single_tag_string(self):
        request = CreateURLRequest(
            urlString="https://example.com",
            urlTitle="title",
            tagStrings=["python"],
        )
        assert request.tagStrings == ["python"]

    def test_several_tag_strings(self):
        request = CreateURLRequest(
            urlString="https://example.com",
            urlTitle="title",
            tagStrings=["python", "web", "flask"],
        )
        assert request.tagStrings == ["python", "web", "flask"]

    def test_case_insensitive_dedup_keeps_first_casing(self):
        request = CreateURLRequest(
            urlString="https://example.com",
            urlTitle="title",
            tagStrings=["Python", "python", "web"],
        )
        assert request.tagStrings == ["Python", "web"]

    def test_whitespace_only_element_rejected(self):
        with pytest.raises(ValidationError):
            CreateURLRequest(
                urlString="https://example.com",
                urlTitle="title",
                tagStrings=["   "],
            )

    def test_per_string_over_max_length_rejected(self):
        too_long = "a" * (TAG_CONSTANTS.MAX_TAG_LENGTH + 1)
        with pytest.raises(ValidationError):
            CreateURLRequest(
                urlString="https://example.com",
                urlTitle="title",
                tagStrings=[too_long],
            )

    def test_list_over_max_url_tags_rejected(self):
        too_many = [f"tag{index}" for index in range(TAG_CONSTANTS.MAX_URL_TAGS + 1)]
        with pytest.raises(ValidationError):
            CreateURLRequest(
                urlString="https://example.com",
                urlTitle="title",
                tagStrings=too_many,
            )


class TestCopyUrlsRequest:
    """Tests for CopyUrlsRequest validation (source UTub + selected UTub-URL ids +
    destination UTub ids). All three fields are required on the consolidated
    multi-destination request."""

    def test_valid_request(self):
        request = CopyUrlsRequest(sourceUtubId=1, utubUrlIds=[1, 2, 3], destUtubIds=[2])
        assert request.sourceUtubId == 1
        assert request.utubUrlIds == [1, 2, 3]
        assert request.destUtubIds == [2]

    def test_valid_request_round_trips(self):
        request = CopyUrlsRequest(
            sourceUtubId=1, utubUrlIds=[1, 2, 3], destUtubIds=[2, 3]
        )
        assert request.sourceUtubId == 1
        assert request.utubUrlIds == [1, 2, 3]
        assert request.destUtubIds == [2, 3]

    def test_dedup_collapses_duplicate_ids_preserving_order(self):
        request = CopyUrlsRequest(
            sourceUtubId=1, utubUrlIds=[3, 1, 3, 2, 1], destUtubIds=[2]
        )
        assert request.utubUrlIds == [3, 1, 2]

    def test_non_positive_url_id_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            CopyUrlsRequest(sourceUtubId=1, utubUrlIds=[1, 0, 2], destUtubIds=[2])
        assert URL_FAILURE.INVALID_URL_ID in str(exc_info.value)

    def test_negative_url_id_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            CopyUrlsRequest(sourceUtubId=1, utubUrlIds=[-5], destUtubIds=[2])
        assert URL_FAILURE.INVALID_URL_ID in str(exc_info.value)

    def test_empty_url_id_list_rejected(self):
        with pytest.raises(ValidationError):
            CopyUrlsRequest(sourceUtubId=1, utubUrlIds=[], destUtubIds=[2])

    def test_over_max_bulk_copy_urls_rejected(self):
        too_many = list(range(1, URL_CONSTANTS.MAX_BULK_COPY_URLS + 2))
        with pytest.raises(ValidationError):
            CopyUrlsRequest(sourceUtubId=1, utubUrlIds=too_many, destUtubIds=[2])

    def test_at_max_bulk_copy_urls_allowed(self):
        at_limit = list(range(1, URL_CONSTANTS.MAX_BULK_COPY_URLS + 1))
        request = CopyUrlsRequest(sourceUtubId=1, utubUrlIds=at_limit, destUtubIds=[2])
        assert len(request.utubUrlIds) == URL_CONSTANTS.MAX_BULK_COPY_URLS

    def test_non_positive_source_utub_id_rejected(self):
        with pytest.raises(ValidationError):
            CopyUrlsRequest(sourceUtubId=0, utubUrlIds=[1], destUtubIds=[2])

    def test_negative_source_utub_id_rejected(self):
        with pytest.raises(ValidationError):
            CopyUrlsRequest(sourceUtubId=-1, utubUrlIds=[1], destUtubIds=[2])

    def test_dest_ids_dedup_collapses_duplicates_preserving_order(self):
        request = CopyUrlsRequest(
            sourceUtubId=1, utubUrlIds=[1], destUtubIds=[3, 2, 3, 4, 2]
        )
        assert request.destUtubIds == [3, 2, 4]

    def test_non_positive_dest_id_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            CopyUrlsRequest(sourceUtubId=1, utubUrlIds=[1], destUtubIds=[2, 0, 3])
        assert URL_FAILURE.INVALID_UTUB_ID in str(exc_info.value)

    def test_negative_dest_id_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            CopyUrlsRequest(sourceUtubId=1, utubUrlIds=[1], destUtubIds=[-5])
        assert URL_FAILURE.INVALID_UTUB_ID in str(exc_info.value)

    def test_empty_dest_id_list_rejected(self):
        with pytest.raises(ValidationError):
            CopyUrlsRequest(sourceUtubId=1, utubUrlIds=[1], destUtubIds=[])

    def test_over_max_bulk_copy_destinations_rejected(self):
        too_many = list(range(1, URL_CONSTANTS.MAX_BULK_COPY_DESTINATIONS + 2))
        with pytest.raises(ValidationError):
            CopyUrlsRequest(sourceUtubId=1, utubUrlIds=[1], destUtubIds=too_many)

    def test_at_max_bulk_copy_destinations_allowed(self):
        at_limit = list(range(1, URL_CONSTANTS.MAX_BULK_COPY_DESTINATIONS + 1))
        request = CopyUrlsRequest(sourceUtubId=1, utubUrlIds=[1], destUtubIds=at_limit)
        assert len(request.destUtubIds) == URL_CONSTANTS.MAX_BULK_COPY_DESTINATIONS

    def test_dest_ids_missing_rejected(self):
        with pytest.raises(ValidationError):
            CopyUrlsRequest(sourceUtubId=1, utubUrlIds=[1])


class TestUpdateURLTitleRequestWhitespaceStripping:
    """Tests that UpdateURLTitleRequest strips leading/trailing whitespace from urlTitle."""

    def test_strips_leading_and_trailing_whitespace(self):
        request = UpdateURLTitleRequest(urlTitle="  hello  ")
        assert request.urlTitle == "hello"

    def test_strips_tabs_and_newlines(self):
        request = UpdateURLTitleRequest(urlTitle="\t\n title here \n\t")
        assert request.urlTitle == "title here"

    def test_all_whitespace_title_raises_validation_error(self):
        with pytest.raises(ValidationError):
            UpdateURLTitleRequest(urlTitle="   ")
