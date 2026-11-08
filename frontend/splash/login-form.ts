import type { Schema, SuccessResponse } from "../types/api-helpers.d.ts";
import { $, bootstrap } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { emit } from "../lib/metrics-client.js";
import { clearOpenForm } from "../lib/modal-tracking.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import {
  showSplashModalAlertBanner,
  resetModalFormState,
  handleImproperFormErrors,
  switchModal,
} from "./init.js";
import { openConfirmEmailModal } from "./confirm-email-form.js";
import { getForwardableNextQuery } from "./next-param.js";
import { VALIDATION_FORM } from "../types/metrics-dim-values.js";
import { debug } from "../lib/debug.js";

const log = debug("splash:login");

type LoginRequest = Schema<"LoginRequest">;
type LoginSuccess = SuccessResponse<"login">;
type LoginError = Schema<"ErrorResponse_LoginErrorCodes">;
type LoginEmailNotValidatedError =
  Schema<"LoginEmailNotValidatedErrorResponse">;

/**
 * Initialize login form handlers
 * Must be called after login form HTML is loaded into the modal
 */
export function initLoginForm($modal: JQuery): void {
  $modal
    .find("#ToRegisterFromLogin")
    .offAndOn("click", () => switchModal($modal, "#RegisterModal"));

  $modal
    .find(".to-forgot-password")
    .offAndOn("click", () => switchModal($modal, "#ForgotPasswordModal"));

  $modal
    .find("#submit")
    .offAndOn("click", (event) => handleLogin(event, $modal));

  $modal.on("show.bs.modal", () => resetModalFormState($modal));

  log("initLoginForm bound");
}

function handleLogin(event: JQuery.TriggeredEvent, $modal: JQuery): void {
  event.preventDefault();
  emit({ event: UI_EVENTS.UI_LOGIN_SUBMIT });
  clearOpenForm();
  $modal.find("#submit").attr("disabled", "disabled").attr("aria-busy", "true");

  // Allow user to attach a query param `next` if browser URL currently includes it
  // This allows for User to be given a link to a UTubID but they haven't logged in recently
  let url: string = APP_CONFIG.routes.login;
  const forwardableQuery = getForwardableNextQuery(window.location.search);
  const nextQueryParam =
    forwardableQuery === null
      ? null
      : new URLSearchParams(forwardableQuery).get("next");
  if (forwardableQuery !== null) {
    url = `${url}?${forwardableQuery}`;
  }

  const username: string = String($modal.find("#username").val() ?? "");
  const password: string = String($modal.find("#password").val() ?? "");

  log("handleLogin submit", {
    hasNextParam: nextQueryParam !== null,
    usernameLength: username.length,
    passwordLength: password.length,
  });

  const payload: LoginRequest = { username, password };
  const loginRequest: JQuery.jqXHR = $.ajax({
    url: url,
    type: "POST",
    data: JSON.stringify(payload),
    contentType: "application/json",
  });

  loginRequest.done((response, textStatus, xhr) =>
    handleLoginSuccess(response, textStatus, xhr),
  );
  loginRequest.fail((xhr, textStatus, error) =>
    handleLoginFailure(xhr, textStatus, error, $modal),
  );
}

function handleLoginSuccess(
  response: LoginSuccess,
  _: string,
  xhr: JQuery.jqXHR,
): void {
  if (xhr.status === 200) {
    bootstrap.Modal.getOrCreateInstance("#LoginModal").hide();
    // Use redirectUrl from JSON response
    const redirectUrl = response.redirectUrl || APP_CONFIG.routes.home;
    log("login success, redirecting", {
      redirectUrl,
      usedFallback: !response.redirectUrl,
    });
    window.location.replace(redirectUrl);
  }
}

function handleLoginFailure(
  xhr: JQuery.jqXHR,
  _: string,
  error: string,
  $modal: JQuery,
): void {
  if (!("responseJSON" in xhr)) {
    log("login failure: non-JSON response", {
      status: xhr.status,
      contentType: xhr.getResponseHeader("Content-Type"),
    });
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

  if (xhr.status === 403 && "errorCode" in xhr.responseJSON) {
    // Account suspended: surface the server's message directly — the user
    // supplied correct credentials but the account is administratively blocked.
    const errorJson = xhr.responseJSON as LoginError;
    showSplashModalAlertBanner($modal, errorJson.message, "danger");
    $modal.find("#submit").removeAttr("disabled").removeAttr("aria-busy");
    return;
  }

  if (
    (xhr.status === 400 || xhr.status === 401) &&
    "errorCode" in xhr.responseJSON
  ) {
    const errorJson = xhr.responseJSON as LoginError;
    log("login failure: JSON error", {
      status: xhr.status,
      errorCode: errorJson.errorCode,
    });
    emit({ event: UI_EVENTS.UI_VALIDATION_ERROR, form: VALIDATION_FORM.LOGIN });
    switch (errorJson.errorCode) {
      case 1: {
        // Correct password, email not yet confirmed: no session was created.
        // Hand the signed resend token to the Confirm modal; login stays usable.
        const notValidatedJson: LoginEmailNotValidatedError = xhr.responseJSON;
        openConfirmEmailModal({
          resendToken: notValidatedJson.resendToken ?? "",
          fromModal: $modal,
        });
        $modal.find("#submit").removeAttr("disabled").removeAttr("aria-busy");
        break;
      }
      case 2: {
        // errorCode 2 covers two shapes: a Pydantic schema-validation failure
        // (empty/malformed fields) carries a populated `errors` dict and has
        // zero enumeration risk — surface the field-level guidance. The opaque
        // credential-failure path carries no `errors` key — keep it generic so
        // account existence never leaks.
        if ("errors" in errorJson && errorJson.errors) {
          handleImproperFormErrors($modal, errorJson);
        } else {
          showSplashModalAlertBanner($modal, errorJson.message, "danger");
        }
        $modal.find("#submit").removeAttr("disabled").removeAttr("aria-busy");
        break;
      }
    }
  } else {
    log("login failure: unhandled JSON shape, showing generic banner", {
      status: xhr.status,
    });
    showSplashModalAlertBanner(
      $modal,
      "Unable to process request...",
      "danger",
    );
    $modal.find("#submit").removeAttr("disabled").removeAttr("aria-busy");
  }
}
