/** URL UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */

  // Add new URL to current UTub
  $("#urlBtnCreate").on("click", function (e) {
    e.stopPropagation();
    hideInputs();
    createURLShowInput();
  });

  // Open all URLs in UTub in separate tabs
  $("#accessAllURLsBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    const ACCESS_ALL_URLS_LIMIT_WARNING = 3;
    if (getNumOfURLs() > ACCESS_ALL_URLS_LIMIT_WARNING) {
      accessAllWarningShowModal();
    } else {
      accessAllURLsInUTub();
    }
  });
});

/** URL Utility Functions **/

// Function to count number of URLs in current UTub
function getNumOfURLs() {
  return $(".urlRow").length;
}

// Simple function to streamline the jQuery selector extraction of selected URL card. Provides ease of reference by URL Functions.
function getSelectedURLCard() {
  const selectedUrlCard = $(".urlRow[urlSelected=true]");
  return selectedUrlCard.length ? selectedUrlCard : null;
}

// function to streamline the jQuery selector extraction of selected URL ID. And makes it easier in case the ID is encoded in a new location in the future
function getSelectedURLID() {
  const selectedUrlCard = getSelectedURLCard();
  return selectedUrlCard === null ? NaN : selectedUrlCard.attr("urlid");
}

// Prevent deselection of URL while modifying its values (e.g. adding a tag, updating URL string or title)
function unbindSelectURLBehavior() {
  getSelectedURLCard().off(".urlSelected");
}

function isURLCurrentlyVisibleInURLDeck(urlString) {
  const visibleURLs = $(".urlString");

  for (let i = 0; i < visibleURLs.length; i++) {
    if ($(visibleURLs[i]).text() === urlString) {
      return true;
    }
  }
  return false;
}

// Perform actions on selection of a URL card
function selectURLCard(urlCard) {
  deselectAllURLs();
  const urlString = urlCard.find(".urlString").text();
  urlCard
    .find(".urlString")
    .off("click.goToURL")
    .on("click.goToURL", function (e) {
      e.stopPropagation();
      accessLink(urlString);
    });
  urlCard.attr({ urlSelected: true });
  urlCard.find(".goToUrlIcon").addClass("visible-flex");
}

// Clean up when deselecting a URL card
function deselectURL(urlCard) {
  urlCard.attr({ urlSelected: false });
  urlCard.find(".urlString").off("click.goToURL");
  urlCard.find(".goToUrlIcon").removeClass("visible-flex hidden");
  hideAndResetUpdateURLTitleForm(urlCard);
  hideAndResetUpdateURLStringForm(urlCard);
  hideAndResetCreateURLTagForm(urlCard);
}

function deselectAllURLs() {
  const previouslySelectedCard = getSelectedURLCard();
  if (previouslySelectedCard !== null) deselectURL(previouslySelectedCard);
}

function showURLCardLoadingIcon(urlCard) {
  urlCard.find(".urlCardDualLoadingRing").addClass("dual-loading-ring");
}

function hideURLCardLoadingIcon(urlCard) {
  urlCard.find(".urlCardDualLoadingRing").removeClass("dual-loading-ring");
}

function setTimeoutAndShowLoadingIcon(urlCard) {
  const timeoutID = setTimeout(function () {
    showURLCardLoadingIcon(urlCard);
  }, SHOW_LOADING_ICON_AFTER_MS);
  return timeoutID;
}

function clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard) {
  clearTimeout(timeoutID);
  hideURLCardLoadingIcon(urlCard);
}

function bindEscapeToExitURLTitleUpdating() {
  $(document)
    .unbind("keyup.escapeUrlTitleUpdating")
    .bind("keyup.escapeUrlTitleUpdating", function (e) {
      if (e.which === 27) {
        console.log("Trying to hide URL title input");
        updateURLTitleHideInput();
      }
    });
}

// Opens new tab
function accessLink(url_string) {
  // Still need to implement: Take user to a new tab with interstitial page warning they are now leaving U4I

  if (!url_string.startsWith("https://")) {
    window.open("https://" + url_string, "_blank").focus();
  } else {
    window.open(url_string, "_blank").focus();
  }
}

