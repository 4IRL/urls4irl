from flask import Blueprint, jsonify, Response

from src.app_logger import (
    safe_add_many_logs,
)
from src.models.utubs import Utubs
from src.models.utub_urls import Utub_Urls
from src.urls.forms import (
    NewURLForm,
    UpdateURLForm,
    UpdateURLTitleForm,
)
from src.urls.services.create_urls import (
    create_url_in_utub,
    handle_invalid_url_form_input,
)
from src.urls.services.delete_urls import (
    check_if_is_url_adder_or_utub_creator_on_url_delete,
    delete_url_in_utub,
)
from src.urls.services.update_url_titles import (
    handle_invalid_update_url_title_form_input,
    update_url_title_if_new,
)
from src.urls.services.update_urls import (
    check_if_is_url_adder_or_utub_creator_on_url_update,
    handle_invalid_update_url_form_input,
    update_url_in_utub,
)
from src.utils.auth_decorators import (
    utub_membership_required,
    utub_membership_with_valid_url_in_utub_required,
    xml_http_request_only,
)
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.url_strs import URL_SUCCESS

urls = Blueprint("urls", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@urls.route("/utubs/<int:utub_id>/urls", methods=["POST"])
@utub_membership_required
def create_url(utub_id: int, current_utub: Utubs) -> tuple[Response, int]:
    """
    User wants to add URL to UTub. On success, adds the URL to the UTub.

    Args:
        utub_id (int): The Utubs to add this URL to
    """
    create_url_form: NewURLForm = NewURLForm()

    if not create_url_form.validate_on_submit():
        return handle_invalid_url_form_input(create_url_form)

    return create_url_in_utub(
        create_url_form=create_url_form, current_utub=current_utub
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["GET"])
@xml_http_request_only
@utub_membership_with_valid_url_in_utub_required
def get_url(
    utub_id: int, utub_url_id: int, current_utub: Utubs, current_utub_url: Utub_Urls
) -> tuple[Response, int]:
    """
    Allows a user to read a URL in a UTub. Only users who are a member of the
    UTub can GET this URL.

    Args:
        utub_id (int): The UTub ID containing the relevant URL
        utub_url_id (int): The URL ID to be modified
    """

    safe_add_many_logs(
        [
            "Retrieved URL",
            f"UTub.id={utub_id}",
            f"UTubURL.id={utub_url_id}",
        ]
    )
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: URL_SUCCESS.URL_FOUND_IN_UTUB,
                URL_SUCCESS.URL: current_utub_url.serialized_on_get_or_update,
            }
        ),
        200,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["PATCH"])
@utub_membership_with_valid_url_in_utub_required
def update_url(
    utub_id: int, utub_url_id: int, current_utub: Utubs, current_utub_url: Utub_Urls
) -> tuple[Response, int]:
    """
    Allows a user to update a URL without updating the title.
    Only the user who added the URL, or who created the UTub containing
    the URL, can modify the URL.

    Args:
        utub_id (int): The UTub ID containing the relevant URL
        utub_url_id (int): The URL ID to be modified
        current_utub: (Utubs): The UTub for this URL
        current_utub_url: (Utub_Urls): The UTub_Urls to update
    """
    utub_creator_or_url_adder_response = (
        check_if_is_url_adder_or_utub_creator_on_url_update(
            utub_id=utub_id, utub_url_id=utub_url_id
        )
    )
    if utub_creator_or_url_adder_response is not None:
        return utub_creator_or_url_adder_response

    update_url_form: UpdateURLForm = UpdateURLForm()

    if not update_url_form.validate_on_submit():
        return handle_invalid_update_url_form_input(update_url_form)

    return update_url_in_utub(
        update_url_form=update_url_form,
        current_utub=current_utub,
        current_utub_url=current_utub_url,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>/title", methods=["PATCH"])
@utub_membership_with_valid_url_in_utub_required
def update_url_title(
    utub_id: int, utub_url_id: int, current_utub: Utubs, current_utub_url: Utub_Urls
) -> tuple[Response, int]:
    """
    Allows a user to update a URL title without updating the url.
    Only the user who added the URL, or who created the UTub containing
    the URL, can modify the title.

    Args:
        utub_id (int): The UTub ID containing the relevant URL
        utub_url_id (int): The URL ID to be modified
        current_utub: (Utubs): The UTub for this URL
        current_utub_url: (Utub_Urls): The UTub_Urls to update
    """
    utub_creator_or_url_adder_response = (
        check_if_is_url_adder_or_utub_creator_on_url_update(
            utub_id=utub_id, utub_url_id=utub_url_id
        )
    )
    if utub_creator_or_url_adder_response is not None:
        return utub_creator_or_url_adder_response

    update_url_title_form: UpdateURLTitleForm = UpdateURLTitleForm()

    if not update_url_title_form.validate_on_submit():
        return handle_invalid_update_url_title_form_input(update_url_title_form)

    return update_url_title_if_new(
        new_url_title=update_url_title_form.url_title.get(),
        current_utub=current_utub,
        current_utub_url=current_utub_url,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["DELETE"])
@utub_membership_with_valid_url_in_utub_required
def delete_url(
    utub_id: int, utub_url_id: int, current_utub: Utubs, current_utub_url: Utub_Urls
) -> tuple[Response, int]:
    """
    User wants to remove a URL from a UTub. Only available to owner of that utub,
    or whoever added the URL into that Utubs.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be removed
        utub_url_id (int): The ID of the UtubUrl to be removed
    """
    utub_creator_or_url_adder_response = (
        check_if_is_url_adder_or_utub_creator_on_url_delete(
            utub_id=utub_id, utub_url_id=utub_url_id
        )
    )

    if utub_creator_or_url_adder_response is not None:
        return utub_creator_or_url_adder_response

    return delete_url_in_utub(
        current_utub=current_utub, current_utub_url=current_utub_url
    )
