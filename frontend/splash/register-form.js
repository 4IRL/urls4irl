import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import {
  showSplashModalAlertBanner,
  hideSplashModalAlertBanner,
  handleImproperFormErrors,
  handleUserHasAccountNotEmailValidated,
  switchModal,
  emailValidationModalOpener,
} from "./init.js";

/**
 * Initialize register form handlers
 * Must be called after register form HTML is loaded into the modal
 */
export function initRegisterForm($modal) {
  $modal
    .find("#ToLoginFromRegister")
    .offAndOn("click", () => switchModal($modal, "#LoginModal"));

  $modal
    .find("#submit")
    .offAndOn("click", (event) => handleRegister(event, $modal));

  $modal.on("show.bs.modal", () => {
    $modal.find(".invalid-feedback").remove();
    $modal.find(".form-control").removeClass("is-invalid");
    hideSplashModalAlertBanner($modal);
  });
}

function handleRegister(event, $modal) {
  event.preventDefault();
  $modal.find("#submit").attr("disabled", "disabled");

  const username = $modal.find("#username").val();
  const email = $modal.find("#email").val();
  const confirmEmail = $modal.find("#confirmEmail").val();
  const password = $modal.find("#password").val();
  const confirmPassword = $modal.find("#confirmPassword").val();

  const registerRequest = $.ajax({
    url: APP_CONFIG.routes.register,
    type: "POST",
    data: JSON.stringify({
      username,
      email,
      confirmEmail,
      password,
      confirmPassword,
    }),
    contentType: "application/json",
  });

  registerRequest.done((response, textStatus, xhr) =>
    handleRegisterSuccess(response, textStatus, xhr, $modal),
  );
  registerRequest.fail((xhr, textStatus, error) =>
    handleRegisterFailure(xhr, textStatus, error, $modal),
  );
}

function handleRegisterSuccess(response, _, xhr, $modal) {
  if (xhr.status === 201) {
    emailValidationModalOpener($modal);
  }
}

function handleRegisterFailure(xhr, _, error, $modal) {
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

  if (xhr.responseJSON.hasOwnProperty("errorCode")) {
    switch (xhr.status) {
      case 400: {
        handleImproperFormErrors($modal, xhr.responseJSON);
        $modal.find("#submit").removeAttr("disabled");
        break;
      }
      case 401: {
        // User found but email not yet validated
        handleUserHasAccountNotEmailValidated($modal, xhr.responseJSON.message);
        $modal.find("input").attr("disabled", true);
        break;
      }
    }
  } else {
    showSplashModalAlertBanner(
      $modal,
      "Unable to process request...",
      "danger",
    );
  }
}
