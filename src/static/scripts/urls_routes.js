/* Add URL */

// Displays new URL input prompt
function createURLHideInput() {
  hideInput("#createURL");
  newURLInputRemoveEventListeners();
  if (!getNumOfURLs()) $("#NoURLsSubheader").show();
}

// Hides new URL input prompt
function createURLShowInput() {
  showInput("#createURL");
  highlightInput($("#urlTitleCreate"));
  newURLInputAddEventListeners();
  if (!getNumOfURLs()) $("#NoURLsSubheader").hide();
}

// Handles addition of new URL after user submission
function createURL() {
  // Extract data to submit in POST request
  [postURL, data] = createURLSetup();

  AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status === 200) {
      createURLSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    if (xhr.status === 404) {
      // Reroute to custom U4I 404 error page
      window.replace.href = "/invalid";
    } else {
      createURLFail(response);
    }
  });
}

// Prepares post request inputs for addition of a new URL
function createURLSetup() {
  // Assemble post request route
  let postURL = routes.createURL(getActiveUTubID());

  // Assemble submission data
  let newURLTitle = $(".#urlTitleCreate").val();
  let newURL = $("#urlStringCreate").val();
  data = {
    urlString: newURL,
    urlTitle: newURLTitle,
  };

  return [postURL, data];
}

// Displays changes related to a successful addition of a new URL
function createURLSuccess(response) {
  resetNewURLForm();

  // DP 09/17 need to implement ability to addTagtoURL interstitially before createURL is completed
  let URLcol = createURLBlock(
    response.URL.utubUrlID,
    response.URL.urlString,
    response.URL.urlTitle,
    [],
    [],
    true,
  );

  $("#UPRRow").prepend(URLcol);
  moveURLsToUpperRowOnSuccessfulCreateURL();

  displayState1URLDeck();
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function createURLFail(response) {
  console.log(response);
  console.log("Basic implementation. Needs revision");
  console.log(response.responseJSON.errorCode);
  console.log(response.responseJSON.message);
  // DP 09/17 could we maybe have a more descriptive reason for failure sent from backend to display to user?
  // Currently STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL is too generic. the # * comments are ideal
}

/* Update URL */

// Shows update URL inputs
function updateURLShowInput() {
  // Show update submission and cancel button, hide update button
  unbindURLKeyboardEventListenersWhenUpdatesOccurring();
  const selectedCardDiv = getSelectedURLCard();
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
  const selectedCardDiv = getSelectedURLCard();
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

  let updatedURL = getSelectedURLCard().find(".updateURL")[0].value;

  data = { urlString: updatedURL };

  return [postURL, data];
}

// Displays changes related to a successful update of a URL
function updateURLSuccess(response) {
  // Extract response data
  let updatedURLID = response.URL.urlID;
  let updatedURLString = response.URL.urlString;

  const selectedCardDiv = getSelectedURLCard();

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
  const selectedCardDiv = getSelectedURLCard();
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
  const selectedCardDiv = getSelectedURLCard();
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

  let updatedURLTitle = getSelectedURLCard().find(".updateURLTitle")[0].value;

  data = { urlTitle: updatedURLTitle };

  return [postURL, data];
}

// Displays changes related to a successful update of a URL
function updateURLTitleSuccess(response) {
  // Extract response data
  let updatedURLTitle = response.URL.urlTitle;

  const selectedCardDiv = getSelectedURLCard();

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
function deleteURLShowModal() {
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
      deleteURL();
    })
    .text(buttonTextSubmit);

  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
  hideIfShown($("#modalRedirect"));
}

// Handles post request and response for removing an existing URL from current UTub, after confirmation
function deleteURL() {
  // Extract data to submit in POST request
  postURL = deleteURLSetup();

  let request = AJAXCall("delete", postURL, []);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status === 200) {
      deleteURLSuccess();
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    if (xhr.status === 404) {
      // Reroute to custom U4I 404 error page
    } else {
      deleteURLFail(response);
    }
  });
}

// Prepares post request inputs for removal of a URL
function deleteURLSetup() {
  let postURL = routes.deleteURL(getActiveUTubID(), getSelectedURLID());

  return postURL;
}

// Displays changes related to a successful removal of a URL
function deleteURLSuccess() {
  // Close modal
  $("#confirmModal").modal("hide");

  let cardCol = $("div[urlid=" + getSelectedURLID() + "]").closest(".cardCol");
  cardCol.fadeOut();
  cardCol.remove();

  displayState1URLDeck();
}

// Displays appropriate prompts and options to user following a failed removal of a URL
function deleteURLFail(xhr, textStatus, error) {
  console.log("Error: Could not delete URL");

  if (xhr.status === 409) {
    console.log(
      "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
    );
    console.log("Error: " + error.Error_code);
  }
}
