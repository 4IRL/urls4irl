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

type CopyUrlsResponse = SuccessResponse<"copyUrlsToUtub">;

const PICKER_MOUNT_SELECTOR = "#bulkCopyPickerMount";
const BANNER_SELECTOR = "#bulkCopyResultBanner";
const DECK_SELECTOR = "#URLDeck";
const PICKER_OPEN_CLASS = "bulkCopyPickerOpen";
// Stable in-mode focus-return anchor (the header Exit control) — never the
// ephemeral #bulkActionButtons button, which rebuilds on every selection change.
const FOCUS_RETURN_SELECTOR = "#bulkSelectExit";
const OPTION_SELECTOR = '.UTubSelector[role="option"]';
const ENABLED_OPTION_SELECTOR = '.UTubSelector[role="option"]:not(.disabled)';
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
let stagedDestUtubID: number | null = null;
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
  stagedDestUtubID = null;
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
 * Build and mount the picker markup: a `role="listbox"` mount holding the
 * destination `role="option"` rows (roving tabindex) plus a footer (message,
 * Cancel, Copy). When every other UTub is locked, an accessible all-locked
 * message replaces the rows and Copy stays disabled (DD-18).
 */
function renderPicker({
  destinations,
  selectedCount,
}: {
  destinations: UtubSummaryItem[];
  selectedCount: number;
}): void {
  const mount = $(PICKER_MOUNT_SELECTOR);
  mount.empty();
  mount.attr({
    role: "listbox",
    "aria-label": APP_CONFIG.strings.URL_BULK_COPY_ARIA.replace(
      "{n}",
      String(selectedCount),
    ),
  });

  const enabledDestinations = destinations.filter((utub) => !utub.isLocked);

  if (enabledDestinations.length === 0) {
    // Every other UTub is locked — no focusable destination row. Render an
    // announced message and focus it; Copy stays disabled (DD-18).
    const allLocked = $(document.createElement("div"))
      .addClass("bulkCopyAllLocked")
      .attr({ role: "status", "aria-live": "polite", tabindex: "-1" })
      .text(APP_CONFIG.strings.URL_BULK_COPY_ALL_LOCKED);
    mount.append(allLocked);
    mount.append(buildFooter());
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

    row.append(
      $(document.createElement("b")).addClass("UTubName").text(utub.name),
    );
    // Row click stages the destination (never fires the copy).
    row.on("click.bulkCopyStage", () => {
      if (row.hasClass("disabled")) return;
      stageRow(row);
    });
    mount.append(row);
  });

  mount.append(buildFooter());
  attachKeyListeners();
  mount.removeClass("hidden");

  // Focus the first enabled row (real DOM focus — DD-7).
  const firstEnabled = mount.find(ENABLED_OPTION_SELECTOR).first();
  firstEnabled[0]?.focus();
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
  stagedDestUtubID = null;
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
 * Stage a destination row: move roving focus to it FIRST (so a click on a row
 * that did not already hold focus never leaves tabindex/focus on a stale row),
 * then record the staged id, mark it `aria-selected`/`.active` (clearing any
 * previously-staged row), and enable the Copy button.
 */
