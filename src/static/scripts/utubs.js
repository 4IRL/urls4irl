/** UTub UI Interactions **/

$(document).ready(function () {
  $("#logout").on("click", () => window.location.assign(routes.logout));
  $(".home#toMembers").on("click", () => {
    setMobileUIWhenMemberDeckSelected();
  });
  $(".home#toURLs").on("click", () => {
    setMobileUIWhenUTubSelectedOrURLNavSelected();
  });
  $(".home#toUTubs").on("click", () => {
    setMobileUIWhenUTubDeckSelected();
  });

  $(".home#toTags").on("click", () => {
    setMobileUIWhenTagDeckSelected();
  });

  const timeoutID = showUTubLoadingIconAndSetTimeout();
  setUIWhenNoUTubSelected();
  // Instantiate UTubDeck with user's accessible UTubs
  try {
    buildUTubDeck(UTubs, timeoutID);
  } catch (error) {
    console.log("Something is wrong!");
    console.log(error);
  }

  let width;
  // Use matchMedia instead of resize when just need to determine if > or < than
  // specific size
  // https://webdevetc.com/blog/matchmedia-events-for-window-resizes/
  const query = matchMedia("(max-width: " + TABLET_WIDTH + "px)");
  query.addEventListener("change", function () {
    width = $(window).width();

    // Handle size changes when tablet or smaller
    if (width < TABLET_WIDTH) {
      // If UTub selected, show URL Deck
      // If no UTub selected, show UTub deck
      // Set tablet-mobile navbar depending on UTub selected or not
      if (!isNaN(getActiveUTubID())) {
        setMobileUIWhenUTubSelectedOrURLNavSelected();
      } else {
        setMobileUIWhenUTubNotSelectedOrUTubDeleted();
      }
    } else {
      // Set full screen navbar
      // Show all panels and decks
      revertMobileUIToFullScreenUI();
    }
  });
});

window.addEventListener("popstate", function (e) {
  if (e.state && e.state.hasOwnProperty("UTubID")) {
    if (!isUtubIdValidFromStateAccess(e.state.UTubID)) {
      // Handle when a user previously went back to a now deleted UTub
      window.history.replaceState(null, null, "/home");
      resetHomePageToInitialState();
      return;
    }

    // State will contain property UTub if URL contains query parameter UTubID
    getUTubInfo(e.state.UTubID).then(
      (selectedUTub) => {
        buildSelectedUTub(selectedUTub);
        // If mobile, go straight to URL deck
        if ($(window).width() < TABLET_WIDTH) {
          setMobileUIWhenUTubSelectedOrURLNavSelected();
        }
      },
      () => {
        resetHomePageToInitialState();
      },
    );
  } else {
    // If does not contain query parameter, user is at /home - then update UTub titles/IDs
    resetHomePageToInitialState();
  }
});

window.addEventListener("pageshow", function (e) {
  if (!this.sessionStorage.getItem("fullyLoaded")) {
    setUIWhenNoUTubSelected();
    getAllUTubs().then((utubData) => {
      buildUTubDeck(utubData);
      setMemberDeckWhenNoUTubSelected();
      setTagDeckSubheaderWhenNoUTubSelected();
    });
  }

  if (history.state && history.state.UTubID) {
    getUTubInfo(history.state.UTubID).then(
      (selectedUTub) => {
        buildSelectedUTub(selectedUTub);
        // If mobile, go straight to URL deck
        if ($(window).width() < TABLET_WIDTH) {
          setMobileUIWhenUTubSelectedOrURLNavSelected();
        }
        return;
      },
      () => {
        // Do nothing in error, as an invalid UTubID should indicate deleted UTub
      },
    );
    return;
  }

  // If a cold start, user might've been using URL with ID in it
  // First pull the query parameter
  // Then pull the UTub ID from the global UTubs variable and match
  // Handle if it doesn't exist
  const searchParams = new URLSearchParams(window.location.search);
  if (searchParams.size === 0) return;

  const utubId = searchParams.get(STRINGS.UTUB_QUERY_PARAM);
  console.log(`utub id is: ${utubId}`);
  if (searchParams.size > 1 || utubId === null) {
    window.location.assign(routes.errorPage);
  }

  if (!isValidUTubID(utubId)) window.location.assign(routes.errorPage);

  if (!isUtubIdValidOnPageLoad(parseInt(utubId))) {
    window.history.replaceState(null, null, "/home");
    window.location.assign(routes.errorPage);
  }

  getUTubInfo(parseInt(utubId)).then(
    (selectedUTub) => {
      buildSelectedUTub(selectedUTub);
      // If mobile, go straight to URL deck
      if ($(window).width() < TABLET_WIDTH) {
        setMobileUIWhenUTubSelectedOrURLNavSelected();
      }
    },
    () => {
      window.location.assign(routes.errorPage);
    },
  );
});

