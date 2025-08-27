"use strict";

$(document).ready(function () {
  bindSwitchURLKeyboardEventListeners();
});

// Clear the URL Deck
function resetURLDeck() {
  // Empty URL Deck
  // Detach NO URLs text and reattach after emptying
  resetNewURLForm();
  newURLInputRemoveEventListeners();
  $(".urlRow").remove();
  $("#urlBtnCreate").hideClass();
  updateUTubDescriptionHideInput();
}

function resetURLDeckOnDeleteUTub() {
  $("#urlBtnCreate").hideClass();
  $("#NoURLsSubheader").hideClass();
  $("#urlBtnDeckCreateWrap").hideClass();
  $("#updateUTubDescriptionBtn")
    .removeClass("visibleBtn")
    .addClass("hiddenBtn");
}

function showURLDeckBannerError(errorMessage) {
  const SECONDS_TO_SHOW_ERROR = 3.5;
  const errorBanner = $("#URLDeckErrorIndicator");
  const CLASS_TO_SHOW = "URLDeckErrorIndicatorShow";
  errorBanner.text(errorMessage).addClass(CLASS_TO_SHOW).trigger("focus");

  setTimeout(() => {
    errorBanner.removeClass(CLASS_TO_SHOW);
  }, 1000 * SECONDS_TO_SHOW_ERROR);
}

// Update URLs in center panel based on asynchronous updates or stale data
function updateURLDeck(updatedUTubUrls, updatedUTubTags) {
  const oldURLs = $(".urlRow");
  const oldURLIDs = $.map(oldURLs, (url) => parseInt($(url).attr("utuburlid")));
  const newURLIDs = $.map(updatedUTubUrls, (newURL) => newURL.utubUrlID);

  // Remove any URLs that are in old that aren't in new
  let oldURLID, urlToRemove;
  for (let i = 0; i < oldURLIDs.length; i++) {
    oldURLID = parseInt($(oldURLIDs[i]).attr("utuburlid"));
    if (!newURLIDs.includes(oldURLID)) {
      urlToRemove = $(".urlRow[utuburlid=" + oldURLID + "]");
      urlToRemove.fadeOut("fast", function () {
        urlToRemove.remove();
      });
    }
  }

  // Add any URLs that are in new that aren't in old
  const urlDeck = $("#listURLs");
  for (let i = 0; i < updatedUTubUrls.length; i++) {
    if (!oldURLIDs.includes(updatedUTubUrls[i].utubUrlID)) {
      urlDeck.append(createURLBlock(updatedUTubUrls[i], updatedUTubTags));
    }
  }

  // Update any URLs in both old/new that might have new data from new
  let urlToUpdate;
  for (let i = 0; i < oldURLIDs.length; i++) {
    if (newURLIDs.includes(oldURLIDs[i])) {
      urlToUpdate = $(".urlRow[utuburlid=" + oldURLIDs[i] + "]");
      updateURLAfterFindingStaleData(
        urlToUpdate,
        updatedUTubUrls.find((url) => url.utubUrlID === oldURLIDs[i]),
        updatedUTubTags,
      );
    }
  }
}

// Build center panel URL list for selectedUTub
function setURLDeckOnUTubSelected(utubName, dictURLs, dictTags) {
  resetURLDeck();
  const parent = $("#listURLs");
  const numOfURLs = dictURLs.length ? dictURLs.length : 0;

  if (numOfURLs !== 0) {
    // Instantiate deck with list of URLs stored in current UTub
    for (let i = 0; i < dictURLs.length; i++) {
      parent.append(
        createURLBlock(dictURLs[i], dictTags).addClass(
          i % 2 === 0 ? "even" : "odd",
        ),
      );
    }

    // Show access all URLs button
    $("#accessAllURLsBtn").showClassNormal();
    $("#NoURLsSubheader").hideClass();
    $("#urlBtnDeckCreateWrap").hideClass();
  } else {
    $("#NoURLsSubheader").showClassNormal();
    $("#urlBtnDeckCreateWrap").showClassFlex();
    $("#accessAllURLsBtn").hideClass();
  }

  $("#urlBtnCreate").showClassNormal();
  setUTubNameAndDescription(utubName);
}

function setURLDeckWhenNoUTubSelected() {
  $(".urlRow").remove();
  $("#URLDeckHeader").text("URLs");
  $(".updateUTubBtn").hideClass();
  $("#urlBtnCreate").hideClass();
  $("#accessAllURLsBtn").hideClass();
  $("#URLDeckSubheaderCreateDescription").hideClass();
  $("#utubNameBtnUpdate").hideClass();
  $("#updateUTubDescriptionBtn")
    .removeClass("visibleBtn")
    .addClass("hiddenBtn");
  removeEventListenersForShowCreateUTubDescIfEmptyDesc();

  const urlDeckSubheader = $("#URLDeckSubheader");
  urlDeckSubheader.text(`${STRINGS.UTUB_SELECT}`);
  urlDeckSubheader.show();

  // Prevent on-hover of URL Deck Header to show update UTub name button in case of back button
  $("#utubNameBtnUpdate").removeClass("visibleBtn");
}

function setUTubNameAndDescription(utubName) {
  $("#URLDeckHeader").text(utubName);
  $("#utubNameUpdate").val(utubName);
  updateUTubNameHideInput();
}
