import type { MemberItem } from "../../types/member.js";
import type { MemberSortValue } from "../../types/preferences.js";

import { APP_CONFIG } from "../../lib/config.js";
import { compareCodePoints, foldName } from "../../lib/name-order.js";

// Leaf module: imports only types, config and the shared name-order helpers.
// Mirrors the server's sort_members (backend/members/services/member_sort.py);
// the shared fixture tests/fixtures/member_sort_parity.json proves they agree.

type MemberComparator = (left: MemberItem, right: MemberItem) => number;

function compareNames({
  left,
  right,
}: {
  left: MemberItem;
  right: MemberItem;
}): number {
  return compareCodePoints({
    left: foldName(left.username),
    right: foldName(right.username),
  });
}

// Owner first, then co-creators, then members; an unknown role sorts after
// members. The owner never reaches this ranking.
function roleRank(memberRole: string): number {
  const roles = APP_CONFIG.constants.MEMBER_ROLES;
  if (memberRole === roles.CO_CREATOR) return 1;
  if (memberRole === roles.MEMBER) return 2;
  return 3;
}

// Millisecond precision only, like the server's truncate_to_milliseconds. A
// missing or unparseable date counts as dateless.
function joinedMillis(member: MemberItem): number | null {
  if (member.joinedAt === null || member.joinedAt === undefined) return null;
  const millis = new Date(member.joinedAt).getTime();
  return Number.isNaN(millis) ? null : millis;
}

function isOwner(member: MemberItem): boolean {
  return member.memberRole === APP_CONFIG.constants.MEMBER_ROLES.CREATOR;
}

function comparePrimary({
  left,
  right,
  memberSort,
}: {
  left: MemberItem;
  right: MemberItem;
  memberSort: MemberSortValue;
}): number {
  switch (memberSort) {
    case "role_then_name": {
      const byRole = roleRank(left.memberRole) - roleRank(right.memberRole);
      return byRole !== 0 ? byRole : compareNames({ left, right });
    }
    case "recently_joined": {
      const leftJoined = joinedMillis(left);
      const rightJoined = joinedMillis(right);
      if (leftJoined !== null && rightJoined !== null) {
        return rightJoined - leftJoined;
      }
      // Dated members first, then dateless ones by name.
      if (leftJoined !== null) return -1;
      if (rightJoined !== null) return 1;
      return compareNames({ left, right });
    }
    case "name_az":
    default:
      return compareNames({ left, right });
  }
}

// The owner is always first; ties break by user id ascending. An unknown sort
// falls back to name order.
export function compareMembers({
  memberSort,
}: {
  memberSort: MemberSortValue;
}): MemberComparator {
  // Array.prototype.sort's comparator contract is positional.
  // eslint-disable-next-line u4i/destructured-params
  return (left, right) => {
    const leftOwner = isOwner(left);
    const rightOwner = isOwner(right);
    if (leftOwner !== rightOwner) return leftOwner ? -1 : 1;
    const primary = leftOwner ? 0 : comparePrimary({ left, right, memberSort });
    return primary !== 0 ? primary : left.id - right.id;
  };
}
