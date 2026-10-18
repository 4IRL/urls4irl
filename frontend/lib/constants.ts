/**
 * Application-wide constants
 * Consolidated from btns_forms.js, mobile.js, and url_cards_utils.js
 */

/**
 * Keyboard key constants
 */
export const KEYS = {
  ENTER: "Enter",
  ESCAPE: "Escape",
  ARROW_UP: "ArrowUp",
  ARROW_DOWN: "ArrowDown",
  BACKSPACE: "Backspace",
  TAB: "Tab",
  SPACE: " ",
  K: "k",
} as const;

/**
 * Form method types for text input creation
 */
export const METHOD_TYPES = Object.freeze({
  CREATE: Symbol("Create"),
  UPDATE: Symbol("Update"),
} as const);

/**
 * Input field types
 */
export const INPUT_TYPES = Object.freeze({
  TEXT: Symbol("text"),
  URL: Symbol("url"),
  EMAIL: Symbol("email"),
} as const);

/**
 * Responsive breakpoint for tablet/mobile
 * Matches Bootstrap's lg breakpoint (992px)
 */
export const TABLET_WIDTH = 992;

/**
 * Delay before showing loading icons (ms)
 * Prevents flicker for fast operations
 */
export const SHOW_LOADING_ICON_AFTER_MS = 50;

/**
 * How long an outcome banner stays up before hiding itself. Long enough to read
 * the message and reach Undo on a phone.
 */
export const OUTCOME_BANNER_AUTO_HIDE_MS = 10000;
/** Longer countdown for partial (error / no-change) banners the user may need to read. */
export const OUTCOME_BANNER_AUTO_HIDE_PARTIAL_MS = 20000;
/** Fixed countdown on a coarse pointer, where hover/focus pause has no equivalent. */
export const OUTCOME_BANNER_AUTO_HIDE_COARSE_MS = 20000;

/** Bounds the worst case of a 100-row bulk delete/restore well above the 35s single-row precedent. */
export const BULK_REQUEST_TIMEOUT_MS = 35000;

/** Stable in-mode focus-return anchor (the header Exit control) for bulk actions. */
export const BULK_FOCUS_RETURN_SELECTOR = "#bulkSelectExit";

export const ICON_SIZE_SM = 20 as const;
export const ICON_SIZE_LG = 30 as const;
export type IconSize = typeof ICON_SIZE_SM | typeof ICON_SIZE_LG;
