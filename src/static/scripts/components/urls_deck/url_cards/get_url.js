"use strict";

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

  if (urlStringElem.attr("href") !== urlUpdateResponse.urlString) {
    const displayURL = modifyURLStringForDisplay(urlUpdateResponse.urlString);

    urlStringElem.attr({ href: urlUpdateResponse.urlString }).text(displayURL);
  }

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
  const receivedTagIDs = receivedTags.map((tag) => tag.utubTagID);
  let removedTagIDs = [];

  // Remove current tags that are not in received tags
  currentTags.each(function () {
    const utubTagID = parseInt($(this).attr("data-utub-tag-id"));
    if (!receivedTagIDs.includes(utubTagID)) {
      $(this).remove();
      removedTagIDs.push(utubTagID);
    }
  });

  // Based on IDs, find if tag still exists in UTub - if not, remove from tag deck
  for (let i = 0; i < removedTagIDs.length; i++) {
    if (!isTagInUTubTagDeck(tag.utubTagID)) {
      removeTagFromTagDeckGivenTagID(removedTagIDs[i]);
    }
  }

  // Add tags that are in received tags but not in current tags
  let exists, receivedTag, currentTag;
  for (let i = 0; i < receivedTags.length; i++) {
    exists = false;
    receivedTag = receivedTags[i];

    for (let j = 0; j < currentTags.length; j++) {
      currentTag = currentTags[j];
      exists =
        parseInt($(currentTag).attr("data-utub-tag-id")) ===
        receivedTag.utubTagID;
      if (exists) break;
    }

    if (!exists) {
      // Add tag to URL
      urlCard
        .find(".urlTagsContainer")
        .append(
          createTagBadgeInURL(
            receivedTag.utubTagID,
            receivedTag.tagString,
            urlCard,
          ),
        );

      // Add tag to UTub if it doesn't already exist
      if (!isTagInUTubTagDeck(receivedTag.utubTagID)) {
        $("#listTags").append(
          buildTagFilterInDeck(receivedTag.utubTagID, receivedTag.tagString),
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
    urlCard.remove();
    $("#listURLs .urlRow").length === 0
      ? $("#accessAllURLsBtn").hide()
      : updateTagFilteringOnURLOrURLTagDeletion();
  });
}
