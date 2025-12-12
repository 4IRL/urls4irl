"use strict";

// Prepares post request inputs for removal of a URL - tag
function deleteURLTagSetup(utubID, utubUrlID, utubTagID) {
  const deleteURLTag = APP_CONFIG.routes.deleteURLTag(
    utubID,
    utubUrlID,
    utubTagID,
  );

  return deleteURLTag;
}

// Remove tag from selected URL
async function deleteURLTag(utubTagID, tagBadge, urlCard, utubID) {
  const utubUrlID = parseInt(urlCard.attr("utuburlid"));
  let timeoutID;
  try {
    timeoutID = setTimeoutAndShowURLCardLoadingIcon(urlCard);
    await getUpdatedURL(utubID, utubUrlID, urlCard);

    // If tag was already deleted on update of URL, exit early
    if (!isTagInURL(utubTagID, urlCard)) {
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    // Extract data to submit in POST request
    const deleteURL = deleteURLTagSetup(utubID, utubUrlID, utubTagID);

    const request = ajaxCall("delete", deleteURL, []);

    // Handle response
    request.done(function (response, _, xhr) {
      if (xhr.status === 200) {
        deleteURLTagSuccess(response, tagBadge, urlCard);
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
function deleteURLTagSuccess(response, tagBadge, urlCard) {
  const tagID = response.utubTag.utubTagID;

  updateTagFilterCount(
    tagID,
    response.tagCountsInUtub,
    TagCountOperation.DECREMENT,
  );

  const currentURLTagIDs = urlCard.attr("data-utub-url-tag-ids") || "";

  if (currentURLTagIDs.trim()) {
    let tagIDs = currentURLTagIDs.split(",").map((s) => s.trim());
    const index = tagIDs.findIndex((num) => parseInt(num) === tagID);

    if (index !== -1) {
      tagIDs.splice(index, 1);
    }
    urlCard.attr("data-utub-url-tag-ids", tagIDs.join(","));
  }

  // Remove the tag badge from the URL card
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
  window.location.assign(APP_CONFIG.routes.errorPage);
}
