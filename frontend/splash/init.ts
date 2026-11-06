import type { Schema } from "../types/api-helpers.d.ts";
import { $, bootstrap } from "../lib/globals.js";
import { emit } from "../lib/metrics-client.js";
import { clearOpenForm, setOpenForm } from "../lib/modal-tracking.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import { NAVBAR_TOGGLER } from "./navbar.js";
import { initLoginForm } from "./login-form.js";
import { initRegisterForm } from "./register-form.js";
import { initRegisterConfirmationModal } from "./register-confirmation-form.js";
import { initConfirmEmailForm } from "./confirm-email-form.js";
import { initForgotPasswordForm } from "./forgot-password-form.js";
import { AUTH_MODAL_OPEN_FORM } from "../types/metrics-dim-values.js";
import { initScrollReveal } from "./scroll-reveal.js";
import { debug } from "../lib/debug.js";

const log = debug("splash");

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
  initScrollReveal();
  setToRegisterButton();
  setToLoginButton();
  clearOpenFormOnAuthModalHide($("#LoginModal"));
  clearOpenFormOnAuthModalHide($("#RegisterModal"));
  initLoginForm($("#LoginModal"));
  initRegisterForm($("#RegisterModal"));
  initRegisterConfirmationModal($("#RegisterConfirmationModal"));
  if ($("#LoginModal").length > 0) {
    initConfirmEmailForm($("#ConfirmEmailModal"), { mode: "inline" });
  }
  initForgotPasswordForm($("#ForgotPasswordModal"));
  log("initSplash invoked");
}

function setToRegisterButton(): void {
  $(".to-register").offAndOn("click", function () {
    registerModalOpener();
    NAVBAR_TOGGLER.toggler?.hide();
  });
}

function setToLoginButton(): void {
  $(".to-login").offAndOn("click", function () {
    loginModalOpener();
    NAVBAR_TOGGLER.toggler?.hide();
  });
}

// Submit and explicit cancel already call clearOpenForm(), but a Bootstrap
// X-button/backdrop dismiss (data-bs-dismiss) does not. Without this, a dismiss
// followed by page navigation leaves the open-form registry populated, so the
// pagehide handler emits a spurious UI_AUTH_CANCEL{trigger:navigation}. Clearing
// on hidden.bs.modal closes that false-positive. offAndOn (off-then-on) keeps the
// binding idempotent across repeated shows/hides and re-inits of initSplash.
export function clearOpenFormOnAuthModalHide($modal: JQuery): void {
  $modal.offAndOn("hidden.bs.modal", () => {
    clearOpenForm();
  });
}

function targetFromSelector(
  selector: string,
): "login" | "register" | "forgot_password" | null {
  if (selector === "#LoginModal") return "login";
  if (selector === "#RegisterModal") return "register";
  if (selector === "#ForgotPasswordModal") return "forgot_password";
  return null;
}

export function switchModal($fromModal: JQuery, toSelector: string): void {
  log("switchModal", {
    from: $fromModal.attr("id"),
    to: toSelector,
    fromInstanceExists: Boolean(bootstrap.Modal.getInstance($fromModal[0])),
  });
  const target = targetFromSelector(toSelector);
  if (target !== null) emit({ event: UI_EVENTS.UI_AUTH_FORM_SWITCH, target });
  if (target === "login" || target === "register") {
    setOpenForm(target);
  } else {
    clearOpenForm();
  }

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
  emit({
    event: UI_EVENTS.UI_AUTH_MODAL_OPEN,
    form: AUTH_MODAL_OPEN_FORM.LOGIN,
  });
  setOpenForm("login");
  bootstrap.Modal.getOrCreateInstance("#LoginModal").show();
}

export function registerModalOpener(): void {
  emit({
    event: UI_EVENTS.UI_AUTH_MODAL_OPEN,
    form: AUTH_MODAL_OPEN_FORM.REGISTER,
  });
  setOpenForm("register");
  bootstrap.Modal.getOrCreateInstance("#RegisterModal").show();
}

export function resetModalFormState($modal: JQuery): void {
  $modal.find(".invalid-feedback").remove();
  $modal.find(".form-control").removeClass("is-invalid");
  $modal.find("#submit").removeAttr("disabled").removeAttr("aria-busy");
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

export function handleImproperFormErrors(
  $modal: JQuery,
  errorResponse: ErrorResponse,
): void {
  log("handleImproperFormErrors", {
    modal: $modal.attr("id"),
    fieldsWithErrors: errorResponse.errors
      ? Object.keys(errorResponse.errors)
      : [],
    errorsNull: errorResponse.errors === null,
  });
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
    if (!isFormFieldName(key)) {
      log("server returned unknown form-field key", {
        modal: $modal.attr("id"),
        unknownKey: key,
      });
      continue;
    }
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
