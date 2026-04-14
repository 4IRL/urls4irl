import { $ } from "../../../lib/globals.js";

export function isEmptyString(value: string | null | undefined): boolean {
  return !value || !value.trim();
}

export function updateColorOfFollowingURLCardsAfterURLCreated(): void {
  const urlCards = $(".urlRow[filterable=true]").toArray();
  let urlCard: JQuery;
  for (let index = 1; index < urlCards.length; index++) {
    urlCard = $(urlCards[index]);
    if (index % 2 === 0) {
      urlCard.removeClass("odd").addClass("even");
    } else {
      urlCard.removeClass("even").addClass("odd");
    }
  }
}

export function enableTabbingOnURLCardElements(urlCard: JQuery): void {
  urlCard.find(".tabbable").enableTab();
}

export function disableTabbingOnURLCardElements(urlCard: JQuery): void {
  urlCard.find(".tabbable").disableTab();
}

// Prevent editing URL title when needed
export function disableEditingURLTitle(urlCard: JQuery): void {
  const showUpdateURLTitleFormIcon = urlCard.find(".urlTitleBtnUpdate");
  if (showUpdateURLTitleFormIcon.length > 0) {
    showUpdateURLTitleFormIcon.hideClass();
  }
}

// Allow editing URL title when needed
export function enableEditingURLTitle(urlCard: JQuery): void {
  const showUpdateURLTitleFormIcon = urlCard.find(".urlTitleBtnUpdate");
  if (showUpdateURLTitleFormIcon.length > 0) {
    showUpdateURLTitleFormIcon.removeHideClass();
  }
}
