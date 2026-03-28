import { $, bootstrap } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import {
  showSplashModalAlertBanner,
  hideSplashModalAlertBanner,
  handleImproperFormErrors,
} from "./init.js";

/**
 * Initialize reset password form handlers
 * Must be called after reset password form HTML is loaded into the modal
 * @param {jQuery} $modal - The modal container element
 */
export function initResetPasswordForm($modal) {
  $modal
    .find("#submit")
    .offAndOn("click", (event) => handleResetPassword(event, $modal));

  $modal.on("hide.bs.modal", function (_) {
    $modal.off("hide.bs.modal");
    window.location.replace("/");
  });
}

function handleResetPassword(event, $modal) {
  event.preventDefault();

  const newPassword = $modal.find("#newPassword").val();
  const confirmNewPassword = $modal.find("#confirmNewPassword").val();

  const resetPasswordRequest = $.ajax({
    url: window.location.pathname,
    type: "POST",
    data: JSON.stringify({ newPassword, confirmNewPassword }),
    contentType: "application/json",
  });

  resetPasswordRequest.done((response, textStatus, xhr) => {
    handleResetPasswordSuccess(response, textStatus, xhr, $modal);
  });

  resetPasswordRequest.fail((xhr, textStatus, error) => {
    handleResetPasswordFailure(xhr, textStatus, error, $modal);
  });
}

function handleResetPasswordSuccess(response, _, xhr, $modal) {
  if (xhr.status === 200) {
    // Password changed!
    $modal.find(".form-control").removeClass("is-invalid");
    $modal.find(".invalid-feedback").remove();
    hideSplashModalAlertBanner($modal);
    showSplashModalAlertBanner($modal, xhr.responseJSON.message, "success");
    handleUserChangedPassword($modal);
  }
}

function handleUserChangedPassword($modal) {
  $modal.find("#submit").removeClass("login-register-buttons");
  $modal
    .find("#submit")
    .prop("type", "button")
    .val("Close")
    .removeClass("btn-success")
    .addClass("btn-warning")
    .offAndOn("click", function (_) {
      const modalElement = $modal[0];
      bootstrap.Modal.getOrCreateInstance(modalElement).hide();
    });
}

function handleResetPasswordFailure(xhr, _, error, $modal) {
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
    switch (xhr.responseJSON.errorCode) {
      case 1:
        $modal.find(".form-control").removeClass("is-invalid");
        $modal.find(".invalid-feedback").remove();
        handleImproperFormErrors($modal, xhr.responseJSON);
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