// Show confirmation modal for opening all URLs in UTub
function accessAllWarningShowModal() {
  let modalTitle =
    "Are you sure you want to open all " +
    getNumOfURLs() +
    " URLs in this UTub?";
  let modalText = "Performance issues may occur.";
  let modalDismiss = "Cancel";

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody").text(modalText);

  $("#modalDismiss")
    .on("click", function (e) {
      e.preventDefault();
      $("#confirmModal").modal("hide");
    })
    .removeClass()
    .addClass("btn btn-danger")
    .text(modalDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .on("click", function (e) {
      e.preventDefault();
      accessAllURLsInUTub();
    })
    .text("Open all URLs");

  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
  hideIfShown($("#modalRedirect"));
}

// Opens all URLs in UTub in separate tabs
function accessAllURLsInUTub() {
  getUTubInfo(getActiveUTubID()).then(function (selectedUTub) {
    let dictURLs = selectedUTub.urls;

    for (i = 0; i < dictURLs.length; i++) {
      accessLink(dictURLs[i].urlString);
    }
  });
}

// Clear new URL Form
function resetNewURLForm() {
  $("#urlTitleCreate").val(null);
  $("#urlStringCreate").val(null);
  hideIfShown($("#createURLWrap"));
  newURLInputRemoveEventListeners();
}

// Clear the URL Deck
function resetURLDeck() {
  // Empty URL Deck
  // Detach NO URLs text and reattach after emptying

  resetNewURLForm();
  newURLInputRemoveEventListeners();
  $(".urlRow").remove();
}

// Prevent editing URL title when needed
function disableEditingURLTitle(urlCard) {
  const showUpdateURLTitleFormIcon = urlCard.find(
    ".updateURLTitleShowFormIcon",
  );
  if (showUpdateURLTitleFormIcon.length > 0) {
    showUpdateURLTitleFormIcon.addClass("hidden");
  }
}

// Allow editing URL title when needed
function enableEditingURLTitle(urlCard) {
  const showUpdateURLTitleFormIcon = urlCard.find(
    ".updateURLTitleShowFormIcon",
  );
  if (showUpdateURLTitleFormIcon.length > 0) {
    showUpdateURLTitleFormIcon.removeClass("hidden");
  }
}

function setURLCardSelectionEventListener(urlCard) {
  urlCard.off("click.urlSelected").on("click.urlSelected", function (e) {
    if ($(e.target).parents(".urlRow").length > 0) {
      if ($(e.target).closest(".urlRow").attr("urlSelected") === "true") return;
      selectURLCard(urlCard);
    }
  });
}

// Show error at top of URL deck
function showURLDeckBannerError(errorMessage) {
  const SECONDS_TO_SHOW_ERROR = 3.5;
  const errorBanner = $("#URLDeckErrorIndicator");
  const CLASS_TO_SHOW = "URLDeckErrorIndicatorShow";
  errorBanner.text(errorMessage).addClass(CLASS_TO_SHOW).focus();

  setTimeout(() => {
    errorBanner.removeClass(CLASS_TO_SHOW);
  }, 1000 * SECONDS_TO_SHOW_ERROR);
}

/** URL Functions **/

// Update URLs in center panel based on asynchronous updates or stale data
function updateURLDeck(updatedUTubUrls, updatedUTubTags) {
  const oldURLs = $(".urlRow");
  const oldURLIDs = $.map(oldURLs, (url) => parseInt($(url).attr("urlid")));
  const newURLIDs = $.map(updatedUTubUrls, (newURL) => newURL.utubUrlID);

  // Remove any URLs that are in old that aren't in new
  let oldURLID, urlToRemove;
  for (let i = 0; i < oldURLIDs.length; i++) {
    oldURLID = parseInt($(oldURLIDs[i]).attr("urlid"));
    if (!newURLIDs.includes(oldURLID)) {
      urlToRemove = $(".urlRow[urlid=" + oldURLID + "]");
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
      urlToUpdate = $(".urlRow[urlid=" + oldURLIDs[i] + "]");
      updateURLAfterFindingStaleData(
        urlToUpdate,
        updatedUTubUrls.find((url) => url.utubUrlID === oldURLIDs[i]),
        updatedUTubTags,
      );
    }
  }
}

function updateURLAfterFindingStaleData(urlCard, newUrl, updatedUTubTags) {
  const urlTitle = urlCard.find(".urlTitle");
  const urlString = urlCard.find(".urlString");

  urlTitle.text() !== newUrl.urlTitle ? urlTitle.text(newUrl.urlTitle) : null;

  urlString.text() !== newUrl.urlString
    ? urlString.text(newUrl.urlString)
    : null;

  const currentURLTags = urlCard.find(".tagBadge");
  const currentURLTagIDs = $.map(currentURLTags, (tag) =>
    parseInt($(tag).attr("tagid")),
  );

  // Find tag IDs that are in old and not in new and remove them
  for (let i = 0; i < currentURLTagIDs.length; i++) {
    if (!newUrl.urlTagIDs.includes(currentURLTagIDs[i])) {
      currentURLTags.each(function (_, tag) {
        if (parseInt($(tag).attr("tagid")) === currentURLTagIDs[i]) {
          $(tag).remove();
          return false;
        }
      });
    }
  }

  // Find tag IDs that are in new and not old and add them
  const urlTagContainer = urlCard.find(".urlTagsContainer");
  let tagToAdd;
  for (let i = 0; i < newUrl.urlTagIDs.length; i++) {
    if (!currentURLTagIDs.includes(newUrl.urlTagIDs[i])) {
      tagToAdd = updatedUTubTags.find((tag) => tag.id === newUrl.urlTagIDs[i]);
      urlTagContainer.append(
        createTagBadgeInURL(tagToAdd.id, tagToAdd.tagString, urlCard),
      );
    }
  }
}

// Build center panel URL list for selectedUTub
function buildURLDeck(UTubName, dictURLs, dictTags) {
  resetURLDeck();
  const parent = $("#listURLs");
  const numOfURLs = dictURLs.length ? dictURLs.length : 0;

  if (numOfURLs !== 0) {
    // Instantiate deck with list of URLs stored in current UTub
    for (let i = 0; i < dictURLs.length; i++) {
      parent.append(createURLBlock(dictURLs[i], dictTags));
    }

    // Show access all URLs button
    showIfHidden($("#accessAllURLsBtn"));
    hideIfShown($("#NoURLsSubheader"));
  } else {
    showIfHidden($("#NoURLsSubheader"));
    hideIfShown($("#accessAllURLsBtn"));
  }
  displayState1URLDeck(UTubName);
}

// Create a URL block to add to current UTub/URLDeck
function createURLBlock(url, tagArray) {
  const outerUrlCard = $(document.createElement("div")).addClass(
    "urlRow flex-column full-width pad-in-15p pointerable",
  ); // Holds everything in the URL

  const urlTitleGoToURLWrap = $(document.createElement("div")).addClass(
    "flex-row full-width align-center justify-space-between",
  );

  // Append update URL title form if user can edit the URL
  url.canDelete
    ? urlTitleGoToURLWrap.append(
        createURLTitleAndUpdateBlock(url.urlTitle, outerUrlCard),
      )
    : urlTitleGoToURLWrap.append(createURLTitle(url.urlTitle));

  urlTitleGoToURLWrap.append(createGoToURLIcon(url.urlString));

  outerUrlCard.append(urlTitleGoToURLWrap).attr({
    urlID: url.utubUrlID,
    urlSelected: false,
  });

  // Append update URL form if user can edit the URL
  url.canDelete
    ? outerUrlCard.append(
        createURLStringAndUpdateBlock(url.urlString, outerUrlCard),
      )
    : outerUrlCard.append(createURLString(url.urlString));

  outerUrlCard.append(
    createTagsAndOptionsForUrlBlock(url, tagArray, outerUrlCard),
  );

  setURLCardSelectionEventListener(outerUrlCard);

  return outerUrlCard;
}

// Icon to visit URL, situated in top right corner of URL card
function createGoToURLIcon(urlString) {
  const WIDTH_HEIGHT_PX = "20px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const goToUrlOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const goToUrlInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const path =
    "M14 0a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2zM5.904 10.803 10 6.707v2.768a.5.5 0 0 0 1 0V5.5a.5.5 0 0 0-.5-.5H6.525a.5.5 0 1 0 0 1h2.768l-4.096 4.096a.5.5 0 0 0 .707.707";

  goToUrlInnerIconPath.attr({
    d: path,
  });

  goToUrlOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-arrow-up-right-square-fill goToUrlIcon pointerable",
      viewBox: "0 0 16 16",
    })
    .append(goToUrlInnerIconPath)
    .on("click", (e) => {
      e.stopPropagation();
      accessLink(urlString);
    });

  return goToUrlOuterIconSvg;
}

