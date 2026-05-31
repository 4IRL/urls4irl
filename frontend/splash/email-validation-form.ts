import type { Schema } from "../types/api-helpers.d.ts";
import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { emit } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import { showSplashModalAlertBanner, resetModalFormState } from "./init.js";
import { VALIDATION_FORM } from "../types/metrics-dim-values.js";

type EmailValidationSuccess = Schema<"EmailValidationResponseSchema">;
type EmailValidationError = Schema<"ErrorResponse">;

export const SEND_INITIAL_EMAIL = true;
export const SKIP_INITIAL_EMAIL = false;

/**
 * Initialize email validation form handlers
 * Must be called after email validation form HTML is loaded into the modal
 * @param $modal - The modal container element
 * @param sendInitialEmail - Whether to send an email on load (true for after register, false for expired token)
 */
export function initEmailValidationForm(
  $modal: JQuery,
  sendInitialEmail: boolean = false,
): void {
  $modal
    .find("#submit")
    .offAndOn("click", (event) => handleValidateEmail($modal, event));

  $modal.on("show.bs.modal", () => resetModalFormState($modal));

  // Send validation email after register, but not if token for validation is expired.
  // Defer until shown.bs.modal so the AJAX response doesn't race the modal fade-in
  // (resetModalFormState fires on show.bs.modal, which precedes shown.bs.modal)
  if (sendInitialEmail) {
    $modal.one("shown.bs.modal", () => handleValidateEmail($modal));
  }
}

function handleValidateEmail(
  $modal: JQuery,
  event: JQuery.TriggeredEvent | null = null,
): void {
  emit({
    event: UI_EVENTS.UI_EMAIL_VALIDATION_SUBMIT,
    trigger: event !== null ? "manual_click" : "auto_after_register",
  });
  if (event !== null) {
    event.preventDefault();
  }

  const validateEmailRequest: JQuery.jqXHR = $.ajax({
    url: APP_CONFIG.routes.sendValidationEmail,
    type: "POST",
    data: $modal.find("#ModalForm").serialize(),
  });

  validateEmailRequest.done((response, textStatus, xhr) =>
    handleValidateEmailSuccess(response, textStatus, xhr, $modal),
  );

  validateEmailRequest.fail((xhr, textStatus, error) =>
    handleValidateEmailFailure(xhr, textStatus, error, $modal),
  );
}

function handleValidateEmailSuccess(
  response: EmailValidationSuccess,
  _: string,
  xhr: JQuery.jqXHR,
  $modal: JQuery,
): void {
  if (xhr.status === 200) {
    // Email sent!
    showSplashModalAlertBanner($modal, response.message, "success");
  }
}

function handleValidateEmailFailure(
  xhr: JQuery.jqXHR,
  _: string,
  error: string,
  $modal: JQuery,
): void {
  if (xhr.status !== 400 && xhr.status !== 429) {
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  if (!("responseJSON" in xhr)) {
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  if (!("errorCode" in xhr.responseJSON)) {
    // Handle other errors here
    emit({
      event: UI_EVENTS.UI_VALIDATION_ERROR,
      form: VALIDATION_FORM.EMAIL_VALIDATION,
    });
    showSplashModalAlertBanner(
      $modal,
      "Unable to process request...",
      "danger",
    );
    return;
  }

  const errorJson = xhr.responseJSON as EmailValidationError;
  const errorCodes = APP_CONFIG.constants.VALIDATE_EMAIL_ERROR_CODES as Record<
    string,
    number
  >;
  emit({
    event: UI_EVENTS.UI_VALIDATION_ERROR,
    form: VALIDATION_FORM.EMAIL_VALIDATION,
  });
  switch (errorJson.errorCode) {
    case errorCodes.MAX_TOTAL_EMAIL_VALIDATION_ATTEMPTS:
      showSplashModalAlertBanner($modal, errorJson.message, "danger");
      break;
    case errorCodes.MAX_TIME_EMAIL_VALIDATION_ATTEMPTS:
    case errorCodes.EMAIL_SEND_FAILURE:
    case errorCodes.MAILJET_SERVER_FAILURE:
      showSplashModalAlertBanner($modal, errorJson.message, "warning");
      break;
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}
