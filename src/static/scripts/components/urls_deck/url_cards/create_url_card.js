"use strict";

function bindCreateURLFocusEventListeners(createURLTitleInput, createURLInput) {
  $(document).on("keyup.createURL", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        createURL(createURLTitleInput, createURLInput);
        break;
      case 27:
        // Handle escape key pressed
        createURLHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function unbindCreateURLFocusEventListeners() {
  $(document).off(".createURL");
}

// Clear new URL Form
function resetNewURLForm() {
  $("#urlTitleCreate").val(null);
  $("#urlStringCreate").val(null);
  hideIfShown($("#createURLWrap"));
  $("#createURLWrap").hide();
  newURLInputRemoveEventListeners();
  showIfHidden($("#urlBtnCreate"));
}
// Displays new URL input prompt
function createURLHideInput() {
  resetNewURLForm();
  if (!getNumOfURLs()) {
    $("#NoURLsSubheader").show();
    $("#urlBtnDeckCreateWrap").show();
  }
}

// Hides new URL input prompt
function createURLShowInput() {
  if (!getNumOfURLs()) {
    $("#NoURLsSubheader").hide();
    $("#urlBtnDeckCreateWrap").hide();
  }
  const createURLInputForm = $("#createURLWrap");
  showIfHidden(createURLInputForm);
  newURLInputAddEventListeners(createURLInputForm);
  $("#urlTitleCreate").trigger("focus");
  hideIfShown($("#urlBtnCreate"));
  hideIfShown($("#urlBtnDeckCreateWrap"));
}

// Prepares post request inputs for addition of a new URL
function createURLSetup(createURLTitleInput, createURLInput, utubID) {
  // Assemble post request route
  const postURL = routes.createURL(utubID);

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
function createURL(createURLTitleInput, createURLInput) {
  const utubID = getActiveUTubID();
  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = createURLSetup(createURLTitleInput, createURLInput, utubID);

  // Show loading icon when creating a URL
  const timeoutId = setTimeout(function () {
    $("#urlCreateDualLoadingRing").addClass("dual-loading-ring");
  }, SHOW_LOADING_ICON_AFTER_MS);
  const request = ajaxCall("post", postURL, data, 35000);

  request.done(function (response, _, xhr) {
    if (xhr.status === 200) {
      createURLSuccess(response);
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
function createURLSuccess(response) {
  resetNewURLForm();
  const url = response.URL;
  url.utubUrlTagIDs = [];
  url.canDelete = true;

  // DP 09/17 need to implement ability to addTagtoURL interstitially before createURL is completed
  const currentNumOfURLs = getNumOfVisibleURLs();
  const newUrlCard = createURLBlock(
    url,
    [], // Mimics an empty array of tags to match against
  ).addClass("even");

  showIfHidden($("#accessAllURLsBtn"));

  newUrlCard.insertAfter($("#createURLWrap"));
  if (currentNumOfURLs === 0) return;
  updateColorOfFollowingURLCardsAfterURLCreated();
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function createURLFail(xhr, utubID) {
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
      window.location.assign(routes.errorPage);
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

function resetCreateURLFailErrors() {
  const newUrlFields = ["urlString", "urlTitle"];
  newUrlFields.forEach((fieldName) => {
    $("#" + fieldName + "Create").removeClass("invalid-field");
    $("#" + fieldName + "Create-error").removeClass("visible");
  });
}
