import pytest
from pydantic import ValidationError

from backend.schemas.requests.urls import DeleteUrlsRequest
from backend.schemas.urls import (
    DeleteUrlsResponseSchema,
    UrlDeleteSkippedSchema,
    UtubUrlDeleteSchema,
)
from backend.urls.constants import BulkDeleteSkipReason
from backend.utils.constants import URL_CONSTANTS
from backend.utils.strings.model_strs import TAG_COUNTS_MODIFIED
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.url_strs import URL_FAILURE

pytestmark = pytest.mark.urls


class TestDeleteUrlsRequest:
    """Tests for DeleteUrlsRequest validation (selected UTub-URL ids in the active
    UTub). The single field is required and bounded by MAX_BULK_DELETE_URLS."""

    def test_valid_request(self):
        request = DeleteUrlsRequest(utubUrlIds=[1, 2, 3])
        assert request.utubUrlIds == [1, 2, 3]

    def test_dedup_collapses_duplicate_ids_preserving_order(self):
        request = DeleteUrlsRequest(utubUrlIds=[3, 1, 3, 2, 1])
        assert request.utubUrlIds == [3, 1, 2]

    def test_non_positive_url_id_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            DeleteUrlsRequest(utubUrlIds=[1, 0, 2])
        assert URL_FAILURE.INVALID_URL_ID in str(exc_info.value)

    def test_negative_url_id_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            DeleteUrlsRequest(utubUrlIds=[-5])
        assert URL_FAILURE.INVALID_URL_ID in str(exc_info.value)

    def test_empty_url_id_list_rejected(self):
        with pytest.raises(ValidationError):
            DeleteUrlsRequest(utubUrlIds=[])

    def test_missing_url_id_list_rejected(self):
        with pytest.raises(ValidationError):
            DeleteUrlsRequest()

    def test_over_max_bulk_delete_urls_rejected(self):
        too_many = list(range(1, URL_CONSTANTS.MAX_BULK_DELETE_URLS + 2))
        with pytest.raises(ValidationError):
            DeleteUrlsRequest(utubUrlIds=too_many)

    def test_at_max_bulk_delete_urls_allowed(self):
        at_limit = list(range(1, URL_CONSTANTS.MAX_BULK_DELETE_URLS + 1))
        request = DeleteUrlsRequest(utubUrlIds=at_limit)
        assert len(request.utubUrlIds) == URL_CONSTANTS.MAX_BULK_DELETE_URLS


class TestDeleteUrlsResponseSchema:
    """Tests for the bulk-delete response schema shape / camelCase alias output."""

    def test_skipped_item_dump_uses_aliases(self):
        skipped = UrlDeleteSkippedSchema(
            utub_url_id=7, reason=BulkDeleteSkipReason.FORBIDDEN
        )
        dumped = skipped.model_dump(by_alias=True)
        assert dumped[M.UTUB_URL_ID] == 7
        assert dumped[M.SKIP_REASON] == BulkDeleteSkipReason.FORBIDDEN

    def test_response_dump_uses_aliases(self):
        deleted_item = UtubUrlDeleteSchema(
            utub_url_id=1, url_string="https://example.com", url_title="Example"
        )
        skipped_item = UrlDeleteSkippedSchema(
            utub_url_id=2, reason=BulkDeleteSkipReason.FORBIDDEN
        )
        response = DeleteUrlsResponseSchema(
            deleted=[deleted_item],
            skipped=[skipped_item],
            tag_counts_modified={5: 0, 6: 2},
            total_deleted=1,
            total_skipped=1,
        )
        dumped = response.model_dump(by_alias=True)
        assert dumped[M.DELETED][0][M.UTUB_URL_ID] == 1
        assert dumped[M.SKIPPED][0][M.SKIP_REASON] == BulkDeleteSkipReason.FORBIDDEN
        assert dumped[TAG_COUNTS_MODIFIED] == {5: 0, 6: 2}
        assert dumped[M.TOTAL_DELETED] == 1
        assert dumped[M.TOTAL_SKIPPED] == 1