// Element to display the URL title
function createURLTitle(urlTitleText) {
  return $(document.createElement("h6"))
    .addClass("urlTitle long-text-ellipsis")
    .text(urlTitleText);
}

// Element to displayu the URL string
function createURLString(urlStringText) {
  return $(document.createElement("span"))
    .addClass("urlString long-text-ellipsis")
    .text(urlStringText);
}

// Creates a container that allows editing of the URL title for member with valid permissions
function createURLTitleAndUpdateBlock(urlTitleText, urlCard) {
  // Overall container for title and updating title
  const urlTitleAndUpdateWrap = $(document.createElement("div")).addClass(
    "flex-row ninetyfive-width",
  );

  // Contains the url title and icon to show the updating input box
  const urlTitleAndShowUpdateIconWrap = $(
    document.createElement("div"),
  ).addClass("flex-row ninetyfive-width urlTitleAndUpdateIconWrap");
  // Parent container with both show update icon and url title, allows hover to show the update icon
  const urlTitleAndShowUpdateIconInnerWrap = $(
    document.createElement("div"),
  ).addClass("flex-row full-width urlTitleAndUpdateIconInnerWrap");

  // Add icon and title to the container
  urlTitleAndShowUpdateIconInnerWrap
    .append(createURLTitle(urlTitleText))
    .append(createShowUpdateURLTitleIcon());
  urlTitleAndShowUpdateIconWrap.append(urlTitleAndShowUpdateIconInnerWrap);

  // Add icon + title container, and update input container to the parent container
  urlTitleAndUpdateWrap
    .append(urlTitleAndShowUpdateIconWrap)
    .append(createUpdateURLTitleInput(urlTitleText, urlCard));

  return urlTitleAndUpdateWrap;
}

