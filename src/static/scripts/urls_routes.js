// Time until loading icon is shown for URL validation after creation/updating, in ms
const SHOW_LOADING_ICON_AFTER_MS = 50;

/* Add URL */

// Displays new URL input prompt
function createURLHideInput() {
  resetNewURLForm();
  if (!getNumOfURLs()) $("#NoURLsSubheader").show();
}

// Hides new URL input prompt
function createURLShowInput() {
  if (!getNumOfURLs()) $("#NoURLsSubheader").hide();
  const createURLInputForm = $("#createURLWrap");
  showIfHidden(createURLInputForm);
  newURLInputAddEventListeners(createURLInputForm);
  $("#urlTitleCreate").trigger("focus");
  hideIfShown($("#urlBtnCreate"));
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
  [postURL, data] = createURLSetup(createURLTitleInput, createURLInput, utubID);

  // Show loading icon when creating a URL
  const timeoutId = setTimeout(function () {
    $("#urlCreateDualLoadingRing").addClass("dual-loading-ring");
  }, SHOW_LOADING_ICON_AFTER_MS);
  const request = ajaxCall("post", postURL, data);

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
  url.urlTagIDs = [];
  url.canDelete = true;

  // DP 09/17 need to implement ability to addTagtoURL interstitially before createURL is completed
  const newUrlCard = createURLBlock(
    url,
    [], // Mimics an empty array of tags to match against
  );

  newUrlCard.insertAfter($("#createURLWrap"));
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function createURLFail(xhr, utubID) {
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

function resetCreateURLFailErrors() {
  const newUrlFields = ["urlString", "urlTitle"];
  newUrlFields.forEach((fieldName) => {
    $("#" + fieldName + "Create").removeClass("invalid-field");
    $("#" + fieldName + "Create-error").removeClass("visible");
  });
}

/* Update URL */

// Shows update URL inputs
function showUpdateURLStringForm(urlCard, urlStringBtnUpdate) {
  hideIfShown(urlCard.find(".urlString"));
  const updateURLStringWrap = urlCard.find(".updateUrlStringWrap");
  enableTabbableChildElements(updateURLStringWrap);
  showIfHidden(updateURLStringWrap);

  // Set timeout in case user pressed enter to avoid propagation through to URL string update
  setTimeout(function () {
    highlightInput(updateURLStringWrap.find("input"));
  }, 100);

  // Disable URL Buttons as URL is being edited
  hideIfShown(urlCard.find(".urlBtnAccess"));
  hideIfShown(urlCard.find(".urlTagBtnCreate"));
  hideIfShown(urlCard.find(".urlBtnDelete"));

  // Disable Go To URL Icon
  urlCard.find(".goToUrlIcon").removeClass("visible-flex").addClass("hidden");

  // Prevent hovering on tags from adding padding
  urlCard.find(".tagBadge").removeClass("tagBadgeHoverable");

  // Update URL Button text to exit editing
  urlStringBtnUpdate
    .removeClass("btn-light")
    .addClass("btn-warning")
    .text("Cancel")
    .offAndOn("click", function (e) {
      e.stopPropagation();
      hideAndResetUpdateURLStringForm(urlCard);
    });

  // For tablets, change some of the sizing
  if ($(window).width() < TABLET_WIDTH) {
    urlStringBtnUpdate.addClass("full-width");
    urlStringBtnUpdate.closest(".urlOptionsInner").addClass("half-width");
  }

  disableTagRemovalInURLCard(urlCard);
  disableClickOnSelectedURLCardToHide(urlCard);
}

// Resets and hides the Update URL form upon cancellation or selection of another URL
function hideAndResetUpdateURLStringForm(urlCard) {
  // Toggle input form and display of URL
  const updateURLStringWrap = urlCard.find(".updateUrlStringWrap");
  hideIfShown(updateURLStringWrap);
  disableTabbableChildElements(updateURLStringWrap);
  const urlStringElem = urlCard.find(".urlString");
  showIfHidden(urlStringElem);

  // Update the input with current value of url string element
  urlCard.find(".urlStringUpdate").val(urlStringElem.attr("data-url"));

  // Make the Update URL button now allow updating again
  const urlStringBtnUpdate = urlCard.find(".urlStringBtnUpdate");
  urlStringBtnUpdate
    .removeClass("btn-warning")
    .addClass("btn-light")
    .text("Edit URL")
    .offAndOn("click", function (e) {
      e.stopPropagation();
      showUpdateURLStringForm(urlCard, urlStringBtnUpdate);
    });

  // For tablets or in case of resize, change some of the sizing
  urlStringBtnUpdate.removeClass("full-width");
  urlStringBtnUpdate.closest(".urlOptionsInner").removeClass("half-width");

  // Enable URL Buttons
  showIfHidden(urlCard.find(".urlBtnAccess"));
  showIfHidden(urlCard.find(".urlTagBtnCreate"));
  showIfHidden(urlCard.find(".urlBtnDelete"));

  // Enable Go To URL Icon
  const selected = urlCard.attr("urlSelected");
  if (typeof selected === "string" && selected.toLowerCase() === "true") {
    urlCard.find(".goToUrlIcon").removeClass("hidden").addClass("visible-flex");
  }

  // Enable hovering on tags for deletion
  urlCard.find(".tagBadge").addClass("tagBadgeHoverable");

  resetUpdateURLFailErrors(urlCard);
  enableTagRemovalInURLCard(urlCard);
  enableClickOnSelectedURLCardToHide(urlCard);
}

// Prepares post request inputs for update of a URL
function updateURLSetup(urlStringUpdateInput, utubID, urlID) {
  const postURL = routes.updateURL(utubID, urlID);

  const updatedURL = urlStringUpdateInput.val();

  const data = { urlString: updatedURL };

  return [postURL, data];
}

// Handles update of an existing URL
async function updateURL(urlStringUpdateInput, urlCard) {
  const utubID = getActiveUTubID();
  const urlID = parseInt(urlCard.attr("urlid"));
  let timeoutID;
  try {
    timeoutID = setTimeoutAndShowLoadingIcon(urlCard);
    await getUpdatedURL(utubID, urlID, urlCard);

    if (
      urlStringUpdateInput.val() === urlCard.find(".urlString").attr("data-url")
    ) {
      hideAndResetUpdateURLStringForm(urlCard);
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    // Extract data to submit in POST request
    [patchURL, data] = updateURLSetup(urlStringUpdateInput, utubID, urlID);

    const request = ajaxCall("patch", patchURL, data);

    request.done(function (response, _, xhr) {
      if (xhr.status === 200) {
        updateURLSuccess(response, urlCard);
      }
    });

    request.fail(function (xhr, _, textStatus) {
      resetUpdateURLFailErrors(urlCard);
      updateURLFail(xhr, urlCard, utubID);
    });

    request.always(function () {
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    });
  } catch (error) {
    clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    handleRejectFromGetURL(error, urlCard, {
      showError: true,
      message: "Another user has deleted this URL",
    });
  }
}

// Displays changes related to a successful update of a URL
function updateURLSuccess(response, urlCard) {
  // Extract response data
  const updatedURLString = response.URL.urlString;

  // If update URL action, rebind the ability to select/deselect URL by clicking it
  //rebindSelectBehavior();

  // Update URL body with latest published data
  urlCard
    .find(".urlString")
    .attr({ "data-url": updatedURLString })
    .text(updatedURLString);

  // Update URL options
  urlCard.find(".urlBtnAccess").offAndOn("click", function (e) {
    e.stopPropagation();
    accessLink(updatedURLString);
  });

  urlCard.find(".goToUrlIcon").offAndOn("click", function (e) {
    e.stopPropagation();
    accessLink(updatedURLString);
  });
  setURLCardURLStringClickableWhenSelected(urlCard);

  hideAndResetUpdateURLStringForm(urlCard);
}

// Displays appropriate prompts and options to user following a failed update of a URL
function updateURLFail(xhr, urlCard, utubID) {
  const responseJSON = xhr.responseJSON;
  const hasErrors = responseJSON.hasOwnProperty("errors");
  const hasMessage = responseJSON.hasOwnProperty("message");
  switch (xhr.status) {
    case 400:
      if (hasErrors) {
        updateURLFailErrors(responseJSON.errors, urlCard);
        break;
      }
      if (hasMessage) {
        displayUpdateURLErrors("urlString", responseJSON.message, urlCard);
        break;
      }
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
      displayUpdateURLErrors("urlString", responseJSON.message, urlCard);
      break;
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

function updateURLFailErrors(errors, urlCard) {
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
function showUpdateURLTitleForm(urlTitleAndShowUpdateIconWrap, urlCard) {
  hideIfShown(urlTitleAndShowUpdateIconWrap);
  const updateTitleForm = urlTitleAndShowUpdateIconWrap.siblings(
    ".updateUrlTitleWrap",
  );
  showIfHidden(updateTitleForm);
  updateTitleForm.find("input").trigger("focus");
  disableClickOnSelectedURLCardToHide(urlCard);
}

// Resets and hides the Update URL form upon cancellation or selection of another URL
function hideAndResetUpdateURLTitleForm(urlCard) {
  hideIfShown(urlCard.find(".updateUrlTitleWrap"));
  showIfHidden(urlCard.find(".urlTitleAndUpdateIconWrap"));
  urlCard.find(".urlTitleUpdate").val(urlCard.find(".urlTitle").text());
  resetUpdateURLTitleFailErrors(urlCard);
  enableClickOnSelectedURLCardToHide(urlCard);
}

// Prepares post request inputs for update of a URL
function updateURLTitleSetup(urlTitleInput, utubID, urlID) {
  const patchURL = routes.updateURLTitle(utubID, urlID);

  const updatedURLTitle = urlTitleInput.val();

  const data = { urlTitle: updatedURLTitle };

  return [patchURL, data];
}

// Handles update of an existing URL
async function updateURLTitle(urlTitleInput, urlCard) {
  // Extract data to submit in POST request
  const utubID = getActiveUTubID();
  const urlID = parseInt(urlCard.attr("urlid"));
  let timeoutID;
  try {
    timeoutID = setTimeoutAndShowLoadingIcon(urlCard);
    await getUpdatedURL(utubID, urlID, urlCard);

    if (urlTitleInput.val() === urlCard.find(".urlTitle").text()) {
      hideAndResetUpdateURLTitleForm(urlCard);
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    [patchURL, data] = updateURLTitleSetup(urlTitleInput, utubID, urlID);

    const request = ajaxCall("patch", patchURL, data);

    // Handle response
    request.done(function (response, _, xhr) {
      if (xhr.status === 200) {
        resetUpdateURLTitleFailErrors(urlCard);
        if (
          response.hasOwnProperty("URL") &&
          response.URL.hasOwnProperty("urlTitle")
        )
          updateURLTitleSuccess(response, urlCard);
      }
    });

    request.fail(function (xhr, _, textStatus) {
      updateURLTitleFail(xhr, urlCard);
    });

    request.always(function () {
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    });
  } catch (error) {
    clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    handleRejectFromGetURL(error, urlCard, {
      showError: true,
      message: "Another user has deleted this URL",
    });
  }
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
        updateURLTitleFailErrors(responseJSON.errors, urlCard);
        break;
      }
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

function updateURLTitleFailErrors(errors, urlCard) {
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
function deleteURLShowModal(urlID, urlCard) {
  let modalTitle = "Are you sure you want to delete this URL from the UTub?";
  let modalText = "You can always add it back again!";
  let buttonTextDismiss = "Just kidding";
  let buttonTextSubmit = "Delete URL";

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody").text(modalText);

  $("#modalDismiss")
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteURLHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteURL(urlID, urlCard);
    })
    .text(buttonTextSubmit);

  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
  hideIfShown($("#modalRedirect"));
}

// Prepares post request inputs for removal of a URL
function deleteURLSetup(utubID, urlID) {
  const deleteURL = routes.deleteURL(utubID, urlID);
  return deleteURL;
}

// Handles post request and response for removing an existing URL from current UTub, after confirmation
async function deleteURL(urlID, urlCard) {
  const utubID = getActiveUTubID();
  try {
    // Check for stale data
    await getUpdatedURL(utubID, urlID, urlCard);
    // Extract data to submit in POST request
    const deleteURL = deleteURLSetup(utubID, urlID);

    const request = ajaxCall("delete", deleteURL, []);

    // Handle response
    request.done(function (response, textStatus, xhr) {
      if (xhr.status === 200) {
        deleteURLSuccessOnDelete(response, urlCard);
      }
    });

    request.fail(function (xhr, _, textStatus) {
      // Reroute to custom U4I 404 error page
      deleteURLFail(xhr);
    });
  } catch (error) {
    handleRejectFromGetURL(error, urlCard, { showError: false });
  }
}

// Displays changes related to a successful removal of a URL
function deleteURLSuccessOnDelete(response, urlCard) {
  // Close modal
  $("#confirmModal").modal("hide");
  urlCard.fadeOut("slow", function () {
    cleanTagsAfterDeleteURL(response);
    urlCard.remove();
    $("#listURLs .urlRow").length === 0
      ? $("#accessAllURLsBtn").hide()
      : updateTagFilteringOnURLOrURLTagDeletion();
  });
}

// Cleans tags after successful URL deletion
function cleanTagsAfterDeleteURL(response) {
  if (!response.hasOwnProperty("tags") || response.tags.length === 0) return;
  const tagsInResponse = response.tags;

  let tag;
  for (let i = 0; i < tagsInResponse.length; i++) {
    tag = tagsInResponse[i];
    if (!tag.tagInUTub) removeTagFromTagDeckGivenTagID(tag.id);
  }
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

/* Get URL */
async function getUpdatedURL(utubID, utubUrlID, urlCard) {
  return new Promise((resolve, reject) => {
    $.ajax({
      url: routes.getURL(utubID, utubUrlID),
      type: "GET",
      dataType: "json",
      success: (response, _, xhr) => {
        if (xhr.status === 200 && response.hasOwnProperty("URL")) {
          updateURLBasedOnGetData(response.URL, urlCard);
          resolve();
        }
        resolve(xhr);
      },
      error: (xhr, _, errorThrown) => {
        reject(xhr);
      },
    });
  });
}

function updateURLBasedOnGetData(urlUpdateResponse, urlCard) {
  const urlTitleElem = urlCard.find(".urlTitle");
  const urlStringElem = urlCard.find(".urlString");
  const urlTags = urlCard.find(".tagBadge");

  urlTitleElem !== urlUpdateResponse.urlTitle
    ? urlTitleElem.text(urlUpdateResponse.urlTitle)
    : null;

  urlStringElem !== urlUpdateResponse.urlString
    ? urlStringElem
        .attr({ "data-url": urlUpdateResponse.urlString })
        .text(urlUpdateResponse.urlString)
    : null;

  updateURLTagsAndUTubTagsBasedOnGetURLData(
    urlTags,
    urlUpdateResponse.urlTags,
    urlCard,
  );
}

function updateURLTagsAndUTubTagsBasedOnGetURLData(
  currentTags,
  receivedTags,
  urlCard,
) {
  const receivedTagIDs = receivedTags.map((tag) => tag.tagID);
  let removedTagIDs = [];

  // Remove current tags that are not in received tags
  currentTags.each(function () {
    const tagID = parseInt($(this).attr("tagid"));
    if (!receivedTagIDs.includes(tagID)) {
      $(this).remove();
      removedTagIDs.push(tagID);
    }
  });

  // Based on IDs, find if tag still exists in UTub - if not, remove from tag deck
  const allCurrentTags = $(".tagBadge");
  for (let i = 0; i < removedTagIDs.length; i++) {
    if (!isTagInUTub(allCurrentTags, removedTagIDs[i])) {
      removeTagFromTagDeckGivenTagID(removedTagIDs[i]);
    }
  }

  // Add tags that are in received tags but not in current tags
  let exists, receivedTag;
  for (let i = 0; i < receivedTags.length; i++) {
    exists = false;
    receivedTag = receivedTags[i];
    currentTags.each(function () {
      if (parseInt($(this).attr("tagid")) === receivedTag.tagID) {
        exists = true;
      }
    });

    if (!exists) {
      // Add tag to URL
      urlCard
        .find(".urlTagsContainer")
        .append(
          createTagBadgeInURL(
            receivedTag.tagID,
            receivedTag.tagString,
            urlCard,
          ),
        );

      // Add tag to UTub if it doesn't already exist
      if (!isTagInUTub(allCurrentTags, receivedTag.tagID)) {
        $("#listTags").append(
          createTagFilterInDeck(receivedTag.tagID, receivedTag.tagString),
        );
      }
    }
  }
}

function handleRejectFromGetURL(xhr, urlCard, errorMessage) {
  switch (xhr.status) {
    case 403:
      // User not authorized for this UTub
      window.location.assign(routes.errorPage);
      break;
    case 404:
      if (xhr.getResponseHeader("content-type").indexOf("text/html") >= 0) {
        // UTub does not exist
        window.location.assign(routes.errorPage);
        break;
      }
      // URL no longer exists
      errorMessage.showError
        ? showURLDeckBannerError(errorMessage.message)
        : null;
      checkForTagUpdatesAndRemoveOnStaleURLDeletion(urlCard);
      deleteURLOnStale(urlCard);
      break;

    default:
      window.location.assign(routes.errorPage);
      break;
  }
}

function deleteURLOnStale(urlCard) {
  // Close modal in case URL was found stale while it's shown
  $("#confirmModal").modal("hide");
  urlCard.fadeOut("slow", function () {
    checkForTagUpdatesAndRemoveOnStaleURLDeletion(urlCard);
    urlCard.remove();
    $("#listURLs .urlRow").length === 0
      ? $("#accessAllURLsBtn").hide()
      : updateTagFilteringOnURLOrURLTagDeletion();
  });
}

function checkForTagUpdatesAndRemoveOnStaleURLDeletion(staleURLCard) {
  const unstaleTagBadges = $(".tagBadge").filter(
    (_, tag) => !$(tag).closest(".urlRow").is(staleURLCard),
  );

  const staleURLTagBadges = staleURLCard.find(".tagBadge");
  if (staleURLTagBadges.length === 0) return;
  const staleURLTagBadgeIDs = staleURLTagBadges.map((_, tag) =>
    parseInt($(tag).attr("tagid")),
  );

  for (let i = 0; i < staleURLTagBadgeIDs.length; i++) {
    if (!isTagInUTub(unstaleTagBadges, staleURLTagBadgeIDs[i])) {
      removeTagFromTagDeckGivenTagID(staleURLTagBadgeIDs[i]);
    }
  }
}
