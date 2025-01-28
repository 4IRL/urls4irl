"use strict";

$("#submit").click((event) => handleValidateEmail(event));

$("#SplashModal").on("hide.bs.modal", function (_) {
  $("#SplashModal").off("hide.bs.modal");
  const searchParams = new URLSearchParams(window.location.search);
  if (searchParams.has("token")) {
    window.location.replace(routes.logout);
  } else {
    $.get(routes.logout);
  }
});

function handleValidateEmail(event = null) {
  event !== null ? event.preventDefault() : null;

  const validateEmailRequest = $.ajax({
    url: routes.sendValidationEmail,
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
    window.location.assign(routes.errorPage);
    return;
  }

  if (!xhr.hasOwnProperty("responseJSON")) {
    window.location.assign(routes.errorPage);
    return;
  }

  if (!xhr.responseJSON.hasOwnProperty("errorCode")) {
    // Handle other errors here
    showSplashModalAlertBanner("Unable to process request...", "danger");
    return;
  }

  switch (xhr.responseJSON.errorCode) {
    case 1:
      showSplashModalAlertBanner(xhr.responseJSON.message, "danger");
      break;
    case 2:
      showSplashModalAlertBanner(xhr.responseJSON.message, "warning");
      break;
    case 3:
    case 4:
      showSplashModalAlertBanner(xhr.responseJSON.message, "warning");
      break;
    default:
      window.location.assign(routes.errorPage);
  }
}

function sendInitialEmailOnLoad() {
  // Send validation email after register, but not if token for validation is expired
  const searchParams = new URLSearchParams(window.location.search);
  if (!searchParams.has("token")) {
    handleValidateEmail();
  }
}
sendInitialEmailOnLoad();
