import type { SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubSummaryItem } from "../../../types/utub.js";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { KEYS, SHOW_LOADING_ICON_AFTER_MS } from "../../../lib/constants.js";
import { debug } from "../../../lib/debug.js";
import { AppEvents, on } from "../../../lib/event-bus.js";
import { clearOpenForm, setOpenForm } from "../../../lib/modal-tracking.js";
import { HOME_FORM } from "../../../types/metrics-dim-values.js";
import { getState } from "../../../store/app-store.js";
import {
  type BulkAction,
  type BulkActionContext,
  registerBulkAction,
} from "./bulk-action-registry.js";
import { flashCardResultCues } from "./card-cues.js";
import {
  isAnyBulkPickerOpen,
  registerPickerClose,
  setPickerOpen,
} from "./picker-guard.js";

const log = debug("urls:cards");

type CopyUrlsResponse = SuccessResponse<"copyUrlsToUtubs">;

const PICKER_MOUNT_SELECTOR = "#bulkCopyPickerMount";
const BANNER_SELECTOR = "#bulkCopyResultBanner";
const DECK_SELECTOR = "#URLDeck";
const PICKER_OPEN_CLASS = "bulkCopyPickerOpen";
// Stable in-mode focus-return anchor (the header Exit control) — never the
// ephemeral #bulkActionButtons button, which rebuilds on every selection change.
const FOCUS_RETURN_SELECTOR = "#bulkSelectExit";
// The role="listbox" element is an INNER child of the mount (not the mount
// itself) so the filter input + footer can live inside the floating dropdown
// without being invalid children of a listbox.
const LISTBOX_SELECTOR = ".bulkCopyListbox";
const NO_MATCHES_SELECTOR = ".bulkCopyNoMatches";
const OPTION_SELECTOR = '.UTubSelector[role="option"]';
// "Enabled" for roving/focus = not locked AND not filtered out (.hidden). The
// filter box adds/removes .hidden as the user types, so arrow-key navigation and
// the roving entry-point row automatically skip filtered rows.
const ENABLED_OPTION_SELECTOR =
  '.UTubSelector[role="option"]:not(.disabled):not(.hidden)';
const CANCEL_BTN_SELECTOR = ".bulkCopyCancelBtn";
const CONFIRM_BTN_SELECTOR = ".bulkCopyConfirmBtn";
const MESSAGE_SELECTOR = ".bulkCopyPickerMsg";
const SUBMIT_LOADING_CLASS = "bulkCopySubmitLoading";

// Trusted static folder-plus icon (green accent — NOT the purple clipboard glyph
// used for single-URL copy). Injected as raw HTML via the registry's
// `.prepend(iconHtml)`, so this MUST stay a hard-coded literal — never
// interpolate user content into it (HTML-injection sink).
const BULK_COPY_ICON_HTML =
  '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" ' +
  'fill="none" stroke="var(--deckSelectionGreen)" stroke-width="1.4" ' +
  'viewBox="0 0 16 16" aria-hidden="true">' +
  '<path d="M1.7 4.2A1 1 0 0 1 2.7 3.3h3l1.4 1.4H13a1 1 0 0 1 1 1v6.6a1 1 0 0 1-1 1H2.7a1 1 0 0 1-1-1z"/>' +
  '<path d="M8 7.2v3.2M6.4 8.8h3.2" stroke-linecap="round"/>' +
  "</svg>";

// Funnel prefix icon for the destination filter — the SAME markup the app's deck
// search bars use (utub-search-prefix-icon in UTubDeckHeaders.html), so the copy
// filter box reads as the same control. Trusted static literal — never
// interpolate user content into it.
const FILTER_ICON_HTML =
  '<svg class="utub-search-prefix-icon" xmlns="http://www.w3.org/2000/svg" ' +
  'fill="currentColor" height="14" width="14" viewBox="0 0 16 16" aria-hidden="true">' +
  '<path d="M1.5 1.5A.5.5 0 0 1 2 1h12a.5.5 0 0 1 .5.5v2a.5.5 0 0 1-.128.334L10 8.692V13.5a.5.5 0 0 1-.342.474l-3 1A.5.5 0 0 1 6 14.5V8.692L1.628 3.834A.5.5 0 0 1 1.5 3.5z"/>' +
  "</svg>";

// --- Picker-open flag (owned here; mirrored into the shared registry) ---------

let bulkCopyPickerOpen = false;

/** Whether the bulk copy picker is currently mounted/open. */
export function isBulkCopyPickerOpen(): boolean {
  return bulkCopyPickerOpen;
}

