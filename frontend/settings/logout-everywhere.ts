/**
 * "Log out everywhere" controller for the settings page (Privacy & Data tab).
 *
 * Drives the non-destructive session-revocation modal
 * (`#SettingsLogoutEverywhereModal`) rendered by Jinja in `pages/settings.html`.
 * Log out everywhere is reversible and non-destructive, so it has no password
 * field, no re-auth branch, and no typed confirmation (D-1) — its Confirm button
 * POSTs an empty body and, on 200, navigates to the splash redirect.
 *
 * Split out of `account-removal.ts` (Phase 5): the trigger card was relocated
 * from the Account tab to the Privacy & Data panel, and this controller now owns
 * the logout-everywhere flow so `account-removal.ts` is delete-only. The shared
 * modal mechanics (banner rendering, in-flight marking, `ajaxCall` submit wiring,
 * cancel-emit + focus-return) live in `removal-shared.ts`.
 *
 * Handlers are delegated on `document` under this controller's own distinct
 * `click.logoutEverywhere` namespace (DD-1), keyed by ids + a `data-action-url`
 * attribute read off the modal (the request target). The Privacy & Data panel is
 * absent from the DOM only in tests; for a real signed-in user it always renders,
 * so `initLogoutEverywhere()` no-ops when `#SettingsPanelPrivacyData` is missing.
 */

import { $ } from "../lib/globals.js";
import { ajaxCall } from "../lib/ajax.js";
import { emit as recordUIEvent } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import {
  _confirmedByModal,
  _triggerByModal,
  clearBanner,
  emitCancelAndRestoreFocus,
  markInFlight,
  wireRemovalRequest,
} from "./removal-shared.js";

// This controller's own distinct delegated-click namespace (DD-1). No keyup
// namespace: the logout modal has no text inputs to bind keyup handlers on.
const CLICK_NAMESPACE = "click.logoutEverywhere";

// --- Logout-everywhere modal element ids + its namespaced hidden event ---
const LOGOUT_MODAL_ID = "SettingsLogoutEverywhereModal";
const LOGOUT_TRIGGER_ID = "SettingsLogoutEverywhereBtn";
const LOGOUT_SUBMIT_BTN_ID = "SettingsLogoutEverywhereSubmitBtn";
const LOGOUT_ERROR_ID = "SettingsLogoutEverywhereError";
const LOGOUT_HIDDEN_EVENT = "hidden.bs.modal.logoutEverywhere";

export function initLogoutEverywhere(): void {
  // Key the no-op guard off the Privacy & Data panel container (the logout
  // card's new home), mirroring account-removal's `#SettingsPanelAccount` guard.
  if (document.getElementById("SettingsPanelPrivacyData") === null) return;

  bindLogoutEverywhereModal();
}

export function _resetLogoutEverywhereForTests(): void {
  $(document).off(CLICK_NAMESPACE);
  $(`#${LOGOUT_MODAL_ID}`).off(LOGOUT_HIDDEN_EVENT);
  _triggerByModal.clear();
  _confirmedByModal.clear();
}

function bindLogoutEverywhereModal(): void {
  // Open the modal from its trigger card.
  $(document)
    .off(CLICK_NAMESPACE, `#${LOGOUT_TRIGGER_ID}`)
    .on(
      CLICK_NAMESPACE,
      `#${LOGOUT_TRIGGER_ID}`,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        openLogoutModal(event.currentTarget as HTMLElement);
      },
    );

  // Confirm button — POSTs an empty body (no field, no gate; D-1).
  $(document)
    .off(CLICK_NAMESPACE, `#${LOGOUT_SUBMIT_BTN_ID}`)
    .on(
      CLICK_NAMESPACE,
      `#${LOGOUT_SUBMIT_BTN_ID}`,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        submitLogoutEverywhere(event.currentTarget as HTMLButtonElement);
      },
    );

  // DD-7 dismissal handler: no fields to clear, but it still emits the CANCEL
  // metric and returns focus to the trigger on a genuine dismissal.
  $(`#${LOGOUT_MODAL_ID}`)
    .off(LOGOUT_HIDDEN_EVENT)
    .offAndOnExact(LOGOUT_HIDDEN_EVENT, function () {
      onLogoutModalHidden();
    });
}

function openLogoutModal(trigger: HTMLElement): void {
  _triggerByModal.set(LOGOUT_MODAL_ID, trigger);
  _confirmedByModal.set(LOGOUT_MODAL_ID, false);
  clearBanner(LOGOUT_ERROR_ID);
  recordUIEvent({ event: UI_EVENTS.UI_ACCOUNT_LOGOUT_EVERYWHERE_OPEN });
  $(`#${LOGOUT_MODAL_ID}`).modal("show");
}

function submitLogoutEverywhere(buttonEl: HTMLButtonElement): void {
  // Reentrancy guard: a disabled (in-flight) button never re-submits.
  if (buttonEl.disabled) return;

  const actionUrl = $(`#${LOGOUT_MODAL_ID}`).attr("data-action-url");
  if (!actionUrl) return;

  clearBanner(LOGOUT_ERROR_ID);
  markInFlight(buttonEl);
  _confirmedByModal.set(LOGOUT_MODAL_ID, true);
  recordUIEvent({ event: UI_EVENTS.UI_ACCOUNT_LOGOUT_EVERYWHERE_CONFIRM });

  // Field-less confirm (D-1): the empty `{}` body makes `ajaxCall`'s isJsonBody
  // check send no body / no Content-Type (harmless — the route's
  // `request_schema=None` never parses one).
  wireRemovalRequest({
    request: ajaxCall("post", actionUrl, {}),
    modalId: LOGOUT_MODAL_ID,
    errorId: LOGOUT_ERROR_ID,
    buttonEl,
    // No gate — re-enable unconditionally so a failed attempt is retryable.
    reenable: () => {
      $(buttonEl).removeAttr("disabled");
    },
    beforeNavigate: () => {},
    renderFieldErrors: () => false,
  });
}

function onLogoutModalHidden(): void {
  clearBanner(LOGOUT_ERROR_ID);
  emitCancelAndRestoreFocus({
    modalId: LOGOUT_MODAL_ID,
    cancelEvent: UI_EVENTS.UI_ACCOUNT_LOGOUT_EVERYWHERE_CANCEL,
  });
}
