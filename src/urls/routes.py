from flask import Blueprint, jsonify, request
from flask_login import current_user

from src import db
from src.models import Utub, Utub_Urls, URLS, Url_Tags
from src.urls.forms import (
    NewURLForm,
    EditURLForm,
)
from src.utils.url_validation import InvalidURLError, check_request_head
from src.utils import strings as U4I_STRINGS
from src.utils.email_validation import email_validation_required

urls = Blueprint("urls", __name__)

# Standard response for JSON messages
STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
URL_FAILURE = U4I_STRINGS.URL_FAILURE
URL_NO_CHANGE = U4I_STRINGS.URL_NO_CHANGE
URL_SUCCESS = U4I_STRINGS.URL_SUCCESS


@urls.route("/url/remove/<int:utub_id>/<int:url_id>", methods=["POST"])
@email_validation_required
def delete_url(utub_id: int, url_id: int):
    """
    User wants to delete a URL from a UTub. Only available to owner of that utub,
    or whoever added the URL into that Utub.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be deleted
        url_id (int): The ID of the URL to be deleted
    """
    utub = Utub.query.get_or_404(utub_id)
    utub_owner_id = int(utub.created_by.id)

    # Search through all urls in the UTub for the one that matches the prescribed URL ID and get the user who added it - should be only one
    url_in_utub = Utub_Urls.query.filter(
        Utub_Urls.url_id == url_id, Utub_Urls.utub_id == utub_id
    ).first_or_404()

    if current_user.id == utub_owner_id or current_user.id == url_in_utub.user_id:
        # Store serialized data from URL association with UTub and associated tags
        serialized_url_in_utub = url_in_utub.serialized

        # Can only delete URLs as the creator of UTub, or as the adder of that URL
        db.session.delete(url_in_utub)

        # Remove all tags associated with this URL in this UTub as well
        Url_Tags.query.filter_by(utub_id=utub_id, url_id=url_id).delete()

        db.session.commit()

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
                    URL_SUCCESS.URL: serialized_url_in_utub,
                    URL_SUCCESS.UTUB_ID: f"{utub.id}",
                    URL_SUCCESS.UTUB_NAME: f"{utub.name}",
                }
            ),
            200,
        )

    else:
        # Can only delete URLs you added, or if you are the creator of this UTub
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_REMOVE_URL,
                }
            ),
            403,
        )


