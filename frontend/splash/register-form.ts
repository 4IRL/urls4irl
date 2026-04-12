import type { components, operations } from "../types/api.d.ts";
import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import {
  showSplashModalAlertBanner,
  resetModalFormState,
  handleImproperFormErrors,
  handleUserHasAccountNotEmailValidated,
  switchModal,
  emailValidationModalOpener,
} from "./init.js";

type RegisterRequest = components["schemas"]["RegisterRequest"];
type RegisterSuccess =
  operations["registerUser"]["responses"][201]["content"]["application/json"];
type RegisterError = components["schemas"]["ErrorResponse_RegisterErrorCodes"];

/**
 * Initialize register form handlers
 * Must be called after register form HTML is loaded into the modal
 */
export function initRegisterForm($modal: JQuery): void {
  $modal
    .find("#ToLoginFromRegister")
    .offAndOn("click", () => switchModal($modal, "#LoginModal"));

  $modal
    .find("#submit")
    .offAndOn("click", (event) => handleRegister(event, $modal));

  $modal.on("show.bs.modal", () => resetModalFormState($modal));
}

function handleRegister(event: JQuery.TriggeredEvent, $modal: JQuery): void {
  event.preventDefault();
  $modal.find("#submit").attr("disabled", "disabled");

  const username: string = String($modal.find("#username").val() ?? "");
  const email: string = String($modal.find("#email").val() ?? "");
  const confirmEmail: string = String($modal.find("#confirmEmail").val() ?? "");
  const password: string = String($modal.find("#password").val() ?? "");
  const confirmPassword: string = String(
    $modal.find("#confirmPassword").val() ?? "",
  );

  const payload: RegisterRequest = {
    username,
    email,
    confirmEmail,
    password,
    confirmPassword,
  };
  const registerRequest: JQuery.jqXHR = $.ajax({
    url: APP_CONFIG.routes.register,
    type: "POST",
    data: JSON.stringify(payload),
    contentType: "application/json",
  });

  registerRequest.done((response, textStatus, xhr) =>
    handleRegisterSuccess(response, textStatus, xhr, $modal),
  );
  registerRequest.fail((xhr, textStatus, error) =>
    handleRegisterFailure(xhr, textStatus, error, $modal),
  );
}

function handleRegisterSuccess(
  _: RegisterSuccess,
  __: string,
  xhr: JQuery.jqXHR,
  $modal: JQuery,
): void {
  if (xhr.status === 201) {
    emailValidationModalOpener($modal);
  }
}

function handleRegisterFailure(
  xhr: JQuery.jqXHR,
  _: string,
  __: string,
  $modal: JQuery,
): void {
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

  if (xhr.responseJSON.hasOwnProperty("errorCode")) {
    const errorJson = xhr.responseJSON as RegisterError;
    switch (xhr.status) {
      case 400: {
        handleImproperFormErrors($modal, errorJson);
        $modal.find("#submit").removeAttr("disabled");
        break;
      }
      case 401: {
        // User found but email not yet validated
        handleUserHasAccountNotEmailValidated($modal, errorJson.message);
        $modal.find("input").attr("disabled", "disabled");
        break;
      }
    }
  } else {
    showSplashModalAlertBanner(
      $modal,
      "Unable to process request...",
      "danger",
    );
  }
}
