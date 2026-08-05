/**
 * Account-deletion controller for the settings page (Account tab).
 *
 * Drives the bespoke dark danger-zone DELETE modal (`#SettingsDeleteModal`)
 * rendered by Jinja in `pages/settings.html`. The non-destructive "Log out
 * everywhere" flow was split out into `logout-everywhere.ts` (Phase 5) when its
 * trigger card was relocated to the Privacy & Data tab; this controller now owns
 * account deletion only. The shared modal mechanics (banner/field-error
 * rendering, in-flight marking, the `ajaxCall` submit wiring, and the
 * `hidden.bs.modal` cancel-emit + focus-return) live in `removal-shared.ts`.
 *
 * Like `change-email.ts` / `change-password.ts`, handlers are delegated on
 * `document` keyed by ids + a `data-action-url` attribute read off the modal
 * (the request target), under this controller's own distinct
 * `click.accountRemoval` / `keyup.accountRemoval` namespaces (DD-1). The Account
 * panel is absent from the DOM only in tests; for a real signed-in user it always
 * renders, so `initAccountRemoval()` no-ops when the `#SettingsPanelAccount`
 * container is missing.
 *
 * Delete's re-auth branches on which controls the template rendered (server-gated
 * by `connected_accounts_has_password`): password accounts get a password input +
 * a confirm button; OAuth-only accounts get a "Re-authenticate with <provider>"
 * button that starts the OAuth-proof round-trip. Both paths hit the SAME delete
 * endpoint — password path sends `{ currentPassword }`, OAuth path sends
 * `{ currentPassword: null }` — and on a 200 navigate to `response.redirectUrl`.
 *
 * Delete requires a typed-username confirmation (DD-C): one shared gate keyed
 * off the typed-username input disables BOTH the password-path submit AND the
 * OAuth-only re-auth button until the typed name exactly matches (DD-8).
 */

import { $ } from "../lib/globals.js";
import { ajaxCall } from "../lib/ajax.js";
import { emit as recordUIEvent } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import type { RemovalErrorResponse } from "./removal-shared.js";
import {
  _confirmedByModal,
  _triggerByModal,
  clearBanner,
  emitCancelAndRestoreFocus,
  isInFlight,
  markInFlight,
  setDisabled,
  showFieldError,
  wireRemovalRequest,
} from "./removal-shared.js";

// The account-info username card the delete gate compares the typed value
// against (DD-C) — a DOM read, mirroring change-email.ts's account-info pattern
// (the username is not carried in APP_CONFIG).
const USERNAME_VALUE_SELECTOR =
  '[data-account-info="username"] .SettingsStatValue';

const CLICK_NAMESPACE = "click.accountRemoval";
const KEYUP_NAMESPACE = "keyup.accountRemoval";

// Field-error alias key (request-schema alias) → the modal-input id it targets.
const FIELD_CURRENT_PASSWORD = "currentPassword";
const FIELD_CONFIRM_USERNAME = "confirmUsername";

// --- Delete modal element ids + its namespaced `hidden.bs.modal` name (DD-7) ---
const DELETE_MODAL_ID = "SettingsDeleteModal";
const DELETE_TRIGGER_ID = "SettingsDeleteBtn";
const DELETE_SUBMIT_BTN_ID = "SettingsDeleteSubmitBtn";
const DELETE_REAUTH_BTN_ID = "SettingsDeleteReauthBtn";
const DELETE_PASSWORD_ID = "SettingsDeleteCurrentPassword";
const DELETE_CONFIRM_USERNAME_ID = "SettingsDeleteConfirmUsername";
const DELETE_ERROR_ID = "SettingsDeleteError";
const DELETE_HIDDEN_EVENT = "hidden.bs.modal.accountDelete";

export function initAccountRemoval(): void {
  // Key the no-op guard off the always-rendered Account panel container, not any
  // single trigger id — the danger-zone/security cards it holds vary, but the
  // panel is present whenever the settings Account tab renders.
  if (document.getElementById("SettingsPanelAccount") === null) return;

  bindDeleteModal();
}

export function _resetAccountRemovalForTests(): void {
  $(document).off(CLICK_NAMESPACE).off(KEYUP_NAMESPACE);
  $(`#${DELETE_MODAL_ID}`).off(DELETE_HIDDEN_EVENT);
  _triggerByModal.clear();
  _confirmedByModal.clear();
}

