import { isCardsLayoutActive } from "../view-mode.js";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/**
 * Scrolls a card the user just selected into view in the Cards grid. A selected
 * card relocates to a full-width row and the content below reflows, so it can
 * land off-screen. A no-op in List, the line modes and below the wide
 * breakpoint (effective List).
 *
 * Call only from user-initiated selections (click, arrow keys), never from
 * `selectURLCard` itself: programmatic selections (cross-UTub search, tag
 * drag-drop auto-select, create-URL) must not scroll. Order is DOM/reading
 * order in every mode, so ArrowUp/ArrowDown mean previous/next card.
 */
export function scrollSelectedCardIntoView(urlCard: JQuery): void {
  if (!isCardsLayoutActive()) return;
  const element = urlCard[0];
  if (typeof element?.scrollIntoView !== "function") return;
  const reduceMotion =
    typeof window.matchMedia === "function" &&
    window.matchMedia(REDUCED_MOTION_QUERY).matches;
  element.scrollIntoView({
    block: "nearest",
    behavior: reduceMotion ? "auto" : "smooth",
  });
}
