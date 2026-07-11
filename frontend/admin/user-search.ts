/**
 * User search controller for the admin /admin/users page.
 *
 * Fetches the server-rendered user search results fragment and swaps it
 * into #AdminUserSearchResults using native jQuery AJAX (via fetchAndSwap):
 *   - immediate fetch on init
 *   - 500 ms-debounced fetch on every `input` event (keystroke)
 *   - immediate fetch on the `search` event (Enter key / clear-X button)
 *   - delegated pagination-link clicks via bindPaginationLinks
 *
 * The search URL is read from the `data-search-url` attribute on the input
 * element (set by the Jinja template via url_for).
 */

import { $ } from "../lib/globals.js";
import {
  bindPaginationLinks,
  fetchAndSwap,
  makeDebouncer,
} from "./fragment-swap.js";

const SEARCH_INPUT_ID = "AdminUserSearchInput";
const SEARCH_RESULTS_ID = "AdminUserSearchResults";
const INPUT_NAMESPACE = "input.adminUserSearch";
const SEARCH_NAMESPACE = "search.adminUserSearch";

/**
 * Wire up user-search on the admin users page.  Returns immediately if
 * the required DOM elements are absent (i.e. the page is not /admin/users).
 */
export function initUserSearch(): void {
  const searchInput = document.getElementById(
    SEARCH_INPUT_ID,
  ) as HTMLInputElement | null;
  const resultsEl = document.getElementById(SEARCH_RESULTS_ID);
  if (searchInput === null || resultsEl === null) return;

  const searchUrl = searchInput.dataset.searchUrl;
  if (!searchUrl) return;

  const doSearch = (): void => {
    const query = searchInput.value;
    fetchAndSwap({
      url: `${searchUrl}?q=${encodeURIComponent(query)}`,
      targetEl: resultsEl,
    });
  };

  const debouncedSearch = makeDebouncer(doSearch, 500);

  $(searchInput)
    .offAndOnExact(INPUT_NAMESPACE, debouncedSearch)
    .offAndOnExact(SEARCH_NAMESPACE, doSearch);

  bindPaginationLinks({ containerEl: resultsEl, targetEl: resultsEl });

  doSearch();
}
