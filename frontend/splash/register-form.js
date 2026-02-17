import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import {
  showSplashModalAlertBanner,
  handleImproperFormErrors,
  handleUserHasAccountNotEmailValidated,
  loginModalOpenerFromModal,
} from "./init.js";
import { initEmailValidationForm } from "./email-validation-form.js";

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

  const registerRequest = $.ajax({
    url: APP_CONFIG.routes.register,
    type: "POST",
    data: $("#ModalForm").serialize(),
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
    $("#SplashModal .modal-content").html(response);
    // Initialize email validation form and send initial email
    initEmailValidationForm(true);
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
