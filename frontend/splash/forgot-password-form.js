import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import {
  showSplashModalAlertBanner,
  handleImproperFormErrors,
  disableInputFields,
  loginModalOpenerFromModal,
} from "./init.js";

/**
 * Initialize forgot password form handlers
 * Must be called after forgot password form HTML is loaded into the modal
 */
export function initForgotPasswordForm() {
  $("#ToLoginFromForgotPassword").offAndOn("click", function () {
    loginModalOpenerFromModal();
  });

  $("#submit").offAndOn("click", (event) => handleForgotPassword(event));
}

function handleForgotPassword(event) {
  event.preventDefault();
  $("#submit").attr("disabled", "disabled");

  const forgotPasswordRequest = $.ajax({
    url: APP_CONFIG.routes.forgotPassword,
    type: "POST",
    data: $("#ModalForm").serialize(),
  });

  forgotPasswordRequest.done((response, textStatus, xhr) =>
    handleForgotPasswordSuccess(response, textStatus, xhr),
  );
  forgotPasswordRequest.fail((xhr, textStatus, error) =>
    handleForgotPasswordFailure(xhr, textStatus, error),
  );
}

function handleForgotPasswordSuccess(response, _, xhr) {
  if (xhr.status === 200) {
    $(".form-control").removeClass("is-invalid");
    $(".invalid-feedback").remove();
    showSplashModalAlertBanner(xhr.responseJSON.message, "success");
    disableSendPasswordResetEmailButton();
  }
}

function disableSendPasswordResetEmailButton() {
  const submitButton = $("#submit");
  submitButton
    .prop("type", "button")
    .prop("disabled", true)
    .offAndOn("click", function (_) {
      submitButton.prop("disabled", true);
    });
}

function handleForgotPasswordFailure(xhr, _, error) {
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

  if (xhr.status === 401 && xhr.responseJSON.hasOwnProperty("errorCode")) {
    switch (xhr.responseJSON.errorCode) {
      case 1: {
        handleImproperFormErrors(xhr.responseJSON);
        $("#submit").removeAttr("disabled");
        break;
      }
    }
  } else {
    console.log("You need to handle other errors!");
  }
}
