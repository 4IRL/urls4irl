import { $ } from "../../../lib/globals.js";
import type { ViewModeValue } from "../../../types/preferences.js";
import { effectiveRenderedViewMode } from "../view-settings.js";
import { WIDE_VIEWPORT_QUERY } from "../view-mode.js";
import { debug } from "../../../lib/debug.js";

const log = debug("urls:cards");

// Views whose unselected rows truncate or clamp text. List never sets a tooltip.
const TRUNCATING_VIEWS: readonly ViewModeValue[] = [
  "title_line",
  "url_line",
  "cards",
];
const TEXT_SELECTORS = [".urlTitle", ".urlString"] as const;
const URL_ROW_SELECTOR = ".urlRow";

/**
 * Sets (or removes) the full-text hover tooltip on a card's title and URL. It is
 * set ONLY while the row is unselected and the rendered view truncates
 * (title_line, url_line, or cards when wide), so a screen reader never hears the
 * text twice. `effectiveRenderedViewMode` is used, not the raw stored value,
 * because `cards` below the wide breakpoint renders as List.
 */
export function syncUrlTooltips(urlCard: JQuery): void {
  const showTooltip =
    urlCard.attr("urlSelected") !== "true" &&
    TRUNCATING_VIEWS.includes(effectiveRenderedViewMode());
  TEXT_SELECTORS.forEach((selector) => {
    const textElement = urlCard.find(selector);
    if (showTooltip) {
      const fullText =
        selector === ".urlString"
          ? (textElement.attr("href") ?? textElement.text())
          : textElement.text();
      textElement.attr("title", fullText);
    } else {
      textElement.removeAttr("title");
    }
  });
}

/** Re-syncs every card in the deck (a view-mode or breakpoint change). */
export function syncAllUrlTooltips(): void {
  $(URL_ROW_SELECTOR).each(function () {
    syncUrlTooltips($(this));
  });
}

let wideViewportListenerBound = false;

/**
 * Binds ONCE (module-level guard, so repeated init never stacks listeners) a
 * change listener on the Cards breakpoint: crossing 992px (resize or rotation)
 * is not a view-mode change but flips whether Cards renders as Cards or List.
 */
export function bindWideViewportTooltipSync(): void {
  if (wideViewportListenerBound) return;
  if (typeof window.matchMedia !== "function") {
    log("matchMedia unavailable, tooltip breakpoint sync not bound");
    return;
  }
  const wideQuery = window.matchMedia(WIDE_VIEWPORT_QUERY);
  if (typeof wideQuery?.addEventListener !== "function") {
    log("MediaQueryList.addEventListener unavailable, sync not bound");
    return;
  }
  wideViewportListenerBound = true;
  log("bound wide-viewport tooltip sync", WIDE_VIEWPORT_QUERY);
  wideQuery.addEventListener("change", () => {
    syncAllUrlTooltips();
  });
}
