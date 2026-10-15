/**
 * Refresh-on-focus trigger for the selected UTub.
 *
 * When the user returns to the tab (visibilitychange -> visible, or a window
 * focus), re-fetches the selected UTub in the background and applies it through
 * `updateUTubOnFindingStaleData({ isBackgroundRefresh: true })`, at most once per
 * `UTUB_REFRESH_MIN_INTERVAL_MS` and only when the user is not busy on the home
 * page (open form/modal/picker/panel, multi-select, in-flight submit, cross-UTub
 * search). The debounce clock advances at dispatch; a busy check on the response
 * (`shouldApply`) discards the payload and rolls the clock back.
 *
 * Lives outside `home/visibility.ts` on purpose: importing the UTub modules there
 * would add a cycle via btns-forms.ts -> utubs/deck.ts -> selectors.ts.
 *
 * Returns a disposer that unbinds every listener this module added.
 */

import { AppEvents, on } from "../../lib/event-bus.js";
import { $ } from "../../lib/globals.js";
import { debug } from "../../lib/debug.js";
import { getOpenForm } from "../../lib/modal-tracking.js";
import { getState } from "../../store/app-store.js";
import { isTransferPickerOpen } from "../members/transfer-picker.js";
import { isCrossUtubSearchActive } from "../search/cross-utub-search.js";
import { isTagSheetOpen } from "../tags/sheet.js";
import { isAnyBulkPickerOpen } from "../urls/bulk-actions/picker-guard.js";
import { isBulkCopySubmitInFlight } from "../urls/bulk-actions/bulk-copy.js";
import { isBulkDeleteSubmitInFlight } from "../urls/bulk-actions/bulk-delete.js";
import { isBulkTagSubmitInFlight } from "../urls/bulk-actions/bulk-tag.js";
import { isURLStringSubmitInFlight } from "../urls/cards/update-string.js";
import { isURLTitleSubmitInFlight } from "../urls/cards/update-title.js";
import { isUTubDescriptionSubmitInFlight } from "../urls/update-description.js";
import { isUTubNameSubmitInFlight } from "../urls/update-name.js";
import { updateUTubOnFindingStaleData } from "./stale-data.js";
import { isUTubSelected } from "./utils.js";

const log = debug("utubs");

export const UTUB_REFRESH_MIN_INTERVAL_MS = 30_000;

const FOCUS_EVENT = "focus.utubRefresh";

// performance.now() timestamp of the last dispatch (or seed).
let lastRefreshAt = 0;
let refreshInFlight = false;
let activeDisposer: (() => void) | null = null;

// Matches jQuery's `:visible` for the block wrappers checked here (display:none
// gives a zero size), without the pseudo-selector: jsdom resolves `:visible`
// natively and ignores jQuery's definition.
function hasRenderedElement(selector: string): boolean {
  return $(selector)
    .toArray()
    .some(
      (element) =>
        element instanceof HTMLElement &&
        (element.offsetWidth > 0 || element.offsetHeight > 0),
    );
}

// Fail closed: any uncertainty counts as busy. There is no global AJAX gate;
// in-flight work is covered by `refreshInFlight` plus the per-feature flags.
export function isUserBusyOnHome(): boolean {
  return (
    getOpenForm() !== null ||
    isAnyBulkPickerOpen() ||
    isTransferPickerOpen() ||
    getState().multiSelectMode ||
    $("#confirmModal").hasClass("show") ||
    $("#MemberDeck").hasClass("member-add-open") ||
    $(".updateUrlTitleWrap:not(.hidden)").length > 0 ||
    $(".updateUrlStringWrap:not(.hidden)").length > 0 ||
    hasRenderedElement(".urlTagComboboxWrap") ||
    hasRenderedElement("#createURLWrap") ||
    hasRenderedElement("#createUTubTagWrap") ||
    $("#URLDeckHeader").hasClass("hidden") ||
    $("#URLDeckSubheader").hasClass("hidden") ||
    !$("#utubEditPanelClose").hasClass("hidden") ||
    isTagSheetOpen() ||
    isURLTitleSubmitInFlight() ||
    isURLStringSubmitInFlight() ||
    isUTubNameSubmitInFlight() ||
    isUTubDescriptionSubmitInFlight() ||
    isBulkTagSubmitInFlight() ||
    isBulkDeleteSubmitInFlight() ||
    isBulkCopySubmitInFlight() ||
    isCrossUtubSearchActive()
  );
}

export function initUTubRefreshOnFocus({
  minIntervalMs = UTUB_REFRESH_MIN_INTERVAL_MS,
}: { minIntervalMs?: number } = {}): () => void {
  // Re-init replaces the previous binding instead of stacking listeners.
  if (activeDisposer !== null) {
    activeDisposer();
  }

  lastRefreshAt = performance.now();
  refreshInFlight = false;

  const handleReturn = async (): Promise<void> => {
    if (document.visibilityState !== "visible") return;

    const utubID = getState().activeUTubID;
    if (
      !isUTubSelected() ||
      utubID === null ||
      refreshInFlight ||
      isUserBusyOnHome()
    ) {
      return;
    }

    if (performance.now() - lastRefreshAt < minIntervalMs) return;

    // The clock advances at dispatch, so a slow response never lengthens the
    // debounce window.
    const previousRefreshAt = lastRefreshAt;
    lastRefreshAt = performance.now();
    refreshInFlight = true;

    const shouldApply = (): boolean => {
      if (isUserBusyOnHome()) {
        lastRefreshAt = previousRefreshAt;
        return false;
      }
      return true;
    };

    try {
      await updateUTubOnFindingStaleData({
        utubID,
        isBackgroundRefresh: true,
        shouldApply,
      });
    } catch (error) {
      log("refresh-on-focus — background refresh failed, ignoring", {
        utubID,
        error,
      });
    } finally {
      refreshInFlight = false;
    }
  };

  const onReturn = (): void => {
    void handleReturn();
  };

  document.addEventListener("visibilitychange", onReturn);
  $(window).on(FOCUS_EVENT, onReturn);
  const offUTubSelected = on(AppEvents.UTUB_SELECTED, () => {
    lastRefreshAt = performance.now();
  });

  const disposer = (): void => {
    document.removeEventListener("visibilitychange", onReturn);
    $(window).off(FOCUS_EVENT, onReturn);
    offUTubSelected();
    if (activeDisposer === disposer) {
      activeDisposer = null;
    }
  };
  activeDisposer = disposer;
  return disposer;
}

export function _resetUTubRefreshOnFocusForTests(): void {
  if (activeDisposer !== null) {
    activeDisposer();
  }
  lastRefreshAt = 0;
  refreshInFlight = false;
}
