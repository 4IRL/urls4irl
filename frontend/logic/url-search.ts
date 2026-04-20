/**
 * Pure logic for URL search filtering -- no DOM dependency.
 * DOM adapter lives in home/urls/search.ts.
 */

interface URLSearchItem {
  id: number;
  title: string;
  urlString: string;
}

/**
 * Given an array of URL objects and a search term, returns the IDs of URLs
 * whose title AND urlString both do NOT contain the search term (i.e., IDs to hide).
 * Lowercases the search term internally to prevent case-sensitivity bugs.
 */
export function filterURLsBySearchTerm(
  urls: URLSearchItem[],
  searchTerm: string,
): number[] {
  if (searchTerm === "") {
    return [];
  }

  const normalizedSearchTerm = searchTerm.toLowerCase();

  return urls
    .filter(
      (url) =>
        !url.title.toLowerCase().includes(normalizedSearchTerm) &&
        !url.urlString.toLowerCase().includes(normalizedSearchTerm),
    )
    .map((url) => url.id);
}
