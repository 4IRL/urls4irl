"use strict";

// Streamline the AJAX call to db for updated info
function getUTubInfo(selectedUTubID) {
  const timeoutID = showUTubLoadingIconAndSetTimeout();
  return $.getJSON(APP_CONFIG.routes.getUTub(selectedUTubID))
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
  const currentUserID = selectedUTub.currentUser;

  const isUTubHistoryNull = window.history.state === null;

  // Allow user to back and forth in browser based on given UTub selection
  if (
    isUTubHistoryNull ||
    JSON.stringify(window.history.state.UTubID) !==
      JSON.stringify(selectedUTub.id)
  ) {
    // Push UTub state to browser history if no history, or if previous UTub history is different
    const utubid_key = APP_CONFIG.strings.UTUB_QUERY_PARAM;
    window.history.pushState(
      { UTubID: selectedUTub.id },
      "",
      `/home?${utubid_key}=${selectedUTub.id}`,
    );

    sessionStorage.setItem("fullyLoaded", "true");
  }

  // LH panels
  // UTub deck
  setUTubDeckOnUTubSelected(selectedUTub.id, isCurrentUserOwner);

  // Tag deck
  setTagDeckOnUTubSelected(dictTags, selectedUTub.id);

  // Center panel
  // URL deck
  setURLDeckOnUTubSelected(selectedUTub.id, utubName, dictURLs, dictTags);

  // UTub Description
  const utubDescriptionHeader = $("#URLDeckSubheader");
  removeEventListenersForShowCreateUTubDescIfEmptyDesc();
  if (utubDescription) {
    utubDescriptionHeader.text(utubDescription);
    $("#URLDeckHeaderWrap > .dynamic-subheader").addClass("height-2p5rem");
  } else {
    isCurrentUserOwner
      ? allowHoverOnUTubTitleToCreateDescriptionIfDescEmpty(selectedUTub.id)
      : null;
    utubDescriptionHeader.text(null);
    $("#URLDeckHeaderWrap > .dynamic-subheader").removeClass("height-2p5rem");
  }

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

  // Members deck
  setMemberDeckOnUTubSelected(
    dictMembers,
    utubOwnerID,
    isCurrentUserOwner,
    currentUserID,
    selectedUTub.id,
  );
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
      window.location.assign(APP_CONFIG.routes.errorPage);
    },
  );
}

// Creates UTub radio button that changes URLDeck display to show contents of the selected UTub
function createUTubSelector(utubName, utubID, memberRole, index) {
  const utubSelector = $(document.createElement("span"));
  const utubSelectorText = $(document.createElement("b"));

  utubSelectorText.addClass("UTubName").text(utubName);

  utubSelector
    .addClass("UTubSelector flex-row jc-sb align-center")
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
        if (e.key === KEYS.ENTER) selectUTub(utubID, utubSelector);
      });
    })
    .offAndOn("blur.selectUTub", function () {
      $(document).off("keyup.selectUTub");
    })
    .append(utubSelectorText)
    .append(makeUTubRoleIcon(memberRole));

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
        if (e.key === KEYS.ENTER) selectUTub(utubID, utubSelector);
      });
    })
    .offAndOn("blur.selectUTub", function () {
      $(document).off("keyup.selectUTub");
    });
}

function makeUTubRoleIcon(memberRole) {
  let icon = "";

  switch (memberRole) {
    case `${APP_CONFIG.constants.MEMBER_ROLES.CREATOR}`:
      icon += `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-diamond-fill memberRole" viewBox="0 0 16 16">`;
      icon += `<path fill-rule="evenodd" d="M6.95.435c.58-.58 1.52-.58 2.1 0l6.515 6.516c.58.58.58 1.519 0 2.098L9.05 15.565c-.58.58-1.519.58-2.098 0L.435 9.05a1.48 1.48 0 0 1 0-2.098z"/>`;

      break;
    case `${APP_CONFIG.constants.MEMBER_ROLES.CO_CREATOR}`:
      icon += `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-diamond-half memberRole" viewBox="0 0 16 16">`;
      icon += `<path d="M9.05.435c-.58-.58-1.52-.58-2.1 0L.436 6.95c-.58.58-.58 1.519 0 2.098l6.516 6.516c.58.58 1.519.58 2.098 0l6.516-6.516c.58-.58.58-1.519 0-2.098zM8 .989c.127 0 .253.049.35.145l6.516 6.516a.495.495 0 0 1 0 .7L8.35 14.866a.5.5 0 0 1-.35.145z"/>`;

      break;
    default:
      icon += `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-people-fill memberRole" viewBox="0 0 16 16">`;
      icon += `<path d="M7 14s-1 0-1-1 1-4 5-4 5 3 5 4-1 1-1 1zm4-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6m-5.784 6A2.24 2.24 0 0 1 5 13c0-1.355.68-2.75 1.936-3.72A6.3 6.3 0 0 0 5 9c-4 0-5 3-5 4s1 1 1 1zM4.5 8a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5"/>`;
  }

  icon += `</svg>`;

  return icon;
}

function makeUTubSelectableAgainIfMobile(utub) {
  $(utub).offAndOn("click.selectUTubMobile", function (e) {
    e.stopPropagation();
    e.preventDefault();
    getSelectedUTubInfo($(this).attr("utubid"));
    $(this).off("click.selectUTubMobile");
  });
}
