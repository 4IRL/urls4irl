/**
 * Whole-row click convenience for admin list tables.
 *
 * Progressive enhancement only: each clickable row already carries a real,
 * keyboard-focusable `<a class="admin-db-row-link">` in its first cell (the
 * no-JS / screen-reader / keyboard fallback). This controller lets a mouse
 * user click anywhere else in the row to reach the same detail page, without
 * adding a second tab stop or altering row semantics.
 *
 * data-* contract on each clickable row:
 *   data-row-href   destination URL (from url_for in Jinja — never hardcoded)
 */

import { $ } from "../lib/globals.js";

const CLICK_NAMESPACE = "click.adminClickableRows";
const ROW_SELECTOR = ".admin-clickable-row";
const INTERACTIVE_SELECTOR = "a, button, input, select, textarea, label";

/**
 * Wire up whole-row navigation via a delegated document listener so rows in
 * server-swapped fragments are covered without rebinding. Returns immediately
 * when no clickable rows are present on the page.
 */
export function initClickableRows(): void {
  if (document.querySelector(ROW_SELECTOR) === null) return;

  $(document)
    .off(CLICK_NAMESPACE, ROW_SELECTOR)
    .on(CLICK_NAMESPACE, ROW_SELECTOR, function (event: JQuery.ClickEvent) {
      // Let native controls (the ID link, any future row buttons/inputs)
      // handle their own clicks.
      if (
        (event.target as HTMLElement).closest(INTERACTIVE_SELECTOR) !== null
      ) {
        return;
      }

      // Don't hijack a click that ends a text selection inside a cell.
      const activeSelection = window.getSelection()?.toString() ?? "";
      if (activeSelection !== "") return;

      const rowEl = event.currentTarget as HTMLElement;
      const rowHref = rowEl.dataset.rowHref;
      if (!rowHref) return;

      window.location.assign(rowHref);
    });
}
