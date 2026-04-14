import type { components, operations } from "../../../types/api.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { KEYS, SHOW_LOADING_ICON_AFTER_MS } from "../../../lib/constants.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { isEmptyString } from "./utils.js";
import { isValidURL } from "../validation.js";
import { getNumOfVisibleURLs, getNumOfURLs } from "../utils.js";
import {
  createURLBlock,
  newURLInputRemoveEventListeners,
  newURLInputAddEventListeners,
} from "./cards.js";
import { selectURLCard } from "./selection.js";
import { updateColorOfFollowingURLCardsAfterURLCreated } from "./utils.js";
import { isURLCurrentlyVisibleInURLDeck } from "./filtering.js";
import { isATagSelected } from "../../tags/utils.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";
import { getState, setState } from "../../../store/app-store.js";

type CreateUrlRequest = components["schemas"]["CreateURLRequest"];
type CreateUrlResponse =
  operations["createUrl"]["responses"][200]["content"]["application/json"];
type CreateUrlError = components["schemas"]["ErrorResponse_URLErrorCodes"];

const CREATE_URL_FIELD_NAMES = ["urlString", "urlTitle"] as const;

type CreateUrlFieldName = (typeof CREATE_URL_FIELD_NAMES)[number];

function isCreateUrlFieldName(key: string): key is CreateUrlFieldName {
  return (CREATE_URL_FIELD_NAMES as readonly string[]).includes(key);
}

