import type { components, operations } from "../../../types/api.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall } from "../../../lib/ajax.js";
import type { RateLimitedXHR } from "../../../lib/ajax.js";
import { getUpdatedURL, handleRejectFromGetURL } from "./get.js";
import {
  setTimeoutAndShowURLCardLoadingIcon,
  clearTimeoutIDAndHideLoadingIcon,
} from "./loading.js";
import {
  disableClickOnSelectedURLCardToHide,
  enableClickOnSelectedURLCardToHide,
} from "./selection.js";
import { getState, setState } from "../../../store/app-store.js";

type UpdateUrlTitleRequest = components["schemas"]["UpdateURLTitleRequest"];
type UpdateUrlTitleResponse =
  operations["updateUrlTitle"]["responses"][200]["content"]["application/json"];
type UpdateUrlTitleError = components["schemas"]["ErrorResponse_URLErrorCodes"];

// Shows the update URL title form
export function showUpdateURLTitleForm(
  urlTitleAndShowUpdateIconWrap: JQuery,
  urlCard: JQuery,
): void {
  urlTitleAndShowUpdateIconWrap.hideClass();
  const updateTitleForm = urlTitleAndShowUpdateIconWrap.siblings(
    ".updateUrlTitleWrap",
  );
  updateTitleForm.showClassFlex();
  updateTitleForm.find("input").trigger("focus");

  // Prevent hovering on tags from adding padding
  urlCard.find(".tagBadge").removeClass("tagBadgeHoverable");

  disableClickOnSelectedURLCardToHide(urlCard);
}

// Resets and hides the Update URL form upon cancellation or selection of another URL
export function hideAndResetUpdateURLTitleForm(urlCard: JQuery): void {
  urlCard.find(".updateUrlTitleWrap").hideClass();
  urlCard.find(".urlTitleAndUpdateIconWrap").showClassFlex();
  urlCard.find(".urlTitleUpdate").val(urlCard.find(".urlTitle").text());

  // Enable hovering on tags for deletion
  urlCard.find(".tagBadge").addClass("tagBadgeHoverable");

  resetUpdateURLTitleFailErrors(urlCard);
  const selected = urlCard.attr("urlSelected");
  if (typeof selected === "string" && selected.toLowerCase() === "true") {
    enableClickOnSelectedURLCardToHide(urlCard);
  }
}

// Prepares post request inputs for update of a URL
function updateURLTitleSetup(
  urlTitleInput: JQuery,
  utubID: number,
  utubUrlID: number,
): [string, UpdateUrlTitleRequest] {
  const patchURL = APP_CONFIG.routes.updateURLTitle(utubID, utubUrlID);

  const updatedURLTitle = urlTitleInput.val() as string;

  const data: UpdateUrlTitleRequest = { urlTitle: updatedURLTitle };

  return [patchURL, data];
}

// Handles update of an existing URL
export async function updateURLTitle(
  urlTitleInput: JQuery,
  urlCard: JQuery,
  utubID: number,
): Promise<void> {
  // Extract data to submit in POST request
  const utubUrlID = parseInt(urlCard.attr("utuburlid") as string);
  let timeoutID: number = 0;
  try {
    timeoutID = setTimeoutAndShowURLCardLoadingIcon(urlCard);
    await getUpdatedURL(utubID, utubUrlID, urlCard);

    if (urlTitleInput.val() === urlCard.find(".urlTitle").text()) {
      hideAndResetUpdateURLTitleForm(urlCard);
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    const [patchURL, data] = updateURLTitleSetup(
      urlTitleInput,
      utubID,
      utubUrlID,
    );

    const request = ajaxCall("patch", patchURL, data);

    // Handle response
    request.done(function (
      response: UpdateUrlTitleResponse,
      _: JQuery.Ajax.SuccessTextStatus,
      xhr: JQuery.jqXHR,
    ) {
      if (xhr.status === 200) {
        resetUpdateURLTitleFailErrors(urlCard);
        if (
          response.hasOwnProperty("URL") &&
          response.URL.hasOwnProperty("urlTitle")
        )
          updateURLTitleSuccess(response, urlCard);
      }
    });

    request.fail(function (xhr: JQuery.jqXHR) {
      updateURLTitleFail(xhr, urlCard);
    });

    request.always(function () {
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    });
  } catch (error) {
    clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    handleRejectFromGetURL(error as JQuery.jqXHR, urlCard, {
      showError: true,
      message: "Another user has deleted this URL",
    });
  }
}

// Displays changes related to a successful update of a URL
function updateURLTitleSuccess(
  response: UpdateUrlTitleResponse,
  urlCard: JQuery,
): void {
  // Extract response data
  const updatedURLTitle = response.URL.urlTitle;

  setState({
    urls: getState().urls.map((existingUrl: UtubUrlItem) =>
      existingUrl.utubUrlID === response.URL.utubUrlID
        ? {
            ...existingUrl,
            urlString: response.URL.urlString,
            urlTitle: response.URL.urlTitle,
            utubUrlTagIDs: response.URL.urlTags.map(
              (urlTag) => urlTag.utubTagID,
            ),
          }
        : existingUrl,
    ),
  });

  // Update URL body with latest published data
  urlCard.find(".urlTitle").text(updatedURLTitle);
  hideAndResetUpdateURLTitleForm(urlCard);
}

// Displays appropriate prompts and options to user following a failed update of a URL
function updateURLTitleFail(xhr: JQuery.jqXHR, urlCard: JQuery): void {
  if ((xhr as RateLimitedXHR)._429Handled) return;

  if (!xhr.hasOwnProperty("responseJSON")) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // Handle invalid CSRF token error response
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  switch (xhr.status) {
    case 400: {
      const responseJSON = xhr.responseJSON as UpdateUrlTitleError;
      const hasErrors = responseJSON.hasOwnProperty("errors");
      if (hasErrors) {
        updateURLTitleFailErrors(
          responseJSON.errors as Partial<Record<"urlTitle", string[]>>,
          urlCard,
        );
        break;
      }
    }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function updateURLTitleFailErrors(
  errors: Partial<Record<"urlTitle", string[]>>,
  urlCard: JQuery,
): void {
  for (const errorFieldName in errors) {
    switch (errorFieldName) {
      case "urlTitle": {
        const errorMessage = errors[errorFieldName]![0];
        displayUpdateURLTitleErrors(errorFieldName, errorMessage, urlCard);
        return;
      }
    }
  }
}

function displayUpdateURLTitleErrors(
  key: string,
  errorMessage: string,
  urlCard: JQuery,
): void {
  urlCard
    .find("." + key + "Update-error")
    .addClass("visible")
    .text(errorMessage);
  urlCard.find("." + key + "Update").addClass("invalid-field");
}

function resetUpdateURLTitleFailErrors(urlCard: JQuery): void {
  const urlTitleUpdateFields = ["urlTitle"];
  urlTitleUpdateFields.forEach((fieldName) => {
    urlCard.find("." + fieldName + "Update").removeClass("invalid-field");
    urlCard.find("." + fieldName + "Update-error").removeClass("visible");
  });
}
