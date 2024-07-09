// Time until loading icon is shown for URL validation after creation/updating, in ms
const SHOW_LOADING_ICON_AFTER_MS = 25;

/* Add URL */

// Displays new URL input prompt
function createURLHideInput(urlInputForm) {
  resetNewURLForm();
  if (!getNumOfURLs()) $("#NoURLsSubheader").show();
}

// Hides new URL input prompt
function createURLShowInput() {
  if (!getNumOfURLs()) $("#NoURLsSubheader").hide();
  const createURLInputForm = $("#createURLWrap");
  showIfHidden(createURLInputForm);
  highlightInput(createURLInputForm.find("#urlTitleCreate"));
  newURLInputAddEventListeners(createURLInputForm);
}

// Prepares post request inputs for addition of a new URL
function createURLSetup(createURLTitleInput, createURLInput) {
  // Assemble post request route
  const postURL = routes.createURL(getActiveUTubID());

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
  // Extract data to submit in POST request
  [postURL, data] = createURLSetup(createURLTitleInput, createURLInput);

  // A custom AJAX call, built to show a loading icon after a given number of MS
  let timeoutId;
  $.ajax({
    url: postURL,
    method: "POST",
    data: data,

    // Following overwrites the global ajaxSetup call, so needs to include CSRFToken again
    beforeSend: function (xhr, settings) {
      globalBeforeSend(xhr, settings);
      timeoutId = setTimeout(function () {
        $("#urlCreateDualLoadingRing").addClass("dual-loading-ring");
      }, SHOW_LOADING_ICON_AFTER_MS);
    },

    success: function (response, _, xhr) {
      if (xhr.status === 200) {
        createURLSuccess(response);
      }
    },

    error: function (xhr, _, errorThrown) {
      resetCreateUrlFailErrors();
      createURLFail(xhr);
    },

    complete: function () {
      // Icon is only shown after 25ms - if <25ms, the timeout and callback function are cleared
      clearTimeout(timeoutId);
      $("#urlCreateDualLoadingRing").removeClass("dual-loading-ring");
    },
  });
}

// Displays changes related to a successful addition of a new URL
function createURLSuccess(response) {
  resetNewURLForm();
  const url = response.URL;
  url.urlTagIDs = [];
  url.canDelete = true;

  // DP 09/17 need to implement ability to addTagtoURL interstitially before createURL is completed
  const newUrlCard = createURLBlock(
    url,
    [], // Mimics an empty array of tags to match against
  );

  newUrlCard.insertAfter($("#createURLWrap"));
  displayState1URLDeck();
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function createURLFail(xhr) {
  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      if (
        responseJSON !== undefined &&
        responseJSON.hasOwnProperty("message")
      ) {
        responseJSON.hasOwnProperty("errors")
          ? createURLShowFormErrors(responseJSON.errors)
          : displayCreateUrlFailErrors("urlString", responseJSON.message);
        highlightInput($("#urlStringCreate"));
      }
      break;
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
  // DP 09/17 could we maybe have a more descriptive reason for failure sent from backend to display to user?
  // Currently STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL is too generic. the # * comments are ideal
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

function resetCreateUrlFailErrors() {
  const newUrlFields = ["urlString", "urlTitle"];
  newUrlFields.forEach((fieldName) => {
    $("#" + fieldName + "Create").removeClass("invalid-field");
    $("#" + fieldName + "Create-error").removeClass("visible");
  });
}

/* Update URL */

// Shows update URL inputs
function showUpdateURLStringForm(urlCard, urlBtnUpdate) {
  hideIfShown(urlCard.find(".urlString"));
  const updateURLStringWrap = urlCard.find(".updateUrlStringWrap");
  showIfHidden(updateURLStringWrap);
  highlightInput(updateURLStringWrap.find("input"));

  // Disable URL Buttons as URL is being edited
  hideIfShown(urlCard.find(".urlBtnAccess"));
  hideIfShown(urlCard.find(".tagBtnCreate"));
  hideIfShown(urlCard.find(".urlBtnDelete"));

  // Disable Go To URL Icon
  urlCard.find(".goToUrlIcon").removeClass("visible-flex").addClass("hidden");

  // Update URL Button text to exit editing
  urlCard
    .find(".urlBtnUpdate")
    .removeClass("btn-light")
    .addClass("btn-warning")
    .text("Return")
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      hideAndResetUpdateURLStringForm(urlCard);
    });

  disableTagRemovalInURLCard(urlCard);
}