/** Set the picker-open flag (and mirror it into the shared picker registry). */
export function setBulkCopyPickerOpen(open: boolean): void {
  bulkCopyPickerOpen = open;
  // Keep the shared open-picker registry in lock-step with this module's flag so
  // isAnyBulkPickerOpen()/closeAllPickers() (picker-guard.ts) always agree.
  setPickerOpen("bulk-copy", open);
}

// --- Open-picker lifecycle state ----------------------------------------------

let currentSnapshot: number[] = [];
let currentSourceUtubID: number | null = null;
// Multi-select: the staged destination UTub ids. Cleared (never reassigned) so
// the module-level reference stays stable across the picker lifecycle.
const stagedDestUtubIDs = new Set<number>();
let submitInFlight = false;
let loadingTimeoutID: number | null = null;
let keydownListener: ((event: KeyboardEvent) => void) | null = null;
let keyupListener: ((event: KeyboardEvent) => void) | null = null;

// --- Action registration ------------------------------------------------------

const bulkCopyAction: BulkAction = {
  id: "bulk-copy",
  label: APP_CONFIG.strings.URL_BULK_COPY_LABEL,
  iconHtml: BULK_COPY_ICON_HTML,
  // Available only when something is selected AND there is at least one OTHER
  // UTub to copy into (locked-vs-unlocked is handled inside the picker — DD-18,
  // isAvailable itself stays a pure selection/other-UTub-exists gate).
  isAvailable: (context: BulkActionContext) =>
    context.selectedURLCardIDs.length > 0 &&
    getState().utubs.some((utub) => utub.id !== getState().activeUTubID),
  onActivate: openBulkCopyPicker,
};

// Bus subscriptions are process-wide (no rebind), and the action registry is
// append-only, so guard both against a repeat initBulkActions().
let _bulkCopyInitialized = false;

/**
 * Register the bulk-copy action, its picker-close callback, and the mode-exit
 * teardown. Called from initBulkActions(); the import itself is what makes
 * registration run.
 */
export function initBulkCopy(): void {
  if (_bulkCopyInitialized) return;
  _bulkCopyInitialized = true;

  registerBulkAction(bulkCopyAction);

  // Register this picker's teardown so closeAllPickers() (picker-guard.ts,
  // invoked by bulk-mode.ts's exitMultiSelectMode before it clears the
  // selection) can close it alongside the tag picker.
  registerPickerClose("bulk-copy", () =>
    closeAndResetPicker({ returnFocus: false }),
  );

  // Mode exit / UTub switch tears the picker down even if the user never closed
  // it. This module depends on the event, never on bulk-mode.ts, keeping the
  // dependency one-way. Idempotent with closeAllPickers()'s own teardown.
  on(AppEvents.URL_MULTISELECT_MODE_CHANGED, ({ active }) => {
    if (active === false && isBulkCopyPickerOpen()) {
      log("bulk copy picker torn down on multi-select mode exit");
      closeAndResetPicker({ returnFocus: false });
    }
  });
}

// --- Open / close lifecycle ---------------------------------------------------

/**
 * Open the destination-UTub picker for the current selection: snapshot the
 * selected ids + source UTub, mount a roving-tabindex listbox of the OTHER UTubs
 * into the stable `#bulkCopyPickerMount`, lock the selection, and focus the
 * first enabled destination row. Re-entrant / cross-picker activation is a
 * defined no-op (only one bulk sub-picker open at a time).
 */
function openBulkCopyPicker(context: BulkActionContext): void {
  if (isAnyBulkPickerOpen()) return;

  const sourceUtubID = getState().activeUTubID;
  if (sourceUtubID === null) return;

  const snapshot = [...context.selectedURLCardIDs];
  if (snapshot.length === 0) return;

  log("open bulk copy picker", { snapshot, sourceUtubID });

  currentSnapshot = snapshot;
  currentSourceUtubID = sourceUtubID;
  stagedDestUtubIDs.clear();
  submitInFlight = false;
  setBulkCopyPickerOpen(true);
  setOpenForm(HOME_FORM.BULK_COPY);

  $(DECK_SELECTOR).addClass(PICKER_OPEN_CLASS);
  // The picker supersedes any prior result banner.
  $(BANNER_SELECTOR).addClass("hidden").empty();

  const destinations = getState().utubs.filter(
    (utub) => utub.id !== sourceUtubID,
  );
  renderPicker({ destinations, selectedCount: snapshot.length });
}

/**
 * Build and mount the picker markup: a filter input (sticky top), an inner
 * `role="listbox"` holding the destination `role="option"` rows (roving
 * tabindex), and a footer (message, Cancel, Copy). The listbox is an INNER child
 * of the mount — not the mount itself — so the filter input and footer are not
 * invalid children of a listbox. When every other UTub is locked, an accessible
 * all-locked message replaces the rows (and the filter) and Copy stays disabled
 * (DD-18).
 */
