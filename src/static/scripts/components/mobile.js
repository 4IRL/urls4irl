"use strict";

const TABLET_WIDTH = 992;

$(document).ready(function () {
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

function setMobileUIWhenUTubSelectedOrURLNavSelected() {
  $(".panel#leftPanel").addClass("hidden");
  $(".panel#centerPanel").addClass("visible-flex");
  $(".home#toUTubs").removeClass("hidden");
  $(".home#toMembers").removeClass("hidden");
  $(".home#toTags").removeClass("hidden");

  $(".deck#MemberDeck").removeClass("visible-flex");
  $(".deck#TagDeck").removeClass("visible-flex");

  NAVBAR_TOGGLER.toggler.hide();
}

function setMobileUIWhenUTubNotSelectedOrUTubDeleted() {
  $(".home#toUTubs").addClass("hidden");
  $(".home#toMembers").addClass("hidden");
  $(".home#toTags").addClass("hidden");
  $(".home#toURLs").addClass("hidden");

  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#MemberDeck").removeClass("visible-flex");
  $(".deck#TagDeck").removeClass("visible-flex");

  $(".deck#UTubDeck").removeClass("hidden");

  NAVBAR_TOGGLER.toggler.hide();
}

function setMobileUIWhenUTubDeckSelected() {
  $(".home#toUTubs").addClass("hidden");
  $(".home#toMembers").removeClass("hidden");
  $(".home#toTags").removeClass("hidden");
  $(".home#toURLs").removeClass("hidden");

  $(".panel#leftPanel").removeClass("hidden");

  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#MemberDeck").removeClass("visible-flex");
  $(".deck#TagDeck").removeClass("visible-flex");

  $(".deck#UTubDeck").removeClass("hidden");

  NAVBAR_TOGGLER.toggler.hide();
}

function setMobileUIWhenMemberDeckSelected() {
  $(".home#toMembers").addClass("hidden");
  $(".deck#MemberDeck").addClass("visible-flex").removeClass("hidden");

  $(".panel#leftPanel").removeClass("hidden");
  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#UTubDeck").addClass("hidden");
  $(".deck#TagDeck").addClass("hidden");

  $(".home#toUTubs").removeClass("hidden");
  $(".home#toTags").removeClass("hidden");
  $(".home#toURLs").removeClass("hidden");

  NAVBAR_TOGGLER.toggler.hide();
}

function setMobileUIWhenTagDeckSelected() {
  $(".home#toTags").addClass("hidden");
  $(".deck#TagDeck").addClass("visible-flex").removeClass("hidden");

  $(".panel#leftPanel").removeClass("hidden");
  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#UTubDeck").addClass("hidden");
  $(".deck#MemberDeck").addClass("hidden");

  $(".home#toUTubs").removeClass("hidden");
  $(".home#toTags").removeClass("hidden");
  $(".home#toURLs").removeClass("hidden");
  $(".home#toMembers").removeClass("hidden");

  NAVBAR_TOGGLER.toggler.hide();
}

function revertMobileUIToFullScreenUI() {
  NAVBAR_TOGGLER.toggler.hide();

  $(".home#toUTubs").addClass("hidden");
  $(".home#toMembers").addClass("hidden");
  $(".home#toTags").addClass("hidden");
  $(".home#toURLs").addClass("hidden");

  $(".panel#centerPanel").removeClass("hidden");
  $(".panel#leftPanel").removeClass("hidden");

  $(".deck#UTubDeck").removeClass("hidden");
  $(".deck#MemberDeck").removeClass("hidden");
  $(".deck#TagDeck").removeClass("hidden");
}
