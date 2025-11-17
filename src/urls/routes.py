from flask import abort, Blueprint, jsonify
from flask_login import current_user

from src import db
from src.app_logger import (
    critical_log,
    safe_add_log,
    safe_add_many_logs,
    turn_form_into_str_for_log,
    warning_log,
)
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls
from src.urls.constants import URLState
from src.urls.forms import (
    NewURLForm,
    UpdateURLForm,
    UpdateURLTitleForm,
)
from src.urls.services import (
    associate_updated_url_with_utub,
    associate_url_with_utub,
    check_for_empty_url_string_on_update,
    check_for_equivalent_url_on_update,
    check_if_is_url_adder_or_utub_creator_on_url_delete,
    check_if_is_url_adder_or_utub_creator_on_url_update,
    check_url_already_in_utub,
    get_or_create_url,
    handle_invalid_update_url_form_input,
    handle_invalid_url_form_input,
    update_tag_counts_on_url_delete,
    normalize_and_validate_url,
)
from src.urls.utils import build_form_errors
from src.utils.auth_decorators import (
    email_validation_required,
    utub_membership_required,
    utub_membership_with_valid_url_in_utub_required,
    xml_http_request_only,
)
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.url_strs import URL_SUCCESS, URL_FAILURE, URL_NO_CHANGE

urls = Blueprint("urls", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["DELETE"])
@utub_membership_with_valid_url_in_utub_required
def delete_url(
    utub_id: int, utub_url_id: int, current_utub: Utubs, current_utub_url: Utub_Urls
):
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

    # Store serialized data from URL association with UTub and associated tags
    url_string_to_remove = current_utub_url.standalone_url.url_string
    url_id_to_remove = current_utub_url.standalone_url.id

    tag_ids_and_updated_count = update_tag_counts_on_url_delete(
        current_utub_url, current_utub
    )

    db.session.delete(current_utub_url)
    current_utub.set_last_updated()

    db.session.commit()

    safe_add_many_logs(
        [
            "Deleted UTubURL and associated UTubURLTags",
            f"User.id={current_user.id}",
            f"UTub.id={utub_id}",
            f"UTubURL.id={utub_url_id}",
            f"URL.id={url_id_to_remove}",
        ]
    )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
                URL_SUCCESS.UTUB_ID: current_utub.id,
                URL_SUCCESS.URL: {
                    URL_SUCCESS.URL_STRING: url_string_to_remove,
                    URL_SUCCESS.UTUB_URL_ID: utub_url_id,
                    URL_SUCCESS.URL_TITLE: current_utub_url.url_title,
                },
                URL_SUCCESS.TAG_COUNTS_MODIFIED: tag_ids_and_updated_count,
            }
        ),
        200,
    )


@urls.route("/utubs/<int:utub_id>/urls", methods=["POST"])
@utub_membership_required
def create_url(utub_id: int, current_utub: Utubs):
    """
    User wants to add URL to UTub. On success, adds the URL to the UTub.

    Args:
        utub_id (int): The Utubs to add this URL to
    """
    utub_new_url_form: NewURLForm = NewURLForm()

    if not utub_new_url_form.validate_on_submit():
        return handle_invalid_url_form_input(utub_new_url_form)

    url_string = utub_new_url_form.url_string.data
    validated_url_response = normalize_and_validate_url(url_string)

    if not isinstance(validated_url_response, str):
        return validated_url_response

    validated_ada_url: str = validated_url_response

    url, url_state = get_or_create_url(validated_ada_url)

    if url_state == URLState.EXISTING_URL:
        safe_add_log(f"URL already exists in U4I, URL.id={url.id}")
        url_already_in_utub_response = check_url_already_in_utub(
            utub_id, url.id, validated_ada_url
        )

        if url_already_in_utub_response is not None:
            return url_already_in_utub_response

    # Associate URL with given UTub
    return associate_url_with_utub(
        current_utub=current_utub,
        url_id=url.id,
        url_title=utub_new_url_form.url_title.get(),
        url_string=validated_ada_url,
        url_state=url_state,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["GET"])
