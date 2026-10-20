from collections.abc import Set as AbstractSet


def can_act_as_url_adder(
    *,
    adder_id: int,
    user_id: int,
    is_manager: bool,
    member_ids: AbstractSet[int],
) -> bool:
    """Return whether ``user_id`` may act on a URL as its adder or as a manager.

    Orphan rule (#770): a URL whose adder is no longer a member of its UTub (left,
    removed or erased) can be acted on by any current member as if they had added it.
    Otherwise only the adder or a UTub manager may act on it.

    This module deliberately imports nothing from ``backend.models`` so the schema
    layer can import it. The SQL twin is ``adder_not_member_clause`` in
    ``backend.utubs.services.trash_predicates``.

    Args:
        adder_id: ID of the user recorded as the URL's adder (``Utub_Urls.user_id``).
        user_id: ID of the user attempting the action.
        is_manager: Whether ``user_id`` is the UTub's creator or a co-creator.
        member_ids: IDs of every current member of the URL's UTub.

    Returns:
        True when the action is allowed. Fails closed: False unless ``user_id`` is in
        ``member_ids``, so a caller that forgot to load members grants nothing.
    """
    if user_id not in member_ids:
        return False
    return is_manager or adder_id == user_id or adder_id not in member_ids
