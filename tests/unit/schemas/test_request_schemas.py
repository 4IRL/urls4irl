import pytest
from pydantic import ValidationError

from backend.utils.constants import UTUB_CONSTANTS, TAG_CONSTANTS
from backend.utils.strings.tag_strs import TAGS_FAILURE

pytestmark = pytest.mark.unit


class TestCreateUTubRequest:
    def test_valid_with_description(self):
        from backend.schemas.requests.utubs import CreateUTubRequest

        req = CreateUTubRequest.model_validate(
            {"utubName": "My UTub", "utubDescription": None}
        )
        assert req.utubName == "My UTub"
        assert req.utubDescription is None

    def test_valid_without_description(self):
        from backend.schemas.requests.utubs import CreateUTubRequest

        req = CreateUTubRequest.model_validate({"utubName": "My UTub"})
        assert req.utubDescription is None

    def test_missing_name_raises(self):
        from backend.schemas.requests.utubs import CreateUTubRequest

        with pytest.raises(ValidationError) as exc_info:
            CreateUTubRequest.model_validate({"utubDescription": "desc"})
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "utubName" for e in errors)

    def test_whitespace_only_name_raises(self):
        from backend.schemas.requests.utubs import CreateUTubRequest

        with pytest.raises(ValidationError) as exc_info:
            CreateUTubRequest.model_validate({"utubName": "   "})
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "utubName" for e in errors)

    def test_name_too_long_raises(self):
        from backend.schemas.requests.utubs import CreateUTubRequest

        with pytest.raises(ValidationError) as exc_info:
            CreateUTubRequest.model_validate(
                {"utubName": "a" * (UTUB_CONSTANTS.MAX_NAME_LENGTH + 1)}
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "utubName" for e in errors)


class TestUpdateUTubDescriptionRequest:
    def test_whitespace_only_description_coerced_to_none(self):
        from backend.schemas.requests.utubs import UpdateUTubDescriptionRequest

        req = UpdateUTubDescriptionRequest.model_validate({"utubDescription": "   "})
        assert req.utubDescription is None

    def test_valid_description(self):
        from backend.schemas.requests.utubs import UpdateUTubDescriptionRequest

        req = UpdateUTubDescriptionRequest.model_validate(
            {"utubDescription": "A description"}
        )
        assert req.utubDescription == "A description"

    def test_none_description(self):
        from backend.schemas.requests.utubs import UpdateUTubDescriptionRequest

        req = UpdateUTubDescriptionRequest.model_validate({"utubDescription": None})
        assert req.utubDescription is None


class TestAddTagRequest:
    def test_whitespace_only_tag_raises(self):
        from backend.schemas.requests.tags import AddTagRequest

        with pytest.raises(ValidationError) as exc_info:
            AddTagRequest.model_validate({"tagString": "   "})
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "tagString" for e in errors)

    def test_html_tag_is_rejected(self):
        from backend.schemas.requests.tags import AddTagRequest

        # HTML input is rejected since sanitized result differs from original
        with pytest.raises(ValidationError) as exc_info:
            AddTagRequest.model_validate({"tagString": "<b>python</b>"})
        errors = exc_info.value.errors()
        assert any(error["loc"][0] == "tagString" for error in errors)

    def test_valid_tag(self):
        from backend.schemas.requests.tags import AddTagRequest

        req = AddTagRequest.model_validate({"tagString": "python"})
        assert req.tagString == "python"

    def test_tag_too_long_raises(self):
        from backend.schemas.requests.tags import AddTagRequest

        with pytest.raises(ValidationError):
            AddTagRequest.model_validate(
                {"tagString": "a" * (TAG_CONSTANTS.MAX_TAG_LENGTH + 1)}
            )


class TestAddTagsRequest:
    def test_valid_multi_string_list(self):
        from backend.schemas.requests.tags import AddTagsRequest

        req = AddTagsRequest.model_validate({"tagStrings": ["python", "web"]})
        assert req.tagStrings == ["python", "web"]

    def test_empty_list_raises(self):
        from backend.schemas.requests.tags import AddTagsRequest

        with pytest.raises(ValidationError) as exc_info:
            AddTagsRequest.model_validate({"tagStrings": []})
        errors = exc_info.value.errors()
        assert any(error["loc"][0] == "tagStrings" for error in errors)

    def test_list_exceeding_max_url_tags_raises(self):
        from backend.schemas.requests.tags import AddTagsRequest

        too_many = [f"tag{index}" for index in range(TAG_CONSTANTS.MAX_URL_TAGS + 1)]
        with pytest.raises(ValidationError) as exc_info:
            AddTagsRequest.model_validate({"tagStrings": too_many})
        errors = exc_info.value.errors()
        assert any(error["loc"][0] == "tagStrings" for error in errors)

    def test_whitespace_only_element_raises(self):
        from backend.schemas.requests.tags import AddTagsRequest

        with pytest.raises(ValidationError) as exc_info:
            AddTagsRequest.model_validate({"tagStrings": ["python", "   "]})
        errors = exc_info.value.errors()
        assert any(TAGS_FAILURE.TAG_EMPTY in str(error["msg"]) for error in errors)

    def test_html_element_is_rejected(self):
        from backend.schemas.requests.tags import AddTagsRequest

        with pytest.raises(ValidationError) as exc_info:
            AddTagsRequest.model_validate({"tagStrings": ["<b>python</b>"]})
        errors = exc_info.value.errors()
        assert any(error["loc"][0] == "tagStrings" for error in errors)

    def test_over_length_element_raises(self):
        from backend.schemas.requests.tags import AddTagsRequest

        with pytest.raises(ValidationError):
            AddTagsRequest.model_validate(
                {"tagStrings": ["a" * (TAG_CONSTANTS.MAX_TAG_LENGTH + 1)]}
            )

    def test_duplicate_elements_deduplicated_case_insensitive(self):
        from backend.schemas.requests.tags import AddTagsRequest

        req = AddTagsRequest.model_validate(
            {"tagStrings": ["python", "Python", " python ", "web"]}
        )
        assert req.tagStrings == ["python", "web"]


class TestAddMemberRequest:
    def test_missing_username_raises(self):
        from backend.schemas.requests.members import AddMemberRequest

        with pytest.raises(ValidationError) as exc_info:
            AddMemberRequest.model_validate({})
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "username" for e in errors)

    def test_valid_username(self):
        from backend.schemas.requests.members import AddMemberRequest

        req = AddMemberRequest.model_validate({"username": "alice"})
        assert req.username == "alice"
