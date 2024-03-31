"use strict";

$("#submit").click((event) => handleResetPassword(event));

$("#SplashModal").on("hide.bs.modal", function (e) {
  $("#SplashModal").off("hide.bs.modal");
  window.location.replace("/");
});

function handleResetPassword(event) {
  event.preventDefault();

  const resetPasswordRequest = $.ajax({
    url: window.location.pathname,
    type: "POST",
    data: $("#ModalForm").serialize(),
  });

  resetPasswordRequest.done((response, textStatus, xhr) => {
    handleResetPasswordSuccess(response, textStatus, xhr);
  });

  resetPasswordRequest.fail((xhr, textStatus, error) => {
    handleResetPasswordFailure(xhr, textStatus, error);
  });
}

function handleResetPasswordSuccess(response, textStatus, xhr) {
  if (xhr.status === 200) {
    // Password changed!
    $(".form-control").removeClass("is-invalid");
    $(".invalid-feedback").remove();
    hideSplashModalAlertBanner();
    showSplashModalAlertBanner(xhr.responseJSON.Message, "success");
    handleUserChangedPassword();
  }
}

function handleUserChangedPassword() {
  $("#submit").removeClass("login-register-buttons");
  $("#submit")
    .off("click")
    .prop("type", "button")
    .val("Close")
    .removeClass("btn-success")
    .addClass("btn-warning")
    .on("click", function (e) {
      bootstrap.Modal.getOrCreateInstance("#SplashModal").hide();
    });
}

function handleResetPasswordFailure(xhr, textStatus, error) {
  if (xhr.status == 400 && xhr.responseJSON.hasOwnProperty("Error_code")) {
    switch (xhr.responseJSON.Error_code) {
      case 1:
        $(".form-control").removeClass("is-invalid");
        $(".invalid-feedback").remove();
        showSplashModalAlertBanner(xhr.responseJSON.Message, "warning");
        break;
      case 2:
        hideSplashModalAlertBanner();
        handleImproperFormErrors(xhr.responseJSON);
        break;
    }
  } else {
    // TODO: Handle other errors here.
    showSplashModalAlertBanner("Unable to process request...", "danger");
    console.log("You need to handle other errors!");
  }
}
