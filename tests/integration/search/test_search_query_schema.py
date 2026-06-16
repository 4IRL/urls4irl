from pydantic import ValidationError
import pytest

from backend.schemas.requests.search import SearchQuerySchema
from backend.schemas.search import SearchHitSchema
from backend.search.constants import MatchedField
from backend.utils.constants import SEARCH_CONSTANTS
from backend.utils.strings.model_strs import MODELS as M

pytestmark = pytest.mark.urls


def test_search_query_schema_strips_surrounding_whitespace():
    validated = SearchQuerySchema.model_validate({"q": "  python  "})
    assert validated.q == "python"


def test_search_query_schema_rejects_empty_string():
    with pytest.raises(ValidationError):
        SearchQuerySchema.model_validate({"q": ""})


def test_search_query_schema_rejects_whitespace_only_string():
    with pytest.raises(ValidationError):
        SearchQuerySchema.model_validate({"q": "   "})


def test_search_query_schema_accepts_single_char():
    single_char_query = "a" * SEARCH_CONSTANTS.MIN_QUERY_LENGTH
    validated = SearchQuerySchema.model_validate({"q": single_char_query})
    assert validated.q == single_char_query


def test_search_query_schema_accepts_max_length_string():
    max_length_query = "a" * SEARCH_CONSTANTS.MAX_QUERY_LENGTH
    validated = SearchQuerySchema.model_validate({"q": max_length_query})
    assert validated.q == max_length_query


def test_search_query_schema_rejects_query_exceeding_max_length():
    too_long_query = "a" * (SEARCH_CONSTANTS.MAX_QUERY_LENGTH + 1)
    with pytest.raises(ValidationError):
        SearchQuerySchema.model_validate({"q": too_long_query})


def test_search_query_schema_rejects_unknown_extra_key():
    with pytest.raises(ValidationError):
        SearchQuerySchema.model_validate({"q": "x", "z": "1"})


def test_search_hit_schema_serializes_matched_fields_to_readable_values():
    hit = SearchHitSchema(
        utub_url_id=7,
        url_string="https://python.org",
        url_title="Python Home",
        url_tags=[],
        matched_fields=[MatchedField.URL_TITLE, MatchedField.URL_STRING],
    )
    dumped = hit.model_dump(by_alias=True)
    assert dumped[M.MATCHED_FIELDS] == ["title", "url"]


def test_search_hit_schema_serializes_empty_matched_fields():
    hit = SearchHitSchema(
        utub_url_id=7,
        url_string="https://python.org",
        url_title="Python Home",
        url_tags=[],
        matched_fields=[],
    )
    dumped = hit.model_dump(by_alias=True)
    assert dumped[M.MATCHED_FIELDS] == []
