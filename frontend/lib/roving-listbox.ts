import { $ } from "./globals.js";
import { KEYS } from "./constants.js";

// Shared roving-tabindex + keyboard + substring-filter listbox machinery, factored
// out of the transfer-owner picker (single-select) and the bulk-copy destination
// picker (multi-select) which had grown two near-identical copies of this
// accessibility-critical behaviour. A single instance (created via
// createRovingListbox) owns the roving tabindex, arrow-key navigation, the
// Enter/Space activation on keyup with page-scroll suppression on keydown, an
// optional Escape hook, and the case-insensitive substring filter. The two
// pickers differ in SELECT semantics (single clears others + stages one id; multi
// toggles a Set and has disabled rows) and in whether Escape is handled here vs by
// Bootstrap — those differences are parameterised, never collapsed.

/**
 * Per-picker configuration for a roving listbox. Selectors are the picker's own
 * (the two pickers use different class names); `container` is a thunk because the
 * container element persists across re-renders while its children are rebuilt.
 */
export interface RovingListboxConfig {
  /** The listbox container (pick view / mount), resolved lazily each call. */
  container: () => JQuery;
  /** All option rows within the container (e.g. `.UTubSelector[role="option"]`). */
  optionSelector: string;
  /** Rows eligible for roving/focus = not filtered out (and, for multi, not disabled). */
  enabledOptionSelector: string;
  /** The inner `role="listbox"` element (a child of the container). */
  listboxSelector: string;
  /** The no-results message element shown when the filter matches nothing. */
  noMatchesSelector: string;
  /** Extract a row's filterable text (username / UTub name). Lower-cased by the filter. */
  filterText: (row: JQuery) => string;
  /**
   * Select (single-select) or toggle (multi-select) the activated row. Called on
   * Enter/Space keyup; the picker owns the single-vs-multi semantic.
   */
  onActivateRow: (row: JQuery) => void;
  /**
   * Whether a row is disabled (excluded from keyup activation). Defaults to a
   * `.disabled` class check — multi-select (bulk-copy) has disabled/locked rows;
   * single-select (transfer) never does, so the default is a harmless no-op there.
   */
  isRowDisabled?: (row: JQuery) => boolean;
  /**
   * Escape handler. When provided (bulk-copy), Escape is stopPropagation +
   * preventDefault here and this fires (the callback owns any in-flight guard).
   * When omitted (transfer), Escape is left to Bootstrap's data-bs-keyboard.
   */
  onEscape?: () => void;
}

/** The roving-listbox behaviours a picker drives. */
export interface RovingListbox {
  /** Move the roving tabindex AND real DOM focus onto `rowEl` atomically. */
  setActiveRow(rowEl: HTMLElement): void;
  /** The enabled (non-filtered, non-disabled) option rows, in DOM order. */
  enabledRowElements(): HTMLElement[];
  /** Move roving focus to the next/prev enabled row, wrapping at the ends. */
  moveRoving(params: { direction: 1 | -1 }): void;
  /** Case-insensitive substring filter; toggles `.hidden` + the no-matches message. */
  applyFilter(rawQuery: string): void;
  /** Re-seed the roving entry point (tabindex 0) onto the first still-visible enabled row. */
  resetRovingEntry(): void;
  /** Attach the capture-phase keydown + bubble keyup listeners on the container. */
  attachKeyListeners(): void;
  /** Detach the keydown/keyup listeners (idempotent). */
  detachKeyListeners(): void;
}

/**
 * Build a roving-listbox controller for one picker. The returned object holds its
 * own keydown/keyup listener references, so two pickers each get an independent
 * instance with no shared mutable state.
 */
