/**
 * Change-username controller for the settings page (Account tab).
 *
 * The form is server-rendered by Jinja (`pages/settings.html`), so — like
 * `connected-accounts.ts` — this binds delegated handlers on `document` keyed
 * by a small `data-*` contract read off the button, rather than binding per
 * element at a TS render step (there is none).
 *
 * data-* contract (rendered by the template, read-only here):
 *   #SettingsChangeUsernameBtn[data-action-url]   PUT target for the rename
 *
 * On a 200 the endpoint echoes the (possibly unchanged) username back; the
 * handler updates the input value, the read-only account-info username card,
 * AND the navbar "Logged in as" label(s) in place (DD-15 — no page reload) and
 * renders the server-sourced banner text (DD-12) into the form's own status
 * region for both the success and no-op branches.
 */

import type { Schema, SuccessResponse } from "../types/api-helpers.d.ts";
import { $ } from "../lib/globals.js";
import { ajaxCall, is429Handled } from "../lib/ajax.js";

type ChangeUsernameRequest = Schema<"ChangeUsernameRequest">;
type ChangeUsernameResponse = SuccessResponse<"changeUsername">;
type ChangeUsernameError = Schema<"ErrorResponse_ChangeUsernameErrorCodes">;

const INPUT_ID = "SettingsNewUsername";
const BUTTON_ID = "SettingsChangeUsernameBtn";
const STATUS_ID = "SettingsUsernameStatus";
const ACCOUNT_USERNAME_VALUE_SELECTOR =
  '[data-account-info="username"] .SettingsStatValue';
// The navbar "Logged in as <username>" label(s) — the dropdown header and the
// desktop inline copy both wrap the username in this span so it refreshes in
// place too (otherwise the navbar shows the stale pre-rename username).
const NAV_USERNAME_SELECTOR = ".navLoggedInAsUsername";

const CLICK_NAMESPACE = "click.changeUsername";
const KEYUP_NAMESPACE = "keyup.changeUsername";

const GENERIC_ERROR_MESSAGE = "Unable to process request.";

export function initChangeUsername(): void {
  if (document.getElementById(INPUT_ID) === null) return;

  $(document)
    .off(CLICK_NAMESPACE, `#${BUTTON_ID}`)
    .on(CLICK_NAMESPACE, `#${BUTTON_ID}`, function (event: JQuery.ClickEvent) {
      event.preventDefault();
      submitUsernameChange(event.currentTarget as HTMLButtonElement);
    });

  // Enter-to-submit from the input, routed through the same handler (and its
  // reentrancy guard) as the button click.
  $(document)
    .off(KEYUP_NAMESPACE, `#${INPUT_ID}`)
    .on(KEYUP_NAMESPACE, `#${INPUT_ID}`, function (event: JQuery.KeyUpEvent) {
      if (event.key !== "Enter") return;
      const buttonEl = document.getElementById(BUTTON_ID);
      if (buttonEl) submitUsernameChange(buttonEl as HTMLButtonElement);
    });
}

export function _resetChangeUsernameForTests(): void {
  $(document).off(CLICK_NAMESPACE).off(KEYUP_NAMESPACE);
}

function submitUsernameChange(buttonEl: HTMLButtonElement): void {
  // Reentrancy guard (DD-13): a keyup-triggered resubmit must not race the
  // disable-in-flight state set by an in-progress click submission.
  if (buttonEl.disabled) return;

  const actionUrl = buttonEl.dataset.actionUrl;
  if (!actionUrl) return;

  const username = String($(`#${INPUT_ID}`).val() ?? "");

  clearFormErrors();
  setInFlight(buttonEl, true);

  const payload: ChangeUsernameRequest = { username };
  const request = ajaxCall("put", actionUrl, payload);

  request.done(function (
    response: ChangeUsernameResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    setInFlight(buttonEl, false);
    if (xhr.status !== 200) return;

    // Update-in-place (DD-15): refresh every on-page display from the single
    // echoed username so they never drift without a reload — the form input,
    // the read-only account-info card, and the navbar "Logged in as" label(s).
    const echoedUsername = response.username;
    $(`#${INPUT_ID}`).val(echoedUsername);
    $(ACCOUNT_USERNAME_VALUE_SELECTOR).text(echoedUsername);
    $(NAV_USERNAME_SELECTOR).text(echoedUsername);

    // Server-sourced banner text (DD-12) for both success and no-op branches.
    showStatus({ message: response.message, type: "success" });
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    setInFlight(buttonEl, false);
    if (is429Handled(xhr)) return;

    const responseJson = xhr.responseJSON as ChangeUsernameError | undefined;
    const fieldErrors = responseJson?.errors?.username;
    if (fieldErrors && fieldErrors.length > 0) {
      showFieldError(fieldErrors[0]);
      return;
    }
    // Non-field error (e.g. the JSON 429 daily-limit message): surface the
    // server message in the status region.
    showStatus({
      message: responseJson?.message ?? GENERIC_ERROR_MESSAGE,
      type: "danger",
    });
  });
}

function setInFlight(buttonEl: HTMLButtonElement, inFlight: boolean): void {
  // DD-16: unlike register-form.ts, re-enable on success too, so the form stays
  // usable for a subsequent edit without a page refresh.
  if (inFlight) {
    $(buttonEl).attr("disabled", "disabled").attr("aria-busy", "true");
  } else {
    $(buttonEl).removeAttr("disabled").removeAttr("aria-busy");
  }
}

function clearFormErrors(): void {
  $(`#${INPUT_ID}`).removeClass("is-invalid");
  $(`#${INPUT_ID}`).siblings(".invalid-feedback").remove();
  $(`#${STATUS_ID}`)
    .addClass("d-none")
    .removeClass("alert-success alert-danger")
    .text("");
}

function showFieldError(message: string): void {
  const input = $(`#${INPUT_ID}`);
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
