import "./lib/security-check.js";
import { $, bootstrap } from "./lib/globals.js";
import { setupCSRF } from "./lib/csrf.js";
import { registerJQueryPlugins } from "./lib/jquery-plugins.js";
import { showNewPageOnAJAXHTMLResponse } from "./lib/page-utils.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { initNavbar, NAVBAR_TOGGLER } from "./splash/navbar.js";
import {
  initSplash,
  loginModalOpener,
  loginModalOpenerFromModal,
  registerModalOpener,
  showSplashModalAlertBanner,
  hideSplashModalAlertBanner,
  handleImproperFormErrors,
  handleUserHasAccountNotEmailValidated,
  emailValidationModalOpener,
  disableInputFields,
  displayFormErrors,
} from "./splash/init.js";
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
    // Show the modal
    bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    // Initialize form handlers
    initResetPasswordForm();
  }
}

/**
 * Initialize email validation form if the modal is present on page load
 * This happens when user clicks an expired email validation link
 */
function initEmailValidationIfPresent() {
  const modalForm = $("#ModalForm[data-modal-type='email-validation']");
  if (modalForm.length) {
    // Show the modal
    bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    // Initialize form handlers (false = don't send initial email for expired token page)
    initEmailValidationForm(false);
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
