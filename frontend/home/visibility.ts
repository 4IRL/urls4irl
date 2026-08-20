import { $ } from "../lib/globals.js";
import { enableTabbableChildElements } from "../lib/jquery-plugins.js";
import { getState } from "../store/app-store.js";

// Where el is the DOM element you'd like to test for visibility
export function isHidden(el: JQuery<HTMLElement>): boolean {
  const domEl = $(el).get(0);
  return domEl ? domEl.offsetParent === null : true;
}

// Initialize visibility handlers (wrapping the $(window) handlers from original)
export function initVisibilityHandlers(): void {
  $(window).on("focus", () => {
    const prevFocusedElem = $(".focus");
    if (prevFocusedElem.length === 0) return;
    if (prevFocusedElem.length > 1) {
      // Only one should've been focused before
      prevFocusedElem.removeClass("focus");
      return;
    }
    // Find the first URL card closest to last focused item
    const urlCard = prevFocusedElem.closest(".urlRow");

    if (prevFocusedElem.hasClass("goToUrlIcon")) {
      urlCard
        .find(".goToUrlIcon")
        .addClass("visible-on-focus")
        .trigger("focus");
    }
  });

  // Refocus when going to another tab
  $(window).on("blur", () => {
    if (document.activeElement !== null) {
      const activeElement = $(document.activeElement);

      const urlCard = activeElement.closest(".urlRow");
      if (urlCard.length == 0) {
        activeElement.addClass("focus");
        return;
      }

      // In multi-select mode a focused URL card must NOT auto-expand when the app
      // is backgrounded / the tab loses focus. Tapping a card's checkbox to select
      // it leaves that card as document.activeElement, so without this guard
      // backgrounding mobile Safari would set urlselected=true on it and it would
      // be expanded (tags + action buttons showing) on return — corrupting the
      // selection view. Selection state is untouched; only the auto-expand is
      // suppressed while selecting.
      if (getState().multiSelectMode) return;

      urlCard.attr({ urlselected: true });
      enableTabbableChildElements(urlCard);
    }
  });
}
