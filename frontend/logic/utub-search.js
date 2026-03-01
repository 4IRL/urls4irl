/**
 * Pure logic for UTub name searching -- no DOM dependency.
 * DOM adapter lives in home/utubs/search.js.
 */

/**
 * Given an array of UTub objects and a search term, returns the IDs of UTubs
 * whose names do NOT contain the search term (i.e., IDs to hide).
 *
 * @param {{ id: number, name: string }[]} utubs
 * @param {string} searchTerm  Already lowercased by the caller
 * @returns {number[]}
 */
export function filterUTubsByName(utubs, searchTerm) {
  return utubs
    .filter((utub) => !utub.name.toLowerCase().includes(searchTerm))
    .map((utub) => utub.id);
}
