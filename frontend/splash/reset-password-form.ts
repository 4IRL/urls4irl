import type { Schema, SuccessResponse } from "../types/api-helpers.d.ts";
import { $, bootstrap } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { emit } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import {
  showSplashModalAlertBanner,
  hideSplashModalAlertBanner,
  handleImproperFormErrors,
} from "./init.js";
import { VALIDATION_FORM } from "../types/metrics-dim-values.js";

type ResetPasswordRequest = Schema<"ResetPasswordRequest">;
type ResetPasswordSuccess = SuccessResponse<"resetPassword">;
type ResetPasswordError = Schema<"ErrorResponse_ResetPasswordErrorCodes">;

/**
 * Initialize reset password form handlers
 * Must be called after reset password form HTML is loaded into the modal
 */
export function initResetPasswordForm($modal: JQuery): void {
  $modal
    .find("form")
    .offAndOn("submit", (event) => handleResetPassword(event, $modal));

  $modal.on("hide.bs.modal", function () {
    $modal.off("hide.bs.modal");
    window.location.replace("/");
  });

  // Mark the form as ready only after the Bootstrap modal show transition
  // has completed. The submit handler is bound synchronously above, but
  // Bootstrap's `show()` is async — it fires `shown.bs.modal` after the
  // CSS transition (~150-300ms) and auto-focuses the modal element at that
  // point, which can steal focus from inputs a test has already typed into.
  // Gating readiness on `shown.bs.modal` means tests that wait on the ready
  // signal never race the auto-focus or the form's default-submit fallback
  // (which would fire if the handler weren't bound yet). Bootstrap fires
  // this event even when the modal ships pre-rendered with `class="show"`,
  // so no fallback is needed.
  $modal.one("shown.bs.modal", () => {
    $modal.find("form").attr("data-form-ready", "true");
  });
}

function handleResetPassword(
  event: JQuery.TriggeredEvent,
  $modal: JQuery,
): void {
  event.preventDefault();
  emit({ event: UI_EVENTS.UI_RESET_PASSWORD_SUBMIT });

  const payload: ResetPasswordRequest = {
    newPassword: String($modal.find("#newPassword").val() ?? ""),
    confirmNewPassword: String($modal.find("#confirmNewPassword").val() ?? ""),
  };

  const resetPasswordRequest: JQuery.jqXHR = $.ajax({
    url: window.location.pathname,
    type: "POST",
    data: JSON.stringify(payload),
    contentType: "application/json",
  });

  resetPasswordRequest.done((response, textStatus, xhr) => {
    handleResetPasswordSuccess(response, textStatus, xhr, $modal);
  });

  resetPasswordRequest.fail((xhr, textStatus, error) => {
    handleResetPasswordFailure(xhr, textStatus, error, $modal);
  });
}

function handleResetPasswordSuccess(
  response: ResetPasswordSuccess,
  _: string,
  xhr: JQuery.jqXHR,
  $modal: JQuery,
): void {
  if (xhr.status === 200) {
    // Password changed!
    $modal.find(".form-control").removeClass("is-invalid");
    $modal.find(".invalid-feedback").remove();
    hideSplashModalAlertBanner($modal);
    showSplashModalAlertBanner($modal, response.message, "success");
    handleUserChangedPassword($modal);
  }
}

function handleUserChangedPassword($modal: JQuery): void {
  $modal.find("#submit").removeClass("login-register-buttons");
  $modal
    .find("#submit")
    .prop("type", "button")
    .val("Close")
    .removeClass("btn-success")
    .addClass("btn-warning")
    .offAndOn("click", function () {
      bootstrap.Modal.getOrCreateInstance($modal[0]).hide();
    });
}

function handleResetPasswordFailure(
  xhr: JQuery.jqXHR,
  _: string,
  error: string,
  $modal: JQuery,
): void {
  if (!("responseJSON" in xhr)) {
    if (xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8") {
      switch (xhr.status) {
        case 403:
        case 429: {
          showNewPageOnAJAXHTMLResponse(xhr.responseText);
          return;
        }
      }
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  if (xhr.status === 400 && "errorCode" in xhr.responseJSON) {
    const errorJson = xhr.responseJSON as ResetPasswordError;
    switch (errorJson.errorCode) {
      case 1:
        emit({
          event: UI_EVENTS.UI_VALIDATION_ERROR,
          form: VALIDATION_FORM.RESET_PASSWORD,
        });
        $modal.find(".form-control").removeClass("is-invalid");
        $modal.find(".invalid-feedback").remove();
        handleImproperFormErrors($modal, errorJson);
        break;
    }
  } else {
    showSplashModalAlertBanner(
      $modal,
      "Unable to process request...",
      "danger",
    );
  }
}
