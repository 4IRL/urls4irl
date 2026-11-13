from __future__ import annotations

from backend.api_common.responses import FlaskResponse
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.utub_settings import resolve_utub_settings
from backend.tags.constants import URLTagErrorCodes, UTubTagErrorCodes
from backend.urls.constants import URLErrorCodes
from backend.utils.strings.tag_strs import (
    TAG_CREATE_NOT_ALLOWED,
    TAG_DELETE_NOT_ALLOWED,
    TAG_REMOVE_NOT_ALLOWED,
    TAG_URLS_NOT_ALLOWED,
)


def can_tag(utub: Utubs, *, is_manager: bool) -> bool:
    """Single rule for who may create tags and add or remove tags on URLs.

    Managers (owner and co-owners) always may. A plain member may only while the
    ``members_can_tag`` switch resolves to exactly True.

    Args:
        utub (Utubs): The UTub whose settings are read.
        is_manager (bool): Whether the caller is a manager of the UTub.

    Returns:
        True when the caller may tag.
    """
    if is_manager:
        return True
    return resolve_utub_settings(utub.settings).tags.members_can_tag is True


def can_delete_tags(utub: Utubs, *, is_manager: bool) -> bool:
    """Single rule for who may delete a UTub tag.

    Managers always may. A plain member needs both ``members_can_tag`` and
    ``members_can_delete_tags`` to resolve to exactly True; the stored delete value
    is never rewritten when tagging is off.

    Args:
        utub (Utubs): The UTub whose settings are read.
        is_manager (bool): Whether the caller is a manager of the UTub.

    Returns:
        True when the caller may delete tags.
    """
    if is_manager:
        return True
    tags = resolve_utub_settings(utub.settings).tags
    return tags.members_can_tag is True and tags.members_can_delete_tags is True


def utub_tag_create_refusal_response(
    utub: Utubs, *, is_manager: bool
) -> FlaskResponse | None:
    """Return the 403 errorCode 4 response when the caller may not create tags, else None."""
    if can_tag(utub, is_manager=is_manager):
        return None
    return build_message_error_response(
        message=TAG_CREATE_NOT_ALLOWED,
        error_code=UTubTagErrorCodes.TAGGING_NOT_ALLOWED,
        status_code=403,
    )


def utub_tag_delete_refusal_response(
    utub: Utubs, *, is_manager: bool
) -> FlaskResponse | None:
    """Return the 403 response when the caller may not delete a UTub tag, else None.

    Tagging off yields errorCode 4; tagging on with deletion off yields errorCode 5.
    """
    if can_delete_tags(utub, is_manager=is_manager):
        return None
    error_code = (
        UTubTagErrorCodes.TAG_DELETE_NOT_ALLOWED
        if can_tag(utub, is_manager=is_manager)
        else UTubTagErrorCodes.TAGGING_NOT_ALLOWED
    )
    return build_message_error_response(
        message=TAG_DELETE_NOT_ALLOWED,
        error_code=error_code,
        status_code=403,
    )


def url_tag_add_refusal_response(
    utub: Utubs, *, is_manager: bool
) -> FlaskResponse | None:
    """Return the 403 URL-tag errorCode 4 response when the caller may not add tags to URLs, else None."""
    if can_tag(utub, is_manager=is_manager):
        return None
    return build_message_error_response(
        message=TAG_URLS_NOT_ALLOWED,
        error_code=URLTagErrorCodes.TAGGING_NOT_ALLOWED,
        status_code=403,
    )


def url_tag_remove_refusal_response(
    utub: Utubs, *, is_manager: bool
) -> FlaskResponse | None:
    """Return the 403 URL-tag errorCode 4 response when the caller may not remove tags from URLs, else None."""
    if can_tag(utub, is_manager=is_manager):
        return None
    return build_message_error_response(
        message=TAG_REMOVE_NOT_ALLOWED,
        error_code=URLTagErrorCodes.TAGGING_NOT_ALLOWED,
        status_code=403,
    )


def url_restore_preserved_tags_refusal_response(
    utub: Utubs, *, is_manager: bool, has_preserved_tags: bool
) -> FlaskResponse | None:
    """Return the 403 URL errorCode 18 response when a restore or revive would re-attach
    preserved tags but the caller may not tag, else None.

    A URL without preserved tags carries no tag write, so it is never refused.
    """
    if not has_preserved_tags:
        return None
    return url_create_tags_refusal_response(utub, is_manager=is_manager)


def url_create_tags_refusal_response(
    utub: Utubs, *, is_manager: bool
) -> FlaskResponse | None:
    """Return the 403 URL errorCode 18 response when the caller may not create a URL with tags, else None."""
    if can_tag(utub, is_manager=is_manager):
        return None
    return build_message_error_response(
        message=TAG_URLS_NOT_ALLOWED,
        error_code=URLErrorCodes.TAGGING_NOT_ALLOWED,
        status_code=403,
    )
