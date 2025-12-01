"use strict";

// Handles updating a UTub if found to include stale data
// For example, a user decides to update a URL string to a new URL, but it returns
// saying the URL already exists in the UTub -> yet the user does not see the URL in the UTub?
// This means another user has updated a URL or added a URL with the new URL string, in which
// we should reload the user's UTub to show them the latest data
async function updateUTubOnFindingStaleData(selectedUTubID) {
  const utub = await getUTubInfo(selectedUTubID);
  const utubName = utub.name;
  const utubDescription = utub.description;
  updateUTubNameAndDescription(utub.id, utubName, utubDescription);

  // Update Tags
  const utubTags = utub.tags;
  updateTagDeck(utubTags, utub.id);

  // Update URLs
  const utubURLs = utub.urls;
  updateURLDeck(utubURLs, utubTags, utub.id);

  // Update members
  const utubMembers = utub.members;
  const utubOwnerID = utub.createdByUserID;
  const isCurrentUserOwner = utub.isCreator;
  updateMemberDeck(
    utubMembers,
    utubOwnerID,
    isCurrentUserOwner,
    selectedUTubID,
  );

  // Update filtering
  updateTagFilteringOnFindingStaleData();
}

function updateUTubNameAndDescription(utubID, utubName, utubDescription) {
  const utubNameElem = $("#URLDeckHeader");
  const utubNameInUTubDeckElem = $(
    "UTubSelector[utubid=" + utubID + "] > .UTubName",
  );
  const utubDescriptionElem = $("#URLDeckSubheader");

  if (utubNameElem.text() !== utubName) {
    utubNameElem.text(utubName);
    utubNameInUTubDeckElem.text(utubName);
  }

  utubDescriptionElem.text() !== utubDescription
    ? utubDescriptionElem.text(utubDescription)
    : null;
}
