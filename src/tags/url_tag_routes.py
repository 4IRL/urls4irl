from flask import Blueprint

from src.api_common.auth_decorators import (
    utub_membership_with_valid_url_in_utub_required,
    utub_membership_with_valid_url_tag,
)
from src.api_common.responses import FlaskResponse
from src.models.utub_tags import Utub_Tags
from src.models.utubs import Utubs
from src.models.utub_urls import Utub_Urls
from src.models.utub_url_tags import Utub_Url_Tags
from src.tags.forms import NewTagForm
from src.tags.services.create_url_tag import (
    add_tag_to_url_if_valid,
    handle_invalid_form_input_for_create_url_tag,
)
from src.tags.services.delete_url_tag import delete_url_tag

utub_url_tags = Blueprint("utub_url_tags", __name__)


@utub_url_tags.route(
    "/utubs/<int:utub_id>/urls/<int:utub_url_id>/tags", methods=["POST"]
)
@utub_membership_with_valid_url_in_utub_required
def create_utub_url_tag(
    utub_id: int, utub_url_id: int, current_utub: Utubs, current_utub_url: Utub_Urls
) -> FlaskResponse:
    """
    User wants to add a tag to a URL. 5 tags per URL.

    Args:
        utub_id (int): The utub that this user is being added to
        url_id (int): The URL this user wants to add a tag to
    """
    url_tag_form: NewTagForm = NewTagForm()

    if not url_tag_form.validate_on_submit():
        return handle_invalid_form_input_for_create_url_tag(
            url_tag_form, current_utub_url
        )

    return add_tag_to_url_if_valid(
        url_tag_form=url_tag_form, utub=current_utub, utub_url=current_utub_url
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
        url_id (int): The ID of the URL containing tag to be deleted
        utub_tag_id (int): The ID of the tag to be deleted
    """
    return delete_url_tag(
        utub=current_utub,
        utub_url=current_utub_url,
        utub_tag=current_utub_tag,
        utub_url_tag=current_url_tag,
    )