export function createRovingListbox(
  config: RovingListboxConfig,
): RovingListbox {
  const {
    container,
    optionSelector,
    enabledOptionSelector,
    listboxSelector,
    noMatchesSelector,
    filterText,
    onActivateRow,
    isRowDisabled = (row: JQuery) => row.hasClass("disabled"),
    onEscape,
  } = config;

  let keydownListener: ((event: KeyboardEvent) => void) | null = null;
  let keyupListener: ((event: KeyboardEvent) => void) | null = null;

  /**
   * Move the roving tabindex AND real DOM focus onto `rowEl` atomically: the
   * previously-active row's tabindex goes back to -1, `rowEl`'s becomes 0, then it
   * receives focus. Both arrow navigation and the pickers' select/toggle call this.
   */
  function setActiveRow(rowEl: HTMLElement): void {
    container().find(optionSelector).attr("tabindex", "-1");
    $(rowEl).attr("tabindex", "0");
    rowEl.focus();
  }

  /** The enabled (non-filtered, non-disabled) option rows, in DOM order, as elements. */
  function enabledRowElements(): HTMLElement[] {
    return container().find(enabledOptionSelector).toArray();
  }

  /**
   * Move roving focus to the next/previous enabled row (wrapping at the ends),
   * skipping filtered/disabled rows. Pure navigation — it never selects a row.
   * `direction` is +1 (ArrowDown/next) or -1 (ArrowUp/previous).
   */
  function moveRoving({ direction }: { direction: 1 | -1 }): void {
    const rows = enabledRowElements();
    if (rows.length === 0) return;
    const active = document.activeElement as HTMLElement | null;
    const currentIndex = active ? rows.indexOf(active) : -1;
    // From -1 (focus elsewhere) ArrowDown lands on 0, ArrowUp on the last row.
    const nextIndex =
      currentIndex === -1
        ? direction === 1
          ? 0
          : rows.length - 1
        : (currentIndex + direction + rows.length) % rows.length;
    setActiveRow(rows[nextIndex]);
  }

  /**
   * Reset the roving tabindex entry point after a filter change: clear tabindex on
   * every option row, then set the FIRST still-visible enabled row to tabindex 0.
   * Focus is not moved (it stays in the filter input while the user types).
   */
  function resetRovingEntry(): void {
    const root = container();
    root.find(optionSelector).attr("tabindex", "-1");
    root.find(enabledOptionSelector).first().attr("tabindex", "0");
  }

  /**
   * Filter the option rows by the typed query (case-insensitive substring on the
   * row's filter text). Non-matching rows get `.hidden` (excluded from roving via
   * the enabled selector); the no-results message shows when nothing matches. A
   * currently-staged row stays staged even if filtered out — the picker's staged
   * state, not row visibility, is what it commits.
   */
  function applyFilter(rawQuery: string): void {
    const query = rawQuery.trim().toLowerCase();
    const listbox = container().find(listboxSelector);

    let visibleCount = 0;
    listbox.find(optionSelector).each((_, element) => {
      const row = $(element);
      const matches =
        query === "" || filterText(row).toLowerCase().includes(query);
      row.toggleClass("hidden", !matches);
      if (matches) visibleCount += 1;
    });

    listbox.find(noMatchesSelector).toggleClass("hidden", visibleCount > 0);
    // Keep a single visible enabled row as the roving entry point (tabindex 0) so
    // ArrowDown / Tab from the input always lands on a shown row.
    resetRovingEntry();
  }

  /**
   * Keydown: optional Escape (stopPropagation + preventDefault + onEscape);
   * ArrowUp/ArrowDown rove focus across enabled rows; Space is prevent-defaulted
   * ONLY when an option row is focused (keydown is where page-scroll-on-Space
   * happens — keyup alone cannot suppress it; footer buttons keep native Space).
   * Activation itself happens on keyup, never here.
   */
  function handleKeydown(event: KeyboardEvent): void {
    switch (event.key) {
      case KEYS.ESCAPE: {
        if (onEscape) {
          event.stopPropagation();
          event.preventDefault();
          onEscape();
        }
        return;
      }
      case KEYS.ARROW_DOWN: {
        event.preventDefault();
        moveRoving({ direction: 1 });
        return;
      }
      case KEYS.ARROW_UP: {
        event.preventDefault();
        moveRoving({ direction: -1 });
        return;
      }
      case KEYS.SPACE: {
        const target = event.target as HTMLElement | null;
        if (target && $(target).closest(optionSelector).length > 0) {
          event.preventDefault();
        }
        return;
      }
      default:
        return;
    }
  }

  /**
   * Keyup: Enter or Space on the currently-focused enabled row activates it
   * (select for single-select, toggle for multi-select). Disabled rows never
   * activate.
   */
  function handleKeyup(event: KeyboardEvent): void {
    if (event.key !== KEYS.ENTER && event.key !== KEYS.SPACE) return;
    const target = event.target as HTMLElement | null;
    if (target === null) return;
    const row = $(target).closest(optionSelector);
    if (row.length === 0 || isRowDisabled(row)) return;
    onActivateRow(row);
  }

  function attachKeyListeners(): void {
    const containerElement = container()[0];
    if (!containerElement) return;
    detachKeyListeners();
    keydownListener = handleKeydown;
    keyupListener = handleKeyup;
    // Capture phase for keydown so Arrow/Escape are handled before any nested or
    // document-level handler (mirrors the pre-refactor pickers).
    containerElement.addEventListener("keydown", keydownListener, {
      capture: true,
    });
    containerElement.addEventListener("keyup", keyupListener);
  }

  function detachKeyListeners(): void {
    const containerElement = container()[0];
    if (containerElement) {
      if (keydownListener) {
        containerElement.removeEventListener("keydown", keydownListener, {
          capture: true,
        });
      }
      if (keyupListener) {
        containerElement.removeEventListener("keyup", keyupListener);
      }
    }
    keydownListener = null;
    keyupListener = null;
  }

  return {
    setActiveRow,
    enabledRowElements,
    moveRoving,
    applyFilter,
    resetRovingEntry,
    attachKeyListeners,
    detachKeyListeners,
  };
}