function renderPicker({
  destinations,
  selectedCount,
}: {
  destinations: UtubSummaryItem[];
  selectedCount: number;
}): void {
  const mount = $(PICKER_MOUNT_SELECTOR);
  mount.empty().removeAttr("role").removeAttr("aria-label");

  const listbox = $(document.createElement("div")).addClass("bulkCopyListbox");
  listbox.attr({
    role: "listbox",
    "aria-multiselectable": "true",
    "aria-label": APP_CONFIG.strings.URL_BULK_COPY_ARIA.replace(
      "{n}",
      String(selectedCount),
    ),
  });

  const enabledDestinations = destinations.filter((utub) => !utub.isLocked);

  if (enabledDestinations.length === 0) {
    // Every other UTub is locked — no focusable destination row and nothing to
    // filter. Render an announced message and focus it; Copy stays disabled
    // (DD-18). No filter input in this path.
    const allLocked = $(document.createElement("div"))
      .addClass("bulkCopyAllLocked")
      .attr({ role: "status", "aria-live": "polite", tabindex: "-1" })
      .text(APP_CONFIG.strings.URL_BULK_COPY_ALL_LOCKED);
    listbox.append(allLocked);
    mount.append(listbox).append(buildFooter());
    attachKeyListeners();
    mount.removeClass("hidden");
    allLocked[0]?.focus();
    return;
  }

  let firstEnabledSeen = false;
  destinations.forEach((utub) => {
    const isEnabled = !utub.isLocked;
    // The first enabled row is the initial roving-tabindex target (tabindex 0);
    // every other row (and all disabled rows) start at tabindex -1.
    const isInitialRow = isEnabled && !firstEnabledSeen;
    if (isInitialRow) firstEnabledSeen = true;

    const row = $(document.createElement("div"))
      .addClass("UTubSelector flex-row jc-sb align-center")
      .attr({
        role: "option",
        id: `bulkCopyOption-${utub.id}`,
        utubid: utub.id,
        "aria-selected": "false",
        tabindex: isInitialRow ? "0" : "-1",
      });
    if (!isEnabled) row.addClass("disabled").attr("aria-disabled", "true");

    // Decorative teal check affordance (DD-7 — aria-hidden, NOT role="checkbox";
    // the row's own aria-selected carries the selected state). Prepended as the
    // FIRST child so it reads left-of-name, mirroring .urlSelectCheckbox.
    row.append(
      $(document.createElement("span"))
        .addClass("bulkCopyOptionCheck")
        .attr({ "aria-hidden": "true" }),
    );
    row.append(
      $(document.createElement("b")).addClass("UTubName").text(utub.name),
    );
    // Per-row trailing affordance (DD-4/DD-12 — mutually exclusive): an enabled
    // row shows its role badge; a locked row shows the locked label instead,
    // never both. Both use .text() (never innerHTML) so a UTub/role value can
    // never inject markup.
    if (isEnabled) {
      row.append(
        $(document.createElement("span"))
          .addClass("bulkCopyRoleBadge")
          .attr(
            "aria-label",
            APP_CONFIG.strings.URL_BULK_COPY_ROLE_ARIA.replace(
              "{role}",
              utub.memberRole,
            ),
          )
          .text(utub.memberRole),
      );
    } else {
      row.append(
        $(document.createElement("span"))
          .addClass("bulkCopyLockedLabel")
          .text(APP_CONFIG.strings.URL_BULK_COPY_LOCKED_LABEL),
      );
    }
    // Row click toggles the destination (never fires the copy).
    row.on("click.bulkCopyStage", () => {
      if (row.hasClass("disabled")) return;
      toggleRow(row);
    });
    listbox.append(row);
  });

  // No-results message shown inside the listbox when the typed filter matches no
  // destination rows; hidden until then (announced via role=status/aria-live).
  const noMatches = $(document.createElement("div"))
    .addClass("bulkCopyNoMatches hidden")
    .attr({ role: "status", "aria-live": "polite" })
    .text(APP_CONFIG.strings.URL_BULK_COPY_NO_MATCHES);
  listbox.append(noMatches);

  mount.append(buildFilterInput()).append(listbox).append(buildFooter());
  // Seed the footer live-region + disabled Copy button so the picker opens
  // already showing the "select at least one" hint (nothing staged yet).
  updateConfirmEnabled();
  attachKeyListeners();
  mount.removeClass("hidden");

  // Focus the FIRST ENABLED destination row on open (never the filter input):
  // keyboard/SR users land inside the listbox with no cursor sitting in a
  // textbox and no mobile soft-keyboard popup. setActiveRow() moves the roving
  // tabindex (0) AND real DOM focus atomically onto that row, so they can never
  // drift. The filter stays reachable via Tab/click and still narrows the list.
  // The all-locked case returns earlier, so there is normally ≥1 enabled row
  // here; guard defensively in case the lookup is empty.
  const firstEnabledRow = mount.find(ENABLED_OPTION_SELECTOR)[0];
  if (firstEnabledRow) setActiveRow(firstEnabledRow);
}

