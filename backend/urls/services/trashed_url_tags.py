from backend.models.utub_urls import Utub_Urls


def count_lost_trashed_tags(utub_url: Utub_Urls) -> int:
    """
    Count how many tags a trashed URL lost while it sat in the trash.

    Deleting a UTub tag cascades to its `Utub_Url_Tags` rows, trashed URLs included, so a
    trashed URL's live associations can shrink after its `trashed_tag_ids` snapshot was taken.
    The lost tags are the snapshot ids that no longer have an association row.

    Used by the revive-on-readd flow, and by the restore flow that follows it.

    Args:
        utub_url (Utub_Urls): The trashed row, with its snapshot in `trashed_tag_ids`

    Returns:
        (int): Snapshot tag ids that are no longer associated with the row. 0 when there is no snapshot.
    """
    snapshot_tag_ids: set[int] = set(utub_url.trashed_tag_ids or [])
    surviving_tag_ids: set[int] = set(utub_url.associated_tag_ids)
    return len(snapshot_tag_ids - surviving_tag_ids)
