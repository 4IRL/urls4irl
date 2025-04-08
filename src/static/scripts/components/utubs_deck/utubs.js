"use strict";

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
  removeEventListenersForShowCreateUTubDescIfEmptyDesc();
  if (utubDescription) {
    utubDescriptionHeader.text(utubDescription);
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
  getSelectedUTubInfo(selectedUTubID);
}

function getSelectedUTubInfo(selectedUTubID) {
  getUTubInfo(selectedUTubID).then(
    (selectedUTub) => {
      buildSelectedUTub(selectedUTub);
      // If mobile, go straight to URL deck
      if (isMobile()) {
        setMobileUIWhenUTubSelectedOrURLNavSelected();
      }
    },
    () => {
      window.location.assign(routes.errorPage);
    },
  );
}

// Creates UTub radio button that changes URLDeck display to show contents of the selected UTub
function createUTubSelector(utubName, utubID, memberRole, index) {
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

  // TODO: Add icon based on memberRole here

  return utubSelector;
}

function setUTubSelectorEventListeners(utub) {
  const utubSelector = $(utub);
  const utubID = utubSelector.attr("utubid");
  utubSelector
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
    });
}

function makeUTubSelectableAgainIfMobile(utub) {
  $(utub).offAndOn("click.selectUTubMobile", function (e) {
    e.stopPropagation();
    e.preventDefault();
    getSelectedUTubInfo($(this).attr("utubid"));
    $(this).off("click.selectUTubMobile");
  });
}
