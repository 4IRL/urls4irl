import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import {
  showSplashModalAlertBanner,
  handleImproperFormErrors,
  switchModal,
} from "./init.js";

/**
 * Initialize forgot password form handlers
 * Must be called after forgot password form HTML is loaded into the modal
 */
export function initForgotPasswordForm($modal) {
  $modal
    .find("#ToLoginFromForgotPassword")
    .offAndOn("click", () =>
      switchModal("#ForgotPasswordModal", "#LoginModal"),
    );

  $modal
    .find("#submit")
    .offAndOn("click", (event) => handleForgotPassword(event, $modal));
}

function handleForgotPassword(event, $modal) {
  event.preventDefault();
  $modal.find("#submit").attr("disabled", "disabled");

  const forgotPasswordRequest = $.ajax({
    url: APP_CONFIG.routes.forgotPassword,
    type: "POST",
    data: JSON.stringify({ email: $modal.find("#email").val() }),
    contentType: "application/json",
  });

  forgotPasswordRequest.done((response, textStatus, xhr) =>
    handleForgotPasswordSuccess(response, textStatus, xhr, $modal),
  );
  forgotPasswordRequest.fail((xhr, textStatus, error) =>
    handleForgotPasswordFailure(xhr, textStatus, error, $modal),
  );
}

function handleForgotPasswordSuccess(response, _, xhr, $modal) {
  if (xhr.status === 200) {
    $modal.find(".form-control").removeClass("is-invalid");
    $modal.find(".invalid-feedback").remove();
    showSplashModalAlertBanner($modal, xhr.responseJSON.message, "success");
    disableSendPasswordResetEmailButton($modal);
  }
}

function disableSendPasswordResetEmailButton($modal) {
  const submitButton = $modal.find("#submit");
  submitButton
    .prop("type", "button")
    .prop("disabled", true)
    .offAndOn("click", function (_) {
      submitButton.prop("disabled", true);
    });
}

function handleForgotPasswordFailure(xhr, _, error, $modal) {
  if (!xhr.hasOwnProperty("responseJSON")) {
    if (xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8") {
      switch (xhr.status) {
        case 403: {
          $("body").html(xhr.responseText);
          return;
        }
      }
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  if (xhr.status === 400 && xhr.responseJSON.hasOwnProperty("errorCode")) {
    switch (xhr.responseJSON.errorCode) {
      case 1: {
        handleImproperFormErrors($modal, xhr.responseJSON);
        $modal.find("#submit").removeAttr("disabled");
        break;
      }
    }
  }
}
