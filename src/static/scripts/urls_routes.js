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

// Handles addition of new URL after user submission
function createURL(createUrlTitleInput, createUrlInput) {
  // Extract data to submit in POST request
  [postURL, data] = createURLSetup(createUrlTitleInput, createUrlInput);

  const SHOW_LOADING_ICON_AFTER_MS = 25;

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

// Prepares post request inputs for addition of a new URL
function createURLSetup(createUrlTitleInput, createUrlInput) {
  // Assemble post request route
  const postURL = routes.createURL(getActiveUTubID());

  // Assemble submission data
  const newURLTitle = createUrlTitleInput.val();
  const newURL = createUrlInput.val();
  data = {
    urlString: newURL,
    urlTitle: newURLTitle,
  };

  return [postURL, data];
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
function updateURLShowInput() {
  // Show update submission and cancel button, hide update button
  unbindURLKeyboardEventListenersWhenUpdatesOccurring();
  const selectedCardDiv = getSelectedUrlCard();
  const updateURLInput = selectedCardDiv.find(".updateURL");
  const URL = selectedCardDiv.find(".URL");

  // Show input field
  showIfHidden(updateURLInput.closest(".createDiv"));
  showIfHidden(updateURLInput.next(".urlBtnUpdateWrap"));
  updateURLInput.focus();

  // Hide published value
  hideIfShown(URL);

  // Disable URL Buttons
  disable(selectedCardDiv.find(".urlBtnAccess"));
  disable(selectedCardDiv.find(".tagBtnCreate"));
  disable(selectedCardDiv.find(".urlBtnDelete"));

  // Update URL Button text to show a return string
  const urlBtnUpdate = selectedCardDiv.find(".urlBtnUpdate");
  urlBtnUpdate.text("Exit Updating");
  urlBtnUpdate.removeClass("btn-light").addClass("btn-warning");

  // Make the button close updating now if clicked
  urlBtnUpdate.off("click").on("click", function (e) {
    e.stopPropagation();
    updateURLHideInput();
  });

  // Inhibit selection toggle behavior until user cancels update, or successfully submits update. User can still select and update other URLs in UTub
  unbindSelectURLBehavior();

  // Allow escape key to close updating
  $(document)
    .unbind("keyup.27")
    .bind("keyup.27", function (e) {
      if (e.which === 27) {
        e.stopPropagation();
        updateURLHideInput();
      }
    });
}

// Hides update URL inputs
function updateURLHideInput() {
  // Show update button, hide other buttons
  const selectedCardDiv = getSelectedUrlCard();
  const updateURLInput = selectedCardDiv.find(".updateURL");
  const URL = selectedCardDiv.find(".URL");

  // Updating input field placeholders
  updateURLInput.text(URL.find("card-text").text());

  // Hide input field
  hideIfShown(updateURLInput.closest(".createDiv"));

  // Show published value
  showIfHidden(URL);

  // Enable URL Buttons
  enable(selectedCardDiv.find(".urlBtnAccess"));
  enable(selectedCardDiv.find(".tagBtnCreate"));
  enable(selectedCardDiv.find(".urlBtnDelete"));

  // Update URL Button text to show a return string
  const urlBtnUpdate = selectedCardDiv.find(".urlBtnUpdate");
  urlBtnUpdate.text("Update URL");
  urlBtnUpdate.removeClass("btn-warning").addClass("btn-light");
  urlBtnUpdate.off("click").on("click", function (e) {
    e.stopPropagation();
    updateURLShowInput();
  });

  // Rebind click selection behavior to unselect URL
  rebindSelectBehavior();

  // Unbind escape key from hiding update
  $(document).unbind("keyup.27");

  // Rebind escape key to hiding selected URL
  bindEscapeToUnselectURL(getSelectedURLID());
  bindURLKeyboardEventListenersWhenUpdatesNotOccurring();
}

// Handles update of an existing URL
function updateURL() {
  // Extract data to submit in POST request
  [postURL, data] = updateURLSetup();

  AJAXCall("patch", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      updateURLSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    if (xhr.status === 404) {
      // Reroute to custom U4I 404 error page
    } else {
      updateURLFail(response);
    }
  });
}

// Prepares post request inputs for update of a URL
function updateURLSetup() {
  let postURL = routes.updateURL(getActiveUTubID(), getSelectedURLID());

  let updatedURL = getSelectedUrlCard().find(".updateURL")[0].value;

  data = { urlString: updatedURL };

  return [postURL, data];
}

// Displays changes related to a successful update of a URL
function updateURLSuccess(response) {
  // Extract response data
  let updatedURLID = response.URL.urlID;
  let updatedURLString = response.URL.urlString;

  const selectedCardDiv = getSelectedUrlCard();

  // Update URL ID
  selectedCardDiv.attr("urlid", updatedURLID);

  // If update URL action, rebind the ability to select/deselect URL by clicking it
  rebindSelectBehavior();

  // Update URL body with latest published data
  selectedCardDiv.find(".card-text").text(updatedURLString);

  // Update URL options
  selectedCardDiv
    .find(".urlBtnAccess")
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      accessLink(updatedURLString);
    });

  updateURLHideInput();
}