/**
 * Build the destination-filter input (sticky top of the dropdown). Typing filters
 * the option rows by UTub name (case-insensitive substring); ArrowDown/ArrowUp
 * from the input rove real focus into the list (handled by the mount keydown
 * listener). It is NOT a listbox child, so it does not corrupt the listbox's ARIA.
 */
function buildFilterInput(): JQuery {
  // Reuse the app's canonical deck-search markup — a `.text-input.search-input`
  // pill inside a `.text-input-inner-container` with an absolutely-positioned
  // funnel prefix icon — so this box is visually identical to the UTub / Tag /
  // Member / URL search bars. The outer wrapper adds the desktop sticky-top +
  // opaque background so scrolling rows never peek through the mount's padding.
  const wrap = $(document.createElement("div")).addClass("bulkCopyFilterWrap");
  const inner = $(document.createElement("div")).addClass(
    "text-input-inner-container",
  );
  inner.append(FILTER_ICON_HTML);
  const input = $(document.createElement("input"))
    .addClass("text-input search-input bulkCopyFilterInput")
    .attr({
      type: "search",
      autocomplete: "off",
      autocorrect: "off",
      autocapitalize: "off",
      "aria-label": APP_CONFIG.strings.URL_BULK_COPY_FILTER_PLACEHOLDER,
      placeholder: APP_CONFIG.strings.URL_BULK_COPY_FILTER_PLACEHOLDER,
    });
  input.on("input.bulkCopyFilter", () =>
    applyFilter(String(input.val() ?? "")),
  );
  inner.append(input);
  wrap.append(inner);
  return wrap;
}

/**
 * Filter the destination rows by the typed query (case-insensitive substring on
 * the UTub name). Non-matching rows get `.hidden` (excluded from roving/focus via
 * ENABLED_OPTION_SELECTOR); the no-results message shows when nothing matches. A
 * currently-staged row stays staged even if filtered out — the staged id, not the
 * row's visibility, is what Copy commits.
 */
function applyFilter(rawQuery: string): void {
  const query = rawQuery.trim().toLowerCase();
  const listbox = $(PICKER_MOUNT_SELECTOR).find(LISTBOX_SELECTOR);

  let visibleCount = 0;
  listbox.find(OPTION_SELECTOR).each((_, element) => {
    const row = $(element);
    const name = row.find(".UTubName").text().toLowerCase();
    const matches = query === "" || name.includes(query);
    row.toggleClass("hidden", !matches);
    if (matches) visibleCount += 1;
  });

  listbox.find(NO_MATCHES_SELECTOR).toggleClass("hidden", visibleCount > 0);
  // Keep a single visible enabled row as the roving entry point (tabindex 0) so
  // ArrowDown / Tab from the input always lands on a shown row.
  resetRovingEntry();
}

/**
 * Reset the roving tabindex entry point after a filter change: clear tabindex on
 * every option row, then set the FIRST still-visible enabled row to tabindex 0.
 * Focus is not moved (it stays in the filter input while the user types).
 */
function resetRovingEntry(): void {
  const mount = $(PICKER_MOUNT_SELECTOR);
  mount.find(OPTION_SELECTOR).attr("tabindex", "-1");
  mount.find(ENABLED_OPTION_SELECTOR).first().attr("tabindex", "0");
}

/** Build the picker footer: a live-region message + Cancel + Copy buttons. */
function buildFooter(): JQuery {
  const footer = $(document.createElement("div")).addClass(
    "bulkCopyPickerFooter flex-row align-center",
  );

  const message = $(document.createElement("div"))
    .addClass("bulkCopyPickerMsg")
    .attr({ role: "status", "aria-live": "polite" });

  const cancelBtn = $(document.createElement("button"))
    .addClass("bulkCopyCancelBtn tabbable")
    .attr({ type: "button" })
    .text("Cancel");
  cancelBtn.on("click.bulkCopyCancel", () => {
    if (submitInFlight) return;
    closeAndResetPicker({ returnFocus: true });
  });

  const confirmBtn = $(document.createElement("button"))
    .addClass("bulkCopyConfirmBtn tabbable")
    .attr({ type: "button" })
    .prop("disabled", true)
    .text(APP_CONFIG.strings.URL_BULK_COPY_LABEL);
  confirmBtn.on("click.bulkCopyConfirm", () => submitCopy());

  footer.append(message).append(cancelBtn).append(confirmBtn);
  return footer;
}

