import type { ViewModeValue } from "../../types/preferences.js";

/** The same query the Cards CSS uses, so JS and CSS agree at the boundary. */
export const WIDE_VIEWPORT_QUERY = "(min-width: 992px)";

const VIEW_MODES: readonly ViewModeValue[] = [
  "list",
  "title_line",
  "url_line",
  "cards",
];

export function isViewMode(value: unknown): value is ViewModeValue {
  return VIEW_MODES.some((mode) => mode === value);
}

/** An unknown (stale or tampered) value fails closed to the plain List layout. */
export function normalizeViewMode(value: unknown): ViewModeValue {
  return isViewMode(value) ? value : "list";
}

/**
 * True when the viewport is wide enough for Cards. Fails closed: a missing
 * `matchMedia` is NOT wide, so Cards is never offered. This is the opposite of
 * the fine-pointer helper in personal-settings-section.ts, which keeps its row
 * when `matchMedia` is missing.
 */
export function isWideViewport(): boolean {
  if (typeof window.matchMedia !== "function") return false;
  return window.matchMedia(WIDE_VIEWPORT_QUERY).matches;
}

/** The view that actually renders: Cards below the wide breakpoint is List. */
export function renderedViewMode(viewMode: ViewModeValue): ViewModeValue {
  return viewMode === "cards" && !isWideViewport() ? "list" : viewMode;
}