/** UTub Utility Functions **/
// Verify UTubID is valid
function isValidUTubID(utubIdStr) {
  const utubId = parseInt(utubIdStr);
  const isANumber = !isNaN(utubId);
  const isPositive = utubId > 0;
  const isValidIntegerFormat = String(utubId) === utubIdStr;

  return isANumber && isPositive && isValidIntegerFormat;
}

// Parses inserted UTubs constant for ID's
function isUtubIdValidOnPageLoad(utubId) {
  let utub;
  for (i = 0; i < UTubs.length; i++) {
    utub = UTubs[i];

    if (utubId === utub.id) {
      return true;
    }
  }
  return false;
}

function isUtubIdValidFromStateAccess(utubId) {
  return $(`.UTubSelector[utubid='${utubId}']`).length === 1;
}

// Function to count number of UTubs current user has access to
function getNumOfUTubs() {
  return $("#listUTubs > .UTubSelector").length;
}

// Streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function getActiveUTubID() {
  return parseInt($(".UTubSelector.active").attr("utubid"));
}

// Streamline the jQuery selector for the UTub Selector.
function getUTubSelectorElemFromID(id) {
  return $(".UTubSelector[utubid='" + id + "']");
}

// Streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function getUTubIDFromName(name) {
  const utubNames = $(".UTubName");
  let utub;

  for (i = 0; i < utubNames.length; i++) {
    utub = $(utubNames[i]);

    if (utub.text() === name) {
      return parseInt(utub.closest(".UTubSelector").attr("utubid"));
    }
  }

  return -1;
}

// Streamline the jQuery selector extraction of UTub name.
function getCurrentUTubName() {
  return $(".UTubSelector.active").text();
}

// Quickly extracts all UTub names from #listUTubs and returns an array.
function getAllAccessibleUTubNames() {
  let utubNames = [];
  const utubSelectorNames = $(".UTubName");
  utubSelectorNames.map((i) => utubNames.push($(utubSelectorNames[i]).text()));
  return utubNames;
}

// Streamline the AJAX call to db for updated info
function getUTubInfo(selectedUTubID) {
  const timeoutID = showUTubLoadingIconAndSetTimeout();
  return $.getJSON(routes.getUTub(selectedUTubID))
    .fail(function () {
      window.history.replaceState(null, null, "/home");
    })
    .always(function () {
      hideUTubLoadingIconAndClearTimeout(timeoutID);
    });
}

// Utility route to get all UTub summaries
function getAllUTubs() {
  const timeoutID = showUTubLoadingIconAndSetTimeout();
  return $.getJSON(routes.getUTubs).always(function () {
    hideUTubLoadingIconAndClearTimeout(timeoutID);
  });
}

// Utility function to show a loading icon when loading UTubs
function showUTubLoadingIconAndSetTimeout() {
  return setTimeout(function () {
    $("#UTubSelectDualLoadingRing").addClass("dual-loading-ring");
  }, SHOW_LOADING_ICON_AFTER_MS);
}

function hideUTubLoadingIconAndClearTimeout(timeoutID) {
  clearTimeout(timeoutID);
  $("#UTubSelectDualLoadingRing").removeClass("dual-loading-ring");
}

// Set event listeners for add and delete UTubs
function setCreateDeleteUTubEventListeners() {
  const utubBtnCreate = $("#utubBtnCreate");
  const utubBtnDelete = $("#utubBtnDelete");

  // Create new UTub
  utubBtnCreate.offAndOn("click.createDeleteUTub", function () {
    createUTubShowInput();
  });

  // Allows user to press enter to bring up form while focusing on the add UTub icon, esp after tabbing
  utubBtnCreate.offAndOn("focus.createDeleteUTub", function () {
    $(document).offAndOn("keyup.createDeleteUTub", function (e) {
      if (e.which === 13) {
        e.stopPropagation();
        createUTubShowInput();
      }
    });
  });

  // Removes the keyup listener from the document once the button is blurred
  utubBtnCreate.offAndOn("blur.createDeleteUTub", function () {
    $(document).off("keyup.createDeleteUTub");
  });

  // Delete UTub
  utubBtnDelete.offAndOn("click.createDeleteUTub", function () {
    deleteUTubShowModal();
  });

  // Allows user to press enter to bring up form while focusing on the delete UTub icon, esp after tabbing
  utubBtnDelete.offAndOn("focus.createDeleteUTub", function () {
    $(document).offAndOn("keyup.createDeleteUTub", function (e) {
      if (e.which === 13) {
        e.stopPropagation();
        deleteUTubShowModal();
      }
    });
  });

  // Removes the keyup listener from the document once the button is blurred
  utubBtnDelete.offAndOn("blur.createDeleteUTub", function () {
    $(document).off("keyup.createDeleteUTub");
  });
}

