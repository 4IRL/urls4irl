from flask import Blueprint

from backend.api_common.auth_decorators import (
    utub_membership_required,
    utub_membership_with_valid_utub_tag,
)
from backend.api_common.parse_request import api_route
from backend.api_common.responses import FlaskResponse
from backend.models.utub_tags import Utub_Tags
from backend.models.utubs import Utubs
from backend.schemas.requests.tags import AddTagRequest
from backend.schemas.tags import (
    UtubTagAddedToUtubResponseSchema,
    UtubTagDeletedFromUtubResponseSchema,
)
from backend.tags.constants import UTubTagErrorCodes
from backend.tags.services.create_utub_tag import create_tag_in_utub
from backend.tags.services.delete_utub_tag import (
    delete_utub_tag_from_utub_and_utub_urls,
)
from backend.utils.strings.tag_strs import TAGS_FAILURE

utub_tags = Blueprint("utub_tags", __name__)


@utub_tags.route("/utubs/<int:utub_id>/tags", methods=["POST"])
@utub_membership_required
@api_route(
    request_schema=AddTagRequest,
    response_schema=UtubTagAddedToUtubResponseSchema,
    error_message=TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
    error_code=UTubTagErrorCodes.INVALID_FORM_INPUT,
)
def create_utub_tag(
    utub_id: int, current_utub: Utubs, validated_request: AddTagRequest
) -> FlaskResponse:
    """
    User wants to add a tag to a UTub.

    Args:
        utub_id (int): The tag is being added to UTub with this ID
        current_utub (Utubs): The UTub model being added to
        validated_request (AddTagRequest): Validated request schema
    """
    return create_tag_in_utub(
        tag_string=validated_request.tagString, current_utub=current_utub
    )


@utub_tags.route(
    "/utubs/<int:utub_id>/tags/<int:utub_tag_id>",
    methods=["DELETE"],
)
@utub_membership_with_valid_utub_tag
@api_route(response_schema=UtubTagDeletedFromUtubResponseSchema)
def delete_utub_tag(
    utub_id: int, utub_tag_id: int, current_utub: Utubs, current_utub_tag: Utub_Tags
) -> FlaskResponse:
    """
    User wants to delete a tag from a UTub. This will remove all instances of this tag
    associated with URLs (Utub_Url_Tags) in this UTub.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be deleted
        utub_tag_id (int): The ID of the tag to be deleted
    """
    return delete_utub_tag_from_utub_and_utub_urls(
        utub=current_utub, utub_tag=current_utub_tag
    )
