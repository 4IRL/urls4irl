import logging
import time

from flask import abort, Blueprint, current_app, jsonify, request
from flask_login import current_user

from src import db, url_validator
from src.extensions.url_validation.url_validator import (
    InvalidURLError,
    WaybackRateLimited,
)
from src.models.urls import Possible_Url_Validation, Urls
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utub_urls import Utub_Urls
from src.urls.forms import (
    NewURLForm,
    UpdateURLForm,
    UpdateURLTitleForm,
)
from src.urls.utils import build_form_errors
from src.utils.email_validation import email_validation_required
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.url_strs import URL_SUCCESS, URL_FAILURE, URL_NO_CHANGE

urls = Blueprint("urls", __name__)
logger = logging.getLogger(__name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["DELETE"])
@email_validation_required
def delete_url(utub_id: int, utub_url_id: int):
    """
    User wants to remove a URL from a UTub. Only available to owner of that utub,
    or whoever added the URL into that Utubs.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be removed
        utub_url_id (int): The ID of the UtubUrl to be removed
    """
    utub: Utubs = Utubs.query.get_or_404(utub_id)
    utub_creator_id = utub.utub_creator

    # Search through all urls in the UTub for the one that matches the prescribed URL ID and get the user who added it - should be only one
    url_in_utub: Utub_Urls = Utub_Urls.query.get_or_404(utub_url_id)
    if url_in_utub.utub_id != utub_id:
        abort(404)

    user_in_utub = Utub_Members.query.get((utub_id, current_user.id)) is not None
    user_url_adder_or_utub_creator = (
        current_user.id == utub_creator_id or current_user.id == url_in_utub.user_id
    )

    if user_in_utub and user_url_adder_or_utub_creator:
        # Store serialized data from URL association with UTub and associated tags
        url_string_to_remove = url_in_utub.standalone_url.url_string

        # Remove all tags associated with this URL in this UTub
        Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_url_id == utub_url_id
        ).delete()

        # Can only remove URLs as the creator of UTub, or as the adder of that URL
        db.session.delete(url_in_utub)
        utub.set_last_updated()

        db.session.commit()

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
                    URL_SUCCESS.UTUB_ID: utub.id,
                    URL_SUCCESS.URL: {
                        URL_SUCCESS.URL_STRING: url_string_to_remove,
                        URL_SUCCESS.UTUB_URL_ID: utub_url_id,
                        URL_SUCCESS.URL_TITLE: url_in_utub.url_title,
                    },
                }
            ),
            200,
        )

    else:
        # Can only remove URLs you added, or if you are the creator of this UTub
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_DELETE_URL,
                }
            ),
            403,
        )


