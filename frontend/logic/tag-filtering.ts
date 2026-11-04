/**
 * Pure logic for URL tag filtering -- no DOM dependency.
 * DOM adapters live in home/urls/cards/filtering.js.
 */

import type { TagMatchModeValue, TagSortValue } from "../types/preferences.js";

interface UrlWithTagIDs {
  urlId: number;
  tagIDs: number[];
}

interface UrlVisibility {
  urlId: number;
  visible: boolean;
}

/**
 * Given selected tag IDs and a list of URL-to-tag mappings, returns
 * visibility for each URL. Mode "all" shows a URL carrying every selected tag,
 * "any" shows one carrying at least one. An empty selection shows every URL in
 * both modes.
 */
export function computeURLVisibility({
  selectedTagIDs,
  urlsWithTagIDs,
  mode,
}: {
  selectedTagIDs: number[];
  urlsWithTagIDs: UrlWithTagIDs[];
  mode: TagMatchModeValue;
}): UrlVisibility[] {
  return urlsWithTagIDs.map(({ urlId, tagIDs }) => {
    if (selectedTagIDs.length === 0) return { urlId, visible: true };
    const matches = (id: number): boolean => tagIDs.includes(id);
    return {
      urlId,
      visible:
        mode === "any"
          ? selectedTagIDs.some(matches)
          : selectedTagIDs.every(matches),
    };
  });
}

/**
 * Given a list of tag-ID arrays (one per visible URL) and all tag IDs in
 * the deck, returns a Map of tagID (string) -> visible URL count.
 *
 * TODO: `visibleURLTagIDsList` uses `string[][]` and `allTagIDs` uses `number[]`
 * because the caller splits raw DOM attribute strings. Once the call site is
 * migrated to pass typed `number[][]` / `number[]` uniformly, these parameter
 * and return types can be tightened to use numeric IDs throughout.
 */
export function computeVisibleTagCounts(
  visibleURLTagIDsList: string[][],
  allTagIDs: number[],
): Map<string, number> {
  const tagIDsMap = new Map<string, number>();
  allTagIDs.forEach((tagID) => tagIDsMap.set(`${tagID}`, 0));

  visibleURLTagIDsList.forEach((tagIDs) => {
    tagIDs.forEach((tagID) => {
      tagIDsMap.set(tagID, (tagIDsMap.get(tagID) || 0) + 1);
    });
  });

  return tagIDsMap;
}

export interface SortableTag {
  id: number;
  name: string;
  /** UTub-wide number of URLs carrying the tag. */
  total: number;
  /** Number of currently visible URLs carrying the tag. */
  inView: number;
}

/**
 * Comparator for the tag deck sorts. Every order breaks ties by casefolded name
 * and then by id, so the result never depends on the input order.
 * "most_used" is the total count; "newest"/"oldest" follow the tag id.
 * (The default "most_in_view" order in the DOM keeps `sortTagsByCount`'s stable,
 * tie-break-free sort; the "most_in_view" branch here is for completeness.)
 */
export function compareTags({
  left,
  right,
  sort,
}: {
  left: SortableTag;
  right: SortableTag;
  sort: TagSortValue;
}): number {
  let primary = 0;
  switch (sort) {
    case "most_in_view":
      primary = right.inView - left.inView;
      break;
    case "most_used":
      primary = right.total - left.total;
      break;
    case "newest":
      return right.id - left.id;
    case "oldest":
      return left.id - right.id;
    default:
      break;
  }
  if (primary !== 0) return primary;
  const byName = left.name
    .toLowerCase()
    .localeCompare(right.name.toLowerCase());
  if (byName !== 0) return byName;
  return left.id - right.id;
}

/**
 * Given an array of tag objects with a `visibleCount` property, returns
 * a new array sorted descending by visibleCount.
 */
export function sortTagsByCount<CountedTag extends { visibleCount: number }>(
  tags: CountedTag[],
): CountedTag[] {
  return [...tags].sort(
    (left, right) => right.visibleCount - left.visibleCount,
  );
}
