import type { SuccessResponse } from "../../types/api-helpers.d.ts";
import type { PanelId } from "../../types/settings.js";
import { resolveUtubSettings } from "../../types/settings.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { debug } from "../../lib/debug.js";
import { getState, setState } from "../../store/app-store.js";
import { removeUTubLocally } from "../utubs/remove-local.js";
import { fetchUTubForRefresh } from "../utubs/selectors.js";
import { showURLDeckBannerError } from "../urls/deck.js";
import type { SaveResult, SectionPatch } from "./types.js";

const log = debug("panel-settings");

/** ajaxCall's 1000ms default is too short for a write. */
export const PATCH_TIMEOUT_MS = 10000;

type UpdateSettingsResponse = SuccessResponse<"updateUtubSettings">;

interface ErrorBody {
  message?: string;
}

/** The failure half of `SaveResult`: never `ok`, never `stale`. */
export type FailedSaveResult = Exclude<
  SaveResult,
  { outcome: "ok" } | { outcome: "stale" }
>;

// Clear, then set on the next tick, so a repeated identical message is
// re-announced by the polite live region.
function announceOnNextTick({
  selector,
  message,
}: {
  selector: string;
  message: string;
}): void {
  $(selector).text("");
  setTimeout(() => $(selector).text(message), 0);
}

/**
 * The UTub-removed handling shared by `patchUtubSettings` (scope 'utub') and the
 * queue (per-utub user sections): the same three steps
 * `updateUTubOnFindingStaleData` runs inline when a refresh finds the UTub gone.
 */
export function handleActiveUTubGone({ utubID }: { utubID: number }): void {
  removeUTubLocally({ utubID });
  showURLDeckBannerError(APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE);
  announceOnNextTick({
    selector: "#MobilePanelAnnouncement",
    message: APP_CONFIG.strings.UTUB_NO_LONGER_AVAILABLE,
  });
}

function isHtmlOrNonJson(xhr: JQuery.jqXHR): boolean {
  const contentType = xhr.getResponseHeader("Content-Type") ?? "";
  return contentType.includes("text/html") || !xhr.responseJSON;
}

function hasPanelSettings({
  response,
  panel,
}: {
  response: unknown;
  panel: PanelId;
}): boolean {
  if (typeof response !== "object" || response === null) return false;
  const settings = (response as { settings?: unknown }).settings;
  if (typeof settings !== "object" || settings === null) return false;
  const panelSettings = (settings as Record<string, unknown>)[panel];
  return typeof panelSettings === "object" && panelSettings !== null;
}

/**
 * Maps a failed request to a `SaveResult` outcome, free of store and removal
 * side effects (the 429 branch still runs the existing `is429Handled` message
 * handler). Never returns `stale`.
 */
export function mapXhrToSaveOutcome(xhr: JQuery.jqXHR): FailedSaveResult {
  if (is429Handled(xhr)) return { outcome: "error", resync: false };

  switch (xhr.status) {
    case 403: {
      // A CSRF 403 is HTML-bodied: roll back, never flip read-only.
      if (isHtmlOrNonJson(xhr)) return { outcome: "error" };
      const message = (xhr.responseJSON as ErrorBody).message;
      if (message === APP_CONFIG.strings.UTUB_IS_LOCKED) {
        return { outcome: "locked" };
      }
      if (message === APP_CONFIG.strings.NOT_AUTHORIZED) {
        return { outcome: "forbidden" };
      }
      return { outcome: "error" };
    }
    case 404:
      // A proxy / stale-deploy HTML 404 says nothing about this UTub.
      if (isHtmlOrNonJson(xhr)) return { outcome: "error" };
      return { outcome: "gone" };
    case 400:
      return { outcome: "invalid" };
    default:
      return { outcome: "error" };
  }
}

/** PATCHes one panel's settings of a UTub; the body is `{ [panel]: patch }`. */
export function patchUtubSettings({
  utubID,
  panel,
  patch,
}: {
  utubID: number;
  panel: PanelId;
  patch: SectionPatch;
}): Promise<SaveResult> {
  return new Promise<SaveResult>((resolve) => {
    const request = ajaxCall(
      "patch",
      APP_CONFIG.routes.updateUTubSettings(utubID),
      { [panel]: patch },
      PATCH_TIMEOUT_MS,
    );

    request.done((response: UpdateSettingsResponse) => {
      // Stale guard: no store or UI effect for a UTub that is no longer active.
      if (getState().activeUTubID !== utubID) {
        resolve({ outcome: "stale", failed: false });
        return;
      }
      // A 200 that is not the app's JSON (e.g. a followed login redirect) must
      // never overwrite the slice with defaults or report "saved".
      if (!hasPanelSettings({ response, panel })) {
        log("patchUtubSettings — malformed 200 body", { utubID, panel });
        resolve({ outcome: "error" });
        return;
      }
      // Merge only the PATCHed panel key so parallel sections of other panels
      // cannot revert each other; bump the version in the same setState.
      const incoming = resolveUtubSettings(response.settings);
      const current = getState();
      const merged = current.settings
        ? { ...current.settings, [panel]: incoming[panel] }
        : incoming;
      setState({
        settings: merged,
        settingsVersion: current.settingsVersion + 1,
      });
      resolve({ outcome: "ok", settings: merged });
    });

    request.fail((xhr: JQuery.jqXHR) => {
      if (getState().activeUTubID !== utubID) {
        resolve({ outcome: "stale", failed: true });
        return;
      }
      const result = mapXhrToSaveOutcome(xhr);
      if (result.outcome === "gone") handleActiveUTubGone({ utubID });
      resolve(result);
    });
  });
}

/**
 * Re-fetches the UTub and writes only `settings` (whole slice, no version
 * bump). Retries once when another section's 200 trips the version guard.
 * Resolves true only when it wrote the slice.
 */
export async function resyncSettings({
  utubID,
}: {
  utubID: number;
}): Promise<boolean> {
  const MAX_ATTEMPTS = 2;
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    if (getState().activeUTubID !== utubID) {
      log("resyncSettings — active UTub changed, skipping", { utubID });
      return false;
    }
    const capturedVersion = getState().settingsVersion;

    const result = await fetchUTubForRefresh({ utubID });
    if (result.kind !== "ok") {
      log("resyncSettings — re-fetch failed", { utubID, kind: result.kind });
      return false;
    }
    if (getState().activeUTubID !== utubID) {
      log("resyncSettings — active UTub changed mid-flight", { utubID });
      return false;
    }
    if (getState().settingsVersion !== capturedVersion) {
      log("resyncSettings — settings saved mid-flight, retrying", {
        utubID,
        attempt,
      });
      continue;
    }
    setState({ settings: resolveUtubSettings(result.data.settings) });
    return true;
  }
  log("resyncSettings — guard tripped again, giving up", { utubID });
  return false;
}
