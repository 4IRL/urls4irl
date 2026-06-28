/**
 * Pure logic for tag name filtering -- no DOM dependency.
 * DOM adapter lives in home/tags/search.js.
 */

interface TagSearchItem {
  id: number;
  name: string;
}

/**
 * Given an array of tag objects and a search term, returns the IDs of tags
 * whose names do NOT contain the search term (i.e., IDs to hide).
 */
export function filterTagsByName(
  tags: TagSearchItem[],
  searchTerm: string,
): number[] {
  return tags
    .filter((tag) => !tag.name.toLowerCase().includes(searchTerm))
    .map((tag) => tag.id);
}
