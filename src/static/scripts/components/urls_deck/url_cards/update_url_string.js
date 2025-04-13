"use strict";

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
    .removeClass("btn-light urlStringBtnUpdate")
    .addClass("btn-warning urlStringCancelBigBtnUpdate")
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
  urlCard.find(".urlStringUpdate").val(urlStringElem.attr("href"));

  // Make the Update URL button now allow updating again
  const urlStringBtnUpdate = urlCard.find(".urlStringCancelBigBtnUpdate");
  urlStringBtnUpdate
    .removeClass("btn-warning urlStringCancelBigBtnUpdate")
    .addClass("btn-light urlStringBtnUpdate")
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
function updateURLSetup(urlStringUpdateInput, utubID, utubUrlID) {
  const postURL = routes.updateURL(utubID, utubUrlID);

  const updatedURL = urlStringUpdateInput.val();

  const data = { urlString: updatedURL };

  return [postURL, data];
}

// Handles update of an existing URL
async function updateURL(urlStringUpdateInput, urlCard) {
  const utubID = getActiveUTubID();
  const utubUrlID = parseInt(urlCard.attr("utuburlid"));
  let timeoutID;
  try {
    timeoutID = setTimeoutAndShowURLCardLoadingIcon(urlCard);
    await getUpdatedURL(utubID, utubUrlID, urlCard);

    if (
      urlStringUpdateInput.val() === urlCard.find(".urlString").attr("href")
    ) {
      hideAndResetUpdateURLStringForm(urlCard);
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    // Extract data to submit in POST request
    let patchURL, data;
    [patchURL, data] = updateURLSetup(urlStringUpdateInput, utubID, utubUrlID);

    const request = ajaxCall("patch", patchURL, data, 35000);

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
    .attr({ href: updatedURLString })
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

  hideAndResetUpdateURLStringForm(urlCard);
}

// Displays appropriate prompts and options to user following a failed update of a URL
function updateURLFail(xhr, urlCard, utubID) {
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
    );
    return;
  }
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