// Remove event listeners for add and delete UTubs
function removeCreateDeleteUTubEventListeners() {
  $(document).off(".createDeleteUTub");
}

// Clear the UTub Deck
function resetUTubDeck() {
  $("#listUTubs").empty();
  hideIfShown($("#utubBtnDelete"));
}

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubName() {
  // Allow user to still click in the text box
  $("#utubNameUpdate")
    .offAndOn("click.updateUTubname", function (e) {
      e.stopPropagation();
    })
    .offAndOn("focus.updateUTubname", function () {
      $(document).on("keyup.updateUTubname", function (e) {
        switch (e.which) {
          case 13:
            // Handle enter key pressed
            // Skip if update is identical
            if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
              updateUTubNameHideInput();
              return;
            }
            checkSameNameUTub(false, $("#utubNameUpdate").val());
            break;
          case 27:
            // Handle escape key pressed
            updateUTubNameHideInput();
            break;
          default:
          /* no-op */
        }
      });
    })
    .offAndOn("blur.updateUTubname", function () {
      $(document).off("keyup.updateUTubname");
    });

  // Bind clicking outside the window
  $(window).offAndOn("click.updateUTubname", function () {
    // Hide UTub name update fields
    updateUTubNameHideInput();
  });
}

function removeEventListenersToEscapeUpdateUTubName() {
  $(window).off(".updateUTubname");
  $(document).off(".updateUTubname");
}

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubDescription() {
  // Allow user to still click in the text box
  $("#utubDescriptionUpdate")
    .on("click.updateUTubDescription", function (e) {
      e.stopPropagation();
    })
    .offAndOn("focus.updateUTubDescription", function () {
      $(document).on("keyup.updateUTubDescription", function (e) {
        switch (e.which) {
          case 13:
            // Handle enter key pressed
            updateUTubDescription();
            break;
          case 27:
            // Handle escape key pressed
            updateUTubDescriptionHideInput();
            break;
          default:
          /* no-op */
        }
      });
    })
    .on("blur.updateUTubDescription", function () {
      $(document).off("keyup.updateUTubDescription");
    });

  // Bind clicking outside the window
  $(window).offAndOn("click.updateUTubDescription", function (e) {
    // Hide UTub description update fields
    updateUTubDescriptionHideInput();
  });
}

function removeEventListenersToEscapeUpdateUTubDescription() {
  $(window).off(".updateUTubDescription");
  $(document).off(".updateUTubDescription");
}

function allowUserToCreateDescriptionIfEmptyOnTitleUpdate() {
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  showIfHidden(clickToCreateDesc);
  clickToCreateDesc.offAndOn("click.createUTubdescription", function (e) {
    e.stopPropagation();
    hideIfShown(clickToCreateDesc);
    updateUTubNameHideInput();
    updateUTubDescriptionShowInput();
    clickToCreateDesc.off("click.createUTubdescription");
  });
}

function allowHoverOnUTubTitleToCreateDescriptionIfDescEmpty() {
  const utubTitle = $("#URLDeckHeader");
  utubTitle.offAndOn("mouseenter.createUTubdescription", function () {
    const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
    showIfHidden(clickToCreateDesc);
    clickToCreateDesc.offAndOn("click.createUTubdescription", function (e) {
      e.stopPropagation();
      hideIfShown(clickToCreateDesc);
      updateUTubDescriptionShowInput();
      clickToCreateDesc.off("click.createUTubdescription");
    });
    hideCreateUTubDescriptionButtonOnMouseExit();
  });
}

