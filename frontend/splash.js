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
import { initEmailValidationForm } from "./splash/email-validation-form.js";

// Register jQuery plugins globally
registerJQueryPlugins();

// Setup CSRF for AJAX requests
setupCSRF();

// Initialize cookie banner
initCookieBanner();

/**
 * Initialize reset password form if the modal is present on page load
 * This happens when user clicks a password reset link
 */
function initResetPasswordIfPresent() {
  const modalForm = $("#ModalForm[data-modal-type='reset-password']");
  if (modalForm.length) {
    bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    initResetPasswordForm($("#SplashModal"));
  }
}

/**
 * Initialize email validation form if the modal is present on page load
 * This happens when user clicks an expired email validation link
 */
function initEmailValidationIfPresent() {
  const modalForm = $("#ModalForm[data-modal-context='expired-token']");
  if (modalForm.length) {
    bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    initEmailValidationForm($("#SplashModal"), false);
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
