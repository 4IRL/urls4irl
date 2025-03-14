"use strict";

// Prepares post request inputs for removal of a URL - tag
function deleteURLTagSetup(utubID, urlID, utubTagID) {
  const deleteURL = routes.deleteURLTag(utubID, urlID, utubTagID);

  return deleteURL;
}

// Remove tag from selected URL
async function deleteURLTag(utubTagID, tagBadge, urlCard) {
  const utubID = getActiveUTubID();
  const urlID = parseInt(urlCard.attr("urlid"));
  let timeoutID;
  try {
    timeoutID = setTimeoutAndShowLoadingIcon(urlCard);
    await getUpdatedURL(utubID, urlID, urlCard);

    // If tag was already deleted on update of URL, exit early
    if (!isTagInURL(utubTagID, urlCard)) {
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    // Extract data to submit in POST request
    const deleteURL = deleteURLTagSetup(utubID, urlID, utubTagID);

    const request = ajaxCall("delete", deleteURL, []);

    // Handle response
    request.done(function (response, _, xhr) {
      if (xhr.status === 200) {
        deleteURLTagSuccess(tagBadge);
      }
    });

    request.fail(function (xhr, _, textStatus) {
      deleteURLTagFail(xhr);
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

// Displays changes related to a successful removal of a URL
function deleteURLTagSuccess(tagBadge) {
  // If the removed tag is the last instance in the UTub, remove it from the Tag Deck. Else, do nothing.
  tagBadge.remove();

  // Hide the URL if selected tag is filtering
  updateTagFilteringOnURLOrURLTagDeletion();
}

// Displays appropriate prompts and options to user following a failed removal of a URL
function deleteURLTagFail(xhr) {
  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Handle invalid CSRF token error response
    $("body").html(xhr.responseText);
    return;
  }
  window.location.assign(routes.errorPage);
}
