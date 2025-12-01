"use strict";

// Shows the update URL title form
function showUpdateURLTitleForm(urlTitleAndShowUpdateIconWrap, urlCard) {
  urlTitleAndShowUpdateIconWrap.hideClass();
  const updateTitleForm = urlTitleAndShowUpdateIconWrap.siblings(
    ".updateUrlTitleWrap",
  );
  updateTitleForm.showClassFlex();
  updateTitleForm.find("input").trigger("focus");

  // Prevent hovering on tags from adding padding
  urlCard.find(".tagBadge").removeClass("tagBadgeHoverable");

  disableClickOnSelectedURLCardToHide(urlCard);
}

// Resets and hides the Update URL form upon cancellation or selection of another URL
function hideAndResetUpdateURLTitleForm(urlCard) {
  urlCard.find(".updateUrlTitleWrap").hideClass();
  urlCard.find(".urlTitleAndUpdateIconWrap").showClassFlex();
  urlCard.find(".urlTitleUpdate").val(urlCard.find(".urlTitle").text());

  // Enable hovering on tags for deletion
  urlCard.find(".tagBadge").addClass("tagBadgeHoverable");

  resetUpdateURLTitleFailErrors(urlCard);
  enableClickOnSelectedURLCardToHide(urlCard);
}

// Prepares post request inputs for update of a URL
function updateURLTitleSetup(urlTitleInput, utubID, utubUrlID) {
  const patchURL = routes.updateURLTitle(utubID, utubUrlID);

  const updatedURLTitle = urlTitleInput.val();

  const data = { urlTitle: updatedURLTitle };

  return [patchURL, data];
}

// Handles update of an existing URL
async function updateURLTitle(urlTitleInput, urlCard, utubID) {
  // Extract data to submit in POST request
  const utubUrlID = parseInt(urlCard.attr("utuburlid"));
  let timeoutID;
  try {
    timeoutID = setTimeoutAndShowURLCardLoadingIcon(urlCard);
    await getUpdatedURL(utubID, utubUrlID, urlCard);

    if (urlTitleInput.val() === urlCard.find(".urlTitle").text()) {
      hideAndResetUpdateURLTitleForm(urlCard);
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    let patchURL, data;
    [patchURL, data] = updateURLTitleSetup(urlTitleInput, utubID, utubUrlID);

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
  if (!xhr.hasOwnProperty("responseJSON")) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // Handle invalid CSRF token error response
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(routes.errorPage);
    return;
  }

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
