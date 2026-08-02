/**
 * Change-email controller for the settings page (Account tab).
 *
 * Like `change-username.ts` / `change-password.ts`, the form is server-rendered
 * by Jinja (`pages/settings.html`), so this binds delegated handlers on
 * `document` keyed by a small `data-*` contract read off the button. The whole
 * section is gated by `{% if connected_accounts_has_password %}` in the
 * template, so on OAuth-only pages the inputs are absent and `initChangeEmail()`
 * no-ops.
 *
 * data-* contract (rendered by the template, read-only here):
 *   #SettingsChangeEmailBtn[data-action-url]   PUT target for the change
 *
 * Approach B (stay on the page): a 200 does NOT navigate. The live email is not
 * swapped until the user opens the confirmation link, so the account-info email
 * card keeps its current address; instead the just-staged `pendingEmail` echoed
 * back (DD-6) is patched into an aria-live pending-change note beside it. The
 * password field is cleared (never leave secrets in the DOM) and the
 * server-sourced banner text is rendered into the form's own status region. On
 * failure, field errors dispatch to the matching input and any non-field
 * message surfaces in the status region.
 */

import type { Schema, SuccessResponse } from "../types/api-helpers.d.ts";
import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { ajaxCall, is429Handled } from "../lib/ajax.js";

type ChangeEmailRequest = Schema<"ChangeEmailRequest">;
type ChangeEmailResponse = SuccessResponse<"changeEmail">;
type ChangeEmailError = Schema<"ErrorResponse_ChangeEmailErrorCodes">;

const NEW_EMAIL_ID = "SettingsNewEmail";
const CONFIRM_EMAIL_ID = "SettingsConfirmNewEmail";
const PASSWORD_ID = "SettingsChangeEmailCurrentPassword";
const BUTTON_ID = "SettingsChangeEmailBtn";
const STATUS_ID = "SettingsEmailStatus";

// The account-info email card and its pending-change note (DD-6). The note may
// not exist yet on a clean page load (nothing staged server-side), so the
// success handler both updates an existing node and constructs a missing one.
const ACCOUNT_EMAIL_CARD_SELECTOR = '[data-account-info="email"]';
const ACCOUNT_PENDING_EMAIL_NOTE_SELECTOR = `${ACCOUNT_EMAIL_CARD_SELECTOR} .SettingsAccountPendingEmailNote`;
const PENDING_EMAIL_NOTE_CLASS = "SettingsAccountPendingEmailNote";
const PENDING_EMAIL_PLACEHOLDER = "{email}";

const CLICK_NAMESPACE = "click.changeEmail";
const KEYUP_NAMESPACE = "keyup.changeEmail";

const GENERIC_ERROR_MESSAGE = "Unable to process request.";
// Success fallback if the server envelope ever omits `message` (it always sends
// EMAIL_CHANGE_CONFIRMATION_SENT) — a green banner must never show error copy.
const SUCCESS_FALLBACK_MESSAGE =
  "We've sent a confirmation link to your new email address.";

// Field-error key (request-schema alias) → input id. The alias keys match
// pydantic's `loc` on validation failure and the service's field-error dict.
const FIELD_TO_INPUT_ID: Record<string, string> = {
  newEmail: NEW_EMAIL_ID,
  confirmEmail: CONFIRM_EMAIL_ID,
  currentPassword: PASSWORD_ID,
};

const ALL_INPUT_IDS = [NEW_EMAIL_ID, CONFIRM_EMAIL_ID, PASSWORD_ID];

export function initChangeEmail(): void {
  if (document.getElementById(NEW_EMAIL_ID) === null) return;

  $(document)
    .off(CLICK_NAMESPACE, `#${BUTTON_ID}`)
    .on(CLICK_NAMESPACE, `#${BUTTON_ID}`, function (event: JQuery.ClickEvent) {
      event.preventDefault();
      submitEmailChange(event.currentTarget as HTMLButtonElement);
    });

  // Enter-to-submit from any of the three inputs, routed through the same
  // handler (and its reentrancy guard) as the button click.
  const inputSelector = ALL_INPUT_IDS.map((id) => `#${id}`).join(", ");
  $(document)
    .off(KEYUP_NAMESPACE, inputSelector)
    .on(KEYUP_NAMESPACE, inputSelector, function (event: JQuery.KeyUpEvent) {
      if (event.key !== "Enter") return;
      const buttonEl = document.getElementById(BUTTON_ID);
      if (buttonEl) submitEmailChange(buttonEl as HTMLButtonElement);
    });
}