// Resets and hides the Update URL form upon cancellation or selection of another URL
function hideAndResetUpdateURLStringForm(urlCard) {
  // Toggle input form and display of URL
  hideIfShown(urlCard.find(".updateUrlStringWrap"));
  const urlStringElem = urlCard.find(".urlString");
  showIfHidden(urlStringElem);

  // Update the input with current value of url string element
  urlCard.find(".urlStringUpdate").val(urlStringElem.text());

  // Make the Update URL button now allow updating again
  const urlBtnUpdate = urlCard.find(".urlBtnUpdate");
  urlBtnUpdate
    .removeClass("btn-warning")
    .addClass("btn-light")
    .text("Edit URL")
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      showUpdateURLStringForm(urlCard, urlBtnUpdate);
    });

  // Enable URL Buttons
  showIfHidden(urlCard.find(".urlBtnAccess"));
  showIfHidden(urlCard.find(".tagBtnCreate"));
  showIfHidden(urlCard.find(".urlBtnDelete"));

  // Enable Go To URL Icon
  const selected = urlCard.attr("urlSelected");
  if (typeof selected === "string" && selected.toLowerCase() === "true") {
    urlCard.find(".goToUrlIcon").removeClass("hidden").addClass("visible-flex");
  }

  resetUpdateURLFailErrors(urlCard);
  enableTagRemovalInURLCard(urlCard);
}

// Prepares post request inputs for update of a URL
function updateURLSetup(urlStringUpdateInput) {
  const postURL = routes.updateURL(getActiveUTubID(), getSelectedURLID());

  const updatedURL = urlStringUpdateInput.val();

  const data = { urlString: updatedURL };

  return [postURL, data];
}

// Handles update of an existing URL
function updateURL(urlStringUpdateInput, urlCard) {
  if (urlStringUpdateInput.val() === urlCard.find(".urlString").text()) {
    hideAndResetUpdateURLStringForm(urlCard);
    return;
  }

  // Extract data to submit in POST request
  [patchURL, data] = updateURLSetup(urlStringUpdateInput);

  // A custom AJAX call, built to show a loading icon after a given number of MS
  let timeoutId;
  $.ajax({
    url: patchURL,
    method: "PATCH",
    data: data,

    // Following overwrites the global ajaxSetup call, so needs to include CSRFToken again
    beforeSend: function (xhr, settings) {
      globalBeforeSend(xhr, settings);
      timeoutId = setTimeout(function () {
        urlCard.find(".urlUpdateDualLoadingRing").addClass("dual-loading-ring");
      }, SHOW_LOADING_ICON_AFTER_MS);
    },

    success: function (response, _, xhr) {
      if (xhr.status === 200) {
        updateURLSuccess(response, urlCard);
      }
    },

    error: function (xhr, _, errorThrown) {
      resetUpdateURLFailErrors(urlCard);
      updateURLFail(xhr, urlCard);
    },

    complete: function () {
      // Icon is only shown after 25ms - if <25ms, the timeout and callback function are cleared
      clearTimeout(timeoutId);
      urlCard
        .find(".urlUpdateDualLoadingRing")
        .removeClass("dual-loading-ring");
    },
  });
}

// Displays changes related to a successful update of a URL
function updateURLSuccess(response, urlCard) {
  // Extract response data
  const updatedURLString = response.URL.urlString;

  // If update URL action, rebind the ability to select/deselect URL by clicking it
  //rebindSelectBehavior();

  // Update URL body with latest published data
  urlCard.find(".urlString").text(updatedURLString);

  // Update URL options
  urlCard
    .find(".urlBtnAccess")
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      accessLink(updatedURLString);
    });

  urlCard
    .find(".goToUrlIcon")
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      accessLink(updatedURLString);
    });

  hideAndResetUpdateURLStringForm(urlCard);
}

