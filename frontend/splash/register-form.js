import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import {
  showSplashModalAlertBanner,
  handleImproperFormErrors,
  handleUserHasAccountNotEmailValidated,
  loginModalOpenerFromModal,
  emailValidationModalOpener,
} from "./init.js";

/**
 * Initialize register form handlers
 * Must be called after register form HTML is loaded into the modal
 */
export function initRegisterForm() {
  $("#ToLoginFromRegister").offAndOn("click", function () {
    loginModalOpenerFromModal();
  });

  $("#submit").offAndOn("click", (event) => handleRegister(event));
}

function handleRegister(event) {
  event.preventDefault();
  $("#submit").attr("disabled", "disabled");

  const username = $("#username").val();
  const email = $("#email").val();
  const confirmEmail = $("#confirmEmail").val();
  const password = $("#password").val();
  const confirmPassword = $("#confirmPassword").val();

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
    handleRegisterSuccess(response, textStatus, xhr),
  );
  registerRequest.fail((xhr, textStatus, error) =>
    handleRegisterFailure(xhr, textStatus, error),
  );
}

function handleRegisterSuccess(response, _, xhr) {
  if (xhr.status === 201) {
    emailValidationModalOpener();
  }
}

function handleRegisterFailure(xhr, _, error) {
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
        handleImproperFormErrors(xhr.responseJSON);
        $("#submit").removeAttr("disabled");
        break;
      }
      case 401: {
        // User found but email not yet validated
        handleUserHasAccountNotEmailValidated(xhr.responseJSON.message);
        $("input").attr("disabled", true);
        break;
      }
    }
  } else {
    showSplashModalAlertBanner("Unable to process request...", "danger");
  }
}
