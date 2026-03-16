from flask import Blueprint

from backend.api_common.auth_decorators import (
    utub_membership_with_valid_url_in_utub_required,
    utub_membership_with_valid_url_tag,
)
from backend.api_common.parse_request import parse_json_body
from backend.api_common.responses import FlaskResponse
from backend.models.utub_tags import Utub_Tags
from backend.models.utubs import Utubs
from backend.models.utub_urls import Utub_Urls
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.schemas.requests.tags import AddTagRequest
from backend.tags.constants import URLTagErrorCodes
from backend.tags.services.create_url_tag import add_tag_to_url_if_valid
from backend.tags.services.delete_url_tag import delete_url_tag
from backend.utils.strings.tag_strs import TAGS_FAILURE

utub_url_tags = Blueprint("utub_url_tags", __name__)


@utub_url_tags.route(
    "/utubs/<int:utub_id>/urls/<int:utub_url_id>/tags", methods=["POST"]
)
@utub_membership_with_valid_url_in_utub_required
@parse_json_body(
    AddTagRequest,
    message=TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
    error_code=URLTagErrorCodes.INVALID_FORM_INPUT,
)
def create_utub_url_tag(
    utub_id: int,
    utub_url_id: int,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    validated_request: AddTagRequest,
) -> FlaskResponse:
    """
    User wants to add a tag to a URL. 5 tags per URL.

    Args:
        utub_id (int): The utub that this user is being added to
        utub_url_id (int): The URL this user wants to add a tag to
        current_utub (Utubs): The UTub model
        current_utub_url (Utub_Urls): The URL model
        validated_request (AddTagRequest): Validated request schema
    """
    return add_tag_to_url_if_valid(
        tag_string=validated_request.tagString,
        utub=current_utub,
        utub_url=current_utub_url,
    )


@utub_url_tags.route(
    "/utubs/<int:utub_id>/urls/<int:utub_url_id>/tags/<int:utub_tag_id>",
    methods=["DELETE"],
)
@utub_membership_with_valid_url_tag
def delete_utub_url_tag(
    utub_id: int,
    utub_url_id: int,
    utub_tag_id: int,
    current_utub: Utubs,
    current_utub_url: Utub_Urls,
    current_utub_tag: Utub_Tags,
    current_url_tag: Utub_Url_Tags,
) -> FlaskResponse:
    """
    User wants to delete a tag from a URL contained in a UTub.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be deleted
        utub_url_id (int): The ID of the URL containing tag to be deleted
        utub_tag_id (int): The ID of the tag to be deleted
    """
    return delete_url_tag(
        utub=current_utub,
        utub_url=current_utub_url,
        utub_tag=current_utub_tag,
        utub_url_tag=current_url_tag,
    )
