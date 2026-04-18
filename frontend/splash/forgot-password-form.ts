import type { Schema, SuccessResponse } from "../types/api-helpers.d.ts";
import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import {
  showSplashModalAlertBanner,
  resetModalFormState,
  handleImproperFormErrors,
  switchModal,
} from "./init.js";

type ForgotPasswordRequest = Schema<"ForgotPasswordRequest">;
type ForgotPasswordSuccess = SuccessResponse<"forgotPassword">;
type ForgotPasswordError = Schema<"ErrorResponse_ForgotPasswordErrorCodes">;

/**
 * Initialize forgot password form handlers
 * Must be called after forgot password form HTML is loaded into the modal
 */
export function initForgotPasswordForm($modal: JQuery): void {
  $modal
    .find("#ToLoginFromForgotPassword")
    .offAndOn("click", () => switchModal($modal, "#LoginModal"));

  $modal
    .find("#submit")
    .offAndOn("click", (event) => handleForgotPassword(event, $modal));

  $modal.on("show.bs.modal", () => resetModalFormState($modal));
}

function handleForgotPassword(
  event: JQuery.TriggeredEvent,
  $modal: JQuery,
): void {
  event.preventDefault();
  $modal.find("#submit").attr("disabled", "disabled");

  const payload: ForgotPasswordRequest = {
    email: String($modal.find("#email").val() ?? ""),
  };

  const forgotPasswordRequest: JQuery.jqXHR = $.ajax({
    url: APP_CONFIG.routes.forgotPassword,
    type: "POST",
    data: JSON.stringify(payload),
    contentType: "application/json",
  });

  forgotPasswordRequest.done((response, textStatus, xhr) =>
    handleForgotPasswordSuccess(response, textStatus, xhr, $modal),
  );
  forgotPasswordRequest.fail((xhr, textStatus, error) =>
    handleForgotPasswordFailure(xhr, textStatus, error, $modal),
  );
}

function handleForgotPasswordSuccess(
  response: ForgotPasswordSuccess,
  _: string,
  xhr: JQuery.jqXHR,
  $modal: JQuery,
): void {
  if (xhr.status === 200) {
    $modal.find(".form-control").removeClass("is-invalid");
    $modal.find(".invalid-feedback").remove();
    showSplashModalAlertBanner($modal, response.message, "success");
    disableSendPasswordResetEmailButton($modal);
  }
}

function disableSendPasswordResetEmailButton($modal: JQuery): void {
  const submitButton = $modal.find("#submit");
  submitButton
    .prop("type", "button")
    .prop("disabled", true)
    .offAndOn("click", function () {
      submitButton.prop("disabled", true);
    });
}

function handleForgotPasswordFailure(
  xhr: JQuery.jqXHR,
  _: string,
  error: string,
  $modal: JQuery,
): void {
  if (!xhr.hasOwnProperty("responseJSON")) {
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

  if (xhr.status === 400 && xhr.responseJSON.hasOwnProperty("errorCode")) {
    const errorJson = xhr.responseJSON as ForgotPasswordError;
    switch (errorJson.errorCode) {
      case 1: {
        handleImproperFormErrors($modal, errorJson);
        $modal.find("#submit").removeAttr("disabled");
        break;
      }
    }
  }
}
