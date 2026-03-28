import { $, bootstrap } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import { NAVBAR_TOGGLER } from "./navbar.js";
import { initLoginForm } from "./login-form.js";
import { initRegisterForm } from "./register-form.js";
import { initForgotPasswordForm } from "./forgot-password-form.js";
import {
  initEmailValidationForm,
  SEND_INITIAL_EMAIL,
} from "./email-validation-form.js";

/**
 * Initialize splash page
 * Sets up button handlers and rate limit error handling
 */
export function initSplash() {
  setToRegisterButton();
  setToLoginButton();
  initLoginForm($("#LoginModal"));
  initRegisterForm($("#RegisterModal"));
  initForgotPasswordForm($("#ForgotPasswordModal"));

  // Auto-show email validation modal for authenticated-but-not-validated users
  const splashConfig = document.getElementById("splashConfig");
  if (splashConfig && splashConfig.dataset.showEmailValidation === "true") {
    bootstrap.Modal.getOrCreateInstance("#EmailValidationModal").show();
    initEmailValidationForm($("#EmailValidationModal"), SEND_INITIAL_EMAIL);
    const logoutOnExit = createLogoutOnExit();
    $("#EmailValidationModal").one("hide.bs.modal", logoutOnExit);
  }

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

export function createLogoutOnExit() {
  return () => {
    $.get(APP_CONFIG.routes.logout).always(() => {
      window.location.replace("/");
    });
  };
}

export function switchModal($fromModal, toSelector) {
  const fromModal = bootstrap.Modal.getInstance($fromModal[0]);
  if (fromModal) {
    $fromModal.one("hidden.bs.modal", () => {
      bootstrap.Modal.getOrCreateInstance(toSelector).show();
    });
    fromModal.hide();
  } else {
    bootstrap.Modal.getOrCreateInstance(toSelector).show();
  }
}

export function loginModalOpener() {
  bootstrap.Modal.getOrCreateInstance("#LoginModal").show();
}

export function registerModalOpener() {
  bootstrap.Modal.getOrCreateInstance("#RegisterModal").show();
}

export function emailValidationModalOpener($fromModal) {
  switchModal($fromModal, "#EmailValidationModal");
  initEmailValidationForm($("#EmailValidationModal"), SEND_INITIAL_EMAIL);
  const logoutOnExit = createLogoutOnExit();
  $("#EmailValidationModal").one("hide.bs.modal", logoutOnExit);
}

export function hideSplashModalAlertBanner($modal) {
  $modal
    .find("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-display")
    .removeClassStartingWith("alert-")
    .addClass("alert-banner-splash-modal-hide");
}

export function showSplashModalAlertBanner($modal, message, category) {
  $modal
    .find("#SplashModalAlertBanner")
    .removeClass("d-none")
    .removeClass("alert-banner-splash-modal-hide")
    .removeClassStartingWith("alert-")
    .addClass("alert-" + category)
    .addClass("alert-banner-splash-modal-display")
    .text(message);
}

export function disableInputFields($modal) {
  $modal.find("input").attr("disabled", true);
}

export function handleUserHasAccountNotEmailValidated($sourceModal, message) {
  const logoutOnExit = createLogoutOnExit();

  $sourceModal.find(".form-control").removeClass("is-invalid");
  $sourceModal.find(".invalid-feedback").remove();
  $sourceModal.find(".to-forgot-password").remove();
  const alertBanner = $sourceModal.find("#SplashModalAlertBanner");
  alertBanner
    .removeClass("d-none")
    .removeClass("alert-banner-splash-modal-hide")
    .addClass("alert-info alert-banner-splash-modal-show")
    .append($("<div>" + message + "</div>"))
    .append(
      $(
        `<button type="button" class="btn btn-link btn-block">${APP_CONFIG.strings.VALIDATE_MY_EMAIL}</button>`,
      ).offAndOn("click", () => {
        $sourceModal.off("hide.bs.modal", logoutOnExit);
        emailValidationModalOpener($sourceModal);
      }),
    );

  $sourceModal.find(".register-to-login-footer").remove();
  $sourceModal.find(".modal-footer").remove();
  $sourceModal.one("hide.bs.modal", logoutOnExit);
}

export function handleImproperFormErrors($modal, errorResponse) {
  $modal.find(".invalid-feedback").remove();
  $modal.find(".alert").each(function () {
    if ($(this).attr("id") !== "SplashModalAlertBanner") {
      $(this).remove();
    }
  });
  $modal.find(".form-control").removeClass("is-invalid");
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
        displayFormErrors($modal, key, errorMessage);
        break;
      default:
        // Error for a field that doesn't exist
        console.log("No op.");
    }
  }
}

export function displayFormErrors($modal, key, errorMessage) {
  $('<div class="invalid-feedback"><span>' + errorMessage + "</span></div>")
    .insertAfter($modal.find("#" + key))
    .show();
  $modal.find("#" + key).addClass("is-invalid");
}
