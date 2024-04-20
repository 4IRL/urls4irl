from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from src import db
from src.models import Utub, Utub_Urls, URLS, Url_Tags
from src.urls.forms import (
    NewURLForm,
    EditURLAndTitleForm,
    EditURLForm,
    EditURLTitleForm,
)
from src.urls.utils import build_form_errors
from src.utils.url_validation import InvalidURLError, find_common_url
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.url_strs import URL_SUCCESS, URL_FAILURE, URL_NO_CHANGE
from src.utils.email_validation import email_validation_required

urls = Blueprint("urls", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@urls.route("/utubs/<int:utub_id>/urls/<int:url_id>", methods=["DELETE"])
@email_validation_required
def remove_url(utub_id: int, url_id: int):
    """
    User wants to remove a URL from a UTub. Only available to owner of that utub,
    or whoever added the URL into that Utub.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be removed
        url_id (int): The ID of the URL to be removed
    """
    utub: Utub = Utub.query.get_or_404(utub_id)
    utub_owner_id = utub.utub_creator

    # Search through all urls in the UTub for the one that matches the prescribed URL ID and get the user who added it - should be only one
    url_in_utub: Utub_Urls = Utub_Urls.query.filter(
        Utub_Urls.url_id == url_id, Utub_Urls.utub_id == utub_id
    ).first_or_404()

    if current_user.id == utub_owner_id or current_user.id == url_in_utub.user_id:
        # Store serialized data from URL association with UTub and associated tags
        associated_tags = url_in_utub.associated_tags

        # Can only remove URLs as the creator of UTub, or as the adder of that URL
        db.session.delete(url_in_utub)

        # Remove all tags associated with this URL in this UTub as well
        Url_Tags.query.filter_by(utub_id=utub_id, url_id=url_id).delete()

        db.session.commit()

        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
                    URL_SUCCESS.UTUB_ID: utub.id,
                    URL_SUCCESS.UTUB_NAME: utub.name,
                    URL_SUCCESS.URL: {
                        URL_SUCCESS.URL_STRING: url_in_utub.standalone_url.url_string,
                        URL_SUCCESS.URL_ID: url_id,
                        URL_SUCCESS.URL_TITLE: url_in_utub.url_title,
                    },
                    URL_SUCCESS.URL_TAGS: associated_tags,
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
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_REMOVE_URL,
                }
            ),
            403,
        )


