/**
 * Pure logic for UTub name searching -- no DOM dependency.
 * DOM adapter lives in home/utubs/search.js.
 */

interface UtubSearchItem {
  id: number;
  name: string;
}

/**
 * Given an array of UTub objects and a search term, returns the IDs of UTubs
 * whose names do NOT contain the search term (i.e., IDs to hide).
 */
export function filterUTubsByName(
  utubs: UtubSearchItem[],
  searchTerm: string,
): number[] {
  return utubs
    .filter((utub) => !utub.name.toLowerCase().includes(searchTerm))
    .map((utub) => utub.id);
}