function stageRow(row: JQuery): void {
  const rowEl = row[0];
  if (!rowEl) return;
  setActiveRow(rowEl);

  const mount = $(PICKER_MOUNT_SELECTOR);
  mount
    .find(OPTION_SELECTOR)
    .attr("aria-selected", "false")
    .removeClass("active");
  row.attr("aria-selected", "true").addClass("active");

  stagedDestUtubID = parseInt(row.attr("utubid") ?? "", 10);
  mount.find(CONFIRM_BTN_SELECTOR).prop("disabled", false);
  log("stage bulk copy destination", { stagedDestUtubID });
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
 * Keyup: Enter or Space on the currently-focused enabled row stages it (mirrors
 * the .UTubSelector keyup-stage idiom, extended to Space since staging here is
 * an action, not navigation). Disabled rows never stage.
 */
function handleMountKeyup(event: KeyboardEvent): void {
  if (event.key !== KEYS.ENTER && event.key !== KEYS.SPACE) return;
  const target = event.target as HTMLElement | null;
  if (target === null) return;
  const row = $(target).closest(OPTION_SELECTOR);
  if (row.length === 0 || row.hasClass("disabled")) return;
  stageRow(row);
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
  if (stagedDestUtubID === null || currentSourceUtubID === null) return;

  const destUtubID = stagedDestUtubID;
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

  log("submit bulk copy", { sourceUtubID, destUtubID, snapshot });

  const request = ajaxCall(
    "post",
    APP_CONFIG.routes.copyURLsToUtub(destUtubID),
    { sourceUtubId: sourceUtubID, utubUrlIds: snapshot },
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
    handleCopySuccess({ response });
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

function handleCopySuccess({ response }: { response: CopyUrlsResponse }): void {
  const copiedCount = response.copied.length;
  const skippedCount = response.skipped.length;

  renderCopyResultBanner({ copiedCount, skippedCount });

  // Per-card cues on the SOURCE deck: "Copied" (green) for each copied source
  // row, "Already there" (amber) for each skipped duplicate. Keyed on the source
  // Utub_Urls id (copied[].sourceUtubUrlID / skipped[].utubUrlID).
  flashCardResultCues({
    cues: [
      ...response.copied.map((entry) => ({
        utubUrlID: entry.sourceUtubUrlID,
        variant: "copied",
        label: APP_CONFIG.strings.URL_BULK_CARD_COPIED,
      })),
      ...response.skipped.map((entry) => ({
        utubUrlID: entry.utubUrlID,
        variant: "skipped",
        label: APP_CONFIG.strings.URL_BULK_CARD_ALREADY_THERE,
      })),
    ],
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
      // The only message-level 400 is a stale/foreign selection
      // (URL_NOT_IN_UTUB / same-UTub / invalid id). Surface the concise fail
      // banner (count-free copy) and close the picker so the user re-selects.
      // Bail if the active UTub changed mid-flight — the banner targets the
      // SOURCE deck, which is no longer showing (mirrors the success guard).
      if (getState().activeUTubID !== sourceUtubID) return;
      renderCopyResultBanner({
        copiedCount: 0,
        skippedCount: 0,
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
 * Render the result banner in `#bulkCopyResultBanner`. Four states:
 *   - all-copied (skipped=0, copied>0) → success/polite  (URLS_COPIED)
 *   - mixed (copied>0, skipped>0)      → partial/polite   (URLS_COPIED_PARTIAL)
 *   - all-skipped (copied=0)           → partial/polite   (URLS_COPY_NONE_NEW)
 *   - hard failure (forceFail)         → fail/assertive   (UNABLE_TO_COPY_URLS)
 * The banner is a concise COUNT ONLY — it MUST NOT echo any URL title or
 * destination UTub name (XSS-safe; the per-card cues carry the which — DD-19).
 */
function renderCopyResultBanner({
  copiedCount,
  skippedCount,
  forceFail = false,
}: {
  copiedCount: number;
  skippedCount: number;
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
  } else if (copiedCount > 0 && skippedCount === 0) {
    variant = "success";
    glyph = "✅";
    ariaLive = "polite";
    text = APP_CONFIG.strings.URLS_COPIED;
  } else if (copiedCount > 0) {
    variant = "partial";
    glyph = "ℹ️";
    ariaLive = "polite";
    text = APP_CONFIG.strings.URLS_COPIED_PARTIAL.replace(
      "{copied}",
      String(copiedCount),
    ).replace("{skipped}", String(skippedCount));
  } else {
    // copiedCount === 0 → every selected URL was already in the destination.
    variant = "partial";
    glyph = "ℹ️";
    ariaLive = "polite";
    text = APP_CONFIG.strings.URLS_COPY_NONE_NEW;
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