/**
 * Shared close/reset used by every close path (copy success, Cancel, Escape,
 * mode-exit, UTub switch): clears the mount, unlocks the selection, drops the
 * open-form token + picker-open flag, and (optionally) returns focus to the
 * stable header Exit control.
 */
function closeAndResetPicker({
  returnFocus = true,
}: {
  returnFocus?: boolean;
} = {}): void {
  detachKeyListeners();
  $(PICKER_MOUNT_SELECTOR)
    .empty()
    .addClass("hidden")
    .removeAttr("role")
    .removeAttr("aria-label");
  $(DECK_SELECTOR).removeClass(PICKER_OPEN_CLASS);

  clearOpenForm();
  setBulkCopyPickerOpen(false);

  currentSnapshot = [];
  currentSourceUtubID = null;
  stagedDestUtubIDs.clear();
  submitInFlight = false;
  if (loadingTimeoutID !== null) {
    clearTimeout(loadingTimeoutID);
    loadingTimeoutID = null;
  }

  if (returnFocus) {
    const anchor = $(FOCUS_RETURN_SELECTOR);
    if (anchor.length > 0) anchor[0]?.focus();
  }
}

// --- Roving tabindex + staging ------------------------------------------------

/**
 * Move the roving tabindex AND real DOM focus onto `rowEl` atomically (DD-20):
 * the previously-active row's tabindex goes back to "-1", `rowEl`'s becomes "0",
 * then `rowEl` receives focus. BOTH arrow-key navigation and the Stage path call
 * this single helper, so tabindex, DOM focus, and the staged selection can never
 * drift apart.
 */
function setActiveRow(rowEl: HTMLElement): void {
  const mount = $(PICKER_MOUNT_SELECTOR);
  mount.find(OPTION_SELECTOR).attr("tabindex", "-1");
  const row = $(rowEl);
  row.attr("tabindex", "0");
  rowEl.focus();
}

/** The enabled option rows, in DOM order, as an array of elements. */
function enabledRowElements(): HTMLElement[] {
  return $(PICKER_MOUNT_SELECTOR).find(ENABLED_OPTION_SELECTOR).toArray();
}

/**
 * Move roving focus to the next/previous enabled row (wrapping at the ends),
 * skipping disabled rows. Pure navigation — it does NOT stage a row. `direction`
 * is +1 (ArrowDown/next) or -1 (ArrowUp/previous).
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
 * Toggle a destination row's staged state (multi-select, DD-7): move roving
 * focus to it FIRST (so a click on a row that did not already hold focus never
 * leaves tabindex/focus on a stale row), then add or remove its id from the
 * staged set and flip its own `aria-selected`/`.active`. Other rows are left
 * untouched — several destinations can be staged at once.
 */
function toggleRow(row: JQuery): void {
  const rowEl = row[0];
  if (!rowEl) return;
  setActiveRow(rowEl);

  const id = parseInt(row.attr("utubid") ?? "", 10);
  if (Number.isNaN(id)) return;

  if (stagedDestUtubIDs.has(id)) {
    stagedDestUtubIDs.delete(id);
    row.attr("aria-selected", "false").removeClass("active");
  } else {
    stagedDestUtubIDs.add(id);
    row.attr("aria-selected", "true").addClass("active");
  }

  updateConfirmEnabled();
  log("toggle bulk copy destination", {
    id,
    staged: [...stagedDestUtubIDs],
  });
}

/**
 * Sync the Copy button's enabled state and the footer live-region count to the
 * staged set: Copy is enabled at ≥1 staged destination; the message shows the
 * "select at least one" hint at 0, a singular "1 UTub selected." at 1, and the
 * plural "{n} UTubs selected." otherwise. Count-only / XSS-safe (`.text()`).
 */
function updateConfirmEnabled(): void {
  const mount = $(PICKER_MOUNT_SELECTOR);
  const stagedCount = stagedDestUtubIDs.size;
  mount.find(CONFIRM_BTN_SELECTOR).prop("disabled", stagedCount === 0);

  let message: string;
  if (stagedCount === 0) {
    message = APP_CONFIG.strings.URL_BULK_COPY_SELECT_DESTINATION;
  } else if (stagedCount === 1) {
    message = APP_CONFIG.strings.URL_BULK_COPY_ONE_SELECTED;
  } else {
    message = APP_CONFIG.strings.URL_BULK_COPY_N_SELECTED.replace(
      "{n}",
      String(stagedCount),
    );
  }
  mount.find(MESSAGE_SELECTOR).text(message);
}