// Create the icon that will show the update URL title form
function createShowUpdateURLTitleIcon() {
  return makeUpdateButton(20)
    .addClass("updateURLTitleShowFormIcon")
    .on("click.showUpdateURLTitle", function (e) {
      if ($(e.target).parents(".urlTitleAndUpdateIconWrap").length > 0) {
        const urlTitleAndIcon = $(e.target).closest(
          ".urlTitleAndUpdateIconWrap",
        );
        showUpdateURLTitleForm(urlTitleAndIcon);
      }
    });
}

// Create the form to update the URL Title
function createUpdateURLTitleInput(urlTitleText, urlCard) {
  // Create the update title text box
  const urlTitleUpdateInputContainer = makeTextInput(
    "urlTitle",
    INPUT_TYPES.UPDATE.description,
  )
    .addClass("updateUrlTitleWrap")
    .css("display", "none");

  urlTitleUpdateInputContainer.find("label").text("URL Title");

  // Customize the input text box for the Url title
  const urlTitleTextInput = urlTitleUpdateInputContainer
    .find("input")
    .prop("minLength", CONSTANTS.URLS_TITLE_MIN_LENGTH)
    .prop("maxLength", CONSTANTS.URLS_TITLE_MAX_LENGTH)
    .val(urlTitleText);

  // Update Url Title submit button
  const urlTitleSubmitBtnUpdate = makeSubmitButton(30)
    .addClass("urlTitleSubmitBtnUpdate")
    .on("click.updateUrlTitle", function () {
      updateURLTitle(urlTitleTextInput, urlCard);
    });

  // Update Url Title cancel button
  const urlTitleCancelBtnUpdate = makeCancelButton(30)
    .addClass("urlTitleCancelBtnUpdate")
    .on("click.updateUrlTitle", function () {
      hideAndResetUpdateURLTitleForm(urlCard);
    });

  urlTitleUpdateInputContainer
    .append(urlTitleSubmitBtnUpdate)
    .append(urlTitleCancelBtnUpdate);

  return urlTitleUpdateInputContainer;
}