@urls.route("/utubs/<int:utub_id>/urls", methods=["POST"])
@email_validation_required
def add_url(utub_id: int):
    """
    User wants to add URL to UTub. On success, adds the URL to the UTub.

    Args:
        utub_id (int): The Utub to add this URL to
    """
    utub: Utub = Utub.query.get_or_404(utub_id)

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
            user_agent = request.headers if not current_app.testing else None
            normalized_url = find_common_url(url_string, user_agent)
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
        already_created_url: URLS = URLS.query.filter_by(
            url_string=normalized_url
        ).first()

        if not already_created_url:
            # If URL does not exist, add it and then associate it with the UTub
            new_url = URLS(
                normalized_url=normalized_url, current_user_id=current_user.id
            )

            # Commit new URL to the database
            db.session.add(new_url)
            db.session.commit()

            url_id = new_url.id

        else:
            # If URL does already exist, check if associated with UTub
            url_id = already_created_url.id
            utub_url_if_already_exists = Utub_Urls.query.filter_by(
                utub_id=utub_id, url_id=url_id
            ).first()

            if utub_url_if_already_exists is not None:
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

        # Associate URL with given UTub
        url_utub_user_add = Utub_Urls(
            utub_id=utub_id,
            url_id=url_id,
            user_id=current_user.id,
            url_title=utub_new_url_form.url_title.data,
        )
        db.session.add(url_utub_user_add)
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
                    URL_SUCCESS.UTUB_NAME: utub.name,
                    URL_SUCCESS.ADDED_BY: current_user.id,
                    URL_SUCCESS.URL: {
                        URL_SUCCESS.URL_STRING: normalized_url,
                        URL_SUCCESS.URL_ID: url_id,
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


@urls.route("/utubs/<int:utub_id>/urls/<int:url_id>", methods=["PUT"])
@email_validation_required
def edit_url_and_title(utub_id: int, url_id: int):
    """
    Edits the URL contained in the UTub.
    If user makes no edits or produces the same URL, then no edits occur.

    If the user provides a different URL, then remove the old URL from URL-UTUB association table, and
    add in the new one.
        If the new URL does not exist in the URLS table, first add it there.
    """

    utub: Utub = Utub.query.get_or_404(utub_id)
    utub_owner_id = utub.utub_creator

    # Search through all urls in the UTub for the one that matches the prescribed
    # URL ID and get the user who added it - should be only one
    url_in_utub: Utub_Urls = Utub_Urls.query.filter(
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

    edit_url_form = EditURLAndTitleForm()

    if edit_url_form.validate_on_submit() and edit_url_form.url_title.data is not None:
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

        if url_to_change_to == url_in_utub.standalone_url.url_string:
            # Identical URL

            if url_title_to_change_to == url_in_utub.url_title:
                # Identical title
                return jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.NO_CHANGE,
                        STD_JSON.MESSAGE: URL_NO_CHANGE.URL_AND_TITLE_NOT_MODIFIED,
                        URL_SUCCESS.URL: serialized_url_in_utub,
                        URL_SUCCESS.UTUB_ID: utub.id,
                        URL_SUCCESS.UTUB_NAME: utub.name,
                    }
                )

            else:
                # Just change the title
                url_in_utub.url_title = url_title_to_change_to
                new_serialized_url = url_in_utub.serialized
                db.session.commit()

                return jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.SUCCESS,
                        STD_JSON.MESSAGE: URL_SUCCESS.URL_TITLE_MODIFIED,
                        URL_SUCCESS.URL: new_serialized_url,
                        URL_SUCCESS.UTUB_ID: utub.id,
                        URL_SUCCESS.UTUB_NAME: utub.name,
                    }
                )

        # Here the user wants to try to change or modify the URL
        try:
            normalized_url = find_common_url(url_to_change_to)
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
            title_diff: bool = url_title_to_change_to != url_in_utub.url_title
            if title_diff:
                # Just change the title
                url_in_utub.url_title = url_title_to_change_to
                serialized_url_in_utub = url_in_utub.serialized
                db.session.commit()

            return (
                jsonify(
                    {
                        STD_JSON.STATUS: (
                            STD_JSON.SUCCESS if title_diff else STD_JSON.NO_CHANGE
                        ),
                        STD_JSON.MESSAGE: (
                            URL_SUCCESS.URL_TITLE_MODIFIED
                            if title_diff
                            else URL_NO_CHANGE.URL_AND_TITLE_NOT_MODIFIED
                        ),
                        URL_SUCCESS.URL: serialized_url_in_utub,
                        URL_SUCCESS.UTUB_ID: utub.id,
                        URL_SUCCESS.UTUB_NAME: utub.name,
                    }
                ),
                200,
            )

        # Completely new URL. Now set the URL ID for the old URL to the new URL
        url_in_utub.url_id = url_in_database.id
        url_in_utub.standalone_url = url_in_database

        # Finally check and update the title
        if url_title_to_change_to != url_in_utub.url_title:
            url_in_utub.url_title = url_title_to_change_to

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
                    URL_SUCCESS.UTUB_ID: utub.id,
                    URL_SUCCESS.UTUB_NAME: utub.name,
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
                    STD_JSON.ERRORS: build_form_errors(edit_url_form),
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


