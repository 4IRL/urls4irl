"use strict";

const SHOW_LOADING_ICON_AFTER_MS = 50;

function updateColorOfFollowingURLCardsAfterURLCreated() {
  const urlCards = $(".urlRow[filterable=true]").toArray();
  let urlCard;
  for (let i = 1; i < urlCards.length; i++) {
    urlCard = $(urlCards[i]);
    if (i % 2 === 0) {
      urlCard.removeClass("odd").addClass("even");
    } else {
      urlCard.removeClass("even").addClass("odd");
    }
  }
}

function enableTabbingOnURLCardElements(urlCard) {
  urlCard.find(".tabbable").enableTab();
}

function disableTabbingOnURLCardElements(urlCard) {
  urlCard.find(".tabbable").disableTab();
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
