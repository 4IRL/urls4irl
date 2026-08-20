from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.schemas.requests.urls import (
    CopyUrlsRequest,
    CreateURLRequest,
    UpdateURLTitleRequest,
)
from backend.utils.constants import TAG_CONSTANTS, URL_CONSTANTS
from backend.utils.strings.model_strs import MODELS as M
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
    associated_tag_ids = [3, 5]
    associated_tags = [
        {M.UTUB_TAG_ID: 3, M.TAG_STRING: "python"},
        {M.UTUB_TAG_ID: 5, M.TAG_STRING: "web"},
    ]


def test_utub_url_schema_dump():
    from backend.schemas.urls import UtubUrlSchema

    schema = UtubUrlSchema.from_orm_url(
        _MockUtubUrl(), current_user_id=2, utub_creator=2
    )
    dumped = schema.model_dump(by_alias=True)
    assert dumped[M.UTUB_URL_ID] == 10
    assert dumped[M.URL_STRING] == "https://example.com"
    assert dumped[M.URL_TAG_IDS] == [3, 5]
    assert dumped[M.URL_TITLE] == "Example Site"
    assert dumped[M.CAN_DELETE] is True
    # added_at is serialized to an ISO-8601 string via field_serializer.
    assert dumped["addedAt"] == "2024-03-09T12:00:00+00:00"


def test_utub_url_schema_can_delete_false():
    from backend.schemas.urls import UtubUrlSchema

    schema = UtubUrlSchema.from_orm_url(
        _MockUtubUrl(), current_user_id=99, utub_creator=100
    )
    assert schema.can_delete is False


def test_utub_url_schema_missing_required_fields():
    from backend.schemas.urls import UtubUrlSchema

    with pytest.raises(ValidationError):
        UtubUrlSchema()


def test_utub_url_detail_schema_dump():
    from backend.schemas.urls import UtubUrlDetailSchema

    schema = UtubUrlDetailSchema.from_orm_url(_MockUtubUrl())
    dumped = schema.model_dump(by_alias=True)
    assert dumped[M.UTUB_URL_ID] == 10
    assert dumped[M.URL_TITLE] == "Example Site"
    assert dumped[M.URL_STRING] == "https://example.com"
    assert len(dumped[M.URL_TAGS]) == 2
    assert dumped[M.URL_TAGS][0] == {M.UTUB_TAG_ID: 3, M.TAG_STRING: "python"}
    assert dumped[M.URL_TAGS][1] == {M.UTUB_TAG_ID: 5, M.TAG_STRING: "web"}


def test_utub_url_detail_schema_missing_required_fields():
    from backend.schemas.urls import UtubUrlDetailSchema

    with pytest.raises(ValidationError):
        UtubUrlDetailSchema()


def test_utub_url_detail_schema_validate_from_dict():
    from backend.schemas.urls import UtubUrlDetailSchema

    data = {
        M.UTUB_URL_ID: 10,
        M.URL_TITLE: "Example Site",
        M.URL_STRING: "https://example.com",
        M.URL_TAGS: [
            {M.UTUB_TAG_ID: 3, M.TAG_STRING: "python"},
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
        M.UTUB_URL_ID: 10,
        M.URL_STRING: "https://example.com",
        M.URL_TITLE: "Example Site",
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
        assert URL_FAILURE.INVALID_URL_ID in str(exc_info.value)

    def test_negative_dest_id_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            CopyUrlsRequest(sourceUtubId=1, utubUrlIds=[1], destUtubIds=[-5])
        assert URL_FAILURE.INVALID_URL_ID in str(exc_info.value)

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
