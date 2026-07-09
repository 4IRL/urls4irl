/**
 * Native fragment-swap helpers used by admin portal dynamic surfaces
 * (health, user search, audit log) to load server-rendered HTML fragments
 * via jQuery AJAX and swap them into target elements.
 *
 * All three exports are intentionally small and single-purpose so each admin
 * surface can import only what it needs.
 *
 *   fetchAndSwap({ url, targetEl, timeout? })
 *     GETs url and sets targetEl.innerHTML to the returned HTML string.
 *
 *   makeDebouncer(fn, delayMs)
 *     Returns a debounced wrapper of fn that delays execution by delayMs.
 *
 *   bindPaginationLinks({ containerEl, targetEl })
 *     Attaches a delegated click handler inside containerEl that intercepts
 *     clicks on [data-fragment-href] anchors and calls fetchAndSwap.
 *     Uses jQuery event delegation so it survives innerHTML replacements.
 */

import { $ } from "../lib/globals.js";
import { ajaxCallFragment, is429Handled } from "../lib/ajax.js";

const PAGINATION_LINK_SELECTOR = "[data-fragment-href]";
const PAGINATION_CLICK_NAMESPACE = "click.adminFragmentPagination";

/**
 * GET `url` and write the response HTML into `targetEl.innerHTML`.
 * Silent on non-429 failures — the region simply retains its previous content.
 */
export function fetchAndSwap({
  url,
  targetEl,
  timeout = 5_000,
}: {
  url: string;
  targetEl: HTMLElement;
  timeout?: number;
}): void {
  ajaxCallFragment(url, timeout)
    .done((html: string) => {
      targetEl.innerHTML = html;
    })
    .fail((xhr: JQuery.jqXHR) => {
      if (is429Handled(xhr)) return;
    });
}

/**
 * Returns a debounced wrapper of `fn`.  Repeated calls within `delayMs`
 * milliseconds reset the timer; `fn` fires only after the last call.
 */
export function makeDebouncer(fn: () => void, delayMs: number): () => void {
  let timer: ReturnType<typeof window.setTimeout> | undefined;
  return (): void => {
    window.clearTimeout(timer);
    timer = window.setTimeout(fn, delayMs);
  };
}

/**
 * Attach a delegated click handler to `containerEl` that intercepts clicks
 * on any descendant [data-fragment-href] anchor, prevents the default
 * navigation, and calls fetchAndSwap targeting `targetEl`.
 *
 * Uses jQuery event delegation so the handler survives innerHTML swaps that
 * replace the pagination links on each result load.
 */
export function bindPaginationLinks({
  containerEl,
  targetEl,
}: {
  containerEl: HTMLElement;
  targetEl: HTMLElement;
}): void {
  $(containerEl)
    .off(PAGINATION_CLICK_NAMESPACE)
    .on(
      PAGINATION_CLICK_NAMESPACE,
      PAGINATION_LINK_SELECTOR,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        const href = $(this).data("fragment-href") as string | undefined;
        if (!href) return;
        fetchAndSwap({ url: href, targetEl });
      },
    );
}