// Create the container for both displaying URL string, and updating the URL string
function createURLStringAndUpdateBlock(urlStringText, urlCard) {
  // Overall container for string and updating string
  const urlStringAndUpdateWrap = $(document.createElement("div")).addClass(
    "flex-row ninetyfive-width",
  );

  urlStringAndUpdateWrap
    .append(createURLString(urlStringText))
    .append(createUpdateURLStringInput(urlStringText, urlCard));

  return urlStringAndUpdateWrap;
}

// Create form to update the URL
function createUpdateURLStringInput(urlStringText, urlCard) {
  const urlStringUpdateTextInputContainer = makeTextInput(
    "urlString",
    INPUT_TYPES.UPDATE.description,
  )
    .addClass("updateUrlStringWrap")
    .css("display", "none");

  urlStringUpdateTextInputContainer.find("label").text("URL");

  // Customize the input text box for the Url title
  const urlStringTextInput = urlStringUpdateTextInputContainer
    .find("input")
    .prop("minLength", CONSTANTS.URLS_MIN_LENGTH)
    .prop("maxLength", CONSTANTS.URLS_MAX_LENGTH)
    .val(urlStringText);

  // Update Url Title submit button
  const urlStringSubmitBtnUpdate = makeSubmitButton(30)
    .addClass("urlStringSubmitBtnUpdate")
    .on("click.updateUrlString", function () {
      updateURL(urlStringTextInput, urlCard);
    });

  // Update Url Title cancel button
  const urlStringCancelBtnUpdate = makeCancelButton(30)
    .addClass("urlStringCancelBtnUpdate")
    .on("click.updateUrlString", function () {
      hideAndResetUpdateURLStringForm(urlCard);
    });

  urlStringUpdateTextInputContainer
    .append(urlStringSubmitBtnUpdate)
    .append(urlStringCancelBtnUpdate);

  return urlStringUpdateTextInputContainer;
}

// Create both the tag container and the button container for a URL
function createTagsAndOptionsForUrlBlock(url, tagArray, urlCard) {
  const tagsAndButtonsWrap = $(document.createElement("div")).addClass(
    "tagsAndButtonsWrap full-width",
  );
  const tagsAndTagCreateWrap = $(document.createElement("div")).addClass(
    "urlTags flex-column",
  );
  const tagBadgesWrap = createTagBadgesAndWrap(
    tagArray,
    url.urlTagIDs,
    urlCard,
  );

  tagsAndButtonsWrap.append(tagsAndTagCreateWrap);
  tagsAndTagCreateWrap.append(tagBadgesWrap);

  tagsAndTagCreateWrap.append(createTagInputBlock(urlCard));

  tagsAndButtonsWrap.append(createURLOptionsButtons(url, urlCard));

  return tagsAndButtonsWrap;
}

// Create the outer container for the tag badges
function createTagBadgesAndWrap(dictTags, tagArray, urlCard) {
  const tagBadgesWrap = $(document.createElement("div")).addClass(
    "urlTagsContainer flex-row flex-start",
  );

  for (let j in tagArray) {
    // Find applicable tags in dictionary to apply to URL card
    let tag = dictTags.find(function (e) {
      if (e.id === tagArray[j]) {
        return e;
      }
    });

    let tagSpan = createTagBadgeInURL(tag.id, tag.tagString, urlCard);

    $(tagBadgesWrap).append(tagSpan);
  }

  return tagBadgesWrap;
}