// Displays appropriate prompts and options to user following a failed update of a URL
function updateURLFail(xhr, urlCard) {
  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      const hasErrors = responseJSON.hasOwnProperty("errors");
      const hasMessage = responseJSON.hasOwnProperty("message");
      if (hasErrors) {
        updateURLFailShowErrors(responseJSON.errors, urlCard);
        break;
      }
      if (hasMessage) {
        displayUpdateURLErrors("urlString", responseJSON.message, urlCard);
        break;
      }
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

function updateURLFailShowErrors(errors, urlCard) {
  for (let key in errors) {
    switch (key) {
      case "urlString":
        let errorMessage = errors[key][0];
        displayUpdateURLErrors(key, errorMessage, urlCard);
        return;
    }
  }
}

function displayUpdateURLErrors(key, errorMessage, urlCard) {
  urlCard
    .find("." + key + "Update-error")
    .addClass("visible")
    .text(errorMessage);
  urlCard.find("." + key + "Update").addClass("invalid-field");
}

function resetUpdateURLFailErrors(urlCard) {
  const urlStringUpdateFields = ["urlString"];
  urlStringUpdateFields.forEach((fieldName) => {
    urlCard.find("." + fieldName + "Update").removeClass("invalid-field");
    urlCard.find("." + fieldName + "Update-error").removeClass("visible");
  });
}

/* Update URL Title */

// Shows the update URL title form
function showUpdateURLTitleForm(urlTitleAndShowUpdateIconWrap) {
  hideIfShown(urlTitleAndShowUpdateIconWrap);
  const updateTitleForm = urlTitleAndShowUpdateIconWrap.siblings(
    ".updateUrlTitleWrap",
  );
  showIfHidden(updateTitleForm);
  updateTitleForm.find("input").focus();
}

// Resets and hides the Update URL form upon cancellation or selection of another URL
function hideAndResetUpdateURLTitleForm(urlCard) {
  hideIfShown(urlCard.find(".updateUrlTitleWrap"));
  showIfHidden(urlCard.find(".urlTitleAndUpdateIconWrap"));
  urlCard.find(".urlTitleUpdate").val(urlCard.find(".urlTitle").text());
  resetUpdateURLTitleFailErrors(urlCard);
}

// Prepares post request inputs for update of a URL
function updateURLTitleSetup(urlTitleInput) {
  const postURL = routes.updateURLTitle(getActiveUTubID(), getSelectedURLID());

  const updatedURLTitle = urlTitleInput.val();

  data = { urlTitle: updatedURLTitle };

  return [postURL, data];
}

// Handles update of an existing URL
function updateURLTitle(urlTitleInput) {
  // Extract data to submit in POST request
  [postURL, data] = updateURLTitleSetup(urlTitleInput);

  AJAXCall("patch", postURL, data);
  const selectedUrlCard = getSelectedUrlCard();

  // Handle response
  request.done(function (response, _, xhr) {
    if (xhr.status === 200) {
      resetUpdateURLTitleFailErrors(selectedUrlCard);
      if (
        response.hasOwnProperty("URL") &&
        response.URL.hasOwnProperty("urlTitle")
      )
        updateURLTitleSuccess(response, selectedUrlCard);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    updateURLTitleFail(xhr, selectedUrlCard);
  });
}

// Displays changes related to a successful update of a URL
function updateURLTitleSuccess(response, urlCard) {
  // Extract response data
  const updatedURLTitle = response.URL.urlTitle;

  // Update URL body with latest published data
  urlCard.find(".urlTitle").text(updatedURLTitle);
  hideAndResetUpdateURLTitleForm(urlCard);
}

// Displays appropriate prompts and options to user following a failed update of a URL
function updateURLTitleFail(xhr, urlCard) {
  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      const hasErrors = responseJSON.hasOwnProperty("errors");
      if (hasErrors) {
        updateURLTitleFailShowErrors(responseJSON.errors, urlCard);
        break;
      }
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

function updateURLTitleFailShowErrors(errors, urlCard) {
  for (let key in errors) {
    switch (key) {
      case "urlTitle":
        let errorMessage = errors[key][0];
        displayUpdateURLTitleErrors(key, errorMessage, urlCard);
        return;
    }
  }
}

function displayUpdateURLTitleErrors(key, errorMessage, urlCard) {
  urlCard
    .find("." + key + "Update-error")
    .addClass("visible")
    .text(errorMessage);
  urlCard.find("." + key + "Update").addClass("invalid-field");
}

function resetUpdateURLTitleFailErrors(urlCard) {
  const urlTitleUpdateFields = ["urlTitle"];
  urlTitleUpdateFields.forEach((fieldName) => {
    urlCard.find("." + fieldName + "Update").removeClass("invalid-field");
    urlCard.find("." + fieldName + "Update-error").removeClass("visible");
  });
}

/* Delete URL */

// Hide confirmation modal for removal of the selected URL
function deleteURLHideModal() {
  $("#confirmModal").modal("hide");
}

// Show confirmation modal for removal of the selected existing URL from current UTub
function deleteURLShowModal(urlID) {
  let modalTitle = "Are you sure you want to delete this URL from the UTub?";
  let modalText = "You can always add it back again!";
  let buttonTextDismiss = "Just kidding";
  let buttonTextSubmit = "Delete URL";

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody").text(modalText);

  $("#modalDismiss")
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      deleteURLHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      deleteURL(urlID);
    })
    .text(buttonTextSubmit);

  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
  hideIfShown($("#modalRedirect"));
}

// Handles post request and response for removing an existing URL from current UTub, after confirmation
function deleteURL(urlID) {
  // Extract data to submit in POST request
  postURL = deleteURLSetup(urlID);

  let request = AJAXCall("delete", postURL, []);

  // Handle response
  request.done(function (_, textStatus, xhr) {
    if (xhr.status === 200) {
      deleteURLSuccess();
    }
  });

  request.fail(function (xhr, _, textStatus) {
    // Reroute to custom U4I 404 error page
    deleteURLFail(xhr);
  });
}

// Prepares post request inputs for removal of a URL
function deleteURLSetup(urlID) {
  let postURL = routes.deleteURL(getActiveUTubID(), urlID);

  return postURL;
}

// Displays changes related to a successful removal of a URL
function deleteURLSuccess() {
  // Close modal
  $("#confirmModal").modal("hide");
  const selectedUrlToRemove = getSelectedUrlCard();
  selectedUrlToRemove.fadeOut("slow", function () {
    selectedUrlToRemove.remove();
    $("#listURLs").children().length === 0
      ? hideIfShown($("#accessAllURLsBtn"))
      : null;
  });

  displayState1URLDeck();
}

// Displays appropriate prompts and options to user following a failed removal of a URL
function deleteURLFail(xhr) {
  switch (xhr.status) {
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}
