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
  SPACE: " ",
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
export const TABLET_WIDTH = 992 as const;

/**
 * Delay before showing loading icons (ms)
 * Prevents flicker for fast operations
 */
export const SHOW_LOADING_ICON_AFTER_MS = 50 as const;