// --- Keyboard handling (capture-phase keydown + keyup on the mount) -----------

function attachKeyListeners(): void {
  const mountElement = $(PICKER_MOUNT_SELECTOR)[0];
  if (!mountElement) return;
  keydownListener = handleMountKeydown;
  keyupListener = handleMountKeyup;
  // Capture phase for keydown so Escape is swallowed before it reaches the
  // document-level multi-select-exit handler (mirrors bulk-tag.ts).
  mountElement.addEventListener("keydown", keydownListener, { capture: true });
  mountElement.addEventListener("keyup", keyupListener);
}

function detachKeyListeners(): void {
  const mountElement = $(PICKER_MOUNT_SELECTOR)[0];
  if (mountElement) {
    if (keydownListener) {
      mountElement.removeEventListener("keydown", keydownListener, {
        capture: true,
      });
    }
    if (keyupListener) {
      mountElement.removeEventListener("keyup", keyupListener);
    }
  }
  keydownListener = null;
  keyupListener = null;
}

/**
 * Keydown: Escape closes the picker (single-stage — no inner dropdown to close
 * first, unlike the tag combobox); ArrowUp/ArrowDown rove focus across enabled
 * rows; Space is prevent-defaulted here (keydown is where the page-scroll-on-
 * Space happens — keyup alone cannot suppress it). Staging itself happens on
 * keyup, never here.
 */
function handleMountKeydown(event: KeyboardEvent): void {
  switch (event.key) {
    case KEYS.ESCAPE: {
      event.stopPropagation();
      event.preventDefault();
      if (submitInFlight) return;
      closeAndResetPicker({ returnFocus: true });
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
      // Suppress the page's default scroll-on-Space ONLY when a destination
      // option row is focused (the paired keyup stages it). Space on the footer
      // Cancel/Copy buttons must keep its native button-activation behaviour, so
      // never preventDefault there.
      const target = event.target as HTMLElement | null;
      if (target && $(target).closest(OPTION_SELECTOR).length > 0) {
        event.preventDefault();
      }
      return;
    }
    default:
      return;
  }
}

/**
 * Keyup: Enter or Space on the currently-focused enabled row toggles its staged
 * state (mirrors the .UTubSelector keyup-stage idiom, extended to Space since
 * toggling here is an action, not navigation). Disabled rows never toggle.
 */
function handleMountKeyup(event: KeyboardEvent): void {
  if (event.key !== KEYS.ENTER && event.key !== KEYS.SPACE) return;
  const target = event.target as HTMLElement | null;
  if (target === null) return;
  const row = $(target).closest(OPTION_SELECTOR);
  if (row.length === 0 || row.hasClass("disabled")) return;
  toggleRow(row);
}

// --- Confirm (Copy) -----------------------------------------------------------

/**
 * Commit the staged copy: disable the buttons, post the transient "Copying…"
 * message + a delayed spinner, then POST the snapshot to the destination. The
 * copy lands in a NON-active UTub, so nothing in the active deck's store is
 * patched — the result banner + per-card cues are the only feedback.
 */
function submitCopy(): void {
  if (submitInFlight) return;
  if (stagedDestUtubIDs.size === 0 || currentSourceUtubID === null) return;

  const destIDs = [...stagedDestUtubIDs];
  const sourceUtubID = currentSourceUtubID;
  const snapshot = [...currentSnapshot];
  const mount = $(PICKER_MOUNT_SELECTOR);
  const cancelBtn = mount.find(CANCEL_BTN_SELECTOR);
  const confirmBtn = mount.find(CONFIRM_BTN_SELECTOR);
  const message = mount.find(MESSAGE_SELECTOR);

  submitInFlight = true;
  cancelBtn.prop("disabled", true);
  confirmBtn.prop("disabled", true);
  loadingTimeoutID = window.setTimeout(() => {
    confirmBtn.addClass(SUBMIT_LOADING_CLASS);
  }, SHOW_LOADING_ICON_AFTER_MS);
  message.text(APP_CONFIG.strings.URL_BULK_COPY_SUBMITTING);

  log("submit bulk copy", { sourceUtubID, destIDs, snapshot });

  // ONE batch request to the multi-destination endpoint (DD-2): source + the
  // full destination list travel in the body (no path param). The explicit 90s
  // timeout (DD-5) bounds the worst case — MAX_BULK_COPY_DESTINATIONS(25) ×
  // MAX_BULK_COPY_URLS(100) = 2,500 row-copies in ONE transaction — well above
  // the 35s single-row precedent.
  const request = ajaxCall(
    "post",
    APP_CONFIG.routes.copyURLsToUtubs,
    { sourceUtubId: sourceUtubID, destUtubIds: destIDs, utubUrlIds: snapshot },
    90000,
  );

  request.done(function (
    response: CopyUrlsResponse,
    _: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status !== 200) return;
    // Bail if the active UTub changed while the request was in flight — the
    // banner + cues target the SOURCE deck, which is no longer showing.
    if (getState().activeUTubID !== sourceUtubID) return;
    handleCopySuccess({ response, snapshot });
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    handleCopyFail({ xhr, sourceUtubID });
  });

  request.always(function () {
    submitInFlight = false;
    if (loadingTimeoutID !== null) {
      clearTimeout(loadingTimeoutID);
      loadingTimeoutID = null;
    }
    const stillMountedConfirm = $(PICKER_MOUNT_SELECTOR).find(
      CONFIRM_BTN_SELECTOR,
    );
    stillMountedConfirm
      .removeClass(SUBMIT_LOADING_CLASS)
      .prop("disabled", false);
    $(PICKER_MOUNT_SELECTOR).find(CANCEL_BTN_SELECTOR).prop("disabled", false);
  });
}

