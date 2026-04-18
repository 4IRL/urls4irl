import "bootstrap/dist/css/bootstrap.min.css";
import "font-awesome/css/font-awesome.min.css";
import "./styles/base.css";
import "./styles/splash.css";
import "./lib/security-check.js";
import { $, bootstrap } from "./lib/globals.js";
import { setupCSRF } from "./lib/csrf.js";
import { registerJQueryPlugins } from "./lib/jquery-plugins.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { initNavbar } from "./splash/navbar.js";
import { initSplash, createLogoutOnExit } from "./splash/init.js";
import { initResetPasswordForm } from "./splash/reset-password-form.js";
import {
  initEmailValidationForm,
  SKIP_INITIAL_EMAIL,
} from "./splash/email-validation-form.js";

// Register jQuery plugins globally
registerJQueryPlugins();

// Setup CSRF for AJAX requests
setupCSRF();

// Initialize cookie banner
initCookieBanner();

function initResetPasswordIfPresent(): void {
  const modalForm = $("#ModalForm[data-modal-type='reset-password']");
  if (modalForm.length) {
    bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    // initResetPasswordForm needs the jQuery wrapper for DOM event binding
    initResetPasswordForm($("#SplashModal"));
  }
}

function initEmailValidationIfPresent(): void {
  const modalForm = $("#ModalForm[data-modal-context='expired-token']");
  if (modalForm.length) {
    bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    initEmailValidationForm($("#SplashModal"), SKIP_INITIAL_EMAIL);
    const logoutOnExit = createLogoutOnExit();
    $("#SplashModal").one("hide.bs.modal", logoutOnExit);
  }
}

// Initialize on document ready
$(document).ready(function () {
  initSplash();
  initNavbar();

  // Check if reset password modal is present and initialize it
  initResetPasswordIfPresent();

  // Check if email validation modal is present and initialize it
  initEmailValidationIfPresent();
});
