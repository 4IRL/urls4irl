/**
 * Change-password controller for the settings page (Account tab).
 *
 * Like `change-username.ts` / `connected-accounts.ts`, the form is
 * server-rendered by Jinja (`pages/settings.html`), so this binds delegated
 * handlers on `document` keyed by a small `data-*` contract read off the
 * button. The whole section is gated by `{% if connected_accounts_has_password %}`
 * in the template, so on OAuth-only pages the inputs are absent and
 * `initChangePassword()` no-ops.
 *
 * data-* contract (rendered by the template, read-only here):
 *   #SettingsChangePasswordBtn[data-action-url]   PUT target for the change
 *
 * On a 200 all three password fields are cleared (never leave secrets in the
 * DOM) and the server-sourced banner text (DD-12) is rendered into the form's
 * own status region. On failure, field errors dispatch to the matching input
 * and any non-field message surfaces in the status region.
 */

import type { Schema, SuccessResponse } from "../types/api-helpers.d.ts";
import { $ } from "../lib/globals.js";
import { ajaxCall, is429Handled } from "../lib/ajax.js";

type ChangePasswordRequest = Schema<"ChangePasswordRequest">;
type ChangePasswordResponse = SuccessResponse<"changePassword">;
type ChangePasswordError = Schema<"ErrorResponse_ChangePasswordErrorCodes">;

const CURRENT_INPUT_ID = "SettingsCurrentPassword";
const NEW_INPUT_ID = "SettingsNewPassword";
const CONFIRM_INPUT_ID = "SettingsConfirmNewPassword";
const BUTTON_ID = "SettingsChangePasswordBtn";
const STATUS_ID = "SettingsPasswordStatus";

const CLICK_NAMESPACE = "click.changePassword";
const KEYUP_NAMESPACE = "keyup.changePassword";

const GENERIC_ERROR_MESSAGE = "Unable to process request.";
// Success fallback if the server envelope ever omits `message` (it always
// sends PASSWORD_CHANGE_SUCCESS) — a green banner must never show error copy.
const SUCCESS_FALLBACK_MESSAGE = "Your password has been updated.";

// Field-error key (request-schema alias) → input id. The alias keys match
// pydantic's `loc` on validation failure and the service's field-error dict.
const FIELD_TO_INPUT_ID: Record<string, string> = {
  currentPassword: CURRENT_INPUT_ID,
  newPassword: NEW_INPUT_ID,
  confirmNewPassword: CONFIRM_INPUT_ID,
};

const ALL_INPUT_IDS = [CURRENT_INPUT_ID, NEW_INPUT_ID, CONFIRM_INPUT_ID];

export function initChangePassword(): void {
  if (document.getElementById(CURRENT_INPUT_ID) === null) return;

  $(document)
    .off(CLICK_NAMESPACE, `#${BUTTON_ID}`)
    .on(CLICK_NAMESPACE, `#${BUTTON_ID}`, function (event: JQuery.ClickEvent) {
      event.preventDefault();
      submitPasswordChange(event.currentTarget as HTMLButtonElement);
    });

  // Enter-to-submit from any of the three inputs, routed through the same
  // handler (and its reentrancy guard) as the button click.
  const inputSelector = ALL_INPUT_IDS.map((id) => `#${id}`).join(", ");
  $(document)
    .off(KEYUP_NAMESPACE, inputSelector)
    .on(KEYUP_NAMESPACE, inputSelector, function (event: JQuery.KeyUpEvent) {
      if (event.key !== "Enter") return;
      const buttonEl = document.getElementById(BUTTON_ID);
      if (buttonEl) submitPasswordChange(buttonEl as HTMLButtonElement);
    });
}

export function _resetChangePasswordForTests(): void {
  $(document).off(CLICK_NAMESPACE).off(KEYUP_NAMESPACE);
}

function submitPasswordChange(buttonEl: HTMLButtonElement): void {
  // Reentrancy guard (DD-13): a keyup-triggered resubmit must not race the
  // disable-in-flight state set by an in-progress click submission.
  if (buttonEl.disabled) return;

  const actionUrl = buttonEl.dataset.actionUrl;
  if (!actionUrl) return;

  const currentPassword = String($(`#${CURRENT_INPUT_ID}`).val() ?? "");
  const newPassword = String($(`#${NEW_INPUT_ID}`).val() ?? "");
  const confirmNewPassword = String($(`#${CONFIRM_INPUT_ID}`).val() ?? "");

  clearFormErrors();
  setInFlight(buttonEl, true);

  const payload: ChangePasswordRequest = {
    currentPassword,
    newPassword,
    confirmNewPassword,
  };
  const request = ajaxCall("put", actionUrl, payload);

  request.done(function (
    _response: ChangePasswordResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    setInFlight(buttonEl, false);
    if (xhr.status !== 200) return;

    // Never leave secrets in the DOM: clear all three fields on success.
    clearPasswordFields();

    // Server-sourced banner text (DD-12).
    const response = xhr.responseJSON as ChangePasswordResponse | undefined;
    showStatus({
      message: response?.message ?? SUCCESS_FALLBACK_MESSAGE,
      type: "success",
    });
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    setInFlight(buttonEl, false);
    if (is429Handled(xhr)) return;

    const responseJson = xhr.responseJSON as ChangePasswordError | undefined;
    const fieldErrors = responseJson?.errors;
    let renderedFieldError = false;
    if (fieldErrors) {
      for (const [field, messages] of Object.entries(fieldErrors)) {
        const inputId = FIELD_TO_INPUT_ID[field];
        if (inputId && messages && messages.length > 0) {
          showFieldError(inputId, messages[0]);
          renderedFieldError = true;
        }
      }
    }
    if (renderedFieldError) return;

    // Non-field error: surface the server message in the status region.
    showStatus({
      message: responseJson?.message ?? GENERIC_ERROR_MESSAGE,
      type: "danger",
    });
  });
}

function setInFlight(buttonEl: HTMLButtonElement, inFlight: boolean): void {
  // DD-16: unlike register-form.ts, re-enable on success too, so the form stays
  // usable for a subsequent change without a page refresh.
  if (inFlight) {
    $(buttonEl).attr("disabled", "disabled").attr("aria-busy", "true");
  } else {
    $(buttonEl).removeAttr("disabled").removeAttr("aria-busy");
  }
}

function clearPasswordFields(): void {
  for (const id of ALL_INPUT_IDS) {
    $(`#${id}`).val("");
  }
}

function clearFormErrors(): void {
  for (const id of ALL_INPUT_IDS) {
    const input = $(`#${id}`);
    input.removeClass("is-invalid");
    input.siblings(".invalid-feedback").remove();
  }
  $(`#${STATUS_ID}`)
    .addClass("d-none")
    .removeClass("alert-success alert-danger")
    .text("");
}

function showFieldError(inputId: string, message: string): void {
  const input = $(`#${inputId}`);
  input.addClass("is-invalid");
  input.siblings(".invalid-feedback").remove();
  $("<div>", { class: "invalid-feedback" })
    .append($("<span>").text(message))
    .insertAfter(input);
}

function showStatus({
  message,
  type,
}: {
  message: string;
  type: "success" | "danger";
}): void {
  $(`#${STATUS_ID}`)
    .removeClass("d-none alert-success alert-danger")
    .addClass(`alert-${type}`)
    .text(message);
}
