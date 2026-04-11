/**
 * Pure logic for URL tag filtering -- no DOM dependency.
 * DOM adapters live in home/urls/cards/filtering.js.
 */

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
 * visibility for each URL (true = all selected tags present on URL).
 */
export function computeURLVisibility(
  selectedTagIDs: number[],
  urlsWithTagIDs: UrlWithTagIDs[],
): UrlVisibility[] {
  return urlsWithTagIDs.map(({ urlId, tagIDs }) => ({
    urlId,
    visible: selectedTagIDs.every((id) => tagIDs.includes(id)),
  }));
}

/**
 * Given a list of tag-ID arrays (one per visible URL) and all tag IDs in
 * the deck, returns a Map of tagID (string) -> visible URL count.
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

/**
 * Given an array of tag objects with a `visibleCount` property, returns
 * a new array sorted descending by visibleCount.
 */
export function sortTagsByCount<T extends { visibleCount: number }>(
  tags: T[],
): T[] {
  return [...tags].sort((a, b) => b.visibleCount - a.visibleCount);
}
