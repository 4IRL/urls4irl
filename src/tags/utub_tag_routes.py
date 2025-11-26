from flask import Blueprint

from src.api_common.auth_decorators import (
    utub_membership_required,
    utub_membership_with_valid_utub_tag,
)
from src.api_common.responses import FlaskResponse
from src.models.utub_tags import Utub_Tags
from src.models.utubs import Utubs
from src.tags.forms import NewTagForm
from src.tags.services.create_utub_tag import (
    create_tag_in_utub,
    handle_invalid_form_input_for_create_utub_tag,
)
from src.tags.services.delete_utub_tag import delete_utub_tag_from_utub_and_utub_urls

utub_tags = Blueprint("utub_tags", __name__)


@utub_tags.route("/utubs/<int:utub_id>/tags", methods=["POST"])
@utub_membership_required
def create_utub_tag(utub_id: int, current_utub: Utubs) -> FlaskResponse:
    """
    User wants to add a tag to a UTub.

    Args:
        utub_id (int): The tag is being added to UTub with this ID
        current_utub (Utubs): The UTub model being added to
    """
    utub_tag_form: NewTagForm = NewTagForm()

    if not utub_tag_form.validate_on_submit():
        return handle_invalid_form_input_for_create_utub_tag(
            utub_tag_form, current_utub
        )

    return create_tag_in_utub(utub_tag_form=utub_tag_form, current_utub=current_utub)


@utub_tags.route(
    "/utubs/<int:utub_id>/tags/<int:utub_tag_id>",
    methods=["DELETE"],
)
@utub_membership_with_valid_utub_tag
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
