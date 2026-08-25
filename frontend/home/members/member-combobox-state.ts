import { getState } from "../../store/app-store.js";

import type { MemberCandidate } from "../../types/member.js";

/**
 * Returns the co-member candidates whose username matches the query
 * (case-insensitive substring), excluding anyone already a current member of
 * the target UTub or already staged as a chip. Usernames are case-sensitive on
 * the backend, so the member/staged exclusions are exact (case-sensitive)
 * equality — only the substring match itself is case-insensitive. An empty or
 * whitespace-only query yields no suggestions (filter-only behavior).
 */
export function filterCoMemberSuggestions({
  query,
  currentMemberUsernames,
  stagedUsernames,
}: {
  query: string;
  currentMemberUsernames: string[];
  stagedUsernames: string[];
}): MemberCandidate[] {
  const normalizedQuery = query.trim().toLowerCase();
  if (normalizedQuery.length === 0) return [];

  const currentMemberSet = new Set(currentMemberUsernames);
  const stagedSet = new Set(stagedUsernames);

  return getState().coMemberCandidates.filter((candidate) => {
    if (currentMemberSet.has(candidate.username)) return false;
    if (stagedSet.has(candidate.username)) return false;
    return candidate.username.toLowerCase().includes(normalizedQuery);
  });
}

/**
 * True when the trimmed query exactly matches a co-member candidate username,
 * compared case-SENSITIVELY (usernames are case-sensitive on the backend).
 * Drives whether the dashed-amber outsider fallback row is suppressed.
 */
export function hasExactCoMemberMatch({ query }: { query: string }): boolean {
  const trimmedQuery = query.trim();
  if (trimmedQuery.length === 0) return false;
  return getState().coMemberCandidates.some(
    (candidate) => candidate.username === trimmedQuery,
  );
}
