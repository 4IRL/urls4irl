/**
 * Account-security controller for the settings page (Account tab).
 *
 * Drives two bespoke dark modals rendered by Jinja in `pages/settings.html`:
 * the danger-zone account DELETE (`#SettingsDeleteModal`) and the
 * non-destructive "Log out everywhere" flow (`#SettingsLogoutEverywhereModal`).
 * Like `change-email.ts` / `change-password.ts`, it binds delegated handlers on
 * `document` keyed by ids + a small `data-*` contract read off each modal
 * (`data-action-url` = the request target). The Account panel is absent from
 * the DOM only in tests; for a real signed-in user it always renders, so
 * `initAccountRemoval()` no-ops when the `#SettingsPanelAccount` container is
 * missing.
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

// Per-modal wiring. `method` is the HTTP verb. A non-null `confirmUsernameId`
// marks the delete modal, whose submit + re-auth button are gated by the
// typed-username match (DD-8); `passwordId`/`reauthBtnId` are null for the
// field-less logout-everywhere modal (D-1). `hiddenEventName` is the namespaced
// `hidden.bs.modal` name bound once via offAndOnExact (DD-7).
interface ModalConfig {
  modalId: string;
  triggerId: string;
  submitBtnId: string;
  reauthBtnId: string | null;
  passwordId: string | null;
  confirmUsernameId: string | null;
  errorId: string;
  method: "put" | "delete" | "post";
  hiddenEventName: string;
  events: { open: UIEventName; confirm: UIEventName; cancel: UIEventName };
}

const LOGOUT_EVERYWHERE_CONFIG: ModalConfig = {
  modalId: "SettingsLogoutEverywhereModal",
  triggerId: "SettingsLogoutEverywhereBtn",
  submitBtnId: "SettingsLogoutEverywhereSubmitBtn",
  reauthBtnId: null,
  passwordId: null,
  confirmUsernameId: null,
  errorId: "SettingsLogoutEverywhereError",
  method: "post",
  hiddenEventName: "hidden.bs.modal.logoutEverywhere",
  events: {
    open: UI_EVENTS.UI_ACCOUNT_LOGOUT_EVERYWHERE_OPEN,
    confirm: UI_EVENTS.UI_ACCOUNT_LOGOUT_EVERYWHERE_CONFIRM,
    cancel: UI_EVENTS.UI_ACCOUNT_LOGOUT_EVERYWHERE_CANCEL,
  },
};

const DELETE_CONFIG: ModalConfig = {
  modalId: "SettingsDeleteModal",
  triggerId: "SettingsDeleteBtn",
  submitBtnId: "SettingsDeleteSubmitBtn",
  reauthBtnId: "SettingsDeleteReauthBtn",
  passwordId: "SettingsDeleteCurrentPassword",
  confirmUsernameId: "SettingsDeleteConfirmUsername",
  errorId: "SettingsDeleteError",
  method: "delete",
  hiddenEventName: "hidden.bs.modal.accountDelete",
  events: {
    open: UI_EVENTS.UI_ACCOUNT_DELETE_OPEN,
    confirm: UI_EVENTS.UI_ACCOUNT_DELETE_CONFIRM,
    cancel: UI_EVENTS.UI_ACCOUNT_DELETE_CANCEL,
  },
};

const ALL_CONFIGS = [LOGOUT_EVERYWHERE_CONFIG, DELETE_CONFIG];

// Per-open state: the trigger element to restore focus to on close, and whether
// this open cycle reached a confirm (so `hidden.bs.modal` knows to emit CANCEL
// only for an actual dismissal). Keyed by modal id.
const _triggerByModal = new Map<string, HTMLElement>();
const _confirmedByModal = new Map<string, boolean>();

export function initAccountRemoval(): void {
  // Key the no-op guard off the always-rendered Account panel container, not any
  // single trigger id — the danger-zone/security cards it holds vary, but the
  // panel is present whenever the settings Account tab renders.
  if (document.getElementById("SettingsPanelAccount") === null) return;

  for (const config of ALL_CONFIGS) {
    bindModal(config);
  }
}

export function _resetAccountRemovalForTests(): void {
  $(document).off(CLICK_NAMESPACE).off(KEYUP_NAMESPACE);
  for (const config of ALL_CONFIGS) {
    $(`#${config.modalId}`).off(config.hiddenEventName);
  }
  _triggerByModal.clear();
  _confirmedByModal.clear();
}

function bindModal(config: ModalConfig): void {
  // Open the modal from its danger-zone trigger.
  $(document)
    .off(CLICK_NAMESPACE, `#${config.triggerId}`)
    .on(
      CLICK_NAMESPACE,
      `#${config.triggerId}`,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        openModal(config, event.currentTarget as HTMLElement);
      },
    );

  // Password-path submit button (absent on OAuth-only renders).
  $(document)
    .off(CLICK_NAMESPACE, `#${config.submitBtnId}`)
    .on(
      CLICK_NAMESPACE,
      `#${config.submitBtnId}`,
      function (event: JQuery.ClickEvent) {
        event.preventDefault();
        submitRemoval(config, event.currentTarget as HTMLButtonElement, false);
      },
    );

  // OAuth-only re-authenticate button (absent on password renders, and absent
  // entirely for logout-everywhere, which has no re-auth branch). Sends a null
  // password so the service takes the OAuth-proof branch.
  if (config.reauthBtnId) {
    $(document)
      .off(CLICK_NAMESPACE, `#${config.reauthBtnId}`)
      .on(
        CLICK_NAMESPACE,
        `#${config.reauthBtnId}`,
        function (event: JQuery.ClickEvent) {
          event.preventDefault();
          submitRemoval(config, event.currentTarget as HTMLButtonElement, true);
        },
      );
  }

  // Enter-to-submit + live gate recompute on the modal's TEXT inputs only
  // (DD-9). Native `<button>`s already fire click on Enter, so the re-auth
  // buttons are intentionally NOT wired here (DD-25 — a manual dispatch would
  // double-submit).
  const textInputSelector = textInputIds(config)
    .map((id) => `#${id}`)
    .join(", ");
  if (textInputSelector.length > 0) {
    $(document)
      .off(KEYUP_NAMESPACE, textInputSelector)
      .on(
        KEYUP_NAMESPACE,
        textInputSelector,
        function (event: JQuery.KeyUpEvent) {
          // Recompute the typed-username gate synchronously on every keystroke
          // (delete only; logout-everywhere is field-less and has no gate).
          refreshGate(config);
          if (event.key !== "Enter") return;
          submitFromEnter(config);
        },
      );
  }

  // DD-7 field-clear-on-dismiss: one handler per modal, firing for every
  // dismissal path (Cancel/Escape/backdrop). Both modals get it — the
  // field-less logout-everywhere modal is not exempt (its handler still emits
  // the CANCEL metric and returns focus to the trigger on dismissal).
  $(`#${config.modalId}`)
    .off(config.hiddenEventName)
    .offAndOnExact(config.hiddenEventName, function () {
      onModalHidden(config);
    });
}

// The modal's text-input ids (never the native re-auth buttons): the password
// input plus, for delete, the typed-username input.
function textInputIds(config: ModalConfig): string[] {
  const ids: string[] = [];
  if (config.passwordId) ids.push(config.passwordId);
  if (config.confirmUsernameId) ids.push(config.confirmUsernameId);
  return ids;
}

function openModal(config: ModalConfig, trigger: HTMLElement): void {
  _triggerByModal.set(config.modalId, trigger);
  _confirmedByModal.set(config.modalId, false);
  clearError(config);
  refreshGate(config);
  recordUIEvent({ event: config.events.open });
  $(`#${config.modalId}`).modal("show");
}

// Enter routes through the currently-relevant button so it inherits that
// button's disabled/gate state (a text input has no native Enter-submit).
function submitFromEnter(config: ModalConfig): void {
  const submitBtn = document.getElementById(config.submitBtnId);
  if (submitBtn) {
    submitRemoval(config, submitBtn as HTMLButtonElement, false);
    return;
  }
  if (!config.reauthBtnId) return;
  const reauthBtn = document.getElementById(config.reauthBtnId);
  if (reauthBtn) submitRemoval(config, reauthBtn as HTMLButtonElement, true);
}

function submitRemoval(
  config: ModalConfig,
  buttonEl: HTMLButtonElement,
  isOauthReauth: boolean,
): void {
  // Reentrancy + gate guard: a disabled button (in-flight, or gate not yet
  // satisfied) never submits.
  if (buttonEl.disabled) return;

  const actionUrl = $(`#${config.modalId}`).attr("data-action-url");
  if (!actionUrl) return;

  // Logout-everywhere has no password field (D-1), so its payload stays `{}` —
  // `ajaxCall`'s isJsonBody check then sends no body / no Content-Type at all
  // (harmless, since the route's `request_schema=None` never parses one).
  const payload: Record<string, string | null> = {};
  if (config.passwordId) {
    payload.currentPassword = isOauthReauth
      ? null
      : String($(`#${config.passwordId}`).val() ?? "");
  }
  if (config.confirmUsernameId) {
    payload.confirmUsername = String(
      $(`#${config.confirmUsernameId}`).val() ?? "",
    );
  }

  clearError(config);
  setInFlight(config, buttonEl, true);
  _confirmedByModal.set(config.modalId, true);
  recordUIEvent({ event: config.events.confirm });

  const request = ajaxCall(config.method, actionUrl, payload);

  request.done(function (
    response: AccountRemovalResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status !== 200) {
      setInFlight(config, buttonEl, false);
      _confirmedByModal.set(config.modalId, false);
      return;
    }
    // Never leave the secret in the DOM before navigating away.
    if (config.passwordId) $(`#${config.passwordId}`).val("");
    // Splash after logout, or the provider redirect for the OAuth round-trip.
    window.location.assign(response.redirectUrl);
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    setInFlight(config, buttonEl, false);
    // A confirm that failed did not complete removal — allow a CANCEL emit if
    // the user now dismisses the still-open modal.
    _confirmedByModal.set(config.modalId, false);
    if (is429Handled(xhr)) return;

    const responseJson = xhr.responseJSON as RemovalErrorResponse | undefined;
    if (renderFieldErrors(config, responseJson)) return;

    showError(config, responseJson?.message ?? GENERIC_ERROR_MESSAGE);
  });
}

// Dispatch field errors to their inputs; return true if any were rendered.
function renderFieldErrors(
  config: ModalConfig,
  responseJson: RemovalErrorResponse | undefined,
): boolean {
  const fieldErrors = responseJson?.errors;
  if (!fieldErrors) return false;

  let rendered = false;
  for (const [field, messages] of Object.entries(fieldErrors)) {
    if (!messages || messages.length === 0) continue;
    let inputId: string | null = null;
    if (field === FIELD_CURRENT_PASSWORD) inputId = config.passwordId;
    else if (field === FIELD_CONFIRM_USERNAME)
      inputId = config.confirmUsernameId;
    if (inputId) {
      showFieldError(inputId, messages[0]);
      rendered = true;
    }
  }
  return rendered;
}

// Recompute the delete modal's gate (DD-8): the submit is enabled only when the
// typed username matches AND (for password accounts) the password is non-empty;
// the OAuth re-auth button is enabled once the typed username matches. The
// logout-everywhere modal has no typed-username field, so its controls stay
// ungated. A control that is currently in flight (`aria-busy`) is NEVER
// re-enabled here — otherwise a keystroke during an in-flight request (including
// the Enter that fired it) would strip the setInFlight `disabled` guard and let
// `submitRemoval` fire a duplicate request.
function refreshGate(config: ModalConfig): void {
  if (!config.confirmUsernameId) return;

  const typedUsername = String(
    $(`#${config.confirmUsernameId}`).val() ?? "",
  ).trim();
  const expectedUsername = (
    document.querySelector(USERNAME_VALUE_SELECTOR)?.textContent ?? ""
  ).trim();
  const usernameMatches =
    typedUsername.length > 0 && typedUsername === expectedUsername;

  const passwordNonEmpty =
    String($(`#${config.passwordId}`).val() ?? "").length > 0;

  const submitInFlight = isInFlight(config.submitBtnId);
  setDisabled(
    config.submitBtnId,
    submitInFlight || !(usernameMatches && passwordNonEmpty),
  );
  if (config.reauthBtnId) {
    const reauthInFlight = isInFlight(config.reauthBtnId);
    setDisabled(config.reauthBtnId, reauthInFlight || !usernameMatches);
  }
}

// A control is "in flight" while setInFlight has marked it aria-busy; the gate
// must not re-enable it until the request settles.
function isInFlight(elementId: string): boolean {
  return (
    document.getElementById(elementId)?.getAttribute("aria-busy") === "true"
  );
}

function onModalHidden(config: ModalConfig): void {
  clearFields(config);
  clearError(config);
  if (!_confirmedByModal.get(config.modalId)) {
    recordUIEvent({ event: config.events.cancel });
  }
  // Return focus to the trigger that opened the modal.
  const trigger = _triggerByModal.get(config.modalId);
  if (trigger) $(trigger).trigger("focus");
  _confirmedByModal.set(config.modalId, false);
}

function clearFields(config: ModalConfig): void {
  if (config.passwordId) $(`#${config.passwordId}`).val("");
  if (config.confirmUsernameId) $(`#${config.confirmUsernameId}`).val("");
  // Re-close the gate now that the fields are empty.
  refreshGate(config);
}

function setInFlight(
  config: ModalConfig,
  buttonEl: HTMLButtonElement,
  inFlight: boolean,
): void {
  if (inFlight) {
    $(buttonEl).attr("disabled", "disabled").attr("aria-busy", "true");
    return;
  }
  $(buttonEl).removeAttr("aria-busy");
  // Re-enable per the gate (delete) or unconditionally (logout-everywhere) so a
  // failed attempt leaves the modal usable for a retry.
  if (config.confirmUsernameId) {
    refreshGate(config);
  } else {
    $(buttonEl).removeAttr("disabled");
  }
}

function setDisabled(elementId: string, disabled: boolean): void {
  const element = document.getElementById(elementId);
  if (!element) return;
  if (disabled) $(element).attr("disabled", "disabled");
  else $(element).removeAttr("disabled");
}

function showFieldError(inputId: string, message: string): void {
  const input = $(`#${inputId}`);
  input.addClass("is-invalid");
  input.siblings(".invalid-feedback").remove();
  $("<div>", { class: "invalid-feedback" })
    .append($("<span>").text(message))
    .insertAfter(input);
}

function showError(config: ModalConfig, message: string): void {
  $(`#${config.errorId}`).removeClass("d-none").text(message);
}

function clearError(config: ModalConfig): void {
  $(`#${config.errorId}`).addClass("d-none").text("");
  for (const inputId of textInputIds(config)) {
    const input = $(`#${inputId}`);
    input.removeClass("is-invalid");
    input.siblings(".invalid-feedback").remove();
  }
}