function hideCreateUTubDescriptionButtonOnMouseExit() {
  const urlHeaderWrap = $("#URLDeckHeaderWrap");
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  urlHeaderWrap.offAndOn("mouseleave.createUTubdescription", function () {
    if (!isHidden($(clickToCreateDesc))) {
      hideIfShown(clickToCreateDesc);
      clickToCreateDesc.off("click.createUTubdescription");
      urlHeaderWrap.off("mouseleave.createUTubdescription");
    }
  });
}

function removeEventListenersForShowCreateUTubDescIfEmptyDesc() {
  const utubTitle = $("#URLDeckHeader");
  utubTitle.off("mouseenter.createUTubdescription");
  const urlHeaderWrap = $("#URLDeckHeaderWrap");
  urlHeaderWrap.off("mouseleave.createUTubdescription");
}

/** UTub Functions **/

// Assembles components of the UTubDeck (top left panel)
function buildUTubDeck(utubs, timeoutID) {
  resetUTubDeck();
  const parent = $("#listUTubs");
  const numOfUTubs = utubs.length;

  if (numOfUTubs !== 0) {
    // Instantiate deck with list of UTubs accessible to current user
    for (let i = 0; i < numOfUTubs; i++) {
      parent.append(createUTubSelector(utubs[i].name, utubs[i].id, i));
    }

    hideInputsAndSetUTubDeckSubheader();
    setURLDeckWhenNoUTubSelected();
  } else {
    resetUTubDeckIfNoUTubs();
  }

  if (timeoutID) hideUTubLoadingIconAndClearTimeout(timeoutID);
}

function buildSelectedUTub(selectedUTub) {
  // Parse incoming data, pass them into subsequent functions as required
  const utubName = selectedUTub.name;
  const dictURLs = selectedUTub.urls;
  const dictTags = selectedUTub.tags;
  const dictMembers = selectedUTub.members;
  const utubOwnerID = selectedUTub.createdByUserID;
  const utubDescription = selectedUTub.description;
  const isCurrentUserOwner = selectedUTub.isCreator;

  const isUTubHistoryNull = window.history.state === null;

  // Allow user to back and forth in browser based on given UTub selection
  if (
    isUTubHistoryNull ||
    JSON.stringify(window.history.state.UTubID) !==
      JSON.stringify(selectedUTub.id)
  ) {
    // Push UTub state to browser history if no history, or if previous UTub history is different
    const utubid_key = STRINGS.UTUB_QUERY_PARAM;
    window.history.pushState(
      { UTubID: selectedUTub.id },
      "",
      `/home?${utubid_key}=${selectedUTub.id}`,
    );

    sessionStorage.setItem("fullyLoaded", "true");
  }

  // LH panels
  // UTub deck
  setUTubDeckOnUTubSelected(selectedUTub.id, utubOwnerID);

  // Tag deck
  buildTagDeck(dictTags);

  // Center panel
  // URL deck
  buildURLDeck(utubName, dictURLs, dictTags);

  // UTub Description
  const utubDescriptionHeader = $("#URLDeckSubheader");
  if (utubDescription) {
    utubDescriptionHeader.text(utubDescription);
    removeEventListenersForShowCreateUTubDescIfEmptyDesc();
  } else {
    isCurrentUserOwner
      ? allowHoverOnUTubTitleToCreateDescriptionIfDescEmpty()
      : null;
    utubDescriptionHeader.text(null);
  }

  // Members deck
  buildMemberDeck(dictMembers, utubOwnerID, isCurrentUserOwner);

  // Only allow owner to update UTub name and description
  if (isCurrentUserOwner) {
    $("#utubNameBtnUpdate").removeClass("hiddenBtn").addClass("visibleBtn");
    $("#updateUTubDescriptionBtn")
      .removeClass("hiddenBtn")
      .addClass("visibleBtn");

    // Setup description update field to match the current header
    $("#utubDescriptionUpdate").val($("#URLDeckSubheader").text());
  } else {
    $("#utubNameBtnUpdate").addClass("hiddenBtn").removeClass("visibleBtn");
    $("#updateUTubDescriptionBtn")
      .addClass("hiddenBtn")
      .removeClass("visibleBtn");
  }
}

