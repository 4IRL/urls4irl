/**
 * Data-export controller for the settings page (Privacy & Data tab).
 *
 * Drives the "Export my data" button (`#SettingsExportDataBtn`) rendered by Jinja
 * in `pages/settings.html`. Export is a non-destructive read: a `fetch`→Blob JSON
 * download of every UTub the user belongs to, plus their account fields. Unlike
 * the modal-driven removal controllers, this is a plain in-page button that
 * keyboard/screen-reader users Tab to directly — so the in-flight guard uses a
 * module-level flag + `aria-disabled`/`aria-busy` (DD-20) rather than the native
 * `disabled` attribute (which would drop the button from the tab order and jump
 * focus to `<body>` mid-fetch).
 *
 * Why raw `fetch` and not `ajaxCall` (DD-5/DD-7): `ajaxCall`'s 1000 ms timeout +
 * JSON-only shape would abort a large export, and a raw `fetch` never runs through
 * `csrf.ts`'s `$.ajaxPrefilter`, so this controller owns its own 429 handling
 * (mirroring `csrf.ts`) and its own try/catch (a raw `fetch` promise REJECTS on a
 * network/DNS/CORS failure instead of resolving with a non-ok `Response`).
 *
 * Handlers are delegated on `document` under this controller's own distinct
 * `click.dataExport` namespace (DD-1). `initDataExport()` no-ops when the Privacy
 * & Data panel container is missing (tests / other pages).
 */

import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { AppEvents, emit as emitAppEvent } from "../lib/event-bus.js";
import { emit as recordUIEvent } from "../lib/metrics-client.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import {
  clearControllerInFlight,
  isAnyOtherControllerInFlight,
  registerControllerInFlight,
} from "./removal-shared.js";

// This controller's own distinct delegated-click namespace (DD-1).
const CLICK_NAMESPACE = "click.dataExport";

const EXPORT_BTN_ID = "SettingsExportDataBtn";
const EXPORT_STATUS_ID = "SettingsExportStatus";

// The reentrancy guard (DD-20): replaces the native-`disabled` check the modal
// submit buttons get for free, since `#SettingsExportDataBtn` never receives the
// native `disabled` attribute (it must stay in the tab order).
let exportInFlight = false;

export function initDataExport(): void {
  // Key the no-op guard off the Privacy & Data panel container (the export card's
  // home), mirroring logout-everywhere's `#SettingsPanelPrivacyData` guard.
  if (document.getElementById("SettingsPanelPrivacyData") === null) return;

  $(document)
    .off(CLICK_NAMESPACE, `#${EXPORT_BTN_ID}`)
    .on(
      CLICK_NAMESPACE,
      `#${EXPORT_BTN_ID}`,
      async function (event: JQuery.ClickEvent) {
        event.preventDefault();
        await handleExportClick(event.currentTarget as HTMLButtonElement);
      },
    );
}

export function _resetDataExportForTests(): void {
  $(document).off(CLICK_NAMESPACE);
  exportInFlight = false;
  clearControllerInFlight("dataExport");
}

async function handleExportClick(buttonEl: HTMLButtonElement): Promise<void> {
  // Reentrancy guard (DD-20): ignore repeat clicks / Enter-repeats on the
  // still-focusable button while a request is already running.
  if (exportInFlight) return;

  // Cross-panel guard (DD-21), symmetric with DD-9's guard in submitDelete():
  // if account-delete is in flight, surface the notice and do not start.
  if (isAnyOtherControllerInFlight("dataExport")) {
    showStatus({
      message: APP_CONFIG.strings.SETTINGS_EXPORT_BLOCKED_BY_DELETE,
      type: "danger",
    });
    return;
  }

  const url = buttonEl.dataset.exportUrl;
  if (!url) return;

  // Mark in flight (DD-20): aria-disabled + aria-busy, never the native
  // `disabled` attribute, so the button stays in the tab order.
  exportInFlight = true;
  $(buttonEl).attr("aria-disabled", "true").attr("aria-busy", "true");
  setStatusAndAnnounce({
    message: APP_CONFIG.strings.SETTINGS_EXPORT_PREPARING,
    type: "info",
  });
  registerControllerInFlight("dataExport");
  recordUIEvent({ event: UI_EVENTS.UI_DATA_EXPORT_TRIGGERED });

  try {
    const res = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        Accept: "application/json",
      },
    });

    // Manual 429 branch (DD-5): a raw fetch never re-enters csrf.ts's prefilter,
    // so mirror its UI_RATE_LIMIT_HIT emission + HTML-page replacement.
    if (res.status === 429) {
      recordUIEvent({ event: UI_EVENTS.UI_RATE_LIMIT_HIT });
      const contentType = res.headers.get("Content-Type");
      if (contentType?.includes("text/html")) {
        showNewPageOnAJAXHTMLResponse(await res.text());
        return;
      }
    }

    if (!res.ok) {
      failExport();
      return;
    }

    const json = await res.json();
    // Defensive: a 200 whose body lacks `export` would otherwise stringify to
    // the literal "undefined" and silently download a corrupt file under a
    // success status — surface the error path instead.
    if (json?.export === undefined) {
      failExport();
      return;
    }
    const blob = new Blob([JSON.stringify(json.export, null, 2)], {
      type: "application/json",
    });
    const href = URL.createObjectURL(blob);
    const filename = `urls4irl-export-${new Date().toISOString().slice(0, 10)}.json`;
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = filename;
    anchor.click();
    // Defer the revoke so the blob URL survives long enough for the browser's
    // download task to latch it — a synchronous revoke can cancel the download
    // in some browsers (e.g. Safari).
    setTimeout(() => URL.revokeObjectURL(href), 0);

    setStatusAndAnnounce({
      message: APP_CONFIG.strings.SETTINGS_EXPORT_STARTED,
      type: "success",
    });
    settleExport();
  } catch {
    // A raw fetch REJECTS on network/DNS/CORS failure (DD-7): same end state as
    // the !res.ok branch, but reached via the catch instead of a non-ok Response.
    failExport();
  }
}

// Failure end state (DD-8/DD-9/DD-20): announce the error and release every
// in-flight marker so the button is retryable and never stuck.
function failExport(): void {
  setStatusAndAnnounce({
    message: APP_CONFIG.strings.SETTINGS_EXPORT_ERROR,
    type: "danger",
  });
  settleExport();
}

// Release the in-flight state (DD-20/DD-9): clear the reentrancy flag, the
// aria markers, and the cross-controller registration.
function settleExport(): void {
  exportInFlight = false;
  $(`#${EXPORT_BTN_ID}`).removeAttr("aria-disabled").removeAttr("aria-busy");
  clearControllerInFlight("dataExport");
}

// Update the in-panel status region AND emit the cross-tab toast event (DD-6) so
// a screen-reader user who switched away still hears the announcement.
function setStatusAndAnnounce({
  message,
  type,
}: {
  message: string;
  type: "info" | "success" | "danger";
}): void {
  showStatus({ message, type });
  emitAppEvent(AppEvents.DATA_EXPORT_STATUS_CHANGED, { message });
}

// Local status-region helper (DD-8), reusing change-username.ts's idiom extended
// with an `alert-info` variant for the preparing/started states.
function showStatus({
  message,
  type,
}: {
  message: string;
  type: "info" | "success" | "danger";
}): void {
  $(`#${EXPORT_STATUS_ID}`)
    .removeClass("d-none alert-info alert-success alert-danger")
    .addClass(`alert-${type}`)
    .text(message);
}
