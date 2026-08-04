/**
 * Account-security controller for the settings page (Account tab).
 *
 * Drives two bespoke dark modals rendered by Jinja in `pages/settings.html`:
 * the danger-zone account DELETE (`#SettingsDeleteModal`) and the
 * non-destructive "Log out everywhere" flow (`#SettingsLogoutEverywhereModal`).
 * Rather than a config-driven engine, each modal has its own purpose-built
 * binder — `bindDeleteModal` and `bindLogoutEverywhereModal` — because the two
 * diverge meaningfully (the delete modal has a typed-username gate + a
 * password/OAuth re-auth split; logout-everywhere is a field-less POST confirm).
 * They share small focused helpers for the common mechanics: banner/field-error
 * rendering, in-flight marking, the `ajaxCall` submit wiring, and the
 * `hidden.bs.modal` cancel-emit + focus-return.
 *
 * Like `change-email.ts` / `change-password.ts`, handlers are delegated on
 * `document` keyed by ids + a `data-action-url` attribute read off each modal
 * (the request target). The Account panel is absent from the DOM only in tests;
 * for a real signed-in user it always renders, so `initAccountRemoval()` no-ops
 * when the `#SettingsPanelAccount` container is missing.
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
 * OAuth-only re-auth button until the typed name exactly matches (DD-8). Log out
 * everywhere is reversible and non-destructive, so it has no password field, no
 * re-auth branch, and no typed confirmation (D-1) — its Confirm button POSTs an
 * empty body and, on 200, navigates to the splash redirect.
 */

import type { Schema } from "../types/api-helpers.d.ts";
import type { UIEventName } from "../types/metrics-events.js";
import { $ } from "../lib/globals.js";
import { ajaxCall, is429Handled } from "../lib/ajax.js";
import { emit as recordUIEvent } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";

type AccountRemovalResponse = Schema<"AccountRemovalResponseSchema">;
type RemovalErrorResponse = Schema<"ErrorResponse">;

// The account-info username card the delete gate compares the typed value
// against (DD-C) — a DOM read, mirroring change-email.ts's account-info pattern
// (the username is not carried in APP_CONFIG).
const USERNAME_VALUE_SELECTOR =
  '[data-account-info="username"] .SettingsStatValue';

const CLICK_NAMESPACE = "click.accountRemoval";
const KEYUP_NAMESPACE = "keyup.accountRemoval";

const GENERIC_ERROR_MESSAGE = "Unable to process request.";

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

// --- Logout-everywhere modal element ids + its namespaced hidden event ---
const LOGOUT_MODAL_ID = "SettingsLogoutEverywhereModal";
const LOGOUT_TRIGGER_ID = "SettingsLogoutEverywhereBtn";
const LOGOUT_SUBMIT_BTN_ID = "SettingsLogoutEverywhereSubmitBtn";
const LOGOUT_ERROR_ID = "SettingsLogoutEverywhereError";
const LOGOUT_HIDDEN_EVENT = "hidden.bs.modal.logoutEverywhere";

// Per-open state, keyed by modal id: the trigger element to restore focus to on
// close, and whether this open cycle reached a confirm (so `hidden.bs.modal`
// knows to emit CANCEL only for an actual dismissal).
const _triggerByModal = new Map<string, HTMLElement>();
const _confirmedByModal = new Map<string, boolean>();

export function initAccountRemoval(): void {
  // Key the no-op guard off the always-rendered Account panel container, not any
  // single trigger id — the danger-zone/security cards it holds vary, but the
  // panel is present whenever the settings Account tab renders.
  if (document.getElementById("SettingsPanelAccount") === null) return;

  bindDeleteModal();
  bindLogoutEverywhereModal();
}

