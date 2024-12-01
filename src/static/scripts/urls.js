/** URL UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */
  const urlBtnCreateSelector = "#urlBtnCreate";
  const urlBtnDeckCreateSelector = "#urlBtnDeckCreate";
  const urlBtnCreate = $(urlBtnCreateSelector);
  const urlBtnDeckCreate = $(urlBtnDeckCreateSelector);

  // Add new URL to current UTub
  urlBtnCreate.on("click", function (e) {
    if ($(e.target).closest("#urlBtnCreate").length > 0) createURLShowInput();
  });
  urlBtnDeckCreate.on("click", function (e) {
    if ($(e.target).closest("#urlBtnDeckCreate").length > 0)
      createURLShowInput();
  });

  // Bind enter key
  urlBtnCreate.on("focus", bindCreateURLSubmissionEnterKeyEventListener());
  urlBtnDeckCreate.on("focus", bindCreateURLSubmissionEnterKeyEventListener());

  urlBtnCreate.on("blur", unbindCreateURLFocusEventListeners());
  urlBtnDeckCreate.on("blur", unbindCreateURLFocusEventListeners());

  // Open all URLs in UTub in separate tabs
  $("#accessAllURLsBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    const ACCESS_ALL_URLS_LIMIT_WARNING = CONSTANTS.MAX_NUM_OF_URLS_TO_ACCESS;
    if (getNumOfVisibleURLs() > ACCESS_ALL_URLS_LIMIT_WARNING) {
      accessAllWarningShowModal();
    } else {
      accessAllURLsInUTub();
    }
  });
});

function bindCreateURLShowInputEventListener(selector) {
  if ($(e.target).closest(selector).length > 0) createURLShowInput();
}

function bindCreateURLSubmissionEnterKeyEventListener() {
  $(document).on("keyup.createURL", function (e) {
    if (e.which === 13) {
      createURLShowInput();
    }
  });
}

