from flask import abort, Blueprint, jsonify
from flask_login import current_user

from src import db
from src.models.utub_tags import Utub_Tags
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls
from src.models.utub_url_tags import Utub_Url_Tags
from src.tags.forms import NewTagForm
from src.utils.constants import TAG_CONSTANTS
from src.utils.strings.json_strs import STD_JSON_RESPONSE
from src.utils.strings.model_strs import MODELS
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS
from src.utils.email_validation import email_validation_required

utub_url_tags = Blueprint("utub_url_tags", __name__)

# Standard response for JSON messages
STD_JSON = STD_JSON_RESPONSE


@utub_url_tags.route(
    "/utubs/<int:utub_id>/urls/<int:utub_url_id>/tags", methods=["POST"]
)
@email_validation_required
def create_utub_url_tag(utub_id: int, utub_url_id: int):
    """
    User wants to add a tag to a URL. 5 tags per URL.
    # TODO: Do not allow empty tags

    Args:
        utub_id (int): The utub that this user is being added to
        url_id (int): The URL this user wants to add a tag to
    """
    utub_url_association: Utub_Urls = Utub_Urls.query.get_or_404(utub_url_id)
    if utub_url_association.utub_id != utub_id:
        abort(404)

    utub: Utubs = utub_url_association.utub
    user_in_utub = Utub_Members.query.get((utub_id, current_user.id)) is not None

    if not user_in_utub:
        # How did a user not in this utub get access to add a tag to this URL?
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
                    STD_JSON.ERROR_CODE: 1,
                }
            ),
            403,
        )

    url_tag_form: NewTagForm = NewTagForm()

    if url_tag_form.validate_on_submit():
        tag_to_add = url_tag_form.tag_string.data

        tags_already_on_this_url: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub.id, Utub_Url_Tags.utub_url_id == utub_url_id
        ).all()

        if len(tags_already_on_this_url) >= TAG_CONSTANTS.MAX_URL_TAGS:
            # Cannot have more than 5 tags on a URL
            return (
                jsonify(
                    {
                        STD_JSON.STATUS: STD_JSON.FAILURE,
                        STD_JSON.MESSAGE: TAGS_FAILURE.FIVE_TAGS_MAX,
                        STD_JSON.ERROR_CODE: 2,
                    }
                ),
                400,
            )

        # Check if tag already exists in UTub
        utub_tag_already_created: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_id, Utub_Tags.tag_string == tag_to_add
        ).first()

        if utub_tag_already_created:
            # Check if tag already on url
            this_tag_is_already_on_this_url = utub_tag_already_created.id in [
                tags.utub_tag_id for tags in tags_already_on_this_url
            ]

            if this_tag_is_already_on_this_url:
                return (
                    jsonify(
                        {
                            STD_JSON.STATUS: STD_JSON.FAILURE,
                            STD_JSON.MESSAGE: TAGS_FAILURE.TAG_ALREADY_ON_URL,
                            STD_JSON.ERROR_CODE: 3,
                        }
                    ),
                    400,
                )

            # Associate with the UTub and URL
            utub_url_tag = Utub_Url_Tags(
                utub_id=utub_id,
                utub_url_id=utub_url_id,
                utub_tag_id=utub_tag_already_created.id,
            )
            tag_model = utub_tag_already_created

        else:
            # Create tag, then associate with this UTub and URL
            new_utub_tag = Utub_Tags(
                utub_id=utub_id, tag_string=tag_to_add, created_by=current_user.id
            )
            db.session.add(new_utub_tag)
            db.session.commit()
            utub_url_tag = Utub_Url_Tags(
                utub_id=utub_id, utub_url_id=utub_url_id, utub_tag_id=new_utub_tag.id
            )
            tag_model = new_utub_tag

        db.session.add(utub_url_tag)
        utub.set_last_updated()
        db.session.commit()

        # Successfully added tag to URL on UTub
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.SUCCESS,
                    STD_JSON.MESSAGE: TAGS_SUCCESS.TAG_ADDED_TO_URL,
                    TAGS_SUCCESS.UTUB_URL_TAG_IDS: utub_url_association.associated_tag_ids,
                    TAGS_SUCCESS.UTUB_TAG: tag_model.serialized_on_add_delete,
                }
            ),
            200,
        )

    # Input form errors
    if url_tag_form.errors is not None:
        errors = {MODELS.TAG_STRING: url_tag_form.tag_string.errors}
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
                    STD_JSON.ERROR_CODE: 4,
                    STD_JSON.ERRORS: errors,
                }
            ),
            400,
        )

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.FAILURE,
                STD_JSON.MESSAGE: TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
                STD_JSON.ERROR_CODE: 5,
            }
        ),
        404,
    )


@utub_url_tags.route(
    "/utubs/<int:utub_id>/urls/<int:utub_url_id>/tags/<int:utub_url_tag_id>",
    methods=["DELETE"],
)
@email_validation_required
def delete_utub_url_tag(utub_id: int, utub_url_id: int, utub_url_tag_id: int):
    """
    User wants to delete a tag from a URL contained in a UTub.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be deleted
        url_id (int): The ID of the URL containing tag to be deleted
        utub_url_tag_id (int): The ID of the tag to be deleted
    """
    utub: Utubs = Utubs.query.get_or_404(utub_id)
    user_in_utub = Utub_Members.query.get((utub_id, current_user.id)) is not None

    if not user_in_utub:
        return (
            jsonify(
                {
                    STD_JSON.STATUS: STD_JSON.FAILURE,
                    STD_JSON.MESSAGE: TAGS_FAILURE.ONLY_UTUB_MEMBERS_DELETE_TAGS,
                }
            ),
            403,
        )

    # User is member of this UTub
    tag_for_url_in_utub: Utub_Url_Tags = Utub_Url_Tags.query.filter(
        Utub_Url_Tags.utub_id == utub_id,
        Utub_Url_Tags.utub_url_id == utub_url_id,
        Utub_Url_Tags.utub_tag_id == utub_url_tag_id,
    ).first_or_404()
    url_id_to_remove_tag = tag_for_url_in_utub.utub_url_id
    tag_to_remove: Utub_Tags = tag_for_url_in_utub.utub_tag_item

    db.session.delete(tag_for_url_in_utub)
    utub.set_last_updated()
    db.session.commit()

    url_utub_association: Utub_Urls = Utub_Urls.query.get_or_404(url_id_to_remove_tag)

    return (
        jsonify(
            {
                STD_JSON.STATUS: STD_JSON.SUCCESS,
                STD_JSON.MESSAGE: TAGS_SUCCESS.TAG_REMOVED_FROM_URL,
                TAGS_SUCCESS.UTUB_URL_TAG_IDS: url_utub_association.associated_tag_ids,
                TAGS_SUCCESS.UTUB_TAG: tag_to_remove.serialized_on_add_delete,
            }
        ),
        200,
    )
