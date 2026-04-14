import type { components, operations } from "../../../types/api.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $, bootstrap } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall } from "../../../lib/ajax.js";
import type { RateLimitedXHR } from "../../../lib/ajax.js";
import {
  enableTabbableChildElements,
  disableTabbableChildElements,
} from "../../../lib/jquery-plugins.js";
import { isEmptyString } from "./utils.js";
import { isValidURL } from "../validation.js";
import { getUpdatedURL, handleRejectFromGetURL } from "./get.js";
import {
  setTimeoutAndShowURLCardLoadingIcon,
  clearTimeoutIDAndHideLoadingIcon,
} from "./loading.js";
import { accessLink } from "./access.js";
import { copyURLString } from "./copy.js";
import {
  disableClickOnSelectedURLCardToHide,
  enableClickOnSelectedURLCardToHide,
} from "./selection.js";
import { isMobile } from "../../mobile.js";
import { highlightInput } from "../../btns-forms.js";
import {
  disableTagRemovalInURLCard,
  enableTagRemovalInURLCard,
} from "../tags/tags.js";
import { createEditURLIcon } from "./options/edit-string-btn.js";
import { isURLCurrentlyVisibleInURLDeck } from "./filtering.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";
import { getState, setState } from "../../../store/app-store.js";

type UpdateUrlStringRequest = components["schemas"]["UpdateURLStringRequest"];
type UpdateUrlStringResponse =
  operations["updateUrl"]["responses"][200]["content"]["application/json"];
type UpdateUrlStringError =
  components["schemas"]["ErrorResponse_URLErrorCodes"];

// Shows update URL inputs
export function showUpdateURLStringForm(
  urlCard: JQuery,
  urlStringBtnUpdate: JQuery,
): void {
  urlCard.find(".urlString").hideClass();
  const updateURLStringWrap = urlCard.find(".updateUrlStringWrap");
  enableTabbableChildElements(updateURLStringWrap);
  updateURLStringWrap.showClassFlex();

  // Handle case where iOS needs a direct focus not in a timeout, even with animation
  if (isMobile()) {
    updateURLStringWrap.find("input").focus();
  }

  // Set timeout in case user pressed enter to avoid propagation through to URL string update
  setTimeout(function () {
    highlightInput(updateURLStringWrap.find("input"));
  }, 100);

  // Disable URL Buttons as URL is being edited
  urlCard.find(".urlBtnAccess").hideClass();
  urlCard.find(".urlTagBtnCreate").hideClass();
  urlCard.find(".urlBtnDelete").hideClass();
  urlCard.find(".urlBtnCopy").hideClass();

  // Disable Go To URL Icon
  urlCard.find(".goToUrlIcon").removeClass("visible-flex").addClass("hidden");

  // Prevent hovering on tags from adding padding
  urlCard.find(".tagBadge").removeClass("tagBadgeHoverable");

  const tooltipElement = urlStringBtnUpdate.get(0);
  const tooltip = tooltipElement
    ? bootstrap.Tooltip.getInstance(tooltipElement)
    : null;
  if (tooltip) {
    tooltip.hide();
    tooltip.disable();
  }

  // Update URL Button text to exit editing
  urlStringBtnUpdate
    .removeClass("urlStringBtnUpdate fourty-p-width")
    .addClass("urlStringCancelBigBtnUpdate")
    .text("Cancel")
    .offAndOnExact("click", function () {
      hideAndResetUpdateURLStringForm(urlCard);
      if (tooltip) tooltip.enable();
    });

  disableTagRemovalInURLCard(urlCard);
  disableClickOnSelectedURLCardToHide(urlCard);
}

// Resets and hides the Update URL form upon cancellation or selection of another URL
export function hideAndResetUpdateURLStringForm(urlCard: JQuery): void {
  // Toggle input form and display of URL
  const updateURLStringWrap = urlCard.find(".updateUrlStringWrap");
  updateURLStringWrap.hideClass();
  disableTabbableChildElements(updateURLStringWrap);
  const urlStringElem = urlCard.find(".urlString");
  urlStringElem.showClassNormal();

  // Update the input with current value of url string element
  urlCard.find(".urlStringUpdate").val(urlStringElem.attr("href") as string);

  // Make the Update URL button now allow updating again
  const urlStringBtnUpdate = urlCard.find(".urlStringCancelBigBtnUpdate");
  urlStringBtnUpdate
    .removeClass("urlStringCancelBigBtnUpdate")
    .addClass("urlStringBtnUpdate")
    .offAndOnExact("click", function () {
      showUpdateURLStringForm(urlCard, urlStringBtnUpdate);
    })
    .text("")
    .append(createEditURLIcon());

  // For tablets or in case of resize, change some of the sizing
  urlStringBtnUpdate.addClass("fourty-p-width");

  // Enable URL Buttons
  urlCard.find(".urlBtnAccess").showClassFlex();
  urlCard.find(".urlTagBtnCreate").showClassFlex();
  urlCard.find(".urlBtnDelete").showClassFlex();
  urlCard.find(".urlBtnCopy").showClassFlex();

  // Enable Go To URL Icon
  const selected = urlCard.attr("urlSelected");
  if (typeof selected === "string" && selected.toLowerCase() === "true") {
    urlCard.find(".goToUrlIcon").removeClass("hidden").addClass("visible-flex");
  }

  // Enable hovering on tags for deletion
  urlCard.find(".tagBadge").addClass("tagBadgeHoverable");

  resetUpdateURLFailErrors(urlCard);
  enableTagRemovalInURLCard(urlCard);
  const selectedAgain = urlCard.attr("urlSelected");
  if (
    typeof selectedAgain === "string" &&
    selectedAgain.toLowerCase() === "true"
  ) {
    enableClickOnSelectedURLCardToHide(urlCard);
  }
}