@urls.route("/utubs/<int:utub_id>/urls", methods=["POST"])
@email_validation_required
def create_url(utub_id: int):
    """
    User wants to add URL to UTub. On success, adds the URL to the UTub.

    Args:
        utub_id (int): The Utubs to add this URL to
    """
    utub: Utubs = Utubs.query.get_or_404(utub_id)
    user_in_utub = Utub_Members.query.get((utub_id, current_user.id)) is not None

    if not user_in_utub:
        # Not authorized to add URL to this UTub
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            403,
        )

    utub_new_url_form: NewURLForm = NewURLForm()

    if utub_new_url_form.validate_on_submit():
        url_string = utub_new_url_form.url_string.data
        start = time.perf_counter() if not current_app.testing else None

        try:
            headers = request.headers
            normalized_url, is_validated = url_validator.validate_url(
                url_string, headers
            )

        except InvalidURLError as e:
            # TODO: Adding logging for this failed URL validation attempts
            # URL was unable to be verified as a valid URL
            end = (
                time.perf_counter() - start
                if not current_app.testing and start
                else None
            )
            (
                logger.error(f"Took {end} seconds to fail validating URL.")
                if not current_app.testing
                else None
            )

            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL,
                        STD_JSON.DETAILS: str(e),
                        STD_JSON.ERROR_CODE: 2,
                    }
                ),
                400,
            )
        except WaybackRateLimited as e:
            end = (
                time.perf_counter() - start
                if not current_app.testing and start
                else None
            )
            (
                logger.error(
                    f"Took {end} seconds to fail validating URL with Wayback rate limiting."
                )
                if not current_app.testing
                else None
            )
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: URL_FAILURE.TOO_MANY_WAYBACK_ATTEMPTS,
                        STD_JSON.DETAILS: str(e),
                        STD_JSON.ERROR_CODE: 6,
                    }
                ),
                400,
            )

        end = time.perf_counter() - start if not current_app.testing and start else None
        (
            logger.info(f"Took {end} seconds to validate URL.")
            if not current_app.testing
            else None
        )

        # Check if URL already exists
        already_created_url: Urls = Urls.query.filter(
            Urls.url_string == normalized_url
        ).first()

        if not already_created_url:
            # If URL does not exist, add it and then associate it with the UTub
            validated_str = (
                Possible_Url_Validation.VALIDATED.value
                if is_validated
                else Possible_Url_Validation.UNKNOWN.value
            )
            new_url = Urls(
                normalized_url=normalized_url,
                current_user_id=current_user.id,
                is_validated=validated_str,
            )

            # Commit new URL to the database
            db.session.add(new_url)
            db.session.commit()

            url_id = new_url.id

        else:
            # If URL does already exist, check if associated with UTub
            url_id = already_created_url.id
            utub_url_if_already_exists = Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id, Utub_Urls.url_id == url_id
            ).first()

            if utub_url_if_already_exists is not None:
                # URL already exists in UTub
                return (
                    jsonify(
                        {
                            STD_JSON.STATUS: STD_JSON.FAILURE,
                            STD_JSON.MESSAGE: URL_FAILURE.URL_IN_UTUB,
                            STD_JSON.ERROR_CODE: 3,
                            URL_FAILURE.URL_STRING: already_created_url.url_string,
                        }
                    ),
                    409,
                )

        # Associate URL with given UTub
        url_utub_user_add = Utub_Urls(
            utub_id=utub_id,
            url_id=url_id,
            user_id=current_user.id,
            url_title=utub_new_url_form.url_title.data,
        )
        db.session.add(url_utub_user_add)
        utub.set_last_updated()
        db.session.commit()

        # Successfully added a URL, and associated it to a UTub
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: (
                        URL_SUCCESS.URL_CREATED_ADDED
                        if not already_created_url
                        else URL_SUCCESS.URL_ADDED
                    ),
                    URL_SUCCESS.UTUB_ID: utub_id,
                    URL_SUCCESS.ADDED_BY: current_user.id,
                    URL_SUCCESS.URL: {
                        URL_SUCCESS.URL_STRING: normalized_url,
                        URL_SUCCESS.UTUB_URL_ID: url_utub_user_add.id,
                        URL_SUCCESS.URL_TITLE: utub_new_url_form.url_title.data,
                    },
                }
            ),
            200,
        )

    # Invalid form input
    if utub_new_url_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL_FORM,
                    STD_JSON.ERROR_CODE: 4,
                    STD_JSON.ERRORS: build_form_errors(utub_new_url_form),
                }
            ),
            400,
        )

    # Something else went wrong
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL,
                STD_JSON.ERROR_CODE: 5,
            }
        ),
        404,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:utub_url_id>", methods=["GET"])