@urls.route("/url/add/<int:utub_id>", methods=["POST"])
@email_validation_required
def add_url(utub_id: int):
    """
    User wants to add URL to UTub. On success, adds the URL to the UTub.

    Args:
        utub_id (int): The Utub to add this URL to
    """
    utub = Utub.query.get_or_404(utub_id)

    if current_user.id not in [member.user_id for member in utub.members]:
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

    utub_new_url_form = NewURLForm()

    if utub_new_url_form.validate_on_submit():
        url_string = utub_new_url_form.url_string.data

        try:
            user_agent = request.headers.get("User-agent")
            normalized_url = check_request_head(url_string, user_agent)
        except InvalidURLError:
            # URL was unable to be verified as a valid URL
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL,
                        STD_JSON.ERROR_CODE: 2,
                    }
                ),
                400,
            )

        # Check if URL already exists
        already_created_url = URLS.query.filter_by(url_string=normalized_url).first()

        if not already_created_url:
            # If URL does not exist, add it and then associate it with the UTub
            new_url = URLS(
                normalized_url=normalized_url, current_user_id=current_user.get_id()
            )

            # Commit new URL to the database
            db.session.add(new_url)
            db.session.commit()

            # Associate URL with given UTub
            url_id = new_url.id
            url_utub_user_add = Utub_Urls(
                utub_id=utub_id,
                url_id=url_id,
                user_id=current_user.id,
                url_notes=utub_new_url_form.url_title.data,
            )
            db.session.add(url_utub_user_add)
            db.session.commit()

            # Successfully added a URL, and associated it to a UTub
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.SUCCESS,
                        STD_JSON.MESSAGE: URL_SUCCESS.URL_CREATED_ADDED,
                        URL_SUCCESS.URL: {
                            URL_SUCCESS.URL_STRING: f"{normalized_url}",
                            URL_SUCCESS.URL_ID: f"{url_id}",
                            URL_SUCCESS.URL_TITLE: f"{utub_new_url_form.url_title.data}",
                        },
                        URL_SUCCESS.UTUB_ID: f"{utub_id}",
                        URL_SUCCESS.UTUB_NAME: f"{utub.name}",
                        URL_SUCCESS.ADDED_BY: f"{current_user.get_id()}",
                    }
                ),
                200,
            )

        else:
            # If URL does already exist, check if associated with UTub
            url_id = already_created_url.id
            utub_url_if_already_exists = Utub_Urls.query.filter_by(
                utub_id=utub_id, url_id=url_id
            ).first()

            if utub_url_if_already_exists is None:
                # URL exists and is not associated with a UTub, so associate this URL with this UTub
                new_url_utub_association = Utub_Urls(
                    utub_id=utub_id,
                    url_id=already_created_url.id,
                    user_id=current_user.id,
                )
                db.session.add(new_url_utub_association)
                db.session.commit()

                # Succesfully associated the URL with a new UTub
                return (
                    jsonify(
                        {
                            STD_JSON.STATUS: STD_JSON.SUCCESS,
                            STD_JSON.MESSAGE: URL_SUCCESS.URL_ADDED,
                            URL_SUCCESS.URL: {
                                URL_SUCCESS.URL_STRING: f"{normalized_url}",
                                URL_SUCCESS.URL_ID: f"{url_id}",
                                URL_SUCCESS.url_title: f"{utub_new_url_form.url_title.data}",
                            },
                            URL_SUCCESS.UTUB_ID: f"{utub_id}",
                            URL_SUCCESS.UTUB_NAME: f"{utub.name}",
                            URL_SUCCESS.ADDED_BY: f"{current_user.get_id()}",
                        }
                    ),
                    200,
                )

            else:
                # URL already exists in UTub
                return (
                    jsonify(
                        {
                            STD_JSON.STATUS: STD_JSON.FAILURE,
                            STD_JSON.MESSAGE: URL_FAILURE.URL_IN_UTUB,
                            STD_JSON.ERROR_CODE: 3,
                        }
                    ),
                    400,
                )

    # Invalid form input
    if utub_new_url_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL_FORM,
                    STD_JSON.ERROR_CODE: 4,
                    STD_JSON.ERRORS: utub_new_url_form.errors,
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