function handleCopySuccess({
  response,
  snapshot,
}: {
  response: CopyUrlsResponse;
  snapshot: number[];
}): void {
  const results = response.results;
  // Destinations that actually received ≥1 copy, and destinations skipped whole
  // because they were locked at write time (DD-8/DD-13). Both feed the banner;
  // lockedCount also gates the per-card cue decision below.
  const destsSucceeded = results.filter(
    (result) => result.status === "ok" && result.copied.length > 0,
  ).length;
  const lockedCount = results.filter(
    (result) => result.status === "locked",
  ).length;

  // Per-card cue (single flashCardResultCues call; DD-13): suppress ONLY when
  // nothing copied into ANY destination AND at least one targeted destination
  // was lock-blocked — never paint a misleading amber "Already there" cue when
  // the real cause was a lock, not a duplicate. Otherwise flash green-if-any:
  // a source id copied into ≥1 destination gets "Copied", else "Already there".
  if (!(destsSucceeded === 0 && lockedCount > 0)) {
    const copiedSourceIDs = new Set<number>();
    results
      .filter((result) => result.status === "ok")
      .forEach((result) =>
        result.copied.forEach((entry) =>
          copiedSourceIDs.add(entry.sourceUtubUrlID),
        ),
      );

    const cues = snapshot.map((sourceUtubUrlID) =>
      copiedSourceIDs.has(sourceUtubUrlID)
        ? {
            utubUrlID: sourceUtubUrlID,
            variant: "copied" as const,
            label: APP_CONFIG.strings.URL_BULK_CARD_COPIED,
          }
        : {
            utubUrlID: sourceUtubUrlID,
            variant: "skipped" as const,
            label: APP_CONFIG.strings.URL_BULK_CARD_ALREADY_THERE,
          },
    );
    flashCardResultCues({ cues });
  }

  renderCopyResultBanner({
    destsSucceeded,
    lockedCount,
    destsTargeted: results.length,
    totalCopied: response.totalCopied,
    totalSkipped: response.totalSkipped,
  });

  closeAndResetPicker({ returnFocus: true });
}