export function bindCreateURLFocusEventListeners(
  inputElem: JQuery,
  createURLInput: JQuery,
  createURLTitleInput: JQuery,
  utubID: number,
): void {
  $(inputElem).on("keydown.createURL", function (event: JQuery.TriggeredEvent) {
    if ((event.originalEvent as KeyboardEvent).repeat) return;
    switch (event.key) {
      case KEYS.ENTER:
        // Handle enter key pressed
        createURL(createURLTitleInput, createURLInput, utubID);
        break;
      case KEYS.ESCAPE:
        // Handle escape key pressed
        createURLHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

export function unbindCreateURLFocusEventListeners(inputElem: JQuery): void {
  $(inputElem).off(".createURL");
}

// Clear new URL Form
export function resetNewURLForm(): void {
  $("#urlTitleCreate").val("");
  $("#urlStringCreate").val("");
  $("#createURLWrap").hideClass();
  newURLInputRemoveEventListeners();
  $("#urlBtnCreate").showClassNormal();
}
// Displays new URL input prompt
export function createURLHideInput(): void {
  resetNewURLForm();
  if (!getNumOfURLs()) {
    $("#NoURLsSubheader").showClassNormal();
    $("#urlBtnDeckCreateWrap").showClassFlex();
  }
}

// Hides new URL input prompt
export function createURLShowInput(utubID: number): void {
  if (!getNumOfURLs()) {
    $("#NoURLsSubheader").hideClass();
    $("#urlBtnDeckCreateWrap").hideClass();
  }
  const createURLInputForm = $("#createURLWrap");
  createURLInputForm.showClassFlex();
  newURLInputAddEventListeners(createURLInputForm, utubID);
  $("#urlTitleCreate").trigger("focus");
  $("#urlBtnCreate").hideClass();
  $("#urlBtnDeckCreateWrap").hideClass();
}

// Prepares post request inputs for addition of a new URL
function createURLSetup(
  createURLTitleInput: JQuery,
  createURLInput: JQuery,
  utubID: number,
): [string, CreateUrlRequest] {
  // Assemble post request route
  const postURL = APP_CONFIG.routes.createURL(utubID);

  // Assemble submission data
  const urlTitle = createURLTitleInput.val() as string;
  const urlString = createURLInput.val() as string;
  const data: CreateUrlRequest = {
    urlString,
    urlTitle,
  };

  return [postURL, data];
}

// Handles addition of new URL after user submission
export function createURL(
  createURLTitleInput: JQuery,
  createURLInput: JQuery,
  utubID: number,
): void {
  // Extract data to submit in POST request
  const [postURL, data] = createURLSetup(
    createURLTitleInput,
    createURLInput,
    utubID,
  );

  if (!isEmptyString(data.urlString) && !isValidURL(data.urlString)) {
    createURLShowFormErrors({
      urlString: [APP_CONFIG.strings.INVALID_URL],
    });
    return;
  }

  // Show loading icon when creating a URL
  const timeoutId = setTimeout(function () {
    $("#urlCreateDualLoadingRing").addClass("dual-loading-ring");
  }, SHOW_LOADING_ICON_AFTER_MS);
  const request = ajaxCall("post", postURL, data, 35000);

  request.done(function (
    response: CreateUrlResponse,
    _: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status === 200) {
      createURLSuccess(response, utubID);
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    resetCreateURLFailErrors();
    createURLFail(xhr, utubID);
  });

  request.always(function () {
    // Icon is only shown after 25ms - if <25ms, the timeout and callback function are cleared
    clearTimeout(timeoutId);
    $("#urlCreateDualLoadingRing").removeClass("dual-loading-ring");
  });
}

// Displays changes related to a successful addition of a new URL
function createURLSuccess(response: CreateUrlResponse, utubID: number): void {
  resetNewURLForm();
  const url = response.URL;

  const newUrl: UtubUrlItem = {
    utubUrlID: url.utubUrlID,
    urlString: url.urlString,
    urlTitle: url.urlTitle,
    utubUrlTagIDs: [],
    canDelete: true,
  };

  setState({
    urls: [...getState().urls, newUrl],
  });

  // DP 09/17 need to implement ability to addTagtoURL interstitially before createURL is completed
  const currentNumOfURLs = getNumOfVisibleURLs();
  const newUrlCard = createURLBlock(
    newUrl,
    [], // Mimics an empty array of tags to match against
    utubID,
  ).addClass("even");

  $("#accessAllURLsBtn").showClassNormal();

  newUrlCard.insertAfter($("#createURLWrap"));

  if (currentNumOfURLs !== 0) {
    updateColorOfFollowingURLCardsAfterURLCreated();
  }

  // Only select the URL when no tags are selected
  // If a tag is selected, new URLs have no Tags associated, so they should be hidden after added
  if (isATagSelected()) {
    newUrlCard.attr({ filterable: false });
  } else {
    selectURLCard(newUrlCard);
  }
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function createURLFail(xhr: JQuery.jqXHR, utubID: number): void {
  if (is429Handled(xhr)) return;

  if (!xhr.hasOwnProperty("responseJSON")) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // Handle invalid CSRF token error response
      $("body").html(xhr.responseText);
      return;
    }
    displayCreateUrlFailErrors(
      "urlString",
      "Server timed out while validating URL. Try again later.",
    );
    return;
  }
  const responseJSON = xhr.responseJSON as CreateUrlError;
  const hasErrors = responseJSON.hasOwnProperty("errors");
  const hasMessage = responseJSON.hasOwnProperty("message");
  switch (xhr.status) {
    case 400:
      if (hasMessage) {
        if (hasErrors) {
          createURLShowFormErrors(
            responseJSON.errors as Partial<
              Record<CreateUrlFieldName, string[]>
            >,
          );
        } else {
          displayCreateUrlFailErrors(
            "urlString",
            responseJSON.message as string,
          );
        }
      }
      break;
    case 409: {
      // Indicates duplicate URL error
      // If duplicate URL is not currently visible, indicates another user has added this URL
      // or updated another card to the new URL
      // Reload UTub and add/modify differences
      const duplicateUrlString = (
        responseJSON as CreateUrlError & { urlString?: string }
      ).urlString;
      if (
        duplicateUrlString !== undefined &&
        !isURLCurrentlyVisibleInURLDeck(duplicateUrlString)
      ) {
        updateUTubOnFindingStaleData(utubID);
      }
      displayCreateUrlFailErrors("urlString", responseJSON.message as string);
      break;
    }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function createURLShowFormErrors(
  errors: Partial<Record<CreateUrlFieldName, string[]>>,
): void {
  for (const key in errors) {
    if (isCreateUrlFieldName(key)) {
      const errorMessage = errors[key]![0];
      displayCreateUrlFailErrors(key, errorMessage);
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayCreateUrlFailErrors(key: string, errorMessage: string): void {
  $("#" + key + "Create-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Create").addClass("invalid-field");
}

export function resetCreateURLFailErrors(): void {
  const newUrlFields = ["urlString", "urlTitle"];
  newUrlFields.forEach((fieldName) => {
    $("#" + fieldName + "Create").removeClass("invalid-field");
    $("#" + fieldName + "Create-error").removeClass("visible");
  });
}