// Prepares post request inputs for update of a URL
function updateURLSetup(
  urlStringUpdateInput: JQuery,
  utubID: number,
  utubUrlID: number,
): [string, UpdateUrlStringRequest] {
  const postURL = APP_CONFIG.routes.updateURL(utubID, utubUrlID);

  const updatedURL = (urlStringUpdateInput.val() as string).trim();

  const data: UpdateUrlStringRequest = { urlString: updatedURL };

  return [postURL, data];
}

// Handles update of an existing URL
export async function updateURL(
  urlStringUpdateInput: JQuery,
  urlCard: JQuery,
  utubID: number,
): Promise<void> {
  const utubUrlID = parseInt(urlCard.attr("utuburlid") as string);
  let timeoutID: number = 0;
  try {
    timeoutID = setTimeoutAndShowURLCardLoadingIcon(urlCard);
    await getUpdatedURL(utubID, utubUrlID, urlCard);

    // Extract data to submit in POST request
    const [patchURL, data] = updateURLSetup(
      urlStringUpdateInput,
      utubID,
      utubUrlID,
    );

    if (data.urlString === urlCard.find(".urlString").attr("href")) {
      hideAndResetUpdateURLStringForm(urlCard);
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    if (!isEmptyString(data.urlString) && !isValidURL(data.urlString)) {
      displayUpdateURLErrors(
        "urlString",
        APP_CONFIG.strings.INVALID_URL,
        urlCard,
      );
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    const request = ajaxCall("patch", patchURL, data, 35000);

    request.done(function (
      response: UpdateUrlStringResponse,
      _: JQuery.Ajax.SuccessTextStatus,
      xhr: JQuery.jqXHR,
    ) {
      if (xhr.status === 200) {
        updateURLSuccess(response, urlCard);
      }
    });

    request.fail(function (xhr: JQuery.jqXHR) {
      resetUpdateURLFailErrors(urlCard);
      updateURLFail(xhr, urlCard, utubID);
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
function updateURLSuccess(
  response: UpdateUrlStringResponse,
  urlCard: JQuery,
): void {
  // Extract response data
  const updatedURLString = response.URL.urlString;

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
  urlCard
    .find(".urlString")
    .attr({ href: updatedURLString })
    .text(updatedURLString);

  // Update URL options
  urlCard.find(".urlBtnAccess").offAndOnExact("click", function () {
    accessLink(updatedURLString);
  });

  urlCard.find(".goToUrlIcon").offAndOnExact("click", function () {
    accessLink(updatedURLString);
  });

  urlCard
    .find(".urlBtnCopy")
    .offAndOnExact("click", function (this: HTMLElement) {
      copyURLString(updatedURLString, this);
    });

  hideAndResetUpdateURLStringForm(urlCard);
}

// Displays appropriate prompts and options to user following a failed update of a URL
function updateURLFail(
  xhr: JQuery.jqXHR,
  urlCard: JQuery,
  utubID: number,
): void {
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
    displayUpdateURLErrors(
      "urlString",
      "Server timed out while validating URL. Try again later.",
      urlCard,
    );
    return;
  }
  const responseJSON = xhr.responseJSON as UpdateUrlStringError;
  const hasErrors = responseJSON.hasOwnProperty("errors");
  const hasMessage = responseJSON.hasOwnProperty("message");
  switch (xhr.status) {
    case 400:
      if (hasErrors) {
        updateURLFailErrors(
          responseJSON.errors as Partial<Record<"urlString", string[]>>,
          urlCard,
        );
        break;
      }
      if (hasMessage) {
        displayUpdateURLErrors(
          "urlString",
          responseJSON.message as string,
          urlCard,
        );
        break;
      }
    case 409: {
      // Indicates duplicate URL error
      // If duplicate URL is not currently visible, indicates another user has added this URL
      // or updated another card to the new URL
      // Reload UTub and add/modify differences
      const duplicateUrlString = (
        responseJSON as UpdateUrlStringError & { urlString?: string }
      ).urlString;
      if (
        duplicateUrlString !== undefined &&
        !isURLCurrentlyVisibleInURLDeck(duplicateUrlString)
      ) {
        updateUTubOnFindingStaleData(utubID);
      }
      displayUpdateURLErrors(
        "urlString",
        responseJSON.message as string,
        urlCard,
      );
      break;
    }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function updateURLFailErrors(
  errors: Partial<Record<"urlString", string[]>>,
  urlCard: JQuery,
): void {
  for (const errorFieldName in errors) {
    switch (errorFieldName) {
      case "urlString": {
        const errorMessage = errors[errorFieldName]![0];
        displayUpdateURLErrors(errorFieldName, errorMessage, urlCard);
        return;
      }
    }
  }
}

function displayUpdateURLErrors(
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

function resetUpdateURLFailErrors(urlCard: JQuery): void {
  const urlStringUpdateFields = ["urlString"];
  urlStringUpdateFields.forEach((fieldName) => {
    urlCard.find("." + fieldName + "Update").removeClass("invalid-field");
    urlCard.find("." + fieldName + "Update-error").removeClass("visible");
  });
}