function createTagInputBlock(urlCard) {
  const urlTagCreateTextInputContainer = makeTextInput(
    "urlTag",
    INPUT_TYPES.CREATE.description,
  )
    .addClass("createUrlTagWrap")
    .css("display", "none");

  urlTagCreateTextInputContainer.find("label").text("Tag");

  // Customize the input text box for the Url title
  const urlTagTextInput = urlTagCreateTextInputContainer
    .find("input")
    .prop("minLength", CONSTANTS.TAGS_MIN_LENGTH)
    .prop("maxLength", CONSTANTS.TAGS_MAX_LENGTH);

  // Create Url Title submit button
  const urlTagSubmitBtnCreate = makeSubmitButton(30)
    .addClass("urlTagSubmitBtnCreate")
    .on("click.createURLTag", function () {
      createURLTag(urlTagTextInput, urlCard);
    });

  // Create Url Title cancel button
  const urlTagCancelBtnCreate = makeCancelButton(30)
    .addClass("urlTagCancelBtnCreate")
    .on("click.createURLTag", function () {
      hideAndResetCreateURLTagForm(urlCard);
    });

  urlTagCreateTextInputContainer
    .append(urlTagSubmitBtnCreate)
    .append(urlTagCancelBtnCreate);

  return urlTagCreateTextInputContainer;
}

// Create all the buttons necessary for a url card
function createURLOptionsButtons(url, urlCard) {
  const urlOptions = $(document.createElement("div")).addClass(
    "urlOptions flex-row justify-content-start",
  );
  const urlBtnAccess = $(document.createElement("button"));
  const urlTagBtnCreate = $(document.createElement("button"));

  // Access the URL button
  urlBtnAccess
    .addClass("btn btn-primary urlBtnAccess")
    .attr({ type: "button" })
    .text("Access Link")
    .on("click", function (e) {
      e.stopPropagation();
      accessLink(url.urlString);
    });

  // Add a tag button
  urlTagBtnCreate
    .addClass("btn btn-info urlTagBtnCreate")
    .attr({ type: "button" })
    .text("Add Tag")
    .on("click", function (e) {
      e.stopPropagation();
      showCreateURLTagForm(urlCard, urlTagBtnCreate);
    });

  urlOptions.append(urlBtnAccess).append(urlTagBtnCreate);

  if (url.canDelete) {
    const urlBtnUpdate = $(document.createElement("button"));
    const urlBtnDelete = $(document.createElement("button"));
    urlBtnDelete
      .addClass("btn btn-danger urlBtnDelete")
      .attr({ type: "button" })
      .text("Delete")
      .on("click", function (e) {
        e.stopPropagation();
        deleteURLShowModal(url.utubUrlID, urlCard);
      });

    urlBtnUpdate
      .addClass("btn btn-light urlBtnUpdate")
      .attr({ type: "button" })
      .text("Edit URL")
      .on("click", function (e) {
        e.stopPropagation();
        showUpdateURLStringForm(urlCard, urlBtnUpdate);
      });

    urlOptions.append(urlBtnUpdate).append(urlBtnDelete);
  }
  const urlCardLoadingIcon = $(document.createElement("div")).addClass(
    "urlCardDualLoadingRing",
  );
  urlOptions.append(urlCardLoadingIcon);

  return urlOptions;
}

// New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
function newURLInputAddEventListeners(urlInputForm) {
  const urlBtnCreate = urlInputForm.find("#urlSubmitBtnCreate");
  const urlBtnDelete = urlInputForm.find("#urlCancelBtnCreate");
  const createURLTitleInput = urlInputForm.find("#urlTitleCreate");
  const createURLInput = urlInputForm.find("#urlStringCreate");

  $(urlBtnCreate).on("click.createURL", function (e) {
    e.stopPropagation();
    createURL(createURLTitleInput, createURLInput);
  });

  $(urlBtnDelete).on("click.createURL", function (e) {
    e.stopPropagation();
    createURLHideInput();
  });

  // TODO: Escape and enter functionality
  $(document).on("keyup.createURL", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        createURL(createURLTitleInput, createURLInput);
        break;
      case 27:
        // Handle escape key pressed
        createURLHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function newURLInputRemoveEventListeners() {
  resetCreateURLFailErrors();
  $("#urlSubmitBtnCreate").off();
  $("#urlCancelBtnCreate").off();
  $(document).off(".createURL");
}

// Handle URL deck display changes related to creating a new tag
function createTagBadgeInURL(tagID, tagString, urlCard) {
  const tagSpan = $(document.createElement("span"));
  const removeButton = $(document.createElement("div"));

  tagSpan
    .addClass("tagBadge flex-row align-center")
    .attr({ tagid: tagID })
    .text(tagString);

  removeButton
    .addClass("urlTagBtnDelete flex-row align-center pointerable")
    .on("click", function (e) {
      e.stopPropagation();
      deleteURLTag(tagID, tagSpan, urlCard);
    });

  removeButton.append(createTagDeleteIcon());

  $(tagSpan).append(removeButton);

  return tagSpan;
}

// Dynamically generates the delete URL-Tag icon when needed
function createTagDeleteIcon() {
  const WIDTH_HEIGHT_PX = "15px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const deleteURLTagOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const deleteURLTagInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const path =
    "M11.46.146A.5.5 0 0 0 11.107 0H4.893a.5.5 0 0 0-.353.146L.146 4.54A.5.5 0 0 0 0 4.893v6.214a.5.5 0 0 0 .146.353l4.394 4.394a.5.5 0 0 0 .353.146h6.214a.5.5 0 0 0 .353-.146l4.394-4.394a.5.5 0 0 0 .146-.353V4.893a.5.5 0 0 0-.146-.353zm-6.106 4.5L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708";

  deleteURLTagInnerIconPath.attr({
    d: path,
  });

  deleteURLTagOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-x-octagon-fill",
      viewBox: "0 0 16 16",
    })
    .append(deleteURLTagInnerIconPath);

  return deleteURLTagOuterIconSvg;
}

