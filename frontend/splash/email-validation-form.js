import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { showSplashModalAlertBanner } from "./init.js";

/**
 * Initialize email validation form handlers
 * Must be called after email validation form HTML is loaded into the modal
 * @param {jQuery} $modal - The modal container element
 * @param {boolean} sendInitialEmail - Whether to send an email on load (true for after register, false for expired token)
 */
export function initEmailValidationForm($modal, sendInitialEmail = false) {
  $modal
    .find("#submit")
    .offAndOn("click", (event) => handleValidateEmail(event, $modal));

  $modal.on("show.bs.modal", () => {
    $modal.find(".invalid-feedback").remove();
    $modal.find(".form-control").removeClass("is-invalid");
    $modal.find("#SplashModalAlertBanner").addClass("d-none");
  });

  // Send validation email after register, but not if token for validation is expired
  if (sendInitialEmail) {
    handleValidateEmail(null, $modal);
  }
}

function handleValidateEmail(event = null, $modal) {
  if (event !== null) {
    event.preventDefault();
  }

  const validateEmailRequest = $.ajax({
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

function handleValidateEmailSuccess(response, _, xhr, $modal) {
  if (xhr.status === 200) {
    // Email sent!
    showSplashModalAlertBanner($modal, xhr.responseJSON.message, "success");
  }
}

function handleValidateEmailFailure(xhr, _, error, $modal) {
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
    showSplashModalAlertBanner(
      $modal,
      "Unable to process request...",
      "danger",
    );
    return;
  }

  const errorCodes = APP_CONFIG.constants.VALIDATE_EMAIL_ERROR_CODES;
  switch (xhr.responseJSON.errorCode) {
    case errorCodes.MAX_TOTAL_EMAIL_VALIDATION_ATTEMPTS:
      showSplashModalAlertBanner($modal, xhr.responseJSON.message, "danger");
      break;
    case errorCodes.MAX_TIME_EMAIL_VALIDATION_ATTEMPTS:
    case errorCodes.EMAIL_SEND_FAILURE:
    case errorCodes.MAILJET_SERVER_FAILURE:
      showSplashModalAlertBanner($modal, xhr.responseJSON.message, "warning");
      break;
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}
