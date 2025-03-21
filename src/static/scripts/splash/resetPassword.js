"use strict";

$("#submit").click((event) => handleResetPassword(event));

$("#SplashModal").on("hide.bs.modal", function (_) {
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

function handleResetPasswordSuccess(response, _, xhr) {
  if (xhr.status === 200) {
    // Password changed!
    $(".form-control").removeClass("is-invalid");
    $(".invalid-feedback").remove();
    hideSplashModalAlertBanner();
    showSplashModalAlertBanner(xhr.responseJSON.message, "success");
    handleUserChangedPassword();
  }
}

function handleUserChangedPassword() {
  $("#submit").removeClass("login-register-buttons");
  $("#submit")
    .prop("type", "button")
    .val("Close")
    .removeClass("btn-success")
    .addClass("btn-warning")
    .offAndOn("click", function (_) {
      bootstrap.Modal.getOrCreateInstance("#SplashModal").hide();
    });
}

function handleResetPasswordFailure(xhr, _, error) {
  if (!xhr.hasOwnProperty("responseJSON")) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // Handle invalid CSRF token error response
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(routes.errorPage);
    return;
  }

  if (xhr.status === 400 && xhr.responseJSON.hasOwnProperty("errorCode")) {
    switch (xhr.responseJSON.errorCode) {
      case 1:
        $(".form-control").removeClass("is-invalid");
        $(".invalid-feedback").remove();
        handleImproperFormErrors(xhr.responseJSON);
        break;
      case 2:
        hideSplashModalAlertBanner();
        showSplashModalAlertBanner(xhr.responseJSON.message, "warning");
        break;
    }
  } else {
    // TODO: Handle other errors here.
    showSplashModalAlertBanner("Unable to process request...", "danger");
  }
}