export function _resetChangeEmailForTests(): void {
  $(document).off(CLICK_NAMESPACE).off(KEYUP_NAMESPACE);
}

function submitEmailChange(buttonEl: HTMLButtonElement): void {
  // Reentrancy guard: a keyup-triggered resubmit must not race the
  // disable-in-flight state set by an in-progress click submission.
  if (buttonEl.disabled) return;

  const actionUrl = buttonEl.dataset.actionUrl;
  if (!actionUrl) return;

  const newEmail = String($(`#${NEW_EMAIL_ID}`).val() ?? "");
  const confirmEmail = String($(`#${CONFIRM_EMAIL_ID}`).val() ?? "");
  const currentPassword = String($(`#${PASSWORD_ID}`).val() ?? "");

  clearFormErrors();
  setInFlight(buttonEl, true);

  const payload: ChangeEmailRequest = {
    newEmail,
    confirmEmail,
    currentPassword,
  };
  const request = ajaxCall("put", actionUrl, payload);

  request.done(function (
    response: ChangeEmailResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    setInFlight(buttonEl, false);
    if (xhr.status !== 200) return;

    // Never leave the secret in the DOM: clear the password field on success.
    $(`#${PASSWORD_ID}`).val("");

    // Update-in-place (DD-6): patch the account-info pending-change note from
    // the echoed staged address so it reflects the in-flight change without a
    // reload. A no-op response (guard 5) echoes null — leave the note untouched.
    if (response.pendingEmail) {
      updatePendingEmailNote(response.pendingEmail);
    }

    // Server-sourced banner text.
    showStatus({
      message: response.message ?? SUCCESS_FALLBACK_MESSAGE,
      type: "success",
    });
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    setInFlight(buttonEl, false);
    if (is429Handled(xhr)) return;

    const responseJson = xhr.responseJSON as ChangeEmailError | undefined;
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

    // Non-field error (e.g. the JSON 429 lockout message): surface the server
    // message in the status region.
    showStatus({
      message: responseJson?.message ?? GENERIC_ERROR_MESSAGE,
      type: "danger",
    });
  });
}

function updatePendingEmailNote(pendingEmail: string): void {
  // split/join (not String.replace) so the email is inserted literally: a
  // string replacement arg treats `$&`/`$$`/etc. as special, and an RFC-valid
  // local part can legitimately contain `$`/`&`.
  const formattedNote =
    APP_CONFIG.strings.SETTINGS_ACCOUNT_PENDING_EMAIL_NOTE.split(
      PENDING_EMAIL_PLACEHOLDER,
    ).join(pendingEmail);

  const existingNote = $(ACCOUNT_PENDING_EMAIL_NOTE_SELECTOR);
  if (existingNote.length > 0) {
    existingNote.text(formattedNote);
    return;
  }

  // No note in the initial server render (first-ever pending change on this page
  // load). Insert-then-set-text (DD-17): build the aria-live region with empty
  // text first, then set its content in a separate statement so screen readers
  // that only announce on a subsequent mutation still announce the note.
  const pendingNote = $("<p>", {
    class: PENDING_EMAIL_NOTE_CLASS,
    "aria-live": "polite",
  }).appendTo(ACCOUNT_EMAIL_CARD_SELECTOR);
  pendingNote.text(formattedNote);
}

function setInFlight(buttonEl: HTMLButtonElement, inFlight: boolean): void {
  // Re-enable on success too, so the form stays usable for a subsequent change
  // without a page refresh.
  if (inFlight) {
    $(buttonEl).attr("disabled", "disabled").attr("aria-busy", "true");
  } else {
    $(buttonEl).removeAttr("disabled").removeAttr("aria-busy");
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
