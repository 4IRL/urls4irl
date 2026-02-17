import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { KEYS, SHOW_LOADING_ICON_AFTER_MS } from "../../../lib/constants.js";
import { ajaxCall } from "../../../lib/ajax.js";
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

export function bindCreateURLFocusEventListeners(
  inputElem,
  createURLInput,
  createURLTitleInput,
  utubID,
) {
  $(inputElem).on("keydown.createURL", function (e) {
    if (e.originalEvent.repeat) return;
    switch (e.key) {
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

export function unbindCreateURLFocusEventListeners(inputElem) {
  $(inputElem).off(".createURL");
}

// Clear new URL Form
export function resetNewURLForm() {
  $("#urlTitleCreate").val(null);
  $("#urlStringCreate").val(null);
  $("#createURLWrap").hideClass();
  newURLInputRemoveEventListeners();
  $("#urlBtnCreate").showClassNormal();
}
// Displays new URL input prompt
export function createURLHideInput() {
  resetNewURLForm();
  if (!getNumOfURLs()) {
    $("#NoURLsSubheader").showClassNormal();
    $("#urlBtnDeckCreateWrap").showClassFlex();
  }
}

// Hides new URL input prompt
export function createURLShowInput(utubID) {
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
function createURLSetup(createURLTitleInput, createURLInput, utubID) {
  // Assemble post request route
  const postURL = APP_CONFIG.routes.createURL(utubID);

  // Assemble submission data
  const newURLTitle = createURLTitleInput.val();
  const newURL = createURLInput.val();
  const data = {
    urlString: newURL,
    urlTitle: newURLTitle,
  };

  return [postURL, data];
}

// Handles addition of new URL after user submission
export function createURL(createURLTitleInput, createURLInput, utubID) {
  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = createURLSetup(createURLTitleInput, createURLInput, utubID);

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

  request.done(function (response, _, xhr) {
    if (xhr.status === 200) {
      createURLSuccess(response, utubID);
    }
  });

  request.fail(function (xhr, _, textStatus) {
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
function createURLSuccess(response, utubID) {
  resetNewURLForm();
  const url = response.URL;
  url.utubUrlTagIDs = [];
  url.canDelete = true;

  // DP 09/17 need to implement ability to addTagtoURL interstitially before createURL is completed
  const currentNumOfURLs = getNumOfVisibleURLs();
  const newUrlCard = createURLBlock(
    url,
    [], // Mimics an empty array of tags to match against
    utubID,
  ).addClass("even");

  $("#accessAllURLsBtn").showClassNormal();

  newUrlCard.insertAfter($("#createURLWrap"));

  currentNumOfURLs === 0
    ? null
    : updateColorOfFollowingURLCardsAfterURLCreated();

  // Only select the URL when no tags are selected
  // If a tag is selected, new URLs have no Tags associated, so they should be hidden after added
  isATagSelected()
    ? newUrlCard.attr({ filterable: false })
    : selectURLCard(newUrlCard);
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function createURLFail(xhr, utubID) {
  if (xhr._429Handled) return;

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
  const responseJSON = xhr.responseJSON;
  const hasErrors = responseJSON.hasOwnProperty("errors");
  const hasMessage = responseJSON.hasOwnProperty("message");
  switch (xhr.status) {
    case 400:
      if (responseJSON !== undefined && hasMessage) {
        hasErrors
          ? createURLShowFormErrors(responseJSON.errors)
          : displayCreateUrlFailErrors("urlString", responseJSON.message);
      }
      break;
    case 409:
      // Indicates duplicate URL error
      // If duplicate URL is not currently visible, indicates another user has added this URL
      // or updated another card to the new URL
      // Reload UTub and add/modify differences
      if (responseJSON.hasOwnProperty("urlString")) {
        if (!isURLCurrentlyVisibleInURLDeck(responseJSON.urlString)) {
          updateUTubOnFindingStaleData(utubID);
        }
      }
      displayCreateUrlFailErrors("urlString", responseJSON.message);
      break;
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function createURLShowFormErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "urlString":
      case "urlTitle":
        let errorMessage = errors[key][0];
        displayCreateUrlFailErrors(key, errorMessage);
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayCreateUrlFailErrors(key, errorMessage) {
  $("#" + key + "Create-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Create").addClass("invalid-field");
}

export function resetCreateURLFailErrors() {
  const newUrlFields = ["urlString", "urlTitle"];
  newUrlFields.forEach((fieldName) => {
    $("#" + fieldName + "Create").removeClass("invalid-field");
    $("#" + fieldName + "Create-error").removeClass("visible");
  });
}
