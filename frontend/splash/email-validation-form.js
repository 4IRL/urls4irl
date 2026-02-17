import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { showSplashModalAlertBanner } from "./init.js";

/**
 * Initialize email validation form handlers
 * Must be called after email validation form HTML is loaded into the modal
 * @param {boolean} sendInitialEmail - Whether to send an email on load (true for after register, false for expired token)
 */
export function initEmailValidationForm(sendInitialEmail = false) {
  $("#submit").offAndOn("click", (event) => handleValidateEmail(event));

  $("#SplashModal").on("hide.bs.modal", function (_) {
    $("#SplashModal").off("hide.bs.modal");
    const searchParams = new URLSearchParams(window.location.search);
    if (searchParams.has("token")) {
      window.location.replace(APP_CONFIG.routes.logout);
    } else {
      $.get(APP_CONFIG.routes.logout);
    }
  });

  // Send validation email after register, but not if token for validation is expired
  if (sendInitialEmail) {
    handleValidateEmail();
  }
}

function handleValidateEmail(event = null) {
  if (event !== null) {
    event.preventDefault();
  }

  const validateEmailRequest = $.ajax({
    url: APP_CONFIG.routes.sendValidationEmail,
    type: "POST",
    data: $("#ModalForm").serialize(),
  });

  validateEmailRequest.done((response, textStatus, xhr) =>
    handleValidateEmailSuccess(response, textStatus, xhr),
  );

  validateEmailRequest.fail((xhr, textStatus, error) =>
    handleValidateEmailFailure(xhr, textStatus, error),
  );
}

function handleValidateEmailSuccess(response, _, xhr) {
  if (xhr.status === 200) {
    // Email sent!
    showSplashModalAlertBanner(xhr.responseJSON.message, "success");
  }
}

function handleValidateEmailFailure(xhr, _, error) {
  if (xhr.status !== 400 && xhr.status !== 429) {
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  if (!xhr.hasOwnProperty("responseJSON")) {
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  if (!xhr.responseJSON.hasOwnProperty("errorCode")) {
    // Handle other errors here
    showSplashModalAlertBanner("Unable to process request...", "danger");
    return;
  }

  const errorCodes = APP_CONFIG.constants.VALIDATE_EMAIL_ERROR_CODES;
  switch (xhr.responseJSON.errorCode) {
    case errorCodes.MAX_TOTAL_EMAIL_VALIDATION_ATTEMPTS:
      showSplashModalAlertBanner(xhr.responseJSON.message, "danger");
      break;
    case errorCodes.MAX_TIME_EMAIL_VALIDATION_ATTEMPTS:
    case errorCodes.EMAIL_SEND_FAILURE:
    case errorCodes.MAILJET_SERVER_FAILURE:
      showSplashModalAlertBanner(xhr.responseJSON.message, "warning");
      break;
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}