@xml_http_request_only
@utub_membership_with_valid_url_in_utub_required
def get_url(
    utub_id: int, utub_url_id: int, current_utub: Utubs, current_utub_url: Utub_Urls
):
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
):
    """
    Allows a user to update a URL without updating the title.
    Only the user who added the URL, or who created the UTub containing
    the URL, can modify the URL.

    Args:
        utub_id (int): The UTub ID containing the relevant URL
        utub_url_id (int): The URL ID to be modified
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

    url_to_change_to: str = update_url_form.get_url_string().replace(" ", "")

    # Check for empty URL string to update to
    empty_url_string_response = check_for_empty_url_string_on_update(
        url_to_change_to, utub_url_id
    )
    if empty_url_string_response is not None:
        return empty_url_string_response

    # Check for updating the URL to the same URL
    equivalent_url_response = check_for_equivalent_url_on_update(
        url_to_change_to, current_utub_url
    )
    if equivalent_url_response is not None:
        return equivalent_url_response

    # Check for a valid and ADA compliant URL
    validated_url_response = normalize_and_validate_url(url_to_change_to)
    if not isinstance(validated_url_response, str):
        return validated_url_response

    validated_ada_url: str = validated_url_response

    url, url_state = get_or_create_url(validated_ada_url)

    # If the URL exists and is already in the UTub, return early
    if url_state == URLState.EXISTING_URL:
        safe_add_log(f"URL already exists in U4I, URL.id={url.id}")
        url_already_in_utub_response = check_url_already_in_utub(
            utub_id=utub_id, url_id=url.id, url_string=validated_ada_url
        )
        if url_already_in_utub_response is not None:
            return url_already_in_utub_response

    return associate_updated_url_with_utub(
        url=url, current_utub=current_utub, current_utub_url=current_utub_url
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>/title", methods=["PATCH"])
@email_validation_required
def update_url_title(utub_id: int, utub_url_id: int):
    """
    Allows a user to update a URL title without updating the url.
    Only the user who added the URL, or who created the UTub containing
    the URL, can modify the title.

    Args:
        utub_id (int): The UTub ID containing the relevant URL title
        utub_url_id (int): The URL ID to have the title be modified
    """
    utub: Utubs = Utubs.query.get_or_404(utub_id)
    utub_creator_id = utub.utub_creator

    # Search through all urls in the UTub for the one that matches the prescribed
    # URL ID and get the user who added it - should be only one
    url_in_utub: Utub_Urls | None = Utub_Urls.query.get(utub_url_id)
    if url_in_utub is None:
        critical_log(
            f"User={current_user.id} tried to modify title for nonexistent UTubURL.id={utub_url_id} from UTub.id={utub_id}"
        )
        abort(404)

    if url_in_utub.utub_id != utub_id:
        critical_log(
            f"User={current_user.id} tried to modify title for UTubURL.id={utub_url_id} that is not in UTub.id={utub_id}"
        )
        abort(404)

    user_in_utub = Utub_Members.query.get((utub_id, current_user.id)) is not None
    user_added_url_or_is_utub_creator = (
        current_user.id == utub_creator_id or current_user.id == url_in_utub.user_id
    )

    if not user_in_utub or not user_added_url_or_is_utub_creator:
        # Can only modify titles for URLs you added, or if you are the creator of this UTub
        if not user_in_utub:
            critical_log(f"User={current_user.id} not in UTub.id={utub_id}")
        else:
            critical_log(
                f"User={current_user.id} not allowed to modify UTubURL.id={utub_url_id} in UTub.id={utub_id}"
            )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            403,
        )

    update_url_title_form: UpdateURLTitleForm = UpdateURLTitleForm()

    if update_url_title_form.validate_on_submit():
        url_title_to_change_to = update_url_title_form.url_title.get()
        serialized_url_in_utub = url_in_utub.serialized_on_get_or_update
        title_diff = url_title_to_change_to != url_in_utub.url_title

        if title_diff:
            # Change the title
            url_in_utub.url_title = url_title_to_change_to
            serialized_url_in_utub = url_in_utub.serialized_on_get_or_update
            utub.set_last_updated()
            db.session.commit()
            safe_add_log("URL title updated")
        else:
            warning_log(f"User={current_user.id} tried updating to identical URL title")

        return jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS if title_diff else STD_JSON.NO_CHANGE,
                STD_JSON.MESSAGE: (
                    URL_SUCCESS.URL_TITLE_MODIFIED
                    if title_diff
                    else URL_NO_CHANGE.URL_TITLE_NOT_MODIFIED
                ),
                URL_SUCCESS.URL: serialized_url_in_utub,
            }
        )

    # Missing URL title field
    if update_url_title_form.url_title.data is None:
        warning_log(f"User={current_user.id} missing URL title field")
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
                    STD_JSON.ERROR_CODE: 2,
                    STD_JSON.ERRORS: {
                        URL_FAILURE.URL_TITLE: URL_FAILURE.FIELD_REQUIRED
                    },
                }
            ),
            400,
        )

    # Invalid form input
    if update_url_title_form.errors is not None:
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(update_url_title_form.errors)}"  # type: ignore
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
                    STD_JSON.ERROR_CODE: 3,
                    STD_JSON.ERRORS: build_form_errors(update_url_title_form),
                }
            ),
            400,
        )

    # Something else went wrong
    critical_log("Unable to update URL title in UTub")
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
                STD_JSON.ERROR_CODE: 4,
            }
        ),
        404,
    )
