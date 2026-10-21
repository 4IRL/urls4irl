from collections.abc import Collection

from sqlalchemy import select

from backend import db
from backend.models.short_links import Short_Links
from backend.models.utub_urls import Utub_Urls


def delete_short_links_for_utub_urls(*, utub_url_ids: Collection[int]) -> None:
    """Hard-delete the share links of the given ``UtubUrls`` rows.

    Call this AFTER the ``Utub_Urls`` UPDATE that kills the links (trash, address
    edit) has been flushed: that UPDATE holds the row lock that serializes against a
    concurrent mint, so a mint can never insert a link after this delete. Does not
    commit; the caller owns the transaction.

    Args:
        utub_url_ids (Collection[int]): The ``UtubUrls`` ids whose links to delete.
    """
    if not utub_url_ids:
        return
    db.session.query(Short_Links).filter(
        Short_Links.utub_url_id.in_(utub_url_ids)
    ).delete(synchronize_session=False)


def delete_short_links_for_utub(*, utub_id: int) -> None:
    """Hard-delete the share links of every URL in a UTub.

    Call this AFTER the ``Utubs`` UPDATE that trashes the UTub has been flushed (see
    ``delete_short_links_for_utub_urls``). Does not commit.

    Args:
        utub_id (int): The UTub whose URLs' links to delete.
    """
    db.session.query(Short_Links).filter(
        Short_Links.utub_url_id.in_(
            select(Utub_Urls.id).where(Utub_Urls.utub_id == utub_id)
        )
    ).delete(synchronize_session=False)