function bindCreateURLFocusEventListeners(createURLTitleInput, createURLInput) {
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

function unbindCreateURLFocusEventListeners() {
  $(document).off(".createURL");
}

// Prevent deselection of URL while modifying its values (e.g. adding a tag, updating URL string or title)
function unbindSelectURLBehavior() {
  getSelectedURLCard().off(".urlSelected");
}

/** URL Utility Functions **/

// Function to count number of URLs in current UTub
function getNumOfURLs() {
  return $(".urlRow").length;
}

// Function to count number of visible URLs in current UTub, after filtering
function getNumOfVisibleURLs() {
  return $(".urlRow[filterable=true]").length;
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

function isURLCurrentlyVisibleInURLDeck(urlString) {
  const visibleURLs = $(".urlString");

  for (let i = 0; i < visibleURLs.length; i++) {
    if ($(visibleURLs[i]).attr("data-url") === urlString) {
      return true;
    }
  }
  return false;
}

// Perform actions on selection of a URL card
function selectURLCard(urlCard) {
  deselectAllURLs();
  setURLCardURLStringClickableWhenSelected(urlCard);

  urlCard.attr({ urlSelected: true });
  urlCard.find(".goToUrlIcon").addClass("visible-flex");
  enableClickOnSelectedURLCardToHide(urlCard);

  enableTabbingOnURLCardElements(urlCard);
}

function setURLCardURLStringClickableWhenSelected(urlCard) {
  const urlString = urlCard.find(".urlString").attr("data-url");
  urlCard
    .find(".urlString")
    .offAndOn("click.goToURL", function (e) {
      e.stopPropagation();
      accessLink(urlString);
    })
    .offAndOn("focus.accessURL", function () {
      $(document).on("keyup.accessURL", function (e) {
        if (e.which === 13) accessLink(urlString);
      });
    })
    .offAndOn("blur.accessURL", function () {
      $(document).off("keyup.accessURL");
    });
}

function enableClickOnSelectedURLCardToHide(urlCard) {
  urlCard.on("click.deselectURL", () => {
    deselectURL(urlCard);
  });
}

function disableClickOnSelectedURLCardToHide(urlCard) {
  urlCard.off("click.deselectURL");
}

// Clean up when deselecting a URL card
function deselectURL(urlCard) {
  disableClickOnSelectedURLCardToHide(urlCard);
  urlCard.attr({ urlSelected: false });
  urlCard.find(".urlString").off("click.goToURL");
  urlCard
    .find(".goToUrlIcon")
    .removeClass("visible-flex hidden visible-on-focus");
  hideAndResetUpdateURLTitleForm(urlCard);
  hideAndResetUpdateURLStringForm(urlCard);
  hideAndResetCreateURLTagForm(urlCard);
  disableTabbingOnURLCardElements(urlCard);
  setURLCardSelectionEventListener(urlCard);
  setFocusEventListenersOnURLCard(urlCard);
  urlCard.blur(); // Remove focus after deselecting the URL
}

function deselectAllURLs() {
  const previouslySelectedCard = getSelectedURLCard();
  if (previouslySelectedCard !== null) deselectURL(previouslySelectedCard);
}

function enableTabbingOnURLCardElements(urlCard) {
  urlCard.find(".tabbable").enableTab();
}

function disableTabbingOnURLCardElements(urlCard) {
  urlCard.find(".tabbable").disableTab();
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

// Opens new tab
function accessLink(urlString) {
  // Still need to implement: Take user to a new tab with interstitial page warning they are now leaving U4I

  if (!urlString.startsWith("https://")) {
    window.open("https://" + urlString, "_blank").focus();
  } else {
    window.open(urlString, "_blank").focus();
  }
}

function hideAccessAllWarningShowModal() {
  $("#confirmModal").removeClass("accessAllUrlModal");
  console.log("Testing hide functionality");
}

// Show confirmation modal for opening all URLs in UTub
function accessAllWarningShowModal() {
  const modalTitle =
    "Are you sure you want to open all " +
    getNumOfURLs() +
    " URLs in this UTub?";
  const modalText = "Performance issues may occur.";
  const modalDismiss = "Cancel";

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
      $("#confirmModal").modal("hide");
    })
    .text("Open all URLs");

  $("#confirmModal")
    .modal("show")
    .addClass("accessAllUrlModal")
    .on("hidden.bs.modal", hideAccessAllWarningShowModal);

  $("#modalRedirect").hide();
  hideIfShown($("#modalRedirect"));
}

// Opens all visible URLs in UTub in separate tabs
function accessAllURLsInUTub() {
  const visibleSelector = ".urlRow[filterable=true] .urlString";
  const visibleURLs = $(visibleSelector);
  if (visibleURLs.length === 0) return;

  const visibleURLsToAccess = $.map(visibleURLs, (url) =>
    $(url).attr("data-url"),
  );

  for (i = 0; i < visibleURLsToAccess.length; i++) {
    accessLink(visibleURLsToAccess[i]);
  }
}

// Clear new URL Form
function resetNewURLForm() {
  $("#urlTitleCreate").val(null);
  $("#urlStringCreate").val(null);
  hideIfShown($("#createURLWrap"));
  newURLInputRemoveEventListeners();
  showIfHidden($("#urlBtnCreate"));
}

// Clear the URL Deck
function resetURLDeck() {
  // Empty URL Deck
  // Detach NO URLs text and reattach after emptying

  resetNewURLForm();
  newURLInputRemoveEventListeners();
  $(".urlRow").remove();
  hideIfShown($("#urlBtnCreate"));
}

function resetURLDeckOnDeleteUTub() {
  hideIfShown($("#urlBtnCreate"));
  hideIfShown($("#NoURLsSubheader"));
  hideIfShown($("#urlBtnDeckCreate"));
}

// Prevent editing URL title when needed
function disableEditingURLTitle(urlCard) {
  const showUpdateURLTitleFormIcon = urlCard.find(".urlTitleBtnUpdate");
  if (showUpdateURLTitleFormIcon.length > 0) {
    showUpdateURLTitleFormIcon.addClass("hidden");
  }
}

// Allow editing URL title when needed
function enableEditingURLTitle(urlCard) {
  const showUpdateURLTitleFormIcon = urlCard.find(".urlTitleBtnUpdate");
  if (showUpdateURLTitleFormIcon.length > 0) {
    showUpdateURLTitleFormIcon.removeClass("hidden");
  }
}

function setURLCardSelectionEventListener(urlCard) {
  urlCard.offAndOn("click.urlSelected", function (e) {
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
  errorBanner.text(errorMessage).addClass(CLASS_TO_SHOW).trigger("focus");

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

  urlString.attr("data-url") !== newUrl.urlString
    ? urlString.text(newUrl.urlString).attr({ "data-url": newUrl.urlString })
    : null;

  const currentURLTags = urlCard.find(".tagBadge");
  const currentURLTagIDs = $.map(currentURLTags, (tag) =>
    parseInt($(tag).attr("data-utub-tag-id")),
  );

  // Find tag IDs that are in old and not in new and remove them
  for (let i = 0; i < currentURLTagIDs.length; i++) {
    if (!newUrl.utubUrlTagIDs.includes(currentURLTagIDs[i])) {
      currentURLTags.each(function (_, tag) {
        if (parseInt($(tag).attr("data-utub-tag-id")) === currentURLTagIDs[i]) {
          $(tag).remove();
          return false;
        }
      });
    }
  }

  // Find tag IDs that are in new and not old and add them
  const urlTagContainer = urlCard.find(".urlTagsContainer");
  let tagToAdd;
  for (let i = 0; i < newUrl.utubUrlTagIDs.length; i++) {
    if (!currentURLTagIDs.includes(newUrl.utubUrlTagIDs[i])) {
      tagToAdd = updatedUTubTags.find(
        (tag) => tag.id === newUrl.utubUrlTagIDs[i],
      );
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
      parent.append(
        createURLBlock(dictURLs[i], dictTags).addClass(
          i % 2 === 0 ? "even" : "odd",
        ),
      );
    }

    // Show access all URLs button
    $("#accessAllURLsBtn").show();
    $("#NoURLsSubheader").hide();
    $("#urlBtnDeckCreate").hide();
  } else {
    $("#NoURLsSubheader").show();
    $("#urlBtnDeckCreate").show();
    $("#accessAllURLsBtn").hide();
  }
  setUTubNameAndDescription(UTubName);
}

// Create a URL block to add to current UTub/URLDeck
function createURLBlock(url, tagArray) {
  const urlCard = $(document.createElement("div"))
    .addClass("urlRow flex-column full-width pad-in-15p pointerable")
    .enableTab(); // Holds everything in the URL

  const urlTitleGoToURLWrap = $(document.createElement("div")).addClass(
    "flex-row full-width align-center justify-space-between",
  );

  // Append update URL title form if user can edit the URL
  url.canDelete
    ? urlTitleGoToURLWrap.append(
        createURLTitleAndUpdateBlock(url.urlTitle, urlCard),
      )
    : urlTitleGoToURLWrap.append(createURLTitle(url.urlTitle));

  urlTitleGoToURLWrap.append(createGoToURLIcon(url.urlString));

  urlCard.append(urlTitleGoToURLWrap).attr({
    urlID: url.utubUrlID,
    urlSelected: false,
    filterable: true,
  });

  // Append update URL form if user can edit the URL
  url.canDelete
    ? urlCard.append(createURLStringAndUpdateBlock(url.urlString, urlCard))
    : urlCard.append(createURLString(url.urlString));

  urlCard.append(createTagsAndOptionsForUrlBlock(url, tagArray, urlCard));

  setURLCardSelectionEventListener(urlCard);
  setFocusEventListenersOnURLCard(urlCard);

  return urlCard;
}

// Add focus and blur on URL card when tabbing through URLs
function setFocusEventListenersOnURLCard(urlCard) {
  const urlID = urlCard.attr("urlID");
  urlCard.offAndOn("focus.focusURLCard" + urlID, function () {
    urlCard.find(".goToUrlIcon").addClass("visible-on-focus");
    $(document).on("keyup.focusURLCard" + urlID, function (e) {
      if (e.which === 13) {
        selectURLCard(urlCard);
        urlCard.trigger("focusout");
      }
    });
  });

  urlCard.offAndOn("focusout.focusURLCard" + urlID, function (e) {
    const target = $(e.target);
    if (target.closest(".urlRow").is(urlCard)) {
      if (target.hasClass("goToUrlIcon")) {
        urlCard.find(".goToUrlIcon").removeClass("visible-on-focus");
      }
      $(document).off("keyup.focusURLCard" + urlID);
    }
  });
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
    .enableTab()
    .append(goToUrlInnerIconPath)
    .on("click", (e) => {
      e.stopPropagation();
      accessLink(urlString);
    })
    .on("focus", () => {
      $(document).on("keyup.accessURL", function (e) {
        if (e.which === 13) {
          accessLink(urlString);
          goToUrlOuterIconSvg.trigger("focus");
        }
      });
    })
    .on("blur", () => {
      $(document).off("keyup.accessURL");
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
    .addClass("urlString long-text-ellipsis tabbable")
    .attr({ "data-url": urlStringText })
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
    .append(createShowUpdateURLTitleIcon(urlCard));
  urlTitleAndShowUpdateIconWrap.append(urlTitleAndShowUpdateIconInnerWrap);

  // Add icon + title container, and update input container to the parent container
  urlTitleAndUpdateWrap
    .append(urlTitleAndShowUpdateIconWrap)
    .append(createUpdateURLTitleInput(urlTitleText, urlCard));

  return urlTitleAndUpdateWrap;
}

// Create the icon that will show the update URL title form
function createShowUpdateURLTitleIcon(urlCard) {
  return makeUpdateButton(20)
    .addClass("urlTitleBtnUpdate")
    .on("click.showUpdateURLTitle", function (e) {
      if ($(e.target).parents(".urlTitleAndUpdateIconWrap").length > 0) {
        const urlTitleAndIcon = $(e.target).closest(
          ".urlTitleAndUpdateIconWrap",
        );
        e.stopPropagation();
        showUpdateURLTitleForm(urlTitleAndIcon, urlCard);
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
  const urlTitleTextInput = urlTitleUpdateInputContainer.find("input");

  urlTitleTextInput
    .prop("minLength", CONSTANTS.URLS_TITLE_MIN_LENGTH)
    .prop("maxLength", CONSTANTS.URLS_TITLE_MAX_LENGTH)
    .val(urlTitleText);

  urlTitleTextInput.offAndOn("focus.updateURLTitleInputFocus", function () {
    $(document).on("keyup.updateURLTitleSubmitEscape", function (e) {
      switch (e.which) {
        case 13:
          updateURLTitle(urlTitleTextInput, urlCard);
          break;
        case 27:
          hideAndResetUpdateURLTitleForm(urlCard);
          break;
        default:
        /* no-op */
      }
    });
  });

  urlTitleTextInput.offAndOn("blur.updateURLTitleInputFocus", function () {
    $(document).off("keyup.updateURLTitleSubmitEscape");
  });

  // Update Url Title submit button
  const urlTitleSubmitBtnUpdate = makeSubmitButton(30).addClass(
    "urlTitleSubmitBtnUpdate",
  );

  urlTitleSubmitBtnUpdate
    .find(".submitButton")
    .on("click.updateUrlTitle", function (e) {
      if (
        $(e.target)
          .closest(".urlTitleSubmitBtnUpdate")
          .is(urlTitleSubmitBtnUpdate) &&
        $(e.target).closest(".urlRow").is(urlCard)
      )
        e.stopPropagation();
      updateURLTitle(urlTitleTextInput, urlCard);
    })
    .offAndOn("focus.submitUpdateUrlTitle", function () {
      $(document).on("keyup.submitUpdateUrlTitle", function (e) {
        if (e.which === 13) updateURLTitle(urlTitleTextInput, urlCard);
      });
    })
    .offAndOn("blur.submitUpdateUrlTitle", function () {
      $(document).off("keyup.submitUpdateUrlTitle");
    });

  // Update Url Title cancel button
  const urlTitleCancelBtnUpdate = makeCancelButton(30).addClass(
    "urlTitleCancelBtnUpdate tabbable",
  );

  urlTitleCancelBtnUpdate
    .find(".cancelButton")
    .on("click.updateUrlTitle", function (e) {
      if (
        $(e.target)
          .closest(".urlTitleCancelBtnUpdate")
          .is(urlTitleCancelBtnUpdate) &&
        $(e.target).closest(".urlRow").is(urlCard)
      )
        e.stopPropagation();
      hideAndResetUpdateURLTitleForm(urlCard);
    })
    .offAndOn("focus.cancelUpdateUrlTitle", function () {
      $(document).on("keyup.cancelUpdateUrlTitle", function (e) {
        if (e.which === 13) hideAndResetUpdateURLTitleForm(urlCard);
      });
    })
    .offAndOn("blur.cancelUpdateUrlTitle", function () {
      $(document).off("keyup.cancelUpdateUrlTitle");
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

  setFocusEventListenersOnUpdateURLStringInput(urlStringTextInput, urlCard);

  // Update Url Title submit button
  const urlStringSubmitBtnUpdate = makeSubmitButton(30).addClass(
    "urlStringSubmitBtnUpdate",
  );

  urlStringSubmitBtnUpdate
    .find(".submitButton")
    .on("click.updateUrlString", function () {
      updateURL(urlStringTextInput, urlCard);
    })
    .on("focus.updateUrlString", function () {
      $(document).on("keyup.updateUrlString", function (e) {
        if (e.which === 13) updateURL(urlStringTextInput, urlCard);
      });
    })
    .on("blur.updateUrlString", function () {
      $(document).off("keyup.updateUrlString");
    });

  // Update Url Title cancel button
  const urlStringCancelBtnUpdate = makeCancelButton(30).addClass(
    "urlStringCancelBtnUpdate",
  );

  urlStringCancelBtnUpdate
    .find(".cancelButton")
    .on("click.updateUrlString", function (e) {
      e.stopPropagation();
      hideAndResetUpdateURLStringForm(urlCard);
    })
    .offAndOn("focus.updateUrlString", function () {
      $(document).on("keyup.updateUrlString", function (e) {
        if (e.which === 13) hideAndResetUpdateURLStringForm(urlCard);
      });
    })
    .offAndOn("blur.updateUrlString", function () {
      $(document).off("keyup.updateUrlString");
    });

  urlStringUpdateTextInputContainer
    .append(urlStringSubmitBtnUpdate)
    .append(urlStringCancelBtnUpdate);

  return urlStringUpdateTextInputContainer;
}

function setFocusEventListenersOnUpdateURLStringInput(urlStringInput, urlCard) {
  urlStringInput.offAndOn("focus.updateURLStringFocus", function () {
    $(document).offAndOn("keyup.updateURLStringFocus", function (e) {
      switch (e.which) {
        case 13:
          // Handle enter key pressed
          updateURL(urlStringInput, urlCard);
          break;
        case 27:
          // Handle escape key pressed
          hideAndResetUpdateURLStringForm(urlCard);
          break;
        default:
        /* no-op */
      }
    });
  });

  urlStringInput.offAndOn("blur.updateURLStringFocus", function () {
    $(document).off("keyup.updateURLStringFocus");
  });
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
    url.utubUrlTagIDs,
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

  setFocusEventListenersOnCreateURLTagInput(urlTagTextInput, urlCard);

  // Create Url Title submit button
  const urlTagSubmitBtnCreate = makeSubmitButton(30).addClass(
    "urlTagSubmitBtnCreate",
  );

  urlTagSubmitBtnCreate
    .find(".submitButton")
    .on("click.createURLTag", function () {
      createURLTag(urlTagTextInput, urlCard);
    })
    .on("focus.createURLTag", function () {
      $(document).on("keyup.createURLTag", function (e) {
        if (e.which === 13) createURLTag(urlTagTextInput, urlCard);
      });
    })
    .on("blur.createURLTag", function () {
      $(document).off("keyup.createURLTag");
    });

  // Create Url Title cancel button
  const urlTagCancelBtnCreate = makeCancelButton(30).addClass(
    "urlTagCancelBtnCreate",
  );

  urlTagCancelBtnCreate
    .find(".cancelButton")
    .on("click.createURLTag", function (e) {
      e.stopPropagation();
      hideAndResetCreateURLTagForm(urlCard);
    })
    .offAndOn("focus.createURLTag", function () {
      $(document).on("keyup.createURLTag", function (e) {
        if (e.which === 13) hideAndResetCreateURLTagForm(urlCard);
      });
    })
    .offAndOn("blur.createURLTag", function () {
      $(document).off("keyup.createURLTag");
    });

  urlTagCreateTextInputContainer
    .append(urlTagSubmitBtnCreate)
    .append(urlTagCancelBtnCreate);

  return urlTagCreateTextInputContainer;
}

function setFocusEventListenersOnCreateURLTagInput(urlTagInput, urlCard) {
  urlTagInput.offAndOn("focus.createURLTagFocus", function () {
    $(document).offAndOn("keyup.createURLTagFocus", function (e) {
      switch (e.which) {
        case 13:
          // Handle enter key pressed
          createURLTag(urlTagInput, urlCard);
          break;
        case 27:
          // Handle escape key pressed
          hideAndResetCreateURLTagForm(urlCard);
          break;
        default:
        /* no-op */
      }
    });
  });

  urlTagInput.offAndOn("blur.createURLTagFocus", function () {
    $(document).off("keyup.createURLTagFocus");
  });
}

// Create all the buttons necessary for a url card
function createURLOptionsButtons(url, urlCard) {
  const urlOptions = $(document.createElement("div")).addClass(
    "urlOptions justify-content-start",
  );
  const urlBtnAccess = $(document.createElement("button"));
  const urlTagBtnCreate = $(document.createElement("button"));

  const accessAndTagBtns = $(document.createElement("div")).addClass(
    "urlOptionsInner flex-row justify-content-start gap-15p",
  );

  // Access the URL button
  urlBtnAccess
    .addClass("btn btn-primary urlBtnAccess tabbable")
    .attr({ type: "button" })
    .text("Access Link")
    .disableTab()
    .on("click", function (e) {
      e.stopPropagation();
      accessLink(url.urlString);
    });

  // Add a tag button
  urlTagBtnCreate
    .addClass("btn btn-info urlTagBtnCreate tabbable")
    .attr({ type: "button" })
    .text("Add Tag")
    .disableTab()
    .on("click", function (e) {
      e.stopPropagation();
      showCreateURLTagForm(urlCard, urlTagBtnCreate);
    })
    .on("focus", function (e) {
      if ($(e.target).hasClass("cancel")) return;
      $(document).on("keyup.showURLTagCreate", function (e) {
        if (e.which === 13) showCreateURLTagForm(urlCard, urlTagBtnCreate);
      });
    })
    .on("blur", function () {
      $(document).off("keyup.showURLTagCreate");
    });

  accessAndTagBtns.append(urlBtnAccess).append(urlTagBtnCreate);
  urlOptions.append(accessAndTagBtns);

  if (url.canDelete) {
    const urlStringBtnUpdate = $(document.createElement("button"));
    const urlBtnDelete = $(document.createElement("button"));
    const urlUpdateAndDeleteBtns = $(document.createElement("div")).addClass(
      "urlOptionsInner flex-row justify-content-start gap-15p",
    );
    urlBtnDelete
      .addClass("btn btn-danger urlBtnDelete tabbable")
      .attr({ type: "button" })
      .text("Delete")
      .disableTab()
      .on("click", function (e) {
        e.stopPropagation();
        deleteURLShowModal(url.utubUrlID, urlCard);
      });

    urlStringBtnUpdate
      .addClass("btn btn-light urlStringBtnUpdate tabbable")
      .attr({ type: "button" })
      .text("Edit URL")
      .disableTab()
      .on("click", function (e) {
        e.stopPropagation();
        showUpdateURLStringForm(urlCard, urlStringBtnUpdate);
      });

    urlUpdateAndDeleteBtns.append(urlStringBtnUpdate).append(urlBtnDelete);
    urlOptions.append(urlUpdateAndDeleteBtns);
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
    if ($(e.target).closest(urlBtnDelete).length > 0) createURLHideInput();
  });

  const inputArr = [createURLInput, createURLTitleInput];

  for (let i = 0; i < inputArr.length; i++) {
    $(inputArr[i]).on("focus.createURL", function () {
      bindCreateURLFocusEventListeners(createURLTitleInput, createURLInput);
    });

    $(inputArr[i]).on("blur.createURL", function () {
      unbindCreateURLFocusEventListeners();
    });
  }
}

function newURLInputRemoveEventListeners() {
  resetCreateURLFailErrors();
  $("#urlSubmitBtnCreate").off();
  $("#urlCancelBtnCreate").off();
  $(document).off(".createURL");
  $("#urlTitleCreate").off(".createURL");
  $("#urlStringCreate").off(".createURL");
}

// Handle URL deck display changes related to creating a new tag
function createTagBadgeInURL(utubTagID, tagString, urlCard) {
  const tagSpan = $(document.createElement("span"));
  const removeButton = $(document.createElement("div"));
  const tagText = $(document.createElement("span"))
    .addClass("tagText")
    .text(tagString);

  tagSpan
    .addClass(
      "tagBadge tagBadgeHoverable flex-row-reverse align-center justify-flex-end",
    )
    .attr({ "data-utub-tag-id": utubTagID });

  removeButton
    .addClass("urlTagBtnDelete flex-row align-center pointerable tabbable")
    .on("click", function (e) {
      e.stopPropagation();
      deleteURLTag(utubTagID, tagSpan, urlCard);
    })
    .offAndOn("focus.removeURLTag", function () {
      $(document).on("keyup.removeURLTag", function (e) {
        if (e.which === 13) deleteURLTag(utubTagID, tagSpan, urlCard);
      });
    })
    .offAndOn("blur.removeURLTag", function () {
      $(document).off("keyup.removeURLTag");
    });

  removeButton.append(createTagDeleteIcon());

  $(tagSpan).append(removeButton).append(tagText);

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

/** URL Display State Functions **/

// Display state 0: Clean slate, no UTub selected
function setURLDeckWhenNoUTubSelected() {
  $("#URLDeckHeader").text("URLs");
  $(".updateUTubBtn").hide();
  $("#urlBtnCreate").hide();
  $("#accessAllURLsBtn").hide();
  $("#URLDeckSubheaderCreateDescription").hide();
  $("#utubNameBtnUpdate").hide();
  $("#updateUTubDescriptionBtn").removeClass("visibleBtn");

  const URLDeckSubheader = $("#URLDeckSubheader");
  URLDeckSubheader.text("Select a UTub");
  URLDeckSubheader.show();

  // Prevent on-hover of URL Deck Header to show update UTub name button in case of back button
  $("#utubNameBtnUpdate").removeClass("visibleBtn");
}

// Display state 1: UTub selected, URL list and subheader prompt
function setUTubNameAndDescription(UTubName) {
  $("#URLDeckHeader").text(UTubName);
  $("#utubNameUpdate").val(UTubName);
  updateUTubNameHideInput();
}