function handleCopyFail({
  xhr,
  sourceUtubID,
}: {
  xhr: JQuery.jqXHR;
  sourceUtubID: number;
}): void {
  if (is429Handled(xhr)) return;

  if (!("responseJSON" in xhr)) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // CSRF token expired → the server returned the login/forbidden HTML page.
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  switch (xhr.status) {
    case 400: {
      // A message-level 400 is a stale/foreign selection (URL_NOT_IN_UTUB /
      // same-UTub / invalid source id) OR a destination-list validation failure
      // (empty / over-cap / invalid destUtubIds). Either way, surface the
      // concise fail banner (count-free copy) and close the picker so the user
      // re-selects. Bail if the active UTub changed mid-flight — the banner
      // targets the SOURCE deck, which is no longer showing (mirrors the
      // success guard).
      if (getState().activeUTubID !== sourceUtubID) return;
      renderCopyResultBanner({
        destsSucceeded: 0,
        lockedCount: 0,
        destsTargeted: 0,
        totalCopied: 0,
        totalSkipped: 0,
        forceFail: true,
      });
      closeAndResetPicker({ returnFocus: true });
      break;
    }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

// --- Result banner (concise COUNT ONLY — never a URL title / dest name) --------

/**
 * Render the aggregated multi-destination result banner in
 * `#bulkCopyResultBanner`, keyed on how many destinations succeeded, how many
 * were lock-skipped, and the total copied/skipped counts. Singular vs `_MULTI`
 * wording is chosen by the SUCCESS count (destsSucceeded===1) — except the
 * pure all-duplicate branch, which keys off destinations TARGETED
 * (destsTargeted===1, DD-14) since no destination succeeded there. States:
 *   - hard failure (forceFail)                         → fail/assertive
 *   - all duplicates, no locks (totalCopied===0)       → partial/polite   NONE_NEW
 *   - all picked destinations locked, nothing copied   → fail/assertive
 *   - some copied + some locked                        → partial/assertive SOME_LOCKED
 *   - mixed duplicates, no locks (totalSkipped>0)      → partial/polite   _PARTIAL
 *   - all clean                                        → success/polite
 * The banner is a concise COUNT ONLY — it MUST NOT echo any URL title or
 * destination UTub name (XSS-safe; the per-card cues carry the which — DD-19).
 */
function renderCopyResultBanner({
  destsSucceeded,
  lockedCount,
  destsTargeted,
  totalCopied,
  totalSkipped,
  forceFail = false,
}: {
  destsSucceeded: number;
  lockedCount: number;
  destsTargeted: number;
  totalCopied: number;
  totalSkipped: number;
  forceFail?: boolean;
}): void {
  const banner = $(BANNER_SELECTOR);
  banner.empty().removeClass("hidden success partial fail");

  let variant: string;
  let glyph: string;
  let ariaLive: string;
  let text: string;

  if (forceFail) {
    variant = "fail";
    glyph = "🚫";
    ariaLive = "assertive";
    text = APP_CONFIG.strings.UNABLE_TO_COPY_URLS;
  } else if (totalCopied === 0 && lockedCount === 0) {
    // Nothing copied and nothing locked → every selected URL was already in
    // every chosen destination. Singular vs plural keys off destsTargeted.
    variant = "partial";
    glyph = "ℹ️";
    ariaLive = "polite";
    text =
      destsTargeted === 1
        ? APP_CONFIG.strings.URLS_COPY_NONE_NEW
        : APP_CONFIG.strings.URLS_COPY_MULTI_NONE_NEW;
  } else if (lockedCount > 0 && destsSucceeded === 0) {
    // Nothing copied AND everything the user picked was locked → surface as a
    // failure (there is no success to report).
    variant = "fail";
    glyph = "🚫";
    ariaLive = "assertive";
    text = APP_CONFIG.strings.UNABLE_TO_COPY_URLS;
  } else if (lockedCount > 0) {
    // Some destinations copied, some were locked → assertive partial.
    variant = "partial";
    glyph = "ℹ️";
    ariaLive = "assertive";
    text =
      destsSucceeded === 1
        ? APP_CONFIG.strings.URLS_COPIED_SOME_LOCKED.replace(
            "{locked}",
            String(lockedCount),
          )
        : APP_CONFIG.strings.URLS_COPIED_MULTI_SOME_LOCKED.replace(
            "{n}",
            String(destsSucceeded),
          ).replace("{locked}", String(lockedCount));
  } else if (totalSkipped > 0) {
    // Some copied, some duplicate-skipped, no locks → polite partial.
    variant = "partial";
    glyph = "ℹ️";
    ariaLive = "polite";
    text =
      destsSucceeded === 1
        ? APP_CONFIG.strings.URLS_COPIED_PARTIAL.replace(
            "{copied}",
            String(totalCopied),
          ).replace("{skipped}", String(totalSkipped))
        : APP_CONFIG.strings.URLS_COPIED_MULTI_PARTIAL.replace(
            "{n}",
            String(destsSucceeded),
          ).replace("{skipped}", String(totalSkipped));
  } else {
    // All clean — everything copied into every destination, no skips, no locks.
    variant = "success";
    glyph = "✅";
    ariaLive = "polite";
    text =
      destsSucceeded === 1
        ? APP_CONFIG.strings.URLS_COPIED
        : APP_CONFIG.strings.URLS_COPIED_MULTI.replace(
            "{n}",
            String(destsSucceeded),
          );
  }

  // `.text()` escapes the whole string.
  const icon = $(document.createElement("span"))
    .addClass("bulkTagBannerIcon")
    .attr({ "aria-hidden": "true" })
    .text(glyph);
  const body = $(document.createElement("div"))
    .addClass("bulkTagBannerBody")
    .text(text);

  banner
    .addClass(variant)
    .attr("aria-live", ariaLive)
    .append(icon)
    .append(body);
}