@urls.route("/utubs/<int:utub_id>/urls/<int:url_id>", methods=["PATCH"])
@email_validation_required
def edit_url(utub_id: int, url_id: int):
    """
    Allows a user to edit a URL without editing the title.
    Only the user who added the URL, or who created the UTub containing
    the URL, can modify the URL.

    Args:
        utub_id (int): The UTub ID containing the relevant URL
        url_id (int): The URL ID to be modified
    """

    utub: Utub = Utub.query.get_or_404(utub_id)
    utub_owner_id = utub.utub_creator

    # Search through all urls in the UTub for the one that matches the prescribed
    # URL ID and get the user who added it - should be only one
    url_in_utub: Utub_Urls = Utub_Urls.query.filter(
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

    if edit_url_form.validate_on_submit():
        url_to_change_to: str = edit_url_form.url_string.data.replace(" ", "")

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

        serialized_url_in_utub = url_in_utub.serialized

        if url_to_change_to == url_in_utub.standalone_url.url_string:
            # Identical URL
            return jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.NO_CHANGE,
                    STD_JSON.MESSAGE: URL_NO_CHANGE.URL_NOT_MODIFIED,
                    URL_SUCCESS.UTUB_ID: utub.id,
                    URL_SUCCESS.UTUB_NAME: utub.name,
                    URL_SUCCESS.URL: serialized_url_in_utub,
                }
            )

        # Here the user wants to try to change or modify the URL
        try:
            normalized_url = find_common_url(url_to_change_to)
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
        url_already_in_database: URLS = URLS.query.filter_by(
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

        # Find tags associated with URL
        url_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_id, url_id=url_id
        ).all()

        for url_tag in url_tags:
            url_tag.url_id = url_in_database.id

        new_serialized_url = url_in_utub.serialized

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
    if edit_url_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
                    STD_JSON.ERROR_CODE: 4,
                    STD_JSON.ERRORS: build_form_errors(edit_url_form),
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
                STD_JSON.ERROR_CODE: 5,
            }
        ),
        404,
    )


@urls.route("/utubs/<int:utub_id>/urls/<int:url_id>/title", methods=["PATCH"])
@email_validation_required
def edit_url_title(utub_id: int, url_id: int):
    """
    Allows a user to edit a URL title without editing the url.
    Only the user who added the URL, or who created the UTub containing
    the URL, can modify the title.

    Args:
        utub_id (int): The UTub ID containing the relevant URL title
        url_id (int): The URL ID to have the title be modified
    """
    utub: Utub = Utub.query.get_or_404(utub_id)
    utub_owner_id = utub.utub_creator

    # Search through all urls in the UTub for the one that matches the prescribed
    # URL ID and get the user who added it - should be only one
    url_in_utub: Utub_Urls = Utub_Urls.query.filter(
        Utub_Urls.url_id == url_id, Utub_Urls.utub_id == utub_id
    ).first_or_404()

    if current_user.id != utub_owner_id and current_user.id != url_in_utub.user_id:
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

    edit_url_title_form = EditURLTitleForm()

    if edit_url_title_form.validate_on_submit():
        url_title_to_change_to = edit_url_title_form.url_title.data
        serialized_url_in_utub = url_in_utub.serialized
        title_diff = url_title_to_change_to != url_in_utub.url_title

        if title_diff:
            # Change the title
            url_in_utub.url_title = url_title_to_change_to
            serialized_url_in_utub = url_in_utub.serialized
            db.session.commit()

        return jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS if title_diff else STD_JSON.NO_CHANGE,
                STD_JSON.MESSAGE: (
                    URL_SUCCESS.URL_TITLE_MODIFIED
                    if title_diff
                    else URL_NO_CHANGE.URL_TITLE_NOT_MODIFIED
                ),
                URL_SUCCESS.UTUB_ID: utub.id,
                URL_SUCCESS.UTUB_NAME: utub.name,
                URL_SUCCESS.URL: serialized_url_in_utub,
            }
        )

    # Missing URL title field
    if edit_url_title_form.url_title.data is None:
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
    if edit_url_title_form.errors is not None:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
                    STD_JSON.ERROR_CODE: 3,
                    STD_JSON.ERRORS: build_form_errors(edit_url_title_form),
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
