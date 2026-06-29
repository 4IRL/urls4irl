/**
 * Pure logic for member name searching -- no DOM dependency.
 * DOM adapter lives in home/members/search.js.
 */

interface MemberSearchItem {
  id: number;
  name: string;
}

/**
 * Given an array of member objects and a search term, returns the IDs of
 * members whose names do NOT contain the search term (i.e., IDs to hide).
 */
export function filterMembersByName(
  members: MemberSearchItem[],
  searchTerm: string,
): number[] {
  return members
    .filter((member) => !member.name.toLowerCase().includes(searchTerm))
    .map((member) => member.id);
}
