"use strict";

$(document).ready(function () {
  setToRegisterButton();
  setToLoginButton();
});

function setToRegisterButton() {
  $(".to-register")
    .off("click")
    .on("click", function () {
      registerModalOpener();
    });
}

function setToLoginButton() {
  $(".to-login")
    .off("click")
    .on("click", function () {
      loginModalOpener();
    });
}

function loginModalOpener() {
  const modalOpener = $.get(routes.login());

  modalOpener.done((data, textStatus, xhr) => {
    if (xhr.status === 200) {
      $("#SplashModal .modal-content").html(data);
      bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    };
  });

  modalOpener.fail(() => {
    bootstrap.Modal.getOrCreateInstance("#SplashErrorModal").show();
    $("#SplashErrorModalAlertBanner").text("Unable to load login form...");
  });
}

function registerModalOpener() {
  const modalOpener = $.get(routes.register());

  modalOpener.done((data, textStatus, xhr) => {
    if (xhr.status === 200) {
      $("#SplashModal .modal-content").html(data);
      bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    };
  });

  modalOpener.fail(() => {
    bootstrap.Modal.getOrCreateInstance("#SplashErrorModal").show();
    $("#SplashErrorModalAlertBanner").text("Unable to load register form...");
  });
}

function hideSplashModalAlertBanner() {
  $("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-display")
    .removeClassStartingWith("alert-")
    .addClass("alert-banner-splash-modal-hide");
}

function showSplashModalAlertBanner(message, category) {
  $("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-hide")
    .removeClassStartingWith("alert-")
    .addClass("alert-" + category)
    .addClass("alert-banner-splash-modal-display")
    .text(message);
}

function disableInputFields() {
  $("input").attr("disabled", true);
}

function handleUserHasAccountNotEmailValidated(message) {
  $(".form-control").removeClass("is-invalid");
  $(".invalid-feedback").remove();
  $(".to-forgot-password").remove();
  const alertBanner = $("#SplashModalAlertBanner");
  alertBanner
   .removeClass("alert-banner-splash-modal-hide")
   .addClass("alert-info alert-banner-splash-modal-show")
   .append($("<div>" + message + "</div>"))
   .append(
     $(
       '<button type="button" class="btn btn-link btn-block">Validate My Email</button>',
     )
       .off("click")
       .on("click", () => {
          $("#SplashModal").off("hide.bs.modal", logoutOnExit);
          emailValidationModalOpener();
       }),
   );

  $(".register-to-login-footer").remove();
  $(".modal-footer").remove();

  const logoutOnExit = () => { 
    $.get(routes.logout()) 
    $("#SplashModal").off("hide.bs.modal", logoutOnExit);
  };
  $("#SplashModal").on("hide.bs.modal", logoutOnExit);     
}

function emailValidationModalOpener() {
  const modalOpener = $.get(routes.confirm_email_after_register());

  modalOpener.done((data, textStatus, xhr) => {
    xhr.status === 200 ? $("#SplashModal .modal-content").html(data) : null;
  });

  modalOpener.fail(() => {
    showSplashModalAlertBanner("Unable to load email validation modal...", "danger");
  });
}

function handleImproperFormErrors(errorResponse) {
  $(".invalid-feedback").remove();
  $(".alert").each(function () {
    if ($(this).attr("id") !== "SplashModalAlertBanner") {
      $(this).remove();
    }
  });
  $(".form-control").removeClass("is-invalid");
  for (let key in errorResponse.Errors) {
    switch (key) {
      case "username":
      case "password":
      case "email":
      case "confirm_email":
      case "confirm_password":
      case "new_password":
      case "confirm_new_password":
        let errorMessage = errorResponse.Errors[key][0];
        displayFormErrors(key, errorMessage);
        break;
      default:
        // Error for a field that doesn't exist
        console.log("No op.");
    }
  }
}

function displayFormErrors(key, errorMessage) {
  $('<div class="invalid-feedback"><span>' + errorMessage + "</span></div>")
    .insertAfter("#" + key)
    .show();
  $("#" + key).addClass("is-invalid");
}

// Extension to allow removal of a class based on a prefix
$.fn.removeClassStartingWith = function (filter) {
  $(this).removeClass(function (index, className) {
    return (
      className.match(new RegExp("\\S*" + filter + "\\S*", "g")) || []
    ).join(" ");
  });
  return this;
};
