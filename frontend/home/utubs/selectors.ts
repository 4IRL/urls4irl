import type { SuccessResponse } from "../../types/api-helpers.d.ts";
import type { UtubDetail } from "../../types/utub.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { setState } from "../../store/app-store.js";
import { KEYS } from "../../lib/constants.js";
import { showNewPageOnAJAXHTMLResponse } from "../../lib/page-utils.js";
import { emit, AppEvents } from "../../lib/event-bus.js";
import {
  showUTubLoadingIconAndSetTimeout,
  hideUTubLoadingIconAndClearTimeout,
  setUTubDeckOnUTubSelected,
} from "./deck.js";
import {
  removeEventListenersForShowCreateUTubDescIfEmptyDesc,
  showCreateDescriptionButtonAlways,
} from "../urls/update-description.js";

type GetSingleUtubResponse = SuccessResponse<"getSingleUtub">;

// Streamline the AJAX call to db for updated info
export function getUTubInfo(
  selectedUTubID: number,
): JQuery.Promise<UtubDetail | null> {
  const timeoutID = showUTubLoadingIconAndSetTimeout();
  const deferred = $.Deferred<UtubDetail | null>();

  $.getJSON(APP_CONFIG.routes.getUTub(selectedUTubID))
    .done((data: GetSingleUtubResponse) => {
      deferred.resolve(data);
    })
    .fail((xhr: JQuery.jqXHR) => {
      switch (xhr.status) {
        case 429: {
          showNewPageOnAJAXHTMLResponse(xhr.responseText);
          deferred.resolve(null);
          return;
        }
        default: {
          window.history.replaceState(null, "", "/home");
          deferred.reject(xhr);
        }
      }
    })
    .always(() => {
      hideUTubLoadingIconAndClearTimeout(timeoutID);
    });
  return deferred.promise();
}

export function buildSelectedUTub(selectedUTub: UtubDetail): void {
  const utubDescription = selectedUTub.description;
  const isCurrentUserOwner = selectedUTub.isCreator;

  setState({
    activeUTubID: selectedUTub.id,
    activeUTubName: selectedUTub.name,
    activeUTubDescription: selectedUTub.description,
    isCurrentUserOwner: selectedUTub.isCreator,
    currentUserID: selectedUTub.currentUser,
    utubOwnerID: selectedUTub.createdByUserID,
    urls: selectedUTub.urls,
    tags: selectedUTub.tags,
    members: selectedUTub.members,
    selectedTagIDs: [],
    selectedURLCardID: null,
  });

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

  // Emit UTUB_SELECTED — deck and mobile modules self-register and handle their own setup
  emit(AppEvents.UTUB_SELECTED, {
    utubID: selectedUTub.id,
    utubName: selectedUTub.name,
    urls: selectedUTub.urls,
    tags: selectedUTub.tags,
    members: selectedUTub.members,
    utubOwnerID: selectedUTub.createdByUserID,
    isCurrentUserOwner: selectedUTub.isCreator,
    currentUserID: selectedUTub.currentUser,
  });

  // LH panels — UTub deck (same domain, direct call)
  setUTubDeckOnUTubSelected(selectedUTub.id, isCurrentUserOwner);

  // UTub Description
  const utubDescriptionHeader = $("#URLDeckSubheader");
  removeEventListenersForShowCreateUTubDescIfEmptyDesc();
  if (utubDescription) {
    utubDescriptionHeader.text(utubDescription);
    $("#UTubDescriptionSubheaderWrap").showClassFlex();
    $("#URLDeckSubheaderCreateDescription").disableTab();
    $("#URLDeckNoDescription").hideClass();
  } else {
    utubDescriptionHeader.text("");
    $("#UTubDescriptionSubheaderWrap").hideClass();
    if (isCurrentUserOwner) {
      showCreateDescriptionButtonAlways(selectedUTub.id);
      $("#URLDeckNoDescription").hideClass();
    } else {
      $("#URLDeckNoDescription").showClassNormal();
    }
  }

  if (isCurrentUserOwner) {
    $("#utubDescriptionUpdate").val($("#URLDeckSubheader").text());
  }
}

// Handles progagating changes across page related to a UTub selection
export function selectUTub(selectedUTubID: number, utubSelector: JQuery): void {
  const currentlySelected = $(".UTubSelector.active");

  // Avoid reselecting if choosing the same UTub selector
  if (currentlySelected.is($(utubSelector))) return;

  currentlySelected.removeClass("active");
  utubSelector.addClass("active");
  getSelectedUTubInfo(selectedUTubID);
}

export function getSelectedUTubInfo(selectedUTubID: number): void {
  getUTubInfo(selectedUTubID).then(
    (selectedUTub) => {
      if (!selectedUTub) return;

      buildSelectedUTub(selectedUTub);
    },
    () => {
      window.location.assign(APP_CONFIG.routes.errorPage);
    },
  );
}

// Creates UTub radio button that changes URLDeck display to show contents of the selected UTub
export function createUTubSelector(
  utubName: string,
  utubID: number,
  memberRole: string,
  index: number,
): JQuery<HTMLElement> {
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
    .onExact("click.selectUTub", function () {
      selectUTub(utubID, utubSelector);
    })
    .offAndOnExact("focus.selectUTub", function () {
      utubSelector.on(
        "keyup.selectUTub",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ENTER) selectUTub(utubID, utubSelector);
        },
      );
    })
    .offAndOnExact("blur.selectUTub", function () {
      utubSelector.off("keyup.selectUTub");
    })
    .append(utubSelectorText)
    .append(makeUTubRoleIcon(memberRole));

  return utubSelector;
}

export function setUTubSelectorEventListeners(utub: HTMLElement): void {
  const utubSelector = $(utub);
  const utubID = parseInt(utubSelector.attr("utubid")!);
  utubSelector
    // Bind display state change function on click
    .onExact("click.selectUTub", function () {
      selectUTub(utubID, utubSelector);
    })
    .offAndOnExact("focus.selectUTub", function () {
      utubSelector.on(
        "keyup.selectUTub",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ENTER) selectUTub(utubID, utubSelector);
        },
      );
    })
    .offAndOnExact("blur.selectUTub", function () {
      utubSelector.off("keyup.selectUTub");
    });
}

function makeUTubRoleIcon(memberRole: string): string {
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

export function makeUTubSelectableAgainIfMobile(utub: JQuery): void {
  $(utub).offAndOnExact("click.selectUTubMobile", function () {
    getSelectedUTubInfo(parseInt($(this).attr("utubid")!));
    $(this).off("click.selectUTubMobile");
  });
}