// Handles progagating changes across page related to a UTub selection
function selectUTub(selectedUTubID, utubSelector) {
  const currentlySelected = $(".UTubSelector.active");

  // Avoid reselecting if choosing the same UTub selector
  if (currentlySelected.is($(utubSelector))) return;

  currentlySelected.removeClass("active");
  utubSelector.addClass("active");

  getUTubInfo(selectedUTubID).then(
    (selectedUTub) => {
      buildSelectedUTub(selectedUTub);
      // If mobile, go straight to URL deck
      if ($(window).width() < TABLET_WIDTH) {
        setMobileUIWhenUTubSelectedOrURLNavSelected();
      }
    },
    () => {
      window.location.assign(routes.errorPage);
    },
  );
}

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
  updateTagDeck(utubTags);

  // Update URLs
  const utubURLs = utub.urls;
  updateURLDeck(utubURLs, utubTags);

  // Update members
  const utubMembers = utub.members;
  const utubOwnerID = utub.createdByUserID;
  const isCurrentUserOwner = utub.isCreator;
  updateMemberDeck(utubMembers, utubOwnerID, isCurrentUserOwner);

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

// Creates UTub radio button that changes URLDeck display to show contents of the selected UTub
function createUTubSelector(utubName, utubID, index) {
  const utubSelector = $(document.createElement("span"));
  const utubSelectorText = $(document.createElement("b"));

  utubSelectorText.addClass("UTubName").text(utubName);

  utubSelector
    .addClass("UTubSelector")
    .attr({
      utubid: utubID,
      position: index,
      tabindex: 0,
    })
    // Bind display state change function on click
    .on("click.selectUTub", function (e) {
      e.stopPropagation();
      e.preventDefault();
      selectUTub(utubID, utubSelector);
    })
    .offAndOn("focus.selectUTub", function () {
      $(document).on("keyup.selectUTub", function (e) {
        if (e.which === 13) selectUTub(utubID, utubSelector);
      });
    })
    .offAndOn("blur.selectUTub", function () {
      $(document).off("keyup.selectUTub");
    })
    .append(utubSelectorText);

  return utubSelector;
}

// Attaches appropriate event listeners to the add UTub and cancel add UTub buttons
function createNewUTubEventListeners() {
  const utubSubmitBtnCreate = $("#utubSubmitBtnCreate");
  const utubCancelBtnCreate = $("#utubCancelBtnCreate");
  utubSubmitBtnCreate.offAndOn("click.createUTub", function (e) {
    if ($(e.target).closest("#utubSubmitBtnCreate").length > 0)
      checkSameNameUTub(true, $("#utubNameCreate").val());
  });

  utubCancelBtnCreate.offAndOn("click.createUTub", function (e) {
    if ($(e.target).closest("#utubCancelBtnCreate").length > 0)
      createUTubHideInput();
  });

  utubSubmitBtnCreate.offAndOn("focus.createUTub", function () {
    $(document).offAndOn("keyup.createUTubSubmit", function (e) {
      if (e.which === 13) checkSameNameUTub(true, $("#utubNameCreate").val());
    });
  });

  utubSubmitBtnCreate.offAndOn("blur.createUTub", function () {
    $(document).off("keyup.createUTubSubmit");
  });

  utubCancelBtnCreate.offAndOn("focus.createUTub", function () {
    $(document).offAndOn("keyup.createUTubCancel", function (e) {
      if (e.which === 13) createUTubHideInput();
    });
  });

  utubCancelBtnCreate.on("blur.createUTub", function () {
    $(document).off("keyup.createUTubCancel");
  });

  const utubNameInput = $("#utubNameCreate");
  const utubDescriptionInput = $("#utubDescriptionCreate");

  utubNameInput.on("focus.createUTub", function () {
    $(document).on("keyup.createUTubName", function (e) {
      handleOnFocusEventListenersForCreateUTub(e);
    });
  });

  utubNameInput.on("blur.createUTub", function () {
    $(document).off(".createUTubName");
  });

  utubDescriptionInput.on("focus.createUTub", function () {
    $(document).on("keyup.createUTubDescription", function (e) {
      handleOnFocusEventListenersForCreateUTub(e);
    });
  });

  utubDescriptionInput.on("blur.createUTub", function () {
    $(document).off(".createUTubDescription");
  });
}

function removeNewUTubEventListeners() {
  $(document).off("keyup.createUTubName");
  $(document).off("keyup.createUTubDescription");
  $(document).off("keyup.createUTubCancel");
  $(document).off("keyup.createUTubSubmit");
  $("#utubNameCreate").off(".createUTub");
  $("#utubDescriptionCreate").off(".createUTub");
  $("#utubSubmitBtnCreate").off(".createUTub");
  $("#utubCancelBtnCreate").off(".createUTub");
}

