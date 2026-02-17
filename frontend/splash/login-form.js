import { $, bootstrap } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import {
  showSplashModalAlertBanner,
  handleImproperFormErrors,
  handleUserHasAccountNotEmailValidated,
  loginModalOpenerFromModal,
  registerModalOpener,
} from "./init.js";
import { initForgotPasswordForm } from "./forgot-password-form.js";

/**
 * Initialize login form handlers
 * Must be called after login form HTML is loaded into the modal
 */
export function initLoginForm() {
  $("#ToRegisterFromLogin").offAndOn("click", () => registerModalOpener());

  $(".to-forgot-password").offAndOn("click", () => openForgotPasswordModal());

  $("#submit").offAndOn("click", (event) => handleLogin(event));
}

function openForgotPasswordModal() {
  const modalOpener = $.get(APP_CONFIG.routes.forgotPassword);

  modalOpener.done((data, _, xhr) => {
    if (xhr.status === 200) {
      $("#SplashModal .modal-content").html(data);
      initForgotPasswordForm();
    }
  });

  modalOpener.fail((xhr) => {
    showSplashModalAlertBanner(
      "Unable to load forgot password form...",
      "danger",
    );
  });
}

function handleLogin(event) {
  event.preventDefault();

  // Allow user to attach a query param `next` if browser URL currently includes it
  // This allows for User to be given a link to a UTubID but they haven't logged in recently
  let url = APP_CONFIG.routes.login;
  const searchParams = new URLSearchParams(window.location.search);
  const nextQueryParam = searchParams.get("next");
  if (searchParams.size === 1 && nextQueryParam !== null) {
    url = `${url}?${searchParams.toString()}`;
  }

  const loginRequest = $.ajax({
    url: url,
    type: "POST",
    data: $("#ModalForm").serialize(),
  });

  loginRequest.done((response, textStatus, xhr) =>
    handleLoginSuccess(response, textStatus, xhr),
  );
  loginRequest.fail((xhr, textStatus, error) =>
    handleLoginFailure(xhr, textStatus, error),
  );
}

function handleLoginSuccess(response, _, xhr) {
  if (xhr.status === 200) {
    bootstrap.Modal.getOrCreateInstance("#SplashModal").hide();
    // Use redirect_url from JSON response
    const redirectUrl = response.redirect_url || APP_CONFIG.routes.home;
    window.location.replace(redirectUrl);
  }
}

function handleLoginFailure(xhr, _, error) {
  if (!xhr.hasOwnProperty("responseJSON")) {
    if (xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8") {
      switch (xhr.status) {
        case 403:
        case 429: {
          showNewPageOnAJAXHTMLResponse(xhr.responseText);
          return;
        }
      }
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  if (
    (xhr.status === 400 || xhr.status === 401) &&
    xhr.responseJSON.hasOwnProperty("errorCode")
  ) {
    switch (xhr.responseJSON.errorCode) {
      case 1: {
        // User found but email not yet validated
        handleUserHasAccountNotEmailValidated(xhr.responseJSON.message);
        $("input").attr("disabled", true);
        break;
      }
      case 2: {
        handleImproperFormErrors(xhr.responseJSON);
        break;
      }
    }
  } else {
    showSplashModalAlertBanner("Unable to process request...", "danger");
  }
}
