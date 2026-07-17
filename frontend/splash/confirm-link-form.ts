import type { Schema, SuccessResponse } from "../types/api-helpers.d.ts";
import { APP_CONFIG } from "../lib/config.js";
import { ajaxCall, is429Handled } from "../lib/ajax.js";
import { showNewPageOnAJAXHTMLResponse } from "../lib/page-utils.js";
import { showSplashModalAlertBanner } from "./init.js";

type ConfirmLinkRequest = Schema<"ConfirmLinkRequest">;
type ConfirmLinkSuccess = SuccessResponse<"oauthConfirmLink">;
type ConfirmLinkError = Schema<"ErrorResponse_OAuthLinkErrorCodes">;

const FORM_SELECTOR = "form[data-modal-type='confirm-link']";

/**
 * Initialize the confirm-link form handler.
 * Must be called after the confirm-link modal HTML is loaded into the modal.
 *
 * The password-less (OAuth-only) variant of this modal renders no `#password`
 * input and no submit button — only provider anchor links, which need no JS.
 * In that case this is a no-op: no submit handler is bound.
 */
export function initConfirmLinkForm($modal: JQuery): void {
  const $form = $modal.find(FORM_SELECTOR);
  if ($form.find("#password").length === 0) return;

  $form.offAndOn("submit", (event) =>
    handleConfirmLinkSubmit(event, $modal, $form),
  );
}

function handleConfirmLinkSubmit(
  event: JQuery.TriggeredEvent,
  $modal: JQuery,
  $form: JQuery,
): void {
  event.preventDefault();

  const payload: ConfirmLinkRequest = {
    password: String($form.find("#password").val() ?? ""),
  };

  const actionUrl = $form.attr("action") ?? "";
  const request = ajaxCall("post", actionUrl, payload);

  request.done(function (
    response: ConfirmLinkSuccess,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status !== 200) return;
    window.location.assign(response.redirectUrl);
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    if (is429Handled(xhr)) return;
    handleConfirmLinkFailure(xhr, $modal);
  });
}

function handleConfirmLinkFailure(xhr: JQuery.jqXHR, $modal: JQuery): void {
  if (!("responseJSON" in xhr)) {
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

  const errorJson = xhr.responseJSON as ConfirmLinkError;
  showSplashModalAlertBanner(
    $modal,
    errorJson.message || "Unable to process request...",
    "danger",
  );
}
