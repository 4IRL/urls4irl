import type { Schema, SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $, getInputValue } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
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

type UpdateUrlTitleRequest = Schema<"UpdateURLTitleRequest">;
type UpdateUrlTitleResponse = SuccessResponse<"updateUrlTitle">;
type UpdateUrlTitleError = Schema<"ErrorResponse_URLErrorCodes">;

const UPDATE_URL_TITLE_FIELD_NAMES = ["urlTitle"] as const;

type UpdateUrlTitleFieldName = (typeof UPDATE_URL_TITLE_FIELD_NAMES)[number];

function isUpdateUrlTitleFieldName(
  key: string,
): key is UpdateUrlTitleFieldName {
  return (UPDATE_URL_TITLE_FIELD_NAMES as readonly string[]).includes(key);
}

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

  const updatedURLTitle = getInputValue(urlTitleInput);

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
  const timeoutID: number = setTimeoutAndShowURLCardLoadingIcon(urlCard);
  try {
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
        if ("URL" in response && "urlTitle" in response.URL)
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
  if (is429Handled(xhr)) return;

  if (!("responseJSON" in xhr)) {
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
      const hasErrors = !!responseJSON.errors;
      if (hasErrors) {
        updateURLTitleFailErrors(
          responseJSON.errors as Partial<
            Record<UpdateUrlTitleFieldName, string[]>
          >,
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
  errors: Partial<Record<UpdateUrlTitleFieldName, string[]>>,
  urlCard: JQuery,
): void {
  for (const errorFieldName in errors) {
    if (isUpdateUrlTitleFieldName(errorFieldName)) {
      const errorMessage = errors[errorFieldName]![0];
      displayUpdateURLTitleErrors(errorFieldName, errorMessage, urlCard);
      return;
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
  urlCard.find(".urlTitleUpdate").removeClass("invalid-field");
  urlCard.find(".urlTitleUpdate-error").removeClass("visible");
}
