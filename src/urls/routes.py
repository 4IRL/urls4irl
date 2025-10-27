import time

from flask import abort, Blueprint, current_app, jsonify
from flask_login import current_user

from src import db
from src.app_logger import (
    critical_log,
    safe_add_log,
    safe_add_many_logs,
    safe_get_request_id,
    turn_form_into_str_for_log,
    warning_log,
)
from src.extensions.extension_utils import safe_get_notif_sender, safe_get_url_validator
from src.extensions.url_validation.url_validator import (
    AdaUrlParsingError,
    InvalidURLError,
    URLWithCredentialsError,
)
from src.models.urls import Urls
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
    associate_url_with_utub,
    check_if_is_url_adder_or_utub_creator_on_url_delete,
    check_url_already_in_utub,
    get_or_create_url,
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
    utub_creator_or_adder_response = (
        check_if_is_url_adder_or_utub_creator_on_url_delete(
            utub_id=utub_id, utub_url_id=utub_url_id
        )
    )

    if utub_creator_or_adder_response is not None:
        return utub_creator_or_adder_response

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

    url_id, url_state = get_or_create_url(validated_ada_url)

    if url_state == URLState.EXISTING_URL:
        url_already_in_utub_response = check_url_already_in_utub(
            utub_id, url_id, validated_ada_url
        )

        if url_already_in_utub_response is not None:
            return url_already_in_utub_response

    # Associate URL with given UTub
    return associate_url_with_utub(
        current_utub=current_utub,
        url_id=url_id,
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
@email_validation_required
def update_url(utub_id: int, utub_url_id: int):
    """
    Allows a user to update a URL without updating the title.
    Only the user who added the URL, or who created the UTub containing
    the URL, can modify the URL.

    Args:
        utub_id (int): The UTub ID containing the relevant URL
        utub_url_id (int): The URL ID to be modified
    """
    utub: Utubs = Utubs.query.get_or_404(utub_id)
    utub_creator_id = utub.utub_creator

    # Search through all urls in the UTub for the one that matches the prescribed
    # URL ID and get the user who added it - should be only one
    url_in_utub: Utub_Urls | None = Utub_Urls.query.get(utub_url_id)
    if url_in_utub is None:
        critical_log(
            f"User={current_user.id} tried to change nonexistent UTubURL.id={utub_url_id} in UTub.id={utub_id}"
        )
        abort(404)

    if url_in_utub.utub_id != utub_id:
        critical_log(
            f"User={current_user.id} tried to change UTubURL.id={utub_url_id} that is not in UTub.id={utub_id}"
        )
        abort(404)

    user_in_utub = Utub_Members.query.get((utub_id, current_user.id)) is not None
    user_added_url_or_is_utub_creator = (
        current_user.id == utub_creator_id or current_user.id == url_in_utub.user_id
    )

    if not user_in_utub or not user_added_url_or_is_utub_creator:
        # Can only modify URLs you added, or if you are the creator of this UTub
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

    update_url_form: UpdateURLForm = UpdateURLForm()

    if update_url_form.validate_on_submit():
        url_to_change_to: str = update_url_form.get_url_string().replace(" ", "")

        if url_to_change_to == "":
            warning_log(
                f"User={current_user.id} tried changing UTubURL.id={utub_url_id} to a URL with only spaces"
            )
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: URL_FAILURE.EMPTY_URL,
                        STD_JSON.ERROR_CODE: 2,
                    }
                ),
                400,
            )

        serialized_url_in_utub = url_in_utub.serialized_on_get_or_update

        if url_to_change_to == url_in_utub.standalone_url.url_string:
            # Identical URL
            warning_log(
                f"User={current_user.id} tried changing UTubURL.id={utub_url_id} to the same URL"
            )
            return jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.NO_CHANGE,
                    STD_JSON.MESSAGE: URL_NO_CHANGE.URL_NOT_MODIFIED,
                    URL_SUCCESS.URL: serialized_url_in_utub,
                }
            )

        # Here the user wants to try to change or modify the URL
        start = time.perf_counter()
        url_validator = safe_get_url_validator(current_app)
        try:
            normalized_url = url_validator.normalize_url(url_to_change_to)

            normalized_time = (time.perf_counter() - start) * 1000

            validated_ada_url = url_validator.validate_url(normalized_url)

            validation_time = (time.perf_counter() - start) * 1000

        except URLWithCredentialsError as e:
            end = (time.perf_counter() - start) * 1000
            request_id = safe_get_request_id()
            warning_log(
                f"[{request_id}] URL with crendentials passed by User={current_user.id}\n"
                + f"[{request_id}] Took {end:.3f} ms to fail validation\n"
                + f"[{request_id}] Exception={str(e)}"
            )

            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION,
                        STD_JSON.DETAILS: str(e),
                        STD_JSON.ERROR_CODE: 7,
                    }
                ),
                400,
            )

        except InvalidURLError as e:
            end = (time.perf_counter() - start) * 1000
            request_id = safe_get_request_id()

            warning_log(
                f"[{request_id}] Unable to validate the URL given by User={current_user.id}\n"
                + f"[{request_id}] Took {end:.3f} ms to fail validation\n"
                + f"[{request_id}] url_string={url_to_change_to}\n"
                + f"[{request_id}] Exception={str(e)}"
            )

            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL,
                        STD_JSON.DETAILS: str(e),
                        STD_JSON.ERROR_CODE: 3,
                    }
                ),
                400,
            )

        except (AdaUrlParsingError, Exception) as e:
            end = (time.perf_counter() - start) * 1000
            request_id = safe_get_request_id()

            critical_log(
                f"[{request_id}] Unexpected exception validating the URL given by User={current_user.id}\n"
                + f"[{request_id}] Took {end:.3f} ms to fail validation\n"
                + f"[{request_id}] url_string={url_to_change_to}\n"
                + f"[{request_id}] Exception={str(e)}"
            )
            notification_sender = safe_get_notif_sender(current_app)
            notification_sender.send_notification(
                f"Unexpected exception validating {url_to_change_to} | Exception={str(e)}"
            )

            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: URL_FAILURE.UNEXPECTED_VALIDATION_EXCEPTION,
                        STD_JSON.DETAILS: str(e),
                        STD_JSON.ERROR_CODE: -1,
                    }
                ),
                400,
            )

        end = (time.perf_counter() - start) * 1000
        safe_add_many_logs(
            [
                f"Finished checks for {url_to_change_to=}",
                f"Took {normalized_time:.3f} ms for normalization",
                f"Took {(validation_time - normalized_time):.3f} ms total for validation",
                f"Took {end:.3f} ms total",
            ]
        )

        # Now check if url already in database
        url_already_in_database: Urls | None = Urls.query.filter(
            Urls.url_string == validated_ada_url
        ).first()

        if url_already_in_database is None:
            # Make a new URL since URL is not already in the database
            new_url = Urls(
                normalized_url=validated_ada_url,
                current_user_id=current_user.id,
            )
            db.session.add(new_url)
            db.session.commit()

            safe_add_log(f"Added new URL, URL.id={new_url.id}")

            url_in_database = new_url
            url_id = url_in_database.id
        else:
            url_in_database = url_already_in_database
            url_id = url_in_database.id

            safe_add_log(f"URL already exists in U4I, URL.id={url_id}")

            # Check if URL already in UTub
            url_already_in_utub = (
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id,
                    Utub_Urls.url_id == url_already_in_database.id,
                ).first()
                is not None
            )

            if url_already_in_utub:
                # URL already exists in UTub
                warning_log(
                    f"User={current_user.id} tried adding URL.id={url_id} but already exists in UTub.id={utub_id}"
                )
                return (
                    jsonify(
                        {
                            STD_JSON.STATUS: STD_JSON.FAILURE,
                            STD_JSON.MESSAGE: URL_FAILURE.URL_IN_UTUB,
                            STD_JSON.ERROR_CODE: 4,
                            URL_FAILURE.URL_STRING: url_already_in_database.url_string,
                        }
                    ),
                    409,
                )

        # Completely new URL. Now set the URL ID for the old URL to the new URL
        url_in_utub.url_id = url_in_database.id
        url_in_utub.standalone_url = url_in_database

        new_serialized_url = url_in_utub.serialized_on_get_or_update

        utub.set_last_updated()
        db.session.commit()

        safe_add_many_logs(
            ["Added URL to UTub", f"UTub.id={utub_id}", f"URL.id={url_id}"]
        )

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
                    URL_SUCCESS.UTUB_ID: utub.id,
                    URL_SUCCESS.UTUB_NAME: utub.name,
                    URL_SUCCESS.URL: new_serialized_url,
                }
            ),
            200,
        )

    # Invalid form input
    if update_url_form.errors is not None:
        warning_log(f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(update_url_form.errors)}")  # type: ignore
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
                    STD_JSON.ERROR_CODE: 5,
                    STD_JSON.ERRORS: build_form_errors(update_url_form),
                }
            ),
            400,
        )

    # Something else went wrong
    critical_log("Unable to update URL to UTub")
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
                STD_JSON.ERROR_CODE: 6,
            }
        ),
        404,
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
