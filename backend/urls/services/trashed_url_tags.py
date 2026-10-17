from collections.abc import Iterable

from backend.models.utub_tags import Utub_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.strings.model_strs import MODELS


def build_tag_name_snapshot_from_ids(tag_ids: Iterable[int]) -> dict[str, str]:
    """
    Look up the tag strings for tag ids about to be snapshotted into ``trashed_tag_ids``.

    Args:
        tag_ids (Iterable[int]): The Utub_Tags ids the trashed URL carries

    Returns:
        (dict[str, str]): ``{str(tag_id): tag_string}`` for every id that still exists.
        Keys are strings because the value is stored as JSONB.
    """
    unique_tag_ids: set[int] = set(tag_ids)
    if not unique_tag_ids:
        return {}
    named_tags: list[Utub_Tags] = Utub_Tags.query.filter(
        Utub_Tags.id.in_(unique_tag_ids)
    ).all()
    return {str(named_tag.id): named_tag.tag_string for named_tag in named_tags}


def build_tag_name_snapshot(utub_url: Utub_Urls) -> dict[str, str]:
    """
    Read the tag strings of a live URL's current associations, for the bulk trash
    path that already has each row's association relationship loaded.

    Args:
        utub_url (Utub_Urls): The row about to be trashed

    Returns:
        (dict[str, str]): ``{str(tag_id): tag_string}`` for the row's tags in its UTub
    """
    return {
        str(tag[MODELS.UTUB_TAG_ID]): str(tag[MODELS.TAG_STRING])
        for tag in utub_url.associated_tags
    }


def _lost_trashed_tag_ids(utub_url: Utub_Urls) -> set[int]:
    snapshot_tag_ids: set[int] = set(utub_url.trashed_tag_ids or [])
    surviving_tag_ids: set[int] = set(utub_url.associated_tag_ids)
    return snapshot_tag_ids - surviving_tag_ids


def count_lost_trashed_tags(utub_url: Utub_Urls) -> int:
    """
    Count how many tags a trashed URL lost while it sat in the trash.

    Deleting a UTub tag cascades to its `Utub_Url_Tags` rows, trashed URLs included, so a
    trashed URL's live associations can shrink after its `trashed_tag_ids` snapshot was taken.
    The lost tags are the snapshot ids that no longer have an association row.

    Used by the revive flows (re-adding a trashed URL, and editing a card's link to one) and by
    the restore flow (restoring a trashed URL from the Trash).

    Args:
        utub_url (Utub_Urls): The trashed row, with its snapshot in `trashed_tag_ids`

    Returns:
        (int): Snapshot tag ids that are no longer associated with the row. 0 when there is no snapshot.
    """
    return len(_lost_trashed_tag_ids(utub_url))


def list_lost_trashed_tag_names(utub_url: Utub_Urls) -> list[str]:
    """
    Name the tags a trashed URL lost while it sat in the trash.

    The lost ids are the same ones `count_lost_trashed_tags` counts, mapped through the
    `trashed_tag_names` snapshot. A row trashed before that snapshot existed has no names,
    so this returns [] for it even though the count is still correct.

    Args:
        utub_url (Utub_Urls): The trashed row, with its snapshots in `trashed_tag_ids`
            and `trashed_tag_names`

    Returns:
        (list[str]): Lost tag strings, sorted alphabetically (case-insensitive, then by
        exact string). Lost ids with no saved name are omitted.
    """
    saved_names: dict[str, str] = utub_url.trashed_tag_names or {}
    lost_names: list[str] = [
        saved_names[str(lost_tag_id)]
        for lost_tag_id in _lost_trashed_tag_ids(utub_url)
        if str(lost_tag_id) in saved_names
    ]
    return sorted(lost_names, key=lambda tag_string: (tag_string.lower(), tag_string))
