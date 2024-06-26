/* Add URL */

// Displays new URL input prompt
function addURLHideInput() {
  hideInput("addURL");
}

// Displays new URL input prompt
function addURLShowInput() {
  showInput("addURL");
  highlightInput($("#newURLTitle"));
}

// Handles addition of new URL after user submission
function addURL() {
  // Extract data to submit in POST request
  [postURL, data] = addURLSetup();

  AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status === 200) {
      addURLSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    if (xhr.status === 404) {
      // Reroute to custom U4I 404 error page
      window.replace.href = "/invalid";
    } else {
      addURLFail(response);
    }
  });
}

// Prepares post request inputs for addition of a new URL
function addURLSetup() {
  // Assemble post request route
  let postURL = routes.addURL(getActiveUTubID());

  // Assemble submission data
  let newURLTitle = $("#newURLTitle").val();
  let newURL = $("#newURLString").val();
  data = {
    urlString: newURL,
    urlTitle: newURLTitle,
  };

  return [postURL, data];
}

// Displays changes related to a successful addition of a new URL
function addURLSuccess(response) {
  resetNewURLForm();

  // DP 09/17 need to implement ability to addTagtoURL interstitially before addURL is completed
  let URLcol = createURLBlock(
    response.URL.utubUrlID,
    response.URL.urlString,
    response.URL.urlTitle,
    [],
    [],
    true,
  );

  $("#UPRRow").prepend(URLcol);
  moveURLsToUpperRowOnSuccessfulAddURL();

  displayState1URLDeck();
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function addURLFail(response) {
  console.log(response);
  console.log("Basic implementation. Needs revision");
  console.log(response.responseJSON.errorCode);
  console.log(response.responseJSON.message);
  // DP 09/17 could we maybe have a more descriptive reason for failure sent from backend to display to user?
  // Currently STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL is too generic. the # * comments are ideal
}

/* Edit URL */

// Shows edit URL inputs
function editURLShowInput() {
  // Show edit submission and cancel button, hide edit button
  const selectedCardDiv = getSelectedURLCard();
  const editURLInput = selectedCardDiv.find(".editURL");
  const URL = selectedCardDiv.find(".URL");

  // Show input field
  showIfHidden(editURLInput.closest(".createDiv"));

  // Hide published value
  hideIfShown(URL);

  // Inhibit selection toggle behavior until user cancels edit, or successfully submits edit. User can still select and edit other URLs in UTub
  unbindSelectURLBehavior();
}

// Hides edit URL inputs
function editURLHideInput() {
  // Show edit button, hide other buttons
  const selectedCardDiv = getSelectedURLCard();
  const editURLInput = selectedCardDiv.find(".editURL");
  const URL = selectedCardDiv.find(".URL");

  // Updating input field placeholders
  editURLInput.text(URL.find("card-text").text());

  // Hide input field
  hideIfShown(editURLInput.closest(".createDiv"));

  // Show published value
  showIfHidden(URL);

  // Rebind select behavior
  rebindSelectBehavior(getSelectedURLID());
}

// Handles edition of an existing URL
function editURL() {
  // Extract data to submit in POST request
  [postURL, data] = editURLSetup();

  AJAXCall("patch", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      editURLSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    if (xhr.status === 404) {
      // Reroute to custom U4I 404 error page
    } else {
      editURLFail(response);
    }
  });
}

// Prepares post request inputs for edition of a URL
function editURLSetup() {
  let postURL = routes.editURL(getActiveUTubID(), getSelectedURLID());

  let editedURL = getSelectedURLCard().find(".editURL")[0].value;

  data = { urlString: editedURL };

  return [postURL, data];
}

// Displays changes related to a successful edition of a URL
function editURLSuccess(response) {
  // Extract response data
  let editedURLID = response.URL.urlID;
  let editedURLString = response.URL.urlString;

  const selectedCardDiv = getSelectedURLCard();

  // Update URL ID
  selectedCardDiv.attr("urlid", editedURLID);

  // If edit URL action, rebind the ability to select/deselect URL by clicking it
  rebindSelectBehavior(getSelectedURLID());

  // Update URL body with latest published data
  selectedCardDiv.find(".card-text").text(editedURLString);

  // Update URL options
  selectedCardDiv
    .find(".accessURLBtn")
    .off("click")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      accessLink(editedURLString);
    });

  editURLHideInput();
}

// Displays appropriate prompts and options to user following a failed edition of a URL
function editURLFail(response) {
  console.log("Error: Could not edit URL");
  console.log(
    "Failure. Error code: " +
      response.responseJSON.errorCode +
      ". Status: " +
      response.responseJSON.message,
  );
}

/* Edit URL Title */

// Shows edit URL Title inputs
function editURLTitleShowInput() {
  // Show edit submission and cancel button, hide edit button
  const selectedCardDiv = getSelectedURLCard();
  const editURLTitleInput = selectedCardDiv.find(".editURLTitle");
  const URLTitle = selectedCardDiv.find(".URLTitle");

  // Show input field
  showIfHidden(editURLTitleInput.closest(".createDiv"));

  // Hide published value
  hideIfShown(URLTitle);

  // Inhibit selection toggle behavior until user cancels edit, or successfully submits edit. User can still select and edit other URLs in UTub
  unbindSelectURLBehavior();
}

// Hides edit URL Title inputs
function editURLTitleHideInput() {
  // Show edit button, hide other buttons
  const selectedCardDiv = getSelectedURLCard();
  const editURLTitleInput = selectedCardDiv.find(".editURLTitle");
  const URLTitle = selectedCardDiv.find(".URLTitle");

  // Updating input field placeholders
  editURLTitleInput.text(URLTitle.find("card-title").text());

  // Hide input field
  hideIfShown(editURLTitleInput.closest(".createDiv"));

  // Show published value
  showIfHidden(URLTitle);

  // Rebind select behavior
  rebindSelectBehavior(getSelectedURLID());
}

// Handles edition of an existing URL
function editURLTitle() {
  // Extract data to submit in POST request
  [postURL, data] = editURLTitleSetup();

  AJAXCall("patch", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      editURLTitleSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    if (xhr.status === 404) {
      // Reroute to custom U4I 404 error page
    } else {
      editURLTitleFail(response);
    }
  });
}

// Prepares post request inputs for edition of a URL
function editURLTitleSetup() {
  let postURL = routes.editURLTitle(getActiveUTubID(), getSelectedURLID());

  let editedURLTitle = getSelectedURLCard().find(".editURLTitle")[0].value;

  data = { urlTitle: editedURLTitle };

  return [postURL, data];
}

// Displays changes related to a successful edition of a URL
function editURLTitleSuccess(response) {
  // Extract response data
  let editedURLTitle = response.URL.urlTitle;

  const selectedCardDiv = getSelectedURLCard();

  // If edit URL action, rebind the ability to select/deselect URL by clicking it
  rebindSelectBehavior(getSelectedURLID());

  // Update URL body with latest published data
  selectedCardDiv.find(".card-title").text(editedURLTitle);

  editURLTitleHideInput();
}

// Displays appropriate prompts and options to user following a failed edition of a URL
function editURLTitleFail(response) {
  console.log("Error: Could not edit URL");
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