function handleOnFocusEventListenersForCreateUTub(e) {
  switch (e.which) {
    case 13:
      // Handle enter key pressed
      checkSameNameUTub(true, $("#utubNameCreate").val());
      break;
    case 27:
      // Handle escape key pressed
      $("#utubNameCreate").trigger("blur");
      $("#utubDescriptionCreate").trigger("blur");
      createUTubHideInput();
      break;
    default:
    /* no-op */
  }
}

/** UTub Display State Functions **/

// Display state 0: Clean slate, no UTubs
function resetUTubDeckIfNoUTubs() {
  // Subheader to prompt user to create a UTub shown
  $("#UTubDeckSubheader").text("Create a UTub");

  // Hide delete UTub button
  hideIfShown($("#utubBtnDelete"));
}

// Display state 1: UTubs list, none selected. selectedUTubID, UTubOwnerID == null
// Enter into this state only at page load, or after UTub deletion
function hideInputsAndSetUTubDeckSubheader() {
  hideInputs();
  const numOfUTubs = getNumOfUTubs();
  const subheaderText =
    numOfUTubs > 1 ? numOfUTubs + " UTubs" : numOfUTubs + " UTub";

  // Subheader to tell user how many UTubs are accessible
  $("#UTubDeckSubheader").text(subheaderText);
}

// Display state 2: UTubs list, 1x selected
// Enter into this state change only if new UTub is selected
// No actions performed within other decks can affect UTub Deck display
function setUTubDeckOnUTubSelected(selectedUTubID, UTubOwnerUserID) {
  hideInputsAndSetUTubDeckSubheader();

  if (getCurrentUserID() === UTubOwnerUserID) {
    $("#utubBtnDelete").show();
  } else hideIfShown($("#utubBtnDelete"));

  const utubSelector = $(`.UTubSelector[utubid=${selectedUTubID}]`);

  if (!utubSelector.hasClass("active")) {
    // Remove all other active UTub selectors first
    $(".UTubSelector.active").removeClass("active").removeClass("focus");

    $(".UTubSelector:focus").blur();

    utubSelector.addClass("active");
  }
}

/** Post data handling **/

// Checks if submitted UTub name exists in db. mode is 0 for updateUTub, 1 for createUTub
function checkSameNameUTub(isCreatingUTub, name) {
  if (getAllAccessibleUTubNames().includes(name)) {
    // UTub with same name exists. Confirm action with user
    isCreatingUTub
      ? sameUTubNameOnNewUTubWarningShowModal()
      : sameUTubNameOnUpdateUTubNameWarningShowModal();
  } else {
    // UTub name is unique. Proceed with requested action
    isCreatingUTub ? createUTub() : updateUTubName();
  }
}

// Hides modal for UTub same name action confirmation
function sameNameWarningHideModal() {
  $("#confirmModal").modal("hide");
}

// Handles a double check if user inputs a new UTub name similar to one already existing. mode true 'add', mode false 'update'
function sameUTubNameOnNewUTubWarningShowModal() {
  const modalTitle = "Create a new UTub with this name?";
  const modalBody = "You already have a UTub with a similar name.";
  const buttonTextDismiss = "Go Back to Editing";
  const buttonTextSubmit = "Create";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .text(buttonTextDismiss)
    .offAndOn("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      sameNameWarningHideModal();
      highlightInput($("#utubNameCreate"));
    });

  hideIfShown($("#modalRedirect"));
  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .offAndOn("click", function (e) {
      e.preventDefault();
      createUTub();
      $("#utubNameCreate").val(null);
      $("#utubDescriptionCreate").val(null);
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    // Refocus on the name's input box
    highlightInput($("#utubNameCreate"));
  });
}

function sameUTubNameOnUpdateUTubNameWarningShowModal() {
  const modalTitle = "Continue with this UTub name?";
  const modalBody = "You are a member of a UTub with an identical name.";
  const buttonTextDismiss = "Go Back to Editing";
  const buttonTextSubmit = "Edit Name";

  removeEventListenersToEscapeUpdateUTubName();

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .text(buttonTextDismiss)
    .offAndOn("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      sameNameWarningHideModal();
      highlightInput($("#utubNameUpdate"));
      setEventListenersToEscapeUpdateUTubName();
    });

  hideIfShown($("#modalRedirect"));
  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .offAndOn("click", function (e) {
      e.preventDefault();
      updateUTubName();
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    e.stopPropagation();
    setEventListenersToEscapeUpdateUTubName();
  });
}
