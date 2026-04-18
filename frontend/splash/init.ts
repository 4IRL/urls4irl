import type { Schema } from "../types/api-helpers.d.ts";
import { $, bootstrap } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { NAVBAR_TOGGLER } from "./navbar.js";
import { initLoginForm } from "./login-form.js";
import { initRegisterForm } from "./register-form.js";
import { initForgotPasswordForm } from "./forgot-password-form.js";
import {
  initEmailValidationForm,
  SEND_INITIAL_EMAIL,
} from "./email-validation-form.js";

type ErrorResponse = Schema<"ErrorResponse">;

const FORM_FIELD_NAMES = [
  "username",
  "password",
  "email",
  "confirmEmail",
  "confirmPassword",
  "newPassword",
  "confirmNewPassword",
] as const;

type FormFieldName = (typeof FORM_FIELD_NAMES)[number];

function isFormFieldName(key: string): key is FormFieldName {
  return (FORM_FIELD_NAMES as readonly string[]).includes(key);
}

/**
 * Initialize splash page
 * Sets up button handlers and rate limit error handling
 */
export function initSplash(): void {
  setToRegisterButton();
  setToLoginButton();
  initLoginForm($("#LoginModal"));
  initRegisterForm($("#RegisterModal"));
  initForgotPasswordForm($("#ForgotPasswordModal"));

  // Auto-show email validation modal for authenticated-but-not-validated users
  const splashConfig: HTMLElement | null =
    document.getElementById("splashConfig");
  if (splashConfig && splashConfig.dataset.showEmailValidation === "true") {
    bootstrap.Modal.getOrCreateInstance("#EmailValidationModal").show();
    initEmailValidationForm($("#EmailValidationModal"), SEND_INITIAL_EMAIL);
    const logoutOnExit = createLogoutOnExit();
    $("#EmailValidationModal").one("hide.bs.modal", logoutOnExit);
  }
}

function setToRegisterButton(): void {
  $(".to-register").offAndOn("click", function () {
    registerModalOpener();
    NAVBAR_TOGGLER.toggler.hide();
  });
}

function setToLoginButton(): void {
  $(".to-login").offAndOn("click", function () {
    loginModalOpener();
    NAVBAR_TOGGLER.toggler.hide();
  });
}

export function createLogoutOnExit(): () => void {
  return () => {
    $.get(APP_CONFIG.routes.logout).always(() => {
      window.location.replace("/");
    });
  };
}

export function switchModal($fromModal: JQuery, toSelector: string): void {
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

export function loginModalOpener(): void {
  bootstrap.Modal.getOrCreateInstance("#LoginModal").show();
}

export function registerModalOpener(): void {
  bootstrap.Modal.getOrCreateInstance("#RegisterModal").show();
}

export function emailValidationModalOpener($fromModal: JQuery): void {
  switchModal($fromModal, "#EmailValidationModal");
  initEmailValidationForm($("#EmailValidationModal"), SEND_INITIAL_EMAIL);
  const logoutOnExit = createLogoutOnExit();
  $("#EmailValidationModal").one("hide.bs.modal", logoutOnExit);
}

export function resetModalFormState($modal: JQuery): void {
  $modal.find(".invalid-feedback").remove();
  $modal.find(".form-control").removeClass("is-invalid");
  hideSplashModalAlertBanner($modal);
}

export function hideSplashModalAlertBanner($modal: JQuery): void {
  $modal
    .find("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-display")
    .removeClassStartingWith("alert-")
    .addClass("alert-banner-splash-modal-hide");
}

export function showSplashModalAlertBanner(
  $modal: JQuery,
  message: string,
  category: string,
): void {
  $modal
    .find("#SplashModalAlertBanner")
    .removeClass("d-none")
    .removeClass("alert-banner-splash-modal-hide")
    .removeClassStartingWith("alert-")
    .addClass("alert-" + category)
    .addClass("alert-banner-splash-modal-display")
    .text(message);
}

export function disableInputFields($modal: JQuery): void {
  $modal.find("input").attr("disabled", "disabled");
}

export function handleUserHasAccountNotEmailValidated(
  $sourceModal: JQuery,
  message: string,
): void {
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

export function handleImproperFormErrors(
  $modal: JQuery,
  errorResponse: ErrorResponse,
): void {
  $modal.find(".invalid-feedback").remove();
  $modal.find(".alert").each(function () {
    if ($(this).attr("id") !== "SplashModalAlertBanner") {
      $(this).remove();
    }
  });
  $modal.find(".form-control").removeClass("is-invalid");
  if (errorResponse.errors === null) {
    return;
  }
  for (const key in errorResponse.errors) {
    if (!isFormFieldName(key)) continue;
    const errorMessage: string = errorResponse.errors[key][0];
    if (!errorMessage) continue;
    displayFormErrors($modal, key, errorMessage);
  }
}

export function displayFormErrors(
  $modal: JQuery,
  key: string,
  errorMessage: string,
): void {
  $('<div class="invalid-feedback"><span>' + errorMessage + "</span></div>")
    .insertAfter($modal.find("#" + key))
    .show();
  $modal.find("#" + key).addClass("is-invalid");
}
