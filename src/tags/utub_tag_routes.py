from flask import Blueprint, jsonify
from flask_login import current_user

from src import db
from src.app_logger import (
    critical_log,
    error_log,
    safe_add_many_logs,
    turn_form_into_str_for_log,
    warning_log,
)
from src.models.utub_tags import Utub_Tags
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_url_tags import Utub_Url_Tags
from src.tags.forms import NewTagForm
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.model_strs import MODELS
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS
from src.utils.email_validation import email_validation_required

utub_tags = Blueprint("utub_tags", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@utub_tags.route("/utubs/<int:utub_id>/tags", methods=["POST"])
@email_validation_required
def create_utub_tag(utub_id: int):
    """
    User wants to add a tag to a UTub.

    Args:
        utub_id (int): The utub that this user is being added to
    """
    utub: Utubs = Utubs.query.get_or_404(utub_id)
    user_in_utub = Utub_Members.query.get((utub_id, current_user.id)) is not None

    if not user_in_utub:
        # How did a user not in this utub get access to add a tag to this UTub?
        error_log(
            f"User={current_user.id} tried adding UTubTag to UTub.id={utub_id} but user not in UTub"
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            403,
        )

    utub_tag_form: NewTagForm = NewTagForm()

    if utub_tag_form.validate_on_submit():
        tag_to_add = utub_tag_form.tag_string.data

        # Check if tag already exists in UTub
        utub_tag_already_created: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_id, Utub_Tags.tag_string == tag_to_add
        ).first()

        if utub_tag_already_created:
            warning_log(
                f"User={current_user.id} tried adding UTubTag.tag_string={tag_to_add} but UTubTag already exists in UTub.id={utub_id}"
            )
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: TAGS_FAILURE.TAG_ALREADY_IN_UTUB,
                        STD_JSON.ERROR_CODE: 2,
                    }
                ),
                400,
            )

        # Create tag, then associate with this UTub
        new_utub_tag = Utub_Tags(
            utub_id=utub_id, tag_string=tag_to_add, created_by=current_user.id
        )
        db.session.add(new_utub_tag)
        utub.set_last_updated()
        db.session.commit()

        # Successfully added tag to UTub
        safe_add_many_logs(
            [
                "Added UTubTag",
                f"UTub.id={utub_id}",
                f"UTubTag.id={new_utub_tag.id}",
                f"UTubTag.tag_string={tag_to_add}",
            ]
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: TAGS_SUCCESS.TAG_ADDED_TO_UTUB,
                    TAGS_SUCCESS.UTUB_TAG: new_utub_tag.serialized_on_add_delete,
                }
            ),
            200,
        )

    # Input form errors
    if utub_tag_form.errors is not None:
        errors = {MODELS.TAG_STRING: utub_tag_form.tag_string.errors}
        warning_log(
            f"User={current_user.id} | Invalid form: {turn_form_into_str_for_log(utub_tag_form.errors)}"  # type: ignore
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
                    STD_JSON.ERROR_CODE: 3,
                    STD_JSON.ERRORS: errors,
                }
            ),
            400,
        )

    critical_log(f"User={current_user.id} failed to add UTubTag to UTub.id={utub_id}")
    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_UTUB,
                STD_JSON.ERROR_CODE: 4,
            }
        ),
        404,
    )


@utub_tags.route(
    "/utubs/<int:utub_id>/tags/<int:utub_tag_id>",
    methods=["DELETE"],
)
@email_validation_required
def delete_utub_tag(utub_id: int, utub_tag_id: int):
    """
    User wants to delete a tag from a UTub. This will remove all instances of this tag
    associated with URLs (Utub_Url_Tags) in this UTub.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be deleted
        utub_tag_id (int): The ID of the tag to be deleted
    """
    utub: Utubs = Utubs.query.get_or_404(utub_id)
    user_in_utub = Utub_Members.query.get((utub_id, current_user.id)) is not None

    if not user_in_utub:
        critical_log(
            f"User={current_user.id} tried removing UTubTag.id={utub_tag_id} but user not in UTub.id={utub_id}"
        )
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.ONLY_UTUB_MEMBERS_DELETE_TAGS,
                }
            ),
            403,
        )

    utub_tag: Utub_Tags = Utub_Tags.query.get_or_404(utub_tag_id)

    utub_url_ids_with_utub_tag: list[int] = [
        id_tuple[0]
        for id_tuple in db.session.query(Utub_Url_Tags.utub_url_id)
        .filter(
            Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_tag_id == utub_tag_id
        )
        .all()
    ]

    serialized_tag = utub_tag.serialized_on_add_delete

    db.session.delete(utub_tag)
    utub.set_last_updated()
    db.session.commit()
    safe_add_many_logs(
        [
            "Deleted UTubTag",
            f"UTub.id={utub_id}",
            f"UTubTag.id={utub_tag_id}",
            f"UTubTag.tag_string={serialized_tag[MODELS.TAG_STRING]}",
        ]
    )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: TAGS_SUCCESS.TAG_REMOVED_FROM_UTUB,
                TAGS_SUCCESS.UTUB_TAG: serialized_tag,
                TAGS_SUCCESS.UTUB_URL_IDS: utub_url_ids_with_utub_tag,
            }
        ),
        200,
    )
