import { $ } from "../../../lib/globals.js";

export function isEmptyString(str) {
  return !str || !str.trim();
}

export function updateColorOfFollowingURLCardsAfterURLCreated() {
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

export function enableTabbingOnURLCardElements(urlCard) {
  urlCard.find(".tabbable").enableTab();
}

export function disableTabbingOnURLCardElements(urlCard) {
  urlCard.find(".tabbable").disableTab();
}

// Prevent editing URL title when needed
export function disableEditingURLTitle(urlCard) {
  const showUpdateURLTitleFormIcon = urlCard.find(".urlTitleBtnUpdate");
  if (showUpdateURLTitleFormIcon.length > 0) {
    showUpdateURLTitleFormIcon.hideClass();
  }
}

// Allow editing URL title when needed
export function enableEditingURLTitle(urlCard) {
  const showUpdateURLTitleFormIcon = urlCard.find(".urlTitleBtnUpdate");
  if (showUpdateURLTitleFormIcon.length > 0) {
    showUpdateURLTitleFormIcon.removeHideClass();
  }
}