// Displays appropriate prompts and options to user following a failed update of a URL
function updateURLFail(response) {
  console.log("Error: Could not update URL");
  console.log(
    "Failure. Error code: " +
      response.responseJSON.errorCode +
      ". Status: " +
      response.responseJSON.message,
  );
}

/* Update URL Title */

// Shows update URL Title inputs
function updateURLTitleShowInput() {
  // Show update submission and cancel button, hide update button
  const selectedCardDiv = getSelectedUrlCard();
  const updateURLTitleInput = selectedCardDiv.find(".updateURLTitle");
  const URLTitle = selectedCardDiv.find(".URLTitle");

  // Show input field
  showIfHidden(updateURLTitleInput.closest(".createDiv"));

  // Hide published value
  hideIfShown(URLTitle);

  // Inhibit selection toggle behavior until user cancels update, or successfully submits update. User can still select and update other URLs in UTub
  unbindSelectURLBehavior();
  unbindURLKeyboardEventListenersWhenUpdatesOccurring();
  unbindEscapeKey();
  bindEscapeToExitURLTitleUpdating();

  $(updateURLTitleInput).focus();
}

// Hides update URL Title inputs
function updateURLTitleHideInput() {
  // Show update button, hide other buttons
  const selectedCardDiv = getSelectedUrlCard();
  const updateURLTitleInput = selectedCardDiv.find(".updateURLTitle");
  const URLTitle = selectedCardDiv.find(".URLTitle");

  // Updating input field placeholders
  updateURLTitleInput.text(URLTitle.find("card-title").text());

  // Hide input field
  hideIfShown(updateURLTitleInput.closest(".createDiv"));

  // Show published value
  showIfHidden(URLTitle);

  // Rebind click selection behavior to unselect URL
  rebindSelectBehavior();

  // Unbind escape key from hiding update
  $(document).unbind("keyup.escapeUrlTitleUpdating");

  // Rebind escape key to hiding selected URL
  bindEscapeToUnselectURL(getSelectedURLID());
  bindURLKeyboardEventListenersWhenUpdatesNotOccurring();
}

// Handles update of an existing URL
function updateURLTitle() {
  // Extract data to submit in POST request
  [postURL, data] = updateURLTitleSetup();

  AJAXCall("patch", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      updateURLTitleSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    if (xhr.status === 404) {
      // Reroute to custom U4I 404 error page
    } else {
      updateURLTitleFail(response);
    }
  });
}

// Prepares post request inputs for update of a URL
function updateURLTitleSetup() {
  let postURL = routes.updateURLTitle(getActiveUTubID(), getSelectedURLID());

  let updatedURLTitle = getSelectedUrlCard().find(".updateURLTitle")[0].value;

  data = { urlTitle: updatedURLTitle };

  return [postURL, data];
}

// Displays changes related to a successful update of a URL
function updateURLTitleSuccess(response) {
  // Extract response data
  let updatedURLTitle = response.URL.urlTitle;

  const selectedCardDiv = getSelectedUrlCard();

  // If update URL action, rebind the ability to select/deselect URL by clicking it
  rebindSelectBehavior();

  // Update URL body with latest published data
  selectedCardDiv.find(".card-title").text(updatedURLTitle);

  updateURLTitleHideInput();
}

// Displays appropriate prompts and options to user following a failed update of a URL
function updateURLTitleFail(response) {
  console.log("Error: Could not update URL");
  console.log(
    "Failure. Error code: " +
      response.responseJSON.errorCode +
      ". Status: " +
      response.responseJSON.message,
  );
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