export function _resetAccountRemovalForTests(): void {
  $(document).off(CLICK_NAMESPACE).off(KEYUP_NAMESPACE);
  $(`#${DELETE_MODAL_ID}`).off(DELETE_HIDDEN_EVENT);
  $(`#${LOGOUT_MODAL_ID}`).off(LOGOUT_HIDDEN_EVENT);
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

// ---------------------------------------------------------------------------
// Logout-everywhere modal
// ---------------------------------------------------------------------------

function bindLogoutEverywhereModal(): void {
  // Open the modal from its danger-zone trigger.
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

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

interface RemovalRequestBinding {
  request: JQuery.jqXHR;
  modalId: string;
  errorId: string;
  buttonEl: HTMLButtonElement;
  // Re-enable the modal's controls after a non-200 / failed attempt (gate
  // recompute for delete, unconditional for logout-everywhere).
  reenable: () => void;
  // Runs just before a successful navigation (e.g. clear the password field).
  beforeNavigate: () => void;
  // Render server field errors onto inputs; return true if any were shown.
  renderFieldErrors: (
    responseJson: RemovalErrorResponse | undefined,
  ) => boolean;
}

// Shared `ajaxCall` submit wiring: on a 200 navigate to the server redirect,
// otherwise settle the button and surface the error (field errors first, then
// the in-modal banner). `is429Handled` short-circuits an already-handled 429.
function wireRemovalRequest({
  request,
  modalId,
  errorId,
  buttonEl,
  reenable,
  beforeNavigate,
  renderFieldErrors,
}: RemovalRequestBinding): void {
  request.done(function (
    response: AccountRemovalResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status !== 200) {
      settleAfterAttempt({ modalId, buttonEl, reenable });
      return;
    }
    beforeNavigate();
    // Splash after logout, or the provider redirect for the OAuth round-trip.
    window.location.assign(response.redirectUrl);
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    settleAfterAttempt({ modalId, buttonEl, reenable });
    if (is429Handled(xhr)) return;

    const responseJson = xhr.responseJSON as RemovalErrorResponse | undefined;
    if (renderFieldErrors(responseJson)) return;

    showBanner({
      errorId,
      message: responseJson?.message ?? GENERIC_ERROR_MESSAGE,
    });
  });
}

// Settle a modal after a non-200 / failed attempt: drop the in-flight marker,
// re-enable controls per the modal's policy, and clear the confirmed flag so a
// subsequent dismiss still emits CANCEL (the removal did not complete).
function settleAfterAttempt({
  modalId,
  buttonEl,
  reenable,
}: {
  modalId: string;
  buttonEl: HTMLButtonElement;
  reenable: () => void;
}): void {
  clearInFlight(buttonEl);
  reenable();
  _confirmedByModal.set(modalId, false);
}

function emitCancelAndRestoreFocus({
  modalId,
  cancelEvent,
}: {
  modalId: string;
  cancelEvent: UIEventName;
}): void {
  if (!_confirmedByModal.get(modalId)) {
    recordUIEvent({ event: cancelEvent });
  }
  // Return focus to the trigger that opened the modal.
  const trigger = _triggerByModal.get(modalId);
  if (trigger) $(trigger).trigger("focus");
  _confirmedByModal.set(modalId, false);
}

// Mark a control in flight: disabled + aria-busy, so both the native guard and
// the gate's `isInFlight` check keep it from re-submitting.
function markInFlight(buttonEl: HTMLButtonElement): void {
  $(buttonEl).attr("disabled", "disabled").attr("aria-busy", "true");
}

function clearInFlight(buttonEl: HTMLButtonElement): void {
  $(buttonEl).removeAttr("aria-busy");
}

// A control is "in flight" while markInFlight has set aria-busy; the gate must
// not re-enable it until the request settles.
function isInFlight(elementId: string): boolean {
  return (
    document.getElementById(elementId)?.getAttribute("aria-busy") === "true"
  );
}

function setDisabled({
  elementId,
  disabled,
}: {
  elementId: string;
  disabled: boolean;
}): void {
  const element = document.getElementById(elementId);
  if (!element) return;
  if (disabled) $(element).attr("disabled", "disabled");
  else $(element).removeAttr("disabled");
}

function showFieldError({
  inputId,
  message,
}: {
  inputId: string;
  message: string;
}): void {
  const input = $(`#${inputId}`);
  input.addClass("is-invalid");
  input.siblings(".invalid-feedback").remove();
  $("<div>", { class: "invalid-feedback" })
    .append($("<span>").text(message))
    .insertAfter(input);
}

function showBanner({
  errorId,
  message,
}: {
  errorId: string;
  message: string;
}): void {
  $(`#${errorId}`).removeClass("d-none").text(message);
}

function clearBanner(errorId: string): void {
  $(`#${errorId}`).addClass("d-none").text("");
}