@urls.route("/url/edit/<int:utub_id>/<int:url_id>", methods=["POST"])
@email_validation_required
def edit_url_and_title(utub_id: int, url_id: int):
    """
    Edits the URL contained in the UTub.
    If user makes no edits or produces the same URL, then no edits occur.

    If the user provides a different URL, then remove the old URL from URL-UTUB association table, and
    add in the new one.
        If the new URL does not exist in the URLS table, first add it there.
    """

    utub = Utub.query.get_or_404(utub_id)
    utub_owner_id = int(utub.created_by.id)

    # Search through all urls in the UTub for the one that matches the prescribed URL ID and get the user who added it - should be only one
    url_in_utub = Utub_Urls.query.filter(
        Utub_Urls.url_id == url_id, Utub_Urls.utub_id == utub_id
    ).first_or_404()

    if current_user.id != utub_owner_id and current_user.id != url_in_utub.user_id:
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

    edit_url_form = EditURLForm()

    if (
        edit_url_form.validate_on_submit()
        and edit_url_form.url_title.data is not None
    ):
        url_to_change_to = edit_url_form.url_string.data.replace(" ", "")

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

        url_title_to_change_to = edit_url_form.url_title.data
        serialized_url_in_utub = url_in_utub.serialized

        if url_to_change_to == url_in_utub.url_in_utub.url_string:
            # Identical URL

            if url_title_to_change_to == url_in_utub.url_notes:
                # Identical title
                return jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.NO_CHANGE,
                        STD_JSON.MESSAGE: URL_NO_CHANGE.URL_AND_TITLE_NOT_MODIFIED,
                        URL_SUCCESS.URL: serialized_url_in_utub,
                        URL_SUCCESS.UTUB_ID: f"{utub.id}",
                        URL_SUCCESS.UTUB_NAME: f"{utub.name}",
                    }
                )

            else:
                # Just change the title
                url_in_utub.url_notes = url_title_to_change_to
                new_serialized_url = url_in_utub.serialized
                db.session.commit()

                return jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.SUCCESS,
                        STD_JSON.MESSAGE: URL_SUCCESS.URL_TITLE_MODIFIED,
                        URL_SUCCESS.URL: new_serialized_url,
                        URL_SUCCESS.UTUB_ID: f"{utub.id}",
                        URL_SUCCESS.UTUB_NAME: f"{utub.name}",
                    }
                )

        # Here the user wants to try to change or modify the URL
        try:
            normalized_url = check_request_head(url_to_change_to)
        except InvalidURLError:
            # URL was unable to be verified as a valid URL
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
                        STD_JSON.ERROR_CODE: 3,
                    }
                ),
                400,
            )

        # Now check if url already in database
        url_already_in_database = URLS.query.filter_by(
            url_string=normalized_url
        ).first()

        if url_already_in_database is None:
            # Make a new URL since URL is not already in the database
            new_url = URLS(
                normalized_url=normalized_url, current_user_id=current_user.id
            )
            db.session.add(new_url)
            db.session.commit()

            url_in_database = new_url
        else:
            url_in_database = url_already_in_database

        # Now check if this normalized URL is the same as the original, just in case
        if url_in_database == url_to_change_to:
            # Same URL after normalizing
            if url_title_to_change_to == url_in_utub.url_notes:
                # Identical title
                return jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.NO_CHANGE,
                        STD_JSON.MESSAGE: URL_NO_CHANGE.URL_AND_TITLE_NOT_MODIFIED,
                        URL_SUCCESS.URL: serialized_url_in_utub,
                        URL_SUCCESS.UTUB_ID: f"{utub.id}",
                        URL_SUCCESS.UTUB_NAME: f"{utub.name}",
                    }
                )

            else:
                # Just change the title 
                url_in_utub.url_notes = url_title_to_change_to
                new_serialized_url = url_in_utub.serialized
                db.session.commit()

                return jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.SUCCESS,
                        STD_JSON.MESSAGE: URL_SUCCESS.URL_TITLE_MODIFIED,
                        URL_SUCCESS.URL: new_serialized_url,
                        URL_SUCCESS.UTUB_ID: f"{utub.id}",
                        URL_SUCCESS.UTUB_NAME: f"{utub.name}",
                    }
                )

        # Completely new URL. Now set the URL ID for the old URL to the new URL
        url_in_utub.url_id = url_in_database.id
        url_in_utub.url_in_utub = url_in_database

        # Finally check and update the title
        if url_title_to_change_to != url_in_utub.url_notes:
            url_in_utub.url_notes = url_title_to_change_to

        # Find tags associated with URL
        url_tags = Url_Tags.query.filter_by(utub_id=utub_id, url_id=url_id).all()

        for url_tag in url_tags:
            url_tag.url_id = url_in_database.id

        new_serialized_url = url_in_utub.serialized

        db.session.commit()

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: URL_SUCCESS.URL_OR_TITLE_MODIFIED,
                    URL_SUCCESS.URL: new_serialized_url,
                    URL_SUCCESS.UTUB_ID: f"{utub.id}",
                    URL_SUCCESS.UTUB_NAME: f"{utub.name}",
                }
            ),
            200,
        )

    # Missing URL title field
    if edit_url_form.url_title.data is None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
                    STD_JSON.ERROR_CODE: 4,
                    STD_JSON.ERRORS: {
                        URL_FAILURE.URL_TITLE: URL_FAILURE.FIELD_REQUIRED
                    },
                }
            ),
            400,
        )

    # Invalid form input
    if edit_url_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
                    STD_JSON.ERROR_CODE: 5,
                    STD_JSON.ERRORS: edit_url_form.errors,
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
