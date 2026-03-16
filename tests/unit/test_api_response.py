import pytest
from pydantic import Field

from backend.api_common.responses import APIResponse
from backend.schemas.base import BaseSchema

pytestmark = pytest.mark.unit


class SampleSchema(BaseSchema):
    item_id: int = Field(alias="itemId")
    label: str = Field(alias="label")


def test_api_response_with_pydantic_model_uses_aliases(app):
    """
    GIVEN an APIResponse with a Pydantic BaseSchema instance as data
    WHEN to_response() is called
    THEN the JSON payload contains aliased field names
    """
    schema = SampleSchema(item_id=42, label="hello")
    with app.app_context():
        response, status_code = APIResponse(data=schema, status_code=200).to_response()
        payload = response.get_json()

    assert status_code == 200
    assert payload["itemId"] == 42
    assert payload["label"] == "hello"
    assert "item_id" not in payload


def test_api_response_with_dict_still_works(app):
    """
    GIVEN an APIResponse with a plain dict as data (existing usage)
    WHEN to_response() is called
    THEN the JSON payload is unchanged
    """
    with app.app_context():
        response, status_code = APIResponse(
            data={"someKey": "someValue"}, status_code=200
        ).to_response()
        payload = response.get_json()

    assert status_code == 200
    assert payload["someKey"] == "someValue"


def test_api_response_with_pydantic_model_failure_response(app):
    """
    GIVEN an APIResponse with a Pydantic schema and a 4xx status code
    WHEN to_response() is called
    THEN the payload still contains aliased field names and correct status
    """
    schema = SampleSchema(item_id=1, label="err")
    with app.app_context():
        response, status_code = APIResponse(
            data=schema, status_code=400, message="bad request"
        ).to_response()
        payload = response.get_json()

    assert status_code == 400
    assert payload["itemId"] == 1
    assert payload["label"] == "err"
