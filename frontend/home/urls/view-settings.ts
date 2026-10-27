import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { getState } from "../../store/app-store.js";
import { announceSettingsStatus } from "../panel-settings/announce.js";
import { fetchUTubForRefresh } from "../utubs/selectors.js";
import { applyServerUrlOrder } from "./deck.js";
import type {
  DensityValue,
  SortOrderValue,
  ViewModeValue,
} from "../../types/preferences.js";

// The member's per-UTub override when a UTub is selected and one is set, else the
// Display preference. With no UTub selected the preference always applies.

export function effectiveSort(): SortOrderValue {
  const { activeUTubID, memberSettings, preferences } = getState();
  if (activeUTubID === null) return preferences.defaultSort;
  return memberSettings?.urls.sort ?? preferences.defaultSort;
}

export function effectiveViewMode(): ViewModeValue {
  const { activeUTubID, memberSettings, preferences } = getState();
  if (activeUTubID === null) return preferences.defaultView;
  return memberSettings?.urls.view_mode ?? preferences.defaultView;
}

export function effectiveDensity(): DensityValue {
  const { activeUTubID, memberSettings, preferences } = getState();
  if (activeUTubID === null) return preferences.density;
  return memberSettings?.urls.density ?? preferences.density;
}

const log = debug("urls-view-settings");

// Incremented at each order-sync issue; only the latest request may apply.
let latestOrderSyncRequest = 0;

/**
 * Reorders the open deck to the server's order for the current effective sort.
 * An explicit call (not the background refresh), so a busy user does not block
 * it. A response is dropped unless it is the latest request, the UTub is still
 * active and the effective sort is unchanged since the request was issued
 * (`memberSettingsVersion` is deliberately not a guard: an unrelated personal
 * save must not drop a valid order). A failed refresh keeps the saved sort and
 * announces a notice.
 */
export async function syncDeckOrderToServer(): Promise<void> {
  const utubID = getState().activeUTubID;
  if (utubID === null) return;
  const requestedSort = effectiveSort();
  latestOrderSyncRequest += 1;
  const requestID = latestOrderSyncRequest;

  const result = await fetchUTubForRefresh({ utubID });

  if (
    requestID !== latestOrderSyncRequest ||
    getState().activeUTubID !== utubID ||
    effectiveSort() !== requestedSort
  ) {
    log("order sync response dropped by guard", { utubID, requestID });
    return;
  }
  if (result.kind !== "ok") {
    log("order sync refresh failed", { utubID, kind: result.kind });
    announceSettingsStatus({
      message:
        APP_CONFIG.strings.URLS_PERSONAL_SETTINGS_SORT_ORDER_PENDING_NOTICE,
    });
    return;
  }
  applyServerUrlOrder(result.data.urls);
}

/** True when the member hides the date for the active UTub. */
export function effectiveHideDateAdded(): boolean {
  const { activeUTubID, memberSettings } = getState();
  if (activeUTubID === null) return false;
  return memberSettings?.urls.hide_date_added ?? false;
}
