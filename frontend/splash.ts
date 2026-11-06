import "bootstrap/dist/css/bootstrap.min.css";
import "font-awesome/css/font-awesome.min.css";
import "./styles/base.css";
import "./styles/splash.css";
import "./lib/security-check.js";
import { $, bootstrap } from "./lib/globals.js";
import { setupCSRF } from "./lib/csrf.js";
import { registerJQueryPlugins } from "./lib/jquery-plugins.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { initMetricsClient } from "./lib/metrics-client.js";
import { initNavbar } from "./splash/navbar.js";
import { initSplash } from "./splash/init.js";
import { initResetPasswordForm } from "./splash/reset-password-form.js";
import { initConfirmLinkForm } from "./splash/confirm-link-form.js";
import { announce, initConfirmEmailForm } from "./splash/confirm-email-form.js";

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

// The expired-link page renders a static #ConfirmEmailModal shell (no
// #LoginModal), so initSplash does not bind it and it is bound exactly once here.
export function initExpiredConfirmEmailIfPresent(): void {
  const $shell = $("#ConfirmEmailModal[data-resend-token]");
  if (!$shell.length) return;

  $shell.data("resendToken", String($shell.data("resendToken") ?? ""));
  $shell.data("cooldownKey", "expired");
  initConfirmEmailForm($shell, { mode: "expired" });

  bootstrap.Modal.getOrCreateInstance($shell[0]).show();
  document.getElementById("ConfirmEmailModalLabel")?.focus();

  // The pre-filled banner is the visual cue; the status node announces it.
  announce({
    $modal: $shell,
    text: $shell.find("#SplashModalAlertBanner").text().trim(),
    isError: false,
  });
}

export function initOAuthRejectIfPresent(): void {
  const modalForm = $("#ModalForm[data-modal-context='oauth-reject']");
  if (modalForm.length) {
    bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
  }
}

function initConfirmLinkIfPresent(): void {
  const modalForm = $("#ModalForm[data-modal-type='confirm-link']");
  if (modalForm.length) {
    bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    initConfirmLinkForm($("#SplashModal"));
  }
}

// Initialize on document ready
$(document).ready(function () {
  initMetricsClient();
  initSplash();
  initNavbar();

  // Check if reset password modal is present and initialize it
  initResetPasswordIfPresent();

  // Check if the expired-link confirm-email shell is present and initialize it
  initExpiredConfirmEmailIfPresent();

  // Check if OAuth reject modal is present and initialize it
  initOAuthRejectIfPresent();

  // Check if confirm-link modal is present and initialize it
  initConfirmLinkIfPresent();
});