// Filters all URLs with tags
function filterAllTaggedURLs() {
  hideInputs();

  let selectedBool = $("#selectAll").hasClass("selected");

  let URLCards = $("div.url");

  // For each URL card, verify there remain at least one visible tagBadge, else hide card.
  for (let i = 0; i < URLCards.length; i++) {
    let cardCol = $(URLCards[i]).closest(".cardCol");
    let tagBadges = cardCol.find("span.tagBadge");

    // Only do something if URL has tags applied
    if (tagBadges.length > 0) {
      if (selectedBool) {
        // Show all tagBadges and URLs
        cardCol.show();
        tagBadges.show();
      } else {
        // Hide all tagBadges and URLs
        cardCol.hide();
        tagBadges.hide();
      }
    }
  }
}

// Filters URLs based on Tag Deck state
function filterURL(tagID) {
  hideInputs();

  let filteredTagList = $(".tagBadge[tagid=" + tagID + "]");
  filteredTagList.toggle();

  let URLCards = $("div.url");
  console.log(URLCards);

  for (let i = 0; i < URLCards.length; i++) {
    console.log($(URLCards[i]).closest(".cardCol").find(".URLTitle").text());
    let cardCol = $(URLCards[i]).closest(".cardCol");
    let tagBadges = cardCol.find("span.tagBadge");

    // Default to hiding URL if it has tags
    // Automaticaly show URL if it doesn't have tags
    let hideBool = tagBadges.length ? 0 : 1;

    // If all tags are filtered, hide URL
    for (let j = 0; j < tagBadges.length; j++) {
      console.log(!($(tagBadges[j]).attr("style") == "display: none;"));

      // If any 1 tag is not "display: none;", then URL remains shown
      if (!($(tagBadges[j]).attr("style") == "display: none;")) hideBool ||= 1;
    }

    if (hideBool) {
      cardCol.show();
    } else {
      deselectURL(cardCol);
      cardCol.hide();
    }
  }
}

/** URL Display State Functions **/

// Display state 0: Clean slate, no UTub selected
function displayState0URLDeck() {
  $("#URLDeckHeader").text("URLs");
  hideIfShown($(".updateUTubBtn"));
  hideIfShown($("#urlBtnCreate"));
  hideIfShown($("#accessAllURLsBtn"));
  hideIfShown($("#URLDeckSubheaderCreateDescription"));

  const URLDeckSubheader = $("#URLDeckSubheader");
  URLDeckSubheader.text("Select a UTub");
  showIfHidden(URLDeckSubheader);

  // Prevent on-hover of URL Deck Header to show update UTub name button in case of back button
  $("#utubNameBtnUpdate").removeClass("visibleBtn");
}

// Display state 1: UTub selected, URL list and subheader prompt
function displayState1URLDeck(UTubName) {
  $("#URLDeckHeader").text(UTubName);
  $("#utubNameUpdate").val(UTubName);

  updateUTubNameHideInput();
}
