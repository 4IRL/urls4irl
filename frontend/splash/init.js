import { $, bootstrap } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import { NAVBAR_TOGGLER } from "./navbar.js";
import { initLoginForm } from "./login-form.js";
import { initRegisterForm } from "./register-form.js";
import { initForgotPasswordForm } from "./forgot-password-form.js";
import { initResetPasswordForm } from "./reset-password-form.js";
import { initEmailValidationForm } from "./email-validation-form.js";

/**
 * Initialize splash page
 * Sets up button handlers and rate limit error handling
 */
export function initSplash() {
  setToRegisterButton();
  setToLoginButton();

  // Setup rate limit error handler
  $.ajaxPrefilter(function (options, originalOptions, jqXHR) {
    let originalError = options.error;

    options.error = function (jqXHR, textStatus, errorThrown) {
      if (jqXHR.status === 429) {
        showNewPageOnAJAXHTMLResponse(jqXHR.responseText);
        return; // Prevents both .error and .fail() from being called
      }

      if (originalError) {
        originalError.call(this, jqXHR, textStatus, errorThrown);
      }
    };
  });
}

function setToRegisterButton() {
  $(".to-register").offAndOn("click", function () {
    registerModalOpener();
    NAVBAR_TOGGLER.toggler.hide();
  });
}

function setToLoginButton() {
  $(".to-login").offAndOn("click", function () {
    loginModalOpener();
    NAVBAR_TOGGLER.toggler.hide();
  });
}

export function loginModalOpener() {
  const modalOpener = $.get(APP_CONFIG.routes.login);

  modalOpener.done((data, _, xhr) => {
    if (xhr.status === 200) {
      $("#SplashModal .modal-content").html(data);
      initLoginForm();
      bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    }
  });

  modalOpener.fail((xhr) => {
    bootstrap.Modal.getOrCreateInstance("#SplashErrorModal").show();
    $("#SplashErrorModalAlertBanner").text("Unable to load login form...");
  });
}

export function loginModalOpenerFromModal() {
  const modalOpener = $.get(APP_CONFIG.routes.login);

  modalOpener.done((data, _, xhr) => {
    if (xhr.status === 200) {
      $("#SplashModal .modal-content").html(data);
      initLoginForm();
    }
  });

  modalOpener.fail((xhr) => {
    bootstrap.Modal.getOrCreateInstance("#SplashErrorModal").show();
    $("#SplashErrorModalAlertBanner").text("Unable to load login form...");
  });
}

export function registerModalOpener() {
  const modalOpener = $.get(APP_CONFIG.routes.register);

  modalOpener.done((data, _, xhr) => {
    if (xhr.status === 200) {
      $("#SplashModal .modal-content").html(data);
      initRegisterForm();
      bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    }
  });

  modalOpener.fail((xhr) => {
    bootstrap.Modal.getOrCreateInstance("#SplashErrorModal").show();
    $("#SplashErrorModalAlertBanner").text("Unable to load register form...");
  });
}

export function hideSplashModalAlertBanner() {
  $("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-display")
    .removeClassStartingWith("alert-")
    .addClass("alert-banner-splash-modal-hide");
}

export function showSplashModalAlertBanner(message, category) {
  $("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-hide")
    .removeClassStartingWith("alert-")
    .addClass("alert-" + category)
    .addClass("alert-banner-splash-modal-display")
    .text(message);
}

export function disableInputFields() {
  $("input").attr("disabled", true);
}

export function handleUserHasAccountNotEmailValidated(message) {
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
        `<button type="button" class="btn btn-link btn-block">${APP_CONFIG.strings.VALIDATE_MY_EMAIL}</button>`,
      ).offAndOn("click", () => {
        $("#SplashModal").off("hide.bs.modal", logoutOnExit);
        emailValidationModalOpener();
      }),
    );

  $(".register-to-login-footer").remove();
  $(".modal-footer").remove();

  const logoutOnExit = () => {
    $.get(APP_CONFIG.routes.logout);
    $("#SplashModal").off("hide.bs.modal", logoutOnExit);
  };
  $("#SplashModal").on("hide.bs.modal", logoutOnExit);
}

export function emailValidationModalOpener() {
  const modalOpener = $.get(APP_CONFIG.routes.confirmEmailAfterRegister);

  modalOpener.done((data, _, xhr) => {
    if (xhr.status === 200) {
      $("#SplashModal .modal-content").html(data);
      // Initialize email validation form and send initial email
      initEmailValidationForm(true);
    }
  });

  modalOpener.fail((xhr) => {
    showSplashModalAlertBanner(
      "Unable to load email validation modal...",
      "danger",
    );
  });
}

export function handleImproperFormErrors(errorResponse) {
  $(".invalid-feedback").remove();
  $(".alert").each(function () {
    if ($(this).attr("id") !== "SplashModalAlertBanner") {
      $(this).remove();
    }
  });
  $(".form-control").removeClass("is-invalid");
  for (let key in errorResponse.errors) {
    switch (key) {
      case "username":
      case "password":
      case "email":
      case "confirmEmail":
      case "confirmPassword":
      case "newPassword":
      case "confirmNewPassword":
        let errorMessage = errorResponse.errors[key][0];
        displayFormErrors(key, errorMessage);
        break;
      default:
        // Error for a field that doesn't exist
        console.log("No op.");
    }
  }
}

export function displayFormErrors(key, errorMessage) {
  $('<div class="invalid-feedback"><span>' + errorMessage + "</span></div>")
    .insertAfter("#" + key)
    .show();
  $("#" + key).addClass("is-invalid");
}
