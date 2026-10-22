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


def can_revoke_short_link(
    *,
    adder_id: int,
    minter_id: int | None,
    user_id: int,
    is_manager: bool,
    member_ids: AbstractSet[int],
) -> bool:
    """Return whether ``user_id`` may revoke a URL's share short link.

    Allowed for anyone who may act as the URL's adder (``can_act_as_url_adder``: the
    adder, a UTub manager, or any member once the adder has left) or for the member
    who minted the link. The minter arm requires current membership, so a minter who
    has left the UTub cannot revoke.

    Args:
        adder_id: ID of the user recorded as the URL's adder.
        minter_id: ID of the user who minted the link, or None if that user was deleted.
        user_id: ID of the user attempting to revoke.
        is_manager: Whether ``user_id`` is the UTub's creator or a co-creator.
        member_ids: IDs of every current member of the URL's UTub.

    Returns:
        True when revoking is allowed. Fails closed: any other case is False.
    """
    if can_act_as_url_adder(
        adder_id=adder_id,
        user_id=user_id,
        is_manager=is_manager,
        member_ids=member_ids,
    ):
        return True
    return minter_id is not None and minter_id == user_id and user_id in member_ids
