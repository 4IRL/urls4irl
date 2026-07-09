/**
 * Audit-log filter controller for the admin /admin/audit-log page.
 *
 * Fetches the server-rendered audit-log rows fragment and swaps it into
 * #AdminAuditLogResults using native jQuery AJAX (via fetchAndSwap):
 *   - immediate fetch on init
 *   - 500 ms-debounced fetch on `input` events (text keystrokes)
 *   - 100 ms-debounced fetch on `change` events (date-picker selections)
 *   - form submit is prevented and triggers an immediate fetch
 *   - delegated pagination-link clicks via bindPaginationLinks
 *
 * The filter URL is read from the `data-filter-url` attribute on the form
 * element (set by the Jinja template via url_for).
 */

import { $ } from "../lib/globals.js";
import {
  bindPaginationLinks,
  fetchAndSwap,
  makeDebouncer,
} from "./fragment-swap.js";

const FILTERS_FORM_ID = "AdminAuditLogFilters";
const RESULTS_ID = "AdminAuditLogResults";
const INPUT_NAMESPACE = "input.adminAuditLog";
const CHANGE_NAMESPACE = "change.adminAuditLog";
const SUBMIT_NAMESPACE = "submit.adminAuditLog";

/**
 * Wire up audit-log filters on the admin audit-log page.  Returns immediately
 * if the required DOM elements are absent (i.e. the page is not
 * /admin/audit-log).
 */
export function initAuditLog(): void {
  const filtersForm = document.getElementById(
    FILTERS_FORM_ID,
  ) as HTMLFormElement | null;
  const resultsEl = document.getElementById(RESULTS_ID);
  if (filtersForm === null || resultsEl === null) return;

  const filterUrl = filtersForm.dataset.filterUrl;
  if (!filterUrl) return;

  const doFilter = (): void => {
    const params = $(filtersForm).serialize();
    fetchAndSwap({ url: `${filterUrl}?${params}`, targetEl: resultsEl });
  };

  const debouncedInput = makeDebouncer(doFilter, 500);
  const debouncedChange = makeDebouncer(doFilter, 100);

  $(filtersForm)
    .offAndOnExact(INPUT_NAMESPACE, debouncedInput)
    .offAndOnExact(CHANGE_NAMESPACE, debouncedChange)
    .offAndOnExact(SUBMIT_NAMESPACE, (event: JQuery.TriggeredEvent) => {
      event.preventDefault();
      doFilter();
    });

  bindPaginationLinks({ containerEl: resultsEl, targetEl: resultsEl });

  doFilter();
}
