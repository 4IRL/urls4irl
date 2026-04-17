import { $ } from "../lib/globals.js";
import { TABLET_WIDTH } from "../lib/constants.js";
import { on, AppEvents } from "../lib/event-bus.js";
import { NAVBAR_TOGGLER } from "./navbar.js";
import {
  resetAllDecksIfCollapsed,
  removeCollapsibleClickableHeaderClass,
  addCollapsibleClickableHeaderClass,
} from "./collapsible-decks.js";
import { getState } from "../store/app-store.js";
import { makeUTubSelectableAgainIfMobile } from "./utubs/selectors.js";

/**
 * Check if current viewport is mobile/tablet size
 */
export function isMobile(): boolean {
  return ($(window).width() ?? 0) < TABLET_WIDTH;
}

/**
 * Initialize mobile layout event listeners
 */
export function initMobileLayout(): void {
  on(AppEvents.UTUB_SELECTED, () => {
    if (isMobile()) setMobileUIWhenUTubSelectedOrURLNavSelected();
  });

  // Use matchMedia instead of resize when just need to determine if > or < than
  // specific size
  // https://webdevetc.com/blog/matchmedia-events-for-window-resizes/
  const query = matchMedia("(max-width: " + TABLET_WIDTH + "px)");
  query.addEventListener("change", function () {
    const width = $(window).width() ?? 0;

    // Handle size changes when tablet or smaller
    if (width < TABLET_WIDTH) {
      resetAllDecksIfCollapsed();
      // If UTub selected, show URL Deck
      // If no UTub selected, show UTub deck
      // Set tablet-mobile navbar depending on UTub selected or not
      if (getState().activeUTubID !== null) {
        setMobileUIWhenUTubSelectedOrURLNavSelected();
      } else {
        setMobileUIWhenUTubNotSelectedOrUTubDeleted();
      }
      removeCollapsibleClickableHeaderClass();
    } else {
      // Set full screen navbar
      // Show all panels and decks
      revertMobileUIToFullScreenUI();
      addCollapsibleClickableHeaderClass();
    }
  });
}

export function setMobileUIWhenUTubSelectedOrURLNavSelected(): void {
  $(".panel#leftPanel").addClass("hidden");
  $(".panel#centerPanel").addClass("visible-flex");
  $("button#toUTubs").removeClass("hidden");
  $("button#toMembers").removeClass("hidden");
  $("button#toTags").removeClass("hidden");
  $("button#toURLs").addClass("hidden");

  $(".deck#MemberDeck").removeClass("visible-flex");
  $(".deck#TagDeck").removeClass("visible-flex");

  NAVBAR_TOGGLER.toggler?.hide();
}

export function setMobileUIWhenUTubNotSelectedOrUTubDeleted(): void {
  $("button#toUTubs").addClass("hidden");
  $("button#toMembers").addClass("hidden");
  $("button#toTags").addClass("hidden");
  $("button#toURLs").addClass("hidden");

  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#MemberDeck").removeClass("visible-flex");
  $(".deck#TagDeck").removeClass("visible-flex");

  $(".deck#UTubDeck").removeClass("hidden");

  NAVBAR_TOGGLER.toggler?.hide();
}

export function setMobileUIWhenUTubDeckSelected(): void {
  $("button#toUTubs").addClass("hidden");
  $("button#toMembers").removeClass("hidden");
  $("button#toTags").removeClass("hidden");
  $("button#toURLs").removeClass("hidden");

  $(".panel#leftPanel").removeClass("hidden");

  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#MemberDeck").removeClass("visible-flex");
  $(".deck#TagDeck").removeClass("visible-flex");

  $(".deck#UTubDeck").removeClass("hidden");

  NAVBAR_TOGGLER.toggler?.hide();
  if ($(".UTubSelector.active").length) {
    makeUTubSelectableAgainIfMobile($(".UTubSelector.active"));
  }
}

export function setMobileUIWhenMemberDeckSelected(): void {
  $("button#toMembers").addClass("hidden");
  $(".deck#MemberDeck").addClass("visible-flex").removeClass("hidden");

  $(".panel#leftPanel").removeClass("hidden");
  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#UTubDeck").addClass("hidden");
  $(".deck#TagDeck").removeClass("visible-flex").addClass("hidden");

  $("button#toUTubs").removeClass("hidden");
  $("button#toTags").removeClass("hidden");
  $("button#toURLs").removeClass("hidden");

  NAVBAR_TOGGLER.toggler?.hide();
}

export function setMobileUIWhenTagDeckSelected(): void {
  $("button#toTags").addClass("hidden");
  $(".deck#TagDeck").addClass("visible-flex").removeClass("hidden");

  $(".panel#leftPanel").removeClass("hidden");
  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#UTubDeck").addClass("hidden");
  $(".deck#MemberDeck").removeClass("visible-flex").addClass("hidden");

  $("button#toUTubs").removeClass("hidden");
  $("button#toTags").addClass("hidden");
  $("button#toURLs").removeClass("hidden");
  $("button#toMembers").removeClass("hidden");

  NAVBAR_TOGGLER.toggler?.hide();
}

export function revertMobileUIToFullScreenUI(): void {
  NAVBAR_TOGGLER.toggler?.hide();

  $("button#toUTubs").addClass("hidden");
  $("button#toMembers").addClass("hidden");
  $("button#toTags").addClass("hidden");
  $("button#toURLs").addClass("hidden");

  $(".panel#centerPanel").removeClass("hidden");
  $(".panel#leftPanel").removeClass("hidden");

  $(".deck#UTubDeck").removeClass("hidden");
  $(".deck#MemberDeck").removeClass("hidden");
  $(".deck#TagDeck").removeClass("hidden");
}