// ---------------------------------------------------------------------------
// Delete modal
// ---------------------------------------------------------------------------

function bindDeleteModal(): void {
  // Open the modal from its danger-zone trigger.
  $(document)
    .off(CLICK_NAMESPACE, `#${DELETE_TRIGGER_ID}`)
    .on(
      CLICK_NAMESPACE,
      `#${DELETE_TRIGGER_ID}`,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        openDeleteModal(event.currentTarget as HTMLElement);
      },
    );

  // Password-path submit button (absent on OAuth-only renders).
  $(document)
    .off(CLICK_NAMESPACE, `#${DELETE_SUBMIT_BTN_ID}`)
    .on(
      CLICK_NAMESPACE,
      `#${DELETE_SUBMIT_BTN_ID}`,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        submitDelete({
          buttonEl: event.currentTarget as HTMLButtonElement,
          isOauthReauth: false,
        });
      },
    );

  // OAuth-only re-authenticate button (absent on password renders). Sends a null
  // password so the service takes the OAuth-proof branch.
  $(document)
    .off(CLICK_NAMESPACE, `#${DELETE_REAUTH_BTN_ID}`)
    .on(
      CLICK_NAMESPACE,
      `#${DELETE_REAUTH_BTN_ID}`,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        submitDelete({
          buttonEl: event.currentTarget as HTMLButtonElement,
          isOauthReauth: true,
        });
      },
    );

  // Enter-to-submit + live gate recompute on the modal's TEXT inputs only
  // (DD-9). Native `<button>`s already fire click on Enter, so the re-auth
  // button is intentionally NOT wired here (DD-25 — a manual dispatch would
  // double-submit).
  const textInputSelector = `#${DELETE_PASSWORD_ID}, #${DELETE_CONFIRM_USERNAME_ID}`;
  $(document)
    .off(KEYUP_NAMESPACE, textInputSelector)
    .on(
      KEYUP_NAMESPACE,
      textInputSelector,
      function (event: JQuery.KeyUpEvent) {
        // Recompute the typed-username gate synchronously on every keystroke.
        refreshDeleteGate();
        if (event.key !== "Enter") return;
        submitDeleteFromEnter();
      },
    );

  // DD-7 field-clear-on-dismiss: one handler for every dismissal path
  // (Cancel/Escape/backdrop).
  $(`#${DELETE_MODAL_ID}`)
    .off(DELETE_HIDDEN_EVENT)
    .offAndOnExact(DELETE_HIDDEN_EVENT, function () {
      onDeleteModalHidden();
    });
}

function openDeleteModal(trigger: HTMLElement): void {
  _triggerByModal.set(DELETE_MODAL_ID, trigger);
  _confirmedByModal.set(DELETE_MODAL_ID, false);
  clearDeleteError();
  refreshDeleteGate();
  recordUIEvent({ event: UI_EVENTS.UI_ACCOUNT_DELETE_OPEN });
  $(`#${DELETE_MODAL_ID}`).modal("show");
}

// Enter routes through the currently-relevant button so it inherits that
// button's disabled/gate state (a text input has no native Enter-submit).
function submitDeleteFromEnter(): void {
  const submitBtn = document.getElementById(DELETE_SUBMIT_BTN_ID);
  if (submitBtn) {
    submitDelete({
      buttonEl: submitBtn as HTMLButtonElement,
      isOauthReauth: false,
    });
    return;
  }
  const reauthBtn = document.getElementById(DELETE_REAUTH_BTN_ID);
  if (reauthBtn)
    submitDelete({
      buttonEl: reauthBtn as HTMLButtonElement,
      isOauthReauth: true,
    });
}

