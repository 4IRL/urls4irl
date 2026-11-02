from backend.models.user_preferences import MemberSort
from backend.models.utub_members import Member_Role, Utub_Members
from backend.utils.datetime_utils import truncate_to_milliseconds


def sort_members(
    memberships: list[Utub_Members], member_sort: MemberSort
) -> list[Utub_Members]:
    """Order a UTub's members by the viewer's chosen sort, owner always first.

    Sorts by user id first and then stable-sorts on the key, so exact ties break
    by id. Join dates are millisecond-truncated first so rows differing only below
    1 ms tie exactly as they do in the browser. An unhandled sort raises.
    """
    by_id = sorted(memberships, key=lambda membership: membership.user_id)

    def name_key(membership: Utub_Members) -> str:
        return membership.to_user.username.casefold()

    def is_owner(membership: Utub_Members) -> bool:
        return membership.member_role == Member_Role.CREATOR

    owners = [membership for membership in by_id if is_owner(membership)]
    others = [membership for membership in by_id if not is_owner(membership)]

    if member_sort == MemberSort.NAME_AZ:
        ordered = sorted(others, key=name_key)
    elif member_sort == MemberSort.ROLE_THEN_NAME:
        ordered = sorted(
            others,
            key=lambda membership: (
                0 if membership.member_role == Member_Role.CO_CREATOR else 1,
                name_key(membership),
            ),
        )
    elif member_sort == MemberSort.RECENTLY_JOINED:
        dated = [
            (membership, truncate_to_milliseconds(membership.joined_at))
            for membership in others
            if membership.joined_at is not None
        ]
        dateless = [membership for membership in others if membership.joined_at is None]
        ordered = [
            membership
            for membership, _ in sorted(dated, key=lambda pair: pair[1], reverse=True)
        ] + sorted(dateless, key=name_key)
    else:
        raise ValueError(f"Unhandled member sort: {member_sort!r}")
    return owners + ordered