@email_validation_required
def get_url(utub_id: int, utub_url_id: int):
    """
    Allows a user to read a URL in a UTub. Only users who are a member of the
    UTub can GET this URL.

    Args:
        utub_id (int): The UTub ID containing the relevant URL
        utub_url_id (int): The URL ID to be modified
    """
    # Following line enforces standard response of 404 error page
    Utubs.query.get_or_404(utub_id)

    user_in_utub = Utub_Members.query.get((utub_id, current_user.id)) is not None
    if not user_in_utub:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_RETRIEVE_URL,
                }
            ),
            403,
        )

    url_in_utub: Utub_Urls | None = Utub_Urls.query.get(utub_url_id)

    if url_in_utub is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: URL_SUCCESS.URL_FOUND_IN_UTUB,
                    URL_SUCCESS.URL: url_in_utub.serialized_on_get_or_update,
                }
            ),
            200,
        )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_RETRIEVE_URL,
            }
        ),
        404,
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
    url_in_utub: Utub_Urls = Utub_Urls.query.get(utub_url_id)
    if url_in_utub.utub_id != utub_id:
        abort(404)

    user_in_utub = Utub_Members.query.get((utub_id, current_user.id)) is not None
    user_added_url_or_is_utub_creator = (
        current_user.id == utub_creator_id or current_user.id == url_in_utub.user_id
    )

    if not user_in_utub or not user_added_url_or_is_utub_creator:
        # Can only modify URLs you added, or if you are the creator of this UTub
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
        url_to_change_to: str = update_url_form.url_string.data.replace(" ", "")  # type: ignore

        if url_to_change_to == "":
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
            return jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.NO_CHANGE,
                    STD_JSON.MESSAGE: URL_NO_CHANGE.URL_NOT_MODIFIED,
                    URL_SUCCESS.URL: serialized_url_in_utub,
                }
            )

        # Here the user wants to try to change or modify the URL
        start = time.perf_counter() if not current_app.testing else None
        try:
            headers = request.headers
            normalized_url, is_validated = url_validator.validate_url(
                url_to_change_to, headers
            )
        except InvalidURLError as e:
            # TODO: Adding logging for this failed URL validation attempt
            # URL was unable to be verified as a valid URL
            end = (
                time.perf_counter() - start
                if not current_app.testing and start
                else None
            )
            (
                logger.error(f"Took {end} seconds to fail validating URL.")
                if not current_app.testing
                else None
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
        except WaybackRateLimited as e:
            end = (
                time.perf_counter() - start
                if not current_app.testing and start
                else None
            )
            (
                logger.error(
                    f"Took {end} seconds to fail validating URL with Wayback rate limiting."
                )
                if not current_app.testing
                else None
            )
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: URL_FAILURE.TOO_MANY_WAYBACK_ATTEMPTS,
                        STD_JSON.DETAILS: str(e),
                        STD_JSON.ERROR_CODE: 6,
                    }
                ),
                400,
            )

        end = time.perf_counter() - start if not current_app.testing and start else None
        (
            logger.info(f"Took {end} seconds to validate URL.")
            if not current_app.testing
            else None
        )

        # Now check if url already in database
        url_already_in_database: Urls | None = Urls.query.filter(
            Urls.url_string == normalized_url
        ).first()

        if url_already_in_database is None:
            # Make a new URL since URL is not already in the database
            validated_str = (
                Possible_Url_Validation.VALIDATED.value
                if is_validated
                else Possible_Url_Validation.UNKNOWN.value
            )
            new_url = Urls(
                normalized_url=normalized_url,
                current_user_id=current_user.id,
                is_validated=validated_str,
            )
            db.session.add(new_url)
            db.session.commit()

            url_in_database = new_url
        else:
            url_in_database = url_already_in_database

            # Check if URL already in UTub
            url_already_in_utub = (
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id,
                    Utub_Urls.url_id == url_already_in_database.id,
                ).first()
                is not None
            )

            if url_already_in_utub:
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

        # Now check if this normalized URL is the same as the original
        if url_in_database.url_string == url_in_utub.standalone_url.url_string:
            # Same URL after normalizing
            return jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.NO_CHANGE,
                    STD_JSON.MESSAGE: URL_NO_CHANGE.URL_NOT_MODIFIED,
                    URL_SUCCESS.UTUB_ID: utub.id,
                    URL_SUCCESS.UTUB_NAME: utub.name,
                    URL_SUCCESS.URL: serialized_url_in_utub,
                }
            )

        # Completely new URL. Now set the URL ID for the old URL to the new URL
        url_in_utub.url_id = url_in_database.id
        url_in_utub.standalone_url = url_in_database

        new_serialized_url = url_in_utub.serialized_on_get_or_update

        utub.set_last_updated()
        db.session.commit()

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
    url_in_utub: Utub_Urls = Utub_Urls.query.get_or_404(utub_url_id)
    if url_in_utub.utub_id != utub_id:
        abort(404)

    user_in_utub = Utub_Members.query.get((utub_id, current_user.id)) is not None
    user_added_url_or_is_utub_creator = (
        current_user.id == utub_creator_id or current_user.id == url_in_utub.user_id
    )

    if not user_in_utub or not user_added_url_or_is_utub_creator:
        # Can only modify titles for URLs you added, or if you are the creator of this UTub
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
        url_title_to_change_to = (
            update_url_title_form.url_title.data
            if update_url_title_form.url_title.data is not None
            else ""
        )
        serialized_url_in_utub = url_in_utub.serialized_on_get_or_update
        title_diff = url_title_to_change_to != url_in_utub.url_title

        if title_diff:
            # Change the title
            url_in_utub.url_title = url_title_to_change_to
            serialized_url_in_utub = url_in_utub.serialized_on_get_or_update
            utub.set_last_updated()
            db.session.commit()

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
