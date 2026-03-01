/**
 * Pure logic for URL tag filtering -- no DOM dependency.
 * DOM adapters live in home/urls/cards/filtering.js.
 */

/**
 * Given selected tag IDs and a list of URL-to-tag mappings, returns
 * visibility for each URL (true = all selected tags present on URL).
 *
 * @param {number[]} selectedTagIDs
 * @param {{ urlId: number, tagIDs: number[] }[]} urlsWithTagIDs
 * @returns {{ urlId: number, visible: boolean }[]}
 */
export function computeURLVisibility(selectedTagIDs, urlsWithTagIDs) {
  return urlsWithTagIDs.map(({ urlId, tagIDs }) => ({
    urlId,
    visible: selectedTagIDs.every((id) => tagIDs.includes(id)),
  }));
}

/**
 * Given a list of tag-ID arrays (one per visible URL) and all tag IDs in
 * the deck, returns a Map of tagID (string) -> visible URL count.
 *
 * @param {string[][]} visibleURLTagIDsList  Array of comma-split tag ID arrays
 * @param {number[]} allTagIDs
 * @returns {Map<string, number>}
 */
export function computeVisibleTagCounts(visibleURLTagIDsList, allTagIDs) {
  const tagIDsMap = new Map();
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
 *
 * @param {{ visibleCount: number }[]} tags
 * @returns {{ visibleCount: number }[]}
 */
export function sortTagsByCount(tags) {
  return [...tags].sort((a, b) => b.visibleCount - a.visibleCount);
}
