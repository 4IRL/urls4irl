"use strict";

$("#submit").click((event) => handleValidateEmail(event));

$("#SplashModal").on("hide.bs.modal", function (e) {
  $("#SplashModal").off("hide.bs.modal");
  const searchParams = new URLSearchParams(window.location.search);
  if (searchParams.has('token')) {
    window.location.replace(routes.logout());
  } else {
    $.get(routes.logout());
  }
});

function handleValidateEmail(event = null) {
  event !== null ? event.preventDefault() : null;

  const validateEmailRequest = $.ajax({
    url: routes.send_validation_email(),
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

function handleValidateEmailSuccess(response, textStatus, xhr) {
  if (xhr.status === 200) {
    // Email sent!
    showSplashModalAlertBanner(xhr.responseJSON.Message, "success");
  }
}

function handleValidateEmailFailure(xhr, textStatus, error) {
  if (
    xhr.status == 429 &&
    xhr.responseJSON.hasOwnProperty("Error_code")
  ) {
    switch (xhr.responseJSON.Error_code) {
      case 1:
        showSplashModalAlertBanner(xhr.responseJSON.Message, "danger");
        break;
      case 2:
        showSplashModalAlertBanner(xhr.responseJSON.Message, "warning");
        break;
    }
  } else if (
    xhr.status == 400 &&
    xhr.responseJSON.hasOwnProperty("Error_code")
  ) {
    if (
      xhr.responseJSON.Error_code == 3 ||
      xhr.responseJSON.Error_code == 4
    ) {
      showSplashModalAlertBanner(xhr.responseJSON.Message, "warning");
    }
  } else {
    // TODO: Handle other errors here.
    showSplashModalAlertBanner("Unable to process request...", "danger");
    console.log("You need to handle other errors!");
  }
}

function sendInitialEmailOnLoad() {
  // Send validation email after register, but not if token for validation is expired
  const searchParams = new URLSearchParams(window.location.search);
  if (!searchParams.has('token')) {
    handleValidateEmail();
  }
}
sendInitialEmailOnLoad();
