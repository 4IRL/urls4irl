import pytest
from pydantic import ValidationError

from backend.utils.strings.model_strs import MODELS as M

pytestmark = pytest.mark.unit


class _MockUrl:
    id = 1
    url_string = "https://example.com"


class _MockUtubUrl:
    id = 10
    url_title = "Example Site"
    user_id = 2
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
        from backend.schemas.requests.urls import CreateURLRequest

        request = CreateURLRequest(
            urlString="https://example.com", urlTitle="  hello  "
        )
        assert request.urlTitle == "hello"

    def test_strips_tabs_and_newlines(self):
        from backend.schemas.requests.urls import CreateURLRequest

        request = CreateURLRequest(
            urlString="https://example.com", urlTitle="\t\n title here \n\t"
        )
        assert request.urlTitle == "title here"

    def test_all_whitespace_title_raises_validation_error(self):
        from backend.schemas.requests.urls import CreateURLRequest

        with pytest.raises(ValidationError):
            CreateURLRequest(urlString="https://example.com", urlTitle="   ")


class TestUpdateURLTitleRequestWhitespaceStripping:
    """Tests that UpdateURLTitleRequest strips leading/trailing whitespace from urlTitle."""

    def test_strips_leading_and_trailing_whitespace(self):
        from backend.schemas.requests.urls import UpdateURLTitleRequest

        request = UpdateURLTitleRequest(urlTitle="  hello  ")
        assert request.urlTitle == "hello"

    def test_strips_tabs_and_newlines(self):
        from backend.schemas.requests.urls import UpdateURLTitleRequest

        request = UpdateURLTitleRequest(urlTitle="\t\n title here \n\t")
        assert request.urlTitle == "title here"

    def test_all_whitespace_title_raises_validation_error(self):
        from backend.schemas.requests.urls import UpdateURLTitleRequest

        with pytest.raises(ValidationError):
            UpdateURLTitleRequest(urlTitle="   ")