function submitDelete({
  buttonEl,
  isOauthReauth,
}: {
  buttonEl: HTMLButtonElement;
  isOauthReauth: boolean;
}): void {
  // Reentrancy + gate guard: a disabled button (in-flight, or gate not yet
  // satisfied) never submits.
  if (buttonEl.disabled) return;

  const actionUrl = $(`#${DELETE_MODAL_ID}`).attr("data-action-url");
  if (!actionUrl) return;

  // Password path reads the input directly; OAuth-proof path sends a null
  // password. The typed-username confirmation is always sent (DD-C).
  const payload: Record<string, string | null> = {
    currentPassword: isOauthReauth
      ? null
      : String($(`#${DELETE_PASSWORD_ID}`).val() ?? ""),
    confirmUsername: String($(`#${DELETE_CONFIRM_USERNAME_ID}`).val() ?? ""),
  };

  clearDeleteError();
  markInFlight(buttonEl);
  _confirmedByModal.set(DELETE_MODAL_ID, true);
  recordUIEvent({ event: UI_EVENTS.UI_ACCOUNT_DELETE_CONFIRM });

  wireRemovalRequest({
    request: ajaxCall("delete", actionUrl, payload),
    modalId: DELETE_MODAL_ID,
    errorId: DELETE_ERROR_ID,
    buttonEl,
    // Re-enable per the typed-username gate so a failed attempt leaves the modal
    // usable for a retry (never re-enabling a control that is still in flight).
    reenable: refreshDeleteGate,
    // Never leave the secret in the DOM before navigating away.
    beforeNavigate: () => {
      $(`#${DELETE_PASSWORD_ID}`).val("");
    },
    renderFieldErrors: renderDeleteFieldErrors,
  });
}

// Recompute the delete modal's gate (DD-8): the submit is enabled only when the
// typed username matches AND (for password accounts) the password is non-empty;
// the OAuth re-auth button is enabled once the typed username matches. Each
// control reads its own field directly — only one of the submit/re-auth pair is
// rendered per account, and `setDisabled` no-ops on the absent one. A control
// currently in flight (`aria-busy`) is NEVER re-enabled here — otherwise a
// keystroke during an in-flight request (including the Enter that fired it)
// would strip the markInFlight `disabled` guard and let a duplicate submit fire.
function refreshDeleteGate(): void {
  const typedUsername = String(
    $(`#${DELETE_CONFIRM_USERNAME_ID}`).val() ?? "",
  ).trim();
  const expectedUsername = (
    document.querySelector(USERNAME_VALUE_SELECTOR)?.textContent ?? ""
  ).trim();
  const usernameMatches =
    typedUsername.length > 0 && typedUsername === expectedUsername;

  const passwordNonEmpty =
    String($(`#${DELETE_PASSWORD_ID}`).val() ?? "").length > 0;

  setDisabled({
    elementId: DELETE_SUBMIT_BTN_ID,
    disabled:
      isInFlight(DELETE_SUBMIT_BTN_ID) ||
      !(usernameMatches && passwordNonEmpty),
  });
  setDisabled({
    elementId: DELETE_REAUTH_BTN_ID,
    disabled: isInFlight(DELETE_REAUTH_BTN_ID) || !usernameMatches,
  });
}

function onDeleteModalHidden(): void {
  $(`#${DELETE_PASSWORD_ID}`).val("");
  $(`#${DELETE_CONFIRM_USERNAME_ID}`).val("");
  // Re-close the gate now that the fields are empty.
  refreshDeleteGate();
  clearDeleteError();
  emitCancelAndRestoreFocus({
    modalId: DELETE_MODAL_ID,
    cancelEvent: UI_EVENTS.UI_ACCOUNT_DELETE_CANCEL,
  });
}

function clearDeleteError(): void {
  clearBanner(DELETE_ERROR_ID);
  for (const inputId of [DELETE_PASSWORD_ID, DELETE_CONFIRM_USERNAME_ID]) {
    const input = $(`#${inputId}`);
    input.removeClass("is-invalid");
    input.siblings(".invalid-feedback").remove();
  }
}

// Dispatch field errors to their inputs; return true if any were rendered.
function renderDeleteFieldErrors(
  responseJson: RemovalErrorResponse | undefined,
): boolean {
  const fieldErrors = responseJson?.errors;
  if (!fieldErrors) return false;

  let rendered = false;
  for (const [field, messages] of Object.entries(fieldErrors)) {
    if (!messages || messages.length === 0) continue;
    let inputId: string | null = null;
    if (field === FIELD_CURRENT_PASSWORD) inputId = DELETE_PASSWORD_ID;
    else if (field === FIELD_CONFIRM_USERNAME)
      inputId = DELETE_CONFIRM_USERNAME_ID;
    if (inputId) {
      showFieldError({ inputId, message: messages[0] });
      rendered = true;
    }
  }
  return rendered;
}
